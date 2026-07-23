from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _import_profile_module():
    ensure_runtime_path()
    runtime = Path(__file__).resolve().parents[2] / "pocket-lab-final-structure" / "runtime"
    agents = runtime / "agents"
    if str(agents) not in sys.path:
        sys.path.insert(0, str(agents))
    import lite_system_profile

    return lite_system_profile


def _configure_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    database = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    from api_fastapi.db.connection import reset_sqlite_path_cache

    reset_sqlite_path_cache()
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    return ControlPlaneProjectionStore()


def _profile_payload(*, collected_at: str = "2026-07-23T08:00:00Z", model: str = "SM-S911B", uptime: int = 7200):
    return {
        "status": "healthy",
        "devices": [
            {
                "id": "phone-two",
                "name": "Phone Two",
                "role": "compute",
                "status": "active",
                "connection": "online",
                "agent_status": "online",
                "supervisor_status": "healthy",
                "agent_process_status": "online",
                "last_seen_at": collected_at,
                "supervisor_version": "1.2.0",
                "system_profile": {
                    "schema_version": 1,
                    "os_family": "android",
                    "os_name": "Android",
                    "os_version": "14",
                    "android_api_level": 34,
                    "security_patch": "2026-07-01",
                    "manufacturer": "samsung",
                    "technical_model": model,
                    "device_codename": "dm1q",
                    "architecture": "aarch64",
                    "android_abi": "arm64-v8a",
                    "kernel": "5.15.123-android13",
                    "runtime_type": "termux",
                    "termux_version": "0.118.3",
                    "python_version": "3.12.9",
                    "agent_version": "2.1.0",
                    "profile_fingerprint": "a" * 64,
                    "collection_status": "current",
                    "collected_at": collected_at,
                },
                "system_health": {
                    "uptime_status": "available",
                    "uptime_seconds": uptime,
                    "load_average_1m": 0.12,
                    "load_average_5m": 0.18,
                    "load_average_15m": 0.22,
                    "load_status": "normal",
                    "collected_at": collected_at,
                },
            }
        ],
        "remote_access": {"ready": True, "status": "healthy"},
        "updated_at": collected_at,
    }


def test_allowlisted_profile_collection_and_bounded_health():
    module = _import_profile_module()
    values = {
        ("getprop", "ro.build.version.release"): "14",
        ("getprop", "ro.build.version.sdk"): "34",
        ("getprop", "ro.build.version.security_patch"): "2026-07-01",
        ("getprop", "ro.product.manufacturer"): "samsung",
        ("getprop", "ro.product.model"): "SM-S911B",
        ("getprop", "ro.product.device"): "dm1q",
        ("getprop", "ro.product.cpu.abi"): "arm64-v8a",
        ("uname", "-m"): "aarch64",
        ("uname", "-r"): "5.15.123-android13",
        ("uptime",): "10:20:00 up 2 days,  4:12,  load average: 0.12, 0.18, 0.22",
    }
    calls = []

    def runner(command):
        calls.append(tuple(command))
        return {"status": "available", "value": values[tuple(command)], "failure_code": ""}

    profile = module.collect_system_profile(
        agent_version="2.1.0",
        command_runner=runner,
        environ={"PREFIX": "/data/data/com.termux/files/usr", "TERMUX_VERSION": "0.118.3"},
    )
    health = module.collect_system_health(command_runner=runner)

    assert profile["os_name"] == "Android"
    assert profile["technical_model"] == "SM-S911B"
    assert profile["device_codename"] == "dm1q"
    assert profile["android_api_level"] == 34
    assert profile["runtime_type"] == "termux"
    assert len(profile["profile_fingerprint"]) == 64
    assert health["uptime_seconds"] == 2 * 86400 + 4 * 3600 + 12 * 60
    assert health["load_average_15m"] == 0.22
    assert health["load_status"] in {"normal", "elevated", "high"}
    assert all(call[0] in {"getprop", "uname", "uptime"} for call in calls)
    assert ("getprop",) not in calls


