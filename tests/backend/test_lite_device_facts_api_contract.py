from __future__ import annotations

import json

import pytest

from pocket_lab_test_utils import client as raw_client, ensure_runtime_path, isolated_state_dir

NOW = "2026-09-05T12:00:00Z"


def _resource(metric, value, *, unit=None, source="server_central_telemetry"):
    return {
        "metric": metric,
        "value": value,
        "unit": unit,
        "status": "available",
        "collection_status": "available",
        "source": source,
        "observed_at": NOW,
        "freshness": "current",
        "reason_code": "collected",
        "support_state": "supported",
        "schema_version": 2,
        "revision": 7,
    }


def _facts(device_id="pocket-lab-lite-server", source="server_central_telemetry"):
    return {
        "schema_version": 2,
        "revision": 9,
        "device_id": device_id,
        "resources": {
            "memory": _resource("memory", {"total_mb": 4096, "free_mb": 2048, "used_mb": 2048}, unit="MB", source=source),
            "storage": _resource("storage", {"total_mb": 256000, "free_mb": 128000}, unit="MB", source=source),
            "cpu_usage": _resource("cpu_usage", {"usage_percent": 12}, unit="percent", source=source),
            "temperature": _resource("temperature", {"celsius": 42}, unit="celsius", source=source),
        },
        "software": {
            "node_agent": {"component": "node_agent", "version": "2.5.0", "status": "current", "source": "runtime_heartbeat", "observed_at": NOW, "freshness": "current", "reason_code": "version_reported"},
            "supervisor": {"component": "supervisor", "version": "2.5.0", "status": "current", "source": "sqlite_supervisor_evidence", "observed_at": NOW, "freshness": "current", "reason_code": "version_reported"},
        },
        "observed_at": NOW,
        "sanitized": True,
    }


def _capabilities():
    return [
        {
            "id": "serve_control_plane", "label": "Serves Pocket Lab", "category": "control_plane",
            "verification_strategy": "control_plane_runtime", "status": "verified", "reason_code": "runtime_evidence_verified",
            "source": "control_plane_runtime_evidence", "advertised": False, "advertised_at": None,
            "evaluated_at": NOW, "verified_at": NOW, "freshness": "current", "expires_at": "2026-09-05T12:03:00Z",
            "revision": 1, "schema_version": 3, "evidence": {"online": True},
        },
        {
            "id": "remote_access", "label": "Remote access", "category": "connectivity",
            "verification_strategy": "remote_access_health", "status": "verified", "reason_code": "runtime_evidence_verified",
            "source": "remote_access_health", "advertised": False, "advertised_at": None,
            "evaluated_at": NOW, "verified_at": NOW, "freshness": "current", "expires_at": "2026-09-05T12:03:00Z",
            "revision": 2, "schema_version": 3, "evidence": {},
        },
    ]


def _services():
    return [
        {
            "service_id": "gateway-alpha", "label": "Gateway Alpha", "category": "api", "manager": "pm2",
            "state": "online", "reported_at": NOW, "freshness": "current", "restart_supported": False,
            "restart_reason": "backend_guard_required", "source": "pm2_prepared_projection", "schema_version": 1, "sanitized": True,
        },
        {
            "service_id": "queue-beta", "label": "Queue Beta", "category": "messaging", "manager": "pm2",
            "state": "online", "reported_at": NOW, "freshness": "current", "restart_supported": False,
            "restart_reason": "backend_guard_required", "source": "pm2_prepared_projection", "schema_version": 1, "sanitized": True,
        },
    ]


