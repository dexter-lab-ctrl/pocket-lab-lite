from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir

NOW = "2026-09-07T18:17:00Z"
NEXT = "2026-09-07T18:17:30Z"
LEGACY_EVALUATED_AT = "2026-09-06T18:29:14Z"
NOW_EPOCH = datetime(2026, 9, 7, 18, 17, tzinfo=timezone.utc).timestamp()


def _server_phone_telemetry(sampled_at: str = NOW) -> dict:
    return {
        "memory_total_mb": 7072,
        "memory_free_mb": 2176,
        "memory_usage_mb": 4896,
        "total_space_mb": 228219,
        "free_space_mb": 135725,
        "pocketlab_workload_cpu_percent": 3.5,
        "pocketlab_workload_process_count": 4,
        "cpu_temp_c": 37.8,
        "sampled_at": sampled_at,
        "timestamp": sampled_at,
    }


def _server_phone_device(at: str = NOW) -> dict:
    return {
        "id": "pocket-lab-lite-server",
        "node_id": "pocket-lab-lite-server",
        "name": "Pocket Lab Lite Server",
        "role": "server_host",
        "status": "healthy",
        "connection": "online",
        "agent_status": "healthy",
        "agent_process_status": "online",
        "supervisor_status": "healthy",
        "is_current": True,
        "protected_server_host": True,
        "last_seen_at": at,
        "last_heartbeat_at": at,
        "last_supervisor_heartbeat_at": at,
        "last_seen_state": {
            "last_seen_at": at,
            "last_heartbeat_at": at,
            "last_telemetry_at": at,
            "last_system_profile_at": at,
            "last_supervisor_heartbeat_at": at,
            "last_nats_connected_at": at,
        },
        "system_profile": {
            "schema_version": 1,
            "technical_model": "Android Server Phone",
            "architecture": "arm64",
            "architecture_family": "arm64",
            "os_name": "Android/Termux",
            "agent_version": "2.5.0-lite-trust-capability-awareness",
            "supervisor_version": "1.2.2-opa-readiness-proof",
            "collected_at": at,
            "freshness": "current",
        },
        "dependencies": {
            "command_delivery_status": "deliverable",
            "remote_access_status": "healthy",
            "recovery_available": True,
            "hosted_apps": [],
            "backup_set_count": 0,
        },
        "capability_schema_version": 1,
    }


def _legacy_health() -> dict:
    return {
        "last_evaluated_at": LEGACY_EVALUATED_AT,
        "health_revision": "9c1a13af91501bf0c8e6",
        "source_revision": 0,
        "resources": {
            "memory": {
                "status": "unknown",
                "available_mb": None,
                "available_percent": None,
                "summary": "Memory information is unavailable.",
            },
            "storage": {
                "status": "unknown",
                "available_mb": None,
                "available_percent": None,
                "summary": "Storage information is unavailable.",
            },
            "load": {
                "status": "unknown",
                "usage_percent": None,
                "summary": "System load is unavailable.",
            },
            "temperature": {
                "status": "unknown",
                "celsius": None,
                "summary": "Temperature is unavailable.",
            },
        },
        "source_freshness": {},
        "attention_items": [],
    }


def _capture_attribute(target, name: str):
    """Capture both descriptor value and whether an instance/module owned it."""
    namespace = vars(target)
    return name in namespace, namespace.get(name), getattr(target, name, None)


def _restore_attribute(target, name: str, snapshot) -> None:
    owned, owned_value, resolved_value = snapshot
    if owned:
        setattr(target, name, owned_value)
        return
    if name in vars(target):
        delattr(target, name)
    # Module globals are always owned. The fallback is only needed for unusual
    # proxy-like test objects where deletion cannot reveal the original value.
    if getattr(target, name, None) is None and resolved_value is not None:
        setattr(target, name, resolved_value)


