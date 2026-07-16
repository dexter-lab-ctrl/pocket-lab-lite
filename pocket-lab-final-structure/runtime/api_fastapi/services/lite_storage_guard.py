from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import stat
import time
from pathlib import Path
from typing import Any, Final

from .. import deps

LOW_STORAGE_SCENARIO: Final[str] = "low-storage-threshold"
LOW_STORAGE_SCENARIO_HEADER: Final[str] = "x-pocketlab-gate-scenario"
LOW_STORAGE_TOKEN_HEADER: Final[str] = "x-pocketlab-gate-token"
_MAX_OVERRIDE_BYTES = 16 * 1024 * 1024 * 1024
_MAX_OVERRIDE_PERCENT = 95.0


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def minimum_free_bytes() -> int:
    return _bounded_int(
        "POCKETLAB_MIN_FREE_SPACE_BYTES",
        128 * 1024 * 1024,
        16 * 1024 * 1024,
        16 * 1024 * 1024 * 1024,
    )


def minimum_free_percent() -> float:
    return _bounded_float("POCKETLAB_MIN_FREE_SPACE_PERCENT", 3.0, 0.5, 50.0)


def emergency_reserve_bytes() -> int:
    return _bounded_int(
        "POCKETLAB_EMERGENCY_RESERVE_BYTES",
        16 * 1024 * 1024,
        1 * 1024 * 1024,
        1024 * 1024 * 1024,
    )


def gate_activation_path() -> Path:
    return deps.settings().state_dir / ".pocketlab-dev" / "gate-faults" / "low-storage-threshold.json"


def _loopback(host: str) -> bool:
    return str(host or "").strip().lower() in {"127.0.0.1", "::1", "localhost", "testclient"}


def _read_activation() -> dict[str, Any] | None:
    path = gate_activation_path()
    try:
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _authorized_override(request: Any | None) -> tuple[int, float] | None:
    if request is None:
        return None
    headers = getattr(request, "headers", {}) or {}
    if str(headers.get(LOW_STORAGE_SCENARIO_HEADER, "")) != LOW_STORAGE_SCENARIO:
        return None
    client = getattr(request, "client", None)
    if not _loopback(getattr(client, "host", "")):
        return None
    token = str(headers.get(LOW_STORAGE_TOKEN_HEADER, ""))
    if len(token) < 24 or len(token) > 256:
        return None
    activation = _read_activation()
    if not activation or activation.get("scenario") != LOW_STORAGE_SCENARIO:
        return None
    try:
        expires = float(activation.get("expires_at_epoch") or 0)
        floor_bytes = int(activation.get("minimum_free_bytes") or 0)
        floor_percent = float(activation.get("minimum_free_percent") or 0)
    except (TypeError, ValueError):
        return None
    if expires <= time.time():
        return None
    expected = str(activation.get("token_sha256") or "")
    actual = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if len(expected) != 64 or not hmac.compare_digest(expected, actual):
        return None
    if not 0 <= floor_bytes <= _MAX_OVERRIDE_BYTES or not 0 <= floor_percent <= _MAX_OVERRIDE_PERCENT:
        return None
    return floor_bytes, floor_percent


def storage_readiness(request: Any | None = None, *, root: Path | None = None) -> dict[str, Any]:
    target = (root or deps.settings().state_dir).expanduser().resolve(strict=False)
    try:
        usage = shutil.disk_usage(target)
        total = int(usage.total)
        free = int(usage.free)
        percent = (free / total * 100.0) if total > 0 else 0.0
        metrics_available = True
    except OSError:
        total = free = 0
        percent = 0.0
        metrics_available = False
    configured_bytes = minimum_free_bytes()
    configured_percent = minimum_free_percent()
    override = _authorized_override(request)
    effective_bytes = max(configured_bytes, override[0] if override else 0)
    effective_percent = max(configured_percent, override[1] if override else 0.0)
    ready = bool(metrics_available and free >= effective_bytes and percent >= effective_percent)
    reason = "ready" if ready else "storage_metrics_unavailable" if not metrics_available else "insufficient_storage"
    return {
        "ready": ready,
        "reason": reason,
        "free_bytes": free,
        "free_percent": round(percent, 3),
        "minimum_free_bytes": effective_bytes,
        "minimum_free_percent": round(effective_percent, 3),
        "emergency_reserve_bytes": emergency_reserve_bytes(),
        "gate_override_active": bool(override),
        "sanitized": True,
    }


def rejection_payload(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "rejected",
        "accepted": False,
        "reason": "insufficient_storage",
        "retryable": True,
        "message": "Pocket Lab needs more free storage before starting this check.",
        "storage": {
            "free_bytes": readiness.get("free_bytes"),
            "free_percent": readiness.get("free_percent"),
            "minimum_free_bytes": readiness.get("minimum_free_bytes"),
            "minimum_free_percent": readiness.get("minimum_free_percent"),
        },
        "sanitized": True,
    }
