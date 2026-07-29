from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import time

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _runtime_root() -> Path:
    ensure_runtime_path()
    return Path(__file__).resolve().parents[2] / "pocket-lab-final-structure" / "runtime"


def test_adaptive_cadence_slows_after_unchanged_and_accelerates_for_transition():
    ensure_runtime_path()
    from api_fastapi.services.adaptive_runtime import AdaptiveRuntimeController

    controller = AdaptiveRuntimeController()
    domain = "apps.lifecycle"
    policy = controller.policy_for(domain, priority=60, work_class="io", optional=True)

    for _ in range(5):
        controller.record_result(
            domain,
            cpu_ms=1,
            wall_ms=2,
            queue_wait_ms=0,
            outcome="unchanged",
            changed=False,
        )
    stable = controller.domain_status(domain)
    assert stable["cadence_state"] == "stable"
    assert stable["consecutive_unchanged"] == 5
    assert stable["next_reconciliation_seconds"] >= int(policy.stable_interval_seconds)

    controller.mark_dirty(domain, active_hint=True)
    controller.record_result(
        domain,
        cpu_ms=2,
        wall_ms=3,
        queue_wait_ms=0,
        outcome="committed",
        changed=True,
        active_transition=True,
    )
    active = controller.domain_status(domain)
    assert active["cadence_state"] == "active_transition"
    assert 0 < active["next_reconciliation_seconds"] <= int(policy.active_interval_seconds * 1.1) + 1


def test_adaptive_cpu_budget_queue_pressure_and_critical_reserve():
    ensure_runtime_path()
    from api_fastapi.services.adaptive_runtime import AdaptivePolicy, AdaptiveRuntimeController

    controller = AdaptiveRuntimeController()
    domain = "apps.catalog"
    controller._policies[domain] = AdaptivePolicy(
        active_interval_seconds=1,
        stable_interval_seconds=10,
        max_interval_seconds=30,
        transition_hold_seconds=2,
        short_cpu_budget_ms=5,
        medium_cpu_budget_ms=5,
        long_cpu_budget_ms=5,
        payload_budget_bytes=64 * 1024,
        allocation_budget_bytes=256 * 1024,
        serialization_budget_ms=50,
        critical=False,
    )
    controller.record_result(
        domain,
        cpu_ms=6,
        wall_ms=6,
        queue_wait_ms=0,
        outcome="committed",
        changed=True,
    )
    deferred = controller.decide(
        domain,
        priority=60,
        work_class="io",
        optional=True,
        queue_depth=0,
        queue_age_ms=0,
        active_count=0,
        capacity=1,
    )
    assert deferred.accepted is False
    assert deferred.reason == "cpu_budget_exhausted"
    assert deferred.retry_after_ms > 0

    critical = controller.decide(
        domain,
        priority=10,
        work_class="critical",
        optional=False,
        queue_depth=controller.queue_depth_critical + 5,
        queue_age_ms=controller.queue_lag_critical_ms + 1,
        active_count=2,
        capacity=1,
        event_loop_lag_ms=controller.event_loop_critical_ms + 1,
    )
    assert critical.accepted is True
    assert critical.load_state == "critical"

    queue_deferred = controller.decide(
        "recovery.details",
        priority=80,
        work_class="io",
        optional=True,
        queue_depth=controller.queue_depth_warning,
        queue_age_ms=0,
        active_count=0,
        capacity=2,
    )
    assert queue_deferred.accepted is False
    assert queue_deferred.reason == "queue_pressure"


def test_payload_assessment_is_deterministic_and_enforces_budgets():
    ensure_runtime_path()
    from api_fastapi.services.adaptive_runtime import AdaptivePolicy, AdaptiveRuntimeController

    controller = AdaptiveRuntimeController()
    domain = "system.test_payload"
    controller._policies[domain] = AdaptivePolicy(
        active_interval_seconds=1,
        stable_interval_seconds=10,
        max_interval_seconds=30,
        transition_hold_seconds=2,
        short_cpu_budget_ms=100,
        medium_cpu_budget_ms=100,
        long_cpu_budget_ms=100,
        payload_budget_bytes=100,
        allocation_budget_bytes=1024 * 1024,
        serialization_budget_ms=500,
        critical=False,
    )
    first = controller.assess_payload(domain, {"b": 2, "a": 1})
    second = controller.assess_payload(domain, {"a": 1, "b": 2})
    assert first.checksum == second.checksum
    assert first.within_budget is True

    oversized = controller.assess_payload(domain, {"items": ["x" * 80, "y" * 80]})
    assert oversized.within_budget is False
    assert oversized.reason == "payload_budget_exceeded"
    assert oversized.payload_bytes > 100


