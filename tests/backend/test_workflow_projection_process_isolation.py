from __future__ import annotations

import json
import os
import signal
import sqlite3
import time
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()


def _configure(tmp_path: Path, monkeypatch, *, role: str = "worker") -> Path:
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "workflow.sqlite3"))
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", role)
    monkeypatch.setenv("POCKETLAB_WORKFLOW_PROCESS_OWNER", "worker")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_STAGGER_MAX_MS", "0")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_POLL_SECONDS", "0.02")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_COMPAT_SNAPSHOT_BATCHES", "1")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_WRITER_QUEUE_SIZE", "8")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_MAILBOX_CAPACITY", "16")
    from api_fastapi.db.connection import reset_sqlite_path_cache

    reset_sqlite_path_cache()
    return state


def _event(event_id: str, workflow_id: str, event_type: str = "command.queued", **data):
    return {
        "id": event_id,
        "type": event_type,
        "subject": "pocketlab.commands.test",
        "time": "2026-07-28T00:00:00Z",
        "data": {"workflow_id": workflow_id, "command_id": workflow_id, **data},
    }


def _wait_for(predicate, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(0.02)
    return last


def test_api_admission_is_nonblocking_and_never_spawns_heavy_projection(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="api")
    from api_fastapi.services import workflow_engine as module

    engine = module.EventSourcedWorkflowEngine()
    monkeypatch.setattr(module, "_apply_projection_event", lambda *_: (_ for _ in ()).throw(AssertionError("heavy projection ran in API")))
    monkeypatch.setattr(engine, "_spawn_projection_process", lambda *_: (_ for _ in ()).throw(AssertionError("API spawned child")))

    started = time.monotonic()
    result = engine.admit_event(_event("api-event-1", "wf-api"))
    elapsed_ms = (time.monotonic() - started) * 1000.0

    assert result["accepted"] is True
    assert result["status"] == "accepted"
    assert elapsed_ms < 100.0
    assert engine._projection_process is None
    assert _wait_for(lambda: list((engine.mailbox_root / "inbox").glob("event-*.json")))
    engine.stop_writer()


def test_admission_is_bounded_coalesces_only_same_event_and_rejects_shutdown(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="api")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    monkeypatch.setattr(engine, "start_writer", lambda: None)

    first = engine.admit_event(_event("same-id", "wf-a"))
    duplicate = engine.admit_event(_event("same-id", "wf-a", stage="display-only"))
    assert first["status"] == "accepted"
    assert duplicate["status"] == "coalesced"

    for index in range(7):
        assert engine.admit_event(_event(f"distinct-{index}", f"wf-{index}"))["accepted"] is True
    full = engine.admit_event(_event("distinct-overflow", "wf-overflow"))
    assert full == {"status": "queue_full", "accepted": False, "retry_after_ms": 2000}
    assert engine.writer_status()["dropped_events"] == 0
    assert engine.writer_status()["rejected_events"] == 1
    assert engine.writer_status()["recent_rejection_evidence"][-1]["reason"] == "queue_full"

    # A known-down child keeps the compact event retained and reports truthful degradation.
    engine._writer_queue.get_nowait()
    engine._writer_queue.task_done()
    engine._pending_ids.discard("same-id")
    engine._process_health_known = True
    engine._process_available = False
    unavailable = engine.admit_event(_event("known-down", "wf-known-down"))
    assert unavailable["status"] == "process_unavailable"
    assert unavailable["accepted"] is True
    assert unavailable["refresh_pending"] is True

    engine._writer_stop.set()
    shutdown = engine.admit_event(_event("after-stop", "wf-stop"))
    assert shutdown["status"] == "shutting_down"
    assert shutdown["accepted"] is False


def test_compact_ipc_redacts_secrets_urls_and_private_paths(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="api")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    token_value = "TEST_" + "ONLY_TOKEN_VALUE"
    password_value = "TEST_" + "ONLY_PASSWORD_VALUE"
    nats_value = "nats" + "://test-user:" + password_value + "@example.invalid:4222"
    private_path = "/data" + "/data/com.termux/files/home/redaction-fixture"
    result = engine.admit_event(
        _event(
            "redacted-event",
            "wf-redacted",
            error=f"token={token_value} {nats_value} {private_path}",
            reason=f"Bearer abc.def.ghi password={password_value}",
        )
    )
    assert result["accepted"] is True
    paths = _wait_for(lambda: list((engine.mailbox_root / "inbox").glob("event-*.json")))
    payload = Path(paths[0]).read_text(encoding="utf-8")
    engine.stop_writer()

    assert token_value not in payload
    assert password_value not in payload
    assert "test-user" not in payload
    assert private_path not in payload
    assert "[redacted" in payload


def test_worker_child_owns_incremental_projection_and_noop_revision(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    engine.start_writer()
    status = _wait_for(lambda: engine.writer_status() if engine.writer_status()["process_alive"] else None)
    assert status
    child_pid = int(status["process_pid"])
    assert child_pid != os.getpid()
    assert int(status["process_generation"]) >= 1
    assert status["execution_owner"] == "pocket-worker/workflow-subprocess"

    assert engine.admit_event(_event("wf-a-1", "wf-a"))["accepted"] is True
    assert engine.admit_event(_event("wf-b-1", "wf-b"))["accepted"] is True
    assert _wait_for(lambda: engine.get_projection("wf-a").get("revision") == 1)
    assert _wait_for(lambda: engine.get_projection("wf-b").get("revision") == 1)
    b_revision = engine.get_projection("wf-b")["revision"]

    # Timestamp-only/display churn is excluded from canonical operational truth.
    same = _event("wf-a-2", "wf-a")
    same["time"] = "2026-07-28T00:01:00Z"
    assert engine.admit_event(same)["accepted"] is True
    assert _wait_for(lambda: engine.writer_status().get("processed_events", 0) >= 3)
    assert engine.get_projection("wf-a")["revision"] == 1
    assert engine.get_projection("wf-b")["revision"] == b_revision
    assert engine.writer_status()["canonical_noop_count"] >= 1

    assert engine.admit_event(_event("wf-a-3", "wf-a", "command.succeeded"))["accepted"] is True
    assert _wait_for(lambda: engine.get_projection("wf-a").get("status") == "succeeded")
    assert engine.get_projection("wf-a")["revision"] == 2
    assert engine.get_projection("wf-b")["revision"] == b_revision
    engine.stop_writer()


def test_late_nonterminal_event_cannot_regress_terminal_workflow_truth(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    assert engine.admit_event(
        _event("terminal-first", "wf-ordering", "command.succeeded", sequence=2)
    )["accepted"] is True
    assert _wait_for(lambda: engine.get_projection("wf-ordering").get("status") == "succeeded")
    terminal_revision = engine.get_projection("wf-ordering")["revision"]

    late = _event("late-queued", "wf-ordering", "command.queued", sequence=1)
    late["time"] = "2026-07-27T23:59:59Z"
    assert engine.admit_event(late)["accepted"] is True
    assert _wait_for(lambda: len(engine.iter_events("wf-ordering", limit=10)) == 2)
    current = engine.get_projection("wf-ordering")
    assert current["status"] == "succeeded"
    assert current["terminal"] is True
    assert current["revision"] == terminal_revision
    assert engine.writer_status()["canonical_noop_count"] >= 1
    engine.stop_writer()


def test_batch_budget_yields_and_retains_pending_work(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_BATCH_MAX_EVENTS", "1")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_BATCH_CPU_MS", "200")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_BATCH_WALL_MS", "500")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    for index in range(4):
        assert engine.admit_event(_event(f"budget-{index}", f"wf-budget-{index}"))["accepted"] is True
    assert _wait_for(lambda: engine.writer_status().get("processed_events", 0) == 4)
    status = engine.writer_status()
    assert status["last_batch_size"] <= 1
    assert status["batch_count"] >= 4
    assert status["dropped_events"] == 0
    engine.stop_writer()


def test_child_crash_restarts_generation_and_preserves_queued_work(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    engine.start_writer()
    initial = _wait_for(lambda: engine.writer_status() if engine.writer_status()["process_alive"] else None)
    assert initial
    initial_pid = int(initial["process_pid"])
    initial_generation = int(initial["process_generation"])

    os.kill(initial_pid, signal.SIGKILL)
    assert engine.admit_event(_event("after-crash", "wf-after-crash"))["accepted"] is True
    restarted = _wait_for(
        lambda: engine.writer_status()
        if engine.writer_status()["process_alive"]
        and int(engine.writer_status()["process_generation"]) > initial_generation
        else None,
        timeout=6.0,
    )
    assert restarted
    assert int(restarted["process_pid"]) != initial_pid
    assert restarted["process_restart_count"] >= 1
    assert _wait_for(lambda: engine.get_projection("wf-after-crash").get("status") == "queued")
    assert engine.writer_status()["dropped_events"] == 0
    engine.stop_writer()


def test_process_generation_survives_worker_restart_and_accepts_new_events(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    first = EventSourcedWorkflowEngine()
    assert first.admit_event(_event("before-worker-restart", "wf-worker-restart"))["accepted"] is True
    initial = _wait_for(lambda: first.writer_status() if first.writer_status()["process_alive"] else None)
    assert initial
    first_generation = int(initial["process_generation"])
    assert _wait_for(lambda: first.get_projection("wf-worker-restart").get("revision") == 1)
    first.stop_writer(drain_timeout_seconds=5)
    first.process_generation_file.unlink(missing_ok=True)

    replacement = EventSourcedWorkflowEngine()
    replacement.start_writer()
    restarted = _wait_for(
        lambda: replacement.writer_status()
        if replacement.writer_status()["process_alive"]
        and int(replacement.writer_status()["process_generation"]) > first_generation
        else None,
        timeout=6.0,
    )
    assert restarted
    assert replacement.admit_event(
        _event("after-worker-restart", "wf-worker-restart", "command.succeeded")
    )["accepted"] is True
    assert _wait_for(lambda: replacement.get_projection("wf-worker-restart").get("status") == "succeeded")
    assert replacement.get_projection("wf-worker-restart")["revision"] == 2
    replacement.stop_writer(drain_timeout_seconds=5)


def test_bounded_recycle_changes_generation_without_event_loss(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_BATCH_MAX_EVENTS", "1")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_RECYCLE_BATCH_COUNT", "10")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_WRITER_QUEUE_SIZE", "32")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    for index in range(12):
        assert engine.admit_event(_event(f"recycle-{index}", f"wf-recycle-{index}"))["accepted"] is True
    recycled = _wait_for(
        lambda: engine.writer_status()
        if int(engine.writer_status().get("process_generation") or 0) >= 2
        and int(engine.writer_status().get("recycle_count") or 0) >= 1
        else None,
        timeout=8.0,
    )
    assert recycled
    assert _wait_for(lambda: engine.writer_status().get("processed_events", 0) >= 2, timeout=5.0)
    # Event index idempotency plus the durable mailbox prevents loss or double application.
    assert _wait_for(lambda: len(engine.list_workflows(limit=20)) == 12, timeout=8.0)
    assert engine.writer_status()["dropped_events"] == 0
    engine.stop_writer()


def test_repeated_child_failure_opens_bounded_circuit_and_exports_compact_diagnostics(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_RESTART_MAX", "1")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    class DeadProcess:
        pid = 424242

        @staticmethod
        def poll():
            return 1

    engine = EventSourcedWorkflowEngine()
    monkeypatch.setattr(engine, "_spawn_projection_process", lambda _generation: DeadProcess())
    engine.start_writer()
    status = _wait_for(
        lambda: engine.writer_status()
        if engine.writer_status().get("last_error_type") == "WorkflowProjectionCircuitOpen"
        else None,
        timeout=3.0,
    )
    assert status
    required = {
        "process_alive", "process_pid", "process_generation", "execution_owner",
        "started_at", "restart_count", "recycle_count", "last_restart_reason",
        "queue_depth", "queue_capacity", "oldest_queue_age_ms", "accepted_events",
        "coalesced_events", "rejected_events", "dropped_events", "processed_events",
        "batch_count", "last_batch_size", "last_batch_started_at",
        "last_batch_completed_at", "last_batch_wall_ms", "last_batch_cpu_ms",
        "serialization_ms", "serialized_bytes", "allocation_bytes",
        "canonical_noop_count", "canonical_change_count",
        "memory_pressure_deferred_count", "cpu_budget_deferred_count",
        "last_error_type", "last_error_at", "last_success_at",
        "last_known_good_revision", "dispatcher_alive", "dispatcher_restart_count",
        "dispatch_count", "last_dispatch_at", "last_dispatch_error_type",
    }
    assert required <= set(status)
    assert status["process_alive"] is False
    assert status["degraded"] is True
    assert status["last_restart_reason"] == "restart_limit"
    encoded = json.dumps(status, sort_keys=True)
    assert "POCKETLAB_" not in encoded
    assert "/data/data/" not in encoded
    engine.stop_writer()


def test_explicit_reconciliation_rebuilds_missing_prepared_component(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch, role="worker")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    assert engine.admit_event(_event("reconcile-source", "wf-reconcile", "command.succeeded"))["accepted"] is True
    assert _wait_for(lambda: engine.get_projection("wf-reconcile").get("status") == "succeeded")
    with sqlite3.connect(str(state / "workflow.sqlite3")) as conn:
        conn.execute("DELETE FROM workflow_current_state WHERE workflow_id='wf-reconcile'")
        conn.commit()
    assert engine.get_projection("wf-reconcile").get("data_source") != "prepared_sqlite"

    scheduled = engine.rebuild_all()
    assert scheduled["accepted"] is True
    rebuilt = _wait_for(
        lambda: engine.get_projection("wf-reconcile")
        if engine.get_projection("wf-reconcile").get("data_source") == "prepared_sqlite"
        else None,
        timeout=5.0,
    )
    assert rebuilt
    assert rebuilt["status"] == "succeeded"
    engine.stop_writer()


def test_controlled_shutdown_leaves_no_orphan_and_prepared_state_survives(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    assert engine.admit_event(_event("shutdown-1", "wf-shutdown"))["accepted"] is True
    status = _wait_for(lambda: engine.writer_status() if engine.writer_status()["process_alive"] else None)
    assert status
    pid = int(status["process_pid"])
    assert _wait_for(lambda: engine.get_projection("wf-shutdown").get("status") == "queued")
    revision = engine.get_projection("wf-shutdown")["revision"]

    engine.stop_writer(drain_timeout_seconds=5)
    assert _wait_for(lambda: _pid_gone(pid), timeout=3.0)
    prepared = engine.get_projection("wf-shutdown")
    assert prepared["revision"] == revision
    assert prepared["data_source"] == "prepared_sqlite"


def _pid_gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def test_stale_process_generation_fails_closed_and_preserves_last_known_good(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch, role="workflow_projection")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_PROCESS_GENERATION", "998")
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine
    from api_fastapi.services.workflow_projection_process import WorkflowProjectionProcess

    apply_migrations()
    engine = EventSourcedWorkflowEngine()
    assert engine.save_projection({"workflow_id": "wf-stale", "status": "queued"}) is True
    with sqlite3.connect(str(state / "workflow.sqlite3")) as conn:
        conn.execute(
            "UPDATE workflow_current_state SET revision=7, process_generation=999 WHERE workflow_id='wf-stale'"
        )
        conn.commit()

    runtime = WorkflowProjectionProcess()
    event_path = runtime.inbox / "event-stale-generation.json"
    event_path.write_text(
        json.dumps(_event("stale-generation", "wf-stale", "command.succeeded")),
        encoding="utf-8",
    )
    outcome = runtime._process_event(
        event_path,
        remaining_serialized_bytes=runtime.serialized_bytes_max,
        workflow_updates={},
    )
    assert outcome == "failed"
    assert list(runtime.failed.glob("event-stale-generation.error.json"))
    current = engine.get_projection("wf-stale")
    assert current["status"] == "queued"
    assert current["revision"] == 7
    assert current["process_generation"] == 999

def test_serialization_budget_defers_at_safe_boundary_without_partial_commit(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch, role="workflow_projection")
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.services.workflow_projection_process import WorkflowProjectionProcess

    apply_migrations()
    runtime = WorkflowProjectionProcess()
    event_path = runtime.inbox / "event-byte-budget.json"
    event_path.write_text(json.dumps(_event("byte-budget", "wf-byte-budget")), encoding="utf-8")
    outcome = runtime._process_event(
        event_path,
        remaining_serialized_bytes=0,
        workflow_updates={},
    )
    assert outcome == "deferred"
    assert event_path.exists()
    with sqlite3.connect(str(state / "workflow.sqlite3")) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM workflow_event_index WHERE event_id='byte-budget'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM workflow_current_state WHERE workflow_id='wf-byte-budget'"
        ).fetchone()[0] == 0


def test_child_environment_is_allowlisted_and_memory_probe_is_process_local(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, role="worker")
    monkeypatch.setenv("POCKETLAB_WORKFLOW_TOKEN", "must-not-leak")
    monkeypatch.setenv(
        "POCKETLAB_NATS_URL",
        "nats" + "://test-user:test-pass@example.invalid:4222",
    )
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine
    import api_fastapi.services.workflow_engine as engine_module
    import api_fastapi.services.workflow_projection_process as process_module

    engine = EventSourcedWorkflowEngine()
    child_env = engine._sanitize_child_environment(1)
    assert "POCKETLAB_WORKFLOW_TOKEN" not in child_env
    assert "POCKETLAB_NATS_URL" not in child_env
    assert "must-not-leak" not in json.dumps(child_env)
    assert "/proc/meminfo" not in Path(engine_module.__file__).read_text(encoding="utf-8")
    assert "/proc/meminfo" in Path(process_module.__file__).read_text(encoding="utf-8")


def test_workflow_sqlite_reads_are_indexed_and_history_is_bounded(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch, role="worker")
    from api_fastapi.db.migrations import apply_migrations

    apply_migrations()
    with sqlite3.connect(str(state / "workflow.sqlite3")) as conn:
        plan = " ".join(
            str(column)
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT event_json FROM workflow_event_index WHERE workflow_id=? ORDER BY observed_at_epoch_ms DESC, event_id DESC LIMIT 20",
                ("wf-index",),
            )
            for column in row
        )
    assert "idx_workflow_event_workflow_time" in plan
