from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database


@pytest.fixture(autouse=True)
def _quiesce_runtime_after_test():
    yield
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services.projection_scheduler import PROJECTION_SCHEDULER

    assert PROJECTION_SCHEDULER.quiesce_for_database_switch(timeout_seconds=5.0)
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    prepare_sqlite_test_database(target, monkeypatch)
    from api_fastapi.db.migrations import apply_migrations

    assert apply_migrations() == list(range(1, 23))
    return target


def _online_payload(device_id: str = "phone-two", name: str = "Phone Two") -> dict:
    return {
        "status": "healthy",
        "devices": [
            {
                "id": device_id,
                "node_id": device_id,
                "name": name,
                "role": "compute",
                "status": "healthy",
                "connection": "online",
                "agent_status": "online",
                "supervisor_status": "online",
                "agent_process_status": "online",
                "last_seen_at": "2026-07-30T08:00:00Z",
                "agent_version": "1.0.1",
                "supervisor_version": "1.0.1",
                "system_profile": {
                    "profile_schema_version": 1,
                    "os_family": "android",
                    "os_name": "Android",
                    "runtime_type": "termux",
                    "agent_version": "1.0.1",
                    "supervisor_version": "1.0.1",
                    "profile_status": "ready",
                    "profile_collected_at": "2026-07-30T08:00:00Z",
                },
                "capabilities": ["compute", "security_scanner"],
                "capability_labels": ["Compute", "Security Scanner"],
                "dependencies": {"hosted_app_count": 0, "backup_set_count": 0},
                "enrollment_status": "enrolled",
                "identity_status": "verified",
                "summary": "Device is online.",
            }
        ],
        "remote_access": {"ready": True, "status": "healthy"},
        "updated_at": "2026-07-30T08:00:00Z",
    }


