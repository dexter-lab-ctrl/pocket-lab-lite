#!/usr/bin/env python3
"""Pocket Lab Lite desired-state runtime reconciler.

The reconciler is intentionally narrower than bootstrap:
- it never installs packages, upgrades binaries, initializes databases, or
  downloads applications;
- it reconstructs missing Lite PM2 definitions through the repository-owned
  reconcile script;
- it records sanitized evidence and uses a bounded repair budget;
- transient network loss is evidence, not a reason to restart the control plane.

PM2 itself is supervised outside PM2 by the Termux boot/runtime guardian.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping

from pocketlab_runtime_registry import (
    CONTROL_PLANE_SERVICES,
    LEGACY_LITE_SERVICES,
    PHOTOPRISM_SPEC,
    RECONCILER_SPEC,
    REPAIRABLE_PM2_STATUSES,
    launch_fingerprint,
    policy_fingerprint,
    policy_match,
)
from pocketlab_runtime_contract import build_runtime_contract

_STOP = False
VERSION = "1.0.0-lite-desired-state"
DEFAULT_INTERVAL_SECONDS = 45
DEFAULT_COOLDOWN_SECONDS = 120
DEFAULT_WINDOW_SECONDS = 1800
DEFAULT_MAX_REPAIRS = 3
MAX_INTERVAL_SECONDS = 3600
MAX_COOLDOWN_SECONDS = 24 * 60 * 60
MAX_WINDOW_SECONDS = 30 * 24 * 60 * 60

# PM2 does not keep every projection field authoritative while a process is
# stopped, errored, or transitioning between lifecycle states.  Treat those
# observations as transient and let the lifecycle owner restore the process
# before evaluating version, policy, or desired-spec metadata.  Rebuilding a
# stopped definition from those transient fields can create a restart loop on
# PM2 7/Termux and consume the bounded runtime restart budget.
TRANSIENT_PM2_STATUSES = frozenset(
    {
        "missing",
        "stopped",
        "errored",
        "error",
        "stopping",
        "launching",
        "waiting restart",
    }
)

# PM2 7/Termux exposes the managed process projection in the child
# environment. Passing those fields to another PM2 CLI invocation can make
# the daemon reuse the current definition's executable for the next
# ecosystem launch. Keep PM2_HOME so the child targets the same daemon, but
# remove all other PM2 control metadata and lowercase PM2/app markers.
PM2_CHILD_ENV_KEYS = frozenset(
    {
        "PM2_USAGE",
        "PM2_JSON_PROCESSING",
        "pm_id",
        "name",
        "unique_id",
        "namespace",
        "cwd",
        "exec_interpreter",
        "exec_mode",
        "pm_cwd",
        "pm_exec_path",
        "pm_out_log_path",
        "pm_err_log_path",
        "pm_pid_path",
        "pm_uptime",
        "status",
        "restart_time",
        "unstable_restarts",
        "version",
        "max_memory_restart",
        "exp_backoff_restart_delay",
        "kill_timeout",
        "max_restarts",
        "min_uptime",
        "autorestart",
        "autostart",
        "instances",
        "instance_var",
        "treekill",
        "merge_logs",
        "vizion",
        "vizion_running",
        "automation",
        "pmx",
        "io",
        "km_link",
        "username",
        "windowsHide",
        "kill_retry_time",
        "created_at",
    }
)


def _sanitize_child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Remove PM2-owned launch metadata before invoking convergence scripts."""

    environment = dict(os.environ if source is None else source)
    for key in tuple(environment):
        if (
            key in PM2_CHILD_ENV_KEYS
            or (key.startswith("PM2_") and key != "PM2_HOME")
            or key[:1].islower()
        ):
            environment.pop(key, None)
    return environment


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(maximum, value))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run(args: list[str], timeout: float = 15.0, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout, env=env)


