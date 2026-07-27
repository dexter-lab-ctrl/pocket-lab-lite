from __future__ import annotations

import heapq
import json
import time

from pocket_lab_test_utils import ensure_runtime_path


def test_queue_reconciliation_counts_only_dirty_due_canonical_entries():
    ensure_runtime_path()
    from api_fastapi.services import projection_scheduler as module

    scheduler = module.ProjectionScheduler()
    builder = lambda: {}
    projector = lambda payload: payload
    for domain in ("clean.domain", "future.domain", "ready.domain"):
        scheduler._jobs[domain] = module.ProjectionJob(
            domain=domain,
            builder=builder,
            projector=projector,
            priority=50,
            work_class="io",
            deadline_seconds=1.0,
        )

    clean = module._DomainState(generation=1, dirty=False, queued=True)
    future = module._DomainState(
        generation=1,
        dirty=True,
        queued=True,
        next_retry_at=time.monotonic() + 60.0,
    )
    ready = module._DomainState(generation=1, dirty=True, queued=True)
    scheduler._states = {
        "clean.domain": clean,
        "future.domain": future,
        "ready.domain": ready,
    }
    scheduler._heap = [
        (50, 1, "clean.domain", 1),
        (50, 2, "future.domain", 1),
        (50, 3, "ready.domain", 1),
    ]
    heapq.heapify(scheduler._heap)

    queue = scheduler.queue_health()

    assert queue["ready_executor_depth"] == 1
    assert queue["scheduled_future_depth"] == 1
    assert queue["clean_entries_removed"] == 1
    assert clean.queued is False
    assert {item[2] for item in scheduler._heap} == {
        "future.domain",
        "ready.domain",
    }


def test_runtime_stall_attribution_is_bounded_and_sanitized():
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(
        loop_warning_ms=10.0,
        loop_critical_ms=20.0,
    )
    token = diagnostics.begin_operation("background.live_status.health")
    diagnostics.record_event_loop_lag(25.0)
    diagnostics.end_operation(token)

    snapshot = diagnostics.snapshot()
    event = snapshot["event_loop"]["recent_lag_events"][-1]
    assert event["active_operations"] == ["background.live_status.health"]
    assert event["severity"] == "critical"
    encoded = json.dumps(event, sort_keys=True)
    for forbidden in ("sql", "payload", "token", "authorization", "args"):
        assert forbidden not in encoded.lower()
    assert len(snapshot["event_loop"]["recent_lag_events"]) <= 12
