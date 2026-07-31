from __future__ import annotations

import os
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from .. import deps
from .fleet_registry import fleet_health_snapshot, list_commands, merged_fleet_nodes, normalize_node_id
from .live_status import LIVE_STATUS
from .nats_bus import BUS
from . import (
    lite_backup,
    lite_catalog as lite_catalog_service,
    lite_device_awareness,
    lite_device_capabilities,
    lite_device_health,
    lite_invites,
    lite_security as lite_security_service,
)

LITE_MODE = "lite"


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


_PUBLIC_PROFILE_TEXT_FIELDS = (
    "os_family", "os_name", "os_version", "security_patch", "manufacturer",
    "technical_model", "device_codename", "architecture", "architecture_raw",
    "architecture_family", "android_abi", "kernel",
    "runtime_type", "termux_version", "python_version", "agent_version",
    "supervisor_version", "collection_status", "profile_status", "collected_at",
    "profile_updated_at", "freshness",
)


def _public_text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").strip().split())
    return "".join(character for character in text if ord(character) >= 32 and ord(character) != 127)[:limit]


def _public_system_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    profile = {
        field: _public_text(value.get(field), 160)
        for field in _PUBLIC_PROFILE_TEXT_FIELDS
        if value.get(field) not in (None, "")
    }
    try:
        schema_version = int(value.get("schema_version") or 0)
    except (TypeError, ValueError):
        schema_version = 0
    if 1 <= schema_version <= 100:
        profile["schema_version"] = schema_version
    try:
        revision = int(value.get("revision") or 0)
    except (TypeError, ValueError):
        revision = 0
    if revision > 0:
        profile["revision"] = revision
    try:
        api_level = int(value.get("android_api_level"))
    except (TypeError, ValueError):
        api_level = 0
    if 1 <= api_level <= 999:
        profile["android_api_level"] = api_level
    consumer = _public_text(value.get("consumer_model_name"), 80)
    technical = _public_text(value.get("technical_model"), 160)
    codename = _public_text(value.get("device_codename"), 160)
    collected_at = _public_text(value.get("collected_at") or value.get("profile_updated_at"), 64)
    if collected_at:
        try:
            age_seconds = max(0.0, (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
            ).total_seconds())
            profile["freshness"] = "current" if age_seconds <= 24 * 60 * 60 else "stale"
        except (TypeError, ValueError):
            profile["freshness"] = "stale"
    else:
        profile["freshness"] = "unavailable"
    profile["consumer_model_name"] = consumer
    profile["display_model"] = consumer or technical or codename or "Device"
    return profile


def _uptime_label(value: Any) -> str:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return "Unavailable"
    if seconds < 0 or seconds > 20 * 365 * 86400:
        return "Unavailable"
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ", ".join(parts[:2])