def test_bounded_command_timeout_empty_oversized_and_sanitized(monkeypatch):
    module = _import_profile_module()

    def timeout(*_args, **_kwargs):
        raise module.subprocess.TimeoutExpired(cmd=("getprop", "ro.product.model"), timeout=1)

    monkeypatch.setattr(module.subprocess, "run", timeout)
    assert module.run_bounded_command(("getprop", "ro.product.model"))["failure_code"] == "command_timeout"

    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    assert module.run_bounded_command(("getprop", "ro.product.model"))["failure_code"] == "command_unavailable"

    class Result:
        returncode = 0
        stdout = b"SM-S911B\xff\x00\x01  extra   text" + b"x" * 5000

    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: Result())
    result = module.run_bounded_command(("getprop", "ro.product.model"), max_output_bytes=32)
    assert result["status"] == "available"
    assert "\x00" not in result["value"]
    assert len(result["value"]) <= 32

    class EmptyResult:
        returncode = 0
        stdout = b"   "

    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: EmptyResult())
    assert module.run_bounded_command(("getprop", "ro.product.model"))["status"] == "empty"


def test_agent_profile_publication_is_startup_reconnect_and_change_only(monkeypatch):
    module = _import_profile_module()
    import pocketlab_node_agent as agent_module

    fingerprints = iter(["a" * 64, "a" * 64, "b" * 64])

    def profile(**_kwargs):
        return {
            "schema_version": 1,
            "technical_model": "SM-S911B",
            "profile_fingerprint": next(fingerprints),
            "collection_status": "current",
            "collected_at": "2026-07-23T08:00:00Z",
        }

    monkeypatch.setattr(agent_module, "collect_system_profile", profile)
    monkeypatch.setattr(agent_module, "collect_system_health", lambda: {"uptime_status": "available", "uptime_seconds": 60, "collected_at": "2026-07-23T08:00:00Z"})
    agent = agent_module.PocketLabNodeAgent()
    first = agent.system_profile_update(force_publish=True)
    assert first["system_profile"]["profile_fingerprint"] == "a" * 64
    assert agent.system_profile_update() == {}
    agent.system_profile_collected_epoch = 0
    periodic = agent.system_profile_update()
    assert periodic["system_profile"]["profile_fingerprint"] == "a" * 64
    agent.system_profile_collected_epoch = 0
    changed = agent.system_profile_update()
    assert changed["system_profile"]["profile_fingerprint"] == "b" * 64

    source = Path(agent_module.__file__).read_text(encoding="utf-8")
    assert "await self.register()" in source and "system_profile_update(force_publish=True)" in source
    assert "self.refresh_system_profile(force=True)" in source
    assert "ro.product.marketname" not in source


def test_uptime_parser_handles_android_and_linux_variants():
    module = _import_profile_module()
    cases = {
        "10:00 up 34 min, load average: 0.10, 0.20, 0.30": 34 * 60,
        "10:00 up 2 hrs, 7 min, load average: 0.10, 0.20, 0.30": 2 * 3600 + 7 * 60,
        "10:00 up 2 days, 34 min, load average: 0.10, 0.20, 0.30": 2 * 86400 + 34 * 60,
        "10:00 up 1 day, 2:34, load averages: 0.10, 0.20, 0.30": 86400 + 2 * 3600 + 34 * 60,
        "10:00 up 4:12, load average: 0.10, 0.20, 0.30": 4 * 3600 + 12 * 60,
    }
    for text, expected in cases.items():
        assert module.parse_uptime_output(text)["uptime_seconds"] == expected
    assert module.parse_uptime_output("unexpected output")["uptime_status"] == "unavailable"


def test_native_linux_profile_skips_android_property_collection(monkeypatch):
    module = _import_profile_module()
    calls = []

    def runner(command):
        calls.append(tuple(command))
        values = {("uname", "-m"): "aarch64", ("uname", "-r"): "6.8.0"}
        return {"status": "available", "value": values[tuple(command)], "failure_code": ""}

    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module.platform, "release", lambda: "6.8.0")
    profile = module.collect_system_profile(agent_version="2.1.0", command_runner=runner, environ={})
    assert profile["runtime_type"] == "native_linux"
    assert profile["os_family"] == "linux"
    assert all(call[0] != "getprop" for call in calls)


