from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from typing import Any, Final

from .. import deps
from . import lite_security_policy as policy
from .lite_security_evidence import write_json

SCHEMA_VERSION: Final[int] = 1
_ALLOWED_FIELDS: Final[tuple[str, ...]] = (
    "frontend_session_id",
    "captured_at",
    "visibility_state",
    "online_state",
    "active_event_source_count",
    "active_poll_timer_count",
    "visibility_listener_count",
    "online_listener_count",
    "offline_listener_count",
    "reconnect_attempt_count",
    "backend_reconciliation_count",
    "cached_run_id",
    "backend_run_id",
    "cached_revision",
    "backend_revision",
    "write_actions_blocked",
    "duplicate_submission_count",
    "last_sse_opened_at",
    "last_sse_closed_at",
    "last_poll_started_at",
    "last_poll_stopped_at",
    "last_backend_reconciled_at",
)


def activation_path() -> Path:
    return deps.settings().state_dir / ".pocketlab-dev" / "gate-faults" / "android-lifecycle-diagnostics.json"


def reports_dir() -> Path:
    path = deps.settings().state_dir / ".pocketlab-dev" / "gate-faults" / "android-lifecycle-reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _activation() -> dict[str, Any] | None:
    path = activation_path()
    try:
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        expires = float(payload.get("expires_at_epoch") or 0)
    except (TypeError, ValueError):
        return None
    challenge = str(payload.get("challenge_id") or "")
    if expires <= time.time() or len(challenge) < 16 or len(challenge) > 128:
        return None
    return payload


def challenge() -> dict[str, Any]:
    payload = _activation()
    return {
        "active": bool(payload),
        "challenge_id": str(payload.get("challenge_id") or "") if payload else "",
        "expires_at_epoch": payload.get("expires_at_epoch") if payload else None,
        "sanitized": True,
    }


def _bounded_int(value: Any, minimum: int = 0, maximum: int = 100000) -> int:
    try:
        return max(minimum, min(maximum, int(value or 0)))
    except (TypeError, ValueError):
        return minimum


def sanitize_report(report: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key in _ALLOWED_FIELDS:
        value = report.get(key)
        if key.endswith("_count"):
            clean[key] = _bounded_int(value)
        elif key in {"online_state", "write_actions_blocked"}:
            clean[key] = bool(value)
        else:
            clean[key] = policy.redact_text(str(value or ""))[:160]
    clean["schema_version"] = SCHEMA_VERSION
    clean["sanitized"] = True
    return clean


def record(challenge_id: str, report: dict[str, Any]) -> dict[str, Any]:
    activation = _activation()
    expected = str((activation or {}).get("challenge_id") or "")
    if not activation or str(challenge_id or "") != expected:
        return {"accepted": False, "reason": "diagnostics_not_active", "sanitized": True}
    clean = sanitize_report(report)
    sequence = time.time_ns()
    write_json(reports_dir() / f"{expected}-{sequence}.json", clean)
    return {"accepted": True, "challenge_id": expected, "sanitized": True}