def test_compact_event_envelope_is_additive_sanitized_and_size_bounded(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services.nats_bus import PocketLabEventBus

    bus = PocketLabEventBus()
    event = bus.envelope(
        "pocketlab.events.security.scan",
        "security.scan.updated",
        {
            "domain": "security.progress",
            "entity_id": "run-1",
            "generation": 4,
            "status": "running",
            "reason_code": "worker_claimed",
            "password": "must-not-be-promoted",
            "metadata": {"safe": True},
        },
        trace_id="trace-1",
    )
    assert event["schema_version"] == 2
    assert event["event_id"] == event["id"]
    assert event["event_type"] == event["type"]
    assert event["occurred_at"] == event["time"]
    assert event["correlation_id"] == event["trace_id"] == "trace-1"
    assert event["domain"] == "security.progress"
    assert "password" not in {key for key in event if key != "data"}
    encoded = bus._encode_event("pocketlab.events.security.scan", event)
    assert json.loads(encoded)["schema_version"] == 2

    monkeypatch.setenv("POCKETLAB_EVENT_MAX_BYTES", str(16 * 1024))
    with pytest.raises(ValueError, match="transport budget"):
        bus._encode_event(
            "pocketlab.events.security.scan",
            bus.envelope(
                "pocketlab.events.security.scan",
                "security.scan.updated",
                {"metadata": "x" * (20 * 1024)},
            ),
        )


def test_bounded_process_runtime_caps_output_and_defers_at_capacity(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services.process_runtime import BoundedProcessRuntime

    class FakeProcess:
        pid = 123456789
        returncode = 0

        def communicate(self, timeout=None):
            return ("x" * (70 * 1024), "")

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    monkeypatch.setenv("POCKETLAB_PROCESS_OUTPUT_LIMIT_BYTES", str(64 * 1024))
    monkeypatch.setenv("POCKETLAB_PROCESS_ACQUIRE_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("POCKETLAB_HEAVY_PROCESS_MAX_CONCURRENT", "1")
    runtime = BoundedProcessRuntime()
    monkeypatch.setattr(runtime, "_apply_limits", lambda *args, **kwargs: None)

    result = runtime.run(
        ["fake", "--safe"],
        cwd=tmp_path,
        timeout=5,
        workload="security.trivy",
        redact=lambda value: value,
        popen_factory=lambda *args, **kwargs: FakeProcess(),
    )
    assert result["ok"] is True
    assert result["output_truncated"] is True
    assert len(result["stdout"].encode()) == 64 * 1024
    snapshot = runtime.snapshot()
    assert snapshot["workloads"]["security.trivy"]["output_truncated"] == 1
    assert "args" not in snapshot["workloads"]["security.trivy"]

    assert runtime._global.acquire(blocking=False) is True
    try:
        deferred = runtime.run(
            ["fake"],
            cwd=tmp_path,
            timeout=5,
            workload="maintenance.integrity",
            redact=lambda value: value,
            popen_factory=lambda *args, **kwargs: FakeProcess(),
        )
    finally:
        runtime._global.release()
    assert deferred["capacity_deferred"] is True
    assert deferred["retry_after_ms"] == 2000


def test_core_supervisor_restart_budget_is_bounded(tmp_path, monkeypatch):
    module_path = _runtime_root() / "supervisors" / "pocketlab_core_supervisor.py"
    spec = importlib.util.spec_from_file_location("phase45_supervisor", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("POCKETLAB_CORE_SUPERVISOR_COOLDOWN_SECONDS", "30")
    monkeypatch.setenv("POCKETLAB_CORE_SUPERVISOR_RESTART_WINDOW_SECONDS", "300")
    monkeypatch.setenv("POCKETLAB_CORE_SUPERVISOR_MAX_RESTARTS_PER_WINDOW", "2")
    supervisor = module.LiteCoreSupervisor()
    now = module.epoch()
    supervisor.restart_history["pocket-worker"] = [now - 5, now - 1]
    allowed, reason, retry_after, generation = supervisor._restart_admission(
        "pocket-worker", "restart:pocket-worker"
    )
    assert allowed is False
    assert reason == "restart_budget_exhausted"
    assert retry_after > 0
    assert generation == 0
    diagnostics = supervisor.restart_diagnostics()
    assert diagnostics["services"]["pocket-worker"]["recent_restart_count"] == 2
    assert diagnostics["sanitized"] is True


def test_prepared_read_and_frontend_expose_truthful_capacity_state():
    ensure_runtime_path()
    from api_fastapi.services.lite_control_plane_store import PreparedRead

    prepared = PreparedRead(
        payload={"status": "healthy"},
        etag='"phase45"',
        source_revision=4,
        projection_age_ms=100,
        read_degraded=True,
        refresh_pending=True,
        timing={"sqlite_query_ms": 0.4},
        retry_after_seconds=5,
        retry_after_ms=5000,
        degraded_reason="queue_pressure",
        data_source="last_known_good",
        load_state="elevated",
    )
    assert prepared.payload["status"] == "healthy"
    assert prepared.degraded_reason == "queue_pressure"
    assert prepared.data_source == "last_known_good"

    repo = Path(__file__).resolve().parents[2]
    query_source = (repo / "src/hooks/useLiteQuery.js").read_text(encoding="utf-8")
    api_source = (repo / "src/lib/liteApi.js").read_text(encoding="utf-8")
    machine_source = (repo / "src/machines/liteSecurityCheckMachine.js").read_text(encoding="utf-8")
    store_source = (repo / "src/stores/liteUiStore.js").read_text(encoding="utf-8")
    assert "structuralSharing: true" in query_source
    assert "retryAfterMs" in query_source
    assert "waitingForCapacity" in machine_source
    assert "degradedVisibility" in machine_source
    assert "controlPlaneLoad" in store_source
    assert "read_degraded" in api_source
    assert "snapshot" in api_source


def test_adaptive_gate_extends_existing_durable_runner_and_has_no_tmp_path():
    repo = Path(__file__).resolve().parents[2]
    main = (repo / "scripts/dev/check-lite-long-duration-gates-server-phone.sh").read_text(encoding="utf-8")
    wrapper = (repo / "scripts/dev/long-gates/adaptive-runtime-hardening.sh").read_text(encoding="utf-8")
    analyzer = (repo / "scripts/dev/lib/long_gate_adaptive_runtime.py").read_text(encoding="utf-8")
    assert '"adaptive-runtime|' in main
    assert "LONG_GATE_ADAPTIVE_DURATION_SECONDS" in main
    assert "long_gate_stage_begin" in wrapper
    assert "long_gate_stage_pass" in wrapper
    assert "long_gate_stage_fail" in wrapper
    assert "atomic" in analyzer.lower()
    assert "samples.jsonl" in analyzer
    assert "/tmp" not in wrapper
    assert "/tmp" not in analyzer


def test_adaptive_gate_analyzer_distinguishes_failures_and_unsupported_metrics():
    module_path = Path(__file__).resolve().parents[2] / "scripts/dev/lib/long_gate_adaptive_runtime.py"
    spec = importlib.util.spec_from_file_location("phase45_gate_analyzer", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    class Args:
        minimum_samples = 5
        queue_depth_budget = 12
        cpu_p99_budget_ms = 750
        wall_p99_budget_ms = 8000
        queue_wait_p99_budget_ms = 20000
        max_exhaustion_ratio = 0.5
        api_p95_budget_ms = 750
        api_p99_budget_ms = 2000
        event_loop_p95_budget_ms = 150
        event_loop_p99_budget_ms = 400
        rss_growth_budget_bytes = 64 * 1024 * 1024
        peak_rss_budget_bytes = 768 * 1024 * 1024

    sample = {
        "http": {"ok": True, "duration_ms": 10},
        "scheduler": {"queued_domains": 0},
        "event_loop": {"latest_lag_ms": 1},
        "adaptive": {
            "event_payloads": {"oversize_rejections": 0},
            "domains": {
                "system.health": {
                    "cpu_budget_exhausted": False,
                    "load_state": "normal",
                    "cpu_ms": {"p99": 2},
                    "wall_ms": {"p99": 3},
                    "queue_wait_ms": {"p99": 1},
                    "payload_bytes": {"max": 100},
                    "allocation_bytes": {"max": 200},
                    "serialization_ms": {"max": 1},
                    "payload_budget_bytes": 1000,
                    "allocation_budget_bytes": 2000,
                    "serialization_budget_ms": 10,
                }
            },
        },
        "process_runtime": {
            "subprocess_count": 0,
            "subprocess_limit": 1,
            "memory_rss_bytes": None,
            "workloads": {},
        },
    }
    checks, failures, warnings = module.evaluate([sample] * 5, Args())
    assert failures == []
    assert "rss_memory_unsupported" in warnings
    assert any(row["check"] == "rss_memory_bytes" and row["status"] == "unsupported" for row in checks)

    overloaded = json.loads(json.dumps(sample))
    overloaded["scheduler"]["queued_domains"] = 99
    _checks, failures, _warnings = module.evaluate([overloaded] * 5, Args())
    assert "scheduler_queue_depth" in failures


def test_worker_registers_core_projection_mailbox_domains_before_consumption() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    worker = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "workers"
        / "pocketlab_worker.py"
    ).read_text(encoding="utf-8")
    shared = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "lite_core_projections.py"
    ).read_text(encoding="utf-8")

    assert "await asyncio.to_thread(lite_core_projections.register_jobs)" in worker
    assert worker.index("lite_core_projections.register_jobs") < worker.index(
        "PROJECTION_SCHEDULER.consume_dirty_signals"
    )
    assert '"fleet.summary"' in shared
    assert '"apps.lifecycle"' in shared
    assert '"recovery.summary"' in shared
    assert '"recovery.details"' in shared
    assert "unregistered=unregistered" in worker
    assert "worker.projection_registry_incomplete" in worker


def test_api_and_worker_share_core_projection_registration_contract() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    router = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "routers"
        / "lite.py"
    ).read_text(encoding="utf-8")
    worker = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "workers"
        / "pocketlab_worker.py"
    ).read_text(encoding="utf-8")

    assert "lite_core_projections.schedule_startup_warmup()" in router
    assert "lite_core_projections.schedule_startup_warmup" in worker
    assert "from api_fastapi.routers import lite" not in worker


def test_core_apps_registration_uses_existing_store_snapshot_api() -> None:
    root = Path(__file__).resolve().parents[2]
    shared = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "lite_core_projections.py"
    ).read_text(encoding="utf-8")

    assert "CONTROL_PLANE.app_projection_snapshot" in shared
    assert "CONTROL_PLANE.apps_projection_snapshot" not in shared


