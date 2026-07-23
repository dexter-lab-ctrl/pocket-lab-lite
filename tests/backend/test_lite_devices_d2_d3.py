from __future__ import annotations

import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_runtime_path()
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    reset_sqlite_path_cache()


def _offline_device() -> dict:
    return {
        "id": "old-phone",
        "name": "Old Phone",
        "role": "compute",
        "status": "offline",
        "connection": "offline",
        "agent_status": "offline",
        "supervisor_status": "offline",
        "agent_process_status": "stopped",
        "last_seen_at": "2025-01-01T00:00:00Z",
        "last_heartbeat_at": "2025-01-01T00:00:00Z",
        "first_heartbeat_at": "2024-12-01T00:00:00Z",
        "identity_status": "verified",
        "identity_verified_at": "2024-12-01T00:00:01Z",
        "advertised_capabilities": ["receive_commands", "run_safety_checks"],
    }


def test_d2_waiting_enrollment_and_identity_mismatch_are_fail_closed():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    context = {
        "invites": [{
            "invite_id": "invite-1",
            "hostname": "Phone Two",
            "node_id": "phone-two",
            "status": "accepted",
            "accepted_at": "2026-07-23T08:00:00Z",
            "created_at": "2026-07-23T07:55:00Z",
        }],
        "events": [{
            "event_type": "pocketlab.events.fleet.bootstrap_blocked",
            "node_id": "phone-two",
            "occurred_at": "2026-07-23T08:01:00Z",
            "reason_code": "invite_identity_mismatch",
            "summary": "A mismatched join attempt was blocked.",
            "token": "must-never-leak",
        }],
        "hosted_apps": {},
        "backup_dependencies": {},
    }
    device = enrich_device({
        "id": "phone-two",
        "name": "Phone Two",
        "role": "compute",
        "status": "waiting",
        "connection": "waiting",
    }, context=context, commands=[])

    assert device["identity_status"] == "join_blocked"
    assert device["enrollment_status"] == "join_blocked"
    assert device["identity"]["repair_required"] is True
    assert device["removal_assessment"]["safe_to_remove"] is False
    serialized = json.dumps(device).lower()
    assert "must-never-leak" not in serialized
    assert "invite_identity_mismatch" in serialized


def test_d3_capabilities_are_verified_not_inferred_from_role():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device({
        **_offline_device(),
        "status": "online",
        "connection": "online",
        "agent_process_status": "online",
        "supervisor_status": "healthy",
        "advertised_capabilities": ["receive_commands", "run_safety_checks"],
    }, context={"invites": [], "events": [], "hosted_apps": {}, "backup_dependencies": {}}, commands=[])
    capabilities = {item["id"]: item for item in device["capability_states"]}

    assert capabilities["receive_commands"]["status"] == "ready"
    assert capabilities["run_safety_checks"]["status"] == "available"
    assert capabilities["host_apps"]["status"] == "unknown"
    assert capabilities["provide_storage"]["status"] == "unknown"
    assert all("token" not in json.dumps(item).lower() for item in device["capability_states"])


