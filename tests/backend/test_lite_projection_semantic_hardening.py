from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    state_dir = tmp_path / "state"
    database = state_dir / "pocketlab-lite.sqlite3"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state_dir))
    monkeypatch.setenv("POCKETLAB_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "test")
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    apply_migrations()
    return database


def test_canonical_projection_material_preserves_intentional_resource_semantics():
    ensure_runtime_path()
    from api_fastapi.services.lite_phase3b_projections import (
        canonical_projection_material,
        canonical_semantic_hash,
    )

    before = canonical_projection_material(
        {
            "cpu_percent": 12,
            "memory_status": "normal",
            "sampled_at": "2026-07-27T00:00:00Z",
        },
        volatile_fields=("sampled_at",),
    )
    after = canonical_projection_material(
        {
            "cpu_percent": 85,
            "memory_status": "elevated",
            "sampled_at": "2026-07-27T00:01:00Z",
        },
        volatile_fields=("sampled_at",),
    )

    assert before == {"cpu_percent": 12, "memory_status": "normal"}
    assert after == {"cpu_percent": 85, "memory_status": "elevated"}
    assert canonical_semantic_hash(before) != canonical_semantic_hash(after)


def test_semantic_diff_is_bounded_and_value_free():
    ensure_runtime_path()
    from api_fastapi.services.lite_phase3b_projections import semantic_diff

    changed = semantic_diff(
        {"status": "healthy", "nested": {"count": 1}, "items": ["alpha"]},
        {"status": "attention", "nested": {"count": 2}, "items": ["secret-value"]},
        max_paths=2,
    )

    assert 1 <= len(changed) <= 2
    assert all(path.startswith("$") or path == "__truncated__" for path in changed)
    encoded = json.dumps(changed).lower()
    assert "healthy" not in encoded
    assert "attention" not in encoded
    assert "secret-value" not in encoded


def test_app_projection_target_revision_ignores_embedded_refresh_timestamps(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_semantic_revisions as revisions

    row = {
        "app_id": "photoprism",
        "status": "ready",
        "installed": 1,
        "health_state": "protected",
        "source_revision": 10,
        "projection_version": 2,
        "backup_targets_json": json.dumps(
            {"status": "healthy", "updated_at": "2026-09-09T16:08:30Z"}
        ),
        "catalog_state_json": json.dumps(
            {"status": "ready", "route_ready": True, "updated_at": "2026-09-09T16:08:30Z"}
        ),
    }

    monkeypatch.setattr(revisions, "_read_rows", lambda *args, **kwargs: [dict(row)])
    before = revisions.canonical_semantic_revision(
        "recovery.target.apps",
        {"current_state": revisions._app_current_rows("photoprism")},
    )

    row["backup_targets_json"] = json.dumps(
        {"status": "healthy", "updated_at": "2026-09-09T16:08:35Z"}
    )
    row["source_revision"] = 11
    row["catalog_state_json"] = json.dumps(
        {"status": "ready", "route_ready": True, "updated_at": "2026-09-09T16:08:35Z"}
    )
    after_refresh = revisions.canonical_semantic_revision(
        "recovery.target.apps",
        {"current_state": revisions._app_current_rows("photoprism")},
    )

    assert after_refresh == before

    row["backup_targets_json"] = json.dumps(
        {"status": "attention", "updated_at": "2026-09-09T16:08:35Z"}
    )
    after_material_change = revisions.canonical_semantic_revision(
        "recovery.target.apps",
        {"current_state": revisions._app_current_rows("photoprism")},
    )
    assert after_material_change != before


def test_recovery_target_app_material_ignores_operational_action_reconciliation(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_semantic_revisions as revisions

    material = {
        "files": [],
        "compatibility_files": [],
        "current_state": [
            {
                "app_id": "photoprism",
                "status": "ready",
                "operation_state_json": {"actions": {"open": {"status": "ready", "run_count": 1}}},
            }
        ],
        "commands": [{"command_id": "app-command-1", "status": "running"}],
        "security": [],
    }
    monkeypatch.setattr(revisions, "app_semantic_material", lambda **kwargs: material)

    before = revisions.canonical_semantic_revision(
        "recovery.target.apps", revisions.recovery_target_app_material()
    )
    material["current_state"][0]["operation_state_json"] = {
        "actions": {"open": {"status": "succeeded", "run_count": 2}}
    }
    material["commands"] = [{"command_id": "app-command-2", "status": "succeeded"}]
    after_operational_reconciliation = revisions.canonical_semantic_revision(
        "recovery.target.apps", revisions.recovery_target_app_material()
    )

    assert after_operational_reconciliation == before

    material["current_state"][0]["status"] = "attention"
    after_lifecycle_change = revisions.canonical_semantic_revision(
        "recovery.target.apps", revisions.recovery_target_app_material()
    )
    assert after_lifecycle_change != before


def test_canonical_commit_skips_identical_semantics_and_explains_change(
    tmp_path, monkeypatch
):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3b_projections as prepared

    payload = {
        "status": "healthy",
        "summary": "No actions need attention.",
        "active_operations": 0,
        "attention_required": 0,
        "workflows": {"devices": {"status": "idle", "active": 0}},
        "collector_duration_ms": 1.234,
        "generation": 10,
        "sanitized": True,
    }
    first = prepared.commit_projection_if_changed(
        domain="system.activity_current",
        payload=payload,
        semantic_selector=lambda value: {
            key: value.get(key)
            for key in (
                "status",
                "summary",
                "active_operations",
                "attention_required",
                "workflows",
            )
        },
        trigger_reason="test_initial",
    )
    duplicate = prepared.commit_projection_if_changed(
        domain="system.activity_current",
        payload={**payload, "collector_duration_ms": 99.0, "generation": 11},
        semantic_selector=lambda value: {
            key: value.get(key)
            for key in (
                "status",
                "summary",
                "active_operations",
                "attention_required",
                "workflows",
            )
        },
        trigger_reason="test_duplicate",
    )
    changed = prepared.commit_projection_if_changed(
        domain="system.activity_current",
        payload={
            **payload,
            "status": "active",
            "summary": "Something is running.",
            "active_operations": 1,
            "workflows": {"devices": {"status": "active", "active": 1}},
        },
        semantic_selector=lambda value: {
            key: value.get(key)
            for key in (
                "status",
                "summary",
                "active_operations",
                "attention_required",
                "workflows",
            )
        },
        trigger_reason="device_transition",
    )

    assert first.changed is True
    assert duplicate.changed is False
    assert duplicate.revision == first.revision
    assert changed.changed is True
    assert changed.revision == first.revision + 1
    assert "$.active_operations" in changed.changed_paths

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT previous_semantic_hash,new_semantic_hash,changed_paths_json,reason "
            "FROM phase3b_revision_events WHERE domain=? ORDER BY event_id",
            ("system.activity_current",),
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert rows[-1]["previous_semantic_hash"] != rows[-1]["new_semantic_hash"]
    assert "$.active_operations" in json.loads(rows[-1]["changed_paths_json"])
    assert rows[-1]["reason"] == "device_transition"


def test_activity_history_changes_do_not_advance_current_projection(
    tmp_path, monkeypatch
):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections as phase3c

    current = {
        "status": "healthy",
        "summary": "No actions need attention.",
        "active_operations": 0,
        "attention_required": 0,
        "workflows": {"devices": {"status": "idle", "active": 0, "attention": 0}},
        "policy_mode": "lite_personal",
        "item_count": 1,
        "sanitized": True,
    }
    history = {
        "status": "available",
        "summary": "Recent activity is available.",
        "recent_completed": 1,
        "latest_change": {"domain": "devices", "status": "succeeded", "summary": "restart"},
        "workflows": {"devices": {"recent_completed": 1, "latest_status": "succeeded"}},
        "audit_reference_count": 1,
        "item_count": 1,
        "sanitized": True,
    }
    phase3c.project("system.activity_current", current)
    phase3c.project("system.activity_history", history)
    before = phase3c.snapshot("system.activity_current")
    phase3c.project(
        "system.activity_history",
        {
            **history,
            "recent_completed": 2,
            "latest_change": {"domain": "apps", "status": "succeeded", "summary": "check"},
        },
    )
    after = phase3c.snapshot("system.activity_current")
    composed = phase3c.snapshot("system.activity_summary")

    assert before["projection_revision"] == after["projection_revision"]
    assert composed["status"] == "healthy"
    assert composed["active_operations"] == 0
    assert composed["recent_completed"] == 2
    assert composed["current_projection_revision"] == after["projection_revision"]
    assert composed["history_projection_revision"] >= 2

    conn = sqlite3.connect(database)
    try:
        current_events = conn.execute(
            "SELECT COUNT(*) FROM phase3b_revision_events WHERE domain='system.activity_current'"
        ).fetchone()[0]
        history_events = conn.execute(
            "SELECT COUNT(*) FROM phase3b_revision_events WHERE domain='system.activity_history'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert current_events == 1
    assert history_events == 2


def test_api_dirty_admission_is_consumed_by_worker_owner(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import (
        ProjectionJob,
        ProjectionScheduler,
    )

    built = threading.Event()
    projected = threading.Event()

    def builder():
        built.set()
        return {"status": "healthy", "item_count": 0, "sanitized": True}

    def projector(_payload):
        projected.set()
        return 1

    scheduler = ProjectionScheduler()
    job = ProjectionJob(
        domain="system.activity_current",
        builder=builder,
        projector=projector,
        priority=10,
        work_class="critical",
        deadline_seconds=2.0,
        source_revision=lambda: 1,
        max_probe_seconds=5.0,
    )
    monkeypatch.setenv("POCKETLAB_PROJECTION_EXECUTION_OWNER", "worker")
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "api")
    admitted = scheduler.mark_dirty(
        "system.activity_current", job=job, reason="api_read_stale"
    )
    second = scheduler.mark_dirty(
        "system.activity_current", job=job, reason="device_transition"
    )
    assert admitted["accepted"] is True
    assert admitted["local_execution"] is False
    assert second["generation"] == admitted["generation"] + 1
    assert built.is_set() is False

    # A worker claiming an earlier observed generation must not swallow a newer
    # API event that arrived before the claim transaction completed.
    scheduler._claim_dirty_signal(
        "system.activity_current", int(admitted["generation"])
    )

    conn = sqlite3.connect(database)
    try:
        pending = conn.execute(
            "SELECT signal_generation,claimed_generation,requested_by "
            "FROM projection_dirty_signals WHERE domain='system.activity_current'"
        ).fetchone()
    finally:
        conn.close()
    assert pending is not None
    assert pending[0] == int(second["generation"])
    assert pending[1] == int(admitted["generation"])
    assert pending[0] > pending[1]
    assert pending[2] == "api"

    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    scheduler.start()
    consumed = scheduler.consume_dirty_signals()
    assert consumed["claimed"] == 1
    assert projected.wait(3.0)

    deadline = time.time() + 3.0
    while time.time() < deadline:
        status = scheduler.status("system.activity_current")
        if status.get("execution_count", 0) >= 1 and not status.get("refresh_pending"):
            break
        time.sleep(0.02)
    scheduler.shutdown()

    conn = sqlite3.connect(database)
    try:
        persisted = conn.execute(
            "SELECT source_revision,last_duration_ms,execution_count,"
            "committed_count,unchanged_count,trigger_reason,"
            "last_trigger_reason,execution_owner,executor_build_version,"
            "executor_process_generation "
            "FROM projection_refresh_state "
            "WHERE domain='system.activity_current'"
        ).fetchone()
    finally:
        conn.close()
    assert persisted is not None
    assert persisted[0] == 1
    assert persisted[1] >= 0
    assert persisted[2] >= 1
    assert persisted[3] >= 1
    assert persisted[4] == 0
    assert persisted[5] == "coalesced_multiple"
    assert persisted[6] == "coalesced_multiple"
    assert persisted[7] == "worker"
    assert str(persisted[8]).startswith("sha256:")
    assert len(str(persisted[9])) == 16

    diagnostics = scheduler.diagnostics()
    assert diagnostics["process_role"] == "worker"
    assert str(diagnostics["loaded_build_version"]).startswith("sha256:")
    assert len(str(diagnostics["process_start_generation"])) == 16


def test_worker_rehydrates_durable_dirty_projection_after_claimed_signal(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    built = threading.Event()
    projected = threading.Event()

    def builder():
        built.set()
        return {"status": "healthy", "item_count": 0, "sanitized": True}

    def projector(_payload):
        projected.set()
        return 1

    conn = sqlite3.connect(database)
    try:
        conn.execute(
            """
            INSERT INTO projection_refresh_state(
                domain,generation,committed_generation,dirty,active,priority,work_class,
                updated_at
            ) VALUES ('recovery.details',7,6,1,1,10,'critical','2026-09-08T00:00:00Z')
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    scheduler = ProjectionScheduler()
    scheduler.register(
        ProjectionJob(
            domain="recovery.details",
            builder=builder,
            projector=projector,
            priority=10,
            work_class="critical",
            deadline_seconds=2.0,
            source_revision=lambda: 1,
            max_probe_seconds=5.0,
        )
    )
    result = scheduler.reconcile_durable_state()
    assert result["requeued"] == 1
    assert result["orphaned_active"] == 1
    with sqlite3.connect(database) as conn:
        active = conn.execute(
            "SELECT active FROM projection_refresh_state WHERE domain='recovery.details'"
        ).fetchone()[0]
    assert active == 0
    scheduler.start()
    assert built.wait(3.0)
    assert projected.wait(3.0)

    deadline = time.time() + 3.0
    while time.time() < deadline:
        state = scheduler.status("recovery.details")
        if state.get("execution_count", 0) >= 1 and not state.get("refresh_pending"):
            break
        time.sleep(0.02)
    scheduler.shutdown()
    assert state.get("execution_count", 0) >= 1
    assert state.get("committed_count", 0) >= 1


def test_worker_restart_does_not_preserve_primary_projection_backoff(
    tmp_path, monkeypatch
):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    retry_epoch_ms = int(time.time() * 1000) + 60_000
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO projection_refresh_state(
                domain,generation,committed_generation,dirty,active,priority,work_class,
                failure_count,next_retry_epoch_ms,updated_at
            ) VALUES ('apps.catalog',4,3,1,0,20,'critical',4,?,
                      '2026-09-08T00:00:00Z')
            """,
            (retry_epoch_ms,),
        )

    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    scheduler = ProjectionScheduler()
    scheduler.register(
        ProjectionJob(
            domain="apps.catalog",
            builder=lambda: {"status": "healthy", "sanitized": True},
            projector=lambda _payload: 1,
            priority=20,
            work_class="critical",
            deadline_seconds=2.0,
            source_revision=lambda: 1,
            max_probe_seconds=5.0,
        )
    )

    result = scheduler.reconcile_durable_state()
    assert result["requeued"] == 1
    status = scheduler.status("apps.catalog")
    assert status["retry_after_seconds"] == 0
    assert status["refresh_pending"] is True
    scheduler.shutdown(drain_seconds=0.1)


def test_worker_rehydrates_clean_projection_completion_for_idle_freshness(
    tmp_path, monkeypatch
):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    completed_at = "2026-09-09T18:00:00Z"
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO projection_refresh_state(
                domain,generation,committed_generation,dirty,active,priority,work_class,
                last_started_at,last_completed_at,last_error_type,source_revision,updated_at
            ) VALUES ('recovery.details',7,7,0,0,1,'recovery',?,?, '',23,?)
            """,
            (completed_at, completed_at, completed_at),
        )

    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    scheduler = ProjectionScheduler()
    scheduler.register(
        ProjectionJob(
            domain="recovery.details",
            builder=lambda: {"status": "healthy", "sanitized": True},
            projector=lambda _payload: 7,
            priority=1,
            work_class="recovery",
            deadline_seconds=2.0,
            source_revision=lambda: 23,
            max_probe_seconds=8.0,
        )
    )

    result = scheduler.reconcile_durable_state()
    state = scheduler._states["recovery.details"]
    assert result["requeued"] == 0
    assert state.last_completed_iso == completed_at
    assert state.last_started_iso == completed_at
    assert state.committed_generation == 7
    assert state.generation == 7
    assert state.dirty is False
    assert state.queued is False
    scheduler.shutdown(drain_seconds=0.1)


def test_worker_replaces_startup_queue_when_rehydrating_newer_durable_generation(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    built = threading.Event()
    projected = threading.Event()

    def builder():
        built.set()
        return {"status": "healthy", "sanitized": True}

    def projector(_payload):
        projected.set()
        return 1

    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO projection_refresh_state(
                domain,generation,committed_generation,dirty,active,priority,work_class,
                updated_at
            ) VALUES ('recovery.summary',7,6,1,0,10,'critical','2026-09-08T00:00:00Z')
            """
        )

    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    scheduler = ProjectionScheduler()
    job = ProjectionJob(
        domain="recovery.summary",
        builder=builder,
        projector=projector,
        priority=10,
        work_class="critical",
        deadline_seconds=2.0,
        source_revision=lambda: 1,
        max_probe_seconds=5.0,
    )
    scheduler.register(job)
    # Simulate startup warm-up inserting an older local heap generation before
    # durable worker state is reconciled. Keep the dispatcher blocked behind the
    # scheduler condition until reconciliation replaces that heap entry.
    with scheduler._condition:
        state = scheduler._states["recovery.summary"]
        state.generation = 1
        state.dirty = True
        state.trigger_reason = "startup_warmup"
        scheduler._enqueue_locked("recovery.summary", state)
    result = scheduler.reconcile_durable_state()
    assert result["requeued"] == 1
    scheduler.start()
    assert built.wait(3.0)
    assert projected.wait(3.0)

    deadline = time.time() + 3.0
    while time.time() < deadline:
        state = scheduler.status("recovery.summary")
        if state.get("execution_count", 0) >= 1 and not state.get("refresh_pending"):
            break
        time.sleep(0.02)
    scheduler.shutdown()
    assert state.get("execution_count", 0) >= 1
    assert state.get("committed_count", 0) >= 1


def test_database_switch_fence_blocks_new_projection_dispatch_until_released(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    built = threading.Event()
    scheduler = ProjectionScheduler()
    scheduler.register(
        ProjectionJob(
            domain="recovery.summary",
            builder=lambda: (built.set() or {"status": "healthy", "sanitized": True}),
            projector=lambda _payload: 1,
            priority=10,
            work_class="critical",
            deadline_seconds=2.0,
            source_revision=lambda: 1,
            max_probe_seconds=5.0,
        )
    )
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    scheduler.start()
    try:
        assert scheduler.begin_database_switch(timeout_seconds=1.0) is True
        scheduler.mark_dirty("recovery.summary", reason="restore_fence_test")
        assert built.wait(0.2) is False
        scheduler.end_database_switch()
        assert built.wait(3.0) is True
    finally:
        scheduler.end_database_switch()
        scheduler.shutdown(drain_seconds=1.0)


def test_database_switch_fence_does_not_claim_durable_dirty_signals(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionScheduler

    scheduler = ProjectionScheduler()
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    monkeypatch.setattr(
        scheduler,
        "_ensure_signal_schema",
        lambda: pytest.fail("database-switch fence must avoid SQLite signal writes"),
    )
    try:
        assert scheduler.begin_database_switch(timeout_seconds=1.0) is True
        result = scheduler.consume_dirty_signals()
        assert result["claimed"] == 0
        assert result["database_switch_fenced"] is True
    finally:
        scheduler.end_database_switch()
        scheduler.shutdown(drain_seconds=1.0)


def test_known_legacy_mailbox_signal_is_retired_without_hiding_unknown_domains(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionScheduler

    scheduler = ProjectionScheduler()
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    scheduler.start()
    try:
        conn = sqlite3.connect(database)
        try:
            conn.execute(
                "INSERT INTO projection_dirty_signals(domain,signal_generation,claimed_generation,"
                "trigger_reason,requested_by,updated_at,updated_at_epoch_ms) "
                "VALUES ('apps.backup:photoprism', 1, 0, 'legacy', 'test', ?, 1)",
                ("2026-09-09T00:00:00Z",),
            )
            conn.commit()
        finally:
            conn.close()

        result = scheduler.consume_dirty_signals()
        assert result["retired"] == 1
        assert result["retired_domains"] == ["apps.backup:photoprism"]
        assert result["unregistered"] == 0
        assert result["total_pending"] == 0

        with sqlite3.connect(database) as conn:
            claimed = conn.execute(
                "SELECT signal_generation,claimed_generation "
                "FROM projection_dirty_signals WHERE domain='apps.backup:photoprism'"
            ).fetchone()
        assert claimed == (1, 1)
        assert scheduler.consume_dirty_signals()["unregistered"] == 0
    finally:
        scheduler.shutdown(drain_seconds=1.0)


def test_database_switch_state_write_fence_blocks_concurrent_json_writers(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi import deps

    blocked = threading.Event()
    completed = threading.Event()

    def contender():
        try:
            with deps.core.state_write_fence(timeout_seconds=0.1):
                pass
        except TimeoutError:
            blocked.set()
        with deps.core.state_write_fence(timeout_seconds=1.0):
            completed.set()

    with deps.core.state_write_fence(timeout_seconds=1.0):
        thread = threading.Thread(target=contender)
        thread.start()
        thread.join(timeout=1.0)
        assert blocked.is_set()
        assert completed.is_set() is False
    thread.join(timeout=1.0)
    assert completed.is_set()


def test_recovery_projection_contract_has_dedicated_lane_and_priority_ordering():
    from api_fastapi.services.lite_semantic_revisions import contract_for

    summary = contract_for("recovery", "summary")
    details = contract_for("recovery", "details")
    assert summary is not None and details is not None
    assert summary.work_class == "recovery"
    assert details.work_class == "recovery"
    assert summary.priority < details.priority
    assert details.priority <= 20


def test_projection_execution_ownership_is_explicit_in_api_and_worker_sources():
    api_source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/main.py"
    ).read_text(encoding="utf-8")
    worker_source = Path(
        "pocket-lab-final-structure/runtime/workers/pocketlab_worker.py"
    ).read_text(encoding="utf-8")

    assert 'POCKETLAB_PROCESS_ROLE", "api"' in api_source
    assert 'POCKETLAB_PROCESS_ROLE", "worker"' in worker_source
    assert "projection_signal_loop" in worker_source
    assert worker_source.index("projection_signal_loop(stop_event)") < worker_source.index(
        "await connect_worker_bus(stop_event)"
    )
    assert "PROJECTION_SCHEDULER.consume_dirty_signals" in worker_source


def test_phase3b_gate_accepts_canonical_unchanged_as_successful_outcome():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    script = (
        root
        / "scripts"
        / "dev"
        / "check-lite-phase3b-projections.sh"
    ).read_text(encoding="utf-8")

    assert "no_successful_outcome" in script
    assert 'get("committed_count")' in script
    assert 'get("unchanged_count")' in script
    assert '"not_committed":not_committed' not in script
