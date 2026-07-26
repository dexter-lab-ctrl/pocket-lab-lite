from __future__ import annotations

"""Phase 3B bounded Security and system current-state projections.

Revision callbacks in this module read only bounded SQLite/in-memory lifecycle
state. Shell/network collectors are used only by scheduler builders or bounded
reconciliation, never by request handlers or semantic revision callbacks.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from typing import Any, Callable

from .. import deps
from ..db.connection import database_path
from ..db.migrations import apply_migrations
from ..db.runtime import SQLITE_READS, SQLITE_WRITER
from .nats_bus import BUS


PHASE3B_DOMAINS = (
    "security.progress",
    "security.summary",
    "system.status",
    "system.health",
    "system.processes",
    "system.agent",
    "system.supervisor",
    "system.remote_access",
    "system.nats_remote",
    "system.fleet_probe",
)

PHASE3C_DOMAINS = (
    "system.telemetry_thresholds",
    "system.storage_pressure",
    "system.sqlite_health",
    "system.activity_summary",
)

SYSTEM_CURRENT_STATE_DOMAINS = PHASE3B_DOMAINS + PHASE3C_DOMAINS

EXPECTED_PM2_PROCESSES = (
    "pocket-api",
    "pocket-worker",
    "pocket-nats",
    "pocket-node-agent",
    "pocketlab-core-supervisor",
    "caddy-proxy",
    "pocketlab-app-photoprism",
)

_MAX_PAYLOAD_BYTES = 48 * 1024
_MAX_ITEMS = 128
_MAX_DEPTH = 7
_SENSITIVE_KEY = re.compile(
    r"(?:token|password|passwd|secret|credential|api[_-]?key|private[_-]?key|"
    r"authorization|cookie|environment|env|command_line|raw|log|evidence|"
    r"nats_url|server_url|database_url|certificate|peer)",
    re.IGNORECASE,
)
_VOLATILE_KEY = re.compile(
    r"(?:^|_)(?:checked|generated|sampled|observed|updated|created|started|"
    r"completed|received|published|seen)_at(?:$|_)|(?:uptime|pid|cpu|memory|"
    r"latency|duration(?:_ms)?|elapsed(?:_ms)?|poll_count|published|received)$",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_ms(value: str | None = None) -> int:
    if not value:
        return int(time.time() * 1000)
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except (TypeError, ValueError):
        return int(time.time() * 1000)


def _database_instance() -> str:
    path = database_path()
    try:
        stat = path.stat()
        raw = f"{path}:{stat.st_dev}:{stat.st_ino}"
    except OSError:
        raw = f"{path}:missing"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _safe_text(value: Any, limit: int = 192) -> str:
    return str(value or "").strip()[:limit]


def _sanitize(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return None
    if key and _SENSITIVE_KEY.search(key):
        return None
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for child_key in sorted(value, key=lambda item: str(item))[:_MAX_ITEMS]:
            name = str(child_key)[:96]
            if _SENSITIVE_KEY.search(name):
                continue
            child = _sanitize(value[child_key], key=name, depth=depth + 1)
            if child is not None and child not in ({}, []):
                output[name] = child
        return output
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_sanitize(item, depth=depth + 1) for item in list(value)[:_MAX_ITEMS]]
        return [item for item in items if item is not None and item not in ({}, [])]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return max(-(2**63), min(2**63 - 1, value))
    if isinstance(value, float):
        return round(value, 3)
    if value is None:
        return None
    text = _safe_text(value, 320)
    if "//" in text or text.startswith(("/data/", "/home/", "/storage/", "/sdcard/")):
        return "[hidden]"
    return text


def _canonical_material(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item))[:_MAX_ITEMS]:
            name = str(key)
            if _SENSITIVE_KEY.search(name) or _VOLATILE_KEY.search(name):
                continue
            child = _canonical_material(value[key])
            if child is not None and child not in ({}, []):
                output[name[:96]] = child
        return output
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_canonical_material(item) for item in list(value)[:_MAX_ITEMS]]
        visible = [item for item in items if item is not None and item not in ({}, [])]
        return sorted(visible, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), default=str))
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 3)
    if value is None:
        return None
    return _safe_text(value, 192)


def semantic_revision(namespace: str, material: Any) -> int:
    blob = json.dumps(
        {"namespace": _safe_text(namespace, 96), "schema_version": 1, "material": _canonical_material(material)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    value = int.from_bytes(hashlib.sha256(blob.encode("utf-8")).digest()[:8], "big")
    return max(1, value & ((1 << 63) - 1))


def _bounded_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    clean = _sanitize(payload)
    if not isinstance(clean, dict):
        clean = {}
    clean.pop("collector_duration_ms", None)
    clean["sanitized"] = True
    encoded = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        clean = {
            "status": _safe_text(clean.get("status") or "degraded", 32),
            "summary": "Prepared state exceeded the bounded payload budget.",
            "truncated": True,
            "item_count": min(_MAX_ITEMS, int(clean.get("item_count") or 0)),
            "sanitized": True,
        }
        encoded = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    return clean, encoded


def _read(
    callback: Callable[[sqlite3.Connection], Any], *, ensure_schema: bool = True
) -> Any:
    if ensure_schema:
        apply_migrations()
    entry, _ = SQLITE_READS.acquire(timeout_seconds=1.0)
    discard = False
    try:
        return callback(entry.connection)
    except sqlite3.Error:
        discard = True
        raise
    finally:
        SQLITE_READS.release(entry, discard=discard)


def snapshot(domain: str) -> dict[str, Any] | None:
    safe_domain = _safe_text(domain, 96).lower()
    if safe_domain not in SYSTEM_CURRENT_STATE_DOMAINS:
        return None

    def read(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT domain,status,generation,source_revision,projection_revision,payload_json,"
            "item_count,collector_duration_ms,updated_at FROM phase3b_current_state WHERE domain=?",
            (safe_domain,),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        payload.setdefault("status", str(row["status"] or "unknown"))
        payload.update(
            {
                "domain": safe_domain,
                "generation": int(row["generation"] or 0),
                "source_revision": int(row["source_revision"] or 0),
                "projection_revision": int(row["projection_revision"] or 0),
                "item_count": int(row["item_count"] or 0),
                "collector_duration_ms": round(float(row["collector_duration_ms"] or 0.0), 3),
                "updated_at": str(row["updated_at"] or ""),
                "projection_only": True,
                "sanitized": True,
            }
        )
        return payload

    return _read(read, ensure_schema=safe_domain in PHASE3B_DOMAINS)


def projection_revision(domain: str) -> int:
    row = snapshot(domain)
    return int((row or {}).get("projection_revision") or 0)


def project(domain: str, payload: dict[str, Any]) -> int:
    safe_domain = _safe_text(domain, 96).lower()
    if safe_domain not in SYSTEM_CURRENT_STATE_DOMAINS:
        raise ValueError("unsupported prepared system projection domain")
    clean, encoded = _bounded_payload(payload)
    status = _safe_text(clean.get("status") or clean.get("overall") or "unknown", 32).lower() or "unknown"
    generation = max(0, int(clean.get("generation") or 0))
    source_revision = semantic_revision(safe_domain, clean)
    item_count = min(_MAX_ITEMS, max(0, int(clean.get("item_count") or len(clean.get("items") or []))))
    collector_duration_ms = max(
        0.0, min(float(payload.get("collector_duration_ms") or 0.0), 300_000.0)
    )
    now = _utc_now()

    def write(conn: sqlite3.Connection) -> int:
        prior = conn.execute(
            "SELECT projection_revision,status,generation,source_revision,payload_json "
            "FROM phase3b_current_state WHERE domain=?",
            (safe_domain,),
        ).fetchone()
        unchanged = bool(
            prior
            and str(prior["status"] or "") == status
            and int(prior["generation"] or 0) == generation
            and int(prior["source_revision"] or 0) == source_revision
        )
        if unchanged:
            return int(prior["projection_revision"] or 0)
        next_revision = max(1, int(prior["projection_revision"] or 0) + 1 if prior else 1)
        conn.execute(
            """
            INSERT INTO phase3b_current_state(
                domain,status,generation,source_revision,projection_revision,payload_json,
                item_count,collector_duration_ms,updated_at,updated_at_epoch_ms,sanitized
            ) VALUES (?,?,?,?,?,?,?,?,?,?,1)
            ON CONFLICT(domain) DO UPDATE SET
                status=excluded.status,
                generation=excluded.generation,
                source_revision=excluded.source_revision,
                projection_revision=excluded.projection_revision,
                payload_json=excluded.payload_json,
                item_count=excluded.item_count,
                collector_duration_ms=excluded.collector_duration_ms,
                updated_at=excluded.updated_at,
                updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                sanitized=1
            """,
            (
                safe_domain,
                status,
                generation,
                source_revision,
                next_revision,
                encoded,
                item_count,
                collector_duration_ms,
                now,
                _epoch_ms(now),
            ),
        )
        conn.execute(
            """
            INSERT INTO domain_revisions(domain,revision,updated_at) VALUES (?,1,?)
            ON CONFLICT(domain) DO UPDATE SET
                revision=domain_revisions.revision+1,
                updated_at=excluded.updated_at
            """,
            (safe_domain, now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO phase3b_revision_events(
                database_instance,domain,projection_revision,source_revision,reason,
                occurred_at,occurred_at_epoch_ms,sanitized
            ) VALUES (?,?,?,?,?,?,?,1)
            """,
            (
                _database_instance(),
                safe_domain,
                next_revision,
                source_revision,
                "semantic_state_changed",
                now,
                _epoch_ms(now),
            ),
        )
        conn.execute(
            "DELETE FROM phase3b_revision_events WHERE event_id NOT IN "
            "(SELECT event_id FROM phase3b_revision_events ORDER BY event_id DESC LIMIT 2048)"
        )
        return next_revision

    previous_revision = projection_revision(safe_domain)
    revision = int(
        SQLITE_WRITER.submit(f"phase3b.project.{safe_domain}", write, deadline_seconds=2.0)
    )
    if revision != previous_revision and safe_domain in {"security.progress", "security.summary"}:
        try:
            from . import lite_phase3c_projections

            lite_phase3c_projections.mark_dirty(
                "system.activity_summary", reason="security_projection_changed"
            )
        except Exception:
            pass
    return revision


