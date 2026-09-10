from __future__ import annotations

import concurrent.futures
from contextlib import contextmanager
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
_RECOVERY_BASE_QUIESCING_FOR_DATABASE_SWITCH = False
RECOVERY_SUMMARY_STALE_AFTER_MS = 10_000
RECOVERY_SUMMARY_MAX_STALE_MS = 60_000
RECOVERY_DETAILS_STALE_AFTER_MS = 15_000
RECOVERY_DETAILS_MAX_STALE_MS = 90_000

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
    expected_actions = {
        str(action_id)
        for action_id, action in (payload.get("actions") or {}).items()
        if isinstance(action, dict)
    }
    revision = CONTROL_PLANE.update_app_subprojection(app_id, "operations", payload)
    committed = CONTROL_PLANE.app_actions_projection_snapshot(
        app_id, max_age_seconds=None
    )
    if not isinstance(committed, dict) or not committed:
        raise PreparedProjectionUnavailable("Committed projection was not readable from SQLite")
    committed_actions = committed.get("actions") if isinstance(committed.get("actions"), dict) else {}
    missing_actions = sorted(expected_actions.difference(committed_actions))
    if missing_actions:
        _LOGGER.error(
            "pocketlab.app_projection.commit_incomplete app_id=%s missing_count=%s",
            app_id, len(missing_actions),
        )
        raise PreparedProjectionUnavailable("Committed projection did not preserve the action contract")
    if int(committed.get("source_revision") or 0) <= 0:
        raise PreparedProjectionUnavailable("Committed projection revision is unavailable")
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
    if future.cancelled():
        with _RECOVERY_BASE_LOCK:
            if _RECOVERY_BASE_FUTURE is future:
                _RECOVERY_BASE_FUTURE = None
        return
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
        if cached is not None and now - cached[1] <= 8.0:
            return dict(cached[0])
        # Do not launch a collector from this fence-sensitive path. Recovery
        # details are assembled from independently prepared SQLite-backed
        # stages below; the worker-owned recovery.summary job will populate
        # the prepared base snapshot. Launching either the legacy deep details
        # collector or a repository-backed summary fallback here can monopolize
        # the single Recovery-base executor on Termux and prevent the database
        # switch fence from quiescing.
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


