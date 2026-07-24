from __future__ import annotations

import hashlib
import json
import os
import re
import time
import threading
from pathlib import Path
from typing import Any, Dict, List

from .. import deps

AGENT_TTL_SECONDS = int(os.environ.get("POCKETLAB_FLEET_AGENT_TTL_SECONDS", "90"))
COMMAND_TTL_SECONDS = int(os.environ.get("POCKETLAB_FLEET_COMMAND_TTL_SECONDS", "3600"))
SUPERVISOR_TTL_SECONDS = int(os.environ.get("POCKETLAB_FLEET_SUPERVISOR_TTL_SECONDS", "180"))
_AGENT_REGISTRY_LOCK = threading.RLock()
_PROFILE_TEXT_FIELDS = (
    "os_family", "os_name", "os_version", "security_patch", "manufacturer",
    "technical_model", "device_codename", "architecture", "android_abi", "kernel",
    "runtime_type", "termux_version", "python_version", "agent_version",
    "profile_fingerprint", "collection_status", "collected_at",
)
_HEALTH_FLOAT_FIELDS = ("load_average_1m", "load_average_5m", "load_average_15m")
_CONTROL_TEXT_RE = re.compile(r"[\x00-\x1f\x7f]")


class DeviceRemovalError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _protected_server_ids() -> set[str]:
    values = {
        "pocket-lab-lite-server",
        normalize_node_id(os.environ.get("POCKETLAB_NODE_ID") or ""),
        normalize_node_id(os.environ.get("POCKETLAB_DEVICE_NAME") or ""),
    }
    return {value for value in values if value and value != "unknown-node"}


def _record_identity_keys(record: Dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field in ("id", "node_id", "hostname", "name"):
        value = record.get(field)
        if value:
            keys.update(_identity_variants(str(value)))
    return {key for key in keys if key and key != "unknown-node"}


def _role_value(record: Dict[str, Any]) -> str:
    return str(record.get("role") or record.get("role_label") or "").strip().lower().replace("-", "_").replace(" ", "_")


def _connection_for_status(status: str) -> str:
    value = str(status or "unknown").strip().lower()
    if value in {"healthy", "active", "online", "ready"}:
        return "online"
    if value in {"joining", "accepted", "setup_started"}:
        return "joining"
    if value in {"invited", "pending", "invite_sent"}:
        return "waiting"
    if value in {"unhealthy", "offline", "failed", "stale", "degraded"}:
        return "offline"
    return "unknown"


def _candidate_status(record: Dict[str, Any], *, from_agent: bool = False) -> str:
    if from_agent:
        return _derive_status(record)
    return str(record.get("connection") or record.get("status") or record.get("agent_status") or "unknown").strip().lower()


def _is_protected_device(record: Dict[str, Any], wanted: str) -> str | None:
    keys = _record_identity_keys(record) | {wanted}
    role = _role_value(record)
    if keys.intersection(_protected_server_ids()):
        return "Cannot remove the current Pocket Lab Lite server device."
    if role in {"server_host", "server", "control_plane", "control_plane_host"}:
        return "Cannot remove the Pocket Lab Lite server host."
    if bool(record.get("is_current") or record.get("isCurrent") or record.get("is_control_plane")):
        return "Cannot remove the current Pocket Lab Lite device."
    return None


def _is_online_or_healthy_status(status: str) -> bool:
    return str(status or "").strip().lower() in {
        "active",
        "healthy",
        "online",
        "ready",
        "success",
        "succeeded",
    }


def _device_conflict_payload(
    record: Dict[str, Any],
    *,
    status: str | None = None,
    source: str = "fleet",
) -> Dict[str, Any]:
    resolved_status = str(status or _candidate_status(record)).strip().lower()
    role = record.get("role") or "compute"
    is_current = bool(record.get("is_current") or record.get("isCurrent") or record.get("is_control_plane"))
    return {
        "device_id": record.get("id") or record.get("node_id") or record.get("hostname") or record.get("name"),
        "device_name": record.get("name") or record.get("hostname") or record.get("node_id") or record.get("id"),
        "role": role,
        "status": "healthy" if resolved_status == "active" else resolved_status,
        "connection": _connection_for_status(resolved_status),
        "is_current": is_current,
        "source": source,
        "can_remove_old_record": (
            not is_current
            and _role_value({"role": role}) not in {"server_host", "server", "control_plane", "control_plane_host"}
            and not _is_online_or_healthy_status(resolved_status)
        ),
    }


def find_device_identity_conflict(device_name: str | None) -> Dict[str, Any] | None:
    wanted = normalize_node_id(device_name)
    wanted_keys = _identity_variants(device_name)
    if not wanted_keys:
        return None

    protected_names = _protected_server_ids() | {
        normalize_node_id("Pocket Lab Lite Server"),
        normalize_node_id(os.environ.get("POCKETLAB_DEVICE_NAME") or ""),
    }
    if wanted_keys.intersection({value for value in protected_names if value and value != "unknown-node"}):
        return _device_conflict_payload(
            {
                "id": "pocket-lab-lite-server",
                "name": os.environ.get("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server"),
                "role": "server_host",
                "status": "healthy",
                "is_current": True,
            },
            status="healthy",
            source="lite-server",
        )

    for agent in list_agents(include_stale=True):
        if isinstance(agent, dict) and _candidate_matches(agent, wanted_keys):
            return _device_conflict_payload(
                agent,
                status=str(agent.get("status") or _derive_status(agent)),
                source="fleet_agents.json",
            )

    for source_name, list_key in (("fleet.json", None), ("fleet_pending.json", "nodes")):
        path = _state_path(source_name)
        if not path.exists():
            continue
        payload = _read(path, {list_key: []} if list_key else [])
        records = payload.get(list_key, []) if list_key and isinstance(payload, dict) else payload
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict) and _candidate_matches(record, wanted_keys):
                return _device_conflict_payload(
                    record,
                    status=_candidate_status(record),
                    source=source_name,
                )

    return None


def _state_path(name: str) -> Path:
    return deps.settings().state_dir / name


def _read(path: Path, default: Any) -> Any:
    return deps.core.read_json_file(path, default)


def _write(path: Path, data: Any) -> None:
    deps.core.write_json_file(path, data)