def test_worker_projection_task_retries_initialization_and_surfaces_exit() -> None:
    root = Path(__file__).resolve().parents[2]
    worker = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "workers"
        / "pocketlab_worker.py"
    ).read_text(encoding="utf-8")

    assert "POCKETLAB_WORKER_PROJECTION_RETRY_SECONDS" in worker
    assert "worker.projection_initialization_degraded" in worker
    assert "projection_registry_incomplete" in worker
    assert "projection_task.add_done_callback(_projection_task_done)" in worker
    assert "worker.projection_task_stopped" in worker


def test_worker_projection_mailbox_loop_imports_monotonic_clock() -> None:
    root = Path(__file__).resolve().parents[2]
    worker_path = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "workers"
        / "pocketlab_worker.py"
    )
    worker = worker_path.read_text(encoding="utf-8")

    compile(worker, str(worker_path), "exec")
    assert "import time" in worker
    assert "now = time.monotonic()" in worker
    assert "consecutive_signal_failures" in worker
    assert "last_error_log_at" in worker
    assert "retry_seconds=1" in worker


def test_projection_scheduler_queue_depth_reconciles_stale_flags() -> None:
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    scheduler = ProjectionScheduler()
    scheduler.register(
        ProjectionJob(
            domain="test.queue.truth",
            builder=lambda: {},
            projector=lambda _payload: 1,
            priority=50,
            work_class="io",
            deadline_seconds=1.0,
        )
    )
    with scheduler._condition:  # targeted invariant test of internal bookkeeping
        state = scheduler._states["test.queue.truth"]
        state.queued = True
        state.dirty = False
        scheduler._heap.clear()

    diagnostics = scheduler.diagnostics()
    assert diagnostics["queued_domains"] == 0
    assert diagnostics["queue"]["executor_depth"] == 0
    assert diagnostics["queue"]["stale_flags_cleared"] == 1
    assert scheduler._states["test.queue.truth"].queued is False


