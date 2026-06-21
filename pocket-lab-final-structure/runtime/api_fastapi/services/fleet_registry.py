from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from .. import deps

AGENT_TTL_SECONDS = int(os.environ.get("POCKETLAB_FLEET_AGENT_TTL_SECONDS", "90"))
COMMAND_TTL_SECONDS = int(os.environ.get("POCKETLAB_FLEET_COMMAND_TTL_SECONDS", "3600"))


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
            keys.add(normalize_node_id(str(value)))
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


def _hash_token(value: str | None) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


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
    agent_status = str(agent.get("agent_status") or "unknown").lower()
    if agent_status in {"invited", "pending"}:
        return "pending"
    if agent_status in {"joining", "accepted"}:
        return agent_status
    if (
        last_seen_epoch
        and (_epoch() - last_seen_epoch) <= AGENT_TTL_SECONDS
        and agent_status not in {"failed", "unhealthy", "offline"}
    ):
        return "active"
    if last_seen_epoch:
        return "offline"
    return "unknown"


def upsert_agent(
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
    payload = _agents_payload()
    agents = payload["agents"]
    existing = dict(agents.get(node_id) or {})
    now = _now()
    merged = {
        **existing,
        "id": node_id,
        "node_id": node_id,
        "name": data.get("name")
        or data.get("hostname")
        or existing.get("name")
        or node_id,
        "hostname": data.get("hostname")
        or data.get("name")
        or existing.get("hostname")
        or node_id,
        "role": data.get("role") or existing.get("role") or "compute",
        "ip": data.get("ip") or data.get("tailnet_ip") or existing.get("ip") or "",
        "tailnet_ip": data.get("tailnet_ip")
        or data.get("ip")
        or existing.get("tailnet_ip")
        or "",
        "agent_version": data.get("agent_version")
        or existing.get("agent_version")
        or "unknown",
        "agent_status": data.get("status")
        or data.get("agent_status")
        or existing.get("agent_status")
        or "online",
        "last_event_type": event_type,
        "last_seen_at": data.get("seen_at")
        or data.get("heartbeat_at")
        or data.get("sampled_at")
        or now,
        "last_seen_epoch": _epoch(),
        "updated_at": now,
        "isCurrent": bool(data.get("is_control_plane", False)),
        "source": "nats-agent",
    }
    if isinstance(data.get("telemetry"), dict):
        merged["telemetry"] = data["telemetry"]
    if isinstance(data.get("health"), dict):
        merged["health"] = data["health"]
    if isinstance(data.get("capabilities"), list):
        merged["capabilities"] = data["capabilities"]
    if data.get("auth_token_hash"):
        merged["auth_token_hash"] = data.get("auth_token_hash")
    agents[node_id] = merged
    payload["updated_at"] = now
    _write(_state_path("fleet_agents.json"), payload)
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
    )
    if not subject.endswith(agent_event_suffixes):
        return
    upsert_agent(data, event_type=event_type or subject)


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
                "telemetry": agent.get("telemetry") or {},
                "health": agent.get("health") or {},
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


def _candidate_matches(record: Dict[str, Any], wanted: str) -> bool:
    return wanted in _record_identity_keys(record)


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
