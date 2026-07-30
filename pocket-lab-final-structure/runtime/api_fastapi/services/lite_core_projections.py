from __future__ import annotations

import concurrent.futures
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..db.connection import database_path
from . import (
    lite_app_actions,
    lite_app_lifecycle,
    lite_catalog,
    lite_catalog_live,
    lite_recovery_subprojections,
    lite_status,
)
from .lite_control_plane_store import CONTROL_PLANE, PreparedProjectionUnavailable

_LOGGER = logging.getLogger(__name__)

APP_PROJECTION_SCHEMA_VERSION = 3
APP_CATALOG_DOMAIN = "apps.catalog"
APP_LIFECYCLE_DOMAIN = "apps.lifecycle"
APP_ACTIONS_DOMAIN_PREFIX = "apps.actions:"
APP_ACTIONS_PHOTOPRISM_DOMAIN = "apps.actions:photoprism"
APP_CATALOG_CACHE_KEY = "apps:catalog"
APP_LIFECYCLE_CACHE_KEY = "apps:lifecycle"
APP_ACTIONS_CACHE_KEY_PREFIX = "apps:actions:"
_RECOVERY_BASE_LOCK = threading.Lock()
_RECOVERY_BASE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="pocketlab-recovery-base"
)
_RECOVERY_BASE_VALUE: tuple[dict[str, Any], float] | None = None
_RECOVERY_BASE_FUTURE: concurrent.futures.Future[Any] | None = None
_RECOVERY_BASE_FAILURES = 0
_RECOVERY_BASE_NEXT_ALLOWED = 0.0

CORE_PROJECTION_DOMAINS = frozenset(
    {
        "fleet.summary",
        APP_CATALOG_DOMAIN,
        APP_LIFECYCLE_DOMAIN,
        APP_ACTIONS_PHOTOPRISM_DOMAIN,
        "recovery.summary",
        "recovery.details",
    }
)

# A missing first snapshot for any of these domains makes a primary Lite screen
# unusable. The scheduler grants these domains one bounded bootstrap execution
# before normal adaptive pressure admission applies.
HOME_CRITICAL_BOOTSTRAP_DOMAINS = frozenset(
    {
        "system.status",
        "system.health",
        "system.fleet_probe",
        "system.nats_remote",
        "system.telemetry_thresholds",
        "system.storage_pressure",
        "system.sqlite_health",
        "system.activity_current",
        "system.activity_history",
    }
)

UI_CRITICAL_BOOTSTRAP_DOMAINS = CORE_PROJECTION_DOMAINS | HOME_CRITICAL_BOOTSTRAP_DOMAINS


def catalog_payload() -> dict[str, Any]:
    return lite_app_lifecycle.hydrate_catalog_lifecycle(
        lite_catalog_live.hydrate_catalog(lite_catalog.catalog_payload(None))
    )


def app_actions_snapshot(app_id: str = "photoprism") -> dict[str, Any] | None:
    saved = CONTROL_PLANE.app_current_subprojections(app_id)
    if not saved:
        return None
    operations = (
        saved.get("operations")
        if isinstance(saved.get("operations"), dict)
        else {}
    )
    if not operations:
        return None
    return {
        **operations,
        "app_id": app_id,
        "projection_only": True,
        "updated_at": saved.get("updated_at"),
        "summary": operations.get("summary") or "Showing the latest saved app actions.",
    }


def app_actions_payload(app_id: str = "photoprism") -> dict[str, Any]:
    return lite_app_actions.app_actions(app_id)


