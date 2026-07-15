from __future__ import annotations

import asyncio
import json
from pathlib import Path
import threading
import time

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


def _manager(capacity: int = 1, queued: int = 1):
    ensure_runtime_path()
    from api_fastapi.services.workload_admission import (
        AdmissionClass,
        AdmissionClassConfig,
        WorkloadAdmissionManager,
    )

    return WorkloadAdmissionManager(
        {
            AdmissionClass.MAINTENANCE_READ: AdmissionClassConfig(capacity, queued),
            AdmissionClass.COMMAND_RESERVATION: AdmissionClassConfig(capacity, queued),
            AdmissionClass.LIFECYCLE_WRITE: AdmissionClassConfig(capacity, queued),
            AdmissionClass.COMPATIBILITY_WRITE: AdmissionClassConfig(capacity, queued),
            AdmissionClass.AUDIT_AGGREGATION: AdmissionClassConfig(capacity, queued),
            AdmissionClass.SYSTEM_PROBE: AdmissionClassConfig(capacity, queued),
            AdmissionClass.CPU_NORMALIZATION: AdmissionClassConfig(capacity, queued),
        }
    )


def test_workload_registry_classifies_hot_heavy_and_authoritative_paths():
    ensure_runtime_path()
    from api_fastapi.services.workload_admission import WORKLOADS

    required = {
        "security.progress.read",
        "security.summary.read",
        "security.scan.reservation",
        "security.scan.lifecycle_commit",
        "security.compatibility.write",
        "security.maintenance.parity_read",
        "sqlite.integrity_check",
        "audit.summary",
        "audit.large_report",
        "workflow.summary",
        "system.local_probe",
        "system.remote_probe",
        "security.cpu_normalization",
        "security.scanner.execute",
        "backup.execute",
        "recovery.execute",
        "package.repair",
    }
    assert required <= set(WORKLOADS)
    assert WORKLOADS["security.progress.read"].execution_owner.value == "event_loop_safe"
    assert WORKLOADS["security.summary.read"].execution_owner.value == "event_loop_safe"
    assert WORKLOADS["security.full_reconstruction"].execution_owner.value == "worker_owned"
    assert WORKLOADS["security.scanner.execute"].execution_owner.value == "worker_owned"
    assert WORKLOADS["security.scan.reservation"].authoritative_output is True
    assert WORKLOADS["security.compatibility.write"].authoritative_output is False


def test_bounded_lane_never_exceeds_capacity_or_queue_and_rejects_full():
    ensure_runtime_path()
    from api_fastapi.services.workload_admission import AdmissionQueueFull

    manager = _manager(1, 1)
    release = threading.Event()
    started = threading.Event()

    def blocking():
        started.set()
        release.wait(2.0)
        return "done"

    async def exercise():
        await manager.start()
        first = asyncio.create_task(
            manager.run(
                "security.details.reconstruction",
                blocking,
                admission_timeout_seconds=0.2,
                deadline_seconds=2.0,
            )
        )
        await asyncio.to_thread(started.wait, 1.0)
        second = asyncio.create_task(
            manager.run(
                "security.details.reconstruction",
                lambda: "second",
                admission_timeout_seconds=0.2,
                deadline_seconds=2.0,
            )
        )
        await asyncio.sleep(0.03)
        snapshot = manager.snapshot()["classes"]["maintenance_read"]
        assert snapshot["active"] == 1
        assert snapshot["queued"] == 1
        with pytest.raises(AdmissionQueueFull):
            await manager.run(
                "security.details.reconstruction",
                lambda: "third",
                admission_timeout_seconds=0.0,
                deadline_seconds=1.0,
            )
        release.set()
        assert (await first)[0] == "done"
        assert (await second)[0] == "second"
        final = manager.snapshot()["classes"]["maintenance_read"]
        assert final["active"] == 0
        assert final["queued"] == 0
        assert final["rejected"] == 1
        await manager.shutdown()

    asyncio.run(exercise())


def test_deadline_exception_and_cancellation_release_permits():
    ensure_runtime_path()
    from api_fastapi.services.workload_admission import OperationDeadlineExceeded

    manager = _manager(1, 1)

    async def exercise():
        await manager.start()
        with pytest.raises(OperationDeadlineExceeded):
            await manager.run(
                "security.details.reconstruction",
                lambda: time.sleep(0.08),
                deadline_seconds=0.01,
            )
        assert manager.snapshot()["classes"]["maintenance_read"]["timed_out"] == 1
        await asyncio.sleep(0.10)
        assert manager.snapshot()["classes"]["maintenance_read"]["active"] == 0

        task = asyncio.create_task(
            manager.run(
                "security.details.reconstruction",
                lambda: time.sleep(0.05),
                deadline_seconds=1.0,
            )
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.07)
        snapshot = manager.snapshot()["classes"]["maintenance_read"]
        assert snapshot["active"] == 0
        assert snapshot["cancelled"] >= 1
        await manager.shutdown()

    asyncio.run(exercise())


