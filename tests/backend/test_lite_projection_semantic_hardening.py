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
