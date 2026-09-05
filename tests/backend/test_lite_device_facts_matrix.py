from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pocket_lab_test_utils import ensure_runtime_path

NOW_ISO = "2026-09-05T12:00:00Z"
NOW_EPOCH = 1788609600.0


def _modules():
    ensure_runtime_path()
    import resource_telemetry
    from api_fastapi.services import lite_capability_projection, lite_device_facts, lite_runtime_services
    return resource_telemetry, lite_capability_projection, lite_device_facts, lite_runtime_services


def _observation(metric: str, value, *, source="agent_telemetry", at=NOW_ISO, status="available", freshness="current", reason="collected"):
    return {
        "metric": metric,
        "value": value,
        "unit": None,
        "status": status,
        "collection_status": "available" if status == "stale" else status,
        "source": source,
        "observed_at": at,
        "freshness": freshness,
        "reason_code": reason,
        "support_state": "unsupported" if status == "unsupported" else "supported",
        "schema_version": 2,
    }


def test_server_and_secondary_use_same_canonical_resource_semantics():
    _, _, facts, _ = _modules()
    server = facts.normalize_resource_observations({"sampled_at": NOW_ISO, "memory_total_mb": 4096, "memory_free_mb": 2048}, source="server_central_telemetry", now_epoch=NOW_EPOCH)
    secondary = facts.normalize_resource_observations({"sampled_at": NOW_ISO, "memory_total_mb": 4096, "memory_free_mb": 2048}, source="agent_telemetry", now_epoch=NOW_EPOCH)
    assert server["memory"]["value"] == secondary["memory"]["value"]
    assert server["memory"]["source"] == "legacy_telemetry"
    assert secondary["memory"]["source"] == "legacy_telemetry"


def test_meminfo_readable_and_denied_are_independent(monkeypatch):
    telemetry, *_ = _modules()
    monkeypatch.setattr(telemetry, "_read_text", lambda path, limit=65536: ("MemTotal: 4194304 kB\nMemAvailable: 2097152 kB\n", None) if str(path) == "/proc/meminfo" else (None, "not_present"))
    good = telemetry._memory(NOW_ISO)
    assert good["status"] == "available" and good["value"]["free_mb"] == 2048
    monkeypatch.setattr(telemetry, "_read_text", lambda path, limit=65536: (None, "permission_denied"))
    denied = telemetry._memory(NOW_ISO)
    assert denied["status"] == "permission_denied" and denied["value"] is None


def test_loadavg_permission_and_uptime_permission_fail_safely(monkeypatch):
    telemetry, *_ = _modules()
    monkeypatch.setattr(telemetry.os, "getloadavg", lambda: (_ for _ in ()).throw(PermissionError("blocked")))
    assert telemetry._load_average(NOW_ISO)["status"] == "permission_denied"
    monkeypatch.delattr(telemetry.time, "CLOCK_BOOTTIME", raising=False)
    monkeypatch.setattr(telemetry, "_read_text", lambda path, limit=65536: (None, "permission_denied"))
    assert telemetry._uptime(NOW_ISO)["status"] == "permission_denied"


def test_storage_success_and_unavailable(monkeypatch):
    telemetry, *_ = _modules()
    monkeypatch.setattr(telemetry.os, "statvfs", lambda path: SimpleNamespace(f_blocks=1000, f_bavail=400, f_frsize=1024 * 1024))
    assert telemetry._storage(NOW_ISO, Path("/tmp"))["value"] == {"total_mb": 1000, "free_mb": 400}
    monkeypatch.setattr(telemetry.os, "statvfs", lambda path: (_ for _ in ()).throw(OSError("gone")))
    failed = telemetry._storage(NOW_ISO, Path("/tmp"))
    assert failed["status"] == "transient_failure" and failed["value"] is None


@pytest.mark.parametrize("raw,expected_status", [
    ("51000", "available"), ("-273000", "unavailable"), ("-40000", "unavailable"), ("151000", "unavailable"), ("0", "unavailable"),
])
def test_thermal_valid_and_invalid_values(monkeypatch, raw, expected_status):
    telemetry, *_ = _modules()
    monkeypatch.setattr(telemetry.glob, "glob", lambda pattern: ["/tmp/thermal_zone0"])
    values = {"/tmp/thermal_zone0/type": ("cpu-thermal", None), "/tmp/thermal_zone0/temp": (raw, None)}
    monkeypatch.setattr(telemetry, "_read_text", lambda path, limit=65536: values.get(str(path), (None, "not_present")))
    result = telemetry._temperature(NOW_ISO)
    assert result["status"] == expected_status
    if expected_status == "available": assert result["value"]["celsius"] == 51.0
    else: assert result["value"] is None


