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

import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Iterable

from pocketlab_runtime_registry import (
    CONTROL_PLANE_SERVICES,
    LEGACY_LITE_SERVICES,
    PHOTOPRISM_SPEC,
    RECONCILER_SPEC,
    REPAIRABLE_PM2_STATUSES,
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
        version = str(env.get("version") or "").strip()
        declared = str(env.get("POCKETLAB_SERVICE_VERSION") or "").strip()
        versions[name] = version or "unavailable"
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
        matches, fields = policy_match(spec.name, env)
        expected_fingerprint = policy_fingerprint(spec.name)
        observed_fingerprint = str(env.get("POCKETLAB_PM2_POLICY_FINGERPRINT") or "").strip()
        if not matches or not expected_fingerprint or observed_fingerprint != expected_fingerprint:
            detail = ",".join(fields) if fields else "fingerprint"
            reasons.append(f"pm2_policy:{spec.name}:{detail}")
    return reasons


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
    observed = {
        str(item.get("name") or ""): str(
            (item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}).get(
                "POCKETLAB_PROCESS_SPEC_HASH"
            ) or ""
        ).strip().lower()
        for item in processes
        if isinstance(item, dict)
    }
    specs = [*CONTROL_PLANE_SERVICES, RECONCILER_SPEC]
    if include_photoprism:
        specs.append(PHOTOPRISM_SPEC)
    reasons: list[str] = []
    for spec in specs:
        if spec.name not in observed:
            continue
        desired = str(expected.get(spec.name) or "").strip().lower()
        if not desired:
            reasons.append(f"pm2_desired_spec_missing:{spec.name}")
        elif observed[spec.name] != desired:
            reasons.append(f"pm2_desired_spec_mismatch:{spec.name}")
    return reasons


def repair_reasons(statuses: dict[str, str]) -> list[str]:
    """Return only reconstruction-class drift.

    Health-level recovery remains owned by the existing core supervisor. This
    avoids a second restart loop and intentionally ignores transient states such
    as "waiting restart" when the process definition still exists.
    """
    reasons: list[str] = []
    for spec in CONTROL_PLANE_SERVICES:
        status = str(statuses.get(spec.name) or "missing").lower()
        if status in REPAIRABLE_PM2_STATUSES:
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
        env = os.environ.copy()
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
        ):
            env.pop(key, None)
        env["POCKETLAB_PROFILE"] = "lite"
        env["POCKETLAB_LITE"] = "1"
        env["POCKETLAB_RECONCILER_CHILD"] = "1"
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
        if reasons:
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
            "legacy_lite_services_present": legacy_present,
            "legacy_lite_services_allowed": False,
            "checked_at": _now_iso(),
            "sanitized": True,
        }
        self._write_json(payload)
        return payload

    def run(self) -> None:
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
