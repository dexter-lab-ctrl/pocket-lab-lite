from __future__ import annotations

import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path


NOW_EPOCH = 1_788_000_000.0
NOW_ISO = "2026-08-29T10:40:00Z"


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_runtime_path()
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_DEVICE_HEALTH_LOAD_MINIMUM_SECONDS", "60")
    monkeypatch.setenv("POCKETLAB_DEVICE_HEALTH_RECOVERY_MINIMUM_SECONDS", "0")
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    reset_sqlite_path_cache()


def _device(**overrides):
    value = {
        "id": "phone-two",
        "node_id": "phone-two",
        "name": "Phone Two",
        "role": "compute",
        "status": "online",
        "connection": "online",
        "agent_status": "online",
        "agent_process_status": "online",
        "supervisor_status": "healthy",
        "last_seen_at": NOW_ISO,
        "last_seen_state": {
            "last_seen_at": NOW_ISO,
            "last_heartbeat_at": NOW_ISO,
            "last_telemetry_at": NOW_ISO,
            "last_system_profile_at": NOW_ISO,
            "last_supervisor_heartbeat_at": NOW_ISO,
            "last_nats_connected_at": NOW_ISO,
            "staleness_state": "current",
        },
        "system_profile": {
            "schema_version": 1,
            "agent_version": "2.5.0-lite-trust-capability-awareness",
            "supervisor_version": "1.0.0-lite-agent-supervisor",
            "collected_at": NOW_ISO,
        },
        "dependencies": {
            "remote_access_status": "ready",
            "command_delivery_status": "deliverable",
            "recovery_available": True,
            "hosted_apps": [],
            "backup_set_count": 0,
        },
        "awareness_revision": 7,
    }
    value.update(overrides)
    return value


def _signals(**overrides):
    value = {
        "telemetry": {
            "timestamp": NOW_ISO,
            "free_space_mb": 40_000,
            "total_space_mb": 64_000,
            "memory_free_mb": 4_000,
            "memory_total_mb": 8_000,
            "cpu_usage_percent": 20,
            "cpu_temp_c": 42,
        },
        "storage": {"available_bytes": 40_000 * 1024 * 1024},
        "reconnect_count": 0,
        "supervisor_repair_count": 0,
        "agent_version": "2.5.0-lite-trust-capability-awareness",
        "supervisor_version": "1.0.0-lite-agent-supervisor",
        "capability_schema_version": 1,
    }
    value.update(overrides)
    return value


def _health_payload(health):
    device = _device(proactive_health=health)
    device.update({
        "health_status": health["status"],
        "health_severity": health["severity"],
        "attention_count": health["attention_count"],
    })
    return {
        "status": "healthy",
        "devices": [device],
        "remote_access": {"ready": True, "status": "healthy"},
        "latest_invite": None,
        "health_summary": {health["status"]: 1, "attention_count": health["attention_count"]},
        "updated_at": health["last_evaluated_at"],
    }


def test_d4_health_evaluator_is_deterministic_backend_owned_and_healthy():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    first = evaluate_device_health(_device(), signals=_signals(), now_epoch=NOW_EPOCH)
    second = evaluate_device_health(
        _device(), signals=_signals(), previous=first, now_epoch=NOW_EPOCH + 5
    )

    assert first["status"] == "healthy"
    assert first["severity"] == "none"
    assert first["reason_codes"] == []
    assert first["attention_items"] == []
    assert first["recommended_action"] == "none"
    assert first["health_revision"] == second["health_revision"]
    assert first["last_evaluated_at"] == second["last_evaluated_at"]
    assert second["sanitized"] is True
    assert "token" not in json.dumps(second).lower()


