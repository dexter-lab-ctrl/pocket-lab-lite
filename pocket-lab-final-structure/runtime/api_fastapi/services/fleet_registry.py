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