def _bus_material() -> dict[str, Any]:
    status = BUS.status()
    durable = status.get("durable_consumer_health") if isinstance(status.get("durable_consumer_health"), dict) else {}
    return {
        "connected": bool(status.get("connected")),
        "jetstream_enabled": bool(status.get("jetstream_enabled")),
        "reconnect_pending": bool(status.get("reconnect_pending")),
        "watchdog_running": bool(status.get("watchdog_running")),
        "last_connected_at": status.get("last_connected_at"),
        "last_disconnected_at": status.get("last_disconnected_at"),
        "durable_consumer_health": {
            str(name)[:80]: {
                "healthy": bool(item.get("healthy")),
                "generation": int(item.get("generation") or 0),
                "recoveries": int(item.get("recoveries") or 0),
                "task_alive": bool(item.get("task_alive")),
                "subscription_present": bool(item.get("subscription_present")),
                "callback_inflight": bool(item.get("callback_inflight")),
            }
            for name, item in sorted(durable.items())[:32]
            if isinstance(item, dict)
        },
    }


def nats_remote_source_revision() -> int:
    current = snapshot("system.nats_remote") or {}
    return semantic_revision(
        "system.nats_remote",
        {
            "bus": _bus_material(),
            "secondary_configured": current.get("secondary_configured"),
            "secondary_reachable": current.get("secondary_reachable"),
            "route_selection": current.get("route_selection"),
            "database_instance": _database_instance(),
        },
    )