def test_d4_resource_hysteresis_and_duration_guards_reduce_flapping():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    healthy = evaluate_device_health(_device(), signals=_signals(), now_epoch=NOW_EPOCH)
    high_load_signals = _signals(telemetry={**_signals()["telemetry"], "cpu_usage_percent": 99})
    candidate = evaluate_device_health(
        _device(), signals=high_load_signals, previous=healthy, now_epoch=NOW_EPOCH + 1
    )
    assert candidate["resources"]["load"]["status"] == "normal"
    assert candidate["resources"]["load"]["candidate_status"] == "critical"
    assert "high_load" not in candidate["reason_codes"]

    sustained = evaluate_device_health(
        _device(), signals=high_load_signals, previous=candidate, now_epoch=NOW_EPOCH + 62
    )
    assert sustained["resources"]["load"]["status"] == "critical"
    assert "high_load" in sustained["reason_codes"]

    storage_watch = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 12_160}),
        now_epoch=NOW_EPOCH,
    )
    assert storage_watch["resources"]["storage"]["status"] == "watch"
    inside_margin = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 13_440}),
        previous=storage_watch,
        now_epoch=NOW_EPOCH + 5,
    )
    assert inside_margin["resources"]["storage"]["status"] == "watch"
    outside_margin = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 15_360}),
        previous=inside_margin,
        now_epoch=NOW_EPOCH + 10,
    )
    assert outside_margin["resources"]["storage"]["status"] == "watch"
    assert outside_margin["resources"]["storage"]["recovery_candidate_status"] == "normal"
    recovered = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 15_360}),
        previous=outside_margin,
        now_epoch=NOW_EPOCH + 41,
    )
    assert recovered["resources"]["storage"]["status"] == "normal"


def test_d4_connection_recovery_versions_and_dependency_impact_are_truthful():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    device = _device(
        dependencies={
            **_device()["dependencies"],
            "hosted_apps": [{"app_id": "photoprism", "label": "PhotoPrism"}],
            "backup_set_count": 1,
        }
    )
    signals = _signals(
        telemetry={**_signals()["telemetry"], "free_space_mb": 2_000},
        reconnect_count=5,
        supervisor_repair_count=5,
        agent_version="2.4.0",
    )
    health = evaluate_device_health(device, signals=signals, now_epoch=NOW_EPOCH)

    assert health["connection"]["status"] == "intermittent"
    assert health["versions"]["node_agent"]["status"] == "behind"
    assert health["dependency_impact"]["status"] == "at_risk"
    assert health["dependency_impact"]["affected_apps"][0]["app_id"] == "photoprism"
    assert "storage_pressure" in health["reason_codes"]
    assert "connection_intermittent" in health["reason_codes"]
    assert "agent_version_behind" in health["reason_codes"]
    assert "hosted_app_at_risk" in health["reason_codes"]
    assert health["attention_count"] == len(health["attention_items"])
    assert all(item["status"] == "active" for item in health["attention_items"])


def test_d4_missing_and_stale_inputs_never_become_healthy():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    missing = evaluate_device_health(
        _device(last_seen_at=None, last_seen_state={}, system_profile={}),
        signals={},
        now_epoch=NOW_EPOCH,
    )
    assert missing["status"] != "healthy"
    assert missing["source_freshness"]["heartbeat"]["state"] == "missing"

    stale_device = _device(
        status="offline",
        connection="offline",
        last_seen_at="2026-08-29T09:00:00Z",
        last_seen_state={
            "last_seen_at": "2026-08-29T09:00:00Z",
            "last_heartbeat_at": "2026-08-29T09:00:00Z",
            "last_telemetry_at": "2026-08-29T09:00:00Z",
            "last_system_profile_at": "2026-08-28T09:00:00Z",
            "last_supervisor_heartbeat_at": "2026-08-29T09:00:00Z",
            "staleness_state": "stale",
        },
    )
    stale = evaluate_device_health(stale_device, signals=_signals(), now_epoch=NOW_EPOCH)
    assert stale["status"] == "unreachable"
    assert "heartbeat_stale" in stale["reason_codes"]