def test_thermal_unreadable_and_absent(monkeypatch):
    telemetry, *_ = _modules()
    monkeypatch.setattr(telemetry.glob, "glob", lambda pattern: ["/tmp/thermal_zone0"])
    monkeypatch.setattr(telemetry, "_read_text", lambda path, limit=65536: (None, "permission_denied"))
    assert telemetry._temperature(NOW_ISO)["status"] == "permission_denied"
    monkeypatch.setattr(telemetry.glob, "glob", lambda pattern: [])
    assert telemetry._temperature(NOW_ISO)["status"] == "unsupported"


def test_one_provider_failure_does_not_invalidate_other_metrics(monkeypatch):
    telemetry, *_ = _modules()
    providers = (
        telemetry.ResourceProvider("memory", "test_memory", lambda at: _observation("memory", {"total_mb": 100, "free_mb": 50, "used_mb": 50}), 100),
        telemetry.ResourceProvider("storage", "test_storage", lambda at, root: (_ for _ in ()).throw(OSError("denied")), 100),
        telemetry.ResourceProvider("cpu_usage", "test_cpu", lambda at: _observation("cpu_usage", {"usage_percent": 0}), 100),
    )
    monkeypatch.setattr(telemetry, "RESOURCE_PROVIDERS", providers)
    sample = telemetry.collect_resource_telemetry("/tmp")
    assert sample["resource_observations"]["memory"]["status"] == "available"
    assert sample["resource_observations"]["storage"]["status"] == "transient_failure"
    assert sample["resource_observations"]["cpu_usage"]["value"]["usage_percent"] == 0


def test_provider_timeout_becomes_transient_failure(monkeypatch):
    telemetry, *_ = _modules()
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr(telemetry.time, "monotonic", lambda: next(ticks))
    provider = telemetry.ResourceProvider("memory", "bounded_test", lambda at: _observation("memory", {"total_mb": 10, "free_mb": 5, "used_mb": 5}), 10.0)
    result = telemetry._run_provider(provider, NOW_ISO)
    assert result["status"] == "transient_failure" and result["reason_code"] == "provider_timeout"


def test_malformed_numeric_stale_and_conflicting_observations():
    _, _, facts, _ = _modules()
    malformed = facts.normalize_resource_observations({"resource_observations": {"cpu_usage": _observation("cpu_usage", {"usage_percent": "not-a-number"})}}, now_epoch=NOW_EPOCH)
    assert malformed["cpu_usage"]["status"] == "unavailable"
    stale = facts.normalize_resource_observations({"resource_observations": {"memory": _observation("memory", {"total_mb": 100, "free_mb": 25, "used_mb": 75}, at="2026-09-05T11:00:00Z")}}, now_epoch=NOW_EPOCH)
    assert stale["memory"]["status"] == "stale"
    chosen = facts.reconcile_resource_observations(
        {"memory": _observation("memory", {"total_mb": 100, "free_mb": 25, "used_mb": 75}, at="2026-09-05T11:00:00Z", freshness="stale", status="stale")},
        {"memory": _observation("memory", {"total_mb": 100, "free_mb": 60, "used_mb": 40}, source="server_central_telemetry")}, now_epoch=NOW_EPOCH)
    assert chosen["memory"]["value"]["free_mb"] == 60


def test_fresh_canonical_telemetry_overrides_stale_health_and_keeps_independent_freshness():
    _, _, facts, _ = _modules()
    device = {"id": "edge", "resource_observations": {"memory": _observation("memory", {"total_mb": 100, "free_mb": 10, "used_mb": 90}, source="system_health", at="2026-09-05T10:00:00Z", freshness="stale", status="stale")}, "system_profile": {"agent_version": "1.0", "collected_at": "2026-09-03T12:00:00Z", "freshness": "stale"}}
    telemetry = {"sampled_at": NOW_ISO, "resource_observations": {"memory": _observation("memory", {"total_mb": 100, "free_mb": 70, "used_mb": 30}, source="server_central_telemetry")}}
    result = facts.build_device_facts(device, telemetry=telemetry, telemetry_source="server_central_telemetry", now_epoch=NOW_EPOCH)
    assert result["resources"]["memory"]["value"]["free_mb"] == 70 and result["resources"]["memory"]["freshness"] == "current"
    assert result["software"]["node_agent"]["freshness"] == "stale"


