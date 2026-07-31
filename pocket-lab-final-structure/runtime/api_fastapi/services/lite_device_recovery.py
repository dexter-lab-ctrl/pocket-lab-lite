from __future__ import annotations

from typing import Any


_SERVICE_IDS = frozenset({"node_agent", "agent_supervisor"})
_RESTARTABLE_AGENT_STATES = frozenset(
    {"stopped", "offline", "errored", "error", "failed", "unhealthy", "unknown"}
)


def _text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").strip().split())
    return "".join(ch for ch in text if ord(ch) >= 32 and ord(ch) != 127)[:limit]


def guarded_recovery_contract(device: dict[str, Any]) -> dict[str, Any]:
    """Return the sanitized, current guarded-recovery contract for one device.

    This function intentionally derives action authorization from current projection
    truth. Persisted copies are display evidence only and must be recomputed on every
    prepared read before they are returned to clients.
    """

    connection = _text(device.get("connection") or "unknown", 32).lower()
    role = _text(device.get("role"), 40).lower()
    is_server = role == "server_host" or bool(device.get("is_current") or device.get("protected_server_host"))
    agent_state = _text(
        device.get("agent_process_status") or device.get("agent_status") or "unknown", 32
    ).lower()
    supervisor_state = _text(device.get("supervisor_status") or "unknown", 32).lower()
    supervisor_freshness = _text(
        device.get("supervisor_status_freshness") or "unknown", 32
    ).lower()
    supervisor_fresh = supervisor_freshness == "fresh" or (
        is_server and supervisor_freshness == "saved"
    )
    command_deliverable = connection == "online" and not is_server
    restart_needed = agent_state in _RESTARTABLE_AGENT_STATES

    if is_server:
        reason_code = "server_host_protected"
        summary = "The protected server host uses local guarded recovery."
    elif connection != "online":
        reason_code = "device_unreachable"
        summary = "Reconnect the device before Pocket Lab can send a restart command."
    elif not supervisor_fresh:
        reason_code = "supervisor_report_stale"
        summary = "Wait for a fresh supervisor report before starting recovery."
    elif not restart_needed:
        reason_code = "agent_already_running"
        summary = "The device agent is already reporting as running."
    else:
        reason_code = "allowed"
        summary = "Pocket Lab can request a guarded device-agent restart."

    allowed = reason_code == "allowed"
    supervisor_reported_at = _text(
        device.get("last_supervisor_heartbeat_at") or device.get("last_supervisor_at"), 64
    ) or None
    agent_reported_at = _text(
        device.get("last_heartbeat_at") or device.get("last_seen_at") or device.get("last_seen"), 64
    ) or None
    supervisor_service_freshness = "fresh" if supervisor_fresh and connection == "online" else "stale"

    services = [
        {
            "service_id": "node_agent",
            "label": "Device agent",
            "manager": "pm2",
            "state": agent_state,
            "reported_at": agent_reported_at,
            "freshness": "fresh" if connection == "online" else "stale",
            "restart_supported": allowed,
            "restart_reason": reason_code,
        },
        {
            "service_id": "agent_supervisor",
            "label": "Recovery supervisor",
            "manager": "pm2",
            "state": supervisor_state,
            "reported_at": supervisor_reported_at,
            "freshness": supervisor_service_freshness,
            "restart_supported": False,
            "restart_reason": "not_remotely_restartable",
        },
    ]

    # Keep the schema bounded and stable even if this function is extended later.
    services = [item for item in services if item.get("service_id") in _SERVICE_IDS][:8]
    return {
        "restart_agent_assessment": {
            "allowed": allowed,
            "reason_code": reason_code,
            "summary": summary,
            "command_deliverable": command_deliverable,
            "supervisor_fresh": supervisor_fresh,
            "agent_state": agent_state,
        },
        "runtime_services": services,
    }
