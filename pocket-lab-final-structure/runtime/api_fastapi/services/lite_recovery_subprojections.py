from __future__ import annotations

import concurrent.futures
import logging
import os
import sys
import threading
import time
from typing import Any, Callable

from .. import deps
from . import lite_app_backup_targets, lite_database_recovery, lite_security_maintenance, lite_status

_LOGGER = logging.getLogger(__name__)
_LOCK = threading.RLock()


def _is_termux() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "").lower() or sys.platform == "android"


_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1 if _is_termux() else 2,
    thread_name_prefix="pocketlab-recovery-subprojection",
)
_VALUES: dict[str, tuple[dict[str, Any], float]] = {}
_FUTURES: dict[str, concurrent.futures.Future[Any]] = {}
_FAILURES: dict[str, int] = {}
_NEXT_ALLOWED: dict[str, float] = {}
_DURATIONS: dict[str, float] = {}


def _done(name: str, started: float, future: concurrent.futures.Future[Any]) -> None:
    duration = max(0.0, time.monotonic() - started)
    try:
        value = future.result()
        if not isinstance(value, dict):
            raise TypeError("Recovery subprojection must return a mapping")
    except Exception as exc:
        with _LOCK:
            failures = min(8, _FAILURES.get(name, 0) + 1)
            _FAILURES[name] = failures
            _DURATIONS[name] = duration
            _NEXT_ALLOWED[name] = time.monotonic() + min(300.0, 2.0 ** failures)
            _FUTURES.pop(name, None)
        _LOGGER.warning(
            "pocketlab.recovery_subprojection.refresh_degraded key=%s error_type=%s",
            name,
            type(exc).__name__,
        )
        return
    with _LOCK:
        _VALUES[name] = (dict(value), time.monotonic())
        _FAILURES[name] = 0
        _DURATIONS[name] = duration
        _NEXT_ALLOWED[name] = time.monotonic() + min(300.0, max(30.0, duration * 2.0))
        _FUTURES.pop(name, None)


def _cached(
    name: str,
    callback: Callable[[], dict[str, Any]],
    fallback: dict[str, Any],
    *,
    wait_seconds: float,
    ttl_seconds: float,
) -> dict[str, Any]:
    now = time.monotonic()
    with _LOCK:
        cached = _VALUES.get(name)
        future = _FUTURES.get(name)
        duration = _DURATIONS.get(name, 0.0)
        dynamic_ttl = min(900.0, max(ttl_seconds, 120.0, duration * 5.0))
        if cached is not None and now - cached[1] <= dynamic_ttl:
            return dict(cached[0])
        if future is None and now >= _NEXT_ALLOWED.get(name, 0.0):
            started = time.monotonic()
            future = _EXECUTOR.submit(callback)
            setattr(future, "_pocketlab_started", started)
            _FUTURES[name] = future
            future.add_done_callback(
                lambda completed, key=name, began=started: _done(key, began, completed)
            )
    if future is not None and wait_seconds > 0:
        try:
            value = future.result(timeout=max(0.01, wait_seconds))
            if isinstance(value, dict):
                return dict(value)
        except concurrent.futures.TimeoutError:
            pass
        except Exception:
            pass
    if cached is not None:
        value = dict(cached[0])
        value["read_degraded"] = True
        value["refresh_pending"] = future is not None
        return value
    value = dict(fallback)
    value["read_degraded"] = True
    value["refresh_pending"] = future is not None
    return value


def recovery_summary() -> dict[str, Any]:
    return _cached(
        "recovery:base-summary",
        lite_status.lite_recovery_summary,
        {
            "status": "degraded",
            "summary": "Recovery summary is refreshing.",
            "updated_at": deps.now_utc_iso(),
        },
        wait_seconds=0.75,
        ttl_seconds=180.0,
    )


def database_protection_summary() -> dict[str, Any]:
    return _cached(
        "recovery:database-summary",
        lite_database_recovery.database_recovery_summary,
        {
            "status": "degraded",
            "summary": "Database protection status is refreshing.",
            "view_model": "database-recovery-summary-r3-v1",
            "sanitized": True,
        },
        wait_seconds=0.75,
        ttl_seconds=300.0,
    )


def database_protection_details() -> dict[str, Any]:
    summary = database_protection_summary()
    fallback = {
        **summary,
        "status": summary.get("status") or "degraded",
        "summary": summary.get("summary") or "Database protection details are refreshing.",
        "history_deferred": True,
        "sanitized": True,
    }
    return _cached(
        "recovery:database-details",
        lite_database_recovery.database_recovery_status,
        fallback,
        wait_seconds=1.0,
        ttl_seconds=600.0,
    )


def maintenance_state() -> dict[str, Any]:
    return _cached(
        "recovery:maintenance",
        lite_security_maintenance.maintenance_state,
        {
            "active": False,
            "state": "unknown",
            "summary": "Maintenance status is refreshing.",
            "writers_stopped": False,
            "sanitized": True,
        },
        wait_seconds=0.25,
        ttl_seconds=60.0,
    )


def backup_targets() -> dict[str, Any]:
    return _cached(
        "recovery:backup-targets",
        lite_app_backup_targets.backup_targets,
        {
            "status": "degraded",
            "summary": "Backup targets are refreshing.",
            "targets": [],
            "items": [],
            "count": 0,
            "ready_count": 0,
            "updated_at": deps.now_utc_iso(),
        },
        wait_seconds=0.5,
        ttl_seconds=180.0,
    )


def app_backup_targets(app_id: str = "photoprism") -> dict[str, Any]:
    payload = backup_targets()
    return {
        **payload,
        "app_id": str(app_id or "photoprism"),
        "name": "PhotoPrism",
    }


def warm_startup_dependencies() -> dict[str, bool]:
    """Prime shared Recovery sources in the background before prepared composition."""
    callbacks = (
        ("recovery_summary", recovery_summary),
        ("database_summary", database_protection_summary),
        ("maintenance", maintenance_state),
        ("backup_targets", backup_targets),
        ("database_details", database_protection_details),
    )
    for _name, callback in callbacks:
        callback()
    deadline = time.monotonic() + max(
        5.0,
        min(180.0, float(os.environ.get("POCKETLAB_LITE_RECOVERY_WARMUP_SECONDS", "90"))),
    )
    while time.monotonic() < deadline:
        with _LOCK:
            if not _FUTURES:
                break
        time.sleep(0.1)
    results: dict[str, bool] = {}
    for name, callback in callbacks:
        payload = callback()
        results[name] = isinstance(payload, dict) and not bool(payload.get("read_degraded"))
    return results


def diagnostics() -> dict[str, Any]:
    now = time.monotonic()
    with _LOCK:
        return {
            "refreshing": {key: round(max(0.0, now - future._pocketlab_started), 3) for key, future in _FUTURES.items() if hasattr(future, "_pocketlab_started")},
            "cached_keys": sorted(_VALUES),
            "failures": dict(_FAILURES),
            "durations_ms": {key: round(value * 1000.0, 3) for key, value in _DURATIONS.items()},
            "sanitized": True,
        }