def test_exception_releases_permit_shutdown_drains_and_rejects_new_work():
    ensure_runtime_path()
    from api_fastapi.services.workload_admission import AdmissionShutdown

    manager = _manager(1, 1)

    def fail():
        raise ValueError("private raw value must not enter diagnostics")

    async def exercise():
        await manager.start()
        with pytest.raises(ValueError):
            await manager.run("security.details.reconstruction", fail)
        snapshot = manager.snapshot()["classes"]["maintenance_read"]
        assert snapshot["active"] == 0
        assert snapshot["failed"] == 1
        assert snapshot["last_error_type"] == "ValueError"
        assert "private raw" not in json.dumps(snapshot).lower()
        await manager.shutdown()
        with pytest.raises(AdmissionShutdown):
            await manager.run("security.details.reconstruction", lambda: None)

    asyncio.run(exercise())


def test_request_size_limit_rejects_before_operation_or_nats_publish(tmp_path, monkeypatch):
    ensure_runtime_path()
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    from api_fastapi import deps
    from api_fastapi.routers import lite as lite_router
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    published = []

    async def forbidden_publish(*args, **kwargs):
        published.append((args, kwargs))
        raise AssertionError("oversized body reached NATS publication")

    monkeypatch.setattr(lite_router, "submit_domain_command", forbidden_publish)
    response = client().post(
        "/api/lite/security/check",
        json={"profile": "quick", "reason": "x" * 5000},
    )
    assert response.status_code == 413
    payload = response.json()
    assert payload == {
        "status": "rejected",
        "accepted": False,
        "reason": "payload_too_large",
        "retryable": False,
        "operation": "security_check",
        "message": "This request is too large for Pocket Lab Lite.",
        "sanitized": True,
    }
    assert published == []
    assert SecuritySQLiteRepository().get_latest_run() is None


def test_reservation_overload_returns_503_without_run_or_publish(tmp_path, monkeypatch):
    ensure_runtime_path()
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    from api_fastapi import deps
    from api_fastapi.routers import lite as lite_router
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository
    from api_fastapi.services.workload_admission import AdmissionClass, AdmissionQueueFull

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    published = []

    async def reject_reservation(*args, **kwargs):
        raise AdmissionQueueFull(
            "security.scan.reservation",
            AdmissionClass.COMMAND_RESERVATION,
            "Pocket Lab is busy with another safe operation. Try again shortly.",
        )

    async def forbidden_publish(*args, **kwargs):
        published.append((args, kwargs))

    async def quiet_audit(**kwargs):
        return None

    monkeypatch.setattr(lite_router.lite_security, "run_api_maintenance_timed", reject_reservation)
    monkeypatch.setattr(lite_router, "submit_domain_command", forbidden_publish)
    monkeypatch.setattr(lite_router, "_record_admission_outcome", quiet_audit)
    response = client().post("/api/lite/security/check", json={"profile": "quick"})
    assert response.status_code == 503
    payload = response.json()
    assert payload["accepted"] is False
    assert payload["reason"] == "control_plane_busy"
    assert payload["retryable"] is True
    assert response.headers["retry-after"] == "2"
    assert published == []
    assert SecuritySQLiteRepository().get_latest_run() is None