def test_d4_sqlite_projection_is_change_only_resolves_attention_and_bounds_history(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore, SQLITE_WRITER
    from api_fastapi.services.lite_device_health import evaluate_device_health

    store = ControlPlaneProjectionStore()
    degraded = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 2_000}),
        now_epoch=NOW_EPOCH,
    )
    first = store.project_fleet(_health_payload(degraded))
    second = store.project_fleet(_health_payload(degraded))
    assert first == 1
    assert second == first

    # A different raw value in the same threshold bucket must not advance the
    # prepared health revision or write a new transition.
    same_bucket_without_previous = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 1_500}),
        now_epoch=NOW_EPOCH + 5,
    )
    assert same_bucket_without_previous["health_revision"] == degraded["health_revision"]
    assert store.project_fleet(_health_payload(same_bucket_without_previous)) == second

    projected = store.device_health("phone-two")
    assert projected["health"]["attention_count"] > 0
    assert projected["health"]["attention_items"]
    acknowledged_id = projected["health"]["attention_items"][0]["id"]
    SQLITE_WRITER.submit(
        "test.device-health.acknowledge",
        lambda conn: conn.execute(
            "UPDATE device_health_attention SET status='acknowledged' WHERE attention_id=?",
            (acknowledged_id,),
        ).rowcount,
        deadline_seconds=1.0,
    )
    assert store.project_fleet(_health_payload(degraded)) == second
    acknowledged = store.device_health("phone-two")
    assert any(
        item["id"] == acknowledged_id and item["status"] == "acknowledged"
        for item in acknowledged["health"]["attention_items"]
    )
    details = store.device_details("phone-two")
    assert details["device"]["proactive_health"]["health_revision"] == degraded["health_revision"]

    healthy = evaluate_device_health(
        _device(), signals=_signals(), previous=projected["health"], now_epoch=NOW_EPOCH + 60
    )
    third = store.project_fleet(_health_payload(healthy))
    assert third > second
    after = store.device_health("phone-two")
    assert after["health"]["status"] == "healthy"
    assert after["health"]["attention_count"] == 0
    assert after["health"]["attention_items"] == []
    history = store.device_health_history("phone-two", limit=20)
    assert len(history["items"]) >= 2
    assert all(item["sanitized"] for item in history["items"])

    with read_connection() as conn:
        active = conn.execute(
            "SELECT COUNT(*) AS count FROM device_health_attention WHERE status='active'"
        ).fetchone()["count"]
        resolved = conn.execute(
            "SELECT COUNT(*) AS count FROM device_health_attention WHERE status='resolved'"
        ).fetchone()["count"]
    assert active == 0
    assert resolved > 0


def test_d4_health_endpoints_use_prepared_sqlite_etags_and_304(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.routers import lite as lite_router
    from api_fastapi.services.lite_device_health import evaluate_device_health

    health = evaluate_device_health(_device(), signals=_signals(), now_epoch=NOW_EPOCH)
    payload = _health_payload(health)
    monkeypatch.setattr(lite_router.lite_status, "lite_fleet", lambda: payload)

    fleet = client().get("/api/lite/fleet")
    assert fleet.status_code == 200
    health_response = client().get("/api/lite/devices/phone-two/health")
    assert health_response.status_code == 200
    assert health_response.headers.get("etag")
    assert health_response.headers.get("cache-control") == "no-cache"
    assert health_response.json()["health"]["status"] == "healthy"
    assert client().get(
        "/api/lite/devices/phone-two/health",
        headers={"If-None-Match": health_response.headers["etag"]},
    ).status_code == 304

    history = client().get("/api/lite/devices/phone-two/health/history?limit=20")
    assert history.status_code == 200
    assert history.headers.get("etag")
    assert client().get(
        "/api/lite/devices/phone-two/health/history?limit=20",
        headers={"If-None-Match": history.headers["etag"]},
    ).status_code == 304

    summary = client().get("/api/lite/fleet/health-summary")
    assert summary.status_code == 200
    assert summary.json()["device_count"] == 1
    assert summary.json()["sanitized"] is True


def test_d4_query_plans_use_health_indexes(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore
    from api_fastapi.services.lite_device_health import evaluate_device_health

    store = ControlPlaneProjectionStore()
    health = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 2_000}),
        now_epoch=NOW_EPOCH,
    )
    store.project_fleet(_health_payload(health))
    plans = store.query_plan_evidence()
    assert any("device_health_current" in part or "sqlite_autoindex_device_health_current" in part for part in plans["device_health_current"])
    assert any("idx_device_health_attention_active_time" in part for part in plans["device_health_attention"])
    assert any("idx_device_health_transitions_device_time" in part for part in plans["device_health_history"])
    assert all("TEMP B-TREE" not in " ".join(parts) for key, parts in plans.items() if key.startswith("device_health"))


