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