def test_d2_d3_projection_is_change_only_bounded_and_revision_fenced(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import (
        ControlPlaneProjectionStore,
        DeviceAwarenessError,
    )
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device(
        _offline_device(),
        context={
            "invites": [],
            "events": [{
                "event_type": "device_returned_online",
                "node_id": "old-phone",
                "occurred_at": "2025-01-01T00:00:00Z",
                "summary": "Device activity recorded.",
            }],
            "hosted_apps": {},
            "backup_dependencies": {},
        },
        commands=[],
    )
    payload = {
        "status": "healthy",
        "devices": [device],
        "remote_access": {"ready": False, "status": "not_ready"},
        "latest_invite": None,
        "updated_at": "2026-07-23T08:00:00Z",
    }
    store = ControlPlaneProjectionStore()
    first = store.project_fleet(payload)
    second = store.project_fleet(payload)
    assert first == 1
    assert second == first

    details = store.device_details("old-phone")
    awareness_revision = details["device"]["awareness_revision"]
    assessment = store.device_removal_assessment("old-phone")
    assert assessment["safe_to_remove"] is True
    assert assessment["offline_authorization"] is False
    assert assessment["awareness_revision"] == awareness_revision
    assert "assessed_at" not in assessment

    validated = store.validate_device_removal_assessment(
        "old-phone",
        assessment_revision=assessment["assessment_revision"],
        expected_awareness_revision=awareness_revision,
    )
    assert validated["safe_to_remove"] is True

    with pytest.raises(DeviceAwarenessError) as stale:
        store.validate_device_removal_assessment(
            "old-phone",
            assessment_revision="stale-assessment",
            expected_awareness_revision=awareness_revision,
        )
    assert stale.value.status_code == 409

    history = store.device_lifecycle_history("old-phone", limit=10)
    assert history["items"]
    assert all(item["sanitized"] for item in history["items"])
    assert "token" not in json.dumps(history).lower()




def test_d2_d3_focused_device_reads_support_etag_and_304(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi import deps

    deps.core.write_json_file(deps.settings().state_dir / "fleet.json", [_offline_device()])
    fleet_response = client().get("/api/lite/fleet")
    assert fleet_response.status_code == 200

    details = client().get("/api/lite/devices/old-phone")
    assert details.status_code == 200
    assert details.headers.get("etag")
    assert details.headers.get("cache-control") == "no-cache"
    details_304 = client().get(
        "/api/lite/devices/old-phone",
        headers={"If-None-Match": details.headers["etag"]},
    )
    assert details_304.status_code == 304

    history = client().get("/api/lite/devices/old-phone/history?limit=20")
    assert history.status_code == 200
    assert history.headers.get("etag")
    history_304 = client().get(
        "/api/lite/devices/old-phone/history?limit=20",
        headers={"If-None-Match": history.headers["etag"]},
    )
    assert history_304.status_code == 304

def test_d2_d3_query_plans_use_targeted_indexes(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device(
        _offline_device(),
        context={
            "invites": [],
            "events": [{
                "event_type": "device_offline",
                "node_id": "old-phone",
                "occurred_at": "2025-01-01T00:00:00Z",
                "summary": "Device went offline.",
            }],
            "hosted_apps": {},
            "backup_dependencies": {},
        },
        commands=[],
    )
    ControlPlaneProjectionStore().project_fleet({
        "status": "healthy",
        "devices": [device],
        "remote_access": {"ready": False, "status": "not_ready"},
        "latest_invite": None,
        "updated_at": "2026-07-23T08:00:00Z",
    })

    with read_connection() as conn:
        lifecycle_plan = " ".join(
            str(row["detail"])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN "
                "SELECT event_id FROM device_lifecycle_events "
                "WHERE device_id=? ORDER BY occurred_at_epoch_ms DESC,event_id DESC LIMIT 20",
                ("old-phone",),
            )
        )
        staleness_plan = " ".join(
            str(row["detail"])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN "
                "SELECT device_id FROM device_awareness_state "
                "WHERE staleness_state=? ORDER BY last_seen_at_epoch_ms ASC LIMIT 20",
                ("stale",),
            )
        )
        removal_plan = " ".join(
            str(row["detail"])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN "
                "SELECT device_id FROM device_awareness_state "
                "WHERE removal_safe=1 ORDER BY last_seen_at_epoch_ms ASC LIMIT 20"
            )
        )

    assert "idx_device_lifecycle_device_time" in lifecycle_plan
    assert "idx_device_awareness_staleness" in staleness_plan
    assert "idx_device_awareness_removal" in removal_plan
    assert "TEMP B-TREE" not in lifecycle_plan
    assert "TEMP B-TREE" not in staleness_plan
    assert "TEMP B-TREE" not in removal_plan

def test_d2_d3_frontend_uses_focused_reads_xstate_and_safe_removal_fence():
    devices = Path("src/lite/LiteDevices.jsx").read_text()
    details = Path("src/lite/devices/DeviceDetailsLazy.jsx").read_text()
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text()
    card = Path("src/lite/devices/DeviceCard.jsx").read_text()
    api = Path("src/lib/liteApi.js").read_text()
    keys = Path("src/lib/liteQueryClient.js").read_text()
    machine = Path("src/machines/liteDeviceRemovalMachine.js").read_text()
    css = Path("src/index.css").read_text()

    assert "deviceRemovalAssessment" in api
    assert "deviceHistory" in api
    assert "liteQueryKeys.device(initialDeviceId)" in details
    assert "DEVICE_DETAILS_SNAPSHOT_PATH_PATTERN" in snapshots
    assert "DEVICE_HISTORY_SNAPSHOT_PATH_PATTERN" in snapshots
    assert "deviceRemovalAssessment" in keys
    assert "expected_awareness_revision" in devices
    assert "assessment_revision" in devices
    assert "useLiteDeviceRemovalFlow" in devices
    assert "liteDeviceRemovalFlow" in machine
    assert "removal_assessment" in card
    assert "Device trust" in details
    assert "Device capabilities" in details
    assert "Device dependencies" in details
    assert "DEVICE_DETAILS_HISTORY_IS_LAZY" in details
    assert "lite-device-awareness-grid" in css
    assert "navigator.shell" not in devices
    assert "nats://" not in details + card
