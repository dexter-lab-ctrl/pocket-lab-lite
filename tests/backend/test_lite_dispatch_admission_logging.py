from __future__ import annotations

import logging
import threading
import time


def test_dispatcher_skips_future_heap_head_for_due_work(monkeypatch) -> None:
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    scheduler = ProjectionScheduler()
    ran = threading.Event()

    def projector(_payload):
        ran.set()
        return 1

    scheduler.register(ProjectionJob(
        domain="future.high",
        builder=lambda: {},
        projector=lambda _payload: None,
        priority=1,
        work_class="io",
        deadline_seconds=1.0,
        optional=False,
    ))
    scheduler.register(ProjectionJob(
        domain="ready.low",
        builder=lambda: {"ok": True},
        projector=projector,
        priority=50,
        work_class="io",
        deadline_seconds=1.0,
        optional=False,
    ))
    scheduler.start()
    with scheduler._condition:
        future_state = scheduler._states["future.high"]
        future_state.next_retry_at = time.monotonic() + 5.0
    scheduler.mark_dirty("future.high")
    scheduler.mark_dirty("ready.low")
    assert ran.wait(2.0)
    diagnostics = scheduler.diagnostics()
    assert diagnostics["dispatcher_alive"] is True
    assert diagnostics["dispatch_count"] >= 1
    assert diagnostics["future_head_skip_count"] >= 1
    scheduler.shutdown()


def test_fleet_event_admission_is_nonblocking_and_coalescing(monkeypatch) -> None:
    from api_fastapi.services import nats_bus

    admission = nats_bus._FleetEventAdmission(maximum=16)
    blocker = threading.Event()

    def slow_handler(_event):
        blocker.wait(0.2)

    import api_fastapi.services.fleet_registry as fleet_registry
    monkeypatch.setattr(fleet_registry, "handle_agent_event", slow_handler)
    event = {
        "subject": "pocketlab.events.fleet.node_heartbeat",
        "data": {"node_id": "node-a"},
    }
    started = time.monotonic()
    first = admission.submit(event)
    second = admission.submit(event)
    elapsed = time.monotonic() - started
    assert first["accepted"] is True
    assert second["accepted"] is True
    assert elapsed < 0.05
    blocker.set()


def test_event_loop_logging_is_enqueued_not_emitted_inline(monkeypatch) -> None:
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(loop_warning_ms=1.0, loop_critical_ms=2.0)
    called = threading.Event()

    def slow_log(_level, _message, *_args):
        time.sleep(0.1)
        called.set()

    monkeypatch.setattr(logging.getLogger("api_fastapi.services.runtime_diagnostics"), "log", slow_log)
    started = time.monotonic()
    diagnostics.record_event_loop_lag(10.0)
    elapsed = time.monotonic() - started
    assert elapsed < 0.05
    assert called.wait(1.0)