def test_d4_frontend_contract_uses_backend_health_and_saved_attention_guard():
    root = Path(__file__).resolve().parents[2]
    view_models = (root / "src/lib/liteViewModels.js").read_text(encoding="utf-8")
    device_card = (root / "src/lite/devices/DeviceCard.jsx").read_text(encoding="utf-8")
    details = (root / "src/lite/devices/DeviceDetailsLazy.jsx").read_text(encoding="utf-8")
    store = (root / "src/stores/liteUiStore.js").read_text(encoding="utf-8")
    snapshots = (root / "src/lib/liteSafeSnapshots.js").read_text(encoding="utf-8")
    health_machine = (root / "src/machines/liteDeviceHealthReviewMachine.js").read_text(encoding="utf-8")
    health_flow = (root / "src/hooks/useLiteDeviceHealthReviewFlow.js").read_text(encoding="utf-8")

    assert "selectDeviceProactiveHealthView" in view_models
    assert "attention_current: false" in view_models
    assert "proactive_health" in device_card
    assert "Review health" in device_card
    assert "DEVICE_HEALTH_RECOMMENDATIONS_DO_NOT_EXECUTE_D4" in details
    assert "deviceHealthHistoryOpenId" in store
    assert "DEVICE_HEALTH_HISTORY_SNAPSHOT_PATH_PATTERN" in snapshots
    assert "LITE_DEVICE_HEALTH_REVIEW_BACKEND_AUTHORITATIVE_D4" in health_machine
    assert "backendConfirmedResolved" in health_machine
    assert "useLiteDeviceHealthReviewFlow" in health_flow
    assert "healthReviewFlow.routeTo" in details
    assert "POCKETLAB_DEVICE_HEALTH_STORAGE" not in device_card
    assert "POCKETLAB_DEVICE_HEALTH_STORAGE" not in details
    assert "execute shell" not in details.lower()


@pytest.mark.parametrize(
    ("telemetry_patch", "resource", "expected"),
    [
        ({"free_space_mb": 12_800}, "storage", "watch"),
        ({"free_space_mb": 2_000}, "storage", "critical"),
        ({"memory_free_mb": 500}, "memory", "critical"),
        ({"cpu_temp_c": 85}, "temperature", "low"),
    ],
)
def test_d4_resource_bands_are_backend_owned_and_bounded(telemetry_patch, resource, expected):
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    health = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], **telemetry_patch}),
        now_epoch=NOW_EPOCH,
    )
    assert health["resources"][resource]["status"] == expected
    assert health["status"] != "healthy"


def test_d4_missing_telemetry_with_current_heartbeat_is_unknown_not_healthy():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    last_seen = dict(_device()["last_seen_state"])
    last_seen["last_telemetry_at"] = None
    health = evaluate_device_health(
        _device(last_seen_state=last_seen),
        signals={
            "telemetry": {},
            "storage": {},
            "agent_version": "2.5.0-lite-trust-capability-awareness",
            "supervisor_version": "1.0.0-lite-agent-supervisor",
            "capability_schema_version": 1,
        },
        now_epoch=NOW_EPOCH,
    )
    assert health["source_freshness"]["heartbeat"]["state"] == "current"
    assert health["source_freshness"]["telemetry"]["state"] == "missing"
    assert health["status"] == "unknown"