def lifecycle_transition_active() -> bool:
    """Return whether the repository-owned dashboard lifecycle is mutating PM2.

    The startup/reconcile shell path holds this lock while it replaces or
    reloads process definitions. PM2 7 on Termux can briefly report a sibling
    definition as missing during that queue drain. A concurrent reconciler
    repair must observe the transition and defer its own mutation until the
    lifecycle owner has finished.
    """

    lock_path = Path(
        os.environ.get(
            "POCKETLAB_START_DASHBOARD_LOCK",
            Path.home() / ".pocket_lab" / "locks" / "start-dashboard.sh.lock",
        )
    ).expanduser()
    if not lock_path.exists():
        return False
    if not lock_path.is_dir():
        try:
            with lock_path.open("a+", encoding="utf-8") as handle:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    # The lifecycle owner may have created the file before
                    # writing metadata. The kernel lock is authoritative.
                    return True
                finally:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        except OSError:
            pass
    try:
        metadata = lock_path / "metadata" if lock_path.is_dir() else lock_path
        values: dict[str, str] = {}
        for line in metadata.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key.strip()] = value.strip()
        owner_pid = int(values.get("pid", "0"))
    except (OSError, ValueError, TypeError):
        return False
    if owner_pid <= 0:
        return False
    try:
        os.kill(owner_pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def load_pm2_processes() -> list[dict[str, Any]]:
    try:
        result = _run(["pm2", "jlist"], timeout=10)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        payload = json.loads(result.stdout)
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def pm2_statuses(processes: Iterable[dict[str, Any]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in processes:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        values[name] = str(env.get("status") or item.get("status") or "unknown").strip().lower()
    return values


def pm2_version_projection(processes: Iterable[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    tracked = {spec.name for spec in CONTROL_PLANE_SERVICES}
    tracked.add(RECONCILER_SPEC.name)
    tracked.add("pocketlab-app-photoprism")
    versions: dict[str, str] = {}
    reasons: list[str] = []
    for item in processes:
        name = str(item.get("name") or "").strip()
        if name not in tracked:
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        status = str(env.get("status") or item.get("status") or "unknown").strip().lower()
        version = str(env.get("version") or "").strip()
        declared = str(env.get("POCKETLAB_SERVICE_VERSION") or "").strip()
        versions[name] = version or "unavailable"
        if status in TRANSIENT_PM2_STATUSES:
            continue
        if not version or version.lower() in {"n/a", "na", "unknown"} or version != declared:
            reasons.append(f"pm2_version_projection:{name}")
    return versions, reasons


def pm2_policy_reasons(
    processes: Iterable[dict[str, Any]],
    *,
    include_photoprism: bool = False,
) -> list[str]:
    """Return desired PM2 policy drift without exposing process environment."""

    tracked = [*CONTROL_PLANE_SERVICES, RECONCILER_SPEC]
    if include_photoprism:
        tracked.append(PHOTOPRISM_SPEC)
    by_name = {
        str(item.get("name") or "").strip(): item
        for item in processes
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    reasons: list[str] = []
    for spec in tracked:
        item = by_name.get(spec.name)
        if not item:
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        status = str(env.get("status") or item.get("status") or "unknown").strip().lower()
        if status in TRANSIENT_PM2_STATUSES:
            continue
        matches, fields = policy_match(spec.name, env)
        expected_fingerprint = policy_fingerprint(spec.name)
        observed_fingerprint = str(env.get("POCKETLAB_PM2_POLICY_FINGERPRINT") or "").strip()
        if not matches or not expected_fingerprint or observed_fingerprint != expected_fingerprint:
            detail = ",".join(fields) if fields else "fingerprint"
            reasons.append(f"pm2_policy:{spec.name}:{detail}")
    return reasons


_IDENTITY_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_SOURCE = re.compile(r"^[0-9a-f]{40}$")
_IDENTITY_GENERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _identity_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _process_identity(item: Mapping[str, Any] | None, name: str) -> tuple[str, bool]:
    """Hash only the bounded, non-secret PM2 identity projection."""

    if not isinstance(item, Mapping):
        return _identity_digest({"service": name, "status": "missing"}), False
    env = item.get("pm2_env") if isinstance(item.get("pm2_env"), Mapping) else {}
    status = str(env.get("status") or item.get("status") or "unknown").strip().lower()
    observed = {
        "service": name,
        "status": status,
        "pid": int(item.get("pid") or env.get("pid") or 0),
        "started_at": int(env.get("pm_uptime") or 0),
        "version": str(env.get("version") or "")[:120],
        "declared_version": str(env.get("POCKETLAB_SERVICE_VERSION") or "")[:120],
        "exec_path": str(env.get("pm_exec_path") or item.get("pm_exec_path") or "")[:512],
        "cwd": str(env.get("pm_cwd") or env.get("cwd") or item.get("cwd") or "")[:512],
    }
    healthy = status == "online" and bool(observed["pid"] and observed["exec_path"] and observed["cwd"])
    return _identity_digest(observed), healthy


def _bounded_json(path: Path, *, limit: int = 64 * 1024) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _source_inventory_digest(root: Path) -> str:
    """Bounded content inventory for a source-checkout fallback.

    Release installs normally use the authenticated artifact manifest.  The
    fallback is deliberately bounded and includes bytes, mode and content so
    a checkout path or Git SHA alone cannot become installed-source proof.
    """

    rows: list[dict[str, Any]] = []
    total = 0
    try:
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative.startswith(".git/"):
                continue
            size = path.stat().st_size
            total += size
            if len(rows) >= 12_000 or total > 128 * 1024 * 1024:
                return _identity_digest({"root": str(root), "status": "inventory_limit"})
            rows.append({
                "path": relative,
                "size": size,
                "mode": path.stat().st_mode & 0o777,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    except OSError:
        return _identity_digest({"root": str(root), "status": "inventory_unavailable"})
    return _identity_digest({"root": "runtime", "files": rows})


def publish_runtime_identity(*, processes: Iterable[dict[str, Any]], runtime_contract: Mapping[str, Any], state_root: Path) -> dict[str, Any]:
    """Publish independently observed component identity from the reconciler.

    This is an owner-side operation, never a request/GET probe.  Any missing
    or contradictory observation is recorded as ``degraded`` so the prepared
    execution gate remains closed until a later owner observation converges.
    """

    runtime_root = Path(__file__).resolve().parents[1]
    by_name = {
        str(item.get("name") or ""): item
        for item in processes
        if isinstance(item, dict) and str(item.get("name") or "")
    }
    pointer = _bounded_json(state_root / "backend-runtime" / "active.json")
    release_root = Path(str(pointer.get("release_root") or "")) if pointer.get("release_root") else None
    # The authenticated backend manifest contains the complete runtime file
    # inventory.  It is intentionally bounded, but the repository's current
    # dependency-complete artifact is larger than the active-pointer bound.
    # Keep the pointer strict while allowing the signed inventory to be read
    # within its separate finite envelope.
    manifest = _bounded_json(release_root / "artifact-manifest.json", limit=512 * 1024) if release_root else {}

    source_commit = str(pointer.get("source_commit") or manifest.get("source_commit") or "").lower()
    if not _IDENTITY_SOURCE.fullmatch(source_commit):
        source_commit = "0" * 40
    artifact_sha = str(pointer.get("artifact_sha256") or "").lower()
    artifact_observed = bool(_IDENTITY_SHA256.fullmatch(artifact_sha))
    if not artifact_observed:
        artifact_sha = _identity_digest({"status": "backend_artifact_unavailable"})
    source_inventory = str(manifest.get("payload_sha256") or "").lower()
    inventory_observed = bool(_IDENTITY_SHA256.fullmatch(source_inventory))
    if not inventory_observed:
        source_inventory = _source_inventory_digest(runtime_root)

    try:
        from api_fastapi.db import migrations
        from api_fastapi.db.connection import connection
        from api_fastapi.services import lite_policy_runtime_evidence, lite_runtime_identity, release_runtime

        installed = release_runtime.read_installed_identity()
        frontend_tag = str(installed.get("release_tag") or "").strip()
        frontend_observed = bool(installed.get("verified") is True and frontend_tag)
        if not frontend_tag:
            frontend_tag = "frontend-unavailable"
        policy = lite_policy_runtime_evidence.observe()
        rows = migrations.migration_rows()
        schema_version = max((int(row.get("version") or 0) for row in rows), default=0)
        ledger_sha = _identity_digest({"migrations": rows})
        policy_revision = str(policy.get("observed_revision") or "unavailable")
        module_sha = str(policy.get("module_identity_sha256") or "").lower()
        data_sha = str(policy.get("data_identity_sha256") or "").lower()
        policy_observed = bool(
            policy.get("state") == "modules_match"
            and policy.get("data_identity") == "registered_template_matches"
            and policy.get("manifest_data_identity") == "registered_roots_match"
            and _IDENTITY_SHA256.fullmatch(module_sha)
            and _IDENTITY_SHA256.fullmatch(data_sha)
            and policy_revision != "unavailable"
        )
        if not _IDENTITY_SHA256.fullmatch(module_sha):
            module_sha = _identity_digest({"status": "policy_module_unavailable"})
        if not _IDENTITY_SHA256.fullmatch(data_sha):
            data_sha = _identity_digest({"status": "policy_data_unavailable"})

        process_identities = {
            name: _process_identity(by_name.get(name), name)
            for name in (
                "pocket-api",
                "pocket-worker",
                "pocketlab-core-supervisor",
                "pocketlab-runtime-reconciler",
            )
        }
        process_ok = all(item[1] for item in process_identities.values())
        generation = str(pointer.get("generation") or "").strip()
        generation_observed = bool(_IDENTITY_GENERATION.fullmatch(generation))
        if not generation_observed:
            generation = "runtime-" + _identity_digest({
                "source": source_commit,
                "artifact": artifact_sha,
                "frontend": frontend_tag,
                "policy": policy_revision,
                "ledger": ledger_sha,
            })[:32]

        stable = bool(
            pointer.get("kind") == "artifact"
            and _IDENTITY_SOURCE.fullmatch(source_commit)
            and source_commit != "0" * 40
            and artifact_observed
            and inventory_observed
            and frontend_observed
            and policy_observed
            and schema_version > 0
            and process_ok
            and runtime_contract.get("stable") is True
            and generation_observed
        )
        observation = lite_runtime_identity.build_observation(
            status="stable" if stable else "degraded",
            reason_code="converged" if stable else "runtime_identity_incomplete",
            coordinated_generation=generation,
            authenticated_source_commit=source_commit,
            installed_artifact_sha256=artifact_sha,
            installed_source_inventory_sha256=source_inventory,
            fastapi_process_identity_sha256=process_identities["pocket-api"][0],
            worker_process_identity_sha256=process_identities["pocket-worker"][0],
            core_supervisor_identity_sha256=process_identities["pocketlab-core-supervisor"][0],
            runtime_reconciler_identity_sha256=process_identities["pocketlab-runtime-reconciler"][0],
            loaded_policy_revision=policy_revision,
            loaded_policy_module_sha256=module_sha,
            loaded_policy_data_sha256=data_sha,
            frontend_generation=frontend_tag,
            sqlite_schema_version=max(schema_version, 1),
            sqlite_migration_ledger_sha256=ledger_sha,
        )
        with connection() as conn:
            projection = lite_runtime_identity.record(conn, observation)
        return {
            "status": "PASS" if stable else "DEGRADED",
            "projection": projection,
            "independent_sources": {
                "backend_pointer": pointer.get("kind", "missing"),
                "backend_artifact_manifest": bool(manifest),
                "loaded_opa_observation": policy_observed,
                "process_projection": process_ok,
                "frontend_installed_marker": frontend_observed,
                "sqlite_migration_ledger": schema_version > 0,
            },
            "sanitized": True,
        }
    except Exception as exc:
        return {"status": "DEGRADED", "reason_code": "runtime_identity_observation_failed", "error_type": type(exc).__name__, "sanitized": True}


def pm2_desired_spec_reasons(
    processes: Iterable[dict[str, Any]],
    *,
    state_root: Path,
    include_photoprism: bool = False,
) -> list[str]:
    """Detect a running PM2 definition that differs from startup's desired hash."""
    evidence_path = state_root / "runtime" / "desired-process-specs.json"
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return ["pm2_desired_specs_unavailable"]
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != "pocketlab.pm2-desired-process-specs/v1"
        or not isinstance(evidence.get("schema_version"), int)
        or isinstance(evidence.get("schema_version"), bool)
        or evidence.get("schema_version") != 1
        or evidence.get("sanitized") is not True
        or not isinstance(evidence.get("processes"), dict)
    ):
        return ["pm2_desired_specs_invalid"]
    expected = evidence["processes"]
    expected_launches = evidence.get("launches") if isinstance(evidence.get("launches"), dict) else {}
    observed_items = {
        str(item.get("name") or ""): item
        for item in processes
        if isinstance(item, dict) and str(item.get("name") or "")
    }
    observed = {
        name: str(
            (item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}).get(
                "POCKETLAB_PROCESS_SPEC_HASH"
            ) or ""
        ).strip().lower()
        for name, item in observed_items.items()
    }
    specs = [*CONTROL_PLANE_SERVICES, RECONCILER_SPEC]
    if include_photoprism:
        specs.append(PHOTOPRISM_SPEC)
    reasons: list[str] = []
    observed_launches = {
        str(item.get("name") or ""): launch_fingerprint(
            str((item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}).get("pm_exec_path") or ""),
            str((item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}).get("exec_interpreter") or ""),
        )
        for item in observed_items.values()
    }
    for spec in specs:
        if spec.name not in observed:
            continue
        item = observed_items.get(spec.name)
        env = item.get("pm2_env") if isinstance(item, dict) and isinstance(item.get("pm2_env"), dict) else {}
        status = str(env.get("status") or (item or {}).get("status") or "unknown").strip().lower()
        if status in TRANSIENT_PM2_STATUSES:
            continue
        desired = str(expected.get(spec.name) or "").strip().lower()
        if not desired:
            reasons.append(f"pm2_desired_spec_missing:{spec.name}")
        elif observed[spec.name] != desired:
            reasons.append(f"pm2_desired_spec_mismatch:{spec.name}")
        desired_launch = str(expected_launches.get(spec.name) or "").strip().lower()
        observed_launch = observed_launches.get(spec.name, "")
        if not desired_launch:
            reasons.append(f"pm2_desired_launch_missing:{spec.name}")
        elif observed_launch != desired_launch:
            reasons.append(f"pm2_desired_launch_mismatch:{spec.name}")
    return reasons


def repair_reasons(statuses: dict[str, str]) -> list[str]:
    """Return only reconstruction-class drift.

    Health-level recovery remains owned by the existing core supervisor. This
    avoids a second restart loop and intentionally ignores stopped/errored
    states when the process definition still exists. The reconciler only
    reconstructs a definition that PM2 no longer reports at all.
    """
    reasons: list[str] = []
    for spec in CONTROL_PLANE_SERVICES:
        status = str(statuses.get(spec.name) or "missing").lower()
        if status == "missing":
            reasons.append(f"pm2_definition_or_process:{spec.name}:{status}")
    return reasons


def tailscale_state() -> dict[str, bool]:
    cli = ""
    for candidate in ("tailscale-cli", "tailscale"):
        try:
            if _run(["sh", "-lc", f"command -v {candidate}"], timeout=3).returncode == 0:
                cli = candidate
                break
        except Exception:
            pass
    daemon_running = False
    try:
        daemon_running = _run(["sh", "-lc", "pgrep -f tailscaled >/dev/null 2>&1"], timeout=3).returncode == 0
    except Exception:
        daemon_running = False

    ipv4_ready = False
    if daemon_running and cli:
        try:
            result = _run([cli, "ip", "-4"], timeout=5)
            ipv4_ready = result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            ipv4_ready = False
    return {
        "installed": bool(cli),
        "daemon_running": daemon_running,
        "ipv4_ready": ipv4_ready,
    }


def remote_reconcile_reasons(current: dict[str, bool], previous: dict[str, Any] | None) -> list[str]:
    """Distinguish network loss from repairable remote-access drift.

    A running Tailscale daemon with no current IPv4 may simply reflect Wi-Fi or
    upstream loss. That state is observable but must not restart Pocket Lab.
    """
    reasons: list[str] = []
    if current.get("installed") and not current.get("daemon_running"):
        reasons.append("tailscaled_missing")
        return reasons
    prior = previous if isinstance(previous, dict) else {}
    if (
        current.get("daemon_running")
        and current.get("ipv4_ready")
        and prior.get("ipv4_ready") is False
    ):
        reasons.append("tailscale_ready_transition")
    return reasons


def photoprism_expected() -> bool:
    root = Path(os.environ.get("POCKETLAB_PHOTOPRISM_ROOT", Path.home() / ".pocket_lab/lite/apps/photoprism")).expanduser()
    return (root / "config" / "photoprism.env").is_file() or (root / "config" / "install-manifest.json").is_file()


def proot_ubuntu_ready() -> bool:
    try:
        return _run(["proot-distro", "login", "ubuntu", "--", "true"], timeout=8).returncode == 0
    except Exception:
        return False


def photoprism_reconcile_reasons(statuses: dict[str, str]) -> list[str]:
    if not photoprism_expected():
        return []
    if not proot_ubuntu_ready():
        return ["proot_ubuntu_unavailable"]
    status = str(statuses.get("pocketlab-app-photoprism") or "missing").lower()
    if status in REPAIRABLE_PM2_STATUSES:
        return [f"photoprism_process:{status}"]
    return []


class RuntimeReconciler:
    def __init__(self) -> None:
        self.interval = _bounded_env_int("POCKETLAB_RUNTIME_RECONCILE_SECONDS", DEFAULT_INTERVAL_SECONDS, 10, MAX_INTERVAL_SECONDS)
        self.cooldown = _bounded_env_int("POCKETLAB_RUNTIME_RECONCILE_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS, 30, MAX_COOLDOWN_SECONDS)
        self.window = _bounded_env_int("POCKETLAB_RUNTIME_RECONCILE_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS, 300, MAX_WINDOW_SECONDS)
        self.max_repairs = _bounded_env_int("POCKETLAB_RUNTIME_RECONCILE_MAX_REPAIRS", DEFAULT_MAX_REPAIRS, 1, 10)
        base = Path(os.environ.get("POCKETLAB_STATE_DIR", Path.home() / "pocket-lab-lite" / "state")).expanduser()
        self.state_dir = base / "runtime-reconciler"
        self.state_file = self.state_dir / "state.json"
        self.events_file = self.state_dir / "events.jsonl"
        self.repair_history: list[float] = []
        self.last_repair_at = 0.0
        self.repo_root = Path(__file__).resolve().parents[3]
        self.reconcile_script = (
            self.repo_root
            / "pocket-lab-final-structure"
            / "pocket-lab-bootstrap-production-scripts-patched"
            / "scripts"
            / "lite"
            / "reconcile-runtime.sh"
        )

    def _acquire_singleton(self):
        """Keep only one reconciler loop active per Lite state directory."""

        self.state_dir.mkdir(parents=True, exist_ok=True)
        handle = (self.state_dir / "active.lock").open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
        return handle

    def _load_previous(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_file.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _write_json(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.state_file)

    def _event(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        safe = {
            "event": str(payload.get("event") or "runtime_reconcile"),
            "reason": str(payload.get("reason") or "")[:160],
            "acted": bool(payload.get("acted")),
            "result": str(payload.get("result") or "")[:80],
            "at": _now_iso(),
        }
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, sort_keys=True) + "\n")

    def _admit_repair(self) -> tuple[bool, str]:
        now = time.time()
        self.repair_history = [value for value in self.repair_history if now - value <= self.window]
        if now - self.last_repair_at < self.cooldown:
            return False, "cooldown"
        if len(self.repair_history) >= self.max_repairs:
            return False, "repair_budget"
        return True, ""

    def _repair(self, reasons: list[str]) -> dict[str, Any]:
        allowed, blocked = self._admit_repair()
        reason = reasons[0] if reasons else "desired_state_drift"
        if not allowed:
            event = {"event": "runtime_reconcile_suppressed", "reason": blocked, "acted": False, "result": reason}
            self._event(event)
            return event
        if not self.reconcile_script.is_file():
            event = {"event": "runtime_reconcile_unavailable", "reason": "reconcile_script_missing", "acted": False, "result": "missing"}
            self._event(event)
            return event
        env = _sanitize_child_environment()
        # Service-specific PM2 projection metadata belongs to this reconciler
        # process only. Never leak it into child convergence, where --update-env
        # or a process-spec hash could otherwise stamp another service with the
        # reconciler's version identity.
        env.pop("POCKETLAB_SERVICE_VERSION", None)
        env.pop("POCKETLAB_PM2_SERVICE_VERSION", None)
        # Reconciliation must derive canonical Server Phone runtime paths from
        # the current checkout. Stale PM2/resurrected DEV overrides such as
        # .pocketlab-dev/state must never leak into OPA or SQLite on Termux.
        for key in (
            "POCKETLAB_BASE_DIR",
            "POCKETLAB_STATE_DIR",
            "POCKETLAB_LITE_DB_PATH",
            "POCKETLAB_OPA_ACTIVE_POLICY_DIR",
            # PM2 injects these path fields into managed processes. They are
            # removed here as well as by the general PM2 metadata filter so
            # this boundary remains explicit for future additions.
            "pm_id",
            "name",
            "unique_id",
            "pm_exec_path",
            "pm_cwd",
            "pm_out_log_path",
            "pm_err_log_path",
            "pm_pid_path",
        ):
            env.pop(key, None)
        env["POCKETLAB_PROFILE"] = "lite"
        env["POCKETLAB_LITE"] = "1"
        try:
            result = _run(["bash", str(self.reconcile_script), "--repair", "--reason", reason], timeout=240, env=env)
            acted = result.returncode == 0
        except Exception:
            acted = False
        now = time.time()
        if acted:
            self.last_repair_at = now
            self.repair_history.append(now)
        event = {
            "event": "runtime_reconcile_attempted",
            "reason": reason,
            "acted": acted,
            "result": "converged" if acted else "failed",
        }
        self._event(event)
        return event

    def tick(self) -> dict[str, Any]:
        previous = self._load_previous()
        processes = load_pm2_processes()
        statuses = pm2_statuses(processes)
        versions, version_reasons = pm2_version_projection(processes)
        remote = tailscale_state()
        reasons = repair_reasons(statuses)
        reasons.extend(version_reasons)
        reasons.extend(pm2_policy_reasons(processes, include_photoprism=photoprism_expected()))
        reasons.extend(pm2_desired_spec_reasons(
            processes,
            state_root=self.state_dir.parent,
            include_photoprism=photoprism_expected(),
        ))
        reasons.extend(remote_reconcile_reasons(remote, previous.get("remote_access")))
        reasons.extend(photoprism_reconcile_reasons(statuses))
        actions: list[dict[str, Any]] = []
        controlled = None
        try:
            runtime_root = str(Path(__file__).resolve().parents[1])
            if runtime_root not in sys.path:
                sys.path.insert(0,runtime_root)
            from api_fastapi.services import lite_infrastructure_configuration
            controlled=lite_infrastructure_configuration.process(self,reasons,lifecycle_transition_active())
        except Exception:
            pass
        if controlled is not None:
            actions.append(controlled)
            processes=load_pm2_processes()
            statuses=pm2_statuses(processes)
            versions,_=pm2_version_projection(processes)
            remote=tailscale_state()
        elif reasons:
            if lifecycle_transition_active():
                event = {
                    "event": "runtime_reconcile_suppressed",
                    "reason": "lifecycle_transition",
                    "acted": False,
                    "result": reasons[0],
                }
                self._event(event)
                actions.append(event)
            else:
                actions.append(self._repair(reasons))
                processes = load_pm2_processes()
                statuses = pm2_statuses(processes)
                versions, _ = pm2_version_projection(processes)
                remote = tailscale_state()
        legacy_present = sorted(name for name in statuses if name in LEGACY_LITE_SERVICES)
        runtime_contract = build_runtime_contract(
            processes=processes,
            state_root=self.state_dir.parent,
            photoprism_expected=photoprism_expected(),
            repairing=bool(reasons or actions),
            remote_access=remote,
        )
        runtime_identity = publish_runtime_identity(
            processes=processes,
            runtime_contract=runtime_contract,
            state_root=self.state_dir.parent,
        )
        payload = {
            "reconciler": "pocketlab-runtime-reconciler",
            "version": VERSION,
            "status": "degraded" if reasons else "healthy",
            "services": {spec.name: statuses.get(spec.name, "missing") for spec in CONTROL_PLANE_SERVICES},
            "service_versions": {name: versions.get(name, "unavailable") for name in statuses if name in versions},
            "remote_access": remote,
            "drift_reasons": reasons,
            "actions": actions,
            "runtime_contract": {
                "schema_version": runtime_contract.get("schema_version"),
                "state": runtime_contract.get("state"),
                "stable": runtime_contract.get("stable"),
                "reason_codes": runtime_contract.get("reason_codes"),
                "observed_at": runtime_contract.get("observed_at"),
            },
            "runtime_identity": runtime_identity,
            "legacy_lite_services_present": legacy_present,
            "legacy_lite_services_allowed": False,
            "checked_at": _now_iso(),
            "sanitized": True,
        }
        self._write_json(payload)
        try:
            runtime_root = str(Path(__file__).resolve().parents[1])
            if runtime_root not in sys.path:
                sys.path.insert(0, runtime_root)
            from api_fastapi.services import lite_infrastructure_service_evidence
            lite_infrastructure_service_evidence.verify_runtime_contract(runtime_contract, processes)
            from api_fastapi.services import lite_infrastructure_configuration
            lite_infrastructure_configuration.verify(self.state_dir.parent,runtime_contract,processes)
        except Exception:
            # Evidence failure must not change the existing reconciliation owner.
            pass
        return payload

    def run(self) -> None:
        singleton = self._acquire_singleton()
        if singleton is None:
            return
        try:
            while not _STOP:
                try:
                    self.tick()
                except Exception as exc:
                    self._event(
                        {
                            "event": "runtime_reconcile_check_failed",
                            "reason": type(exc).__name__,
                            "acted": False,
                            "result": "degraded",
                        }
                    )
                time.sleep(self.interval)
        finally:
            try:
                fcntl.flock(singleton.fileno(), fcntl.LOCK_UN)
            finally:
                singleton.close()


def _stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    RuntimeReconciler().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