def _device():
    facts = _facts()
    return {
        "id": "pocket-lab-lite-server",
        "node_id": "pocket-lab-lite-server",
        "name": "Pocket Lab Lite Server",
        "role": "server_host",
        "role_label": "Server Host",
        "status": "healthy",
        "connection": "online",
        "agent_status": "healthy",
        "agent_process_status": "online",
        "supervisor_status": "healthy",
        "supervisor_status_freshness": "fresh",
        "last_seen_at": NOW,
        "last_heartbeat_at": NOW,
        "last_supervisor_heartbeat_at": NOW,
        "is_current": True,
        "protected_server_host": True,
        "remote_access": True,
        "system_profile": {"agent_version": "2.5.0", "supervisor_version": "2.5.0", "collection_status": "current", "freshness": "current", "collected_at": NOW},
        "device_facts": facts,
        "resource_observations": facts["resources"],
        "capability_states": _capabilities(),
        "runtime_services": _services(),
        "dependencies": {"hosted_apps": [], "hosted_app_count": 0, "backup_set_count": 0},
        "restart_agent_assessment": {"allowed": False, "reason_code": "server_host_protected", "summary": "Protected server host.", "command_deliverable": False, "supervisor_fresh": True, "agent_state": "online"},
        "proactive_health": {
            "status": "healthy", "severity": "none", "summary": "Device health is current.",
            "resources": {}, "resource_observations": facts["resources"], "device_facts": facts,
            "versions": {"status": "current"}, "software_posture": {"status": "current", "summary": "Software is current."},
            "source_freshness": {"telemetry": "current", "profile": "current", "supervisor": "current"},
            "attention_items": [], "attention_count": 0, "last_evaluated_at": NOW,
        },
    }


@pytest.fixture(autouse=True)
def isolated_device_facts_api_state(tmp_path):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE
    from api_fastapi.services.lite_device_fact_store_extension import (
        install_device_fact_store_extension,
        uninstall_device_fact_store_extension,
    )

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    CONTROL_PLANE.initialize()
    install_device_fact_store_extension(CONTROL_PLANE)
    try:
        yield
    finally:
        uninstall_device_fact_store_extension(CONTROL_PLANE)


def _prime_four_surfaces():
    from api_fastapi.routers import lite
    from api_fastapi.services import lite_phase3b_projections as phase3b

    device = _device()
    fleet_payload = {
        "status": "healthy", "summary": "Devices are connected.", "devices": [device], "items": [device],
        "count": 1, "online": 1, "offline": 0, "remote_access": {"ready": True, "status": "ready"},
        "updated_at": NOW, "projection_only": True, "sanitized": True,
    }
    lite.CONTROL_PLANE.prepared_read(
        domain="fleet", key="summary", builder=lambda: fleet_payload,
        projector=lite.CONTROL_PLANE.project_fleet, stale_after_ms=30_000,
        max_stale_ms=30_000, deadline_seconds=6.0,
    )

    facts = device["device_facts"]
    status_payload = {
        "overall": "healthy", "checked_at": NOW,
        "device": {"name": "Pocket Lab Lite Server", "mode": "lite", "resource_profile": "low-power", "device_facts": facts},
        "device_facts": facts, "resource_observations": facts["resources"],
        "summary": {"apps_available": 0, "devices_known": 1, "device_health_attention": 0, "device_health_attention_current": True, "device_health_summary": {"by_status": {"healthy": 1}, "by_severity": {}}, "security_findings": 0, "nats_connected": True, "jetstream_enabled": True, "live_sampler_running": True, "remote_access_ready": True},
        "telemetry": {"status": "healthy", "sampled_at": NOW, "resource_observations": facts["resources"], "memory_total_mb": 4096, "memory_free_mb": 2048, "cpu_usage_percent": 12, "cpu_temp_c": 42, "total_space_mb": 256000, "free_space_mb": 128000},
        "services": [{"name": "Control API", "status": "healthy", "summary": "Ready"}],
        "system_current_state": {}, "projection_only": True, "sanitized": True,
    }
    phase3b.project("system.status", status_payload)
    lite.CONTROL_PLANE.prepared_read(
        domain="system", key="status",
        snapshot_builder=lambda: phase3b.snapshot("system.status"),
        builder=lambda: status_payload,
        projector=lambda payload: phase3b.project("system.status", payload),
        stale_after_ms=30_000, max_stale_ms=30_000, deadline_seconds=6.0,
    )
    return device


