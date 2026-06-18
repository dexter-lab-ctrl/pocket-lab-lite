from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import Request

from .. import deps
from .fleet_registry import normalize_node_id, upsert_agent
from .nats_bus import BUS

LITE_INVITE_TTL_SECONDS = int(os.environ.get("POCKETLAB_LITE_INVITE_TTL_SECONDS", "1800"))

LITE_ROLES: dict[str, dict[str, Any]] = {
    "compute": {
        "role": "compute",
        "role_label": "App Host",
        "description": "Runs apps and services for your Pocket Lab.",
        "capabilities": ["Run apps", "Report device health", "Eligible for app installs"],
    },
    "storage": {
        "role": "storage",
        "role_label": "Storage Node",
        "description": "Stores backups, files, or app data.",
        "capabilities": ["Store backups or app data", "Report storage health", "Eligible as backup/storage target"],
    },
}

_ROLE_ALIASES = {
    "app_host": "compute",
    "app-host": "compute",
    "app host": "compute",
    "compute": "compute",
    "storage_node": "storage",
    "storage-node": "storage",
    "storage node": "storage",
    "storage": "storage",
}


def _state_path(name: str):
    return deps.settings().state_dir / name


def _read_state(name: str, default: Any) -> Any:
    return deps.core.read_json_file(_state_path(name), default)


def _write_state(name: str, data: Any) -> None:
    deps.core.write_json_file(_state_path(name), data)


def _now_epoch() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _expires_at(ttl_seconds: int = LITE_INVITE_TTL_SECONDS) -> tuple[str, float]:
    expires = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=ttl_seconds)
    return expires.isoformat().replace("+00:00", "Z"), expires.timestamp()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_hint(token: str) -> str:
    compact = token.replace("-", "").replace("_", "")
    if len(compact) <= 10:
        return compact
    return f"{compact[:6]}…{compact[-4:]}"


def normalize_lite_role(role: str | None) -> str:
    value = str(role or "compute").strip().lower()
    normalized = _ROLE_ALIASES.get(value)
    if not normalized or normalized not in LITE_ROLES:
        allowed = ", ".join(sorted(LITE_ROLES))
        raise ValueError(f"Unsupported Lite device role '{role}'. Allowed roles: {allowed}.")
    return normalized


def role_metadata(role: str | None) -> dict[str, Any]:
    normalized = normalize_lite_role(role)
    return dict(LITE_ROLES[normalized])


def lite_role_options() -> list[dict[str, Any]]:
    return [dict(item) for item in LITE_ROLES.values()]


def _invite_base_url(request: Request | None) -> str:
    configured = os.environ.get("POCKETLAB_LITE_INVITE_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        return str(request.base_url).rstrip("/")
    return f"http://{deps.settings().host}:{deps.settings().port}"


def _invite_path() -> str:
    return os.environ.get("POCKETLAB_LITE_INVITE_PATH", "/api/join.sh").strip() or "/api/join.sh"


def _public_invite(record: dict[str, Any], *, url: str | None = None) -> dict[str, Any]:
    public = {
        "invite_id": record.get("invite_id"),
        "token_hint": record.get("token_hint"),
        "hostname": record.get("hostname"),
        "role": record.get("role"),
        "role_label": record.get("role_label"),
        "capabilities": record.get("capabilities") or [],
        "expires_at": record.get("expires_at"),
        "status": record.get("status", "pending"),
        "instructions": "Open this invite on the new device while it is connected to the same Pocket Lab private network.",
    }
    if url:
        public["url"] = url
        public["copy_text"] = url
    return public


def _invites_payload() -> dict[str, Any]:
    payload = _read_state("fleet_invites.json", {"invites": [], "updated_at": None})
    if not isinstance(payload, dict):
        payload = {"invites": [], "updated_at": None}
    if not isinstance(payload.get("invites"), list):
        payload["invites"] = []
    return payload


def _safe_event_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "invite_id": record.get("invite_id"),
        "hostname": record.get("hostname"),
        "role": record.get("role"),
        "role_label": record.get("role_label"),
        "capabilities": record.get("capabilities") or [],
        "expires_at": record.get("expires_at"),
        "token_hint": record.get("token_hint"),
        "status": record.get("status", "pending"),
        "uses_remaining": record.get("uses_remaining", 1),
    }


