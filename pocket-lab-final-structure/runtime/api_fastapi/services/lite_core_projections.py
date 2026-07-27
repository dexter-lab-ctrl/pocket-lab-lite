from __future__ import annotations

import concurrent.futures
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..db.connection import database_path
from . import lite_app_lifecycle, lite_recovery_subprojections, lite_status
from .lite_control_plane_store import CONTROL_PLANE, PreparedProjectionUnavailable

_LOGGER = logging.getLogger(__name__)
_RECOVERY_BASE_LOCK = threading.Lock()
_RECOVERY_BASE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="pocketlab-recovery-base"
)
_RECOVERY_BASE_VALUE: tuple[dict[str, Any], float] | None = None
_RECOVERY_BASE_FUTURE: concurrent.futures.Future[Any] | None = None
_RECOVERY_BASE_FAILURES = 0
_RECOVERY_BASE_NEXT_ALLOWED = 0.0

CORE_PROJECTION_DOMAINS = frozenset(
    {"fleet.summary", "apps.lifecycle", "recovery.summary", "recovery.details"}
)


def _timed_stage(timings: dict[str, float], name: str, callback: Callable[[], Any]) -> Any:
    started = time.monotonic()
    try:
        return callback()
    finally:
        timings[name] = round(max(0.0, (time.monotonic() - started) * 1000.0), 3)


def _recovery_base_done(future: concurrent.futures.Future[Any]) -> None:
    global _RECOVERY_BASE_VALUE, _RECOVERY_BASE_FUTURE
    global _RECOVERY_BASE_FAILURES, _RECOVERY_BASE_NEXT_ALLOWED
    try:
        value = future.result()
        if not isinstance(value, dict):
            raise TypeError("Recovery base must return a mapping")
    except Exception as exc:
        with _RECOVERY_BASE_LOCK:
            _RECOVERY_BASE_FAILURES = min(8, _RECOVERY_BASE_FAILURES + 1)
            _RECOVERY_BASE_NEXT_ALLOWED = time.monotonic() + min(300.0, 2.0 ** _RECOVERY_BASE_FAILURES)
            _RECOVERY_BASE_FUTURE = None
        _LOGGER.warning("pocketlab.recovery_base.refresh_degraded error_type=%s", type(exc).__name__)
        return
    with _RECOVERY_BASE_LOCK:
        _RECOVERY_BASE_VALUE = (value, time.monotonic())
        _RECOVERY_BASE_FAILURES = 0
        _RECOVERY_BASE_NEXT_ALLOWED = time.monotonic() + 60.0
        _RECOVERY_BASE_FUTURE = None


def recovery_base_subprojection() -> dict[str, Any]:
    global _RECOVERY_BASE_FUTURE
    prepared_summary = CONTROL_PLANE.prepared_payload("recovery:summary")
    if prepared_summary is not None:
        return prepared_summary
    now = time.monotonic()
    with _RECOVERY_BASE_LOCK:
        cached = _RECOVERY_BASE_VALUE
        future = _RECOVERY_BASE_FUTURE
        if cached is not None and now - cached[1] <= 300.0:
            return dict(cached[0])
        if future is None and now >= _RECOVERY_BASE_NEXT_ALLOWED:
            future = _RECOVERY_BASE_EXECUTOR.submit(lite_status.lite_recovery_details)
            _RECOVERY_BASE_FUTURE = future
            future.add_done_callback(_recovery_base_done)
    if future is not None:
        try:
            result = future.result(timeout=1.5)
            if isinstance(result, dict):
                return dict(result)
        except concurrent.futures.TimeoutError:
            pass
        except Exception:
            pass
    if cached is not None:
        result = dict(cached[0])
        result["read_degraded"] = True
        result["refresh_pending"] = future is not None
        return result
    return {
        "status": "degraded",
        "summary": "Recovery details are refreshing.",
        "read_degraded": True,
        "refresh_pending": future is not None,
    }


def recovery_details_payload() -> dict[str, Any]:
    timings: dict[str, float] = {}
    state = _timed_stage(timings, "recovery_base", recovery_base_subprojection)
    profiles = _timed_stage(timings, "app_backup_profiles", lite_app_lifecycle.cached_app_backup_profiles)
    lifecycle = _timed_stage(
        timings,
        "app_lifecycle_profiles",
        lambda: CONTROL_PLANE.prepared_payload("apps:lifecycle") or lite_app_lifecycle.app_lifecycle_profiles(),
    )
    targets = _timed_stage(timings, "backup_targets", lite_recovery_subprojections.backup_targets)
    state["view_model"] = "recovery-details-r3-v1"
    state["app_backups"] = profiles.get("apps", [])
    state["app_backup_profiles"] = profiles
    state["app_lifecycle_profiles"] = lifecycle
    state["backup_targets"] = targets.get("targets", [])
    state["backup_target_profiles"] = targets
    state["database_protection"] = _timed_stage(
        timings, "database_protection", lite_recovery_subprojections.database_protection_details
    )
    state["maintenance"] = _timed_stage(timings, "maintenance", lite_recovery_subprojections.maintenance_state)
    state["__projection_stage_timing_ms"] = timings
    return state


