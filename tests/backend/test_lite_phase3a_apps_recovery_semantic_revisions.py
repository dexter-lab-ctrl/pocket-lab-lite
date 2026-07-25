from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _configure_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    database = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(database.parent))
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    database.parent.mkdir(parents=True, exist_ok=True)
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    apply_migrations()
    return database


def test_phase3a_canonical_revision_ignores_timestamps_and_ordering():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import canonical_semantic_revision

    first = {
        "updated_at": "2026-07-25T10:00:00Z",
        "apps": {
            "photo-b": {"status": "ready", "operation_id": "op-2"},
            "photo-a": {"status": "ready", "operation_id": "op-1"},
        },
        "items": [
            {"backup_id": "backup-b", "status": "verified"},
            {"backup_id": "backup-a", "status": "verified"},
        ],
    }
    second = {
        "updated_at": "2026-07-25T10:05:00Z",
        "apps": {
            "photo-a": {"operation_id": "op-1", "status": "ready"},
            "photo-b": {"operation_id": "op-2", "status": "ready"},
        },
        "items": [
            {"backup_id": "backup-a", "status": "verified"},
            {"backup_id": "backup-b", "status": "verified"},
        ],
    }

    assert canonical_semantic_revision("apps.lifecycle", first) == canonical_semantic_revision(
        "apps.lifecycle", second
    )


def test_phase3a_canonical_revision_changes_on_meaningful_transition():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import canonical_semantic_revision

    ready = {"apps": {"photoprism": {"status": "ready", "installed": True}}}
    repairing = {"apps": {"photoprism": {"status": "repairing", "installed": True}}}
    assert canonical_semantic_revision("apps.lifecycle", ready) != canonical_semantic_revision(
        "apps.lifecycle", repairing
    )


def test_phase3a_summary_and_details_revision_contracts_are_distinct():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import contract_for

    summary = contract_for("recovery", "summary")
    details = contract_for("recovery", "details")
    assert summary is not None
    assert details is not None
    assert summary.source_revision is not details.source_revision
    assert summary.max_probe_seconds < details.max_probe_seconds
    assert summary.quiet_window_seconds < details.quiet_window_seconds
    assert summary.priority < details.priority


def test_phase3a_contracts_cover_actual_app_and_recovery_projection_keys():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import contract_for

    keys = {
        ("apps", "catalog"),
        ("apps", "lifecycle"),
        ("apps", "actions:photoprism"),
        ("apps", "update:photoprism"),
        ("apps", "backup:photoprism"),
        ("recovery", "summary"),
        ("recovery", "details"),
    }
    for domain, key in keys:
        contract = contract_for(domain, key)
        assert contract is not None, (domain, key)
        assert callable(contract.source_revision)
        assert contract.deadline_seconds > 0
        assert contract.max_probe_seconds >= 5
        assert contract.quiet_window_seconds > 0


