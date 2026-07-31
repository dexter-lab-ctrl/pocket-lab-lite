from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _configure_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    database = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    from api_fastapi.db.connection import reset_sqlite_path_cache

    reset_sqlite_path_cache()
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    return ControlPlaneProjectionStore()


def _iso(offset_seconds: int = 0) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    ).isoformat().replace("+00:00", "Z")


def test_supervisor_evidence_is_sqlite_owned_and_out_of_order_safe(tmp_path, monkeypatch):
    store = _configure_store(tmp_path, monkeypatch)
    current_at = _iso()
    current = store.record_supervisor_evidence({
        "node_id": "phone-two",
        "evidence_schema_version": 1,
        "supervisor_status": "healthy",
        "supervisor_version": "1.0.0-lite-agent-supervisor",
        "supervisor_process_status": "online",
        "agent_process_status": "online",
        "nats_reachable": True,
        "repair_result": "not_needed",
        "checked_at": current_at,
    })
    assert current["changed"] is True

    mapped = store.supervisor_state_map()["phone-two"]
    assert mapped["supervisor_status"] == "healthy"
    assert mapped["supervisor_process_status"] == "online"
    assert mapped["agent_process_status"] == "online"
    assert mapped["nats_reachable"] is True
    assert mapped["source"] == "sqlite_supervisor_evidence"

    stale = store.record_supervisor_evidence({
        "node_id": "phone-two",
        "supervisor_status": "stopped",
        "supervisor_process_status": "stopped",
        "agent_process_status": "stopped",
        "nats_reachable": False,
        "checked_at": _iso(-3600),
    })
    assert stale["changed"] is False
    assert stale["ignored_out_of_order"] is True
    assert store.supervisor_state_map()["phone-two"]["supervisor_status"] == "healthy"


def test_online_secondary_removal_is_guarded_not_prohibited():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    context = {"invites": [], "events": [], "hosted_apps": {}, "backup_dependencies": {}}
    device = {
        "id": "phone-two",
        "node_id": "phone-two",
        "name": "Phone Two",
        "role": "compute",
        "status": "online",
        "connection": "online",
        "identity_status": "verified",
        "first_heartbeat_at": _iso(-60),
        "last_heartbeat_at": _iso(),
        "last_seen_at": _iso(),
        "agent_process_status": "online",
        "supervisor_status": "healthy",
        "advertised_capabilities": ["receive_commands"],
    }
    enriched = enrich_device(device, context=context, commands=[])
    removal = enriched["removal_assessment"]
    assert removal["allowed"] is True
    assert removal["protected"] is False
    assert removal["policy"] == "confirmation_required"
    assert removal["confirmation_required"] is True
    assert any(item["code"] == "device_online" for item in removal["warnings"])
    assert removal["blockers"] == []


def test_server_host_remains_permanently_protected():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    context = {"invites": [], "events": [], "hosted_apps": {}, "backup_dependencies": {}}
    protected = enrich_device({
        "id": "pocket-lab-lite-server",
        "node_id": "pocket-lab-lite-server",
        "name": "Pocket Lab Lite Server",
        "role": "server_host",
        "status": "online",
        "connection": "online",
        "is_current": True,
        "last_heartbeat_at": _iso(),
        "advertised_capabilities": ["receive_commands", "serve_control_plane"],
    }, context=context, commands=[])
    removal = protected["removal_assessment"]
    assert removal["allowed"] is False
    assert removal["protected"] is True
    assert removal["policy"] == "protected"
    assert any(item["code"] == "protected_server_host" for item in removal["blockers"])


def test_capabilities_distinguish_advertised_verified_and_missing():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import verified_capabilities

    states = {
        item["id"]: item
        for item in verified_capabilities({
            "id": "phone-two",
            "role": "compute",
            "status": "online",
            "connection": "online",
            "agent_process_status": "online",
            "supervisor_status": "unknown",
            "advertised_capabilities": ["host_apps", "receive_commands"],
            "last_seen_at": _iso(),
        }, hosted_apps=[])
    }
    assert states["receive_commands"]["status"] == "verified"
    assert states["host_apps"]["status"] == "verification_pending"
    assert states["store_backups"]["status"] == "not_advertised"


def test_transport_and_history_contracts_are_bounded_and_truthful():
    root = Path(__file__).resolve().parents[2]
    agent = (root / "pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py").read_text(encoding="utf-8")
    supervisor = (root / "pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py").read_text(encoding="utf-8")
    virtual_list = (root / "src/lite/components/LiteVirtualList.jsx").read_text(encoding="utf-8")

    assert "async def connection_manager" in agent
    assert "max_reconnect_attempts\": 0" in agent
    assert "await self.publish_profile(force=True)" in agent
    assert "await self.publish_capabilities(critical=True)" in agent
    assert "if critical:" in agent and "await self.nc.flush(timeout=2)" in agent
    assert "await nc.drain()" not in supervisor
    assert "MAX_NATS_BACKOFF_SECONDS" in supervisor
    assert "Math.max(rows.length" in virtual_list


def test_nats_fanout_restores_transport_subject_for_external_agent_envelopes():
    root = Path(__file__).resolve().parents[2]
    source = (
        root
        / "pocket-lab-final-structure/runtime/api_fastapi/services/nats_bus.py"
    ).read_text(encoding="utf-8")
    assert 'event.setdefault("subject", str(getattr(msg, "subject", "") or ""))' in source
    assert 'event.setdefault("type", str(event.get("event_type") or ""))' in source
    assert 'event.setdefault("id", str(event.get("event_id") or ""))' in source


def test_device_merge_uses_freshest_runtime_timestamps():
    ensure_runtime_path()
    from api_fastapi.services.lite_status import _merge_lite_device

    merged = _merge_lite_device(
        {
            "id": "phone-two",
            "status": "online",
            "last_seen_at": "2026-06-23T12:58:33Z",
            "last_heartbeat_at": "2026-06-23T12:58:33Z",
            "last_capabilities_at": "2026-06-23T12:58:33Z",
        },
        {
            "id": "phone-two",
            "status": "online",
            "last_seen_at": "2026-07-31T09:56:02Z",
            "last_heartbeat_at": "2026-07-31T09:56:02Z",
            "last_capabilities_at": "2026-07-31T09:56:02Z",
        },
    )
    assert merged["last_seen_at"] == "2026-07-31T09:56:02Z"
    assert merged["last_heartbeat_at"] == "2026-07-31T09:56:02Z"
    assert merged["last_capabilities_at"] == "2026-07-31T09:56:02Z"


def test_supervisor_persistence_failures_are_not_silently_swallowed():
    root = Path(__file__).resolve().parents[2]
    source = (
        root
        / "pocket-lab-final-structure/runtime/api_fastapi/services/fleet_registry.py"
    ).read_text(encoding="utf-8")
    assert 'merged["supervisor_evidence_persisted"] = False' in source
    assert 'merged["supervisor_evidence_error_type"] = type(exc).__name__[:80]' in source
    assert "raise\n" in source
