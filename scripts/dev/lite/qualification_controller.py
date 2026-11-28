#!/usr/bin/env python3
"""Resumable, run-owned coordinator for Trusted Lifecycle qualification.

The existing ``run-coordinated-runtime-qualification.py`` remains the fast
preflight entry point.  This controller supplies the continuation boundary
that preflight deliberately did not own: a durable, expiring run manifest;
explicit start/await/resume/cutover/recover/cleanup operations; and delegation
to the existing coordinated promotion owner for every mutable runtime action.

The manifest contains no session token, cookie, private key, signature, or
credential.  It is an operator checkpoint, not an authority.  ``cutover`` and
``recover`` still require the independently issued, exact-bound authorization
files consumed by ``coordinated_runtime_promotion``.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator, Mapping


ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT / "scripts" / "dev" / "lite" / "run-coordinated-runtime-qualification.py"
PROMOTION = ROOT / "scripts" / "dev" / "lite" / "backend_runtime_promotion.py"
MANIFEST_NAME = "qualification-run.json"
SCHEMA = "pocketlab.coordinated-runtime-qualification/v2"
DEFAULT_TTL_MINUTES = 20
EXIT_SUCCESS = 0
EXIT_AWAITING_OPERATOR = 3
EXIT_FAILED = 2
EXIT_BLOCKED = 4


class QualificationControllerError(RuntimeError):
    """A bounded, sanitized qualification-controller failure."""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def _runner():
    """Load the existing runner without duplicating its setup primitives."""
    spec = importlib.util.spec_from_file_location("pocketlab_coordinated_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise QualificationControllerError("runner_unavailable", "The coordinated qualification runner is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _expiry(minutes: int = DEFAULT_TTL_MINUTES) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def _epoch(value: str | None) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(dict(value), handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationControllerError("manifest_invalid", "The qualification run manifest is unavailable or invalid.") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise QualificationControllerError("manifest_invalid", "The qualification run manifest schema is unsupported.")
    return value


def _manifest_path(run_root: Path) -> Path:
    root = run_root.expanduser().resolve(strict=False)
    return root / MANIFEST_NAME


def _run_id() -> str:
    return secrets.token_hex(12)


def _full_sha(value: str, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 40 or any(char not in "0123456789abcdef" for char in text):
        raise QualificationControllerError(f"{label}_invalid", f"The {label} must be a full commit SHA.")
    return text


def _root_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError as exc:
        raise QualificationControllerError("run_path_outside_root", "A qualification path escaped the run root.") from exc


def _root_path(run: Mapping[str, Any], key: str) -> Path:
    root = Path(str(run.get("run_root") or "")).expanduser().resolve(strict=True)
    relative = str((run.get("paths") or {}).get(key) or "")
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise QualificationControllerError("manifest_path_invalid", f"The manifest {key} path is invalid.")
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise QualificationControllerError("manifest_path_invalid", f"The manifest {key} path escaped the run root.") from exc
    return candidate


def _safe_paths(run: Mapping[str, Any]) -> dict[str, Path]:
    keys = ("baseline", "candidate", "runtime", "state", "base_dir", "evidence", "manifest")
    values = {key: _root_path(run, key) for key in keys}
    for path in values.values():
        if path.is_symlink():
            raise QualificationControllerError("run_path_symlink", "Qualification paths may not be symlinks.")
    return values


def _validate_run(run: Mapping[str, Any], *, expected_run_id: str | None = None, allow_expired: bool = False) -> dict[str, Any]:
    if str(run.get("run_id") or "") != (expected_run_id or str(run.get("run_id") or "")):
        raise QualificationControllerError("run_identity_mismatch", "The qualification run identity does not match the checkpoint.")
    if not allow_expired and _epoch(str(run.get("expires_at") or "")) <= time.time():
        raise QualificationControllerError("checkpoint_expired", "The qualification checkpoint has expired and cannot retain authority.")
    _full_sha(str(run.get("candidate_sha") or ""), "candidate_sha")
    _full_sha(str(run.get("baseline_sha") or ""), "baseline_sha")
    if run.get("candidate_sha") == run.get("baseline_sha"):
        raise QualificationControllerError("baseline_candidate_not_distinct", "The baseline and candidate must be different exact commits.")
    paths = _safe_paths(run)
    if paths["manifest"] != _manifest_path(paths["manifest"].parent):
        raise QualificationControllerError("manifest_path_invalid", "The manifest path is not run-owned.")
    return {**dict(run), "paths_resolved": paths}


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=45,
        check=False,
    )
    if check and result.returncode != 0:
        raise QualificationControllerError("git_identity_unavailable", "The exact qualification commit could not be verified.")
    return result.stdout.strip()


def _find_binary(value: str | None, name: str) -> Path:
    selected = Path(value).expanduser() if value else None
    if selected is None:
        resolved = shutil.which(name)
        selected = Path(resolved) if resolved else None
    if selected is None or not selected.is_file() or not os.access(selected, os.X_OK):
        raise QualificationControllerError(f"{name.replace('-', '_')}_unavailable", f"The {name} binary is unavailable.")
    return selected.resolve()


def _node_for_npm(npm: Path) -> Path:
    candidates = [npm.parent / "node", *(parent / "bin" / "node" for parent in npm.parents)]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise QualificationControllerError("node_unavailable", "The Node.js binary is unavailable.")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _ports() -> dict[str, int]:
    result: dict[str, int] = {}
    for name in ("api", "caddy", "nats", "monitor", "opa"):
        port = _free_port()
        while port in result.values():
            port = _free_port()
        result[name] = port
    return result


def _write_phase(run: dict[str, Any], *, phase: str, next_action: str, status: str = "RUNNING", **fields: Any) -> dict[str, Any]:
    run = dict(run)
    # ``_validate_run`` attaches resolved Path objects for the current
    # operation.  They are an in-memory convenience only; persisting them
    # would make the JSON checkpoint unserializable and would prevent cleanup
    # or a later resumable invocation from reaching its next action.
    run.pop("paths_resolved", None)
    run.update({"phase": phase, "next_action": next_action, "status": status, "updated_at": _utc(), **fields})
    path = _manifest_path(Path(str(run["run_root"])))
    _atomic_json(path, run)
    return run


def _base_env(run: Mapping[str, Any]) -> dict[str, str]:
    runner = _runner()
    root = Path(str(run["run_root"])).resolve(strict=True)
    paths = _safe_paths(run)
    binaries = {name: Path(value) for name, value in (run.get("binaries") or {}).items()}
    node = Path(str(run.get("node") or ""))
    if not node.is_file() or not all(path.is_file() for path in binaries.values()):
        raise QualificationControllerError("runtime_toolchain_missing", "The run-owned qualification toolchain is unavailable.")
    env = runner._environment(root, str(run["run_id"]), str(run["baseline_sha"]), dict(run["ports"]), binaries, node)
    env.update({
        "POCKETLAB_REPO_ROOT": str(paths["baseline"]),
        "POCKETLAB_CANDIDATE_SOURCE_COMMIT": str(run["baseline_sha"]),
        "POCKETLAB_LOCAL_DIST_ZIP": str(root / "baseline-assets" / "assets" / "dist.zip"),
        "POCKETLAB_LOCAL_RELEASE_MANIFEST": str(root / "baseline-assets" / "assets" / "pocketlab-lite-release.json"),
        "POCKETLAB_LOCAL_RELEASE_CHECKSUMS": str(root / "baseline-assets" / "assets" / "checksums.txt"),
        "POCKETLAB_LOCAL_RELEASE_TAG": str(run.get("baseline_release_tag") or ""),
        "PYTHONPATH": os.pathsep.join((str(paths["baseline"] / "pocket-lab-final-structure" / "runtime"), str(paths["baseline"] / "pocket-lab-final-structure" / "runtime" / "supervisors"), os.environ.get("PYTHONPATH", ""))),
    })
    # The exact main baseline predates the qualification PM2-shim branch in
    # common.sh.  Its PM2 wrapper therefore invokes the configured "native
    # node" as ``node <cli>``.  In this disposable lane the run-owned PM2
    # implementation is Python; point that compatibility invocation at the
    # repository venv interpreter while leaving the manifest's real Node
    # identity unchanged for asset/build work.  The candidate-side common.sh
    # takes its explicit qualification branch and invokes the same shim
    # directly.  No application owner uses this value to execute JavaScript.
    env["POCKETLAB_NATIVE_NODE"] = sys.executable
    return env


def _baseline_start_script(run: Mapping[str, Any]) -> Path:
    """Create a run-owned compatibility overlay for an older exact baseline.

    The T0--T2 baseline predates the isolated-runtime port contract and writes
    NATS directly to 4222/8222.  Copying or editing the checked-out baseline
    would blur the source identity, so the controller creates a disposable
    sibling script that keeps the baseline startup owners and replaces only
    those hard-coded listener values with the already allocated run ports.
    """
    paths = _safe_paths(run)
    source = paths["baseline"] / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "start-dashboard.sh"
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise QualificationControllerError("baseline_startup_unavailable", "The exact baseline startup owner is unavailable.") from exc
    replacements = {
        "listen: 0.0.0.0:4222": "listen: ${POCKETLAB_NATS_LISTEN_HOST:-127.0.0.1}:${POCKETLAB_LITE_NATS_PORT:-4222}",
        "http: 127.0.0.1:8222": "http: 127.0.0.1:${POCKETLAB_LITE_NATS_MONITOR_PORT:-8222}",
    }
    changed = False
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
            changed = True
    if not changed and "POCKETLAB_LITE_NATS_PORT" not in text:
        raise QualificationControllerError("baseline_startup_contract_unsupported", "The exact baseline has no safe isolated NATS port contract.")
    overlay = source.with_name(".qualification-start-dashboard.sh")
    try:
        overlay.write_text(text, encoding="utf-8")
        overlay.chmod(0o700)
    except OSError as exc:
        raise QualificationControllerError("baseline_startup_overlay_failed", "The run-owned baseline startup overlay could not be created.") from exc
    return overlay


@contextmanager
def _environment(env: Mapping[str, str]) -> Iterator[None]:
    previous = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update({str(key): str(value) for key, value in env.items()})
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _run(command: list[str], *, env: Mapping[str, str] | None = None, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, env=dict(env) if env is not None else None, cwd=str(cwd) if cwd else None, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise QualificationControllerError("qualification_command_unavailable", "A qualification owner could not be invoked.") from exc
    return result


def _baseline_package(runner: Any, repo: Path, baseline: str, root: Path) -> dict[str, Any]:
    """Build the baseline artifact from an exact temporary Git worktree.

    ``backend_runtime_promotion.prepare`` intentionally rejects a dirty or
    mismatched checkout.  The controller must not switch the developer's
    feature worktree merely to build the distinct baseline, so it gives the
    existing builder its own detached, exact-SHA worktree and removes that
    worktree after the artifact is sealed.
    """
    worktree = root / "baseline-package" / "exact-source"
    worktree.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    added = _run(["git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), baseline], timeout=90)
    if added.returncode != 0:
        raise QualificationControllerError("baseline_worktree_failed", "The exact baseline worktree could not be created.")
    try:
        return runner._promotion_artifact(worktree, baseline, root / "baseline-package")
    finally:
        removed = _run(["git", "-C", str(repo), "worktree", "remove", "--force", str(worktree)], timeout=90)
        if removed.returncode != 0:
            raise QualificationControllerError("baseline_worktree_cleanup_failed", "The temporary baseline worktree could not be removed safely.")


def _sanitize_tail(text: str, root: Path) -> list[str]:
    output: list[str] = []
    for line in (text or "").splitlines()[-16:]:
        value = line.replace(str(root), "<qualification-root>").replace(str(ROOT), "<repository-root>").strip()
        lowered = value.casefold()
        if any(marker in lowered for marker in ("password", "token", "secret", "cookie", "private key", "authorization:")):
            continue
        if value:
            output.append(value[:240])
    return output


def _report(run: Mapping[str, Any], name: str, payload: Mapping[str, Any]) -> Path:
    paths = _safe_paths(run)
    path = paths["evidence"] / name
    _atomic_json(path, payload)
    return path


def prepare(*, baseline_sha: str, candidate_sha: str, run_root: Path | None, evidence_dir: Path | None, npm_bin: str | None, nats_bin: str | None, caddy_bin: str | None, opa_bin: str | None, ttl_minutes: int) -> dict[str, Any]:
    runner = _runner()
    repo = ROOT
    candidate = _full_sha(candidate_sha, "candidate_sha")
    baseline = _full_sha(baseline_sha, "baseline_sha")
    if candidate == baseline:
        raise QualificationControllerError("baseline_candidate_not_distinct", "The baseline and candidate must be different exact commits.")
    observed = _git(repo, "rev-parse", "HEAD").lower()
    if observed != candidate:
        raise QualificationControllerError("candidate_checkout_mismatch", "The working checkout does not match the requested candidate SHA.")
    if _git(repo, "status", "--porcelain"):
        raise QualificationControllerError("candidate_checkout_dirty", "The candidate checkout is not clean.")
    root = (run_root or (ROOT / ".pocketlab-dev" / "qualification-runs" / _run_id())).expanduser().resolve()
    if root.exists():
        if root.is_symlink() or any(root.iterdir()):
            raise QualificationControllerError("run_root_not_empty", "The qualification run root must be a new empty directory.")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    # The run identity is a random hex value, never a user-selected path
    # name.  qualification_context validates this value before arming any
    # mutable owner, so a path such as ``fc01-candidate`` must not become an
    # accepted process identity.
    run_id = _run_id()
    evidence = (evidence_dir or root / "evidence").expanduser().resolve()
    try:
        evidence.relative_to(root)
    except ValueError as exc:
        raise QualificationControllerError("evidence_outside_run_root", "Qualification evidence must remain inside the run-owned root.") from exc
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    binaries = {
        "nats": _find_binary(nats_bin or os.environ.get("NATS_SERVER_BIN"), "nats-server"),
        "caddy": _find_binary(caddy_bin or os.environ.get("CADDY_BIN"), "caddy"),
        "opa": _find_binary(opa_bin or os.environ.get("OPA_BIN"), "opa"),
    }
    npm = _find_binary(npm_bin or os.environ.get("NPM_BIN"), "npm")
    node = _node_for_npm(npm)
    copied = runner._copy_binaries(root, binaries)
    baseline_source = root / "baseline"
    candidate_source = root / "candidate"
    runner._extract_commit(repo, baseline, baseline_source)
    runner._extract_commit(repo, candidate, candidate_source)
    baseline_assets = runner._release_assets(baseline_source, baseline, root / "baseline-assets", npm)
    candidate_assets = runner._release_assets(candidate_source, candidate, root / "candidate-assets", npm)
    baseline_package = _baseline_package(runner, repo, baseline, root)
    candidate_package = runner._promotion_artifact(repo, candidate, root / "candidate-package")
    ports = _ports()
    run = {
        "schema": SCHEMA,
        "run_id": run_id,
        "status": "PREPARED",
        "phase": "prepared",
        "next_action": "start",
        "baseline_sha": baseline,
        "candidate_sha": candidate,
        "baseline_release_tag": baseline_assets["tag"],
        "candidate_release_tag": candidate_assets["tag"],
        "run_root": str(root),
        "created_at": _utc(),
        "updated_at": _utc(),
        "expires_at": _expiry(ttl_minutes),
        "ports": ports,
        "binaries": {key: str(value) for key, value in copied.items() if key != "pm2"},
        "pm2": {"path": str(copied["pm2"]), "mode": "qualification_pm2_shim", "native_pm2_qualification": "not_run"},
        "node": str(node),
        "paths": {
            "baseline": _root_relative(baseline_source, root),
            "candidate": _root_relative(candidate_source, root),
            "runtime": _root_relative(root / "runtime", root),
            "state": _root_relative(root / "state", root),
            "base_dir": _root_relative(root / "base", root),
            "evidence": _root_relative(evidence, root),
            "manifest": MANIFEST_NAME,
        },
        "package": {
            "baseline": {"artifact": baseline_package["verified"], "pwa": {"source_commit": baseline, "artifact_sha256": baseline_assets["digest"]}},
            "candidate": {"artifact": candidate_package["verified"], "pwa": {"source_commit": candidate, "artifact_sha256": candidate_assets["digest"]}},
        },
        "services": {"started": False, "owned": list(runner.SERVICE_NAMES)},
        "authority": {"owner": "not_authenticated", "promotion": "not_issued", "recovery": "not_issued"},
        "origin": {"status": "not_verified", "url": None},
        "evidence": [],
        "cleanup_obligations": ["stop_run_owned_services", "revoke_qualification_sessions", "remove_run_root"],
        "production_execution": False,
        "sanitized": True,
    }
    path = _manifest_path(root)
    _atomic_json(path, run)
    run["manifest"] = str(path)
    _report(run, "qualification-controller.json", {**run, "manifest": "<qualification-root>/qualification-run.json"})
    return run


def _start(run: dict[str, Any]) -> dict[str, Any]:
    runner = _runner()
    validated = _validate_run(run)
    paths = validated["paths_resolved"]
    env = _base_env(validated)
    runner._assert_isolated_environment(env, paths["manifest"].parent)
    Path(env["HOME"]).mkdir(mode=0o700, parents=True, exist_ok=True)
    install = paths["baseline"] / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "install-pwa-ui.sh"
    installed = _run(["bash", str(install)], cwd=paths["baseline"], env=env, timeout=180)
    if installed.returncode != 0:
        raise QualificationControllerError("baseline_install_failed", "The isolated baseline PWA installation failed.")
    start_script = _baseline_start_script(validated)
    started = _run(["bash", str(start_script), "--lite", "--reconcile-only"], cwd=paths["baseline"], env=env, timeout=300)
    if started.returncode != 0:
        raise QualificationControllerError("runtime_start_failed", "The isolated runtime owners did not start.")
    observation = runner._observe(env, str(validated["run_id"]))
    if not observation.get("all_required_online"):
        raise QualificationControllerError("runtime_identity_unavailable", "The isolated runtime owners did not establish run-owned identity.")
    status, runtime = runner._http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/api/lite/runtime")
    health, _ = runner._http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/health")
    ready, _ = runner._http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/ready")
    projection = runner._identity_projection(env)
    if status != 200 or health != 200 or ready != 200 or runtime.get("stable") is not True or projection.get("status") != "stable":
        raise QualificationControllerError("runtime_convergence_failed", "The isolated baseline did not converge with independently observed identity.")
    updated = _write_phase(validated, phase="awaiting_owner", next_action="verify_candidate_https_then_request_owner_authentication", status="AWAITING_OPERATOR", services={"started": True, "owned": list(runner.SERVICE_NAMES), "process_manager": "qualification_pm2_shim"}, baseline_identity={"status": "PASS", "source_commit": validated["baseline_sha"], "runtime": runtime, "projection": projection, "observation": observation}, startup={"status": "PASS", "owner": "exact_baseline_start_dashboard", "qualification_overlay": "isolated_nats_port_only"}, evidence=["baseline_identity"])
    updated["manifest"] = str(_manifest_path(paths["manifest"].parent))
    _report(updated, "baseline-start.json", {"status": "PASS", "run_id": updated["run_id"], "baseline_sha": updated["baseline_sha"], "runtime": runtime, "projection": projection, "services": observation, "sanitized": True})
    return updated


def _verify_origin(origin: str) -> dict[str, Any]:
    value = str(origin or "").strip().rstrip("/")
    if not value.startswith("https://") or any(marker in value for marker in ("@", "?", "#")):
        raise QualificationControllerError("candidate_https_origin_invalid", "The candidate origin must be an HTTPS URL without credentials or query state.")
    try:
        parsed = urllib.parse.urlparse(value)
        if not parsed.hostname:
            raise ValueError("missing host")
        context = ssl.create_default_context()
        with urllib.request.urlopen(value + "/health", timeout=8, context=context) as response:
            status = int(response.status)
            body = response.read(128 * 1024)
    except (OSError, urllib.error.URLError, ValueError, ssl.SSLError) as exc:
        raise QualificationControllerError("candidate_https_unavailable", "The candidate HTTPS origin could not be verified with normal certificate validation.") from exc
    return {"status": "PASS" if status == 200 else "FAIL", "url": value, "health_status": status, "response_sha256": _sha256(body), "sanitized": True}


def await_owner(run: dict[str, Any], origin: str) -> dict[str, Any]:
    validated = _validate_run(run)
    if str(validated.get("phase")) not in {"awaiting_owner", "owner_ready"}:
        raise QualificationControllerError("owner_checkpoint_invalid", "The qualification run is not at its owner-authentication checkpoint.")
    verified = _verify_origin(origin)
    updated = _write_phase(validated, phase="owner_ready", next_action="open_origin_and_complete_purpose_bound_webauthn", status="AWAITING_OPERATOR", origin=verified)
    updated["operator_prompt"] = "HUMAN INTERVENTION REQUIRED: complete the displayed Pocket Lab Lite Owner passkey ceremony, then resume this exact run."
    _atomic_json(_manifest_path(Path(str(updated["run_root"]))), updated)
    _report(updated, "owner-checkpoint.json", {"status": "AWAITING_OPERATOR", "run_id": updated["run_id"], "candidate_sha": updated["candidate_sha"], "origin": verified, "operator_prompt": updated["operator_prompt"], "credentials_excluded": True, "sanitized": True})
    return updated


def _owner_evidence(run: Mapping[str, Any], path: Path | None) -> dict[str, Any]:
    if path is None:
        raise QualificationControllerError("owner_authorization_required", "A backend-issued owner checkpoint is required before execution.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationControllerError("owner_evidence_invalid", "The backend-issued owner checkpoint is unavailable or invalid.") from exc
    if not isinstance(value, dict) or value.get("sanitized") is not True or value.get("candidate_sha") != run.get("candidate_sha"):
        raise QualificationControllerError("owner_evidence_binding_invalid", "The owner checkpoint is not sanitized and bound to this candidate.")
    if any(key in value for key in ("cookie", "token", "signature", "assertion", "private_key")):
        raise QualificationControllerError("owner_evidence_secret", "Owner evidence must not contain credential material.")
    if value.get("authentication") != "backend_confirmed_human_owner":
        raise QualificationControllerError("owner_authentication_unconfirmed", "The backend has not confirmed human Owner authentication for this run.")
    return {"status": "PASS", "authentication": "backend_confirmed_human_owner", "purpose": str(value.get("purpose") or "")[:120], "candidate_sha": run["candidate_sha"], "authority_epoch": value.get("authority_epoch"), "policy_revision": value.get("policy_revision"), "expires_at": value.get("expires_at"), "sanitized": True}


def _promotion(run: dict[str, Any], *, owner_evidence: Path | None, grant_id: str | None, authorization: Path | None, promotion_public_key: Path | None, recovery_authorization: Path | None, recovery_public_key: Path | None) -> dict[str, Any]:
    runner = _runner()
    validated = _validate_run(run)
    owner = _owner_evidence(validated, owner_evidence)
    required = {"grant_id": grant_id, "authorization": authorization, "promotion_public_key": promotion_public_key, "recovery_authorization": recovery_authorization, "recovery_public_key": recovery_public_key}
    missing = [key for key, value in required.items() if value is None]
    if missing:
        raise QualificationControllerError("execution_authority_incomplete", "The execution continuation is missing: " + ", ".join(missing) + ".")
    paths = validated["paths_resolved"]
    env = _base_env(validated)
    command = [sys.executable, str(PROMOTION), "activate-coordinated", "--grant-id", str(grant_id), "--authorization", str(authorization), "--promotion-public-key", str(promotion_public_key), "--recovery-authorization", str(recovery_authorization), "--recovery-public-key", str(recovery_public_key), "--confirm-cutover"]
    result = _run(command, env=env, cwd=paths["baseline"], timeout=600)
    try:
        payload = json.loads(result.stdout or result.stderr)
    except json.JSONDecodeError:
        payload = {"status": "FAIL", "reason_code": "promotion_owner_invalid_output"}
    if result.returncode != 0 or payload.get("status") != "committed":
        updated = _write_phase(validated, phase="recovery_required", next_action="inspect_journal_and_use_separate_recovery_authorization", status="BLOCKED", authority={"owner": owner, "promotion": "rejected_or_uncertain", "recovery": "available_if_valid"}, cutover={"status": "FAIL", "owner": payload, "production_execution": False})
        _report(updated, "cutover.json", {"status": "FAIL", "run_id": updated["run_id"], "candidate_sha": updated["candidate_sha"], "owner": owner, "promotion": payload, "production_execution": False, "sanitized": True})
        raise QualificationControllerError("coordinated_cutover_failed", "The existing coordinated promotion owner did not commit the isolated cutover.")
    updated = _write_phase(validated, phase="committed", next_action="recover_or_cleanup", status="PASS", authority={"owner": owner, "promotion": "backend_verified", "recovery": "separately_bound"}, cutover={"status": "PASS", "owner": payload, "production_execution": False})
    _report(updated, "cutover.json", {"status": "PASS", "run_id": updated["run_id"], "baseline_sha": updated["baseline_sha"], "candidate_sha": updated["candidate_sha"], "owner": owner, "promotion": payload, "production_execution": False, "sanitized": True})
    return updated


def _recover(run: dict[str, Any], *, journal: Path, recovery_authorization: Path, recovery_public_key: Path) -> dict[str, Any]:
    validated = _validate_run(run)
    paths = validated["paths_resolved"]
    env = _base_env(validated)
    command = [sys.executable, str(PROMOTION), "recover-coordinated", "--journal", str(journal), "--candidate-sha", str(validated["candidate_sha"]), "--current-sha", str(validated["baseline_sha"]), "--device-id", "qualification-" + str(validated["run_id"]), "--recovery-authorization", str(recovery_authorization), "--recovery-public-key", str(recovery_public_key), "--confirm-recovery"]
    result = _run(command, env=env, cwd=paths["baseline"], timeout=600)
    try:
        payload = json.loads(result.stdout or result.stderr)
    except json.JSONDecodeError:
        payload = {"status": "FAIL", "reason_code": "recovery_owner_invalid_output"}
    if result.returncode != 0 or payload.get("status") not in {"recovered", "already_terminal"}:
        updated = _write_phase(validated, phase="recovery_required", next_action="manual_recovery_review", status="BLOCKED", recovery={"status": "FAIL", "owner": payload, "newer_writes_preserved": payload.get("reason_code") == "newer_writes_observed"})
        _report(updated, "recovery.json", {"status": "FAIL", "run_id": updated["run_id"], "candidate_sha": updated["candidate_sha"], "owner": payload, "sanitized": True})
        raise QualificationControllerError("recovery_failed", "The existing recovery owner did not independently verify recovery.")
    updated = _write_phase(validated, phase="recovered", next_action="cleanup", status="PASS", recovery={"status": "PASS", "owner": payload, "newer_writes_preserved": True})
    _report(updated, "recovery.json", {"status": "PASS", "run_id": updated["run_id"], "candidate_sha": updated["candidate_sha"], "owner": payload, "newer_writes_preserved": True, "sanitized": True})
    return updated


def cleanup(run: dict[str, Any], *, remove_root: bool) -> dict[str, Any]:
    runner = _runner()
    validated = _validate_run(run, allow_expired=True)
    paths = validated["paths_resolved"]
    env = _base_env(validated)
    cleanup_ok = runner._cleanup(env)
    updated = _write_phase(validated, phase="cleaned", next_action="none", status="PASS" if cleanup_ok else "BLOCKED", cleanup={"status": "PASS" if cleanup_ok else "BLOCKED", "run_owned_services_stopped": cleanup_ok, "root_removed": False})
    _report(updated, "cleanup.json", {"status": updated["status"], "run_id": updated["run_id"], "services_stopped": cleanup_ok, "root_removed": False, "sanitized": True})
    if remove_root and cleanup_ok:
        root = Path(str(updated["run_root"])).resolve()
        if root == ROOT or root == Path("/") or root.is_symlink():
            raise QualificationControllerError("run_root_cleanup_invalid", "The requested cleanup root is not a safe run-owned directory.")
        shutil.rmtree(root)
        updated["cleanup"]["root_removed"] = True
    return updated


def _print(value: Mapping[str, Any]) -> None:
    sanitized = dict(value)
    sanitized.pop("paths_resolved", None)
    print(json.dumps(sanitized, ensure_ascii=True, sort_keys=True, indent=2))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pocket Lab Lite resumable coordinated-runtime qualification controller")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--baseline-sha", required=True)
    prepare_parser.add_argument("--candidate-sha", required=True)
    prepare_parser.add_argument("--run-root", type=Path)
    prepare_parser.add_argument("--evidence-dir", type=Path)
    prepare_parser.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)
    for name in ("npm-bin", "nats-bin", "caddy-bin", "opa-bin"):
        prepare_parser.add_argument("--" + name)
    for name in ("start", "status", "cleanup"):
        command = commands.add_parser(name)
        command.add_argument("--run-root", type=Path, required=True)
    commands.choices["cleanup"].add_argument("--remove-root", action="store_true")
    owner = commands.add_parser("await-owner")
    owner.add_argument("--run-root", type=Path, required=True)
    owner.add_argument("--origin", required=True)
    resume = commands.add_parser("resume")
    resume.add_argument("--run-root", type=Path, required=True)
    resume.add_argument("--owner-evidence", type=Path, required=True)
    resume.add_argument("--grant-id", required=True)
    resume.add_argument("--authorization", type=Path, required=True)
    resume.add_argument("--promotion-public-key", type=Path, required=True)
    resume.add_argument("--recovery-authorization", type=Path, required=True)
    resume.add_argument("--recovery-public-key", type=Path, required=True)
    cutover = commands.add_parser("cutover")
    cutover.add_argument("--run-root", type=Path, required=True)
    cutover.add_argument("--owner-evidence", type=Path, required=True)
    cutover.add_argument("--grant-id", required=True)
    cutover.add_argument("--authorization", type=Path, required=True)
    cutover.add_argument("--promotion-public-key", type=Path, required=True)
    cutover.add_argument("--recovery-authorization", type=Path, required=True)
    cutover.add_argument("--recovery-public-key", type=Path, required=True)
    recover = commands.add_parser("recover")
    recover.add_argument("--run-root", type=Path, required=True)
    recover.add_argument("--journal", type=Path, required=True)
    recover.add_argument("--recovery-authorization", type=Path, required=True)
    recover.add_argument("--recovery-public-key", type=Path, required=True)
    qualify = commands.add_parser("qualify")
    qualify.add_argument("--baseline-sha", required=True)
    qualify.add_argument("--candidate-sha", required=True)
    qualify.add_argument("--run-root", type=Path)
    qualify.add_argument("--evidence-dir", type=Path)
    qualify.add_argument("--origin")
    qualify.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(baseline_sha=args.baseline_sha, candidate_sha=args.candidate_sha, run_root=args.run_root, evidence_dir=args.evidence_dir, npm_bin=args.npm_bin, nats_bin=args.nats_bin, caddy_bin=args.caddy_bin, opa_bin=args.opa_bin, ttl_minutes=args.ttl_minutes)
            _print(result)
            return EXIT_SUCCESS
        root = args.run_root.expanduser().resolve()
        run = _read_manifest(_manifest_path(root))
        if args.command == "start":
            _print(_start(run))
            return EXIT_AWAITING_OPERATOR
        if args.command == "status":
            validated = _validate_run(run, allow_expired=True)
            runner = _runner()
            env = _base_env(validated)
            observation = runner._observe(env, str(validated["run_id"])) if validated.get("services", {}).get("started") else {"status": "not_started"}
            _print({**validated, "runtime_observation": observation})
            return EXIT_AWAITING_OPERATOR if validated.get("phase") in {"awaiting_owner", "owner_ready", "recovery_required"} else EXIT_SUCCESS
        if args.command == "await-owner":
            _print(await_owner(run, args.origin))
            return EXIT_AWAITING_OPERATOR
        if args.command in {"resume", "cutover"}:
            _print(_promotion(run, owner_evidence=args.owner_evidence, grant_id=args.grant_id, authorization=args.authorization, promotion_public_key=args.promotion_public_key, recovery_authorization=args.recovery_authorization, recovery_public_key=args.recovery_public_key))
            return EXIT_SUCCESS
        if args.command == "recover":
            _print(_recover(run, journal=args.journal, recovery_authorization=args.recovery_authorization, recovery_public_key=args.recovery_public_key))
            return EXIT_SUCCESS
        if args.command == "cleanup":
            _print(cleanup(run, remove_root=args.remove_root))
            return EXIT_SUCCESS
        if args.command == "qualify":
            prepared = prepare(baseline_sha=args.baseline_sha, candidate_sha=args.candidate_sha, run_root=args.run_root, evidence_dir=args.evidence_dir, npm_bin=None, nats_bin=None, caddy_bin=None, opa_bin=None, ttl_minutes=args.ttl_minutes)
            started = _start(prepared)
            if not args.origin:
                _print(started)
                return EXIT_AWAITING_OPERATOR
            ready = await_owner(started, args.origin)
            _print(ready)
            return EXIT_AWAITING_OPERATOR
        raise QualificationControllerError("command_invalid", "The qualification controller command is invalid.")
    except QualificationControllerError as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": exc.reason_code, "message": exc.message, "sanitized": True}, ensure_ascii=True, sort_keys=True), file=sys.stderr)
        return EXIT_BLOCKED if exc.reason_code in {"owner_authorization_required", "candidate_https_origin_invalid", "candidate_https_unavailable", "owner_authentication_unconfirmed", "execution_authority_incomplete", "checkpoint_expired"} else EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