def test_d4_out_of_order_telemetry_and_late_recovery_do_not_regress_state():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    recovered_device = _device(
        last_recovery_at=NOW_ISO,
        last_recovery_result="succeeded",
        last_seen_state={**_device()["last_seen_state"], "last_recovery_at": NOW_ISO},
    )
    first = evaluate_device_health(
        recovered_device,
        signals=_signals(supervisor_repair_count=1),
        now_epoch=NOW_EPOCH,
    )
    assert first["status"] == "healthy"
    assert first["recovery"]["status"] == "recovered"

    old_iso = "2026-08-29T10:30:00Z"
    late_device = _device(
        last_recovery_at=old_iso,
        last_recovery_result="failed",
        last_seen_state={
            **_device()["last_seen_state"],
            "last_telemetry_at": old_iso,
            "last_recovery_at": old_iso,
        },
    )
    late = evaluate_device_health(
        late_device,
        signals=_signals(
            telemetry={
                **_signals()["telemetry"],
                "timestamp": old_iso,
                "free_space_mb": 500,
            },
            supervisor_repair_count=1,
        ),
        previous=first,
        now_epoch=NOW_EPOCH + 5,
    )
    assert late["resources"]["storage"]["status"] == "normal"
    assert late["source_freshness"]["telemetry"]["ignored_out_of_order"] is True
    assert late["recovery"]["status"] == "recovered"
    assert "repair_failed" not in late["reason_codes"]


def test_d4_temporary_disconnect_recovery_and_agent_stopped_states_are_distinct():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    temporary = evaluate_device_health(
        _device(status="offline", connection="offline"),
        signals=_signals(),
        now_epoch=NOW_EPOCH,
    )
    assert temporary["connection"]["status"] == "unknown"
    assert temporary["status"] == "unknown"
    assert "heartbeat_stale" not in temporary["reason_codes"]

    stopped = evaluate_device_health(
        _device(
            status="agent_stopped",
            agent_process_status="stopped",
            supervisor_status="missing",
        ),
        signals=_signals(),
        now_epoch=NOW_EPOCH,
    )
    assert stopped["connection"]["status"] == "disconnected"
    assert stopped["recovery"]["status"] == "manual_attention_required"
    assert "agent_stopped" in stopped["reason_codes"]
    assert stopped["recommended_action"] == "restart_agent"


def test_d4_recovery_patterns_and_supervisor_staleness_are_bounded():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    repeated = evaluate_device_health(
        _device(
            last_recovery_at=NOW_ISO,
            last_seen_state={**_device()["last_seen_state"], "last_recovery_at": NOW_ISO},
        ),
        signals=_signals(supervisor_repair_count=5),
        now_epoch=NOW_EPOCH,
    )
    assert repeated["recovery"]["status"] == "repeated_recovery"
    assert "repeated_recovery" in repeated["reason_codes"]

    stale_supervisor = evaluate_device_health(
        _device(last_seen_state={
            **_device()["last_seen_state"],
            "last_supervisor_heartbeat_at": "2026-08-29T10:30:00Z",
        }),
        signals=_signals(),
        now_epoch=NOW_EPOCH,
    )
    assert "supervisor_stale" in stale_supervisor["reason_codes"]


def test_d4_unknown_version_is_safe_and_schema_incompatibility_is_explicit():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    unknown = evaluate_device_health(
        _device(system_profile={
            **_device()["system_profile"],
            "agent_version": "development-build",
        }),
        signals=_signals(agent_version="development-build"),
        now_epoch=NOW_EPOCH,
    )
    assert unknown["versions"]["node_agent"]["status"] == "unknown"
    assert unknown["versions"]["status"] == "unknown"
    assert "schema_incompatible" not in unknown["reason_codes"]
    assert unknown["status"] == "unknown"

    incompatible = evaluate_device_health(
        _device(),
        signals=_signals(capability_schema_version=2),
        now_epoch=NOW_EPOCH,
    )
    assert incompatible["versions"]["status"] == "incompatible"
    assert "schema_incompatible" in incompatible["reason_codes"]
    assert incompatible["status"] == "degraded"