def collect_nats_remote_state() -> dict[str, Any]:
    from . import lite_status

    material = _bus_material()
    secondary = lite_status.lite_secondary_nats_status()
    connected = bool(material.get("connected"))
    jetstream = bool(material.get("jetstream_enabled"))
    consumers = material.get("durable_consumer_health") or {}
    consumers_healthy = all(bool(item.get("healthy")) for item in consumers.values()) if consumers else connected
    secondary_configured = bool(secondary.get("configured"))
    secondary_reachable = bool(secondary.get("reachable"))
    status = "healthy" if connected and jetstream and consumers_healthy else "degraded" if connected else "unavailable"
    if secondary_configured and not secondary_reachable and status == "healthy":
        status = "degraded"
    return {
        "status": status,
        "connected": connected,
        "jetstream_enabled": jetstream,
        "reconnect_pending": bool(material.get("reconnect_pending")),
        "watchdog_running": bool(material.get("watchdog_running")),
        "durable_consumer_health": consumers,
        "primary_ready": connected,
        "secondary_configured": secondary_configured,
        "secondary_reachable": secondary_reachable,
        "secondary_ready": secondary_reachable if secondary_configured else None,
        "route_selection": _safe_text(
            secondary.get("route_selection")
            or ("primary" if connected else "unavailable"),
            24,
        ),
        "summary": "Command delivery is ready." if status == "healthy" else "Command delivery needs attention.",
        "item_count": len(consumers),
        "generation": semantic_revision("system.nats_remote.generation", material),
        "sanitized": True,
    }


def _pm2_binary() -> str | None:
    return shutil.which("pm2")


