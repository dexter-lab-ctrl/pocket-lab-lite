from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from . import lite_device_runtime_projection, lite_runtime_services


_RESTARTABLE_AGENT_STATES = frozenset(
    {"stopped", "offline", "errored", "error", "failed", "unhealthy", "unknown"}
)
_SERVICE_CURRENT_SECONDS = 180
_SECRETISH_SERVICE_TEXT = re.compile(
    r"(?:token|password|passwd|secret|credential|api[_-]?key|private[_-]?key|"
    r"authorization|bearer\s+|nats://|https?://[^\s/@]+:[^\s/@]+@|"
    r"(?:^|\s)(?:/data/data/|/home/|/mnt/|/root/|~[/\\]))",
    re.IGNORECASE,
)


def _text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").strip().split())
    return "".join(ch for ch in text if ord(ch) >= 32 and ord(ch) != 127)[:limit]


def _service_text(value: Any, limit: int, fallback: str = "") -> str:
    text = _text(value, limit)
    if not text or _SECRETISH_SERVICE_TEXT.search(text):
        return fallback
    return text


def _service_freshness(reported_at: Any, supplied: Any = None) -> str:
    reported = _text(reported_at, 64)
    if not reported:
        supplied_text = _text(supplied, 24).lower()
        return "stale" if supplied_text in {"stale", "saved"} else "missing"
    try:
        observed = datetime.fromisoformat(reported.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds())
        return "current" if age <= _SERVICE_CURRENT_SECONDS else "stale"
    except (TypeError, ValueError):
        supplied_text = _text(supplied, 24).lower()
        return "stale" if supplied_text in {"stale", "saved"} else "missing"


def _explicit_agent_supervisor_services(
    device: dict[str, Any], *, allowed: bool, is_server: bool
) -> list[dict[str, Any]]:
    """Adapt explicit agent/supervisor status fields into service evidence.

    This is compatibility projection, not topology inference: a row is emitted
    only when the device actually reports the corresponding process/status field.
    """
    rows: list[dict[str, Any]] = []
    agent_raw = device.get("agent_process_status")
    if agent_raw in (None, ""):
        agent_raw = device.get("agent_status")
    if agent_raw not in (None, ""):
        reported_at = device.get("last_heartbeat_at") or device.get("last_seen_at") or device.get("last_seen")
        rows.append({
            "service_id": "node_agent",
            "label": "Device Agent",
            "category": "agent",
            "manager": "agent_runtime",
            "state": _text(agent_raw, 32).lower(),
            "reported_at": reported_at,
            "freshness": _service_freshness(reported_at, device.get("agent_version_freshness")),
            "restart_supported": bool(allowed and not is_server),
            "restart_reason": "allowed" if allowed and not is_server else "protected_runtime_service" if is_server else "guarded_recovery_not_allowed",
            "source": "device_agent_status_evidence",
            "schema_version": 1,
            "sanitized": True,
        })

    supervisor_raw = device.get("supervisor_process_status")
    if supervisor_raw in (None, ""):
        supervisor_raw = device.get("supervisor_status")
    if supervisor_raw not in (None, ""):
        reported_at = device.get("last_supervisor_heartbeat_at") or device.get("last_supervisor_at")
        rows.append({
            "service_id": "agent_supervisor",
            "label": "Recovery Supervisor",
            "category": "supervisor",
            "manager": "supervisor_runtime",
            "state": _text(supervisor_raw, 32).lower(),
            "reported_at": reported_at,
            "freshness": _service_freshness(reported_at, device.get("supervisor_status_freshness")),
            "restart_supported": False,
            "restart_reason": "protected_runtime_service" if is_server else "device_service_display_only",
            "source": "device_supervisor_status_evidence",
            "schema_version": 1,
            "sanitized": True,
        })
    return rows


def guarded_recovery_contract(device: dict[str, Any]) -> dict[str, Any]:
    """Return the sanitized, current guarded-recovery contract for one device.

    This function intentionally derives action authorization from current projection
    truth. Persisted copies are display evidence only and must be recomputed on every
    prepared read before they are returned to clients. Runtime extension installation
    is owned by FastAPI startup, never by this read-side function.
    """

    original_device = dict(device) if isinstance(device, dict) else {}
    device = lite_device_runtime_projection.enrich_device(original_device)

    connection = _text(device.get("connection") or "unknown", 32).lower()
    role = _text(device.get("role"), 40).lower()
    is_server = role == "server_host" or bool(device.get("is_current") or device.get("protected_server_host"))
    agent_state = _text(
        device.get("agent_process_status") or device.get("agent_status") or "unknown", 32
    ).lower()
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

    observed_services = (
        device.get("_runtime_service_evidence")
        if isinstance(device.get("_runtime_service_evidence"), list)
        else device.get("runtime_services")
        if isinstance(device.get("runtime_services"), list)
        else []
    )
    services: list[dict[str, Any]] = []
    seen_services: set[str] = set()
    for raw in observed_services[:24]:
        if not isinstance(raw, dict):
            continue
        service = lite_runtime_services.sanitize_runtime_service(
            raw, source="prepared_device_service_evidence"
        )
        if not service or service["service_id"] in seen_services:
            continue
        seen_services.add(service["service_id"])
        service["restart_supported"] = False
        service["restart_reason"] = (
            "protected_runtime_service" if is_server else "device_service_display_only"
        )
        services.append(service)

    # Preserve compatibility for devices that report agent/supervisor status
    # but not the newer runtime_services array. These rows are backed by those
    # explicit status observations and therefore remain device-specific evidence.
    if not services:
        for service in _explicit_agent_supervisor_services(
            original_device, allowed=allowed, is_server=is_server
        ):
            if service["service_id"] not in seen_services:
                seen_services.add(service["service_id"])
                services.append(service)

    return {
        "restart_agent_assessment": {
            "allowed": allowed,
            "reason_code": reason_code,
            "summary": summary,
            "command_deliverable": command_deliverable,
            "supervisor_fresh": supervisor_fresh,
            "agent_state": agent_state,
        },
        "runtime_services": services[:24],
        "device_facts": device.get("device_facts") if isinstance(device.get("device_facts"), dict) else {},
        "resource_observations": device.get("resource_observations") if isinstance(device.get("resource_observations"), dict) else {},
        "capability_states": device.get("capability_states") if isinstance(device.get("capability_states"), list) else [],
        "dependencies": device.get("dependencies") if isinstance(device.get("dependencies"), dict) else {},
        "_health_signals": device.get("_health_signals") if isinstance(device.get("_health_signals"), dict) else {},
    }
