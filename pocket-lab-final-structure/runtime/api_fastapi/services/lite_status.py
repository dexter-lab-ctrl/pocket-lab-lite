from __future__ import annotations

import os
import socket
from typing import Any

from .. import deps
from .fleet_registry import fleet_health_snapshot, merged_fleet_nodes
from .live_status import LIVE_STATUS
from .nats_bus import BUS
from . import lite_invites

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

    try:
        telemetry = await LIVE_STATUS.sample_telemetry(source="lite-status")
    except Exception as exc:  # pragma: no cover - environment dependent
        telemetry = {"status": "unknown", "summary": f"Telemetry unavailable: {exc}"}

    vault = _find_health_service(engine, "vault")
    gitea = _find_health_service(engine, "gitea")
    mariadb_socket = _mysql_socket_available()

    catalog_items = deps.core.build_catalog_view()
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
            "Worker Execution",
            "healthy" if live.get("running") else "degraded",
            "Worker heartbeat sampler is active" if live.get("running") else "Worker heartbeat is not active yet",
            source="FastAPI live status",
        ),
        _service(
            "App Catalog",
            "healthy" if catalog_items else "degraded",
            f"{len(catalog_items)} catalog item(s) available" if catalog_items else "Catalog is empty or not refreshed yet",
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
        "name": os.environ.get("POCKETLAB_DEVICE_NAME", "pocket-lab"),
        "mode": LITE_MODE,
        "resource_profile": os.environ.get("POCKETLAB_RESOURCE_PROFILE", "low-power"),
        "tailnet_ip": os.environ.get("TAILSCALE_IP") or os.environ.get("POCKETLAB_TAILNET_IP"),
    }

    return {
        "overall": _overall(services),
        "checked_at": now,
        "device": device,
        "services": services,
        "summary": {
            "apps_available": len(catalog_items),
            "devices_known": len(fleet_nodes),
            "security_findings": len(blocked_findings),
            "nats_connected": bool(bus.get("connected")),
            "jetstream_enabled": bool(bus.get("jetstream_enabled")),
            "live_sampler_running": bool(live.get("running")),
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


def lite_catalog() -> dict[str, Any]:
    items = deps.core.build_catalog_view()
    simple_items: list[dict[str, Any]] = []
    for item in items:
        name = _text(item.get("name") or item.get("title") or item.get("id") or "App")
        simple_items.append(
            {
                "id": _text(item.get("id") or item.get("slug") or name).lower().replace(" ", "-"),
                "name": name,
                "status": _status(item.get("status", "available"), default="available"),
                "summary": _text(item.get("summary") or item.get("description") or "Ready to install and manage"),
                "installed": bool(item.get("installed", False)),
            }
        )
    return {"items": simple_items, "count": len(simple_items), "updated_at": deps.now_utc_iso()}


def lite_identity() -> dict[str, Any]:
    engine = deps.core.build_health_engine_snapshot()
    vault = _find_health_service(engine, "vault") or {}
    return {
        "status": _status(vault.get("status", "unknown")),
        "summary": vault.get("summary") or "Vault readiness will appear after bootstrap initializes identity services",
        "actions": ["change_password", "rotate_secret"],
    }


def lite_security() -> dict[str, Any]:
    evaluations = deps.core.build_opa_evaluations()
    findings = [
        item
        for item in evaluations
        if _text(item.get("decision") or item.get("status")).lower()
        in {"deny", "failed", "blocked"}
    ]
    return {
        "status": "needs_attention" if findings else "healthy",
        "summary": f"{len(findings)} item(s) need review" if findings else "No critical issues in the current safety summary",
        "findings_count": len(findings),
        "checks_count": len(evaluations),
        "last_checked": deps.now_utc_iso(),
    }


def lite_fleet() -> dict[str, Any]:
    nodes = merged_fleet_nodes()
    devices: list[dict[str, Any]] = []
    for item in nodes:
        role = item.get("role") or "compute"
        try:
            role_info = lite_invites.role_metadata(str(role))
        except ValueError:
            role_info = lite_invites.role_metadata("compute")
        devices.append(
            {
                "id": item.get("id") or item.get("node_id") or item.get("name"),
                "name": item.get("name") or item.get("hostname") or item.get("node_id") or "Device",
                "status": _status(item.get("status", "unknown")),
                "last_seen": item.get("last_seen") or item.get("last_seen_at") or item.get("updated_at"),
                "remote_access": bool(item.get("tailnet_ip") or item.get("tailscale_ip")),
                "role": role_info["role"],
                "role_label": role_info["role_label"],
                "capabilities": role_info["capabilities"],
            }
        )
    return {
        "status": fleet_health_snapshot().get("status", "unknown"),
        "devices": devices,
        "count": len(devices),
        "roles": lite_invites.lite_role_options(),
        "latest_invite": lite_invites.latest_invite(),
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
    runs = deps.operation_service().list(limit=50)
    backup_runs = [
        run for run in runs if _text(run.get("operation")).lower() in {"backup_now", "backup_verify", "restore_backup"}
    ]
    latest = backup_runs[0] if backup_runs else None
    return {
        "status": _status((latest or {}).get("status", "unknown")) if latest else "unknown",
        "summary": "Recovery actions are ready" if latest else "No backup activity has been recorded yet",
        "last_activity": latest,
        "actions": ["backup_now", "restore"],
    }
