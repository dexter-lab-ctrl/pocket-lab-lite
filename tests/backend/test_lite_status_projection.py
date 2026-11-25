from __future__ import annotations

from pocket_lab_test_utils import ensure_runtime_path


def test_worker_execution_status_uses_prepared_consumer_when_local_sampler_is_absent(
    monkeypatch,
):
    ensure_runtime_path()
    from api_fastapi.services import lite_status

    monkeypatch.setattr(lite_status.lite_catalog_service, "catalog_apps_count", lambda: 1)
    payload = lite_status._build_lite_status_from_inputs(
        checked_at="2026-11-25T12:00:00Z",
        engine={"status": "healthy", "services": {}},
        bus={
            "connected": True,
            "jetstream_enabled": True,
            "durable_consumer_health": {
                "pocketlab_command_worker_v1": {
                    "healthy": True,
                    "task_alive": True,
                    "subscription_present": True,
                }
            },
        },
        live={"running": False},
        remote_access={"status": "healthy", "ready": True, "summary": "Remote access is ready."},
        telemetry={"status": "healthy"},
        fleet={"status": "healthy"},
        fleet_nodes=[{"system_health": {"status": "healthy", "severity": "none", "attention_count": 0}}],
        current_state={
            "runtime_contract": {"state": "stable", "summary": "System running normally"},
            "security_summary": {},
        },
    )

    worker = next(item for item in payload["services"] if item["name"] == "Worker Execution")
    assert worker["status"] == "healthy"
    assert worker["summary"] == "Worker command consumer is healthy"
    assert worker["source"] == "NATS durable worker consumer"
    assert payload["summary"]["live_sampler_running"] is False
    assert payload["summary"]["worker_execution_ready"] is True
