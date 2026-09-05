from __future__ import annotations

from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


NOW_EPOCH = 1788609600.0


def _services():
    ensure_runtime_path()
    from api_fastapi.services import lite_capability_projection, lite_device_facts, lite_device_health
    return lite_capability_projection, lite_device_facts, lite_device_health


def test_resource_facts_preserve_valid_zero_cpu_without_converting_null_to_zero():
    _, facts, _ = _services()
    normalized = facts.normalize_resource_observations({
        "sampled_at": "2026-09-05T12:00:00Z",
        "cpu_usage_percent": 0,
        "memory_total_mb": None,
        "memory_free_mb": None,
    }, now_epoch=NOW_EPOCH)
    assert normalized["cpu_usage"]["value"]["usage_percent"] == 0
    assert "memory" not in normalized


def test_resource_facts_keep_unsupported_temperature_distinct_from_missing():
    _, facts, _ = _services()
    normalized = facts.normalize_resource_observations({
        "sampled_at": "2026-09-05T12:00:00Z",
        "resource_observations": {
            "temperature": {
                "metric": "temperature",
                "value": None,
                "status": "unsupported",
                "source": "sysfs_thermal",
                "observed_at": "2026-09-05T12:00:00Z",
                "reason_code": "no_semantic_cpu_sensor",
                "support_state": "unsupported",
                "schema_version": 1,
            }
        },
    }, now_epoch=NOW_EPOCH)
    assert normalized["temperature"]["status"] == "unsupported"
    assert normalized["temperature"]["reason_code"] == "no_semantic_cpu_sensor"
    assert normalized["temperature"]["value"] is None


def test_freshest_resource_observation_wins_per_field():
    _, facts, _ = _services()
    older = {"memory": {"metric": "memory", "status": "available", "collection_status": "available", "freshness": "current", "source": "agent_telemetry", "observed_at": "2026-09-05T11:59:00Z", "value": {"total_mb": 1000, "free_mb": 250, "used_mb": 750}}}
    newer = {"memory": {"metric": "memory", "status": "available", "collection_status": "available", "freshness": "current", "source": "server_central_telemetry", "observed_at": "2026-09-05T12:00:00Z", "value": {"total_mb": 1000, "free_mb": 500, "used_mb": 500}}}
    chosen = facts.reconcile_resource_observations(older, newer, now_epoch=NOW_EPOCH)
    assert chosen["memory"]["value"]["free_mb"] == 500
    assert chosen["memory"]["source"] == "server_central_telemetry"


def test_health_resource_projection_keeps_observation_reason_and_source():
    _, _, health = _services()
    from api_fastapi.services.lite_device_runtime_extensions import _overlay_resource_metadata

    device = {
        "id": "edge-phone",
        "connection": "online",
        "last_seen_at": "2026-09-05T12:00:00Z",
        "last_seen_state": {"last_heartbeat_at": "2026-09-05T12:00:00Z", "last_telemetry_at": "2026-09-05T12:00:00Z"},
    }
    signals = {
        "telemetry": {
            "sampled_at": "2026-09-05T12:00:00Z",
            "memory_total_mb": 4096,
            "memory_free_mb": 2048,
        },
        "resource_observations": {
            "memory": {
                "status": "available", "collection_status": "available", "freshness": "current",
                "source": "agent_telemetry", "observed_at": "2026-09-05T12:00:00Z",
                "reason_code": "proc_meminfo", "support_state": "supported",
            }
        },
    }
    result = health.evaluate_device_health(device, signals=signals, now_epoch=NOW_EPOCH)
    resources = _overlay_resource_metadata(result["resources"], signals["resource_observations"])
    assert resources["memory"]["source"] == "agent_telemetry"
    assert resources["memory"]["reason_code"] == "proc_meminfo"
    assert resources["memory"]["observation_status"] == "available"


def test_capability_verified_at_only_exists_for_verified_evidence():
    awareness, _, _ = _services()
    pending = awareness.verified_capabilities({
        "id": "edge-phone", "role": "compute", "connection": "online",
        "advertised_capabilities": ["host_apps"], "last_capabilities_at": "2026-09-05T12:00:00Z",
    }, hosted_apps=[], now_epoch=NOW_EPOCH)
    host_apps = next(item for item in pending if item["id"] == "host_apps")
    assert host_apps["status"] == "verification_pending"
    assert host_apps["verified_at"] is None

    verified = awareness.verified_capabilities({
        "id": "server", "role": "server_host", "connection": "online", "is_current": True,
        "advertised_capabilities": ["host_apps"], "last_capabilities_at": "2026-09-05T12:00:00Z",
    }, hosted_apps=[{"status": "running"}], now_epoch=NOW_EPOCH)
    host_apps = next(item for item in verified if item["id"] == "host_apps")
    assert host_apps["status"] == "verified"
    assert host_apps["verified_at"] == "2026-09-05T12:00:00Z"