@pytest.fixture(autouse=True)
def isolated_runtime_state(tmp_path):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services import (
        fleet_registry,
        lite_device_health,
        lite_phase3b_projections as phase3b,
        lite_status,
    )
    from api_fastapi.services.live_status import LIVE_STATUS
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    state = isolated_state_dir(tmp_path)
    original_settings = deps.core.SETTINGS
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    CONTROL_PLANE.initialize()

    # Runtime-extension installers intentionally mutate shared module/instance
    # callbacks. Snapshot every attribute touched by these tests so one test file
    # cannot change the evaluator contract seen by later unit tests in the same
    # pytest process.
    snapshots = [
        (lite_device_health, "evaluate_device_health", _capture_attribute(lite_device_health, "evaluate_device_health")),
        (lite_device_health, "_resource_assessment", _capture_attribute(lite_device_health, "_resource_assessment")),
        (lite_device_health, "_pocketlab_device_facts_health_extension_v3", _capture_attribute(lite_device_health, "_pocketlab_device_facts_health_extension_v3")),
        (lite_status, "_server_host_device", _capture_attribute(lite_status, "_server_host_device")),
        (lite_status, "_pocketlab_server_health_signals_v2", _capture_attribute(lite_status, "_pocketlab_server_health_signals_v2")),
        (lite_status, "_lite_telemetry", _capture_attribute(lite_status, "_lite_telemetry")),
        (lite_status, "_build_lite_status_from_inputs", _capture_attribute(lite_status, "_build_lite_status_from_inputs")),
        (lite_status, "default_lite_status_state", _capture_attribute(lite_status, "default_lite_status_state")),
        (lite_status, "_pocketlab_device_facts_status_extension_v2", _capture_attribute(lite_status, "_pocketlab_device_facts_status_extension_v2")),
        (phase3b, "status_source_revision", _capture_attribute(phase3b, "status_source_revision")),
        (phase3b, "builder_for", _capture_attribute(phase3b, "builder_for")),
        (phase3b, "source_revision_for", _capture_attribute(phase3b, "source_revision_for")),
        (phase3b, "_pocketlab_device_facts_source_revision_v2", _capture_attribute(phase3b, "_pocketlab_device_facts_source_revision_v2")),
        (fleet_registry, "fleet_source_revision", _capture_attribute(fleet_registry, "fleet_source_revision")),
        (LIVE_STATUS, "sample_telemetry", _capture_attribute(LIVE_STATUS, "sample_telemetry")),
        (LIVE_STATUS, "_pocketlab_device_facts_telemetry_invalidation_v2", _capture_attribute(LIVE_STATUS, "_pocketlab_device_facts_telemetry_invalidation_v2")),
    ]
    try:
        yield
    finally:
        for target, name, snapshot in reversed(snapshots):
            _restore_attribute(target, name, snapshot)
        deps.core.SETTINGS = original_settings


def test_live_server_phone_facts_rebuild_legacy_unknown_health():
    ensure_runtime_path()
    from api_fastapi.services import lite_device_health, lite_device_runtime_extensions

    lite_device_runtime_extensions.install_health_projection_extension()
    health = lite_device_health.evaluate_device_health(
        _server_phone_device(),
        signals={
            "telemetry": _server_phone_telemetry(),
            "agent_version": "2.5.0-lite-trust-capability-awareness",
            "supervisor_version": "1.2.2-opa-readiness-proof",
            "capability_schema_version": 1,
        },
        previous=_legacy_health(),
        now_epoch=NOW_EPOCH,
    )

    assert health["source_revision"] > 0
    assert health["health_input_contract_version"] == 2
    assert health["last_evaluated_at"] != LEGACY_EVALUATED_AT

    resources = health["resources"]
    assert resources["memory"]["status"] == "normal"
    assert resources["memory"]["available_mb"] == 2176
    assert resources["memory"]["summary"] == "Memory is available."
    assert resources["storage"]["status"] == "normal"
    assert resources["storage"]["available_mb"] == 135725
    assert resources["load"]["status"] == "normal"
    assert resources["load"]["usage_percent"] == 3.5
    assert resources["load"]["process_count"] == 4
    assert resources["load"]["resource_metric"] == "pocketlab_workload_cpu"
    assert resources["load"]["summary"] == "Pocket Lab workload CPU is normal."
    assert resources["temperature"]["status"] == "normal"
    assert resources["temperature"]["celsius"] == 37.8

    facts = health["device_facts"]
    assert facts["resources"]["memory"]["value"]["total_mb"] == 7072
    assert facts["resources"]["storage"]["value"]["total_mb"] == 228219
    assert facts["resources"]["pocketlab_workload_cpu"]["value"] == {
        "usage_percent": 3.5,
        "process_count": 4,
    }
    assert facts["resources"]["temperature"]["value"]["celsius"] == 37.8