def test_fresh_heartbeat_does_not_make_saved_resources_current():
    _, _, facts, _ = _modules()
    result = facts.build_device_facts({"id":"edge","last_heartbeat_at":NOW_ISO,"resource_observations":{"memory":_observation("memory",{"total_mb":100,"free_mb":50,"used_mb":50},at="2026-09-05T10:00:00Z",freshness="stale",status="stale")}}, now_epoch=NOW_EPOCH)
    assert result["resources"]["memory"]["freshness"] == "stale"


def test_old_schema_missing_optional_and_unknown_future_fields_are_compatible():
    _, _, facts, _ = _modules()
    old = facts.normalize_resource_observations({"sampled_at": NOW_ISO, "memoryTotalMB": 4096, "memoryFreeMB": 1024, "future_field": {"anything": True}}, now_epoch=NOW_EPOCH)
    assert old["memory"]["value"]["free_mb"] == 1024 and "future_field" not in old
    assert facts.normalize_resource_observations({"sampled_at": NOW_ISO, "resource_observations": {}}, now_epoch=NOW_EPOCH) == {}


@pytest.mark.parametrize("status", ["advertised", "verification_pending", "verified", "unavailable", "unsupported", "stale", "blocked", "not_applicable"])
def test_capability_record_supports_full_lifecycle(status):
    _, capability, _, _ = _modules()
    item = capability._capability("future", "Future", category="custom", verification_strategy="test", advertised=status not in {"not_applicable"}, advertised_at=NOW_ISO, evidence_present=True, runtime_ready=True if status == "verified" else None, evaluated_at=NOW_ISO, source="test", explicit_status=status if status != "advertised" else "advertised", now_epoch=NOW_EPOCH)
    assert item["status"] == status and item["verified_at"] == (NOW_ISO if status == "verified" else None) and item["revision"] > 0


def test_advertised_only_is_verification_pending_and_unknown_future_capability_is_safe():
    _, capability, _, _ = _modules()
    states = capability.verified_capabilities({"id":"edge","connection":"online","advertised_capabilities":["host_apps","future_accelerator"],"last_capabilities_at":NOW_ISO}, now_epoch=NOW_EPOCH)
    host = next(item for item in states if item["id"] == "host_apps"); future = next(item for item in states if item["id"] == "future_accelerator")
    assert host["status"] == "verification_pending" and host["verified_at"] is None
    assert future["category"] == "custom" and future["status"] == "verification_pending"


def test_capability_authoritative_adapters_verify_without_frontend_role_guessing():
    _, capability, _, _ = _modules()
    device = {"id":"server","role":"server_host","connection":"online","is_current":True,"last_capabilities_at":NOW_ISO,"control_plane_runtime_ready":True,"control_plane_runtime_checked_at":NOW_ISO,"command_delivery_ready":True,"command_delivery_checked_at":NOW_ISO,"supervisor_status":"healthy","agent_process_status":"online","last_supervisor_heartbeat_at":NOW_ISO,"storage":{"ready":False,"supported":True,"backup_target_ready":False,"restore_target_ready":False}}
    remote = {"ready":True,"nats_reachable":True,"running":True,"checked_at":NOW_ISO}
    states = {item["id"]:item for item in capability.verified_capabilities(device, remote_access=remote, hosted_apps=[{"status":"running"}], now_epoch=NOW_EPOCH)}
    assert states["serve_control_plane"]["status"] == "verified" and states["host_apps"]["status"] == "verified" and states["receive_commands"]["status"] == "verified" and states["supervisor_recovery"]["status"] == "verified"
    assert states["remote_access"]["status"] == "verified" and states["remote_access"]["advertised"] is False
    assert states["provide_storage"]["status"] != "verified"