def test_unknown_advertised_capability_is_safe_and_pending():
    awareness, _, _ = _services()
    states = awareness.verified_capabilities({
        "id": "future-phone", "role": "compute", "connection": "online",
        "advertised_capabilities": ["future_accelerator"], "last_capabilities_at": "2026-09-05T12:00:00Z",
    }, now_epoch=NOW_EPOCH)
    future = next(item for item in states if item["id"] == "future_accelerator")
    assert future["status"] == "verification_pending"
    assert future["verified_at"] is None
    assert future["category"] == "custom"


def test_temperature_provider_rejects_sentinel_and_non_cpu_sensor_classes(monkeypatch):
    ensure_runtime_path()
    from core import resource_telemetry

    zones = [Path('/tmp/thermal_zone0'), Path('/tmp/thermal_zone1'), Path('/tmp/thermal_zone2')]
    monkeypatch.setattr(resource_telemetry.glob, 'glob', lambda pattern: [str(zone) for zone in zones])

    values = {
        '/tmp/thermal_zone0/type': ('battery', None),
        '/tmp/thermal_zone0/temp': ('42000', None),
        '/tmp/thermal_zone1/type': ('soc-thermal', None),
        '/tmp/thermal_zone1/temp': ('-273000', None),
        '/tmp/thermal_zone2/type': ('cpu-thermal', None),
        '/tmp/thermal_zone2/temp': ('51000', None),
    }
    monkeypatch.setattr(resource_telemetry, '_read_text', lambda path, limit=65536: values.get(str(path), (None, 'not_present')))
    result = resource_telemetry._temperature('2026-09-05T12:00:00Z')
    assert result['status'] == 'available'
    assert result['value']['celsius'] == 51.0
    assert 'cpu-thermal' in result['source']


def test_storage_provider_reports_permission_denied_without_fake_zero(monkeypatch):
    ensure_runtime_path()
    from core import resource_telemetry

    def denied(_path):
        raise PermissionError('denied')

    monkeypatch.setattr(resource_telemetry.os, 'statvfs', denied)
    result = resource_telemetry._storage('2026-09-05T12:00:00Z', Path('/tmp'))
    assert result['status'] == 'permission_denied'
    assert result['value'] is None


def test_dynamic_server_runtime_services_are_sanitized_and_not_fixed_to_two():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_recovery import guarded_recovery_contract

    result = guarded_recovery_contract({
        'id': 'server', 'role': 'server_host', 'connection': 'online', 'is_current': True,
        '_runtime_service_evidence': [
            {'service_id': 'pocket_api', 'label': 'Control API', 'manager': 'pm2', 'state': 'online', 'freshness': 'current'},
            {'service_id': 'pocket_worker', 'label': 'Worker', 'manager': 'pm2', 'state': 'online', 'freshness': 'current'},
            {'service_id': 'pocket_nats', 'label': 'NATS', 'manager': 'pm2', 'state': 'online', 'freshness': 'current'},
        ],
    })
    assert [item['service_id'] for item in result['runtime_services']] == ['pocket_api', 'pocket_worker', 'pocket_nats']
    assert all(item['restart_supported'] is False for item in result['runtime_services'])


def test_software_fact_prefers_newer_authoritative_supervisor_evidence():
    _, facts, _ = _services()
    result = facts.build_device_facts({
        'id': 'edge-phone',
        'supervisor_version': '2.0.0',
        'supervisor_status_source': 'sqlite_supervisor_evidence',
        'supervisor_status_freshness': 'fresh',
        'last_supervisor_heartbeat_at': '2026-09-05T12:00:00Z',
        'system_profile': {
            'supervisor_version': '1.9.0', 'freshness': 'current',
            'collected_at': '2026-09-05T11:00:00Z',
        },
    }, now_epoch=NOW_EPOCH)
    supervisor = result['software']['supervisor']
    assert supervisor['version'] == '2.0.0'
    assert supervisor['source'] == 'sqlite_supervisor_evidence'