def _append_local_evidence(record: dict[str, Any]) -> None:
    safe = _safe_event_payload(record)
    for name, event_type in (
        ("fleet_invite_events.json", "pocketlab.events.fleet.invite_created"),
        ("fleet_invite_audit.json", "pocketlab.audit.fleet.invite_created"),
    ):
        payload = _read_state(name, {"events": [], "updated_at": None})
        if not isinstance(payload, dict):
            payload = {"events": [], "updated_at": None}
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        events.insert(0, {"event_type": event_type, "created_at": _now_iso(), **safe})
        payload["events"] = events[:200]
        payload["updated_at"] = _now_iso()
        _write_state(name, payload)


def create_lite_invite(*, role: str, hostname: str | None, request: Request | None = None) -> dict[str, Any]:
    metadata = role_metadata(role)
    hostname_text = (hostname or "").strip() or f"Pocket Lab {metadata['role_label']}"
    node_id = normalize_node_id(hostname_text)
    token = secrets.token_urlsafe(32)
    expires_at, expires_epoch = _expires_at()
    command_id = secrets.token_hex(12)
    invite_id = secrets.token_hex(12)
    base = _invite_base_url(request)
    query = urlencode({"role": metadata["role"], "token": token})
    invite_url = f"{base}{_invite_path()}?{query}"

    record = {
        "invite_id": invite_id,
        "command_id": command_id,
        "job_id": command_id,
        "node_id": node_id,
        "hostname": hostname_text,
        "role": metadata["role"],
        "role_label": metadata["role_label"],
        "capabilities": metadata["capabilities"],
        "token_hash": _hash_token(token),
        "token_hint": _token_hint(token),
        "expires_at": expires_at,
        "expires_at_epoch": expires_epoch,
        "uses_remaining": 1,
        "status": "pending",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    payload = _invites_payload()
    payload["invites"] = [
        item
        for item in payload["invites"]
        if isinstance(item, dict) and float(item.get("expires_at_epoch") or 0) > _now_epoch()
    ]
    payload["invites"].insert(0, record)
    payload["updated_at"] = _now_iso()
    _write_state("fleet_invites.json", payload)

    upsert_agent(
        {
            "node_id": node_id,
            "hostname": hostname_text,
            "role": metadata["role"],
            "status": "invited",
            "auth_token_hash": record["token_hash"][:16],
            "capabilities": metadata["capabilities"],
        },
        event_type="fleet.agent_invited",
    )
    _append_local_evidence(record)

    return {
        "accepted": True,
        "status": "invite_ready",
        "summary": f"Invite ready for {hostname_text}.",
        "command_id": command_id,
        "job_id": command_id,
        "invite": _public_invite(record, url=invite_url),
        "event": _safe_event_payload(record),
    }


def latest_invite() -> dict[str, Any] | None:
    payload = _invites_payload()
    valid = [
        item
        for item in payload["invites"]
        if isinstance(item, dict) and float(item.get("expires_at_epoch") or 0) > _now_epoch()
    ]
    if len(valid) != len(payload["invites"]):
        payload["invites"] = valid
        payload["updated_at"] = _now_iso()
        _write_state("fleet_invites.json", payload)
    if not valid:
        return None
    return _public_invite(valid[0])


def validate_invite_token(token: str, role: str | None = None) -> dict[str, Any] | None:
    if not token:
        return None
    token_hash = _hash_token(token)
    expected_role = normalize_lite_role(role) if role else None
    payload = _invites_payload()
    for item in payload["invites"]:
        if not isinstance(item, dict):
            continue
        if item.get("token_hash") != token_hash:
            continue
        if expected_role and item.get("role") != expected_role:
            return None
        if float(item.get("expires_at_epoch") or 0) <= _now_epoch():
            return None
        if int(item.get("uses_remaining") or 0) <= 0:
            return None
        return item
    return None


async def publish_invite_evidence(invite_result: dict[str, Any]) -> None:
    """Publish safe invite command/event evidence when NATS is available.

    Invite metadata is prepared by FastAPI so the user can copy a bounded link.
    Device execution and ongoing join behavior remain worker/agent owned through
    the existing fleet join command path when the command bus is connected.
    """
    event = dict(invite_result.get("event") or {})
    if not event or not BUS.connected:
        return
    command_id = str(invite_result.get("command_id") or event.get("invite_id") or "")
    command_payload = {**event, "command_id": command_id, "trace_id": command_id}
    await BUS.publish_json(
        "pocketlab.commands.fleet.join",
        "fleet.join.requested",
        command_payload,
        trace_id=command_id,
    )
    await BUS.publish_json(
        "pocketlab.events.fleet.invite_created",
        "fleet.invite_created",
        event,
        trace_id=command_id,
    )
    await BUS.publish_json(
        "pocketlab.audit.fleet.invite_created",
        "fleet.invite_created",
        event,
        trace_id=command_id,
    )