def test_phase3a_prepared_read_installs_mandatory_contract_without_running_collector(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services.lite_control_plane_store import (
        ControlPlaneProjectionStore,
        PreparedProjectionUnavailable,
    )

    captured = {}
    builds = 0

    class SchedulerStub:
        def mark_dirty(self, domain, *, job=None, priority=None, force_followup=False):
            captured[domain] = job
            return {
                "accepted": True,
                "refresh_pending": True,
                "retry_after_seconds": 0,
            }

        def status(self, _domain):
            return {"registered": True, "refresh_pending": False, "retry_after_seconds": 0}

    monkeypatch.setattr(
        "api_fastapi.services.projection_scheduler.PROJECTION_SCHEDULER", SchedulerStub()
    )
    store = ControlPlaneProjectionStore()
    monkeypatch.setattr(store, "initialize", lambda: None)

    def builder():
        nonlocal builds
        builds += 1
        return {"status": "ready"}

    for domain, key in (
        ("apps", "lifecycle"),
        ("recovery", "summary"),
        ("recovery", "details"),
    ):
        with pytest.raises(PreparedProjectionUnavailable):
            store.prepared_only_read(
                domain=domain,
                key=key,
                snapshot_builder=lambda: None,
                builder=builder,
                projector=lambda _payload: 1,
                stale_after_ms=0,
                max_stale_ms=0,
            )

    assert builds == 0
    assert captured["apps.lifecycle"].source_revision is not None
    assert captured["recovery.summary"].source_revision is not None
    assert captured["recovery.details"].source_revision is not None
    assert captured["apps.lifecycle"].work_class == "cpu"
    assert captured["recovery.summary"].deadline_seconds == 8.0
    assert captured["recovery.details"].deadline_seconds == 10.0


def test_phase3a_incomplete_reregistration_cannot_drop_rich_contract():
    ensure_runtime_path()
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    scheduler = ProjectionScheduler()
    callback = lambda: 11
    unchanged = lambda: None
    scheduler.register(
        ProjectionJob(
            "apps.lifecycle",
            lambda: {"status": "ready"},
            lambda _payload: 1,
            35,
            "cpu",
            8.0,
            optional=True,
            source_revision=callback,
            on_unchanged=unchanged,
            max_probe_seconds=300.0,
            quiet_window_seconds=1.0,
        )
    )
    scheduler.register(
        ProjectionJob(
            "apps.lifecycle",
            lambda: {"status": "ready"},
            lambda _payload: 1,
            80,
            "io",
            1.0,
        )
    )

    registered = scheduler._jobs["apps.lifecycle"]
    assert registered.source_revision is callback
    assert registered.on_unchanged is unchanged
    assert registered.priority == 35
    assert registered.work_class == "cpu"
    assert registered.deadline_seconds == 8.0
    assert registered.max_probe_seconds == 300.0
    assert registered.quiet_window_seconds == 1.0


def test_phase3a_scheduler_skips_unchanged_source_without_stale_generation(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    scheduler = ProjectionScheduler()
    builds = 0
    commits = 0
    source = {"revision": 41}

    def builder():
        nonlocal builds
        builds += 1
        return {"status": "ready"}

    def projector(_payload):
        nonlocal commits
        commits += 1
        return commits

    job = ProjectionJob(
        "recovery.summary",
        builder,
        projector,
        50,
        "io",
        2.0,
        source_revision=lambda: source["revision"],
        max_probe_seconds=300.0,
    )
    scheduler.mark_dirty("recovery.summary", job=job)
    assert _wait_for(lambda: scheduler.status("recovery.summary").get("committed_count") == 1)
    scheduler.mark_dirty("recovery.summary")
    assert _wait_for(lambda: scheduler.status("recovery.summary").get("unchanged_count") == 1)
    status = scheduler.status("recovery.summary")
    assert builds == 1
    assert commits == 1
    assert status["source_revision_enabled"] is True
    assert status["source_revision"] == 41
    assert status["stale_generation_count"] == 0
    assert status["followup_requested"] is False
    scheduler.shutdown(drain_seconds=1.0)


def test_phase3a_active_dirty_signals_coalesce_to_one_bounded_followup(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    scheduler = ProjectionScheduler()
    release = threading.Event()
    source = {"revision": 1}
    calls = 0

    def builder():
        nonlocal calls
        calls += 1
        release.wait(1.0)
        return {"status": "ready", "generation": source["revision"]}

    scheduler.mark_dirty(
        "apps.lifecycle",
        job=ProjectionJob(
            "apps.lifecycle",
            builder,
            lambda _payload: calls,
            35,
            "io",
            2.0,
            source_revision=lambda: source["revision"],
            max_probe_seconds=300.0,
        ),
    )
    assert _wait_for(lambda: scheduler.status("apps.lifecycle").get("active") is True)
    source["revision"] = 2
    for _ in range(40):
        scheduler.mark_dirty("apps.lifecycle")
    release.set()
    assert _wait_for(lambda: scheduler.status("apps.lifecycle").get("refresh_pending") is False)
    status = scheduler.status("apps.lifecycle")
    assert calls == 1
    assert status["coalesced_count"] >= 40
    assert status["unchanged_count"] >= 1
    assert status["stale_generation_count"] == 0
    assert status["followup_requested"] is False
    scheduler.shutdown(drain_seconds=1.0)


def test_phase3a_app_projection_ignores_display_timestamp_churn(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    base = {
        "status": "healthy",
        "updated_at": "2026-07-25T10:00:00Z",
        "apps": [
            {
                "app_id": "photoprism",
                "name": "PhotoPrism",
                "status": "ready",
                "installed": True,
                "actions": {
                    "repair_app": {
                        "status": "ready",
                        "enabled": True,
                        "category": "safety",
                        "risk": "low",
                        "updated_at": "2026-07-25T10:00:00Z",
                    }
                },
            }
        ],
    }
    first = store.project_apps(base)
    changed_time = {
        **base,
        "updated_at": "2026-07-25T10:05:00Z",
        "apps": [
            {
                **base["apps"][0],
                "actions": {
                    "repair_app": {
                        **base["apps"][0]["actions"]["repair_app"],
                        "updated_at": "2026-07-25T10:05:00Z",
                    }
                },
            }
        ],
    }
    second = store.project_apps(changed_time)
    assert first == 1
    assert second == first


def test_phase3a_recovery_projection_ignores_display_timestamp_churn(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    base = {
        "status": "healthy",
        "summary": "Recovery ready.",
        "updated_at": "2026-07-25T10:00:00Z",
        "last_backup": {
            "backup_id": "backup-1",
            "status": "succeeded",
            "verification_status": "verified",
            "created_at": "2026-07-25T09:00:00Z",
            "verified_at": "2026-07-25T09:05:00Z",
            "size_bytes": 1024,
            "summary": "Backup verified.",
        },
        "active_operation": {
            "operation_id": "backup-op-1",
            "status": "succeeded",
            "phase": "complete",
            "updated_at": "2026-07-25T10:00:00Z",
            "summary": "Backup completed.",
        },
        "maintenance": {"active": False, "status": "idle"},
    }
    first = store.project_recovery(base)
    changed_time = {
        **base,
        "updated_at": "2026-07-25T10:05:00Z",
        "last_backup": {**base["last_backup"], "verified_at": "2026-07-25T09:06:00Z"},
        "active_operation": {**base["active_operation"], "updated_at": "2026-07-25T10:05:00Z"},
    }
    second = store.project_recovery(changed_time)
    assert first == 1
    assert second == first


def test_phase3a_hot_reads_use_targeted_indexes(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import apply_migrations

    apply_migrations()
    with read_connection() as conn:
        app_plan = " ".join(
            str(row[3])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT operation_id FROM app_action_lifecycle "
                "WHERE app_id=? ORDER BY updated_at_epoch_ms DESC,operation_id DESC LIMIT 21",
                ("photoprism",),
            )
        )
        recovery_plan = " ".join(
            str(row[3])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT operation_id FROM recovery_operations "
                "ORDER BY updated_at_epoch_ms DESC,operation_id DESC LIMIT 21"
            )
        )
        manifest_plan = " ".join(
            str(row[3])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT backup_id FROM backup_manifest_index "
                "ORDER BY updated_at_epoch_ms DESC,backup_id DESC LIMIT 1"
            )
        )

    assert "idx_app_actions_history" in app_plan
    assert "idx_recovery_operations_updated" in recovery_plan
    assert "idx_backup_manifest_created" in manifest_plan
    assert "USE TEMP B-TREE" not in app_plan.upper()
    assert "USE TEMP B-TREE" not in recovery_plan.upper()
    assert "USE TEMP B-TREE" not in manifest_plan.upper()


def test_phase3a_probe_diagnostics_are_sanitized(monkeypatch, tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import lite_semantic_revisions

    state = tmp_path / "state"
    state.mkdir()
    (state / "lite_catalog_state.json").write_text(
        '{"apps":{"photoprism":{"status":"ready","updated_at":"2026-07-25T10:00:00Z"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        lite_semantic_revisions.deps,
        "settings",
        lambda: SimpleNamespace(state_dir=state),
    )
    monkeypatch.setattr(lite_semantic_revisions, "_app_command_rows", lambda _app_id: [])
    monkeypatch.setattr(lite_semantic_revisions, "_latest_app_security_rows", lambda _app_id: [])
    monkeypatch.setattr(lite_semantic_revisions, "_manifest_semantics", lambda: {"count": 0, "items": []})

    revision = lite_semantic_revisions.app_source_revision(scope="catalog")
    diagnostics = lite_semantic_revisions.diagnostics()
    assert revision > 0
    assert diagnostics["sanitized"] is True
    assert diagnostics["probe_count"] >= 1
    probe = diagnostics["probes"]["apps.catalog:photoprism"]
    assert probe["bounded"] is True
    assert "material" not in probe
    assert "password" not in str(diagnostics).lower()


def test_phase3a_app_action_generation_and_progress_change_revision():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import canonical_semantic_revision

    accepted = {
        "actions": {
            "photoprism": {
                "action_id": "repair_app",
                "operation_id": "repair-17",
                "status": "accepted",
                "progress": {"phase": "queued", "current": 0, "total": 3},
                "updated_at": "2026-07-25T10:00:00Z",
            }
        }
    }
    running = {
        "actions": {
            "photoprism": {
                **accepted["actions"]["photoprism"],
                "status": "running",
                "progress": {"phase": "route_check", "current": 1, "total": 3},
                "updated_at": "2026-07-25T10:00:05Z",
            }
        }
    }
    timestamp_only = {
        "actions": {
            "photoprism": {
                **accepted["actions"]["photoprism"],
                "updated_at": "2026-07-25T10:00:10Z",
            }
        }
    }

    initial_revision = canonical_semantic_revision("apps.actions:photoprism", accepted)
    assert initial_revision == canonical_semantic_revision(
        "apps.actions:photoprism", timestamp_only
    )
    assert initial_revision != canonical_semantic_revision(
        "apps.actions:photoprism", running
    )


def test_phase3a_backup_and_restore_transitions_change_recovery_revision():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import canonical_semantic_revision

    ready = {
        "recovery": {
            "status": "ready",
            "active_operation": None,
            "updated_at": "2026-07-25T10:00:00Z",
        }
    }
    backup = {
        "recovery": {
            "status": "active",
            "active_operation": {
                "operation_id": "backup-17",
                "operation_type": "backup",
                "status": "running",
                "phase": "snapshot",
            },
            "updated_at": "2026-07-25T10:00:05Z",
        }
    }
    restore = {
        "recovery": {
            "status": "active",
            "active_operation": {
                "operation_id": "restore-19",
                "operation_type": "restore",
                "status": "running",
                "phase": "checkpoint",
            },
            "updated_at": "2026-07-25T10:00:10Z",
        }
    }

    revisions = {
        canonical_semantic_revision("recovery.summary", ready),
        canonical_semantic_revision("recovery.summary", backup),
        canonical_semantic_revision("recovery.summary", restore),
    }
    assert len(revisions) == 3


def test_phase3a_details_only_input_does_not_change_summary_revision(monkeypatch, tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import lite_semantic_revisions

    state = tmp_path / "state"
    state.mkdir()
    mapping = state / "lite_app_storage_mappings.json"
    mapping.write_text(
        '{"mappings":{"photoprism":{"mapping_id":"map-1","status":"ready"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        lite_semantic_revisions.deps,
        "settings",
        lambda: SimpleNamespace(state_dir=state),
    )
    monkeypatch.setattr(lite_semantic_revisions, "_recovery_rows", lambda: {})
    monkeypatch.setattr(lite_semantic_revisions, "_app_command_rows", lambda _app_id: [])
    monkeypatch.setattr(lite_semantic_revisions, "_latest_app_security_rows", lambda _app_id: [])
    monkeypatch.setattr(lite_semantic_revisions, "_manifest_semantics", lambda: {"count": 0, "items": []})
    monkeypatch.setattr(lite_semantic_revisions, "_read_rows", lambda *_args, **_kwargs: [])

    summary_before = lite_semantic_revisions.recovery_summary_source_revision()
    details_before = lite_semantic_revisions.recovery_details_source_revision()
    mapping.write_text(
        '{"mappings":{"photoprism":{"mapping_id":"map-1","status":"unavailable"}}}',
        encoding="utf-8",
    )
    summary_after = lite_semantic_revisions.recovery_summary_source_revision()
    details_after = lite_semantic_revisions.recovery_details_source_revision()

    assert summary_after == summary_before
    assert details_after != details_before


def test_phase3a_oversized_snapshot_is_bounded_without_parsing(tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import lite_semantic_revisions

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + (b"x" * (lite_semantic_revisions._MAX_JSON_BYTES + 1)))
    result = lite_semantic_revisions._read_json_semantics(oversized)
    assert result == {"file": "oversized.json", "state": "oversized"}


def test_phase3a_database_instance_change_rejects_projection_commit(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    commits = 0

    def projector(_payload):
        nonlocal commits
        commits += 1
        return commits

    scheduler = ProjectionScheduler()
    result = scheduler._execute(
        ProjectionJob(
            "recovery.details",
            lambda: {"status": "ready"},
            projector,
            60,
            "io",
            1.0,
        ),
        generation=1,
        database_instance="stale-database-instance",
    )
    assert result["outcome"] == "database_changed"
    assert commits == 0
    scheduler.shutdown(drain_seconds=1.0)


def test_phase3a_timeout_retains_last_good_prepared_state(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.services import lite_semantic_revisions, projection_scheduler
    from api_fastapi.services.lite_control_plane_store import (
        ControlPlaneProjectionStore,
        _PreparedItem,
        _database_instance,
    )
    from api_fastapi.services.lite_semantic_revisions import ProjectionRevisionContract

    scheduler = projection_scheduler.ProjectionScheduler()
    monkeypatch.setattr(projection_scheduler, "PROJECTION_SCHEDULER", scheduler)
    monkeypatch.setattr(
        lite_semantic_revisions,
        "contract_for",
        lambda _domain, _key: ProjectionRevisionContract(
            source_revision=lambda: 17,
            max_probe_seconds=300.0,
            quiet_window_seconds=0.0,
            priority=50,
            work_class="io",
            deadline_seconds=0.01,
        ),
    )
    store = ControlPlaneProjectionStore()
    store.initialize()
    store._prepared["recovery:summary"] = _PreparedItem(
        payload={"status": "ready", "summary": "Last known good."},
        revision=9,
        prepared_at=time.monotonic() - 10.0,
        database_instance=_database_instance(),
    )

    read = store.prepared_only_read(
        domain="recovery",
        key="summary",
        snapshot_builder=lambda: None,
        builder=lambda: (time.sleep(0.15) or {"status": "failed"}),
        projector=lambda _payload: 10,
        stale_after_ms=1,
        max_stale_ms=60_000,
    )
    assert read.payload["summary"] == "Last known good."
    assert _wait_for(
        lambda: scheduler.status("recovery.summary").get("last_error_type")
        == "DeadlineExceeded"
    )
    retained = store._prepared["recovery:summary"]
    assert retained.payload["summary"] == "Last known good."
    assert retained.revision == 9
    scheduler.shutdown(drain_seconds=1.0)


def test_phase3a_recovery_progress_is_change_only_and_truthful(tmp_path, monkeypatch):
    _configure_database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    accepted = {
        "status": "active",
        "summary": "Backup accepted.",
        "active_operation": {
            "operation_id": "backup-op-21",
            "operation_type": "backup",
            "status": "accepted",
            "phase": "queued",
            "current": 0,
            "total": 3,
            "updated_at": "2026-07-25T10:00:00Z",
            "summary": "Backup accepted.",
        },
    }
    running = {
        **accepted,
        "summary": "Backup in progress.",
        "active_operation": {
            **accepted["active_operation"],
            "status": "running",
            "phase": "snapshot",
            "current": 1,
            "updated_at": "2026-07-25T10:00:10Z",
            "summary": "Backup in progress.",
        },
    }

    first = store.project_recovery(accepted)
    second = store.project_recovery(running)
    assert second == first + 1
    with read_connection() as conn:
        row = conn.execute(
            "SELECT status,metadata_json FROM recovery_operations WHERE operation_id=?",
            ("backup-op-21",),
        ).fetchone()
    assert row["status"] == "running"
    assert '"phase":"snapshot"' in row["metadata_json"]
    assert '"current":1' in row["metadata_json"]


def test_phase3a_corrupt_or_oversized_source_fails_closed(monkeypatch, tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import lite_semantic_revisions

    state = tmp_path / "state"
    state.mkdir()
    (state / "lite_catalog_state.json").write_bytes(
        b"{" + (b"x" * (lite_semantic_revisions._MAX_JSON_BYTES + 1))
    )
    monkeypatch.setattr(
        lite_semantic_revisions.deps,
        "settings",
        lambda: SimpleNamespace(state_dir=state),
    )
    monkeypatch.setattr(lite_semantic_revisions, "_app_command_rows", lambda _app_id: [])
    monkeypatch.setattr(lite_semantic_revisions, "_latest_app_security_rows", lambda _app_id: [])
    monkeypatch.setattr(lite_semantic_revisions, "_manifest_semantics", lambda: {"count": 0, "items": []})

    with pytest.raises(lite_semantic_revisions.SemanticSourceUnavailable):
        lite_semantic_revisions.app_source_revision(scope="catalog")
    probe = lite_semantic_revisions.diagnostics()["probes"]["apps.catalog:photoprism"]
    assert probe["last_error_type"] == "SemanticSourceUnavailable"