def _row(database: Path, sql: str, params: tuple = ()) -> dict | None:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def test_missing_live_snapshot_retains_enrollment_and_projects_offline(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.project_fleet(_online_payload())
    enrolled = _row(database, "SELECT * FROM device_enrollment_registry WHERE device_id='phone-two'")
    assert enrolled and enrolled["removal_status"] == "active"
    assert enrolled["identity_status"] == "verified"

    store.project_fleet({
        "status": "degraded", "devices": [], "remote_access": {"ready": False},
        "updated_at": "2026-07-30T08:05:00Z",
    })

    current = _row(database, "SELECT * FROM device_current_state WHERE device_id='phone-two'")
    assert current and current["connection_state"] == "offline"
    assert current["agent_status"] == "offline"
    enrolled = _row(database, "SELECT * FROM device_enrollment_registry WHERE device_id='phone-two'")
    assert enrolled and enrolled["removal_status"] == "active"
    assert enrolled["last_known_state"] == "offline"

    snapshot = store.fleet_projection_snapshot()
    device = next(item for item in snapshot["devices"] if item["id"] == "phone-two")
    assert device["connection"] == "offline"
    assert device["staleness_state"] == "stale"
    assert device["command_delivery_status"] == "undeliverable"
    assert device["review_recommended"] is True
    assert device["system_profile"]["agent_version"] == "1.0.1"
    assert set(device["capability_labels"]) == {"Compute", "Security Scanner"}


def test_registry_survives_store_restart_and_blocks_cascade_delete(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    ControlPlaneProjectionStore().project_fleet(_online_payload())
    restarted = ControlPlaneProjectionStore()
    devices = restarted.durable_enrolled_devices()
    assert [item["id"] for item in devices] == ["phone-two"]

    conn = sqlite3.connect(database)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="retired explicitly"):
            conn.execute("DELETE FROM device_current_state WHERE device_id='phone-two'")
        conn.rollback()
    finally:
        conn.close()
    assert _row(database, "SELECT * FROM device_system_profiles WHERE node_id='phone-two'")


def test_legacy_command_reconciliation_is_command_only(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.project_fleet(_online_payload())
    store.project_fleet({
        "status": "degraded", "devices": [], "remote_access": {"ready": False},
        "updated_at": "2026-07-30T08:05:00Z",
    })
    conn = sqlite3.connect(database)
    try:
        conn.execute(
            """INSERT INTO command_lifecycle(
                command_id,entity_type,entity_id,operation_type,status,created_at,updated_at,
                updated_at_epoch_ms,source_ref,summary,metadata_json,lifecycle_stage
            ) VALUES('stale-restart','device','phone-two','agent.restart','queued',
                     '2026-07-30T07:00:00Z','2026-07-30T07:00:00Z',1,'test','queued','{}','accepted')"""
        )
        conn.commit()
    finally:
        conn.close()

    result = store.reconcile_command_lifecycle(
        now_epoch_ms=10_000_000, legacy_max_age_seconds=60,
        missing_target_grace_seconds=30,
    )
    command = _row(database, "SELECT * FROM command_lifecycle WHERE command_id='stale-restart'")
    assert result["reconciled_count"] == 1
    assert command["status"] == "undeliverable"
    assert command["recovery_action"] == "legacy_orphan_reconciled"
    assert _row(database, "SELECT * FROM device_enrollment_registry WHERE device_id='phone-two'")["removal_status"] == "active"
    assert _row(database, "SELECT * FROM device_current_state WHERE device_id='phone-two'")["connection_state"] == "offline"


def test_explicit_retirement_hides_active_device_and_retains_history(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.project_fleet(_online_payload())
    store.project_fleet({
        "status": "degraded", "devices": [], "remote_access": {"ready": False},
        "updated_at": "2026-07-30T08:05:00Z",
    })
    result = store.retire_enrolled_device(
        "phone-two", reason_code="confirmed_stale_device_cleanup",
        assessment_revision="assessment-1", awareness_revision=1,
    )
    assert result["changed"] is True
    assert result["receipt"]["sanitized"] == 1
    assert store.durable_enrolled_devices() == []
    assert _row(database, "SELECT * FROM device_current_state WHERE device_id='phone-two'")["connection_state"] == "removed"
    assert _row(database, "SELECT * FROM device_system_profiles WHERE node_id='phone-two'")
    assert _row(database, "SELECT * FROM device_removal_receipts WHERE device_id='phone-two'")
    lifecycle = _row(database, "SELECT * FROM device_lifecycle_events WHERE device_id='phone-two' AND event_type='removal_completed'")
    assert lifecycle and lifecycle["sanitized"] == 1
    assert _row(database, "SELECT * FROM device_enrollment_registry WHERE device_id='phone-two'")["removal_status"] == "removed"



def test_full_disconnect_restart_reconnect_and_explicit_removal_acceptance_sequence(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    # Enroll and observe the device online.
    store = ControlPlaneProjectionStore()
    store.project_fleet(_online_payload())
    online = next(item for item in store.fleet_projection_snapshot()["devices"] if item["id"] == "phone-two")
    assert online["connection"] == "online"

    # Tailscale/NATS discovery disappears beyond the stale boundary. Enrollment
    # remains durable and a new API/worker process instance still reads it.
    store.project_fleet({
        "status": "degraded", "devices": [], "remote_access": {"ready": False},
        "updated_at": "2026-07-30T09:00:00Z",
    })
    after_api_restart = ControlPlaneProjectionStore()
    offline = next(
        item for item in after_api_restart.fleet_projection_snapshot()["devices"]
        if item["id"] == "phone-two"
    )
    assert offline["connection"] == "offline"
    assert offline["staleness_state"] == "stale"
    assert offline["command_delivery_status"] == "undeliverable"

    # A fresh process after a simulated worker/server restart sees the same row.
    after_worker_restart = ControlPlaneProjectionStore()
    assert [item["id"] for item in after_worker_restart.durable_enrolled_devices()] == ["phone-two"]

    # The same canonical identity reconnects without creating a duplicate record.
    reconnect = _online_payload()
    reconnect["devices"][0]["last_seen_at"] = "2026-07-30T09:05:00Z"
    reconnect["devices"][0]["agent_version"] = "1.0.2"
    reconnect["devices"][0]["system_profile"]["agent_version"] = "1.0.1"
    after_worker_restart.project_fleet(reconnect)
    reconnected = next(
        item for item in after_worker_restart.fleet_projection_snapshot()["devices"]
        if item["id"] == "phone-two"
    )
    assert reconnected["connection"] == "online"
    assert _row(database, "SELECT COUNT(*) AS count FROM device_enrollment_registry")["count"] == 1

    # A second disconnect still retains history until an explicit guarded removal.
    after_worker_restart.project_fleet({
        "status": "degraded", "devices": [], "remote_access": {"ready": False},
        "updated_at": "2026-07-30T09:10:00Z",
    })
    removal = after_worker_restart.retire_enrolled_device(
        "phone-two", reason_code="confirmed_stale_device_cleanup",
        assessment_revision="assessment-acceptance", awareness_revision=4,
    )
    assert removal["changed"] is True
    assert after_worker_restart.durable_enrolled_devices() == []
    assert _row(database, "SELECT * FROM device_removal_receipts WHERE device_id='phone-two'")
    assert _row(database, "SELECT * FROM device_lifecycle_events WHERE device_id='phone-two'")
    assert _row(database, "SELECT * FROM device_enrollment_registry WHERE device_id='phone-two'")["removal_status"] == "removed"


def test_protected_server_host_registry_is_non_removable(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore, DeviceAwarenessError

    store = ControlPlaneProjectionStore()
    payload = _online_payload(device_id="pocket-lab-lite-server", name="Pocket Lab Lite Server")
    payload["devices"][0].update({
        "role": "server_host", "is_current": True, "protected_server_host": True,
    })
    store.project_fleet(payload)

    with pytest.raises(DeviceAwarenessError, match="protected server host"):
        store.retire_enrolled_device(
            "pocket-lab-lite-server", reason_code="invalid_attempt",
            assessment_revision="protected", awareness_revision=1,
        )
    assert store.durable_enrolled_devices()[0]["protected_server_host"] is True

def test_separator_insensitive_duplicate_and_retired_identity_reuse_fail_closed(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.project_fleet(_online_payload(device_id="phone-one", name="Pocket Phone"))
    duplicate = _online_payload(device_id="phone-two", name="pocket_phone")
    with pytest.raises(ValueError, match="explicit repair/rejoin"):
        store.project_fleet(duplicate)


def test_frontend_device_count_and_role_contracts_are_connection_based():
    repo = Path(__file__).resolve().parents[2]
    devices = (repo / "src/lite/LiteDevices.jsx").read_text(encoding="utf-8")
    card = (repo / "src/lite/devices/DeviceCard.jsx").read_text(encoding="utf-8")
    view_models = (repo / "src/lib/liteViewModels.js").read_text(encoding="utf-8")
    ui = (repo / "src/lite/LiteUi.jsx").read_text(encoding="utf-8")

    assert "String(device?.connection || '').toLowerCase() === 'online'" in devices
    assert "String(device?.connection || '').toLowerCase() === 'online'" in card
    assert "normalizeDeviceStatus(device.connection) === 'online'" in view_models
    assert "const devices = Array.isArray(payload?.devices) ? payload.devices : [];" in view_models
    assert "if (String(value || '').toLowerCase() === 'server_host') return 'Server host';" in ui
    assert devices.count("<LiteRefreshButton scope=\"devices\"") == 1


def test_runtime_version_precedence_is_explicit_and_sanitized():
    ensure_runtime_path()
    from datetime import datetime, timezone
    from api_fastapi.services.lite_status import _lite_device_from_node

    device = _lite_device_from_node({
        "id": "phone-two", "name": "Phone Two", "role": "compute",
        "status": "active", "agent_status": "active", "agent_version": "1.0.1",
        "supervisor_version": "1.0.1",
        "system_profile": {"agent_version": "1.0.0", "supervisor_version": "1.0.0"},
    })
    assert device["system_profile"]["agent_version"] == "1.0.1"
    assert device["agent_version_source"] == "runtime_heartbeat"
    assert device["agent_version_freshness"] == "fresh"

    fresh_profile = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    offline = _lite_device_from_node({
        "id": "phone-three", "name": "Phone Three", "role": "compute",
        "status": "offline", "agent_status": "offline", "agent_version": "1.0.0",
        "supervisor_version": "1.0.0",
        "system_profile": {
            "agent_version": "2.0.0", "supervisor_version": "2.0.0",
            "collected_at": fresh_profile,
        },
    })
    assert offline["agent_version"] == "2.0.0"
    assert offline["agent_version_source"] == "system_profile"
    assert offline["agent_version_freshness"] == "fresh"
    assert offline["system_profile"]["agent_version"] == "2.0.0"
    assert "token" not in json.dumps({"online": device, "offline": offline}).lower()


def test_protected_host_uses_prepared_local_process_truth_only(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b
    from api_fastapi.services.lite_status import _server_host_device

    monkeypatch.setenv("POCKETLAB_NODE_ID", "pocket-lab-lite-server")
    snapshots = {
        "system.processes": {
            "updated_at": "2026-07-30T10:00:00Z",
            "items": [
                {"name": "pocket-node-agent", "status": "online"},
                {"name": "pocketlab-core-supervisor", "status": "online"},
            ],
        },
        "system.agent": {
            "updated_at": "2026-07-30T10:00:00Z",
            "items": [{"device_id": "pocket-lab-lite-server", "process_status": "online"}],
        },
        "system.supervisor": {
            "updated_at": "2026-07-30T10:00:00Z",
            "items": [{
                "device_id": "pocket-lab-lite-server", "supervisor_status": "healthy"
            }],
        },
    }
    monkeypatch.setattr(phase3b, "snapshot", lambda domain: snapshots.get(domain, {}))
    server = _server_host_device({
        "ready": False, "status": "not_ready", "running": False,
        "nats_reachable": False, "summary": "Remote access not ready",
    })
    assert server["agent_process_status"] == "online"
    assert server["agent_process_status_source"] == "protected_host_pm2_projection"
    assert server["supervisor_status"] == "healthy"
    assert server["supervisor_status_source"] == "protected_host_supervisor_projection"
    assert server["recovery_available"] is True
    assert server["last_supervisor_heartbeat_at"] == "2026-07-30T10:00:00Z"


def test_supervisor_recovery_evidence_is_immediate_and_sanitized():
    repo = Path(__file__).resolve().parents[2]
    source = (repo / "pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py").read_text(encoding="utf-8")
    assert '"repair_reason_code": repair_reason_code' in source
    assert '"repair_result": "recovered" if repaired' in source
    assert '"repair_started_at": repair_started_at or None' in source
    assert '"repair_completed_at": repair_completed_at or None' in source
    assert '"error_type": type(exc).__name__' in source
    assert '"error": str(exc)' not in source
    assert 'await self._publish_status(payload)' in source


def test_unchanged_projection_generations_converge_without_false_staleness():
    repo = Path(__file__).resolve().parents[2]
    scheduler = (repo / "pocket-lab-final-structure/runtime/api_fastapi/services/projection_scheduler.py").read_text(encoding="utf-8")
    store = (repo / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py").read_text(encoding="utf-8")
    assert 'elif outcome in {"unchanged", "source_unchanged"}:' in scheduler
    assert 'state.committed_generation = max(state.committed_generation, generation)' in scheduler
    assert 'refresh_pending = bool(\n            refresh_status.get("dirty")' in store
    assert 'generation mismatch can survive a process restart' in store