def collect_process_state() -> dict[str, Any]:
    started = time.monotonic()
    pm2 = _pm2_binary()
    if not pm2:
        return {
            "status": "unknown",
            "summary": "Process manager status is not available.",
            "items": [],
            "item_count": 0,
            "pm2_available": False,
            "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
            "sanitized": True,
        }
    try:
        result = subprocess.run(
            [pm2, "jlist"],
            check=False,
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        rows = json.loads(result.stdout or "[]") if result.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError):
        rows = []
    by_name = {
        str(row.get("name") or ""): row
        for row in rows[:256]
        if isinstance(row, dict) and row.get("name")
    }
    items: list[dict[str, Any]] = []
    for name in EXPECTED_PM2_PROCESSES:
        row = by_name.get(name) or {}
        env = row.get("pm2_env") if isinstance(row.get("pm2_env"), dict) else {}
        status = _safe_text(env.get("status") or "missing", 24).lower()
        restart_generation = max(0, int(env.get("restart_time") or 0))
        items.append(
            {
                "name": name,
                "expected": name != "pocketlab-app-photoprism",
                "status": status,
                "running": status == "online",
                "restart_generation": restart_generation,
                "exit_generation": max(0, int(env.get("unstable_restarts") or 0)),
                "failure_type": _safe_text(env.get("exit_code") if status not in {"online", "missing"} else "", 40),
            }
        )
    required = [item for item in items if item.get("expected")]
    missing_required = [item for item in required if item.get("status") != "online"]
    overall = "healthy" if not missing_required else "degraded"
    return {
        "status": overall,
        "summary": (
            "Core processes are online."
            if overall == "healthy"
            else "One or more core processes need attention."
        ),
        "pm2_available": True,
        "items": items,
        "item_count": len(items),
        "generation": semantic_revision("system.processes.generation", items),
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }


def process_source_revision() -> int:
    current = snapshot("system.processes") or {}
    return semantic_revision(
        "system.processes",
        {
            "status": current.get("status"),
            "generation": current.get("generation"),
            "items": current.get("items") or [],
            "database_instance": _database_instance(),
        },
    )


def _fleet_rows() -> list[dict[str, Any]]:
    try:
        from .lite_control_plane_store import CONTROL_PLANE

        return CONTROL_PLANE.fleet_rows()[:256]
    except Exception:
        return []


def collect_agent_state() -> dict[str, Any]:
    items = []
    for row in _fleet_rows():
        device_id = _safe_text(row.get("device_id"), 120)
        if not device_id:
            continue
        connection = _safe_text(row.get("connection_state") or "unknown", 32).lower()
        agent = _safe_text(row.get("agent_status") or "unknown", 32).lower()
        process = _safe_text(row.get("pm2_status") or "unknown", 32).lower()
        command_deliverable = (
            connection in {"online", "active", "healthy"}
            and agent not in {"stopped", "offline", "failed"}
        )
        items.append(
            {
                "device_id": device_id,
                "connection_state": connection,
                "freshness_band": (
                    "offline"
                    if connection in {"offline", "stale"}
                    else "fresh"
                    if connection in {"online", "active", "healthy"}
                    else "unknown"
                ),
                "agent_status": agent,
                "process_status": process,
                "command_deliverable": command_deliverable,
                "source_revision": int(row.get("source_revision") or 0),
            }
        )
    status = (
        "healthy"
        if items and all(item["command_deliverable"] for item in items)
        else "degraded"
        if items
        else "unknown"
    )
    return {
        "status": status,
        "summary": "Device agents are ready." if status == "healthy" else "One or more device agents need attention.",
        "items": items,
        "item_count": len(items),
        "generation": semantic_revision("system.agent.generation", items),
        "sanitized": True,
    }


def agent_source_revision() -> int:
    return semantic_revision("system.agent", collect_agent_state())


def collect_supervisor_state() -> dict[str, Any]:
    items = []
    for row in _fleet_rows():
        device_id = _safe_text(row.get("device_id"), 120)
        if not device_id:
            continue
        supervisor = _safe_text(row.get("supervisor_status") or "unknown", 32).lower()
        agent_process = _safe_text(row.get("pm2_status") or "unknown", 32).lower()
        if supervisor in {"repairing", "recovering", "restarting"}:
            state = "recovering"
        elif supervisor in {"healthy", "online", "available"}:
            state = "healthy"
        elif supervisor in {"missing", "unavailable", "offline", "stopped"}:
            state = "unavailable"
        else:
            state = "unknown"
        if agent_process in {"stopped", "errored", "missing"} and state == "unavailable":
            state = "agent_stopped_without_supervisor"
        items.append(
            {
                "device_id": device_id,
                "state": state,
                "supervisor_status": supervisor,
                "watched_agent_status": agent_process,
                "source_revision": int(row.get("source_revision") or 0),
            }
        )
    status = (
        "healthy"
        if items and all(item["state"] == "healthy" for item in items)
        else "degraded"
        if items
        else "unknown"
    )
    return {
        "status": status,
        "summary": "Agent supervision is ready." if status == "healthy" else "Agent supervision needs attention.",
        "items": items,
        "item_count": len(items),
        "generation": semantic_revision("system.supervisor.generation", items),
        "sanitized": True,
    }


