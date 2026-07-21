from __future__ import annotations

import os
import socket
import subprocess
from typing import Any

from .. import deps
from .fleet_registry import fleet_health_snapshot, merged_fleet_nodes, normalize_node_id
from .live_status import LIVE_STATUS
from .nats_bus import BUS
from . import lite_backup, lite_catalog as lite_catalog_service, lite_device_capabilities, lite_invites, lite_security as lite_security_service

LITE_MODE = "lite"


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _status(value: Any, *, default: str = "unknown") -> str:
    raw = _text(value, default).strip().lower().replace(" ", "_")
    if raw in {"ok", "healthy", "ready", "success", "succeeded", "active", "online", "up"}:
        return "healthy"
    if raw in {"warning", "degraded", "partial", "stale", "needs_attention"}:
        return "degraded"
    if raw in {"agent_stopped", "repairing", "supervisor_repairing"}:
        return raw
    if raw in {"failed", "error", "unhealthy", "down", "offline"}:
        return "unhealthy"
    if raw in {"unavailable", "missing", "disabled", "not_configured"}:
        return "unavailable"
    return raw or default


def _service(name: str, status: Any, summary: str, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": name,
        "status": _status(status),
        "summary": summary,
    }
    item.update({k: v for k, v in extra.items() if v is not None})
    return item


def _overall(services: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "unknown") for item in services}
    if "unhealthy" in statuses:
        return "unhealthy"
    if statuses.intersection({"degraded", "unavailable", "unknown"}):
        return "degraded"
    return "healthy"


def _find_health_service(engine: dict[str, Any], *needles: str) -> dict[str, Any] | None:
    services = engine.get("services") if isinstance(engine, dict) else {}
    if not isinstance(services, dict):
        return None
    lowered = [needle.lower() for needle in needles]
    for key, value in services.items():
        haystack = f"{key} {value.get('name') if isinstance(value, dict) else ''}".lower()
        if all(needle in haystack for needle in lowered) and isinstance(value, dict):
            return value
    return None




def _run_remote_access_command(command: list[str], timeout: float = 1.5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _first_available_command(*names: str) -> str | None:
    for name in names:
        result = _run_remote_access_command(["sh", "-lc", f"command -v {name}"], timeout=0.8)
        if result and result.returncode == 0:
            value = result.stdout.strip().splitlines()
            if value:
                return value[0]
    return None


def _tailscaled_running() -> bool:
    result = _run_remote_access_command(["pgrep", "-f", "tailscaled"], timeout=0.8)
    if result and result.returncode == 0 and result.stdout.strip():
        return True
    result = _run_remote_access_command(["sh", "-lc", "ps -A 2>/dev/null | grep -v grep | grep -q tailscaled"], timeout=0.8)
    return bool(result and result.returncode == 0)


def _tailscale_ipv4_status() -> str | None:
    command = _first_available_command("tailscale-cli", "tailscale")
    if not command:
        return None
    result = _run_remote_access_command([command, "ip", "-4"], timeout=1.8)
    if not result or result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        value = line.strip()
        if value and not value.startswith("127."):
            return value
    return None


def _nats_reachable_on_host(host: str | None) -> bool:
    if not host:
        return False
    try:
        port = int(os.environ.get("POCKETLAB_LITE_NATS_PORT") or os.environ.get("POCKETLAB_PUBLIC_NATS_PORT") or "4222")
    except ValueError:
        port = 4222
    try:
        with socket.create_connection((host, port), timeout=0.8) as sock:
            sock.settimeout(0.5)
            try:
                sock.recv(120)
            except Exception:
                pass
        return True
    except Exception:
        return False


def lite_remote_access_status() -> dict[str, Any]:
    running = _tailscaled_running()
    ip = _tailscale_ipv4_status() if running else None
    nats_reachable = _nats_reachable_on_host(ip) if ip else False
    ready = bool(running and ip and nats_reachable)
    if ready:
        status = "healthy"
        summary = "Remote access is ready. Other devices can reach this Pocket Lab over the private network."
    elif running and ip:
        status = "degraded"
        summary = "Remote access is running, but the device command port is not reachable on the private network."
    else:
        status = "unavailable"
        summary = "Remote access not ready. Start Tailscale on the server phone so other devices can reconnect."
    return {
        "status": status,
        "running": bool(running),
        "ready": ready,
        "ip": ip if ready else None,
        "tailscale_ip": ip if ready else None,
        "nats_reachable": bool(nats_reachable),
        "summary": summary,
        "checked_at": deps.now_utc_iso(),
    }


def _mysql_socket_available() -> bool | None:
    candidates = [
        os.environ.get("POCKETLAB_MARIADB_SOCKET"),
        "/data/data/com.termux/files/usr/var/run/mysqld.sock",
        "/var/run/mysqld/mysqld.sock",
        "/tmp/mysql.sock",
    ]
    for candidate in [c for c in candidates if c]:
        try:
            if os.path.exists(candidate):
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.15)
                    sock.connect(candidate)
                return True
        except Exception:
            return False
    return None