def test_d4_attention_is_deduplicated_and_bounded():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    stale = "2026-08-29T09:00:00Z"
    device = _device(
        status="agent_stopped",
        connection="offline",
        agent_process_status="stopped",
        supervisor_status="missing",
        identity_status="mismatch",
        last_recovery_at=NOW_ISO,
        last_recovery_result="failed",
        last_seen_state={
            **_device()["last_seen_state"],
            "last_heartbeat_at": stale,
            "last_telemetry_at": stale,
            "last_system_profile_at": "2026-08-27T10:40:00Z",
            "last_supervisor_heartbeat_at": stale,
            "last_recovery_at": NOW_ISO,
            "staleness_state": "stale",
        },
        dependencies={
            **_device()["dependencies"],
            "hosted_apps": [{"app_id": "photoprism", "label": "PhotoPrism"}],
            "backup_set_count": 1,
            "pending_command_count": 1,
            "command_delivery_status": "stale",
        },
    )
    signals = _signals(
        telemetry={
            **_signals()["telemetry"],
            "timestamp": stale,
            "free_space_mb": 500,
            "memory_free_mb": 100,
            "cpu_temp_c": 95,
        },
        reconnect_count=8,
        supervisor_repair_count=8,
        agent_version="2.4.0",
        capability_schema_version=2,
    )
    health = evaluate_device_health(device, signals=signals, now_epoch=NOW_EPOCH)
    assert len(health["attention_items"]) <= 12
    assert len({item["id"] for item in health["attention_items"]}) == len(health["attention_items"])
    again = evaluate_device_health(device, signals=signals, previous=health, now_epoch=NOW_EPOCH + 5)
    assert [item["id"] for item in again["attention_items"]] == [item["id"] for item in health["attention_items"]]
    assert [item["created_at"] for item in again["attention_items"]] == [item["created_at"] for item in health["attention_items"]]


def test_d4_history_cursor_and_unknown_device_are_safe(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore, DeviceAwarenessError
    from api_fastapi.services.lite_device_health import evaluate_device_health

    store = ControlPlaneProjectionStore()
    health_states = [
        evaluate_device_health(_device(), signals=_signals(), now_epoch=NOW_EPOCH),
        evaluate_device_health(
            _device(),
            signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 12_000}),
            now_epoch=NOW_EPOCH,
        ),
        evaluate_device_health(
            _device(),
            signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 2_000}),
            now_epoch=NOW_EPOCH,
        ),
    ]
    for health in health_states:
        store.project_fleet(_health_payload(health))

    first_page = store.device_health_history("phone-two", limit=1)
    assert len(first_page["items"]) == 1
    assert first_page["next_cursor"]
    second_page = store.device_health_history(
        "phone-two", limit=1, cursor=first_page["next_cursor"]
    )
    assert len(second_page["items"]) == 1
    assert second_page["items"][0]["event_id"] != first_page["items"][0]["event_id"]
    with pytest.raises(DeviceAwarenessError):
        store.device_health_history("missing-node", limit=20)