def supervisor_source_revision() -> int:
    return semantic_revision("system.supervisor", collect_supervisor_state())


def collect_remote_access_state() -> dict[str, Any]:
    from . import lite_status

    started = time.monotonic()
    remote = lite_status.lite_remote_access_status()
    nats = collect_nats_remote_state()
    ready = bool(remote.get("ready") and remote.get("nats_reachable"))
    status = "healthy" if ready else "degraded" if remote.get("running") else "unavailable"
    ip = remote.get("ip") if ready else None
    return {
        "status": status,
        "ready": ready,
        "running": bool(remote.get("running")),
        "authenticated": bool(remote.get("running") and (remote.get("ip") or remote.get("tailscale_ip"))),
        "tailnet_ip_present": bool(remote.get("ip") or remote.get("tailscale_ip")),
        "tailnet_ip": ip,
        "nats_reachable": bool(remote.get("nats_reachable")),
        "local_nats_ready": bool(nats.get("connected")),
        "summary": "Remote access ready" if ready else "Remote access not ready",
        "generation": semantic_revision(
            "system.remote_access.generation",
            {
                "status": status,
                "ready": ready,
                "running": bool(remote.get("running")),
                "tailnet_ip": ip,
                "nats_reachable": bool(remote.get("nats_reachable")),
            },
        ),
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }


def remote_access_source_revision() -> int:
    current = snapshot("system.remote_access") or {}
    return semantic_revision(
        "system.remote_access",
        {
            "status": current.get("status"),
            "generation": current.get("generation"),
            "running": current.get("running"),
            "ready": current.get("ready"),
            "tailnet_ip": current.get("tailnet_ip"),
            "nats_reachable": current.get("nats_reachable"),
            "nats_generation": nats_remote_source_revision(),
            "database_instance": _database_instance(),
        },
    )


def collect_fleet_probe_state() -> dict[str, Any]:
    try:
        from .lite_control_plane_store import CONTROL_PLANE

        prepared = CONTROL_PLANE.fleet_projection_snapshot()
    except Exception:
        prepared = None
    devices = (prepared or {}).get("devices") if isinstance((prepared or {}).get("devices"), list) else []
    online = sum(
        1
        for item in devices
        if str(item.get("connection") or item.get("status") or "").lower()
        in {"online", "active", "healthy"}
    )
    offline = sum(
        1
        for item in devices
        if str(item.get("connection") or item.get("status") or "").lower()
        in {"offline", "stale", "agent stopped"}
    )
    status = "healthy" if devices and offline == 0 else "degraded" if devices else "unknown"
    items = [
        {
            "id": _safe_text(item.get("id") or item.get("device_id"), 120),
            "connection": _safe_text(item.get("connection") or item.get("status"), 32).lower(),
            "agent_status": _safe_text(item.get("agent_status"), 32).lower(),
            "supervisor_status": _safe_text(item.get("supervisor_status"), 32).lower(),
        }
        for item in devices[:_MAX_ITEMS]
        if isinstance(item, dict)
    ]
    return {
        "status": status,
        "summary": {"online": online, "offline": offline, "total": len(devices)},
        "items": items,
        "item_count": len(devices),
        "source_revision": int((prepared or {}).get("source_revision") or 0),
        "generation": semantic_revision(
            "system.fleet_probe.generation",
            [
                {
                    "id": item.get("id"),
                    "connection": item.get("connection"),
                    "agent_status": item.get("agent_status"),
                    "supervisor_status": item.get("supervisor_status"),
                }
                for item in devices
            ],
        ),
        "projection_only": True,
        "sanitized": True,
    }


def fleet_probe_source_revision() -> int:
    try:
        from .fleet_registry import fleet_source_revision

        return max(1, int(fleet_source_revision()))
    except Exception:
        return semantic_revision("system.fleet_probe", snapshot("system.fleet_probe") or {})


def _maintenance_material() -> list[dict[str, Any]]:
    def read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT maintenance_id,kind,mode,status FROM security_maintenance_runs "
            "ORDER BY requested_at DESC,maintenance_id DESC LIMIT 4"
        ).fetchall()
        return [dict(row) for row in rows]

    try:
        return _read(read)
    except Exception:
        return []