def test_observation_revision_advances_without_false_health_transition():
    ensure_runtime_path()
    from api_fastapi.services import lite_device_health, lite_device_runtime_extensions

    lite_device_runtime_extensions.install_health_projection_extension()
    first = lite_device_health.evaluate_device_health(
        _server_phone_device(),
        signals={"telemetry": _server_phone_telemetry(), "capability_schema_version": 1},
        previous=_legacy_health(),
        now_epoch=NOW_EPOCH,
    )
    second = lite_device_health.evaluate_device_health(
        _server_phone_device(NEXT),
        signals={"telemetry": _server_phone_telemetry(NEXT), "capability_schema_version": 1},
        previous=first,
        now_epoch=NOW_EPOCH + 30,
    )

    assert first["source_revision"] > 0
    assert second["source_revision"] > 0
    assert second["source_revision"] != first["source_revision"]
    assert second["health_revision"] == first["health_revision"]
    assert second["last_evaluated_at"] == first["last_evaluated_at"]
    assert second["resources"]["memory"]["status"] == "normal"
    assert second["resources"]["load"]["summary"] == "Pocket Lab workload CPU is normal."


def test_status_builder_projects_live_equivalent_canonical_server_facts(monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services import lite_device_runtime_extensions, lite_status
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    lite_device_runtime_extensions.install_status_projection_extension()
    monkeypatch.setattr(lite_status, "_mysql_socket_available", lambda: None)
    monkeypatch.setattr(lite_status.lite_catalog_service, "catalog_apps_count", lambda: 1)
    monkeypatch.setattr(
        CONTROL_PLANE,
        "fleet_health_summary",
        lambda: {
            "status": "ready",
            "device_count": 1,
            "attention_count": 0,
            "by_status": {"healthy": 1},
            "by_severity": {"none": 1},
            "attention_by_category": {},
            "sanitized": True,
        },
    )
    monkeypatch.setattr(deps.core, "build_opa_evaluations", lambda: [])

    payload = lite_status._build_lite_status_from_inputs(
        checked_at=NOW,
        engine={"status": "healthy", "services": {}},
        bus={"connected": True, "jetstream_enabled": True},
        live={"running": True},
        remote_access={"status": "healthy", "ready": True, "summary": "Remote access is ready."},
        telemetry=_server_phone_telemetry(),
        fleet={"status": "healthy"},
        fleet_nodes=[{"id": "pocket-lab-lite-server"}],
        current_state={},
    )

    assert payload["device"]["id"] == "pocket-lab-lite-server"
    assert payload["device"]["role"] == "server_host"
    assert payload["device_facts"]["resources"]["memory"]["value"]["total_mb"] == 7072
    assert payload["device_facts"]["resources"]["storage"]["value"]["total_mb"] == 228219
    assert payload["resource_observations"]["pocketlab_workload_cpu"]["value"]["usage_percent"] == 3.5
    assert payload["telemetry"]["pocketlab_workload_cpu_percent"] == 3.5
    assert "cpu_usage_percent" not in payload["telemetry"] or payload["telemetry"]["cpu_usage_percent"] is None


def test_status_callbacks_are_late_bound_and_dirty_generation_changes_revision(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import (
        lite_device_runtime_extensions,
        lite_phase3b_projections as phase3b,
        lite_status,
    )

    lite_device_runtime_extensions.install_source_revision_extensions()

    builder = phase3b.builder_for("system.status")
    source = phase3b.source_revision_for("system.status")
    with monkeypatch.context() as patch:
        patch.setattr(lite_status, "build_lite_status_projection", lambda: {"sentinel": "late-bound"})
        assert builder() == {"sentinel": "late-bound"}
        patch.setattr(phase3b, "status_source_revision", lambda: 4242)
        assert source() == 4242

    first_generation = {"value": 7}
    monkeypatch.setattr(
        lite_device_runtime_extensions,
        "_projection_dirty_generation",
        lambda domain: first_generation["value"] if domain == "system.status" else 0,
    )
    first = phase3b.status_source_revision()
    first_generation["value"] = 8
    second = phase3b.status_source_revision()
    assert first != second


def test_worker_projection_registration_installs_extensions_before_job_capture(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_core_projections, lite_device_runtime_extensions

    events: list[str] = []
    monkeypatch.setattr(
        lite_device_runtime_extensions,
        "install_runtime_extensions",
        lambda: events.append("install"),
    )

    def register_job(**kwargs):
        events.append(f"register:{kwargs['domain']}.{kwargs['key']}")
        return True

    monkeypatch.setattr(lite_core_projections, "_register_job", register_job)
    result = lite_core_projections.register_jobs()

    assert result["fleet"] is True
    assert events[0] == "install"
    assert any(event == "register:fleet.summary" for event in events[1:])