def _now() -> str:
    return deps.now_utc_iso()


def _epoch() -> float:
    return time.time()


def normalize_node_id(value: str | None) -> str:
    raw = (value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip("-._")
    return raw or "unknown-node"


def _identity_variants(value: str | None) -> set[str]:
    canonical = normalize_node_id(value)
    variants = {canonical}
    if canonical and canonical != "unknown-node":
        variants.add(canonical.replace("_", "-"))
        variants.add(canonical.replace("_", "."))
    return {item for item in variants if item and item != "unknown-node"}




def _canonical_server_node_id() -> str:
    return normalize_node_id(
        os.environ.get("POCKETLAB_SERVER_NODE_ID")
        or os.environ.get("POCKETLAB_NODE_ID")
        or "pocket-lab-lite-server"
    )


def _safe_local_control_plane_claim(data: Dict[str, Any], node_id: str) -> bool:
    if not bool(data.get("is_control_plane")):
        return False
    role = _role_value(data)
    if role not in {"server_host", "server", "control_plane", "control_plane_host"}:
        return False
    local_aliases = {
        _canonical_server_node_id(),
        "localhost",
        "127-0-0-1",
        normalize_node_id(os.environ.get("HOSTNAME") or ""),
        normalize_node_id(os.environ.get("POCKETLAB_DEVICE_NAME") or ""),
    }
    try:
        import socket
        local_aliases.add(normalize_node_id(socket.gethostname()))
    except Exception:
        pass
    return node_id in {item for item in local_aliases if item and item != "unknown-node"}


def _hash_token(value: str | None) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _safe_profile_text(value: Any, limit: int = 160) -> str:
    text = _CONTROL_TEXT_RE.sub(" ", str(value or ""))
    return " ".join(text.strip().split())[:limit]


def _normalize_system_profile(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    profile: Dict[str, Any] = {
        field: _safe_profile_text(value.get(field), 160)
        for field in _PROFILE_TEXT_FIELDS
        if value.get(field) not in (None, "")
    }
    try:
        schema_version = int(value.get("schema_version") or 0)
    except (TypeError, ValueError):
        schema_version = 0
    if 1 <= schema_version <= 100:
        profile["schema_version"] = schema_version
    try:
        api_level = int(value.get("android_api_level"))
    except (TypeError, ValueError):
        api_level = 0
    if 1 <= api_level <= 999:
        profile["android_api_level"] = api_level
    unavailable = value.get("unavailable_fields")
    if isinstance(unavailable, list):
        profile["unavailable_fields"] = [
            _safe_profile_text(item, 64) for item in unavailable[:16]
            if _safe_profile_text(item, 64)
        ]
    return profile


def _normalize_system_health(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    health: Dict[str, Any] = {
        "uptime_status": _safe_profile_text(value.get("uptime_status"), 32) or "unavailable",
        "failure_code": _safe_profile_text(value.get("failure_code"), 64),
        "load_status": _safe_profile_text(value.get("load_status"), 32),
        "collected_at": _safe_profile_text(value.get("collected_at"), 64),
    }
    try:
        uptime_seconds = int(value.get("uptime_seconds"))
    except (TypeError, ValueError):
        uptime_seconds = -1
    if 0 <= uptime_seconds <= 20 * 365 * 24 * 60 * 60:
        health["uptime_seconds"] = uptime_seconds
    for field in _HEALTH_FLOAT_FIELDS:
        try:
            number = float(value.get(field))
        except (TypeError, ValueError):
            continue
        if 0 <= number <= 100_000:
            health[field] = round(number, 3)
    return health


def _agents_payload() -> Dict[str, Any]:
    payload = _read(
        _state_path("fleet_agents.json"), {"agents": {}, "updated_at": None}
    )
    if not isinstance(payload, dict):
        payload = {"agents": {}, "updated_at": None}
    if not isinstance(payload.get("agents"), dict):
        payload["agents"] = {}
    return payload


def _commands_payload() -> Dict[str, Any]:
    payload = _read(
        _state_path("fleet_agent_commands.json"), {"commands": [], "updated_at": None}
    )
    if not isinstance(payload, dict):
        payload = {"commands": [], "updated_at": None}
    if not isinstance(payload.get("commands"), list):
        payload["commands"] = []
    return payload


def _derive_status(agent: Dict[str, Any]) -> str:
    last_seen_epoch = float(agent.get("last_seen_epoch") or 0)
    supervisor_seen_epoch = float(agent.get("last_supervisor_epoch") or 0)
    agent_status = str(agent.get("agent_status") or "unknown").lower()
    supervisor_status = str(agent.get("supervisor_status") or "").lower()
    process_status = str(agent.get("agent_process_status") or "").lower()
    supervisor_fresh = bool(supervisor_seen_epoch and (_epoch() - supervisor_seen_epoch) <= SUPERVISOR_TTL_SECONDS)

    if agent_status in {"invited", "pending"}:
        return "pending"
    if agent_status in {"joining", "accepted"}:
        return agent_status
    if supervisor_fresh and supervisor_status == "repairing":
        return "repairing"
    if supervisor_fresh and process_status in {"stopped", "missing", "errored", "error", "stopping"}:
        return "agent_stopped"
    if (
        last_seen_epoch
        and (_epoch() - last_seen_epoch) <= AGENT_TTL_SECONDS
        and agent_status not in {"failed", "unhealthy", "offline", "agent_stopped"}
    ):
        return "active"
    if supervisor_fresh and agent_status in {"agent_stopped", "repairing"}:
        return agent_status
    if last_seen_epoch:
        return "offline"
    return "unknown"



def append_device_lifecycle_event(
    device_id: str,
    event_type: str,
    *,
    reason_code: str = "",
    summary: str = "",
    status: str = "recorded",
    occurred_at: str | None = None,
    invite_id: str | None = None,
    command_id: str | None = None,
) -> Dict[str, Any]:
    """Append a bounded, sanitized lifecycle event without storing raw payloads."""
    safe_device_id = normalize_node_id(device_id)
    safe_type = re.sub(r"[^a-z0-9_.-]+", "_", str(event_type or "device_activity").lower())[:80]
    safe_reason = re.sub(r"[^a-z0-9_.-]+", "_", str(reason_code or "").lower())[:80]
    safe_summary = _safe_profile_text(summary or "Device activity recorded.", 220)
    at = occurred_at or _now()
    material = json.dumps(
        [safe_device_id, safe_type, at, safe_reason, invite_id or "", command_id or ""],
        separators=(",", ":"),
    )
    event = {
        "event_id": hashlib.sha256(material.encode("utf-8")).hexdigest()[:24],
        "device_id": safe_device_id,
        "node_id": safe_device_id,
        "event_type": safe_type,
        "reason_code": safe_reason,
        "summary": safe_summary,
        "occurred_at": at,
        "created_at": at,
        "status": _safe_profile_text(status, 32) or "recorded",
        "invite_id": _safe_profile_text(invite_id, 120) if invite_id else None,
        "command_id": _safe_profile_text(command_id, 120) if command_id else None,
        "sanitized": True,
    }
    payload = _read(_state_path("fleet_device_events.json"), {"events": [], "updated_at": None})
    if not isinstance(payload, dict):
        payload = {"events": [], "updated_at": None}
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    events = [
        item for item in events
        if not (isinstance(item, dict) and str(item.get("event_id") or "") == event["event_id"])
    ]
    events.insert(0, event)
    payload["events"] = events[:500]
    payload["updated_at"] = at
    _write(_state_path("fleet_device_events.json"), payload)
    return event


def _event_timestamp_fields(event_type: str, data: Dict[str, Any], now: str) -> Dict[str, Any]:
    normalized = str(event_type or "").lower()
    result: Dict[str, Any] = {}
    if normalized.endswith("node_heartbeat") or normalized.endswith("node_seen"):
        result["last_heartbeat_at"] = data.get("heartbeat_at") or data.get("seen_at") or now
    if normalized.endswith("node_telemetry"):
        result["last_telemetry_at"] = data.get("sampled_at") or now
    if normalized.endswith("node_health"):
        result["last_health_at"] = data.get("sampled_at") or data.get("checked_at") or now
    if normalized.endswith("node_supervisor"):
        result["last_supervisor_heartbeat_at"] = data.get("checked_at") or data.get("seen_at") or now
    if normalized.endswith("node_reconnected") or data.get("nats_connected_at"):
        result["last_nats_connected_at"] = data.get("nats_connected_at") or data.get("reconnected_at") or now
    if normalized.endswith("node_left") or data.get("last_nats_disconnected_at"):
        result["last_nats_disconnected_at"] = data.get("last_nats_disconnected_at") or data.get("left_at") or now
    if isinstance(data.get("system_profile"), dict):
        result["last_system_profile_at"] = data["system_profile"].get("collected_at") or now
    return result


def upsert_agent(
    data: Dict[str, Any], *, event_type: str = "fleet.node_seen"
) -> Dict[str, Any]:
    """Atomically merge one agent event into the durable fleet registry.

    NATS callbacks can overlap inside the API process. Serializing the full
    read/merge/write cycle prevents a newer heartbeat from replacing a payload
    that also contained an enrolled offline device.
    """
    with _AGENT_REGISTRY_LOCK:
        return _upsert_agent_unlocked(data, event_type=event_type)


def _upsert_agent_unlocked(
    data: Dict[str, Any], *, event_type: str = "fleet.node_seen"
) -> Dict[str, Any]:
    node_id = normalize_node_id(
        str(
            data.get("node_id")
            or data.get("id")
            or data.get("hostname")
            or data.get("name")
            or ""
        )
    )
    control_plane_claim = _safe_local_control_plane_claim(data, node_id)
    if control_plane_claim:
        node_id = _canonical_server_node_id()
    payload = _agents_payload()
    agents = payload["agents"]
    existing = dict(agents.get(node_id) or {})
    now = _now()
    incoming_hash = str(data.get("auth_token_hash") or "").strip()
    existing_hash = str(existing.get("auth_token_hash") or "").strip()

    # A display label or consumer model never participates in identity. When a
    # different enrolled credential reports for an existing node, keep the
    # previously trusted record and fail closed. This path never writes env
    # files or restarts PM2; it only records bounded sanitized evidence.
    if (
        not control_plane_claim
        and existing_hash
        and incoming_hash
        and existing_hash != incoming_hash
    ):
        trusted = str(existing.get("identity_status") or "").lower() == "verified"
        existing.update({
            "identity_status": "verified" if trusted else "join_blocked",
            "enrollment_status": existing.get("enrollment_status") or ("ready" if trusted else "join_blocked"),
            "identity_mismatch_count": int(existing.get("identity_mismatch_count") or 0) + 1,
            "blocked_join_count": int(existing.get("blocked_join_count") or 0) + 1,
            "last_identity_mismatch_at": now,
            "last_identity_reason_code": "invite_identity_mismatch",
            "last_blocked_join_at": now,
            "repair_required": bool(existing.get("repair_required") or not trusted),
            "repair_reason_code": existing.get("repair_reason_code") or ("invite_identity_mismatch" if not trusted else ""),
            "updated_at": now,
        })
        agents[node_id] = existing
        payload["updated_at"] = now
        _write(_state_path("fleet_agents.json"), payload)
        append_device_lifecycle_event(
            node_id,
            "identity_mismatch_blocked",
            reason_code="invite_identity_mismatch",
            summary="A mismatched device join was blocked without changing the enrolled identity.",
            status="blocked",
            occurred_at=now,
        )
        return existing

    event_fields = _event_timestamp_fields(event_type, data, now)
    normalized_event = str(event_type or "").lower()
    is_heartbeat = normalized_event.endswith("node_heartbeat") or normalized_event.endswith("node_seen")
    is_join_start = normalized_event.endswith("agent_join_started")
    is_invited = normalized_event.endswith("agent_invited")
    is_supervisor = normalized_event.endswith("node_supervisor")
    previous_status = str(existing.get("agent_status") or "").lower()
    previous_identity = str(existing.get("identity_status") or "").lower()

    merged = {
        **existing,
        **event_fields,
        "id": node_id,
        "node_id": node_id,
        "name": (os.environ.get("POCKETLAB_DEVICE_NAME") if control_plane_claim else None)
        or data.get("name")
        or data.get("hostname")
        or existing.get("name")
        or node_id,
        "hostname": data.get("hostname")
        or data.get("name")
        or existing.get("hostname")
        or node_id,
        "role": "server_host" if control_plane_claim else (data.get("role") or existing.get("role") or "compute"),
        "ip": data.get("ip") or data.get("tailnet_ip") or existing.get("ip") or "",
        "tailnet_ip": data.get("tailnet_ip")
        or data.get("ip")
        or existing.get("tailnet_ip")
        or "",
        "agent_version": data.get("agent_version")
        or existing.get("agent_version")
        or "unknown",
        "capability_schema_version": data.get("capability_schema_version")
        or existing.get("capability_schema_version")
        or 1,
        "reconnect_count": int(
            data.get("reconnect_count")
            if data.get("reconnect_count") is not None
            else existing.get("reconnect_count") or 0
        ),
        "agent_status": data.get("status")
        or data.get("agent_status")
        or existing.get("agent_status")
        or "online",
        "last_event_type": event_type,
        "last_seen_at": data.get("seen_at")
        or data.get("heartbeat_at")
        or data.get("sampled_at")
        or data.get("checked_at")
        or now,
        "last_seen_epoch": _epoch(),
        "updated_at": now,
        "isCurrent": control_plane_claim,
        "source": "nats-agent",
    }

    if control_plane_claim:
        merged.update({
            "identity_status": "protected_server_host",
            "enrollment_status": "ready",
            "identity_verified_at": existing.get("identity_verified_at") or now,
            "enrolled_at": existing.get("enrolled_at") or now,
            "first_ready_at": existing.get("first_ready_at") or now,
            "last_successful_join_at": now,
        })
    elif is_invited:
        merged.update({
            "identity_status": existing.get("identity_status") or "pending",
            "enrollment_status": "invite_pending",
            "last_join_attempt_at": now,
        })
    elif is_join_start:
        merged.update({
            "identity_status": existing.get("identity_status") or "pending",
            "enrollment_status": "waiting_for_heartbeat",
            "last_join_attempt_at": now,
        })
    elif is_heartbeat:
        first_heartbeat = existing.get("first_heartbeat_at") or event_fields.get("last_heartbeat_at") or now
        merged.update({
            "first_heartbeat_at": first_heartbeat,
            "identity_status": "verified",
            "identity_verified_at": existing.get("identity_verified_at") or first_heartbeat,
            "enrollment_status": "ready",
            "enrolled_at": existing.get("enrolled_at") or first_heartbeat,
            "first_ready_at": existing.get("first_ready_at") or first_heartbeat,
            "last_successful_join_at": event_fields.get("last_heartbeat_at") or now,
            "repair_required": False,
            "repair_reason_code": "",
        })

    supervisor_seen = bool(
        data.get("supervisor_status")
        or data.get("agent_process_status")
        or is_supervisor
    )
    if supervisor_seen:
        merged["supervisor_status"] = data.get("supervisor_status") or existing.get("supervisor_status") or "unknown"
        merged["agent_process"] = data.get("agent_process") or existing.get("agent_process")
        merged["agent_process_status"] = data.get("agent_process_status") or existing.get("agent_process_status") or "unknown"
        merged["supervisor_process"] = data.get("supervisor_process") or existing.get("supervisor_process")
        merged["supervisor_version"] = data.get("supervisor_version") or existing.get("supervisor_version")
        merged["last_supervisor_at"] = data.get("checked_at") or data.get("seen_at") or now
        merged["last_supervisor_epoch"] = _epoch()
        merged["first_supervisor_heartbeat_at"] = existing.get("first_supervisor_heartbeat_at") or merged["last_supervisor_at"]
        merged["supervisor_repair_count"] = int(data.get("repair_count") or existing.get("supervisor_repair_count") or 0)
        merged["last_supervisor_repair_at"] = data.get("last_repair_at") or existing.get("last_supervisor_repair_at") or ""
        merged["supervisor_nats_reachable"] = bool(data.get("nats_reachable"))
        if data.get("last_repair_at"):
            merged["last_recovery_at"] = data.get("last_repair_at")
            merged["last_recovery_result"] = "recovered"

    if isinstance(data.get("telemetry"), dict):
        merged["telemetry"] = data["telemetry"]
    if isinstance(data.get("health"), dict):
        merged["health"] = data["health"]
    system_profile = _normalize_system_profile(data.get("system_profile"))
    if system_profile:
        merged["system_profile"] = system_profile
    system_health = _normalize_system_health(data.get("system_health"))
    if system_health:
        merged["system_health"] = system_health
    advertised = data.get("advertised_capabilities") if isinstance(data.get("advertised_capabilities"), list) else data.get("capabilities")
    if isinstance(advertised, list):
        merged["advertised_capabilities"] = [
            _safe_profile_text(item, 80) for item in advertised[:32] if _safe_profile_text(item, 80)
        ]
        merged["capabilities"] = list(merged["advertised_capabilities"])
    if isinstance(data.get("storage"), dict):
        merged["storage"] = data["storage"]
    if isinstance(data.get("media_roots"), list):
        merged["media_roots"] = data["media_roots"]
    for storage_key in ("available_gb", "free_storage_gb", "storage_available_gb"):
        if data.get(storage_key) is not None:
            merged[storage_key] = data.get(storage_key)
    if incoming_hash:
        merged["auth_token_hash"] = incoming_hash
    if merged.get("tailnet_ip"):
        merged["last_tailnet_ready_at"] = data.get("seen_at") or data.get("heartbeat_at") or now

    agents[node_id] = merged
    payload["updated_at"] = now
    _write(_state_path("fleet_agents.json"), payload)

    if is_invited and previous_status not in {"invited", "pending"}:
        append_device_lifecycle_event(node_id, "invite_created", summary="Device invite created.", occurred_at=now)
    if is_join_start and previous_status not in {"joining", "accepted"}:
        append_device_lifecycle_event(node_id, "join_started", summary="Device join started.", occurred_at=now)
    if is_heartbeat and not existing.get("first_heartbeat_at"):
        append_device_lifecycle_event(node_id, "first_heartbeat_received", summary="First valid device heartbeat received.", occurred_at=merged.get("first_heartbeat_at"))
    if is_heartbeat and previous_identity != "verified":
        append_device_lifecycle_event(node_id, "identity_verified", summary="Device identity verified from the enrolled agent heartbeat.", occurred_at=merged.get("identity_verified_at"))
    if is_heartbeat and previous_status in {"offline", "failed", "unhealthy", "agent_stopped"}:
        append_device_lifecycle_event(node_id, "device_returned_online", summary="Device returned online.", occurred_at=now)
    if is_supervisor and not existing.get("first_supervisor_heartbeat_at"):
        append_device_lifecycle_event(node_id, "first_supervisor_heartbeat", summary="Device supervisor reported for the first time.", occurred_at=merged.get("first_supervisor_heartbeat_at"))
    if is_supervisor and data.get("last_repair_at") and data.get("last_repair_at") != existing.get("last_supervisor_repair_at"):
        append_device_lifecycle_event(node_id, "repair_completed", summary="Device supervisor completed a recovery action.", occurred_at=str(data.get("last_repair_at")), status="completed")
    return merged


def handle_agent_event(event: Dict[str, Any]) -> None:
    subject = str(event.get("subject") or "")
    event_type = str(event.get("type") or "")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if not subject.startswith("pocketlab.events.fleet.node_"):
        return
    if subject.endswith("node_command_queued") or event_type.endswith("command_queued"):
        return
    if not data:
        return
    if subject.endswith("node_command_result") or event_type.endswith("command_result"):
        record_command_result(data)
        return
    agent_event_suffixes = (
        "node_seen",
        "node_heartbeat",
        "node_telemetry",
        "node_health",
        "node_left",
        "node_supervisor",
        "node_reconnected",
    )
    if not subject.endswith(agent_event_suffixes):
        return
    upsert_agent(data, event_type=event_type or subject)
    # Agent events are the source of truth for fleet freshness. Drop only the
    # prepared fleet snapshot so the next read rebuilds from the sanitized
    # registry; do not execute commands or write through the frontend.
    try:
        from .lite_control_plane_store import CONTROL_PLANE

        CONTROL_PLANE.invalidate_domain("fleet")
    except Exception:
        pass


def list_agents(include_stale: bool = True) -> List[Dict[str, Any]]:
    payload = _agents_payload()
    agents = []
    for agent in payload["agents"].values():
        if not isinstance(agent, dict):
            continue
        item = dict(agent)
        item["status"] = _derive_status(item)
        item["online"] = item["status"] == "active"
        if include_stale or item["online"]:
            agents.append(item)
    return sorted(
        agents, key=lambda item: str(item.get("last_seen_at") or ""), reverse=True
    )


def get_agent(node_id: str) -> Dict[str, Any] | None:
    node_id = normalize_node_id(node_id)
    for agent in list_agents(include_stale=True):
        if normalize_node_id(str(agent.get("node_id") or agent.get("id"))) == node_id:
            return agent
    return None


def agent_fleet_nodes() -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    for agent in list_agents(include_stale=True):
        status = str(agent.get("status") or "unknown")
        nodes.append(
            {
                "id": agent.get("node_id"),
                "name": agent.get("name")
                or agent.get("hostname")
                or agent.get("node_id"),
                "role": agent.get("role") or "compute",
                "ip": agent.get("tailnet_ip") or agent.get("ip") or "",
                "status": "active" if status == "active" else status,
                "isCurrent": bool(agent.get("isCurrent")),
                "source": "nats-agent",
                "last_seen_at": agent.get("last_seen_at"),
                "agent_version": agent.get("agent_version"),
                "capability_schema_version": agent.get("capability_schema_version"),
                "reconnect_count": agent.get("reconnect_count"),
                "telemetry": agent.get("telemetry") or {},
                "health": agent.get("health") or {},
                "system_profile": agent.get("system_profile") or {},
                "system_health": agent.get("system_health") or {},
                "storage": agent.get("storage") or {},
                "media_roots": agent.get("media_roots") or [],
                "available_gb": agent.get("available_gb"),
                "free_storage_gb": agent.get("free_storage_gb"),
                "storage_available_gb": agent.get("storage_available_gb"),
                "supervisor_status": agent.get("supervisor_status"),
                "supervisor_version": agent.get("supervisor_version"),
                "agent_process": agent.get("agent_process"),
                "agent_process_status": agent.get("agent_process_status"),
                "last_supervisor_at": agent.get("last_supervisor_at"),
                "supervisor_repair_count": agent.get("supervisor_repair_count"),
                "last_supervisor_repair_at": agent.get("last_supervisor_repair_at"),
                "supervisor_nats_reachable": agent.get("supervisor_nats_reachable"),
                "advertised_capabilities": agent.get("advertised_capabilities") or agent.get("capabilities") or [],
                "last_heartbeat_at": agent.get("last_heartbeat_at"),
                "last_telemetry_at": agent.get("last_telemetry_at"),
                "last_system_profile_at": agent.get("last_system_profile_at"),
                "last_supervisor_heartbeat_at": agent.get("last_supervisor_heartbeat_at"),
                "last_command_received_at": agent.get("last_command_received_at"),
                "last_command_completed_at": agent.get("last_command_completed_at"),
                "last_nats_connected_at": agent.get("last_nats_connected_at"),
                "last_nats_disconnected_at": agent.get("last_nats_disconnected_at"),
                "last_tailnet_ready_at": agent.get("last_tailnet_ready_at"),
                "last_recovery_at": agent.get("last_recovery_at"),
                "last_recovery_result": agent.get("last_recovery_result"),
                "invite_created_at": agent.get("invite_created_at"),
                "invite_accepted_at": agent.get("invite_accepted_at"),
                "enrolled_at": agent.get("enrolled_at"),
                "first_heartbeat_at": agent.get("first_heartbeat_at"),
                "first_supervisor_heartbeat_at": agent.get("first_supervisor_heartbeat_at"),
                "first_ready_at": agent.get("first_ready_at"),
                "last_join_attempt_at": agent.get("last_join_attempt_at"),
                "last_successful_join_at": agent.get("last_successful_join_at"),
                "enrollment_status": agent.get("enrollment_status"),
                "identity_status": agent.get("identity_status"),
                "identity_verified_at": agent.get("identity_verified_at"),
                "identity_mismatch_count": agent.get("identity_mismatch_count"),
                "last_identity_mismatch_at": agent.get("last_identity_mismatch_at"),
                "last_identity_reason_code": agent.get("last_identity_reason_code"),
                "blocked_join_count": agent.get("blocked_join_count"),
                "last_blocked_join_at": agent.get("last_blocked_join_at"),
                "repair_required": agent.get("repair_required"),
                "repair_reason_code": agent.get("repair_reason_code"),
            }
        )
    return nodes


def merged_fleet_nodes() -> List[Dict[str, Any]]:
    base = list(deps.core.load_fleet_nodes())
    by_id: Dict[str, Dict[str, Any]] = {}
    for node in base:
        key = normalize_node_id(str(node.get("id") or node.get("name") or ""))
        by_id[key] = node
    for node in agent_fleet_nodes():
        key = normalize_node_id(str(node.get("id") or node.get("name") or ""))
        by_id[key] = {**by_id.get(key, {}), **node}
    return list(by_id.values())


def fleet_health_snapshot() -> Dict[str, Any]:
    nodes = merged_fleet_nodes()
    healthy = sum(
        1 for node in nodes if str(node.get("status") or "").lower() == "active"
    )
    stale = sum(1 for node in nodes if str(node.get("status") or "").lower() in {"stale", "offline"})
    unhealthy = max(0, len(nodes) - healthy)
    return {
        "status": (
            "healthy"
            if nodes and unhealthy == 0
            else ("degraded" if nodes else "unknown")
        ),
        "summary": {
            "healthy": healthy,
            "unhealthy": unhealthy,
            "stale": stale,
            "total": len(nodes),
        },
        "nodes": nodes,
        "agents": list_agents(include_stale=True),
        "agent_ttl_seconds": AGENT_TTL_SECONDS,
        "last_checked_at": _now(),
    }


def create_node_command(
    node_id: str,
    command: str,
    payload: Dict[str, Any] | None = None,
    *,
    requested_by: str = "api",
) -> Dict[str, Any]:
    node_id = normalize_node_id(node_id)
    command_id = hashlib.sha256(
        f"{node_id}:{command}:{json.dumps(payload or {}, sort_keys=True)}:{time.time()}".encode(
            "utf-8"
        )
    ).hexdigest()[:24]
    item = {
        "command_id": command_id,
        "node_id": node_id,
        "command": command,
        "payload": payload or {},
        "status": "queued",
        "requested_by": requested_by,
        "created_at": _now(),
        "created_at_epoch": _epoch(),
        "updated_at": _now(),
        "expires_at_epoch": _epoch() + COMMAND_TTL_SECONDS,
    }
    state = _commands_payload()
    state["commands"] = [
        cmd
        for cmd in state["commands"]
        if float(cmd.get("expires_at_epoch") or 0) > _epoch()
    ]
    state["commands"].insert(0, item)
    state["updated_at"] = _now()
    _write(_state_path("fleet_agent_commands.json"), state)
    return item




def get_command(command_id: str, node_id: str | None = None) -> Dict[str, Any] | None:
    command_id = str(command_id or "").strip()
    if not command_id:
        return None
    for command in list_commands(node_id=node_id, limit=500):
        if str(command.get("command_id") or "") == command_id:
            return command
    return None


def command_progress(command: Dict[str, Any] | None, agent: Dict[str, Any] | None = None) -> Dict[str, Any]:
    command = command or {}
    agent = agent or {}
    command_status = str(command.get("status") or "queued").lower()
    command_id = str(command.get("command_id") or "")
    node_id = normalize_node_id(str(command.get("node_id") or agent.get("node_id") or agent.get("id") or ""))
    created_epoch = float(command.get("created_at_epoch") or 0)
    last_seen_epoch = float(agent.get("last_seen_epoch") or 0)
    agent_status = str(agent.get("status") or "unknown").lower()
    process_status = str(agent.get("agent_process_status") or "").lower()
    supervisor_status = str(agent.get("supervisor_status") or "").lower()
    supervisor_seen_epoch = float(agent.get("last_supervisor_epoch") or 0)
    supervisor_fresh = bool(supervisor_seen_epoch and (_epoch() - supervisor_seen_epoch) <= SUPERVISOR_TTL_SECONDS)
    command_finished = command_status in {"acknowledged", "completed", "succeeded"}
    command_failed = command_status in {"failed", "error", "unsupported"}
    heartbeat_after_request = bool(last_seen_epoch and created_epoch and last_seen_epoch >= created_epoch)
    online = agent_status in {"active", "healthy", "online"}
    stopped = agent_status == "agent_stopped" or process_status in {"stopped", "missing", "errored", "error", "stopping"}
    repairing = agent_status == "repairing" or supervisor_status == "repairing"
    supervisor_known = bool(supervisor_status or process_status or supervisor_seen_epoch)

    def step(step_id: str, label: str, detail: str, state: str) -> Dict[str, Any]:
        return {"id": step_id, "label": label, "detail": detail, "state": state}

    if stopped or repairing:
        supervisor_state = "active" if repairing else ("complete" if supervisor_known and not stopped else "waiting" if supervisor_known else "failed")
        heartbeat_state = "complete" if heartbeat_after_request and online else "waiting"
        overall = "completed" if heartbeat_after_request and online else ("repairing" if repairing or supervisor_state == "active" else "agent_stopped")
        steps = [
            step("request_saved", "Request saved", "Pocket Lab recorded the restart request safely.", "complete" if command_id else "waiting"),
            step(
                "private_channel",
                "Private channel checked",
                "The normal restart request can run only after the device agent is available.",
                "waiting" if stopped and not online else "complete",
            ),
            step(
                "device_agent",
                "Device agent is stopped" if stopped else "Device agent is being repaired",
                "The device agent is not currently available to receive commands." if stopped else "The local supervisor is working to bring the device agent back.",
                "failed" if stopped and not supervisor_known else "active" if repairing else "waiting",
            ),
            step(
                "local_supervisor",
                "Local supervisor",
                "The local supervisor can start the stopped device agent on that phone." if supervisor_known else "This phone has not reported a local supervisor yet. Open Termux on that phone to start the supervisor once.",
                supervisor_state,
            ),
            step("heartbeat", "Waiting for the device to report back", "The device will show Online after a fresh heartbeat arrives.", heartbeat_state),
        ]
        return {
            "status": overall,
            "command_id": command_id,
            "node_id": node_id,
            "command_status": command_status,
            "agent_status": agent_status,
            "agent_process_status": process_status or "unknown",
            "supervisor_status": supervisor_status or "unknown",
            "heartbeat_after_request": heartbeat_after_request,
            "last_seen_at": agent.get("last_seen_at"),
            "steps": steps,
            "summary": (
                "Device reported back after local repair."
                if overall == "completed"
                else "The device agent is stopped. Pocket Lab is waiting for the local supervisor to start it."
                if overall == "agent_stopped"
                else "The local supervisor is repairing the device agent."
            ),
        }

    def normal_step(step_id: str, label: str, detail: str, state: str) -> Dict[str, Any]:
        return {"id": step_id, "label": label, "detail": detail, "state": state}

    steps = [
        normal_step(
            "request_saved",
            "Request saved",
            "Pocket Lab recorded the restart request safely.",
            "complete" if command_id else "waiting",
        ),
        normal_step(
            "private_channel",
            "Sent through the private channel",
            "Pocket Lab sent the request through the device command channel.",
            "complete" if command_id else "waiting",
        ),
        normal_step(
            "device_ack",
            "Waiting for the device agent",
            "The device agent needs to receive and acknowledge the restart request.",
            "failed" if command_failed else ("complete" if command_finished else "active"),
        ),
        normal_step(
            "heartbeat",
            "Waiting for the device to report back",
            "The device will show Online after a fresh heartbeat arrives.",
            "failed" if command_failed else ("complete" if heartbeat_after_request and online else "active" if command_finished else "waiting"),
        ),
    ]
    overall = "failed" if command_failed else ("completed" if heartbeat_after_request and online else "waiting")
    if not command_id:
        overall = "unknown"
    return {
        "status": overall,
        "command_id": command_id,
        "node_id": node_id,
        "command_status": command_status,
        "agent_status": agent_status,
        "agent_process_status": process_status or "unknown",
        "supervisor_status": supervisor_status or "unknown",
        "heartbeat_after_request": heartbeat_after_request,
        "last_seen_at": agent.get("last_seen_at"),
        "steps": steps,
        "summary": (
            "Device reported back after restart."
            if overall == "completed"
            else "Pocket Lab is waiting for the device agent to report back."
            if overall == "waiting"
            else "Pocket Lab could not confirm the restart."
        ),
    }

def record_command_result(data: Dict[str, Any]) -> Dict[str, Any]:
    command_id = str(data.get("command_id") or "")
    node_id = normalize_node_id(str(data.get("node_id") or ""))
    state = _commands_payload()
    found = None
    for cmd in state["commands"]:
        if command_id and cmd.get("command_id") == command_id:
            found = cmd
            break
    if found is None:
        found = {
            "command_id": command_id
            or hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[
                :24
            ],
            "node_id": node_id,
            "command": data.get("command") or "unknown",
            "created_at": _now(),
        }
        state["commands"].insert(0, found)
    found.update(
        {
            "status": data.get("status") or "completed",
            "result": data.get("result") or {},
            "error": data.get("error"),
            "updated_at": _now(),
            "finished_at": _now(),
        }
    )
    state["updated_at"] = _now()
    _write(_state_path("fleet_agent_commands.json"), state)
    agents_payload = _agents_payload()
    agent = agents_payload.get("agents", {}).get(node_id) if node_id else None
    if isinstance(agent, dict):
        completed_at = found.get("finished_at") or found.get("updated_at") or _now()
        agent["last_command_received_at"] = data.get("received_at") or completed_at
        agent["last_command_completed_at"] = completed_at
        agent["updated_at"] = completed_at
        agents_payload["updated_at"] = completed_at
        _write(_state_path("fleet_agents.json"), agents_payload)
        status = str(found.get("status") or "completed").lower()
        append_device_lifecycle_event(
            node_id,
            "restart_delivered",
            reason_code="agent_received_command",
            summary="Device agent received the restart request.",
            status="delivered",
            occurred_at=data.get("received_at") or completed_at,
            command_id=found.get("command_id"),
        )
        append_device_lifecycle_event(
            node_id,
            "restart_completed" if status in {"completed", "succeeded", "acknowledged"} else "restart_failed",
            reason_code="command_completed" if status in {"completed", "succeeded", "acknowledged"} else "command_failed",
            summary="Device restart completed." if status in {"completed", "succeeded", "acknowledged"} else "Device restart did not complete.",
            status=status,
            occurred_at=completed_at,
            command_id=found.get("command_id"),
        )
    return found


def list_commands(node_id: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
    state = _commands_payload()
    commands = [cmd for cmd in state["commands"] if isinstance(cmd, dict)]
    if node_id:
        wanted = normalize_node_id(node_id)
        commands = [
            cmd
            for cmd in commands
            if normalize_node_id(str(cmd.get("node_id") or "")) == wanted
        ]
    return commands[: max(1, min(limit, 500))]


def _candidate_matches(record: Dict[str, Any], wanted: str | set[str]) -> bool:
    wanted_keys = wanted if isinstance(wanted, set) else _identity_variants(wanted)
    return bool(wanted_keys.intersection(_record_identity_keys(record)))


def _cleanup_json_list_file(name: str, wanted: str, list_key: str | None = None) -> tuple[int, list[Dict[str, Any]]]:
    path = _state_path(name)
    if not path.exists():
        return 0, []
    default = {list_key: []} if list_key else []
    payload = _read(path, default)
    if list_key:
        records = payload.get(list_key, []) if isinstance(payload, dict) else []
    else:
        records = payload if isinstance(payload, list) else []
    if not isinstance(records, list):
        return 0, []

    removed: list[Dict[str, Any]] = []
    kept: list[Dict[str, Any]] = []
    for record in records:
        if isinstance(record, dict) and _candidate_matches(record, wanted):
            removed.append(record)
        else:
            kept.append(record)

    if removed:
        if list_key:
            if not isinstance(payload, dict):
                payload = {list_key: kept}
            else:
                payload[list_key] = kept
                payload["updated_at"] = _now()
            _write(path, payload)
        else:
            _write(path, kept)
    return len(removed), removed


def remove_device_records(device_id: str) -> Dict[str, Any]:
    wanted = normalize_node_id(device_id)
    if not wanted or wanted == "unknown-node":
        raise DeviceRemovalError(400, "Choose a device to remove.")
    if wanted in _protected_server_ids():
        raise DeviceRemovalError(409, "Cannot remove the current Pocket Lab Lite server device.")

    candidates: list[tuple[str, str, Dict[str, Any], str]] = []

    agents_payload = _agents_payload()
    for key, agent in agents_payload["agents"].items():
        if isinstance(agent, dict) and (normalize_node_id(str(key)) == wanted or _candidate_matches(agent, wanted)):
            candidates.append(("fleet_agents.json", str(key), agent, _candidate_status(agent, from_agent=True)))

    for source_name, list_key in (("fleet.json", None), ("fleet_pending.json", "nodes")):
        path = _state_path(source_name)
        if not path.exists():
            continue
        payload = _read(path, {list_key: []} if list_key else [])
        records = payload.get(list_key, []) if list_key and isinstance(payload, dict) else payload
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if isinstance(record, dict) and _candidate_matches(record, wanted):
                candidates.append((source_name, str(index), record, _candidate_status(record)))

    if not candidates:
        raise DeviceRemovalError(404, "Device record was not found.")

    for _source, _key, record, _status in candidates:
        reason = _is_protected_device(record, wanted)
        if reason:
            raise DeviceRemovalError(409, reason)

    for _source, _key, record, status in candidates:
        connection = str(record.get("connection") or "").strip().lower()
        if _is_online_or_healthy_status(status) or connection == "online":
            raise DeviceRemovalError(409, "Online devices are protected. Disconnect or mark the device stale before removing its saved record.")

    _primary_source, _primary_key, primary, primary_status = candidates[0]
    removed_device_records = 0

    removed_agent_records: list[Dict[str, Any]] = []
    agent_keys_to_remove = [
        key
        for key, agent in agents_payload["agents"].items()
        if isinstance(agent, dict) and (normalize_node_id(str(key)) == wanted or _candidate_matches(agent, wanted))
    ]
    for key in agent_keys_to_remove:
        removed = agents_payload["agents"].pop(key, None)
        if isinstance(removed, dict):
            removed_agent_records.append(removed)
    if removed_agent_records:
        agents_payload["updated_at"] = _now()
        _write(_state_path("fleet_agents.json"), agents_payload)
        removed_device_records += len(removed_agent_records)

    for source_name, list_key in (("fleet.json", None), ("fleet_pending.json", "nodes")):
        removed_count, _removed = _cleanup_json_list_file(source_name, wanted, list_key=list_key)
        removed_device_records += removed_count

    return {
        "status": "removed",
        "device_id": wanted,
        "device_name": primary.get("name") or primary.get("hostname") or primary.get("node_id") or wanted,
        "role": primary.get("role") or "compute",
        "previous_status": "healthy" if primary_status == "active" else primary_status,
        "previous_connection": _connection_for_status(primary_status),
        "removed_device_records": removed_device_records,
        "removed_from": sorted({source for source, _key, _record, _status in candidates}),
        "updated_at": _now(),
    }


def append_device_removed_evidence(
    removal: Dict[str, Any],
    *,
    removed_invite_records: int = 0,
    reason: str | None = None,
    requested_by: str = "lite-api",
) -> Dict[str, Any]:
    event = {
        "event_type": "lite.fleet.device_removed",
        "created_at": _now(),
        "device_id": removal.get("device_id"),
        "device_name": removal.get("device_name"),
        "role": removal.get("role"),
        "previous_status": removal.get("previous_status"),
        "previous_connection": removal.get("previous_connection"),
        "reason": reason or "Old device cleanup",
        "removed_device_records": int(removal.get("removed_device_records") or 0),
        "removed_invite_records": int(removed_invite_records or 0),
        "requested_by": requested_by,
        "timestamp": _now(),
    }
    for name, item_type in (
        ("fleet_device_events.json", "lite.fleet.device_removed"),
        ("fleet_device_audit.json", "lite.audit.fleet.device_removed"),
    ):
        payload = _read(_state_path(name), {"events": [], "updated_at": None})
        if not isinstance(payload, dict):
            payload = {"events": [], "updated_at": None}
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        events.insert(0, {**event, "event_type": item_type})
        payload["events"] = events[:200]
        payload["updated_at"] = _now()
        _write(_state_path(name), payload)
    return event


async def publish_device_removed_evidence(event: Dict[str, Any]) -> None:
    if not event:
        return
    from .nats_bus import BUS

    if not BUS.connected:
        return
    trace_id = str(event.get("device_id") or "lite-device-removed")
    await BUS.publish_json(
        "pocketlab.events.fleet.device_removed",
        "lite.fleet.device_removed",
        event,
        trace_id=trace_id,
    )
    await BUS.publish_json(
        "pocketlab.audit.fleet.device_removed",
        "lite.fleet.device_removed",
        event,
        trace_id=trace_id,
    )


def bootstrap_config(
    role: str = "compute", hostname: str | None = None
) -> Dict[str, Any]:
    node_id = normalize_node_id(hostname or os.environ.get("HOSTNAME") or "pocket-node")
    token = hashlib.sha256(
        f"{node_id}:{time.time()}:{os.urandom(8).hex()}".encode("utf-8")
    ).hexdigest()
    return {
        "node_id": node_id,
        "hostname": hostname or node_id,
        "role": role,
        "nats_url": os.environ.get("POCKETLAB_NATS_URL", "nats://127.0.0.1:4222"),
        "agent_token": token,
        "agent_token_hash": _hash_token(token),
        "subjects": {
            "events": "pocketlab.events.fleet.node_*",
            "commands": f"pocketlab.commands.node.{node_id}.>",
        },
        "created_at": _now(),
    }