def test_d4_reconnect_window_boundary_avoids_stale_session_alarm(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    monkeypatch.setenv("POCKETLAB_DEVICE_HEALTH_RECONNECT_WINDOW_SECONDS", "3600")
    recent = evaluate_device_health(
        _device(),
        signals=_signals(reconnect_count=4),
        now_epoch=NOW_EPOCH,
    )
    assert recent["connection"]["status"] == "intermittent"
    assert recent["connection"]["reconnect_window_seconds"] == 3600

    old_connection = _device(last_seen_state={
        **_device()["last_seen_state"],
        "last_nats_connected_at": "2026-08-29T08:40:00Z",
    })
    outside_window = evaluate_device_health(
        old_connection,
        signals=_signals(reconnect_count=4),
        now_epoch=NOW_EPOCH,
    )
    assert outside_window["connection"]["status"] == "stable"
    assert "connection_intermittent" not in outside_window["reason_codes"]


def test_d4_memory_and_load_hysteresis_boundaries(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    monkeypatch.setenv("POCKETLAB_DEVICE_HEALTH_LOAD_MINIMUM_SECONDS", "0")
    monkeypatch.setenv("POCKETLAB_DEVICE_HEALTH_RECOVERY_MINIMUM_SECONDS", "0")
    memory_watch = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "memory_free_mb": 1_600}),
        now_epoch=NOW_EPOCH,
    )
    memory_inside_margin = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "memory_free_mb": 2_160}),
        previous=memory_watch,
        now_epoch=NOW_EPOCH + 5,
    )
    memory_outside_margin = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "memory_free_mb": 2_400}),
        previous=memory_inside_margin,
        now_epoch=NOW_EPOCH + 10,
    )
    assert memory_watch["resources"]["memory"]["status"] == "watch"
    assert memory_inside_margin["resources"]["memory"]["status"] == "watch"
    assert memory_outside_margin["resources"]["memory"]["status"] == "normal"

    load_watch = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "cpu_usage_percent": 75}),
        now_epoch=NOW_EPOCH,
    )
    load_inside_margin = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "cpu_usage_percent": 68}),
        previous=load_watch,
        now_epoch=NOW_EPOCH + 5,
    )
    load_outside_margin = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "cpu_usage_percent": 65}),
        previous=load_inside_margin,
        now_epoch=NOW_EPOCH + 10,
    )
    assert load_watch["resources"]["load"]["status"] == "watch"
    assert load_inside_margin["resources"]["load"]["status"] == "watch"
    assert load_outside_margin["resources"]["load"]["status"] == "normal"


def test_d4_attention_timestamp_updates_only_when_material_changes():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    watch = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 12_000}),
        now_epoch=NOW_EPOCH,
    )
    same = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 12_000}),
        previous=watch,
        now_epoch=NOW_EPOCH + 5,
    )
    critical = evaluate_device_health(
        _device(),
        signals=_signals(telemetry={**_signals()["telemetry"], "free_space_mb": 1_000}),
        previous=same,
        now_epoch=NOW_EPOCH + 10,
    )
    assert same["attention_items"][0]["created_at"] == watch["attention_items"][0]["created_at"]
    assert same["attention_items"][0]["updated_at"] == watch["attention_items"][0]["updated_at"]
    assert critical["attention_items"][0]["created_at"] == watch["attention_items"][0]["created_at"]
    assert critical["attention_items"][0]["updated_at"] != watch["attention_items"][0]["updated_at"]