async def build_lite_status() -> dict[str, Any]:
    """Build a user-facing Lite status summary without exposing tool internals."""
    deps.settings().ensure_dirs()
    now = deps.now_utc_iso()
    engine = deps.core.build_health_engine_snapshot()
    bus = BUS.status()
    live = LIVE_STATUS.status()
    remote_access = lite_remote_access_status()

    try:
        telemetry = await LIVE_STATUS.sample_telemetry(source="lite-status")
    except Exception as exc:  # pragma: no cover - environment dependent
        telemetry = {"status": "unknown", "summary": f"Telemetry unavailable: {exc}"}

    vault = _find_health_service(engine, "vault")
    gitea = _find_health_service(engine, "gitea")
    mariadb_socket = _mysql_socket_available()

    catalog_items_count = lite_catalog_service.catalog_apps_count()
    fleet = fleet_health_snapshot()
    fleet_nodes = merged_fleet_nodes()
    opa_evaluations = deps.core.build_opa_evaluations()
    blocked_findings = [
        item
        for item in opa_evaluations
        if _text(item.get("decision") or item.get("status")).lower()
        in {"deny", "failed", "blocked"}
    ]

    services = [
        _service(
            "Control API",
            engine.get("status", "unknown"),
            "Pocket Lab Lite API is serving local control-plane requests",
            source="FastAPI /health",
        ),
        _service(
            "Command Bus",
            "healthy" if bus.get("connected") and bus.get("jetstream_enabled") else "degraded",
            "NATS / JetStream is ready for worker-owned operations" if bus.get("connected") else "Command bus is not connected yet",
            source="FastAPI NATS status",
        ),
        _service(
            "Remote Access",
            remote_access.get("status"),
            remote_access.get("summary") or "Remote access status is being checked",
            source="Tailscale / NATS",
            tailnet_ip=remote_access.get("ip"),
        ),
        _service(
            "Worker Execution",
            "healthy" if live.get("running") else "degraded",
            "Worker heartbeat sampler is active" if live.get("running") else "Worker heartbeat is not active yet",
            source="FastAPI live status",
        ),
        _service(
            "App Catalog",
            "healthy" if catalog_items_count else "degraded",
            f"{catalog_items_count} app available" if catalog_items_count else "Catalog is empty or not refreshed yet",
        ),
        _service(
            "Identity & Access",
            (vault or {}).get("status", "unknown"),
            (vault or {}).get("summary") or "Vault readiness will appear after bootstrap initializes identity services",
        ),
        _service(
            "Device Fleet",
            fleet.get("status", "unknown"),
            f"{len(fleet_nodes)} device record(s) known to Pocket Lab Lite",
        ),
        _service(
            "Security",
            "degraded" if blocked_findings else "healthy",
            f"{len(blocked_findings)} item(s) need review" if blocked_findings else "No blocking safety findings in the current policy summary",
        ),
        _service(
            "Policy & Compliance",
            "degraded" if blocked_findings else "healthy",
            "Rules are reporting items that need review" if blocked_findings else "Basic protection rules are available",
        ),
        _service(
            "Recovery",
            "healthy",
            "Backup and restore actions are available through worker-owned typed operations",
        ),
    ]

    if gitea:
        services.append(
            _service(
                "Local Source Store",
                gitea.get("status", "unknown"),
                gitea.get("summary") or "Gitea status is available",
            )
        )

    if mariadb_socket is not None:
        services.append(
            _service(
                "Database",
                "healthy" if mariadb_socket else "degraded",
                "MariaDB socket is reachable" if mariadb_socket else "MariaDB socket was found but is not reachable",
            )
        )

    device = {
        "name": os.environ.get("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server"),
        "mode": LITE_MODE,
        "resource_profile": os.environ.get("POCKETLAB_RESOURCE_PROFILE", "low-power"),
        "tailnet_ip": remote_access.get("ip"),
        "remote_access": remote_access,
    }

    return {
        "overall": _overall(services),
        "checked_at": now,
        "device": device,
        "services": services,
        "summary": {
            "apps_available": catalog_items_count,
            "devices_known": len(fleet_nodes),
            "security_findings": len(blocked_findings),
            "nats_connected": bool(bus.get("connected")),
            "jetstream_enabled": bool(bus.get("jetstream_enabled")),
            "live_sampler_running": bool(live.get("running")),
            "remote_access_ready": bool(remote_access.get("ready")),
        },
        "telemetry": _lite_telemetry(telemetry),
    }


