from __future__ import annotations

import asyncio
from pathlib import Path
import time


def test_queue_reconciliation_reports_only_dirty_canonical_work() -> None:
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    scheduler = ProjectionScheduler()
    for domain in ("test.clean", "test.ready", "test.future"):
        scheduler.register(
            ProjectionJob(
                domain=domain,
                builder=lambda: {},
                projector=lambda _payload: 1,
                priority=50,
                work_class="io",
                deadline_seconds=1.0,
            )
        )

    with scheduler._condition:
        clean = scheduler._states["test.clean"]
        clean.generation = 1
        clean.dirty = False
        scheduler._enqueue_locked("test.clean", clean)

        ready = scheduler._states["test.ready"]
        ready.generation = 1
        ready.dirty = True
        scheduler._enqueue_locked("test.ready", ready)

        future = scheduler._states["test.future"]
        future.generation = 1
        future.dirty = True
        future.next_retry_at = time.monotonic() + 60.0
        scheduler._enqueue_locked("test.future", future)

    queue = scheduler.queue_health()
    assert queue["ready_executor_depth"] == 1
    assert queue["scheduled_future_depth"] == 1
    assert queue["clean_entries_removed"] == 1
    assert scheduler._states["test.clean"].queued is False


def test_worker_compact_snapshot_preserves_queue_classification() -> None:
    from workers.pocketlab_worker import _compact_scheduler_snapshot

    scheduler = {
        "status": "running",
        "registered_domains": 19,
        "projection_execution_owner": "worker",
        "is_execution_owner": True,
        "process_role": "worker",
        "loaded_build_version": "sha256:test",
        "process_start_generation": "generation-test",
        "queue": {
            "executor_depth": 0,
            "ready_executor_depth": 0,
            "scheduled_future_depth": 3,
            "active_domains": 0,
            "followup_domains": 0,
            "clean_entries_removed": 11,
            "active_entries_removed": 1,
            "stale_generation_entries_removed": 2,
            "duplicate_entries_removed": 3,
            "unregistered_entries_removed": 4,
            "stale_entries_removed": 18,
            "stale_flags_cleared": 11,
            "orphaned_dirty_requeued": 1,
        },
    }
    compact, health = _compact_scheduler_snapshot(
        scheduler,
        mailbox={"claimed": 0, "pending": 0, "unregistered": 0},
    )
    queue = compact["queue"]
    assert compact["queued_domains"] == 0
    assert queue["scheduled_future_depth"] == 3
    assert queue["clean_entries_removed"] == 11
    assert queue["duplicate_entries_removed"] == 3
    assert health["loaded_build_version"] == "sha256:test"
    assert health["queue"] == queue


def test_idle_efficiency_sampling_uses_dedicated_executor() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "idle_efficiency.py"
    ).read_text(encoding="utf-8")
    assert 'thread_name_prefix="pocketlab-idle-sampler"' in source
    assert "await loop.run_in_executor(executor, self.sample_now)" in source
    assert 'operation("background.idle_efficiency.sample")' in source
    loop_body = source.split("async def _loop", 1)[1].split("def sample_now", 1)[0]
    assert "self.sample_now()" not in loop_body


def test_stale_stack_capture_is_not_attached_to_later_lag() -> None:
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(
        loop_interval_seconds=0.1,
        loop_warning_ms=10.0,
        loop_critical_ms=20.0,
    )
    diagnostics._critical_stack_capture_enabled = True
    diagnostics._stack_correlation_seconds = 0.5
    with diagnostics._lock:
        diagnostics._critical_stack_captures.append(
            {
                "captured_at": "2026-01-01T00:00:00Z",
                "_captured_monotonic": time.monotonic() - 5.0,
                "frames": [{"module": "safe.module", "function": "safe", "line": 1}],
            }
        )
    diagnostics.record_event_loop_lag(25.0)
    event = diagnostics.snapshot()["event_loop"]["recent_lag_events"][-1]
    assert event["main_thread_stack"] is None
    exposed = diagnostics.snapshot()["event_loop"]["critical_stack_captures"][-1]
    assert "_captured_monotonic" not in exposed