def project_app_actions_payload(app_id: str, payload: dict[str, Any]) -> int:
    """Commit an App action projection after fencing its parent row.

    Startup jobs are concurrent, so an action job may arrive before catalog or
    lifecycle has created app_current_state. The worker may bootstrap that row
    once; request paths remain prepared-read only.
    """
    if not CONTROL_PLANE.ensure_app_projection_parent(
        app_id, app_name=str(payload.get("name") or app_id)
    ):
        raise PreparedProjectionUnavailable("App action projection parent row is unavailable")
    revision = CONTROL_PLANE.update_app_subprojection(app_id, "operations", payload)
    committed = CONTROL_PLANE.app_actions_projection_snapshot(app_id)
    if not isinstance(committed, dict) or not committed:
        raise PreparedProjectionUnavailable("App action projection parent row is unavailable")
    return revision


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
        lambda: CONTROL_PLANE.prepared_payload(APP_LIFECYCLE_CACHE_KEY) or lite_app_lifecycle.app_lifecycle_profiles(),
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
        "catalog": _register_job(
            domain="apps",
            key="catalog",
            snapshot_builder=CONTROL_PLANE.app_catalog_projection_snapshot,
            builder=catalog_payload,
            projector=lambda payload: _project_for_database(
                expected_database_path, CONTROL_PLANE.project_app_catalog, payload
            ),
            deadline_seconds=8.0, priority=45, work_class="io",
        ),
        "app_actions_photoprism": _register_job(
            domain="apps",
            key="actions:photoprism",
            snapshot_builder=app_actions_snapshot,
            builder=app_actions_payload,
            projector=lambda payload: _project_for_database(
                expected_database_path,
                lambda value: project_app_actions_payload("photoprism", value),
                payload,
            ),
            deadline_seconds=6.0, priority=30, work_class="io",
        ),
        "fleet": _register_job(
            domain="fleet", key="summary", snapshot_builder=CONTROL_PLANE.fleet_projection_snapshot,
            builder=lite_status.lite_fleet,
            projector=lambda payload: _project_for_database(expected_database_path, CONTROL_PLANE.project_fleet, payload),
            deadline_seconds=20.0, priority=15, work_class="critical",
        ),
        "apps": _register_job(
            domain="apps", key="lifecycle", snapshot_builder=CONTROL_PLANE.app_lifecycle_projection_snapshot,
            builder=lite_app_lifecycle.app_lifecycle_profiles,
            projector=lambda payload: _project_for_database(expected_database_path, CONTROL_PLANE.project_app_lifecycle, payload),
            deadline_seconds=8.0, priority=25, work_class="critical",
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



def reconcile_app_projection_schema() -> dict[str, Any]:
    """Idempotently fence obsolete App projections without deleting history."""
    snapshot = CONTROL_PLANE.app_catalog_projection_snapshot()
    stored_schema = int((snapshot or {}).get("projection_schema_version") or 0)
    stale = bool(snapshot) and stored_schema < APP_PROJECTION_SCHEMA_VERSION
    if stale:
        CONTROL_PLANE.invalidate_domain("apps")
    return {
        "schema_version": APP_PROJECTION_SCHEMA_VERSION,
        "stored_schema_version": stored_schema,
        "rebuild_required": stale or snapshot is None,
        "history_preserved": True,
        "database_wiped": False,
        "sanitized": True,
    }

def schedule_startup_warmup() -> dict[str, bool]:
    if os.environ.get("POCKETLAB_LITE_DISABLE_PROJECTION_WARMUP", "").lower() in {"1", "true", "yes", "on"}:
        return {"catalog": False, "app_actions_photoprism": False, "fleet": False, "apps": False, "recovery_summary": False, "recovery_details": False}
    reconcile_app_projection_schema()
    register_jobs()
    expected_database_path = str(database_path())
    jobs = (
        # Canonical dependency order: lifecycle truth, catalog card, actions.
        ("apps", "apps", "lifecycle", lite_app_lifecycle.app_lifecycle_profiles, CONTROL_PLANE.project_app_lifecycle, 8.0, 40, "cpu"),
        ("catalog", "apps", "catalog", catalog_payload, CONTROL_PLANE.project_app_catalog, 8.0, 45, "io"),
        (
            "app_actions_photoprism", "apps", "actions:photoprism", app_actions_payload,
            lambda payload: project_app_actions_payload("photoprism", payload),
            6.0, 30, "io",
        ),
        ("fleet", "fleet", "summary", lite_status.lite_fleet, CONTROL_PLANE.project_fleet, 20.0, 15, "critical"),
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