def _lite_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": _status(payload.get("status", "unknown")),
        "cpu_temp_c": payload.get("cpu_temp_c") or payload.get("cpuTemp"),
        "free_space_mb": payload.get("free_space_mb") or payload.get("freeSpaceMB"),
        "cpu_usage_percent": payload.get("cpu_usage_percent"),
        "memory_usage_mb": payload.get("memory_usage_mb"),
        "sampled_at": payload.get("sampled_at") or payload.get("time"),
    }


_DUMMY_DEVICE_IDS = {
    "pixel-edge-1",
    "pixel-edge-2",
    "localhost",
    "127-0-0-1",
    "demo-device",
    "example-device",
}


def _server_host_device(remote_access: dict[str, Any] | None = None) -> dict[str, Any]:
    now = deps.now_utc_iso()
    name = os.environ.get("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")
    node_id = normalize_node_id(os.environ.get("POCKETLAB_NODE_ID") or "pocket-lab-lite-server")
    role_info = lite_invites.role_metadata("server_host")
    remote_access = remote_access or lite_remote_access_status()
    ready = bool(remote_access.get("ready"))
    return {
        "id": node_id,
        "name": name,
        "status": "healthy",
        "last_seen": now,
        "last_seen_at": now,
        "remote_access": ready,
        "remote_access_status": remote_access.get("status"),
        "remote_access_summary": remote_access.get("summary"),
        "tailnet_ip": remote_access.get("ip") if ready else None,
        "connection": "online",
        "role": role_info["role"],
        "role_label": role_info["role_label"],
        "capabilities": lite_device_capabilities.capability_ids_for_role("server_host"),
        "capability_labels": lite_device_capabilities.labels_for_capabilities(lite_device_capabilities.capability_ids_for_role("server_host")),
        "is_current": True,
        "source": "lite-server",
    }


def _device_identity(item: dict[str, Any]) -> str:
    return normalize_node_id(str(item.get("id") or item.get("node_id") or item.get("hostname") or item.get("name") or ""))


def _is_dummy_device(item: dict[str, Any]) -> bool:
    identity = _device_identity(item)
    name = normalize_node_id(str(item.get("name") or item.get("hostname") or ""))
    if identity in _DUMMY_DEVICE_IDS or name in _DUMMY_DEVICE_IDS:
        return True
    if identity.startswith("pixel-edge-") or name.startswith("pixel-edge-"):
        return True
    return False


def _is_static_fleet_record(item: dict[str, Any]) -> bool:
    """Return True for full-app/demo/static fleet records that should not appear in Lite.

    Lite should show the local Server Host plus real invite/agent lifecycle records.
    Static fleet inventory from the full app can leak names such as worker2,
    samsung-nfs, localhost, or pixel-edge-* into the Lite Devices tab.
    """
    source = str(item.get("source") or "fleet").strip().lower()
    identity = _device_identity(item)
    name = normalize_node_id(str(item.get("name") or item.get("hostname") or ""))

    if _is_dummy_device(item):
        return True

    if identity in {"worker1", "worker2", "worker3"}:
        return True

    if source in {"fleet", "static", "demo", ""} and not any(
        item.get(key)
        for key in (
            "agent_version",
            "last_seen_at",
            "auth_token_hash",
            "accepted_at",
            "created_at",
        )
    ):
        return True

    # If a static full-app record uses the Android/Termux hostname, merge/ignore it
    # rather than showing it as a second device beside the canonical Server Host.
    local_hostname = normalize_node_id(socket.gethostname())
    if source in {"fleet", "static", "demo", ""} and name and name == local_hostname:
        return True

    return False