def test_prepared_runtime_contract_is_compact_cached_and_worker_authoritative() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    worker = (root / "pocket-lab-final-structure" / "runtime" / "workers" / "pocketlab_worker.py").read_text(encoding="utf-8")
    snapshot = (root / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "services" / "runtime_snapshot_store.py").read_text(encoding="utf-8")
    router = (root / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "routers" / "lite.py").read_text(encoding="utf-8")

    assert '"executor_depth"' in worker
    assert '"durable_pending"' in worker
    assert '"worker_health"' in worker
    assert "_compact_adaptive_runtime" in worker
    assert "_compact_process_runtime" in worker
    assert "encoded_runtime_response" in snapshot
    assert "_RESPONSE_CACHE_BYTES" in snapshot
    assert 'media_type="application/json"' in router


def test_projection_scheduler_ready_depth_excludes_future_entries() -> None:
    import time

    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    scheduler = ProjectionScheduler()
    scheduler.register(
        ProjectionJob(
            domain="test.queue.future",
            builder=lambda: {},
            projector=lambda _payload: 1,
            priority=50,
            work_class="io",
            deadline_seconds=1.0,
        )
    )
    with scheduler._condition:
        state = scheduler._states["test.queue.future"]
        state.generation += 1
        state.dirty = True
        state.not_before_at = time.monotonic() + 60.0
        scheduler._enqueue_locked("test.queue.future", state)

    queue = scheduler.queue_health()
    assert queue["executor_depth"] == 0
    assert queue["ready_executor_depth"] == 0
    assert queue["scheduled_future_depth"] == 1
    assert scheduler.diagnostics()["queued_domains"] == 0