def _public_system_health(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    uptime_status = _public_text(value.get("uptime_status") or value.get("collection_status") or "unavailable", 32)
    health = {
        "collection_status": _public_text(value.get("collection_status") or uptime_status, 32),
        "uptime_status": uptime_status,
        "load_status": _public_text(value.get("load_status") or "unavailable", 32),
        "collected_at": _public_text(value.get("collected_at") or value.get("health_updated_at"), 64) or None,
        "health_updated_at": _public_text(value.get("health_updated_at") or value.get("collected_at"), 64) or None,
    }
    try:
        uptime_seconds = int(value.get("uptime_seconds"))
    except (TypeError, ValueError):
        uptime_seconds = None
    if uptime_seconds is not None and 0 <= uptime_seconds <= 20 * 365 * 86400:
        health["uptime_seconds"] = uptime_seconds
        health["uptime_label"] = _uptime_label(uptime_seconds)
    loads = value.get("load_average") if isinstance(value.get("load_average"), list) else [
        value.get("load_average_1m"), value.get("load_average_5m"), value.get("load_average_15m")
    ]
    normalized_loads = []
    for candidate in list(loads)[:3]:
        try:
            number = float(candidate)
        except (TypeError, ValueError):
            normalized_loads.append(None)
            continue
        normalized_loads.append(round(number, 3) if 0 <= number <= 100_000 else None)
    health["load_average"] = normalized_loads
    return health


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


def _nats_reachable_on_host(host: str | None, port: int | None = None) -> bool:
    if not host:
        return False
    if port is None:
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


def lite_secondary_nats_status() -> dict[str, Any]:
    """Probe configured secondary NATS reachability without returning its URL."""
    configured = str(os.environ.get("POCKETLAB_NATS_URL") or "").strip()
    if not configured:
        return {
            "configured": False,
            "reachable": False,
            "route_selection": "primary" if BUS.status().get("connected") else "unavailable",
            "sanitized": True,
        }
    try:
        parsed = urlsplit(configured if "://" in configured else f"nats://{configured}")
        host = parsed.hostname
        port = int(parsed.port or 4222)
    except (TypeError, ValueError):
        host = None
        port = 4222
    reachable = _nats_reachable_on_host(host, port) if host else False
    primary = bool(BUS.status().get("connected"))
    return {
        "configured": True,
        "reachable": bool(reachable),
        "route_selection": "secondary" if reachable else "primary" if primary else "unavailable",
        "sanitized": True,
    }


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


def _build_lite_status_from_inputs(
    *,
    checked_at: str,
    engine: dict[str, Any],
    bus: dict[str, Any],
    live: dict[str, Any],
    remote_access: dict[str, Any],
    telemetry: dict[str, Any],
    fleet: dict[str, Any],
    fleet_nodes: list[dict[str, Any]],
    current_state: dict[str, Any],
) -> dict[str, Any]:
    vault = _find_health_service(engine, "vault")
    gitea = _find_health_service(engine, "gitea")
    mariadb_socket = _mysql_socket_available()

    catalog_items_count = lite_catalog_service.catalog_apps_count()
    try:
        from .lite_control_plane_store import CONTROL_PLANE

        fleet_health_summary = CONTROL_PLANE.fleet_health_summary()
    except Exception:
        fleet_health_summary = {
            "status": "unavailable",
            "device_count": 0,
            "attention_count": 0,
            "by_status": {},
            "by_severity": {},
            "attention_by_category": {},
            "sanitized": True,
        }
    device_health_attention_current = bool(
        fleet_health_summary.get("status") == "ready"
        and max(0, int(fleet_health_summary.get("device_count") or 0)) == len(fleet_nodes)
    )
    device_health_attention = (
        max(0, int(fleet_health_summary.get("attention_count") or 0))
        if device_health_attention_current
        else 0
    )
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
            tailnet_ip=remote_access.get("tailnet_ip") or remote_access.get("ip"),
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
            "degraded" if device_health_attention_current and device_health_attention else fleet.get("status", "unknown"),
            (
                f"{device_health_attention} device health item(s) need review"
                if device_health_attention
                else f"{len(fleet_nodes)} device record(s) known to Pocket Lab Lite"
            ),
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

    tailnet_ip = remote_access.get("tailnet_ip") or remote_access.get("ip")
    device = {
        "name": os.environ.get("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server"),
        "mode": LITE_MODE,
        "resource_profile": os.environ.get("POCKETLAB_RESOURCE_PROFILE", "low-power"),
        "tailnet_ip": tailnet_ip if remote_access.get("ready") else None,
        "remote_access": remote_access,
    }

    return {
        "overall": _overall(services),
        "checked_at": checked_at,
        "device": device,
        "services": services,
        "summary": {
            "apps_available": catalog_items_count,
            "devices_known": len(fleet_nodes),
            "device_health_attention": device_health_attention,
            "device_health_attention_current": device_health_attention_current,
            "device_health_summary": {
                "by_status": fleet_health_summary.get("by_status") or {},
                "by_severity": fleet_health_summary.get("by_severity") or {},
            },
            "security_findings": len(blocked_findings),
            "nats_connected": bool(bus.get("connected")),
            "jetstream_enabled": bool(bus.get("jetstream_enabled")),
            "live_sampler_running": bool(live.get("running")),
            "remote_access_ready": bool(remote_access.get("ready")),
        },
        "telemetry": _lite_telemetry(telemetry),
        "system_current_state": current_state,
        "projection_only": True,
        "sanitized": True,
    }


def default_lite_status_state() -> dict[str, Any]:
    """Safe request-path fallback while the first background projection warms."""
    services = [
        _service(
            "Control API",
            "healthy",
            "Pocket Lab Lite API is serving local control-plane requests",
            source="FastAPI",
        ),
        _service(
            "Command Bus",
            "unknown",
            "Command delivery status is being refreshed",
        ),
        _service(
            "Remote Access",
            "unavailable",
            "Remote access not ready",
        ),
    ]
    return {
        "overall": "degraded",
        "checked_at": None,
        "device": {
            "name": os.environ.get("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server"),
            "mode": LITE_MODE,
            "resource_profile": os.environ.get("POCKETLAB_RESOURCE_PROFILE", "low-power"),
            "tailnet_ip": None,
            "remote_access": {
                "status": "unavailable",
                "ready": False,
                "summary": "Remote access not ready",
                "sanitized": True,
            },
        },
        "services": services,
        "summary": {
            "apps_available": 0,
            "devices_known": 0,
            "device_health_attention": 0,
            "device_health_attention_current": False,
            "device_health_summary": {"by_status": {}, "by_severity": {}},
            "security_findings": 0,
            "nats_connected": False,
            "jetstream_enabled": False,
            "live_sampler_running": False,
            "remote_access_ready": False,
        },
        "telemetry": {"status": "unknown"},
        "system_current_state": {},
        "projection_only": True,
        "read_degraded": True,
        "refresh_pending": True,
        "retry_after_seconds": 2,
        "sanitized": True,
    }


def build_lite_status_projection() -> dict[str, Any]:
    """Build the status projection in scheduler/background context only."""
    deps.settings().ensure_dirs()
    from .lite_control_plane_store import CONTROL_PLANE
    from . import lite_phase3b_projections as phase3b

    dependency_builders = (
        ("system.processes", phase3b.collect_process_state),
        ("system.agent", phase3b.collect_agent_state),
        ("system.supervisor", phase3b.collect_supervisor_state),
        ("system.nats_remote", phase3b.collect_nats_remote_state),
        ("system.remote_access", phase3b.collect_remote_access_state),
        ("system.fleet_probe", phase3b.collect_fleet_probe_state),
        ("security.summary", phase3b.collect_security_summary_state),
    )
    for domain, collector in dependency_builders:
        if phase3b.snapshot(domain):
            continue
        try:
            phase3b.project(domain, collector())
        except Exception:
            # Keep the last-good prepared dependency when one bounded collector fails.
            continue
    prepared_health = phase3b.snapshot("system.health")
    if prepared_health:
        components = (
            prepared_health.get("components")
            if isinstance(prepared_health.get("components"), dict)
            else {}
        )
        engine = {
            "status": components.get("api") or prepared_health.get("status") or "unknown",
            "services": (
                prepared_health.get("services")
                if isinstance(prepared_health.get("services"), dict)
                else {}
            ),
        }
    else:
        engine = deps.core.build_health_engine_snapshot()
        try:
            phase3b.project("system.health", phase3b.collect_system_health_state(engine))
        except Exception:
            pass
    snapshots = {
        domain: phase3b.snapshot(domain) or {}
        for domain in (
            "system.health",
            "system.processes",
            "system.agent",
            "system.supervisor",
            "system.remote_access",
            "system.nats_remote",
            "system.fleet_probe",
            "security.summary",
            "system.telemetry_thresholds",
            "system.storage_pressure",
            "system.sqlite_health",
            "system.activity_current",
            "system.activity_history",
        )
    }
    bus = snapshots["system.nats_remote"] or BUS.status()
    live = LIVE_STATUS.status()
    remote_access = snapshots["system.remote_access"] or lite_remote_access_status()
    semantic_telemetry = snapshots["system.telemetry_thresholds"]
    raw_telemetry = LIVE_STATUS.last_telemetry_snapshot()
    if not raw_telemetry:
        try:
            raw_telemetry = deps.core.telemetry_snapshot()
        except Exception:
            raw_telemetry = {"status": "unknown"}
    telemetry = dict(raw_telemetry) if isinstance(raw_telemetry, dict) else {"status": "unknown"}
    if isinstance(semantic_telemetry, dict) and semantic_telemetry:
        # Preserve worker-prepared semantic status while retaining the local numeric
        # capacity sample required by the Home UI. Never let one projection replace
        # the other: mixed-version agents may provide only a subset of these fields.
        telemetry.update(semantic_telemetry)

    prepared_fleet = CONTROL_PLANE.fleet_projection_snapshot() or {}
    fleet_nodes = prepared_fleet.get("devices") if isinstance(prepared_fleet.get("devices"), list) else []
    if fleet_nodes:
        fleet = snapshots["system.fleet_probe"] or {
            "status": prepared_fleet.get("status", "unknown"),
            "summary": prepared_fleet.get("summary") or {},
        }
    else:
        # First warm-up only. Request handlers never call this builder.
        fleet = fleet_health_snapshot()
        fleet_nodes = merged_fleet_nodes()

    stable_times = [
        str(value.get("updated_at") or "")
        for value in snapshots.values()
        if value.get("updated_at")
    ]
    checked_at = max(stable_times) if stable_times else deps.now_utc_iso()
    from . import lite_phase3c_projections

    activity_summary = lite_phase3c_projections.compose_activity_summary(
        snapshots["system.activity_current"],
        snapshots["system.activity_history"],
    )
    current_state = {
        "health": snapshots["system.health"],
        "processes": snapshots["system.processes"],
        "agent": snapshots["system.agent"],
        "supervisor": snapshots["system.supervisor"],
        "remote_access": snapshots["system.remote_access"],
        "nats_remote": snapshots["system.nats_remote"],
        "fleet_probe": snapshots["system.fleet_probe"],
        "security_summary": snapshots["security.summary"],
        "telemetry_thresholds": snapshots["system.telemetry_thresholds"],
        "storage_pressure": snapshots["system.storage_pressure"],
        "sqlite_health": snapshots["system.sqlite_health"],
        "activity_summary": activity_summary,
        "activity_current": snapshots["system.activity_current"],
        "activity_history": snapshots["system.activity_history"],
        "sanitized": True,
    }
    return _build_lite_status_from_inputs(
        checked_at=checked_at,
        engine=engine,
        bus=bus,
        live=live,
        remote_access=remote_access,
        telemetry=telemetry,
        fleet=fleet,
        fleet_nodes=fleet_nodes,
        current_state=current_state,
    )


async def build_lite_status() -> dict[str, Any]:
    """Compatibility builder; normal GET /status uses prepared state only."""
    return build_lite_status_projection()


def _lite_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("devices"), list) or isinstance(payload.get("counts"), dict):
        return {
            "status": _status(payload.get("status", "unknown")),
            "summary": str(payload.get("summary") or "Telemetry is not available.")[:192],
            "counts": payload.get("counts") if isinstance(payload.get("counts"), dict) else {},
            "device_count": len(payload.get("devices") or []),
            "semantic": True,
            # Semantic health and numeric capacity are complementary. Keep both so
            # Home can show measured RAM/CPU/storage while respecting health tone.
            "cpu_temp_c": payload.get("cpu_temp_c") or payload.get("cpuTemp"),
            "free_space_mb": payload.get("free_space_mb") or payload.get("freeSpaceMB"),
            "total_space_mb": payload.get("total_space_mb") or payload.get("totalSpaceMB"),
            "cpu_usage_percent": payload.get("cpu_usage_percent"),
            "memory_usage_mb": payload.get("memory_usage_mb"),
            "memory_total_mb": payload.get("memory_total_mb") or payload.get("memoryTotalMB"),
            "memory_free_mb": payload.get("memory_free_mb") or payload.get("memoryFreeMB"),
            "sampled_at": payload.get("sampled_at") or payload.get("time") or payload.get("updated_at"),
        }
    return {
        "status": _status(payload.get("status", "unknown")),
        "cpu_temp_c": payload.get("cpu_temp_c") or payload.get("cpuTemp"),
        "free_space_mb": payload.get("free_space_mb") or payload.get("freeSpaceMB"),
        "total_space_mb": payload.get("total_space_mb") or payload.get("totalSpaceMB"),
        "cpu_usage_percent": payload.get("cpu_usage_percent"),
        "memory_usage_mb": payload.get("memory_usage_mb"),
        "memory_total_mb": payload.get("memory_total_mb") or payload.get("memoryTotalMB"),
        "memory_free_mb": payload.get("memory_free_mb") or payload.get("memoryFreeMB"),
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
    """Build the protected host from canonical identity plus last-good projections."""
    now = deps.now_utc_iso()
    name = os.environ.get("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")
    node_id = normalize_node_id(
        os.environ.get("POCKETLAB_SERVER_NODE_ID")
        or os.environ.get("POCKETLAB_NODE_ID")
        or "pocket-lab-lite-server"
    )
    role_info = lite_invites.role_metadata("server_host")
    remote_access = remote_access or lite_remote_access_status()
    ready = bool(remote_access.get("ready"))

    profile_record: dict[str, Any] = {}
    supervisor_record: dict[str, Any] = {}
    try:
        from .lite_control_plane_store import CONTROL_PLANE

        profiles = CONTROL_PLANE.device_profile_map()
        supervisors = CONTROL_PLANE.supervisor_state_map()
        profile_record = profiles.get(node_id) or profiles.get("pocket-lab-lite-server") or {}
        supervisor_record = supervisors.get(node_id) or supervisors.get("pocket-lab-lite-server") or {}
    except Exception:
        # Prepared fleet reads retain their last-good snapshot when this transient
        # lookup fails; do not fabricate fresh profile timestamps.
        pass

    system_profile = _public_system_profile(profile_record.get("system_profile"))
    system_health = _public_system_health(profile_record.get("system_health"))
    profile_at = _public_text(system_profile.get("collected_at") or system_profile.get("profile_updated_at"), 64) or None

    process_snapshot: dict[str, Any] = {}
    agent_snapshot: dict[str, Any] = {}
    supervisor_snapshot: dict[str, Any] = {}
    try:
        from . import lite_phase3b_projections as phase3b

        process_snapshot = phase3b.snapshot("system.processes") or {}
        agent_snapshot = phase3b.snapshot("system.agent") or {}
        supervisor_snapshot = phase3b.snapshot("system.supervisor") or {}
    except Exception:
        pass

    process_items = {
        str(item.get("name") or ""): item
        for item in (process_snapshot.get("items") or [])
        if isinstance(item, dict)
    }
    agent_item = next((
        item for item in (agent_snapshot.get("items") or [])
        if isinstance(item, dict) and normalize_node_id(item.get("device_id")) == node_id
    ), {})
    supervisor_item = next((
        item for item in (supervisor_snapshot.get("items") or [])
        if isinstance(item, dict) and normalize_node_id(item.get("device_id")) == node_id
    ), {})

    agent_pm2 = _public_text((process_items.get("pocket-node-agent") or {}).get("status"), 32) \
        or _public_text(agent_item.get("process_status"), 32) or "unknown"
    supervisor_pm2 = _public_text((process_items.get("pocketlab-core-supervisor") or {}).get("status"), 32) or "unknown"
    evidence_status = _public_text(supervisor_record.get("supervisor_status"), 32)
    projected_status = _public_text(
        supervisor_item.get("supervisor_status")
        or supervisor_snapshot.get("supervisor_status"), 32
    )
    supervisor_status = evidence_status or projected_status or "unknown"
    supervisor_process_status = _public_text(
        supervisor_record.get("supervisor_process_status"), 32
    ) or supervisor_pm2
    supervisor_at = _public_text(
        supervisor_record.get("checked_at")
        or supervisor_item.get("checked_at")
        or supervisor_snapshot.get("checked_at")
        or supervisor_snapshot.get("updated_at"), 64
    ) or None
    supervisor_freshness = _public_text(supervisor_record.get("freshness"), 24)
    if not supervisor_freshness and supervisor_at:
        try:
            observed = datetime.fromisoformat(supervisor_at.replace("Z", "+00:00"))
            age_seconds = max(0, int((datetime.now(timezone.utc) - observed).total_seconds()))
            supervisor_freshness = "fresh" if age_seconds <= 180 else "stale"
        except (TypeError, ValueError):
            supervisor_freshness = "saved"
    agent_version = _public_text(system_profile.get("agent_version"), 80)
    supervisor_version = _public_text(supervisor_record.get("supervisor_version") or system_profile.get("supervisor_version"), 80)
    profile_ready = bool(system_profile.get("technical_model") or system_profile.get("architecture_family") or system_profile.get("architecture"))
    supervisor_ready = bool(supervisor_status in {"healthy", "online", "available"} and supervisor_freshness == "fresh")

    field_freshness = {
        "heartbeat": {"state": "current", "reported_at": now, "source": "protected_host_runtime"},
        "telemetry": {"state": "current", "reported_at": now, "source": "protected_host_runtime"},
        "system_profile": {"state": system_profile.get("freshness") or "unavailable", "reported_at": profile_at, "source": "sqlite_last_good_profile" if profile_at else "unavailable"},
        "supervisor": {"state": supervisor_freshness, "reported_at": supervisor_at, "source": supervisor_record.get("source") or "prepared_process_projection"},
        "capabilities": {"state": "current", "reported_at": now, "source": "protected_host_policy"},
        "remote_access": {"state": "current" if remote_access.get("checked_at") else "saved", "reported_at": remote_access.get("checked_at"), "source": "tailscale_runtime"},
    }

    return {
        "id": node_id,
        "node_id": node_id,
        "name": name,
        "status": "healthy",
        "last_seen": now,
        "last_seen_at": now,
        "remote_access": ready,
        "remote_access_status": remote_access.get("status"),
        "remote_access_summary": remote_access.get("summary"),
        "tailscale_installed": bool(_first_available_command("tailscale-cli", "tailscale")),
        "tailscaled_running": bool(remote_access.get("running")),
        "tailnet_ip_ready": bool(remote_access.get("ip")),
        "nats_tailnet_reachable": bool(remote_access.get("nats_reachable")),
        "tailnet_ip": remote_access.get("ip") if ready else None,
        "connection": "online",
        "role": role_info["role"],
        "role_label": role_info["role_label"],
        "capabilities": lite_device_capabilities.capability_ids_for_role("server_host"),
        "advertised_capabilities": [
            "host_apps", "run_safety_checks", "receive_commands",
            "supervisor_recovery", "remote_access", "serve_control_plane",
            "access_phone_media",
        ],
        "capability_schema_version": 1,
        "capability_labels": lite_device_capabilities.labels_for_capabilities(
            lite_device_capabilities.capability_ids_for_role("server_host")
        ),
        "identity_status": "protected_server_host",
        "identity_owner": "durable_enrollment_registry",
        "enrollment_status": "ready",
        "identity_verified_at": now,
        "enrolled_at": now,
        "first_ready_at": now,
        "last_heartbeat_at": now,
        "last_system_profile_at": profile_at,
        "last_capabilities_at": now,
        "last_nats_connected_at": now,
        "last_tailnet_ready_at": now if ready else None,
        "agent_version": agent_version,
        "agent_version_source": "last_valid_system_profile" if agent_version else "unknown",
        "agent_version_freshness": system_profile.get("freshness") or "unknown",
        "agent_process_status": agent_pm2,
        "agent_process_status_source": "protected_host_pm2_projection" if agent_pm2 != "unknown" else "unknown",
        "agent_process_status_freshness": "saved" if process_snapshot.get("updated_at") else "unknown",
        "supervisor_status": supervisor_status,
        "supervisor_version": supervisor_version or _public_text(
            supervisor_item.get("supervisor_version")
            or supervisor_snapshot.get("version"), 80
        ),
        "supervisor_process_status": supervisor_process_status,
        "supervisor_status_source": supervisor_record.get("source") or ("protected_host_supervisor_projection" if projected_status else "unknown"),
        "supervisor_status_freshness": supervisor_freshness,
        "supervisor_evidence_schema_version": supervisor_record.get("evidence_schema_version"),
        "last_supervisor_heartbeat_at": supervisor_at,
        "recovery_available": supervisor_ready,
        "system_profile": system_profile,
        "system_health": system_health,
        "field_freshness": field_freshness,
        "convergence": {
            "state": "ready" if profile_ready and supervisor_ready else "waiting_for_details",
            "profile_ready": profile_ready,
            "supervisor_ready": supervisor_ready,
            "last_good_projection": bool(profile_record or supervisor_record),
            "target_seconds": 45,
        },
        "is_current": True,
        "protected_server_host": True,
        "source": "lite-server-canonical",
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
    result = {
        "id": item.get("id") or item.get("node_id") or _device_identity(item),
        "name": item.get("name") or item.get("hostname") or item.get("node_id") or "Device",
        "status": status,
        "agent_status": item.get("agent_status") or raw_status,
        "last_seen": last_seen,
        "last_seen_at": last_seen,
        "remote_access": bool(item.get("tailnet_ip") or item.get("tailscale_ip") or item.get("ip")),
        "tailnet_ip": item.get("tailnet_ip") or item.get("tailscale_ip") or None,
        "connection": _connection_label(status),
        "role": role_info["role"],
        "role_label": role_info["role_label"],
        "capabilities": item.get("capabilities") if isinstance(item.get("capabilities"), list) else lite_device_capabilities.capability_ids_for_role(role_info["role"]),
        "capability_labels": item.get("capability_labels") if isinstance(item.get("capability_labels"), list) else lite_device_capabilities.labels_for_capabilities(
            item.get("capabilities") if isinstance(item.get("capabilities"), list) else lite_device_capabilities.capability_ids_for_role(role_info["role"])
        ),
        "advertised_capabilities": item.get("advertised_capabilities") if isinstance(item.get("advertised_capabilities"), list) else item.get("capabilities") if isinstance(item.get("capabilities"), list) else [],
        "source": item.get("source") or "fleet",
        "agent_process_status": item.get("agent_process_status"),
        "supervisor_process_status": item.get("supervisor_process_status"),
        "supervisor_status": item.get("supervisor_status"),
        "supervisor_evidence_schema_version": item.get("supervisor_evidence_schema_version"),
        "supervisor_evidence_delivery_status": item.get("supervisor_evidence_delivery_status"),
        "last_supervisor_at": item.get("last_supervisor_at"),
        "supervisor_repair_count": item.get("supervisor_repair_count"),
        "last_supervisor_repair_at": item.get("last_supervisor_repair_at"),
        "storage": item.get("storage") if isinstance(item.get("storage"), dict) else None,
        "available_gb": item.get("available_gb") or item.get("free_storage_gb") or item.get("storage_available_gb"),
        "media_roots": item.get("media_roots") if isinstance(item.get("media_roots"), list) else [],
        "system_profile": _public_system_profile(item.get("system_profile")),
        "system_health": _public_system_health(item.get("system_health")),
        "supervisor_version": item.get("supervisor_version"),
        "_health_signals": {
            "telemetry": item.get("telemetry") if isinstance(item.get("telemetry"), dict) else {},
            "health": item.get("health") if isinstance(item.get("health"), dict) else {},
            "storage": item.get("storage") if isinstance(item.get("storage"), dict) else {},
            "reconnect_count": item.get("reconnect_count"),
            "supervisor_repair_count": item.get("supervisor_repair_count"),
            "agent_version": item.get("agent_version"),
            "supervisor_version": item.get("supervisor_version"),
            "capability_schema_version": item.get("capability_schema_version"),
        },
    }
    runtime_agent_version = _public_text(item.get("agent_version"), 80)
    runtime_supervisor_version = _public_text(item.get("supervisor_version"), 80)
    profile = result.get("system_profile") if isinstance(result.get("system_profile"), dict) else {}
    profile_agent_version = _public_text(profile.get("agent_version"), 80)
    profile_supervisor_version = _public_text(profile.get("supervisor_version"), 80)
    profile_is_fresh = str(profile.get("freshness") or "").lower() == "current"
    runtime_is_fresh = result.get("connection") == "online"

    def select_version(runtime_value: str, profile_value: str, runtime_source: str) -> tuple[str, str, str]:
        if runtime_value and runtime_is_fresh:
            return runtime_value, runtime_source, "fresh"
        if profile_value and profile_is_fresh:
            return profile_value, "system_profile", "fresh"
        if runtime_value:
            return runtime_value, "last_valid_runtime", "saved"
        if profile_value:
            return profile_value, "last_valid_system_profile", "saved"
        return "unknown", "unknown", "unknown"

    selected_agent_version, agent_source, agent_freshness = select_version(
        runtime_agent_version, profile_agent_version, "runtime_heartbeat"
    )
    selected_supervisor_version, supervisor_source, supervisor_freshness = select_version(
        runtime_supervisor_version, profile_supervisor_version, "runtime_supervisor_event"
    )
    result.update({
        "agent_version": selected_agent_version,
        "agent_version_source": agent_source,
        "agent_version_freshness": agent_freshness,
        "supervisor_version": selected_supervisor_version,
        "supervisor_version_source": supervisor_source,
        "supervisor_version_freshness": supervisor_freshness,
        "system_profile": {
            **profile,
            "agent_version": selected_agent_version,
            "supervisor_version": selected_supervisor_version,
        },
    })
    if item.get("last_supervisor_at") or item.get("last_supervisor_heartbeat_at"):
        result["supervisor_status_source"] = "runtime_supervisor_event"
        result["supervisor_status_freshness"] = "fresh" if runtime_is_fresh else "saved"

    passthrough = (
        "invite_created_at", "invite_accepted_at", "enrolled_at",
        "first_heartbeat_at", "first_supervisor_heartbeat_at", "first_ready_at",
        "last_join_attempt_at", "last_successful_join_at", "enrollment_status",
        "identity_status", "identity_verified_at", "identity_mismatch_count",
        "last_identity_mismatch_at", "last_identity_reason_code",
        "blocked_join_count", "last_blocked_join_at", "repair_required",
        "repair_reason_code", "last_heartbeat_at", "last_telemetry_at",
        "last_system_profile_at", "last_capabilities_at", "last_supervisor_heartbeat_at",
        "last_command_received_at", "last_command_completed_at",
        "last_nats_connected_at", "last_nats_disconnected_at",
        "last_tailnet_ready_at", "last_recovery_at", "last_recovery_result",
        "tailscale_installed", "tailscaled_running", "tailnet_ip_ready",
        "nats_tailnet_reachable", "remote_access_status",
    )
    for field in passthrough:
        if item.get(field) not in (None, ""):
            result[field] = item.get(field)
    return result

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
    existing_profile = existing.get("system_profile") if isinstance(existing.get("system_profile"), dict) else {}
    incoming_profile = incoming.get("system_profile") if isinstance(incoming.get("system_profile"), dict) else {}
    existing_health = existing.get("system_health") if isinstance(existing.get("system_health"), dict) else {}
    incoming_health = incoming.get("system_health") if isinstance(incoming.get("system_health"), dict) else {}
    if existing_profile or incoming_profile:
        merged["system_profile"] = _public_system_profile({**existing_profile, **incoming_profile})
    if existing_health or incoming_health:
        merged["system_health"] = _public_system_health({**existing_health, **incoming_health})
    def freshest_timestamp(*values: Any) -> Any:
        candidates: list[tuple[float, Any]] = []
        for value in values:
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                candidates.append((parsed.timestamp(), value))
            except (TypeError, ValueError):
                continue
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
        return next((value for value in values if value), None)

    merged["last_seen"] = freshest_timestamp(
        incoming.get("last_seen"), existing.get("last_seen")
    )
    merged["last_seen_at"] = freshest_timestamp(
        incoming.get("last_seen_at"), existing.get("last_seen_at")
    )
    for timestamp_key in (
        "last_heartbeat_at", "last_telemetry_at", "last_health_at",
        "last_system_profile_at", "last_supervisor_heartbeat_at",
        "last_capabilities_at", "last_nats_connected_at",
        "last_tailnet_ready_at",
    ):
        merged[timestamp_key] = freshest_timestamp(
            incoming.get(timestamp_key), existing.get(timestamp_key)
        )
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
    # Durable enrollment is the canonical fleet owner. Live agents, heartbeats
    # and invites enrich it but cannot remove an enrolled identity by omission.
    # Let a registry read failure abort this refresh so the prepared-read layer
    # keeps serving the last valid fleet instead of rebuilding from discovery only.
    from .lite_control_plane_store import CONTROL_PLANE

    nodes = CONTROL_PLANE.durable_enrolled_devices()
    nodes.extend(lite_invites.enrolled_invite_nodes())
    nodes.extend(merged_fleet_nodes())
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

    try:
        from .lite_control_plane_store import CONTROL_PLANE

        profile_map = CONTROL_PLANE.device_profile_map()
        supervisor_map = CONTROL_PLANE.supervisor_state_map()
    except Exception:
        profile_map = {}
        supervisor_map = {}

    merged_devices = []
    for item in devices_by_id.values():
        profile = profile_map.get(str(item.get("id") or ""))
        if profile:
            live_profile = item.get("system_profile") if isinstance(item.get("system_profile"), dict) else {}
            projected_profile = profile.get("system_profile") if isinstance(profile.get("system_profile"), dict) else {}
            consumer_model_name = _public_text(projected_profile.get("consumer_model_name"), 80)
            merged_profile = _public_system_profile({**projected_profile, **live_profile})
            merged_profile["consumer_model_name"] = consumer_model_name
            merged_profile["display_model"] = (
                consumer_model_name
                or _public_text(merged_profile.get("technical_model"), 160)
                or _public_text(merged_profile.get("device_codename"), 160)
                or "Device"
            )
            live_health = item.get("system_health") if isinstance(item.get("system_health"), dict) else {}
            projected_health = profile.get("system_health") if isinstance(profile.get("system_health"), dict) else {}
            item = {
                **item,
                "system_profile": merged_profile,
                "system_health": _public_system_health({**projected_health, **live_health}),
            }
        supervisor = supervisor_map.get(str(item.get("id") or ""))
        if supervisor:
            item = {
                **item,
                "supervisor_status": supervisor.get("supervisor_status") or item.get("supervisor_status") or "unknown",
                "supervisor_version": supervisor.get("supervisor_version") or item.get("supervisor_version") or "",
                "supervisor_process_status": supervisor.get("supervisor_process_status") or item.get("supervisor_process_status") or "unknown",
                "agent_process_status": supervisor.get("agent_process_status") or item.get("agent_process_status") or "unknown",
                "supervisor_status_source": supervisor.get("source") or "sqlite_supervisor_evidence",
                "supervisor_status_freshness": supervisor.get("freshness") or "stale",
                "supervisor_evidence_schema_version": supervisor.get("evidence_schema_version"),
                "last_supervisor_heartbeat_at": supervisor.get("checked_at") or item.get("last_supervisor_heartbeat_at"),
                "recovery_available": bool(
                    supervisor.get("freshness") == "fresh"
                    and supervisor.get("supervisor_status") in {"healthy", "online", "available", "repairing"}
                ),
            }
        profile_value = item.get("system_profile") if isinstance(item.get("system_profile"), dict) else {}
        profile_ready = bool(profile_value.get("technical_model") or profile_value.get("architecture_family") or profile_value.get("architecture"))
        supervisor_ready = bool(item.get("supervisor_status_freshness") == "fresh" and item.get("supervisor_status") in {"healthy", "online", "available", "repairing"})
        item["convergence"] = {
            "state": "ready" if profile_ready and supervisor_ready else "waiting_for_details",
            "profile_ready": profile_ready,
            "supervisor_ready": supervisor_ready,
            "last_good_projection": bool(profile or supervisor),
            "target_seconds": 45,
        }
        item["field_freshness"] = {
            "heartbeat": {"reported_at": item.get("last_heartbeat_at") or item.get("last_seen_at"), "source": "agent_heartbeat"},
            "telemetry": {"reported_at": item.get("last_telemetry_at"), "source": "agent_telemetry"},
            "system_profile": {"reported_at": item.get("last_system_profile_at") or profile_value.get("collected_at"), "source": "sqlite_last_good_profile" if profile else "agent_profile"},
            "supervisor": {"reported_at": item.get("last_supervisor_heartbeat_at"), "state": item.get("supervisor_status_freshness") or "unavailable", "source": item.get("supervisor_status_source") or "unknown"},
            "capabilities": {"reported_at": item.get("last_capabilities_at"), "source": "agent_capabilities"},
            "remote_access": {"reported_at": item.get("last_tailnet_ready_at"), "source": "agent_private_connection"},
        }
        merged_devices.append(item)

    try:
        CONTROL_PLANE.reconcile_command_lifecycle(limit=100)
        commands = list_commands(limit=500)
    except Exception:
        commands = []
    merged_devices = lite_device_awareness.enrich_devices(
        merged_devices, remote_access=remote_access, commands=commands
    )

    try:
        from .lite_control_plane_store import CONTROL_PLANE

        previous_health = CONTROL_PLANE.device_health_map()
    except Exception:
        previous_health = {}
    health_summary = {
        "healthy": 0,
        "watch": 0,
        "needs_attention": 0,
        "degraded": 0,
        "repairing": 0,
        "unreachable": 0,
        "unknown": 0,
        "attention_count": 0,
    }
    assessed_devices = []
    for item in merged_devices:
        device_id = str(item.get("id") or item.get("node_id") or "")
        signals = item.pop("_health_signals", {}) if isinstance(item.get("_health_signals"), dict) else {}
        health = lite_device_health.evaluate_device_health(
            item,
            signals=signals,
            previous=previous_health.get(device_id, {}),
        )
        item["proactive_health"] = health
        item["health_status"] = health.get("status")
        item["health_severity"] = health.get("severity")
        item["attention_count"] = int(health.get("attention_count") or 0)
        health_key = str(health.get("status") or "unknown")
        if health_key not in health_summary:
            health_key = "unknown"
        health_summary[health_key] += 1
        health_summary["attention_count"] += int(health.get("attention_count") or 0)
        assessed_devices.append(item)
    merged_devices = assessed_devices

    devices = sorted(
        merged_devices,
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
        "health_summary": health_summary,
        "staleness_policy": {
            "recently_offline_seconds": lite_device_awareness.RECENTLY_OFFLINE_SECONDS,
            "stale_seconds": lite_device_awareness.STALE_SECONDS,
            "review_seconds": lite_device_awareness.REVIEW_SECONDS,
        },
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