def _is_current_server_record(item: dict[str, Any]) -> bool:
    identity = _device_identity(item)
    local_names = {
        "localhost",
        "127-0-0-1",
        normalize_node_id(socket.gethostname()),
        normalize_node_id(os.environ.get("HOSTNAME") or ""),
        normalize_node_id(os.environ.get("POCKETLAB_DEVICE_NAME") or ""),
        "pocket-lab",
        "pocket-lab-lite",
        "pocket-lab-lite-server",
    }
    return bool(item.get("isCurrent") or item.get("is_current") or identity in local_names)


def _device_status_rank(status: str) -> int:
    value = str(status or "").strip().lower()
    if value in {"healthy", "active", "online", "ready"}:
        return 40
    if value in {"joining", "accepted", "setup_started"}:
        return 30
    if value in {"invited", "pending", "invite_sent"}:
        return 20
    if value in {"degraded", "stale", "warning"}:
        return 10
    return 0


def _connection_label(status: str) -> str:
    value = str(status or "").strip().lower()
    if value in {"healthy", "active", "online", "ready"}:
        return "online"
    if value in {"joining", "accepted", "setup_started"}:
        return "joining"
    if value in {"invited", "pending", "invite_sent"}:
        return "waiting"
    if value in {"agent_stopped", "stopped"}:
        return "stopped"
    if value in {"repairing", "supervisor_repairing"}:
        return "repairing"
    if value in {"unhealthy", "offline", "failed", "stale", "degraded"}:
        return "offline"
    return "unknown"


def _lite_device_from_node(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict) or _is_dummy_device(item):
        return None

    raw_role = item.get("role") or "compute"
    try:
        role_info = lite_invites.role_metadata(str(raw_role))
    except ValueError:
        role_info = lite_invites.role_metadata("compute")

    raw_status = str(item.get("status") or item.get("agent_status") or "unknown").lower()
    if raw_status == "active":
        status = "healthy"
    elif raw_status in {"invited", "pending"}:
        status = "invited"
    elif raw_status in {"joining", "accepted"}:
        status = "joining"
    elif raw_status in {"agent_stopped", "repairing", "supervisor_repairing"}:
        status = raw_status
    else:
        status = _status(raw_status)

    last_seen = (
        item.get("last_seen")
        or item.get("last_seen_at")
        or item.get("updated_at")
        or item.get("accepted_at")
        or item.get("created_at")
    )

    return {
        "id": item.get("id") or item.get("node_id") or _device_identity(item),
        "name": item.get("name") or item.get("hostname") or item.get("node_id") or "Device",
        "status": status,
        "last_seen": last_seen,
        "last_seen_at": last_seen,
        "remote_access": bool(item.get("tailnet_ip") or item.get("tailscale_ip") or item.get("ip")),
        "connection": _connection_label(status),
        "role": role_info["role"],
        "role_label": role_info["role_label"],
        "capabilities": lite_device_capabilities.capability_ids_for_role(role_info["role"]),
        "capability_labels": lite_device_capabilities.labels_for_capabilities(lite_device_capabilities.capability_ids_for_role(role_info["role"])),
        "source": item.get("source") or "fleet",
        "agent_process_status": item.get("agent_process_status"),
        "supervisor_status": item.get("supervisor_status"),
        "last_supervisor_at": item.get("last_supervisor_at"),
        "supervisor_repair_count": item.get("supervisor_repair_count"),
        "last_supervisor_repair_at": item.get("last_supervisor_repair_at"),
        "storage": item.get("storage") if isinstance(item.get("storage"), dict) else None,
        "available_gb": item.get("available_gb") or item.get("free_storage_gb") or item.get("storage_available_gb"),
        "media_roots": item.get("media_roots") if isinstance(item.get("media_roots"), list) else [],
    }


def _lite_device_merge_key(device: dict[str, Any]) -> str:
    role = str(device.get("role") or "")
    if role == "server_host":
        return str(device.get("id") or "pocket-lab-lite-server")

    identity = normalize_node_id(str(device.get("id") or ""))
    name = normalize_node_id(str(device.get("name") or ""))

    # Collapse pending invite IDs into their intended device name.
    if identity.startswith("pending-") and name:
        return name

    return name or identity