def test_post_publication_lifecycle_timeout_remains_truthfully_accepted(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import lite as lite_router
    from api_fastapi.services.workload_admission import (
        AdmissionClass,
        OperationDeadlineExceeded,
    )

    calls = 0
    published = []

    async def fake_maintenance(function, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            run_id = kwargs["run_id"]
            return (
                {
                    "command": {
                        "run_id": run_id,
                        "command_id": run_id,
                        "profile": kwargs["profile"],
                        "scope": kwargs["scope"],
                        "requested_at": kwargs["requested_at"],
                    },
                    "reservation": {"reserved": True, "run": {"run_id": run_id}},
                    "reservation_stages": {},
                },
                {"queue_wait_ms": 0.0, "execution_ms": 1.0},
            )
        raise OperationDeadlineExceeded(
            "security.scan.lifecycle_commit",
            AdmissionClass.LIFECYCLE_WRITE,
            "Pocket Lab is still finishing a safe operation. Check status shortly.",
        )

    async def fake_submit(subject, event_type, command, **kwargs):
        published.append((subject, event_type, command))
        return {"job_id": command["run_id"], "command_id": command["run_id"]}

    async def quiet_audit(**kwargs):
        return None

    monkeypatch.setattr(lite_router.lite_security, "run_api_maintenance_timed", fake_maintenance)
    monkeypatch.setattr(lite_router, "submit_domain_command", fake_submit)
    monkeypatch.setattr(lite_router, "_record_admission_outcome", quiet_audit)
    response = client().post("/api/lite/security/check", json={"profile": "quick"})
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["lifecycle_pending"] is True
    assert len(published) == 1


def test_runtime_diagnostics_include_bounded_sanitized_admission_metrics():
    response = client().get("/api/lite/diagnostics/runtime")
    assert response.status_code == 200
    payload = response.json()
    admission = payload["workload_admission"]
    assert admission["sanitized"] is True
    for item in admission["classes"].values():
        for key in (
            "capacity",
            "queue_capacity",
            "active",
            "queued",
            "accepted",
            "rejected",
            "completed",
            "failed",
            "timed_out",
            "cancelled",
            "admission_wait_count",
        ):
            assert isinstance(item[key], int)
        assert item["active"] <= item["capacity"]
        assert item["queued"] <= item["queue_capacity"]
    text = json.dumps(payload).lower()
    for forbidden in ("authorization", "bearer ", "password=", "nats://", "private key"):
        assert forbidden not in text


def test_no_unbounded_security_executor_or_raw_executor_submission_regression():
    root = Path(__file__).resolve().parents[2]
    security = (root / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py").read_text()
    admission = (root / "pocket-lab-final-structure/runtime/api_fastapi/services/workload_admission.py").read_text()
    main = (root / "pocket-lab-final-structure/runtime/api_fastapi/main.py").read_text()
    api = (root / "src/lib/liteApi.js").read_text()

    assert "_SECURITY_MAINTENANCE_EXECUTOR" not in security
    assert "run_in_executor(_SECURITY_MAINTENANCE_EXECUTOR" not in security
    assert "self._active += 1" in admission
    assert "loop.run_in_executor(self._executor, invoke)" in admission
    assert admission.index("self._active += 1") < admission.index("loop.run_in_executor(self._executor, invoke)")
    assert "asyncio.to_thread(lite_security.initialize_security_sqlite_runtime)" not in main
    assert "LiteRequestSizeLimitMiddleware" in main
    assert "data?.detail?.message" in api


def test_admission_timeout_is_distinct_and_releases_queued_permit():
    ensure_runtime_path()
    from api_fastapi.services.workload_admission import AdmissionTimeout

    manager = _manager(1, 1)
    release = threading.Event()
    started = threading.Event()

    def blocking():
        started.set()
        release.wait(2.0)
        return "done"

    async def exercise():
        await manager.start()
        first = asyncio.create_task(
            manager.run(
                "security.details.reconstruction",
                blocking,
                admission_timeout_seconds=0.2,
                deadline_seconds=2.0,
            )
        )
        await asyncio.to_thread(started.wait, 1.0)
        with pytest.raises(AdmissionTimeout):
            await manager.run(
                "security.details.reconstruction",
                lambda: "never",
                admission_timeout_seconds=0.02,
                deadline_seconds=1.0,
            )
        snapshot = manager.snapshot()["classes"]["maintenance_read"]
        assert snapshot["active"] == 1
        assert snapshot["queued"] == 0
        assert snapshot["timed_out"] == 1
        release.set()
        assert (await first)[0] == "done"
        await manager.shutdown()

    asyncio.run(exercise())


def test_fastapi_owned_to_thread_calls_are_classified_or_removed():
    root = Path(__file__).resolve().parents[2]
    services = root / "pocket-lab-final-structure/runtime/api_fastapi/services"
    action_queue = (services / "action_queue.py").read_text()
    observability = (services / "observability_status.py").read_text()
    live_status = (services / "live_status.py").read_text()
    domain_commands = (services / "domain_commands.py").read_text()
    release_orchestrator = (services / "release_orchestrator.py").read_text()
    nats_bus = (services / "nats_bus.py").read_text()

    assert "asyncio.to_thread" not in action_queue
    assert "asyncio.to_thread" not in observability
    assert "asyncio.to_thread" not in live_status
    assert '"control.command_envelope.prepare"' in action_queue
    assert '"system.observability_probe"' in observability
    assert '"system.telemetry_probe"' in live_status
    assert '"system.health_probe"' in live_status
    assert '"system.fleet_probe"' in live_status

    # These remaining thread hops are execution-plane or bounded-owner paths,
    # not unclassified FastAPI request maintenance work.
    assert "asyncio.to_thread" in domain_commands
    assert "asyncio.to_thread" in release_orchestrator
    assert "WORKFLOW_ENGINE.stop_writer" in nats_bus


def test_generic_admission_error_handler_is_sanitized_and_retryable(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import observability_status
    from api_fastapi.services.workload_admission import (
        AdmissionClass,
        AdmissionQueueFull,
    )

    async def reject(*args, **kwargs):
        raise AdmissionQueueFull(
            "system.observability_probe",
            AdmissionClass.SYSTEM_PROBE,
            "Pocket Lab is busy with another safe operation. Try again shortly.",
        )

    monkeypatch.setattr(observability_status.WORKLOAD_ADMISSION, "run", reject)
    response = client().get("/api/observability/status?refresh=true")
    assert response.status_code == 503
    payload = response.json()
    assert payload == {
        "status": "busy",
        "accepted": False,
        "reason": "control_plane_busy",
        "retryable": True,
        "operation": "system.observability_probe",
        "admission_class": "system_probe",
        "message": "Pocket Lab is busy with another safe operation. Try again shortly.",
        "sanitized": True,
    }
    assert response.headers["retry-after"] == "2"
