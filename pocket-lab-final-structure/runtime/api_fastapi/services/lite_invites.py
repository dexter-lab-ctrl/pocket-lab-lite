from __future__ import annotations

import hashlib
import ipaddress
import os
import secrets
import socket
import subprocess
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
    "server_host": {
        "role": "server_host",
        "role_label": "Server Host",
        "description": "Runs the Pocket Lab Lite control plane and coordinates invited devices.",
        "capabilities": ["Run control plane", "Serve Lite UI", "Issue device invites", "Report server health"],
        "joinable": False,
    },
    "compute": {
        "role": "compute",
        "role_label": "App Host",
        "description": "Runs apps and services for your Pocket Lab.",
        "capabilities": ["Run apps", "Report device health", "Eligible for app installs"],
        "joinable": True,
    },
    "storage": {
        "role": "storage",
        "role_label": "Storage Node",
        "description": "Stores backups, files, or app data.",
        "capabilities": ["Store backups or app data", "Report storage health", "Eligible as backup/storage target"],
        "joinable": True,
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
    "server_host": "server_host",
    "server-host": "server_host",
    "server host": "server_host",
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
    return [
        {key: value for key, value in item.items() if key != "joinable"}
        for item in LITE_ROLES.values()
        if item.get("joinable", True)
    ]


def _is_loopback_or_unspecified_host(host: str | None) -> bool:
    value = str(host or "").strip().lower()
    if not value:
        return True
    if value in {"localhost", "localhost.localdomain", "testserver"}:
        return True
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        ip = ipaddress.ip_address(value)
        return ip.is_loopback or ip.is_unspecified
    except ValueError:
        return False


def _safe_ipv4(value: str | None) -> str | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if ip.version != 4 or ip.is_loopback or ip.is_unspecified or ip.is_link_local:
        return None
    return candidate


def _run_first_ipv4(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        value = _safe_ipv4(line)
        if value:
            return value
    return None


def _tailscale_ipv4() -> str | None:
    # Termux Tailscale installer exposes tailscale-cli; standard installs expose tailscale.
    return _run_first_ipv4(["tailscale-cli", "ip", "-4"]) or _run_first_ipv4(["tailscale", "ip", "-4"])


def _lan_ipv4() -> str | None:
    # UDP connect does not send traffic; it asks the OS which source IP would be used.
    for target in ("100.100.100.100", "8.8.8.8", "1.1.1.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(1)
                sock.connect((target, 80))
                value = _safe_ipv4(sock.getsockname()[0])
                if value:
                    return value
        except Exception:
            continue
    return None


def _request_scheme(request: Request | None) -> str:
    configured = os.environ.get("POCKETLAB_LITE_INVITE_SCHEME", "").strip().lower()
    if configured in {"http", "https"}:
        return configured
    if request is not None and request.url.scheme in {"http", "https"}:
        return request.url.scheme
    return "http"


def _request_port(request: Request | None) -> int:
    configured = os.environ.get("POCKETLAB_LITE_INVITE_PORT", "").strip()
    if configured:
        try:
            return int(configured)
        except ValueError:
            pass
    if request is not None and request.url.port:
        return int(request.url.port)
    return int(os.environ.get("DASH_PORT", "8443"))


def _format_host_for_url(host: str) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _compose_base_url(*, scheme: str, host: str, port: int) -> str:
    formatted_host = _format_host_for_url(host)
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        return f"{scheme}://{formatted_host}"
    return f"{scheme}://{formatted_host}:{port}"


def _strip_port(host: str | None) -> str | None:
    value = str(host or "").strip()
    if not value:
        return None
    if value.startswith("["):
        end = value.find("]")
        if end != -1:
            return value[1:end]
    if ":" in value and value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


def _request_host(request: Request | None) -> str | None:
    if request is None:
        return None
    host = _strip_port(request.url.hostname or request.headers.get("host"))
    if host:
        return host
    return None


def _normalize_nats_url(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"nats://{raw}"
    if not raw.startswith(("nats://", "tls://", "ws://", "wss://")):
        return None
    return raw


def bootstrap_host(request: Request | None) -> str | None:
    """Return a safe public-ish host for generated secondary-device scripts.

    The result intentionally comes from operator config, the incoming request host,
    Tailscale/Tailnet discovery, or LAN discovery. It never hardcodes a device
    address in source code.
    """
    configured_host = os.environ.get("POCKETLAB_LITE_BOOTSTRAP_HOST", "").strip()
    if configured_host and not _is_loopback_or_unspecified_host(configured_host):
        return configured_host

    host = _request_host(request)
    if host and not _is_loopback_or_unspecified_host(host):
        return host

    return _tailscale_ipv4() or _lan_ipv4()


def resolve_public_nats_url(request: Request | None) -> str:
    """Resolve the NATS URL that a newly invited Lite device should use.

    Priority:
    1. POCKETLAB_LITE_PUBLIC_NATS_URL
    2. POCKETLAB_PUBLIC_NATS_URL
    3. POCKETLAB_LITE_NATS_URL
    4. Incoming bootstrap request host -> nats://<host>:4222
    5. Autodetected Tailscale/Tailnet IPv4
    6. Autodetected LAN IPv4
    7. localhost fallback for single-device/local-only setups
    """
    for name in (
        "POCKETLAB_LITE_PUBLIC_NATS_URL",
        "POCKETLAB_PUBLIC_NATS_URL",
        "POCKETLAB_LITE_NATS_URL",
    ):
        configured = _normalize_nats_url(os.environ.get(name))
        if configured:
            return configured

    host = bootstrap_host(request)
    if host:
        return f"nats://{_format_host_for_url(host)}:4222"

    return "nats://127.0.0.1:4222"


def _bootstrap_url_from_invite_url(invite_url: str) -> str:
    return (
        invite_url.replace("/api/join.sh?", "/api/lite/fleet/agent/bootstrap.sh?", 1)
        .replace("/api/join?", "/api/lite/fleet/agent/bootstrap.sh?", 1)
    )


def _bootstrap_command(bootstrap_url: str | None) -> str | None:
    if not bootstrap_url:
        return None
    return f"curl -fsSL {bootstrap_url!r} | bash"


def _detected_invite_host(request: Request | None) -> str | None:
    configured_host = os.environ.get("POCKETLAB_LITE_INVITE_HOST", "").strip()
    if configured_host and not _is_loopback_or_unspecified_host(configured_host):
        return configured_host

    if request is not None:
        request_host = request.url.hostname
        if request_host and not _is_loopback_or_unspecified_host(request_host):
            return request_host

    return _tailscale_ipv4() or _lan_ipv4()


def _invite_base_url(request: Request | None) -> str:
    configured = os.environ.get("POCKETLAB_LITE_INVITE_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured

    scheme = _request_scheme(request)
    port = _request_port(request)
    detected_host = _detected_invite_host(request)
    if detected_host:
        return _compose_base_url(scheme=scheme, host=detected_host, port=port)

    if request is not None:
        return str(request.base_url).rstrip("/")
    return f"http://{deps.settings().host}:{deps.settings().port}"


def _invite_path() -> str:
    return os.environ.get("POCKETLAB_LITE_INVITE_PATH", "/api/join.sh").strip() or "/api/join.sh"


def _public_invite(
    record: dict[str, Any],
    *,
    url: str | None = None,
    bootstrap_url: str | None = None,
) -> dict[str, Any]:
    if not bootstrap_url and url:
        bootstrap_url = _bootstrap_url_from_invite_url(url)

    bootstrap_command = _bootstrap_command(bootstrap_url) or record.get("bootstrap_command")

    public = {
        "invite_id": record.get("invite_id"),
        "token_hint": record.get("token_hint"),
        "hostname": record.get("hostname"),
        "role": record.get("role"),
        "role_label": record.get("role_label"),
        "capabilities": record.get("capabilities") or [],
        "expires_at": record.get("expires_at"),
        "status": record.get("status", "pending"),
        "instructions": (
            "Run this in Termux on the new phone. Pocket Lab will set up "
            "the secure connection and start the device agent automatically."
        ),
        "bootstrap_url": bootstrap_url,
        "bootstrap_command": bootstrap_command,
    }
    if url:
        public["url"] = url
    if bootstrap_command:
        public["copy_text"] = bootstrap_command
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


def _append_local_evidence(
    record: dict[str, Any],
    *,
    event_type: str = "pocketlab.events.fleet.invite_created",
    audit_type: str = "pocketlab.audit.fleet.invite_created",
) -> None:
    safe = _safe_event_payload(record)
    for name, item_type in (
        ("fleet_invite_events.json", event_type),
        ("fleet_invite_audit.json", audit_type),
    ):
        payload = _read_state(name, {"events": [], "updated_at": None})
        if not isinstance(payload, dict):
            payload = {"events": [], "updated_at": None}
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        events.insert(0, {"event_type": item_type, "created_at": _now_iso(), **safe})
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
    bootstrap_url = _bootstrap_url_from_invite_url(invite_url)
    bootstrap_command = _bootstrap_command(bootstrap_url)

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

    public_invite = _public_invite(record, url=invite_url, bootstrap_url=bootstrap_url)
    return {
        "accepted": True,
        "status": "invite_ready",
        "summary": f"Invite ready for {hostname_text}.",
        "command_id": command_id,
        "job_id": command_id,
        "bootstrap_url": bootstrap_url,
        "bootstrap_command": bootstrap_command,
        "copy_text": bootstrap_command,
        "invite": public_invite,
        "event": _safe_event_payload(record),
    }


def active_invite_device_keys() -> set[str]:
    keys: set[str] = set()
    payload = _invites_payload()
    for item in payload.get("invites", []):
        if not isinstance(item, dict):
            continue
        if float(item.get("expires_at_epoch") or 0) <= _now_epoch():
            continue
        if int(item.get("uses_remaining") or 0) <= 0:
            continue
        if str(item.get("status") or "").lower() in {"accepted", "used", "joined", "expired"}:
            continue
        for value in (item.get("node_id"), item.get("hostname"), item.get("name")):
            if value:
                keys.add(str(value).strip().lower().replace("_", "-").replace(" ", "-"))
    return keys


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


def invite_token_status(token: str, role: str | None = None) -> tuple[str, dict[str, Any] | None]:
    if not token:
        return "missing", None

    try:
        expected_role = normalize_lite_role(role) if role else None
    except ValueError:
        return "invalid_role", None

    token_hash = _hash_token(token)
    payload = _invites_payload()

    for item in payload["invites"]:
        if not isinstance(item, dict):
            continue
        if item.get("token_hash") != token_hash:
            continue
        if expected_role and item.get("role") != expected_role:
            return "role_mismatch", item
        if float(item.get("expires_at_epoch") or 0) <= _now_epoch():
            return "expired", item
        if int(item.get("uses_remaining") or 0) <= 0 or str(item.get("status") or "").lower() in {
            "accepted",
            "used",
            "joined",
        }:
            return "used", item
        return "valid", item

    return "not_found", None


def validate_invite_token(token: str, role: str | None = None) -> dict[str, Any] | None:
    status, item = invite_token_status(token, role=role)
    return item if status == "valid" else None


def consume_invite_token(token: str, role: str | None = None) -> dict[str, Any] | None:
    status, item = invite_token_status(token, role=role)
    if status != "valid" or not item:
        return None

    payload = _invites_payload()
    invite_id = item.get("invite_id")
    updated: dict[str, Any] | None = None

    for existing in payload["invites"]:
        if not isinstance(existing, dict):
            continue
        if existing.get("invite_id") != invite_id:
            continue
        existing["uses_remaining"] = 0
        existing["status"] = "accepted"
        existing["accepted_at"] = _now_iso()
        existing["updated_at"] = _now_iso()
        updated = dict(existing)
        break

    if not updated:
        return None

    payload["updated_at"] = _now_iso()
    _write_state("fleet_invites.json", payload)

    upsert_agent(
        {
            "node_id": updated.get("node_id"),
            "hostname": updated.get("hostname"),
            "role": updated.get("role"),
            "status": "joining",
            "auth_token_hash": str(updated.get("token_hash") or "")[:16],
            "capabilities": updated.get("capabilities") or [],
        },
        event_type="fleet.agent_join_started",
    )

    _append_local_evidence(
        updated,
        event_type="pocketlab.events.fleet.invite_accepted",
        audit_type="pocketlab.audit.fleet.invite_accepted",
    )

    return updated


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