def test_profile_projection_display_override_is_idempotent_and_identity_safe(tmp_path, monkeypatch):
    store = _configure_store(tmp_path, monkeypatch)
    first_revision = store.project_fleet(_profile_payload())
    profiles = store.device_profile_map()
    assert profiles["phone-two"]["system_profile"]["technical_model"] == "SM-S911B"
    assert profiles["phone-two"]["system_profile"]["display_model"] == "SM-S911B"

    changed = store.update_device_consumer_model("phone-two", "Samsung Galaxy S23")
    assert changed["changed"] is True
    assert changed["revision"] > first_revision
    assert changed["system_profile"]["display_model"] == "Samsung Galaxy S23"
    assert changed["system_profile"]["technical_model"] == "SM-S911B"

    noop = store.update_device_consumer_model("phone-two", " Samsung   Galaxy S23 ")
    assert noop["changed"] is False
    assert noop["revision"] == changed["revision"]

    safe_round_trip = _profile_payload()
    safe_round_trip["devices"][0]["system_profile"] = store.device_profile_map()["phone-two"]["system_profile"]
    safe_round_trip["devices"][0]["system_health"] = store.device_profile_map()["phone-two"]["system_health"]
    round_trip_revision = store.project_fleet(safe_round_trip)
    assert round_trip_revision == changed["revision"]

    stale = _profile_payload(collected_at="2026-07-22T08:00:00Z", model="SHOULD-NOT-WIN", uptime=60)
    store.project_fleet(stale)
    projected = store.device_profile_map()["phone-two"]
    assert projected["system_profile"]["technical_model"] == "SM-S911B"
    assert projected["system_profile"]["consumer_model_name"] == "Samsung Galaxy S23"
    assert projected["system_health"]["uptime_seconds"] == 7200

    cleared = store.update_device_consumer_model("phone-two", None)
    assert cleared["system_profile"]["consumer_model_name"] == ""
    assert cleared["system_profile"]["display_model"] == "SM-S911B"


def test_display_model_fastapi_update_is_revisioned_and_idempotent(tmp_path, monkeypatch):
    store = _configure_store(tmp_path, monkeypatch)
    store.project_fleet(_profile_payload())
    from api_fastapi import deps
    from api_fastapi.routers.lite import LiteDeviceDisplayModelRequest, update_lite_device_display_model

    monkeypatch.setattr(deps, "require_auth", lambda _request: None)
    payload = update_lite_device_display_model(
        "phone-two",
        LiteDeviceDisplayModelRequest(consumer_model_name="Samsung Galaxy S23", expected_profile_revision=1),
        object(),
    )
    assert payload["changed"] is True
    assert payload["profile_revision"] == 2
    assert payload["system_profile"]["technical_model"] == "SM-S911B"
    assert payload["system_profile"]["display_model"] == "Samsung Galaxy S23"
    assert "profile_fingerprint" not in payload["system_profile"]

    repeated = update_lite_device_display_model(
        "phone-two",
        LiteDeviceDisplayModelRequest(consumer_model_name="Samsung Galaxy S23", expected_profile_revision=1),
        object(),
    )
    assert repeated["changed"] is False
    assert repeated["revision"] == payload["revision"]


def test_display_model_optimistic_revision_blocks_late_tab_write(tmp_path, monkeypatch):
    store = _configure_store(tmp_path, monkeypatch)
    store.project_fleet(_profile_payload())
    first = store.update_device_consumer_model(
        "phone-two",
        "Samsung Galaxy S23",
        expected_profile_revision=1,
    )
    assert first["profile_revision"] == 2

    from api_fastapi.services.lite_control_plane_store import DeviceProfileUpdateError

    with pytest.raises(DeviceProfileUpdateError) as exc_info:
        store.update_device_consumer_model(
            "phone-two",
            "Samsung Galaxy S23 Ultra",
            expected_profile_revision=1,
        )
    assert exc_info.value.status_code == 409
    projected = store.device_profile_map()["phone-two"]["system_profile"]
    assert projected["consumer_model_name"] == "Samsung Galaxy S23"
    assert projected["technical_model"] == "SM-S911B"