def collect_system_health_state(engine: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    engine = engine if isinstance(engine, dict) else deps.core.build_health_engine_snapshot()
    processes = snapshot("system.processes") or collect_process_state()
    agent = snapshot("system.agent") or collect_agent_state()
    supervisor = snapshot("system.supervisor") or collect_supervisor_state()
    remote = snapshot("system.remote_access") or collect_remote_access_state()
    nats = snapshot("system.nats_remote") or collect_nats_remote_state()
    telemetry = snapshot("system.telemetry_thresholds") or {}
    storage = snapshot("system.storage_pressure") or {}
    sqlite_health = snapshot("system.sqlite_health") or {}
    maintenance = _maintenance_material()
    maintenance_active = any(
        str(item.get("status") or "").lower() in {"accepted", "running", "active"}
        for item in maintenance
    )
    components = {
        "api": str(engine.get("status") or "unknown").lower(),
        "processes": str(processes.get("status") or "unknown").lower(),
        "agent": str(agent.get("status") or "unknown").lower(),
        "supervisor": str(supervisor.get("status") or "unknown").lower(),
        "remote_access": str(remote.get("status") or "unknown").lower(),
        "nats": str(nats.get("status") or "unknown").lower(),
        "telemetry": str(telemetry.get("status") or "unknown").lower(),
        "storage": str(storage.get("status") or "unknown").lower(),
        "sqlite": str(sqlite_health.get("status") or "unknown").lower(),
    }
    engine_services = (
        engine.get("services") if isinstance(engine.get("services"), dict) else {}
    )
    services = {
        _safe_text(name, 80): {
            "name": _safe_text(item.get("name") or name, 80),
            "status": _safe_text(item.get("status") or "unknown", 32).lower(),
            "summary": _safe_text(item.get("summary"), 192),
        }
        for name, item in sorted(engine_services.items())[:32]
        if isinstance(item, dict)
    }
    unavailable_states = {"unavailable", "unhealthy", "critical", "read_only", "recovery_required"}
    degraded_states = {
        "degraded", "unknown", "unsupported", "watch", "elevated",
        "storage_pressure", "maintenance_active", "attention", "active",
    }
    if maintenance_active:
        overall = "maintenance"
    elif any(value in unavailable_states for value in components.values()):
        overall = "unavailable"
    elif any(value in degraded_states for value in components.values()):
        overall = "degraded"
    else:
        overall = "healthy"
    return {
        "status": overall,
        "summary": (
            "Pocket Lab is healthy."
            if overall == "healthy"
            else "Pocket Lab needs attention."
            if overall != "maintenance"
            else "Maintenance is active."
        ),
        "components": components,
        "services": services,
        "maintenance_active": maintenance_active,
        "database_instance": _database_instance(),
        "generation": semantic_revision(
            "system.health.generation",
            {
                "components": components,
                "maintenance_active": maintenance_active,
                "database_instance": _database_instance(),
            },
        ),
        "item_count": len(components),
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }


def _health_component_status(domain: str, fallback: dict[str, Any] | None = None) -> str:
    current = snapshot(domain) or fallback or {}
    return _safe_text(current.get("status") or "unknown", 32).lower()


def system_health_source_revision() -> int:
    maintenance_active = any(
        str(item.get("status") or "").lower() in {"accepted", "running", "active"}
        for item in _maintenance_material()
    )
    return semantic_revision(
        "system.health",
        {
            "database_instance": _database_instance(),
            "components": {
                "processes": _health_component_status("system.processes"),
                "agent": _health_component_status("system.agent"),
                "supervisor": _health_component_status("system.supervisor"),
                "remote_access": _health_component_status("system.remote_access"),
                "nats": _health_component_status("system.nats_remote", _bus_material()),
                "telemetry": _health_component_status("system.telemetry_thresholds"),
                "storage": _health_component_status("system.storage_pressure"),
                "sqlite": _health_component_status("system.sqlite_health"),
            },
            "maintenance_active": maintenance_active,
        },
    )


def collect_security_progress_state() -> dict[str, Any]:
    from . import lite_security

    try:
        prepared, age_ms = lite_security.prepared_security_progress()
        payload = prepared.body_for_age(age_ms)
    except Exception:
        payload = lite_security.security_progress_event()
    if not isinstance(payload, dict):
        payload = {}
    return {
        "status": _safe_text(payload.get("status") or "unknown", 32).lower(),
        "run_id": _safe_text(payload.get("run_id"), 120) or None,
        "profile": _safe_text(payload.get("profile") or "quick", 24).lower(),
        "app_id": _safe_text(payload.get("app_id"), 120) or None,
        "stage": _safe_text(payload.get("stage") or payload.get("step"), 96),
        "percent": max(0, min(100, int(payload.get("percent") or 0))),
        "active_scan": bool(payload.get("active_scan")),
        "event_id": max(0, int(payload.get("event_id") or 0)),
        "generation": semantic_revision(
            "security.progress.generation",
            {
                "run_id": payload.get("run_id"),
                "status": payload.get("status"),
                "profile": payload.get("profile"),
                "app_id": payload.get("app_id"),
                "stage": payload.get("stage") or payload.get("step"),
                "percent": payload.get("percent"),
                "event_id": payload.get("event_id"),
            },
        ),
        "sanitized": True,
    }


def security_progress_source_revision() -> int:
    from . import lite_security

    try:
        freshness = lite_security.freshness_state()
    except Exception:
        freshness = {}
    progress = freshness.get("progress") if isinstance(freshness.get("progress"), dict) else {}
    return semantic_revision(
        "security.progress",
        {
            "database_instance": _database_instance(),
            "security_revision": freshness.get("revision"),
            "progress_revision": freshness.get("progress_revision"),
            "run_id": progress.get("run_id"),
            "status": progress.get("status"),
            "stage": progress.get("stage") or progress.get("step"),
            "percent": progress.get("percent"),
            "profile": progress.get("profile"),
            "app_id": progress.get("app_id"),
            "maintenance": _maintenance_material(),
        },
    )


def collect_security_summary_state() -> dict[str, Any]:
    from . import lite_security

    payload = lite_security.summary_state()
    if not isinstance(payload, dict):
        payload = {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    latest = (
        payload.get("last_run")
        if isinstance(payload.get("last_run"), dict)
        else payload.get("latest_run")
        if isinstance(payload.get("latest_run"), dict)
        else {}
    )
    return {
        "status": _safe_text(payload.get("status") or latest.get("status") or "unknown", 32).lower(),
        "score": max(0, min(100, int(payload.get("score") or latest.get("score") or 0))),
        "active_scan": bool(payload.get("active_scan")),
        "latest_run_id": _safe_text(latest.get("run_id"), 120) or None,
        "profile": _safe_text(latest.get("profile") or payload.get("profile") or "quick", 24).lower(),
        "critical_count": max(0, int(summary.get("critical") or payload.get("critical_count") or 0)),
        "attention_count": max(0, int(summary.get("attention") or payload.get("attention_count") or 0)),
        "generation": semantic_revision(
            "security.summary.generation",
            {
                "status": payload.get("status"),
                "score": payload.get("score"),
                "active_scan": payload.get("active_scan"),
                "latest_run_id": latest.get("run_id"),
                "profile": latest.get("profile"),
                "critical_count": summary.get("critical"),
                "attention_count": summary.get("attention"),
                "revision": payload.get("revision"),
                "summary_revision": payload.get("summary_revision"),
            },
        ),
        "sanitized": True,
    }


def security_summary_source_revision() -> int:
    from . import lite_security

    try:
        freshness = lite_security.freshness_state()
    except Exception:
        freshness = {}
    return semantic_revision(
        "security.summary",
        {
            "database_instance": _database_instance(),
            "revision": freshness.get("revision"),
            "summary_revision": freshness.get("summary_revision"),
            "history_revision": freshness.get("history_revision"),
            "profile_revisions": freshness.get("profile_revisions") or {},
            "active_scan": freshness.get("active_scan"),
            "maintenance": _maintenance_material(),
        },
    )


_STATUS_SNAPSHOT_ENVELOPE_KEYS = frozenset(
    {
        "collector_duration_ms",
        "domain",
        "generation",
        "projection_age_ms",
        "projection_only",
        "projection_revision",
        "read_degraded",
        "refresh_pending",
        "retry_after_seconds",
        "scheduler_generation",
        "semantic_source_revision",
        "source_revision",
        "stored_projection_revision",
        "updated_at",
    }
)


def _status_snapshot_material(domain: str) -> dict[str, Any]:
    """Return only user-visible semantic state for the status revision fence.

    Child projection envelopes advance whenever collectors execute or reconcile.
    They must not make ``system.status`` look changed when the rendered status
    payload is identical.  The projector still consumes the complete prepared
    snapshots; this helper is only for the cheap source-revision callback.
    """

    prepared = snapshot(domain) or {}
    return {
        key: value
        for key, value in prepared.items()
        if key not in _STATUS_SNAPSHOT_ENVELOPE_KEYS
    }


def status_source_revision() -> int:
    return semantic_revision(
        "system.status",
        {
            "database_instance": _database_instance(),
            "health": _status_snapshot_material("system.health"),
            "processes": _status_snapshot_material("system.processes"),
            "agent": _status_snapshot_material("system.agent"),
            "supervisor": _status_snapshot_material("system.supervisor"),
            "remote_access": _status_snapshot_material("system.remote_access"),
            "nats": _status_snapshot_material("system.nats_remote") or _bus_material(),
            "fleet": _status_snapshot_material("system.fleet_probe"),
            "security": _status_snapshot_material("security.summary"),
            "telemetry": _status_snapshot_material("system.telemetry_thresholds"),
            "storage": _status_snapshot_material("system.storage_pressure"),
            "sqlite": _status_snapshot_material("system.sqlite_health"),
            "activity": _status_snapshot_material("system.activity_summary"),
        },
    )


def builder_for(domain: str) -> Callable[[], dict[str, Any]]:
    builders: dict[str, Callable[[], dict[str, Any]]] = {
        "security.progress": collect_security_progress_state,
        "security.summary": collect_security_summary_state,
        "system.health": collect_system_health_state,
        "system.processes": collect_process_state,
        "system.agent": collect_agent_state,
        "system.supervisor": collect_supervisor_state,
        "system.remote_access": collect_remote_access_state,
        "system.nats_remote": collect_nats_remote_state,
        "system.fleet_probe": collect_fleet_probe_state,
    }
    if domain == "system.status":
        from . import lite_status

        return lite_status.build_lite_status_projection
    try:
        return builders[domain]
    except KeyError as exc:
        raise ValueError("unsupported Phase 3B projection domain") from exc


def source_revision_for(domain: str) -> Callable[[], int]:
    callbacks: dict[str, Callable[[], int]] = {
        "security.progress": security_progress_source_revision,
        "security.summary": security_summary_source_revision,
        "system.status": status_source_revision,
        "system.health": system_health_source_revision,
        "system.processes": process_source_revision,
        "system.agent": agent_source_revision,
        "system.supervisor": supervisor_source_revision,
        "system.remote_access": remote_access_source_revision,
        "system.nats_remote": nats_remote_source_revision,
        "system.fleet_probe": fleet_probe_source_revision,
    }
    try:
        return callbacks[domain]
    except KeyError as exc:
        raise ValueError("unsupported Phase 3B projection domain") from exc


def mark_dirty(*domains: str, reason: str = "event") -> None:
    try:
        from .projection_scheduler import PROJECTION_SCHEDULER, ProjectionJob
    except Exception:
        return
    selected = domains or PHASE3B_DOMAINS
    for domain in selected:
        if domain not in PHASE3B_DOMAINS:
            continue
        work_class = "critical" if domain in {"security.progress", "system.nats_remote"} else "io"
        priority = (
            10
            if domain == "security.progress"
            else 20
            if domain in {"security.summary", "system.status", "system.health"}
            else 40
        )
        PROJECTION_SCHEDULER.mark_dirty(
            domain,
            job=ProjectionJob(
                domain=domain,
                builder=builder_for(domain),
                projector=lambda payload, selected_domain=domain: project(selected_domain, payload),
                priority=priority,
                work_class=work_class,
                deadline_seconds=8.0 if domain not in {"system.processes", "system.remote_access"} else 10.0,
                optional=work_class != "critical",
                source_revision=source_revision_for(domain),
                max_probe_seconds=(
                    30.0
                    if domain == "security.progress"
                    else 60.0
                    if domain
                    in {"system.nats_remote", "system.agent", "system.supervisor"}
                    else 300.0
                ),
                quiet_window_seconds=0.25 if domain == "security.progress" else 1.0,
            ),
            priority=priority,
        )


def schedule_startup_warmup() -> dict[str, bool]:
    result: dict[str, bool] = {}
    for domain in PHASE3B_DOMAINS:
        try:
            mark_dirty(domain, reason="startup")
            result[domain] = True
        except Exception:
            result[domain] = False
    return result


def diagnostics() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for domain in PHASE3B_DOMAINS:
        item = snapshot(domain)
        rows[domain] = {
            "prepared": bool(item),
            "status": (item or {}).get("status", "missing"),
            "source_revision": int((item or {}).get("source_revision") or 0),
            "projection_revision": int((item or {}).get("projection_revision") or 0),
            "item_count": int((item or {}).get("item_count") or 0),
            "collector_duration_ms": float((item or {}).get("collector_duration_ms") or 0.0),
        }
    return {
        "domains": rows,
        "database_instance": _database_instance(),
        "payload_budget_bytes": _MAX_PAYLOAD_BYTES,
        "sanitized": True,
    }