def test_runtime_snapshot_hot_path_is_preencoded_revisioned_and_nonblocking() -> None:
    root = Path(__file__).resolve().parents[2]
    scheduler = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "projection_scheduler.py"
    ).read_text(encoding="utf-8")
    runtime = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "runtime_snapshot_store.py"
    ).read_text(encoding="utf-8")
    diagnostics = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "runtime_diagnostics.py"
    ).read_text(encoding="utf-8")
    router = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "routers"
        / "lite.py"
    ).read_text(encoding="utf-8")

    assert '"ready_executor_depth"' in scheduler
    assert '"scheduled_future_depth"' in scheduler
    assert "snapshot_revision" in runtime
    assert "runtime_fragment" in runtime
    assert "json.loads(row[\"payload_json\"])" not in runtime.split(
        "def encoded_runtime_response", 1
    )[1]
    assert "def compact_runtime_fragment" in diagnostics
    assert "async def get_lite_runtime_diagnostics" in router
    assert "encoded_runtime_response, runtime_revision, runtime_fragment" in router
    assert "RUNTIME_DIAGNOSTICS.snapshot()" not in router.split(
        '@router.get("/diagnostics/runtime")', 1
    )[1].split('@router.get("/diagnostics/runtime/full")', 1)[0]


def test_worker_registry_covers_ui_critical_catalog_domains_and_is_authoritative() -> None:
    from api_fastapi.services import lite_core_projections

    assert {
        "apps.catalog",
        "apps.actions:photoprism",
        "apps.lifecycle",
        "fleet.summary",
        "recovery.summary",
        "recovery.details",
    }.issubset(lite_core_projections.CORE_PROJECTION_DOMAINS)
    assert "system.status" in lite_core_projections.UI_CRITICAL_BOOTSTRAP_DOMAINS

    root = Path(__file__).resolve().parents[2]
    worker = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "workers"
        / "pocketlab_worker.py"
    ).read_text(encoding="utf-8")
    diagnostics = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "routers"
        / "lite.py"
    ).read_text(encoding="utf-8")

    assert "missing_required_domains" in worker
    assert '"diagnostic_source": "worker_prepared_sqlite"' in worker
    assert '"authoritative_execution_registry": True' in diagnostics
    assert '"projection_scheduler_local"' in diagnostics


def test_unregistered_mailbox_rows_are_separate_from_runnable_pressure() -> None:
    root = Path(__file__).resolve().parents[2]
    scheduler = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "projection_scheduler.py"
    ).read_text(encoding="utf-8")

    assert '"runnable_pending": runnable_pending' in scheduler
    assert '"total_pending": max(0, len(rows) - claimed)' in scheduler
    assert '"unregistered_domains": sorted(unregistered_domains)' in scheduler
    assert "queue_depth=0 if bootstrap_required" in scheduler
    assert "optional=False if bootstrap_required" in scheduler
    assert "bootstrap_admission_count" in scheduler
