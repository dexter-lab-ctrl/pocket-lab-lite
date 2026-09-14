#!/usr/bin/env python3
"""Bounded loopback client for the server-owned Runtime Security Assurance API.

The client submits only a registered suite/scenario and never accepts a URL,
command, argv, target, scanner option, filesystem path, or NATS subject.  The
private Ed25519 key is used only by the existing harness client; this client
receives a short-lived session through an environment variable and never
prints it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import harness as harness_client


SESSION_ENV = "POCKETLAB_HARNESS_SESSION"
RUN_ID_RE = re.compile(r"^assurance-[0-9a-f]{32}$")
POLL_SECONDS = 2.0
MAX_POLL_SECONDS = 2 * 60 * 60
DEFAULT_PRINCIPAL_ID = "codex-security-assurance"
DEFAULT_KEY_FILE = Path.home() / ".pocketlab-qualification" / "codex-security-assurance.key"
CONTINUITY_ENV = "POCKETLAB_HARNESS_CONTINUITY_FILE"
CONTINUITY_FILE = Path.home() / ".pocketlab-qualification" / "runtime-security-assurance.json"
CONTINUITY_KEYS = frozenset({
    "principal_id",
    "public_key_fingerprint",
    "private_key_file_path",
    "active_run_id",
    "suite_id",
    "scenario_id",
    "last_event_sequence",
    "runtime_id",
    "revision_sha",
})
FIXED_PROFILE = "security-assurance-runner"
FIXED_PURPOSE = "security.assurance"
FIXED_TARGET_SCOPE = "local_server_host_only"
TERMINAL_STATUSES = frozenset({"PASS", "FAIL", "PARTIAL", "BLOCKED", "CANCELLED"})
REAUTHENTICATE_REASONS = frozenset({
    "assurance_transport_unavailable",
    "harness_session_expired",
    "harness_session_invalid",
})


def _request(
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    authenticated: bool = False,
    session_token: str | None = None,
) -> dict:
    if not path.startswith("/api/lite/harness/security-assurance/") or ".." in path or "//" in path:
        raise ValueError("assurance API path is not registered")
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if authenticated:
        token = str(session_token or os.environ.get(SESSION_ENV, "")).strip()
        if not token:
            raise ValueError(f"{SESSION_ENV} is required")
        headers["X-Pocket-Lab-Harness-Session"] = token
    request = urllib.request.Request(harness_client._api_url() + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(256 * 1024)
            result = json.loads(raw.decode("utf-8")) if raw else {}
            return result if isinstance(result, dict) else {"result": result}
    except urllib.error.HTTPError as exc:
        raw = exc.read(32 * 1024)
        try:
            detail = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = {}
        if isinstance(detail.get("detail"), dict):
            detail = detail["detail"]
        reason = str(detail.get("reason_code") or "assurance_request_failed")[:80]
        raise RuntimeError(f"{reason}: the assurance request was rejected") from None
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"assurance_transport_unavailable: {type(exc).__name__}") from None


def _safe_run_id(value: str) -> str:
    if not RUN_ID_RE.fullmatch(str(value or "").strip()):
        raise ValueError("run identifier is invalid")
    return str(value).strip()


def cmd_check(_args: argparse.Namespace) -> dict:
    runtime = Path(__file__).resolve().parents[3] / "pocket-lab-final-structure" / "runtime"
    sys.path.insert(0, str(runtime))
    from api_fastapi.services import lite_security_assurance

    return {"registry": lite_security_assurance.check_registries(), "sanitized": True}


def cmd_preflight(args: argparse.Namespace) -> dict:
    suite = str(args.suite_id)
    return _request("GET", f"/api/lite/harness/security-assurance/preflight?suite_id={suite}", authenticated=True)


def _sync_policy(
    lease: dict,
    *,
    wait_seconds: float = 120.0,
    principal_id: str | None = None,
    key_file: str | None = None,
    session_ttl_seconds: int | None = None,
) -> dict:
    """Request the fixed qualification policy sync and wait for OPA proof."""
    queued = _request(
        "POST",
        "/api/lite/harness/security-assurance/policy-sync",
        {},
        authenticated=True,
        session_token=lease.get("session_token"),
    )
    bounded_wait = max(0.0, min(float(wait_seconds), 600.0))
    deadline = time.monotonic() + bounded_wait
    last = _request(
        "GET",
        "/api/lite/harness/security-assurance/preflight?suite_id=standard",
        authenticated=True,
        session_token=lease.get("session_token"),
    )
    while str(last.get("status") or "").casefold() != "ready" and time.monotonic() < deadline:
        if _session_needs_renewal(lease) and principal_id and key_file:
            _renew_lease(
                lease,
                principal_id=principal_id,
                key_file=key_file,
                ttl_seconds=session_ttl_seconds,
            )
        time.sleep(min(2.0, max(0.1, deadline - time.monotonic())))
        last = _request(
            "GET",
            "/api/lite/harness/security-assurance/preflight?suite_id=standard",
            authenticated=True,
            session_token=lease.get("session_token"),
        )
    return {
        "status": "PASS" if str(last.get("status") or "").casefold() == "ready" else "BLOCKED",
        "request": queued,
        "preflight": last,
        "sanitized": True,
    }


def cmd_policy_sync(args: argparse.Namespace) -> dict:
    token = os.environ.get(SESSION_ENV, "").strip()
    if not token:
        raise ValueError(f"{SESSION_ENV} is required")
    return _sync_policy({"session_token": token}, wait_seconds=args.wait_seconds)


def cmd_fault(args: argparse.Namespace) -> dict:
    token = os.environ.get(SESSION_ENV, "").strip()
    if not token:
        raise ValueError(f"{SESSION_ENV} is required")
    return _request(
        "POST",
        f"/api/lite/harness/security-assurance/faults/{args.fault_id}",
        {"confirm": True},
        authenticated=True,
        session_token=token,
    )


def _terminal_status(result: dict) -> str:
    return str(result.get("status") or "").upper()


def _parse_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _session_lease(raw: dict) -> dict:
    session = raw.get("session") if isinstance(raw.get("session"), dict) else {}
    token = str(raw.get("session_token") or "").strip()
    session_id = str(session.get("harness_session_id") or "").strip()
    if not token or not session_id:
        raise RuntimeError("harness_session_invalid: the server did not return a usable session")
    return {
        "session_token": token,
        "session": dict(session),
        "session_ids": [session_id],
        "renewal_count": 0,
    }


def _session_needs_renewal(lease: dict) -> bool:
    session = lease.get("session") if isinstance(lease.get("session"), dict) else {}
    started = _parse_timestamp(session.get("started_at"))
    expires = _parse_timestamp(session.get("expires_at"))
    if started is None or expires is None:
        return False
    duration = max(1.0, (expires - started).total_seconds())
    remaining = (expires - datetime.now(timezone.utc)).total_seconds()
    threshold = max(30.0, min(300.0, duration * 0.25))
    return remaining <= threshold


def _should_reauthenticate(exc: RuntimeError) -> bool:
    """Retry only transport/session-lifecycle failures, never app errors."""
    reason = str(exc).split(":", 1)[0].strip()
    return reason in REAUTHENTICATE_REASONS


def _renew_lease(lease: dict, *, principal_id: str, key_file: str, ttl_seconds: int | None = None) -> None:
    renewed = harness_client.start_session(
        principal_id=principal_id,
        profile=FIXED_PROFILE,
        purpose=FIXED_PURPOSE,
        key_file=key_file,
        ttl_seconds=ttl_seconds,
    )
    replacement = _session_lease(renewed)
    old_ids = list(lease.get("session_ids") or [])
    old_renewal_count = int(lease.get("renewal_count") or 0)
    lease.clear()
    lease.update(replacement)
    lease["session_ids"] = old_ids + replacement["session_ids"]
    lease["renewal_count"] = old_renewal_count + 1


def _ensure_lease(
    lease: dict,
    *,
    principal_id: str,
    key_file: str,
    ttl_seconds: int | None = None,
) -> None:
    """Refresh a session before a control request can cross its expiry."""
    if _session_needs_renewal(lease):
        _renew_lease(
            lease,
            principal_id=principal_id,
            key_file=key_file,
            ttl_seconds=ttl_seconds,
        )


def _continuity_path() -> Path:
    configured = os.environ.get(CONTINUITY_ENV, "").strip()
    path = Path(configured).expanduser() if configured else CONTINUITY_FILE
    return harness_client._ensure_key_path_outside_repo(path)


def _load_continuity(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("assurance_continuity_invalid: the local continuity record is unreadable") from None
    if not isinstance(raw, dict):
        raise RuntimeError("assurance_continuity_invalid: the local continuity record is invalid")
    return {key: raw[key] for key in CONTINUITY_KEYS if key in raw and isinstance(raw[key], (str, int))}


def _write_continuity(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {
        key: state[key]
        for key in CONTINUITY_KEYS
        if key in state and isinstance(state[key], (str, int))
    }
    encoded = (json.dumps(safe, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        written = os.write(fd, encoded)
        if written != len(encoded):
            raise OSError("continuity write was incomplete")
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def _remove_continuity(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _record_run(path: Path, state: dict, run: dict, *, suite_id: str, scenario_id: str | None = None) -> None:
    state.update({
        "active_run_id": str(run.get("run_id") or ""),
        "suite_id": suite_id,
        "scenario_id": scenario_id or "",
        "last_event_sequence": int(run.get("last_event_sequence") or 0),
        "runtime_id": str(run.get("runtime_id") or ""),
        "revision_sha": str(run.get("revision_sha") or ""),
    })
    _write_continuity(path, state)


def _poll(
    run_id: str,
    *,
    lease: dict | None = None,
    principal_id: str | None = None,
    key_file: str | None = None,
    continuity_path: Path | None = None,
    continuity_state: dict | None = None,
    session_ttl_seconds: int | None = None,
    max_poll_seconds: float = MAX_POLL_SECONDS,
) -> dict:
    deadline = time.monotonic() + MAX_POLL_SECONDS
    result: dict = {}
    if max_poll_seconds <= 0 or max_poll_seconds > MAX_POLL_SECONDS:
        raise ValueError("assurance poll deadline is outside the bounded range")
    deadline = time.monotonic() + max_poll_seconds
    while time.monotonic() < deadline:
        if lease is not None and principal_id and key_file and _session_needs_renewal(lease):
            _renew_lease(lease, principal_id=principal_id, key_file=key_file, ttl_seconds=session_ttl_seconds)
        token = lease.get("session_token") if lease is not None else None
        try:
            result = _request(
                "GET",
                f"/api/lite/harness/security-assurance/runs/{run_id}",
                authenticated=True,
                session_token=token,
            )
        except RuntimeError as exc:
            if (
                lease is None
                or not principal_id
                or not key_file
                or not _should_reauthenticate(exc)
            ):
                raise
            _renew_lease(lease, principal_id=principal_id, key_file=key_file, ttl_seconds=session_ttl_seconds)
            result = _request(
                "GET",
                f"/api/lite/harness/security-assurance/runs/{run_id}",
                authenticated=True,
                session_token=lease["session_token"],
            )
        if continuity_path is not None and continuity_state is not None:
            continuity_state["last_event_sequence"] = int(result.get("last_event_sequence") or 0)
            _write_continuity(continuity_path, continuity_state)
        if _terminal_status(result) not in {"QUEUED", "RUNNING"}:
            return result
        time.sleep(min(POLL_SECONDS, max(0.1, deadline - time.monotonic())))
    raise RuntimeError("assurance_poll_timeout: the run did not reach a terminal state")


def cmd_run(args: argparse.Namespace) -> dict:
    payload = {"suite_id": args.suite_id}
    if args.scenario_id:
        payload["scenario_id"] = args.scenario_id
    if args.baseline_run_id:
        payload["baseline_run_id"] = _safe_run_id(args.baseline_run_id)
    queued = _request("POST", "/api/lite/harness/security-assurance/runs", payload, authenticated=True)
    run_id = _safe_run_id(str(queued.get("run_id") or ""))
    result = _poll(run_id)
    return {
        "run": result,
        "run_id": run_id,
        "report": _request("GET", f"/api/lite/harness/security-assurance/runs/{run_id}/report", authenticated=True),
        "sanitized": True,
    }


def _ensure_qualification_key(path: Path) -> tuple[Path, str]:
    path = harness_client._ensure_key_path_outside_repo(path)
    if not path.exists():
        harness_client.cmd_keygen(argparse.Namespace(
            key_file=str(path),
            public_key_file=str(path) + ".pub",
            force=False,
        ))
    key = harness_client._private_key(str(path))
    public = key.public_key().public_bytes(
        harness_client.serialization.Encoding.Raw,
        harness_client.serialization.PublicFormat.Raw,
    )
    return path, "sha256:" + hashlib.sha256(public).hexdigest()


def _run_qualified_suite(
    *,
    suite_id: str,
    lease: dict,
    principal_id: str,
    key_file: str,
    continuity_path: Path,
    continuity_state: dict,
    session_ttl_seconds: int | None,
    max_poll_seconds: float,
) -> dict:
    preflight = _request(
        "GET",
        f"/api/lite/harness/security-assurance/preflight?suite_id={suite_id}",
        authenticated=True,
        session_token=lease["session_token"],
    )
    if str(preflight.get("status") or "").casefold() != "ready":
        return {"status": "BLOCKED", "preflight": preflight, "suite_id": suite_id, "sanitized": True}
    queued = _request(
        "POST",
        "/api/lite/harness/security-assurance/runs",
        {"suite_id": suite_id},
        authenticated=True,
        session_token=lease["session_token"],
    )
    run_id = _safe_run_id(str(queued.get("run_id") or ""))
    _record_run(continuity_path, continuity_state, queued, suite_id=suite_id)
    result = _poll(
        run_id,
        lease=lease,
        principal_id=principal_id,
        key_file=key_file,
        continuity_path=continuity_path,
        continuity_state=continuity_state,
        session_ttl_seconds=session_ttl_seconds,
        max_poll_seconds=max_poll_seconds,
    )
    _ensure_lease(
        lease,
        principal_id=principal_id,
        key_file=key_file,
        ttl_seconds=session_ttl_seconds,
    )
    report = _request(
        "GET",
        f"/api/lite/harness/security-assurance/runs/{run_id}/report",
        authenticated=True,
        session_token=lease["session_token"],
    )
    return {
        "status": _terminal_status(result),
        "suite_id": suite_id,
        "run": result,
        "run_id": run_id,
        "report": report,
        "session": {
            "renewal_count": int(lease.get("renewal_count") or 0),
            "session_ids": list(lease.get("session_ids") or []),
        },
        "preflight": preflight,
        "sanitized": True,
    }


def _reattach_or_resume(
    *,
    state: dict,
    lease: dict,
    principal_id: str,
    key_file: str,
    continuity_path: Path,
    session_ttl_seconds: int | None,
    max_poll_seconds: float,
) -> dict | None:
    raw_run_id = str(state.get("active_run_id") or "")
    if not raw_run_id:
        return None
    run_id = _safe_run_id(raw_run_id)
    current = _request(
        "GET",
        f"/api/lite/harness/security-assurance/runs/{run_id}",
        authenticated=True,
        session_token=lease["session_token"],
    )
    status = _terminal_status(current)
    if status in {"PASS", "FAIL", "BLOCKED", "CANCELLED"}:
        return {
            "status": status,
            "suite_id": str(state.get("suite_id") or ""),
            "run_id": run_id,
            "run": current,
            "report": _request(
                "GET",
                f"/api/lite/harness/security-assurance/runs/{run_id}/report",
                authenticated=True,
                session_token=lease["session_token"],
            ),
            "reattached": True,
            "sanitized": True,
        }
    if status == "PARTIAL":
        resumed = _request(
            "POST",
            f"/api/lite/harness/security-assurance/runs/{run_id}/resume",
            {},
            authenticated=True,
            session_token=lease["session_token"],
        )
        if str(resumed.get("resume_action") or "") not in {"requeued", "already_running"}:
            return {"status": "PARTIAL", "run_id": run_id, "run": resumed, "reattached": True, "sanitized": True}
    continuity_state = dict(state)
    result = _poll(
        run_id,
        lease=lease,
        principal_id=principal_id,
        key_file=key_file,
        continuity_path=continuity_path,
        continuity_state=continuity_state,
        session_ttl_seconds=session_ttl_seconds,
        max_poll_seconds=max_poll_seconds,
    )
    _ensure_lease(
        lease,
        principal_id=principal_id,
        key_file=key_file,
        ttl_seconds=session_ttl_seconds,
    )
    return {
        "status": _terminal_status(result),
        "suite_id": str(state.get("suite_id") or ""),
        "run_id": run_id,
        "run": result,
        "report": _request(
            "GET",
            f"/api/lite/harness/security-assurance/runs/{run_id}/report",
            authenticated=True,
            session_token=lease["session_token"],
        ),
        "reattached": True,
        "sanitized": True,
    }


def _cleanup_lease(
    lease: dict,
    *,
    continuity_path: Path,
    principal_id: str,
    key_file: str,
    ttl_seconds: int | None = None,
) -> dict:
    try:
        _ensure_lease(
            lease,
            principal_id=principal_id,
            key_file=key_file,
            ttl_seconds=ttl_seconds,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return {
            "status": "FAIL",
            "reason": str(exc)[:240],
            "session_ids": list(lease.get("session_ids") or []),
            "sanitized": True,
        }
    try:
        revoked = harness_client._request(
            "POST",
            "/api/lite/harness/principal/revoke",
            headers={"X-Pocket-Lab-Harness-Session": lease["session_token"]},
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return {
            "status": "FAIL",
            "reason": str(exc)[:240],
            "session_ids": list(lease.get("session_ids") or []),
            "sanitized": True,
        }
    _remove_continuity(continuity_path)
    return {
        "status": "PASS",
        "principal": revoked,
        "session_ids": list(lease.get("session_ids") or []),
        "sanitized": True,
    }


def _establish_lease(
    *,
    principal_id: str,
    key_path: Path,
    active_run_id: str | None,
    session_ttl_seconds: int | None,
) -> tuple[dict, bool]:
    """Reuse a registered principal; bootstrap only when it is absent."""
    key_file = str(key_path)
    try:
        session = harness_client.start_session(
            principal_id=principal_id,
            profile=FIXED_PROFILE,
            purpose=FIXED_PURPOSE,
            key_file=key_file,
            ttl_seconds=session_ttl_seconds,
        )
        return _session_lease(session), False
    except RuntimeError as exc:
        # A client crash can happen after bootstrap creates the principal but
        # before it admits a run. Reuse that principal instead of attempting a
        # second bootstrap. No other rejection is safe to reinterpret as
        # "principal absent".
        if active_run_id or str(exc).split(":", 1)[0].strip() != "principal_not_found":
            raise
    session = harness_client.bootstrap_session(
        principal_id=principal_id,
        key_file=key_file,
        ttl_seconds=session_ttl_seconds,
    )
    return _session_lease(session), True


def cmd_qualify(args: argparse.Namespace) -> dict:
    continuity_path = _continuity_path()
    state = _load_continuity(continuity_path)
    principal_id = str(args.principal_id or state.get("principal_id") or DEFAULT_PRINCIPAL_ID).strip().casefold()
    key_path = Path(args.key_file).expanduser() if args.key_file else Path(str(state.get("private_key_file_path") or DEFAULT_KEY_FILE))
    key_path, fingerprint = _ensure_qualification_key(key_path)
    state.update({
        "principal_id": principal_id,
        "public_key_fingerprint": fingerprint,
        "private_key_file_path": str(key_path),
    })
    _write_continuity(continuity_path, state)

    lease: dict | None = None
    reattached = None
    bootstrap_completed = False
    try:
        if state.get("active_run_id"):
            lease, bootstrap_completed = _establish_lease(
                principal_id=principal_id,
                key_path=key_path,
                active_run_id=str(state.get("active_run_id") or ""),
                session_ttl_seconds=args.session_ttl_seconds,
            )
            reattached = _reattach_or_resume(
                state=state,
                lease=lease,
                principal_id=principal_id,
                key_file=str(key_path),
                continuity_path=continuity_path,
                session_ttl_seconds=args.session_ttl_seconds,
                max_poll_seconds=args.max_poll_seconds,
            )
            if reattached is not None:
                cleanup = _cleanup_lease(
                    lease,
                    continuity_path=continuity_path,
                    principal_id=principal_id,
                    key_file=str(key_path),
                    ttl_seconds=args.session_ttl_seconds,
                )
                status = _terminal_status(reattached)
                return {
                    "status": status if cleanup["status"] == "PASS" else "PARTIAL",
                    "identity": {"principal_id": principal_id, "public_key_fingerprint": fingerprint, "private_key_path": str(key_path)},
                    "bootstrap": {"completed": False, "sanitized": True},
                    "reattached": reattached,
                    "cleanup": cleanup,
                    "session": {"renewal_count": int(lease.get("renewal_count") or 0), "session_ids": list(lease.get("session_ids") or [])},
                    "continuity_file": str(continuity_path),
                    "sanitized": True,
                }
        else:
            lease, bootstrap_completed = _establish_lease(
                principal_id=principal_id,
                key_path=key_path,
                active_run_id=None,
                session_ttl_seconds=args.session_ttl_seconds,
            )
    except (OSError, RuntimeError, ValueError):
        raise

    if lease is None:
        raise RuntimeError("assurance_session_invalid: no assurance session was established")

    preflight: dict = {"status": "blocked", "failure_code": "preflight_not_run", "sanitized": True}
    runs: dict[str, dict] = {
        "smoke": {"status": "NOT_RUN", "sanitized": True},
        "standard": {"status": "NOT_RUN", "sanitized": True},
        "adversarial": {"status": "NOT_RUN", "sanitized": True},
    }
    workflow_error: str | None = None
    policy_sync_result: dict = {"status": "NOT_RUN", "sanitized": True}
    try:
        if args.sync_policy:
            _ensure_lease(
                lease,
                principal_id=principal_id,
                key_file=str(key_path),
                ttl_seconds=args.session_ttl_seconds,
            )
            policy_sync_result = _sync_policy(
                lease,
                wait_seconds=args.policy_sync_wait_seconds,
                principal_id=principal_id,
                key_file=str(key_path),
                session_ttl_seconds=args.session_ttl_seconds,
            )
        preflight = _request(
            "GET",
            "/api/lite/harness/security-assurance/preflight?suite_id=smoke",
            authenticated=True,
            session_token=lease["session_token"],
        )
        if str(preflight.get("status") or "").casefold() == "ready":
            runs["smoke"] = _run_qualified_suite(
                suite_id="smoke",
                lease=lease,
                principal_id=principal_id,
                key_file=str(key_path),
                continuity_path=continuity_path,
                continuity_state=state,
                session_ttl_seconds=args.session_ttl_seconds,
                max_poll_seconds=args.max_poll_seconds,
            )
            if runs["smoke"]["status"] == "PASS" and not args.skip_standard:
                runs["standard"] = _run_qualified_suite(
                    suite_id="standard",
                    lease=lease,
                    principal_id=principal_id,
                    key_file=str(key_path),
                    continuity_path=continuity_path,
                    continuity_state=state,
                    session_ttl_seconds=args.session_ttl_seconds,
                    max_poll_seconds=args.max_poll_seconds,
                )
            else:
                runs["standard"] = {"status": "NOT_RUN", "reason": "Smoke did not pass or Standard was skipped", "sanitized": True}
            if runs["smoke"]["status"] == "PASS" and runs["standard"]["status"] in {"PASS", "NOT_RUN", "BLOCKED"} and not args.skip_adversarial:
                runs["adversarial"] = _run_qualified_suite(
                    suite_id="adversarial",
                    lease=lease,
                    principal_id=principal_id,
                    key_file=str(key_path),
                    continuity_path=continuity_path,
                    continuity_state=state,
                    session_ttl_seconds=args.session_ttl_seconds,
                    max_poll_seconds=args.max_poll_seconds,
                )
            else:
                runs["adversarial"] = {"status": "NOT_RUN", "reason": "Smoke did not pass or adversarial checks were skipped", "sanitized": True}
        else:
            runs["smoke"] = {"status": "BLOCKED", "preflight": preflight, "sanitized": True}
    except (OSError, RuntimeError, ValueError) as exc:
        workflow_error = str(exc)[:240]
        runs["smoke"] = {"status": "PARTIAL", "reason": "qualification client lost a bounded workflow step", "error": workflow_error, "sanitized": True}

    active_run = bool(state.get("active_run_id"))
    cleanup = _cleanup_lease(
        lease,
        continuity_path=continuity_path,
        principal_id=principal_id,
        key_file=str(key_path),
        ttl_seconds=args.session_ttl_seconds,
    ) if (not active_run or workflow_error is None) and all(
        str(item.get("status") or "").upper() in TERMINAL_STATUSES | {"NOT_RUN"} for item in runs.values()
    ) else {
        "status": "DEFERRED",
        "reason": "active run continuity was retained after a client-side interruption",
        "session_ids": list(lease.get("session_ids") or []),
        "sanitized": True,
    }
    statuses = [str(item.get("status") or "").upper() for item in runs.values()]
    if preflight.get("status") != "ready":
        overall = "BLOCKED"
    elif "FAIL" in statuses:
        overall = "FAIL"
    elif "BLOCKED" in statuses:
        overall = "BLOCKED"
    elif "PARTIAL" in statuses or cleanup.get("status") not in {"PASS", "DEFERRED"}:
        overall = "PARTIAL"
    else:
        overall = "PASS"
    return {
        "status": overall,
        "identity": {"principal_id": principal_id, "public_key_fingerprint": fingerprint, "private_key_path": str(key_path)},
        "bootstrap": {"completed": bootstrap_completed, "sanitized": True},
        "preflight": preflight,
        "policy_sync": policy_sync_result,
        "runs": runs,
        "cleanup": cleanup,
        "session": {
            "renewal_count": int(lease.get("renewal_count") or 0),
            "session_ids": list(lease.get("session_ids") or []),
        },
        "continuity_file": str(continuity_path),
        "sanitized": True,
    }


def cmd_report(args: argparse.Namespace) -> dict:
    run_id = _safe_run_id(args.run_id)
    return _request("GET", f"/api/lite/harness/security-assurance/runs/{run_id}/report", authenticated=True)


def cmd_compare(args: argparse.Namespace) -> dict:
    report = cmd_report(args)
    files = report.get("files") if isinstance(report.get("files"), dict) else {}
    return {"run_id": args.run_id, "delta": files.get("delta.json", {}), "sanitized": True}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pocket Lab loopback Runtime Security Assurance client")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="show registered assurance capabilities and suites")
    check.set_defaults(handler=cmd_check, success_status=True)

    preflight = commands.add_parser("preflight", help="run fixed local admission checks")
    preflight.add_argument("suite_id", choices=("smoke", "standard", "deep", "adversarial"))
    preflight.set_defaults(handler=cmd_preflight, success_status=False)

    policy_sync = commands.add_parser(
        "policy-sync",
        help="queue the current repository Safety Rules through the qualification-only supervisor lifecycle",
    )
    policy_sync.add_argument("--wait-seconds", type=float, default=120.0)
    policy_sync.set_defaults(
        handler=cmd_policy_sync,
        success_status=False,
    )

    fault = commands.add_parser(
        "fault",
        help="execute one fixed, one-use, non-destructive qualification service recovery control",
    )
    fault.add_argument(
        "fault_id",
        choices=("worker_restart_once", "nats_restart_once", "opa_restart_once"),
    )
    fault.set_defaults(handler=cmd_fault, success_status=False)

    run = commands.add_parser("run", help="run one registered assurance suite")
    run.add_argument("suite_id", choices=("smoke", "standard", "deep", "adversarial"))
    run.add_argument("--scenario-id", dest="scenario_id")
    run.add_argument("--baseline-run-id", dest="baseline_run_id")
    run.set_defaults(handler=cmd_run, success_status=False)

    scenario = commands.add_parser("scenario", help="run one registered scenario in Standard")
    scenario.add_argument("scenario_id")
    scenario.set_defaults(handler=lambda args: cmd_run(argparse.Namespace(
        suite_id="standard",
        scenario_id=args.scenario_id,
        baseline_run_id=None,
    )), success_status=False)

    qualify = commands.add_parser(
        "qualify",
        help="bootstrap or reattach a bounded Smoke/Standard/Adversarial qualification run",
    )
    qualify.add_argument("--principal-id", default=None)
    qualify.add_argument("--key-file", default=None)
    qualify.add_argument("--session-ttl-seconds", type=int, choices=range(60, 3601))
    qualify.add_argument("--max-poll-seconds", type=float, default=MAX_POLL_SECONDS)
    qualify.add_argument("--skip-standard", action="store_true")
    qualify.add_argument("--skip-adversarial", action="store_true")
    qualify.add_argument("--sync-policy", action="store_true", help="request the fixed qualification policy-source sync before suites")
    qualify.add_argument("--policy-sync-wait-seconds", type=float, default=120.0)
    qualify.set_defaults(handler=cmd_qualify, success_status=False)

    report = commands.add_parser("report", help="read a sanitized report")
    report.add_argument("run_id")
    report.set_defaults(handler=cmd_report, success_status=True)

    compare = commands.add_parser("compare", help="show the normalized baseline delta")
    compare.add_argument("run_id")
    compare.set_defaults(handler=cmd_compare, success_status=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = args.handler(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR {str(exc)[:320]}", file=sys.stderr)
        return 2
    print(json.dumps(harness_client._sanitize_output(result), ensure_ascii=True, sort_keys=True, indent=2))
    if args.success_status:
        return 0
    status = _terminal_status(result.get("run") if isinstance(result.get("run"), dict) else result)
    if status in {"READY", "PASS", "SUCCEEDED", "SUCCESS", "COMPLETED"}:
        return 0
    return {"FAIL": 10, "PARTIAL": 11, "BLOCKED": 12, "DEGRADED": 11}.get(status, 0)


if __name__ == "__main__":
    raise SystemExit(main())