def test_d4_migration_and_revision_sync_are_bounded_and_focused():
    root = Path(__file__).resolve().parents[2]
    migration = (root / "pocket-lab-final-structure/runtime/api_fastapi/db/schema/0012_device_proactive_health.sql").read_text(encoding="utf-8")
    revisions = (root / "src/lib/liteRevisionSync.js").read_text(encoding="utf-8")
    router = (root / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS device_health_current" in migration
    assert "CREATE TABLE IF NOT EXISTS device_health_attention" in migration
    assert "CREATE TABLE IF NOT EXISTS device_health_transitions" in migration
    assert "raw telemetry" in migration.lower()
    assert "payload_json" not in migration
    assert "device_health_changed" in revisions
    assert "device_attention_changed" in revisions
    assert "new Set([1, 2, 3, 4])" in revisions
    assert "liteQueryKeys.deviceHealth(nodeId)" in revisions
    assert "health_changed_ids" in (root / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py").read_text(encoding="utf-8")
    assert "device_health_projection_sweep_loop" in router
    assert "POCKETLAB_DEVICE_HEALTH_SWEEP_SECONDS" in router


def test_d4_missing_optional_supervisor_does_not_block_current_device_health():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_health import evaluate_device_health

    device = _device(
        supervisor_status=None,
        last_seen_state={
            **_device()["last_seen_state"],
            "last_supervisor_heartbeat_at": None,
        },
        system_profile={
            **_device()["system_profile"],
            "supervisor_version": None,
        },
        dependencies={
            **_device()["dependencies"],
            "recovery_available": False,
            "supervisor_status": "unknown",
        },
    )
    signals = _signals(supervisor_version=None)

    health = evaluate_device_health(device, signals=signals, now_epoch=NOW_EPOCH)

    assert health["source_freshness"]["supervisor"]["state"] == "missing"
    assert health["source_freshness"]["state"] == "current"
    assert health["source_freshness"]["optional_state"] == "unavailable"
    assert health["versions"]["supervisor"]["status"] == "unknown"
    assert health["versions"]["status"] == "current"
    assert health["status"] == "healthy"
    assert health["summary"] == "No immediate action is needed."


def test_d4_accepted_invite_remains_visible_as_offline_fleet_fallback(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import lite_invites

    deps.core.write_json_file(
        deps.settings().state_dir / "fleet_invites.json",
        {
            "updated_at": NOW_ISO,
            "invites": [
                {
                    "invite_id": "invite-phone-two",
                    "node_id": "phone-two",
                    "hostname": "Phone Two",
                    "role": "compute",
                    "capabilities": ["compute", "health"],
                    "status": "accepted",
                    "uses_remaining": 0,
                    "accepted_at": NOW_ISO,
                    "updated_at": NOW_ISO,
                    "created_at": NOW_ISO,
                    "expires_at_epoch": NOW_EPOCH - 1,
                }
            ],
        },
    )

    nodes = lite_invites.enrolled_invite_nodes()

    assert len(nodes) == 1
    assert nodes[0]["id"] == "phone-two"
    assert nodes[0]["status"] == "offline"
    assert nodes[0]["identity_status"] == "verified"
    assert nodes[0]["source"] == "accepted-invite"
    assert "token" not in json.dumps(nodes[0]).lower()


def test_d4_agent_registry_serializes_overlapping_device_updates(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from concurrent.futures import ThreadPoolExecutor
    from api_fastapi.services import fleet_registry

    def write_device(index: int):
        node_id = f"phone-{index}"
        return fleet_registry.upsert_agent(
            {
                "node_id": node_id,
                "hostname": f"Phone {index}",
                "role": "compute",
                "status": "online",
                "heartbeat_at": NOW_ISO,
            },
            event_type="fleet.node_heartbeat",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_device, range(20)))

    agents = fleet_registry.list_agents(include_stale=True)
    assert {item["node_id"] for item in agents} == {f"phone-{index}" for index in range(20)}
    from api_fastapi import deps
    payload = deps.core.read_json_file(
        deps.settings().state_dir / "fleet_device_events.json", {"events": []}
    )
    first_heartbeats = [
        item for item in payload.get("events", [])
        if item.get("event_type") == "first_heartbeat_received"
    ]
    assert len(first_heartbeats) == 20


def test_d4_background_health_sweep_uses_low_power_safe_configurable_deadline(monkeypatch):
    ensure_runtime_path()
    from types import SimpleNamespace
    from api_fastapi.routers import lite

    captured = {}

    def prepared_read(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(source_revision=9, projection_age_ms=0, read_degraded=False)

    monkeypatch.setenv("POCKETLAB_DEVICE_HEALTH_SWEEP_DEADLINE_SECONDS", "20")
    monkeypatch.setattr(lite.CONTROL_PLANE, "prepared_read", prepared_read)

    result = lite._refresh_device_health_projection()

    assert captured["deadline_seconds"] == 20.0
    assert captured["cold_start_async"] is False
    assert result["source_revision"] == 9