def begin_recovery_base_database_switch(*, timeout_seconds: float = 5.0) -> bool:
    """Drain and hold the core Recovery-base reader for a SQLite handoff."""
    global _RECOVERY_BASE_FUTURE, _RECOVERY_BASE_VALUE
    global _RECOVERY_BASE_FAILURES, _RECOVERY_BASE_NEXT_ALLOWED
    global _RECOVERY_BASE_QUIESCING_FOR_DATABASE_SWITCH

    deadline = time.monotonic() + max(0.1, min(float(timeout_seconds), 120.0))
    with _RECOVERY_BASE_LOCK:
        _RECOVERY_BASE_QUIESCING_FOR_DATABASE_SWITCH = True
        future = _RECOVERY_BASE_FUTURE
        if future is not None and not future.running():
            future.cancel()

    try:
        if future is not None:
            while not future.done():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                concurrent.futures.wait(
                    (future,),
                    timeout=min(0.1, remaining),
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
        with _RECOVERY_BASE_LOCK:
            if _RECOVERY_BASE_FUTURE is future:
                _RECOVERY_BASE_FUTURE = None
            _RECOVERY_BASE_VALUE = None
            _RECOVERY_BASE_FAILURES = 0
            _RECOVERY_BASE_NEXT_ALLOWED = 0.0
        return True
    except BaseException:
        end_recovery_base_database_switch()
        raise


def end_recovery_base_database_switch() -> None:
    """Release the core Recovery-base database-switch fence."""
    global _RECOVERY_BASE_QUIESCING_FOR_DATABASE_SWITCH
    with _RECOVERY_BASE_LOCK:
        _RECOVERY_BASE_QUIESCING_FOR_DATABASE_SWITCH = False


@contextmanager
def recovery_base_database_switch_fence(*, timeout_seconds: float = 5.0):
    """Hold the core Recovery-base reader quiescent across SQLite replacement."""
    if not begin_recovery_base_database_switch(timeout_seconds=timeout_seconds):
        end_recovery_base_database_switch()
        raise RuntimeError("Recovery base reader did not quiesce before database promotion")
    try:
        yield
    finally:
        end_recovery_base_database_switch()


def quiesce_recovery_base_for_database_switch(*, timeout_seconds: float = 5.0) -> bool:
    """Drain the core Recovery-base reader for compatibility with existing callers."""
    try:
        with recovery_base_database_switch_fence(timeout_seconds=timeout_seconds):
            return True
    except RuntimeError:
        return False


def recovery_details_payload() -> dict[str, Any]:
    timings: dict[str, float] = {}
    state = _timed_stage(timings, "recovery_base", recovery_base_subprojection)

    def saved_app_lifecycle() -> dict[str, Any]:
        """Use the canonical App projection when the worker cache is cold.

        Recovery details are a critical prepared read. Re-running the full
        App Lifecycle collector here couples its freshness to the app-stage
        executor and can consume most of the Recovery deadline on Termux.
        The dedicated apps.lifecycle job owns that collector; Recovery should
        compose its last committed SQLite snapshot and let that job refresh it.
        """
        prepared = CONTROL_PLANE.prepared_payload(APP_LIFECYCLE_CACHE_KEY)
        if isinstance(prepared, dict):
            return prepared
        snapshot = CONTROL_PLANE.app_lifecycle_projection_snapshot()
        if isinstance(snapshot, dict):
            return snapshot
        return {
            "status": "degraded",
            "summary": "Saved App Lifecycle state is refreshing.",
            "apps": [],
            "items": [],
            "count": 0,
            "projection_only": True,
        }

    lifecycle = _timed_stage(
        timings,
        "app_lifecycle_profiles",
        saved_app_lifecycle,
    )

    def saved_app_backup_profiles() -> dict[str, Any]:
        """Compose app-backup cards from the committed App Lifecycle snapshot."""
        apps = lifecycle.get("apps") if isinstance(lifecycle, dict) else []
        profiles: list[dict[str, Any]] = []
        for app in apps if isinstance(apps, list) else []:
            if not isinstance(app, dict):
                continue
            backup = app.get("backup") if isinstance(app.get("backup"), dict) else {}
            profiles.append(
                {
                    "app_id": str(app.get("app_id") or "photoprism"),
                    "name": str(app.get("name") or "PhotoPrism"),
                    **backup,
                }
            )
        return {
            "status": lifecycle.get("status") or "degraded",
            "summary": "Saved app backup profiles are available."
            if profiles
            else "Saved app backup profiles are refreshing.",
            "apps": profiles,
            "count": len(profiles),
            "updated_at": lifecycle.get("updated_at"),
            "read_degraded": bool(lifecycle.get("read_degraded")) or not profiles,
            "refresh_pending": bool(lifecycle.get("refresh_pending")),
            "projection_only": True,
        }

    profiles = _timed_stage(
        timings,
        "app_backup_profiles",
        saved_app_backup_profiles,
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
    # Registration is a scheduler concern, not a prepared-read request. The
    # previous implementation called prepared_only_read for every core job,
    # which performed request-path status work (and could start the dispatcher)
    # while the worker was still booting. Install the same semantic contract
    # directly, just as the Phase 3B/3C registries do; startup warm-up remains
    # the only path that marks these jobs dirty.
    from .lite_semantic_revisions import contract_for
    from .projection_scheduler import PROJECTION_SCHEDULER, ProjectionJob

    contract = contract_for(domain, key)
    effective_priority = int(contract.priority if contract is not None else priority)
    effective_work_class = str(contract.work_class if contract is not None else work_class)
    effective_deadline = float(
        contract.deadline_seconds if contract is not None else deadline_seconds
    )
    source_revision = contract.source_revision if contract is not None else None
    max_probe_seconds = contract.max_probe_seconds if contract is not None else 900.0
    quiet_window_seconds = contract.quiet_window_seconds if contract is not None else 0.0
    PROJECTION_SCHEDULER.register(
        ProjectionJob(
            domain=f"{domain}.{key}",
            builder=builder,
            projector=projector,
            priority=effective_priority,
            work_class=effective_work_class,
            deadline_seconds=effective_deadline,
            optional=effective_work_class not in {"critical", "recovery"},
            source_revision=source_revision,
            max_probe_seconds=max_probe_seconds,
            quiet_window_seconds=quiet_window_seconds,
        )
    )
    return True


def register_jobs() -> dict[str, bool]:
    # The worker is the normal projection executor. Install the same Device Facts
    # adapters used by the API before any builder or source-revision callback is
    # captured so worker-owned fleet/status projections cannot persist legacy
    # health semantics.
    from .lite_device_runtime_extensions import install_runtime_extensions

    install_runtime_extensions()
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
            builder=lambda: lite_status.lite_fleet(),
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
            deadline_seconds=8.0, priority=10, work_class="recovery",
        ),
        "recovery_details": _register_job(
            domain="recovery", key="details", snapshot_builder=lambda: CONTROL_PLANE.recovery_projection_snapshot(details=True),
            builder=recovery_details_payload,
            projector=lambda payload: _project_for_database(expected_database_path, CONTROL_PLANE.project_recovery, payload),
            deadline_seconds=10.0, priority=15, work_class="recovery",
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
        ("apps", "apps", "lifecycle", lite_app_lifecycle.app_lifecycle_profiles, CONTROL_PLANE.app_lifecycle_projection_snapshot, CONTROL_PLANE.project_app_lifecycle, 8.0, 40, "cpu"),
        ("catalog", "apps", "catalog", catalog_payload, CONTROL_PLANE.app_catalog_projection_snapshot, CONTROL_PLANE.project_app_catalog, 8.0, 45, "io"),
        (
            "app_actions_photoprism", "apps", "actions:photoprism", app_actions_payload, app_actions_snapshot,
            lambda payload: project_app_actions_payload("photoprism", payload),
            6.0, 30, "io",
        ),
        ("fleet", "fleet", "summary", lambda: lite_status.lite_fleet(), CONTROL_PLANE.fleet_projection_snapshot, CONTROL_PLANE.project_fleet, 20.0, 15, "critical"),
        ("recovery_summary", "recovery", "summary", recovery_summary_payload, CONTROL_PLANE.recovery_projection_snapshot, CONTROL_PLANE.project_recovery, 8.0, 10, "recovery"),
        ("recovery_details", "recovery", "details", recovery_details_payload, lambda: CONTROL_PLANE.recovery_projection_snapshot(details=True), CONTROL_PLANE.project_recovery, 10.0, 15, "recovery"),
    )
    results: dict[str, bool] = {}
    for name, domain, key, builder, snapshot_builder, projector, deadline, priority, work_class in jobs:
        results[name] = CONTROL_PLANE.warm_prepared_read(
            domain=domain,
            key=key,
            snapshot_builder=snapshot_builder,
            builder=builder,
            projector=lambda payload, p=projector: _project_for_database(expected_database_path, p, payload),
            deadline_seconds=deadline,
            priority=priority,
            work_class=work_class,
        )
    return results