def recovery_summary_payload() -> dict[str, Any]:
    timings: dict[str, float] = {}
    state = _timed_stage(timings, "recovery_summary", lite_recovery_subprojections.recovery_summary)
    state["database_protection"] = _timed_stage(
        timings, "database_protection_summary", lite_recovery_subprojections.database_protection_summary
    )
    state["maintenance"] = _timed_stage(timings, "maintenance", lite_recovery_subprojections.maintenance_state)
    state["__projection_stage_timing_ms"] = timings
    return state


def _project_for_database(expected_database_path: str, projector: Callable[[dict[str, Any]], int], payload: dict[str, Any]) -> int:
    if str(database_path()) != expected_database_path:
        raise PreparedProjectionUnavailable("Projection warm-up database changed before commit")
    return projector(payload)


def _register_job(
    *, domain: str, key: str, snapshot_builder: Callable[[], dict[str, Any] | None],
    builder: Callable[[], dict[str, Any]], projector: Callable[[dict[str, Any]], int],
    deadline_seconds: float, priority: int, work_class: str,
) -> bool:
    try:
        CONTROL_PLANE.prepared_only_read(
            domain=domain,
            key=key,
            snapshot_builder=snapshot_builder,
            builder=builder,
            projector=projector,
            stale_after_ms=0,
            max_stale_ms=0,
            deadline_seconds=deadline_seconds,
            priority=priority,
            work_class=work_class,
        )
    except PreparedProjectionUnavailable:
        pass
    return True


def register_jobs() -> dict[str, bool]:
    expected_database_path = str(database_path())
    return {
        "fleet": _register_job(
            domain="fleet", key="summary", snapshot_builder=CONTROL_PLANE.fleet_projection_snapshot,
            builder=lite_status.lite_fleet,
            projector=lambda payload: _project_for_database(expected_database_path, CONTROL_PLANE.project_fleet, payload),
            deadline_seconds=20.0, priority=15, work_class="critical",
        ),
        "apps": _register_job(
            domain="apps", key="lifecycle", snapshot_builder=CONTROL_PLANE.apps_projection_snapshot,
            builder=lite_app_lifecycle.app_lifecycle_profiles,
            projector=lambda payload: _project_for_database(expected_database_path, CONTROL_PLANE.project_apps, payload),
            deadline_seconds=8.0, priority=40, work_class="cpu",
        ),
        "recovery_summary": _register_job(
            domain="recovery", key="summary", snapshot_builder=CONTROL_PLANE.recovery_projection_snapshot,
            builder=recovery_summary_payload,
            projector=lambda payload: _project_for_database(expected_database_path, CONTROL_PLANE.project_recovery, payload),
            deadline_seconds=4.0, priority=50, work_class="io",
        ),
        "recovery_details": _register_job(
            domain="recovery", key="details", snapshot_builder=lambda: CONTROL_PLANE.recovery_projection_snapshot(details=True),
            builder=recovery_details_payload,
            projector=lambda payload: _project_for_database(expected_database_path, CONTROL_PLANE.project_recovery, payload),
            deadline_seconds=8.0, priority=60, work_class="io",
        ),
    }


def schedule_startup_warmup() -> dict[str, bool]:
    if os.environ.get("POCKETLAB_LITE_DISABLE_PROJECTION_WARMUP", "").lower() in {"1", "true", "yes", "on"}:
        return {"fleet": False, "apps": False, "recovery_summary": False, "recovery_details": False}
    register_jobs()
    expected_database_path = str(database_path())
    jobs = (
        ("fleet", "fleet", "summary", lite_status.lite_fleet, CONTROL_PLANE.project_fleet, 20.0, 15, "critical"),
        ("apps", "apps", "lifecycle", lite_app_lifecycle.app_lifecycle_profiles, CONTROL_PLANE.project_apps, 8.0, 40, "cpu"),
        ("recovery_summary", "recovery", "summary", recovery_summary_payload, CONTROL_PLANE.project_recovery, 4.0, 50, "io"),
        ("recovery_details", "recovery", "details", recovery_details_payload, CONTROL_PLANE.project_recovery, 8.0, 60, "io"),
    )
    results: dict[str, bool] = {}
    for name, domain, key, builder, projector, deadline, priority, work_class in jobs:
        results[name] = CONTROL_PLANE.warm_prepared_read(
            domain=domain,
            key=key,
            builder=builder,
            projector=lambda payload, p=projector: _project_for_database(expected_database_path, p, payload),
            deadline_seconds=deadline,
            priority=priority,
            work_class=work_class,
        )
    return results