def _merge_lite_device(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if _device_status_rank(incoming.get("status")) >= _device_status_rank(existing.get("status")):
        merged = {**existing, **incoming}
    else:
        merged = {**incoming, **existing}
    merged["last_seen"] = incoming.get("last_seen") or existing.get("last_seen")
    merged["last_seen_at"] = incoming.get("last_seen_at") or existing.get("last_seen_at")
    merged["remote_access"] = bool(existing.get("remote_access") or incoming.get("remote_access"))
    merged["connection"] = _connection_label(str(merged.get("status") or "unknown"))
    return merged


def lite_catalog() -> dict[str, Any]:
    return lite_catalog_service.catalog_payload()


def lite_identity() -> dict[str, Any]:
    engine = deps.core.build_health_engine_snapshot()
    vault = _find_health_service(engine, "vault") or {}
    return {
        "status": _status(vault.get("status", "unknown")),
        "summary": vault.get("summary") or "Vault readiness will appear after bootstrap initializes identity services",
        "actions": ["change_password", "rotate_secret"],
    }


def lite_security() -> dict[str, Any]:
    return lite_security_service.current_state()


def lite_fleet() -> dict[str, Any]:
    nodes = merged_fleet_nodes()
    active_invite_keys = lite_invites.active_invite_device_keys()
    remote_access = lite_remote_access_status()
    server = _server_host_device(remote_access)
    server_id = str(server["id"])
    devices_by_id: dict[str, dict[str, Any]] = {server_id: server}

    for item in nodes:
        if not isinstance(item, dict):
            continue

        if _is_static_fleet_record(item):
            continue

        if _is_current_server_record(item):
            # Current-server records may appear as localhost or the Android/Termux hostname.
            # Merge only useful connectivity/last-seen data into the canonical Server Host row.
            incoming = _lite_device_from_node({**item, "role": "server_host", "status": "healthy"})
            if incoming:
                incoming["id"] = server_id
                incoming["name"] = server["name"]
                incoming["is_current"] = True
                devices_by_id[server_id] = _merge_lite_device(devices_by_id[server_id], incoming)
            continue

        device = _lite_device_from_node(item)
        if not device:
            continue

        key = _lite_device_merge_key(device)
        if not key or key in _DUMMY_DEVICE_IDS:
            continue

        if (
            str(device.get("status") or "").lower() in {"invited", "pending", "invite_sent"}
            and key not in active_invite_keys
        ):
            continue

        existing = devices_by_id.get(key)
        devices_by_id[key] = _merge_lite_device(existing, device) if existing else device

    devices = sorted(
        (lite_device_capabilities.apply_device_capabilities(item) for item in devices_by_id.values()),
        key=lambda item: (0 if item.get("role") == "server_host" else 1, str(item.get("name") or "")),
    )

    fleet_status = "healthy" if any(item.get("role") == "server_host" for item in devices) else fleet_health_snapshot().get("status", "unknown")

    return {
        "status": fleet_status,
        "devices": devices,
        "count": len(devices),
        "roles": lite_invites.lite_role_options(),
        "remote_access": remote_access,
        "latest_invite": lite_invites.latest_invite(),
        "capability_summary": lite_device_capabilities.catalog_device_summary(devices),
        "updated_at": deps.now_utc_iso(),
    }


def lite_policy() -> dict[str, Any]:
    state = deps.core.read_json_file(deps.settings().state_dir / "opa.json", {"enforce_mode": False})
    security = lite_security()
    return {
        "status": security["status"],
        "summary": "Protection rules are enabled" if state.get("enforce_mode") else "Protection rules are available in advisory mode",
        "protection_enabled": bool(state.get("enforce_mode", False)),
        "requires_confirmation": True,
        "allowed_actions": ["install_app", "add_device", "run_safety_check", "backup_now"],
    }


def lite_recovery() -> dict[str, Any]:
    return lite_backup.recovery_status()


def lite_recovery_summary() -> dict[str, Any]:
    return lite_backup.recovery_summary()


def lite_recovery_details() -> dict[str, Any]:
    return lite_backup.recovery_details()