def test_display_model_validation_and_query_plan(tmp_path, monkeypatch):
    store = _configure_store(tmp_path, monkeypatch)
    store.project_fleet(_profile_payload())
    from api_fastapi.services.lite_control_plane_store import DeviceProfileUpdateError

    for unsafe in (
        "https://example.invalid/token",
        "javascript:alert(1)",
        "<script>alert(1)</script>",
        "../private/device",
        "api_key Pixel",
    ):
        with pytest.raises(DeviceProfileUpdateError):
            store.update_device_consumer_model("phone-two", unsafe)
    with pytest.raises(DeviceProfileUpdateError):
        store.update_device_consumer_model("missing-device", "Pixel 8")
    plans = store.query_plan_evidence()
    assert "device_system_profile" in plans
    assert any("sqlite_autoindex_device_system_profiles_1" in detail or "PRIMARY KEY" in detail for detail in plans["device_system_profile"])


def test_fleet_public_profile_strips_internal_fingerprint_and_formats_health():
    ensure_runtime_path()
    from api_fastapi.services import lite_status

    public = lite_status._public_system_profile({
        "schema_version": 1,
        "technical_model": "SM-S911B",
        "device_codename": "dm1q",
        "profile_fingerprint": "a" * 64,
        "unavailable_fields": ["security_patch"],
    })
    health = lite_status._public_system_health({
        "uptime_status": "available",
        "uptime_seconds": 2 * 86400 + 34 * 60,
        "load_average_1m": 0.1,
        "load_average_5m": 0.2,
        "load_average_15m": 0.3,
    })
    assert public["display_model"] == "SM-S911B"
    assert "profile_fingerprint" not in public
    assert "unavailable_fields" not in public
    assert health["uptime_label"] == "2 days, 34 minutes"
    assert health["load_average"] == [0.1, 0.2, 0.3]


def test_phase_d1_frontend_contract_is_display_only():
    root = Path(__file__).resolve().parents[2]
    sources = {
        name: (root / name).read_text(encoding="utf-8")
        for name in (
            "src/lite/devices/DeviceModelPickerLazy.jsx",
            "src/machines/liteDeviceModelMachine.js",
            "src/lib/liteViewModels.js",
            "src/lite/LiteDevices.jsx",
        )
    }
    joined = "\n".join(sources.values()).lower()
    mutation_source = (root / "src/hooks/useLiteMutation.js").read_text(encoding="utf-8")
    assert "update_device_model: [liteQueryKeys.fleet()]" in mutation_source
    assert "consumer_model_name" in joined
    assert "expected_profile_revision" in (root / "src/lib/liteApi.js").read_text(encoding="utf-8")
    assert "technical_model" in joined
    assert "backend_confirmed" in sources["src/machines/liteDeviceModelMachine.js"].lower()
    assert "getprop" not in joined
    assert "navigator?.vibrate" in sources["src/lite/devices/DeviceModelPickerLazy.jsx"]
    assert "battery" not in joined
    assert "protected_server_host || activeDetailsDevice?.role === 'server_host'" in sources["src/lite/LiteDevices.jsx"]
    assert "profile_fingerprint" not in sources["src/lib/liteViewModels.js"]
    assert "snapshotSelect: selectDevicesScreenView" in sources["src/lite/LiteDevices.jsx"]


def test_phase_d1_sources_do_not_collect_battery_or_unrestricted_getprop():
    root = Path(__file__).resolve().parents[2]
    collector = (root / "pocket-lab-final-structure/runtime/agents/lite_system_profile.py").read_text(encoding="utf-8").lower()
    assert "battery" not in collector
    assert '("getprop",)' not in collector
    assert "ro.product.model" in collector
    assert "ro.product.device" in collector
    assert "ro.product.manufacturer" in collector
    assert "ro.product.marketname" not in collector
    assert "12 * 60 * 60" in (root / "pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py").read_text(encoding="utf-8")