def _public_facts_from_health(payload):
    health = payload.get("health") if isinstance(payload.get("health"), dict) else {}
    return payload.get("device_facts") or health.get("device_facts") or {}


def test_four_read_surfaces_share_canonical_resource_semantics_and_provenance():
    _prime_four_surfaces()
    api = raw_client()
    status = api.get("/api/lite/status")
    fleet = api.get("/api/lite/fleet")
    details = api.get("/api/lite/devices/pocket-lab-lite-server")
    health = api.get("/api/lite/devices/pocket-lab-lite-server/health")
    assert [response.status_code for response in (status, fleet, details, health)] == [200, 200, 200, 200]

    status_facts = status.json()["device_facts"]
    fleet_device = next(item for item in fleet.json()["devices"] if item["id"] == "pocket-lab-lite-server")
    detail_device = details.json()["device"]
    health_facts = _public_facts_from_health(health.json())
    facts = [status_facts, fleet_device["device_facts"], detail_device["device_facts"], health_facts]
    for payload in facts:
        memory = payload["resources"]["memory"]
        assert memory["value"]["free_mb"] == 2048
        assert memory["source"] == "server_central_telemetry"
        assert memory["reason_code"] == "collected"
        assert memory["freshness"] == "current"
        assert payload["software"]["node_agent"]["version"] == "2.5.0"


def test_fleet_detail_health_keep_capability_and_runtime_service_parity():
    _prime_four_surfaces()
    api = raw_client()
    fleet_device = api.get("/api/lite/fleet").json()["devices"][0]
    detail_device = api.get("/api/lite/devices/pocket-lab-lite-server").json()["device"]
    health_payload = api.get("/api/lite/devices/pocket-lab-lite-server/health").json()

    expected_caps = [(item["id"], item["status"], item["source"]) for item in fleet_device["capability_states"]]
    assert [(item["id"], item["status"], item["source"]) for item in detail_device["capability_states"]] == expected_caps
    expected_services = [(item["service_id"], item["state"], item["freshness"]) for item in fleet_device["runtime_services"]]
    assert [(item["service_id"], item["state"], item["freshness"]) for item in detail_device["runtime_services"]] == expected_services
    if health_payload.get("capability_states"):
        assert [(item["id"], item["status"], item["source"]) for item in health_payload["capability_states"]] == expected_caps
    if health_payload.get("runtime_services"):
        assert [(item["service_id"], item["state"], item["freshness"]) for item in health_payload["runtime_services"]] == expected_services


def test_four_read_surfaces_are_sanitized_and_do_not_expose_secret_metadata():
    _prime_four_surfaces()
    api = raw_client()
    forbidden_values = (
        "nats" + "://user:", "bear" + "er ", "pass" + "word=",
        "api" + "_key", "/data" + "/data/", "/root" + "/", "pm2_env", "command_args",
    )
    for path in (
        "/api/lite/status", "/api/lite/fleet", "/api/lite/devices/pocket-lab-lite-server",
        "/api/lite/devices/pocket-lab-lite-server/health",
    ):
        response = api.get(path)
        assert response.status_code == 200
        encoded = json.dumps(response.json()).lower()
        for forbidden in forbidden_values:
            assert forbidden not in encoded


def test_read_endpoints_do_not_start_or_execute_runtime_side_effects(monkeypatch):
    _prime_four_surfaces()
    ensure_runtime_path()
    from api_fastapi.services import lite_runtime_services, lite_status

    def forbidden(*args, **kwargs):
        raise AssertionError("prepared GET attempted runtime execution")

    monkeypatch.setattr(lite_runtime_services, "collect_process_state", forbidden)
    monkeypatch.setattr(lite_status, "lite_remote_access_status", forbidden)
    monkeypatch.setattr(lite_status, "_run_remote_access_command", forbidden)

    api = raw_client()
    for path in (
        "/api/lite/status", "/api/lite/fleet", "/api/lite/devices/pocket-lab-lite-server",
        "/api/lite/devices/pocket-lab-lite-server/health",
    ):
        response = api.get(path)
        assert response.status_code == 200