def test_capability_expiry_and_stale_evidence_are_explicit():
    _, capability, _, _ = _modules()
    states = capability.verified_capabilities({"id":"edge","connection":"online","advertised_capabilities":["supervisor_recovery"],"last_capabilities_at":"2026-09-05T10:00:00Z","last_supervisor_heartbeat_at":"2026-09-05T10:00:00Z","supervisor_status":"healthy","agent_process_status":"online"}, now_epoch=NOW_EPOCH)
    item = next(row for row in states if row["id"] == "supervisor_recovery")
    assert item["status"] == "stale" and item["expires_at"] is not None and item["verified_at"] is None


def test_dynamic_unknown_stale_and_disappearing_services():
    _, _, _, services = _modules()
    fresh = services.runtime_services_from_snapshot({"updated_at":NOW_ISO,"items":[{"name":"future-sidecar","category":"future","status":"online"}]}, now_epoch=NOW_EPOCH)
    assert fresh[0]["service_id"] == "future-sidecar" and fresh[0]["category"] == "service"
    stale = services.runtime_services_from_snapshot({"updated_at":"2026-09-05T10:00:00Z","items":[{"name":"alpha","status":"online"}]}, now_epoch=NOW_EPOCH)
    assert stale[0]["freshness"] == "stale" and services.runtime_services_from_snapshot({"updated_at":NOW_ISO,"items":[]}, now_epoch=NOW_EPOCH) == []


def test_pm2_snapshot_does_not_expose_environment_commands_or_secret_values(monkeypatch):
    _, _, _, services = _modules()
    monkeypatch.setattr(services.shutil, "which", lambda name: "/usr/bin/pm2")
    row = {"name":"alpha","pm2_env":{"status":"online","POCKETLAB_PROCESS_ROLE":"worker","POCKETLAB_NATS_URL":"nats://user:secret@example:4222","TOKEN":"secret"},"args":["--token","secret"],"pm_exec_path":"/data/data/private/run.py"}
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps([row])))
    payload = services.collect_process_state(); encoded = json.dumps(payload).lower()
    assert payload["items"][0]["service_id"] == "alpha" and "nats://" not in encoded and "secret" not in encoded and "/data/data/" not in encoded and "args" not in encoded and "pm_exec_path" not in encoded and "pm2_env" not in encoded


def test_software_version_sources_conflicts_and_staleness():
    _, _, facts, _ = _modules()
    result = facts.build_device_facts({"id":"edge","agent_version":"2.5.0","agent_version_source":"runtime_heartbeat","agent_version_freshness":"fresh","last_heartbeat_at":NOW_ISO,"supervisor_version":"2.6.0","supervisor_status_source":"supervisor_evidence","supervisor_status_freshness":"fresh","last_supervisor_heartbeat_at":NOW_ISO,"system_profile":{"agent_version":"1.0.0","supervisor_version":"1.0.0","collected_at":"2026-09-04T12:00:00Z","freshness":"stale"}}, now_epoch=NOW_EPOCH)
    assert result["software"]["node_agent"]["version"] == "2.5.0" and result["software"]["supervisor"]["version"] == "2.6.0"
    stale = facts.build_device_facts({"id":"old","system_profile":{"agent_version":"1.0.0","collected_at":"2026-09-01T12:00:00Z","freshness":"stale"}}, now_epoch=NOW_EPOCH)
    assert stale["software"]["node_agent"]["freshness"] == "stale"
    assert facts.build_device_facts({"id":"old-schema"}, now_epoch=NOW_EPOCH)["software"]["node_agent"]["status"] == "verification_pending"


def test_collector_and_fact_errors_do_not_leak_private_paths_or_secrets():
    _, _, facts, services = _modules()
    normalized = facts.normalize_resource_observations({"resource_observations":{"memory":{**_observation("memory",{"total_mb":100,"free_mb":50,"used_mb":50}),"source":"nats://user:pass@example","reason_code":"password=secret"}}}, now_epoch=NOW_EPOCH)
    encoded = json.dumps(normalized).lower(); assert "nats://" not in encoded and "password" not in encoded and "secret" not in encoded
    service = services.sanitize_runtime_service({"name":"safe","label":"/root/private","source":"Bearer secret","status":"online"}, reported_at=NOW_ISO, now_epoch=NOW_EPOCH)
    encoded = json.dumps(service).lower(); assert "/root/" not in encoded and "bearer" not in encoded and "secret" not in encoded