def test_protected_server_host_model_update_is_rejected_and_identity_preserved(tmp_path, monkeypatch):
    store = _configure_store(tmp_path, monkeypatch)
    payload = _profile_payload()
    payload["devices"][0].update({"role": "server_host", "is_current": True, "name": "Pocket Lab Server"})
    store.project_fleet(payload)

    from api_fastapi.services.lite_control_plane_store import DeviceProfileUpdateError

    with pytest.raises(DeviceProfileUpdateError) as exc_info:
        store.update_device_consumer_model("phone-two", "Samsung Galaxy S23")
    assert exc_info.value.status_code == 409

    current, _, _ = store._read(
        lambda conn: dict(conn.execute(
            "SELECT device_id, device_name, role, protected_server_host FROM device_current_state WHERE device_id=?",
            ("phone-two",),
        ).fetchone())
    )
    assert current == {
        "device_id": "phone-two",
        "device_name": "Pocket Lab Server",
        "role": "server_host",
        "protected_server_host": 1,
    }
    profile = store.device_profile_map()["phone-two"]["system_profile"]
    assert profile["technical_model"] == "SM-S911B"
    assert profile["consumer_model_name"] == ""


def test_display_model_audit_metadata_is_sanitized(tmp_path, monkeypatch):
    store = _configure_store(tmp_path, monkeypatch)
    store.project_fleet(_profile_payload())
    store.update_device_consumer_model("phone-two", "Samsung Galaxy S23")
    rows, _, _ = store._read(
        lambda conn: [dict(row) for row in conn.execute(
            "SELECT event_type, entity_id, operation_id, summary, evidence_ref "
            "FROM audit_evidence_index WHERE event_type='device.display_model.updated'"
        )]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["entity_id"] == "phone-two"
    assert row["summary"] == "Device display model updated."
    assert row["evidence_ref"] == "sqlite:device_system_profiles"
    assert "Samsung" not in " ".join(str(value) for value in row.values())


def test_model_catalog_duplicate_matches_remain_explicit_suggestions():
    root = Path(__file__).resolve().parents[2]
    catalog = (root / "src/data/androidDeviceModels.js").read_text(encoding="utf-8")
    picker = (root / "src/lite/devices/DeviceModelPickerLazy.jsx").read_text(encoding="utf-8")
    assert "matches are suggestions and are never auto-selected" in catalog
    assert ".sort((a, b) => b.score - a.score" in catalog
    assert "flow.review(entry.consumerModelName)" in picker
    assert "flow.succeeded" in picker


def test_server_agent_identity_is_canonical_and_remote_claims_fail_closed(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import fleet_registry

    state = {"agents": {}, "updated_at": None}
    monkeypatch.setenv("POCKETLAB_SERVER_NODE_ID", "pocket-lab-lite-server")
    monkeypatch.setenv("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")
    monkeypatch.setattr(fleet_registry, "_agents_payload", lambda: state)
    monkeypatch.setattr(fleet_registry, "_write", lambda _path, _payload: None)
    monkeypatch.setattr(fleet_registry, "_now", lambda: "2026-07-23T12:00:00Z")
    monkeypatch.setattr(fleet_registry, "_epoch", lambda: 100.0)

    local = fleet_registry.upsert_agent({
        "node_id": "localhost",
        "name": "localhost",
        "role": "server_host",
        "is_control_plane": True,
        "system_profile": {"architecture": "aarch64", "collection_status": "current"},
        "system_health": {"uptime_seconds": 123, "uptime_status": "available"},
    })
    assert local["node_id"] == "pocket-lab-lite-server"
    assert local["name"] == "Pocket Lab Lite Server"
    assert local["role"] == "server_host"
    assert local["isCurrent"] is True
    assert local["system_profile"]["architecture"] == "aarch64"

    remote = fleet_registry.upsert_agent({
        "node_id": "remote-phone",
        "name": "Remote Phone",
        "role": "server_host",
        "is_control_plane": True,
    })
    assert remote["node_id"] == "remote-phone"
    assert remote["isCurrent"] is False
    assert "remote-phone" in state["agents"]


def test_agent_event_invalidates_only_fleet_prepared_snapshot(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import fleet_registry
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    calls = []
    monkeypatch.setattr(fleet_registry, "upsert_agent", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(CONTROL_PLANE, "invalidate_domain", lambda domain: calls.append(domain))

    fleet_registry.handle_agent_event({
        "subject": "pocketlab.events.fleet.node_heartbeat",
        "type": "fleet.node_heartbeat",
        "data": {"node_id": "pocket-lab-lite-server"},
    })
    assert calls == ["fleet"]


def test_canonical_server_profile_and_health_merge_into_lite_fleet(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_status
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    monkeypatch.setenv("POCKETLAB_NODE_ID", "pocket-lab-lite-server")
    monkeypatch.setenv("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")
    monkeypatch.setattr(lite_status, "lite_remote_access_status", lambda: {
        "status": "healthy", "ready": True, "ip": "100.64.0.1",
        "summary": "Ready", "checked_at": "2026-07-23T12:00:00Z",
    })
    monkeypatch.setattr(lite_status, "merged_fleet_nodes", lambda: [{
        "id": "pocket-lab-lite-server",
        "node_id": "pocket-lab-lite-server",
        "name": "Pocket Lab Lite Server",
        "role": "server_host",
        "status": "active",
        "isCurrent": True,
        "source": "nats-agent",
        "last_seen_at": "2026-07-23T12:00:00Z",
        "system_profile": {
            "architecture": "aarch64",
            "os_name": "Android",
            "technical_model": "SM-S911B",
            "runtime_type": "termux",
            "collection_status": "current",
            "collected_at": "2026-07-23T12:00:00Z",
        },
        "system_health": {
            "uptime_seconds": 183480,
            "uptime_status": "available",
            "load_status": "normal",
            "collected_at": "2026-07-23T12:00:00Z",
        },
    }])
    monkeypatch.setattr(CONTROL_PLANE, "device_profile_map", lambda: {})

    payload = lite_status.lite_fleet()
    server = payload["devices"][0]
    assert payload["count"] == 1
    assert server["id"] == "pocket-lab-lite-server"
    assert server["system_profile"]["architecture"] == "aarch64"
    assert server["system_profile"]["technical_model"] == "SM-S911B"
    assert server["system_health"]["uptime_seconds"] == 183480
    assert server["system_health"]["uptime_status"] == "available"


def test_server_startup_sets_stable_protected_agent_identity():
    root = Path(__file__).resolve().parents[2]
    script = (root / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh").read_text(encoding="utf-8")
    agent = (root / "pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py").read_text(encoding="utf-8")

    assert 'POCKETLAB_NODE_ID="${POCKETLAB_SERVER_NODE_ID:-pocket-lab-lite-server}"' in script
    assert 'POCKETLAB_NODE_ROLE=server_host' in script
    assert 'POCKETLAB_IS_CONTROL_PLANE=1' in script
    assert '"is_control_plane": self.is_control_plane' in agent


def test_devices_ui_polish_preserves_server_protection_and_hides_empty_storage():
    root = Path(__file__).resolve().parents[2]
    card = (root / "src/lite/devices/DeviceCard.jsx").read_text(encoding="utf-8")
    details = (root / "src/lite/devices/DeviceDetailsLazy.jsx").read_text(encoding="utf-8")
    screen = (root / "src/lite/LiteDevices.jsx").read_text(encoding="utf-8")
    styles = (root / "src/index.css").read_text(encoding="utf-8")

    assert "function hasMeaningfulStorage(device)" in card
    assert "Storage status will appear after the device reports it." not in card
    assert "lite-device-system-strip" in card
    assert "Server model detected automatically" in details
    assert "The protected server identity comes from the local agent" in details
    assert "<details className=\"lite-device-advanced-details\">" in details
    assert "<details className=\"lite-devices-add-disclosure\">" in screen
    assert "Current connection, system identity, and health at a glance." in screen
    assert ".lite-device-protected-model" in styles
    assert ".lite-device-advanced-details" in styles
