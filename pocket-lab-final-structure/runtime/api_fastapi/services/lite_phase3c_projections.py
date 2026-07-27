from __future__ import annotations

"""Phase 3C bounded telemetry, storage, SQLite, and activity projections.

All request handlers read the shared prepared-current-state table. Collectors are
bounded and run only through the existing projection scheduler.
"""

from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Callable

from .. import deps
from ..db.connection import database_path
from ..db.runtime import SQLITE_READS, SQLITE_WRITER
from . import lite_phase3b_projections as prepared
from .lite_semantic_bands import POLICY_VERSION, ThresholdPolicy, policy_material, semantic_band

PHASE3C_DOMAINS = prepared.PHASE3C_DOMAINS
_MAX_DEVICES = 128
_MAX_RECENT = 24
_ACTIVE = frozenset({"queued", "published", "received", "accepted", "running", "working", "in_progress"})
_FAILED = frozenset({"failed", "undeliverable", "timed_out", "error", "blocked"})
_TERMINAL = frozenset({"succeeded", "failed", "cancelled", "undeliverable", "timed_out", "degraded"})
_SEVERITY = {"unsupported": -2, "unknown": -1, "normal": 0, "watch": 1, "elevated": 2, "critical": 3}
_COUNTER_LOCK = threading.Lock()
_COUNTERS: dict[str, Counter[str]] = {domain: Counter() for domain in PHASE3C_DOMAINS}


def _counter(domain: str, name: str, amount: int = 1) -> None:
    with _COUNTER_LOCK:
        _COUNTERS.setdefault(domain, Counter())[name] += max(0, int(amount))


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _safe_status(value: Any) -> str:
    text = str(value or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    return text[:32] if text else "unknown"


def _public_band(value: Any) -> str:
    band = _safe_status(value)
    if band == "low":
        return "elevated"
    if band in _SEVERITY:
        return band
    if band in {"healthy", "ready", "current", "online", "available"}:
        return "normal"
    if band in {"stale", "degraded", "warning"}:
        return "watch"
    if band in {"high", "unhealthy", "unavailable", "offline"}:
        return "elevated"
    return "unknown"


def _worst(values: list[str]) -> str:
    visible = [item for item in values if item in _SEVERITY]
    return max(visible, key=lambda item: _SEVERITY[item]) if visible else "unknown"


def _env_scaled(name: str, default: float, minimum: float, maximum: float, scale: int = 1000) -> int:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    value = max(minimum, min(maximum, value))
    return int(round(value * scale))


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _read(callback: Callable[[sqlite3.Connection], Any]) -> Any:
    """Read without performing migrations from a semantic probe or collector."""
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
    safe_domain = str(domain or "").strip().lower()[:96]
    if safe_domain == "system.activity_summary":
        current = snapshot("system.activity_current")
        history = snapshot("system.activity_history")
        if not current and not history:
            return None
        return compose_activity_summary(current or {}, history or {})
    if safe_domain not in PHASE3C_DOMAINS:
        return None

    def read(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT domain,status,generation,source_revision,projection_revision,payload_json,"
            "item_count,collector_duration_ms,updated_at,canonical_hash "
            "FROM phase3b_current_state WHERE domain=?",
            (safe_domain,),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update({
            "domain": safe_domain,
            "generation": int(row["generation"] or 0),
            "source_revision": int(row["source_revision"] or 0),
            "projection_revision": int(row["projection_revision"] or 0),
            "item_count": int(row["item_count"] or 0),
            "collector_duration_ms": round(float(row["collector_duration_ms"] or 0.0), 3),
            "updated_at": str(row["updated_at"] or ""),
            "canonical_hash": str(row["canonical_hash"] or "")[:64],
            "projection_only": True,
            "sanitized": True,
        })
        return payload

    try:
        return _read(read)
    except Exception:
        return prepared.snapshot(safe_domain)

def _telemetry_rows() -> list[dict[str, Any]]:
    def read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT device_id,health_status,health_severity,health_revision,source_revision,"
            "source_freshness_json,resources_json,connection_json "
            "FROM device_health_current ORDER BY device_id LIMIT ?",
            (_MAX_DEVICES,),
        ).fetchall()
        return [dict(row) for row in rows]

    try:
        return _read(read)
    except Exception:
        return []


def _telemetry_material() -> dict[str, Any]:
    devices: list[dict[str, Any]] = []
    for row in _telemetry_rows():
        resources = _json(row.get("resources_json"), {})
        freshness = _json(row.get("source_freshness_json"), {})
        connection = _json(row.get("connection_json"), {})
        telemetry_freshness = freshness.get("telemetry") if isinstance(freshness.get("telemetry"), dict) else {}
        device = {
            "device_id": str(row.get("device_id") or "")[:120],
            "health_revision": str(row.get("health_revision") or "")[:40],
            "source_revision": max(0, int(row.get("source_revision") or 0)),
            "health": _public_band(row.get("health_status")),
            "storage": _public_band((resources.get("storage") or {}).get("status") if isinstance(resources.get("storage"), dict) else None),
            "memory": _public_band((resources.get("memory") or {}).get("status") if isinstance(resources.get("memory"), dict) else None),
            "cpu": _public_band((resources.get("load") or {}).get("status") if isinstance(resources.get("load"), dict) else None),
            "thermal": _public_band((resources.get("temperature") or {}).get("status") if isinstance(resources.get("temperature"), dict) else None),
            "connectivity": _public_band(connection.get("status")),
            "freshness": _public_band(telemetry_freshness.get("state")),
        }
        devices.append(device)
    return {
        "policy_version": POLICY_VERSION,
        "database_instance": prepared._database_instance(),
        "devices": devices,
    }


def telemetry_source_revision() -> int:
    return prepared.semantic_revision("system.telemetry_thresholds", _telemetry_material())


def collect_telemetry_thresholds() -> dict[str, Any]:
    started = time.monotonic()
    material = _telemetry_material()
    devices: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for raw in material["devices"]:
        bands = [raw[key] for key in ("storage", "memory", "cpu", "thermal", "connectivity", "freshness")]
        status = _worst(bands)
        counts[status] += 1
        devices.append({
            "device_id": raw["device_id"],
            "status": status,
            "storage": raw["storage"],
            "memory": raw["memory"],
            "cpu": raw["cpu"],
            "thermal": raw["thermal"],
            "connectivity": raw["connectivity"],
            "freshness": raw["freshness"],
            "summary": (
                "Device health looks good."
                if status == "normal"
                else "Telemetry is not available."
                if status in {"unknown", "unsupported"}
                else "Device needs attention."
            ),
        })
    overall = _worst([item["status"] for item in devices]) if devices else "unknown"
    return {
        "status": overall,
        "summary": (
            "Device health looks good."
            if overall == "normal"
            else "Telemetry is not available."
            if overall in {"unknown", "unsupported"}
            else "One or more devices need attention."
        ),
        "devices": devices,
        "counts": {key: int(counts.get(key, 0)) for key in ("normal", "watch", "elevated", "critical", "unknown", "unsupported")},
        "capabilities": {"battery": "unsupported", "charging": "unsupported", "thermal": "available_if_reported"},
        "policy_version": POLICY_VERSION,
        "generation": prepared.semantic_revision("system.telemetry_thresholds.generation", material),
        "item_count": len(devices),
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }


def _storage_policies() -> dict[str, ThresholdPolicy]:
    from . import lite_storage_guard

    minimum = max(500, int(round(lite_storage_guard.minimum_free_percent() * 1000)))
    critical = _env_scaled("POCKETLAB_STORAGE_CRITICAL_PERCENT", max(1.0, minimum / 1000.0), 0.5, 25.0)
    elevated = _env_scaled("POCKETLAB_STORAGE_LOW_PERCENT", max(8.0, critical / 1000.0 + 2.0), 1.0, 40.0)
    watch = _env_scaled("POCKETLAB_STORAGE_WATCH_PERCENT", max(15.0, elevated / 1000.0 + 3.0), 2.0, 60.0)
    return {
        "free_percent": ThresholdPolicy(watch=watch, elevated=elevated, critical=critical, hysteresis=_env_scaled("POCKETLAB_STORAGE_HYSTERESIS_PERCENT", 2.0, 0.0, 10.0), low_is_bad=True),
        "wal_bytes": ThresholdPolicy(
            watch=_env_int("POCKETLAB_SQLITE_WAL_WATCH_BYTES", 16 * 1024 * 1024, 1, 4 * 1024 * 1024 * 1024),
            elevated=_env_int("POCKETLAB_SQLITE_WAL_LOW_BYTES", 64 * 1024 * 1024, 1, 8 * 1024 * 1024 * 1024),
            critical=_env_int("POCKETLAB_SQLITE_WAL_CRITICAL_BYTES", 256 * 1024 * 1024, 1, 16 * 1024 * 1024 * 1024),
            hysteresis=_env_int("POCKETLAB_SQLITE_WAL_HYSTERESIS_BYTES", 4 * 1024 * 1024, 0, 1024 * 1024 * 1024),
            low_is_bad=False,
        ),
    }


def _file_size(path: Path) -> int | None:
    try:
        return max(0, int(path.stat().st_size))
    except OSError:
        return None


def _storage_material() -> dict[str, Any]:
    from . import lite_storage_guard

    previous = snapshot("system.storage_pressure") or {}
    readiness = lite_storage_guard.storage_readiness(root=deps.settings().state_dir)
    percent_scaled = int(round(float(readiness.get("free_percent") or 0.0) * 1000)) if readiness.get("reason") != "storage_metrics_unavailable" else None
    policies = _storage_policies()
    free_band = semantic_band(percent_scaled, policies["free_percent"], previous=str(previous.get("free_space_band") or "unknown"), supported=percent_scaled is not None)
    db_path = database_path()
    wal_bytes = _file_size(Path(f"{db_path}-wal"))
    wal_band = semantic_band(wal_bytes, policies["wal_bytes"], previous=str(previous.get("wal_band") or "unknown"), supported=wal_bytes is not None)
    try:
        writable = bool(os.access(deps.settings().state_dir, os.W_OK))
        available = deps.settings().state_dir.exists()
    except OSError:
        writable = False
        available = False

    def read_targets(conn: sqlite3.Connection) -> dict[str, int]:
        rows = conn.execute(
            "SELECT connection_state,COUNT(*) AS count FROM device_current_state "
            "WHERE role IN ('storage','storage_node','backup_target') GROUP BY connection_state"
        ).fetchall()
        counts = {str(row["connection_state"] or "unknown"): int(row["count"] or 0) for row in rows}
        return {"configured": sum(counts.values()), "ready": sum(value for key, value in counts.items() if key in {"online", "active", "healthy"})}

    try:
        targets = _read(read_targets)
    except Exception:
        targets = {"configured": 0, "ready": 0}
    if not available:
        status = "unavailable"
    elif not writable:
        status = "read_only"
    else:
        status = _worst([free_band, wal_band])
    return {
        "policy_version": POLICY_VERSION,
        "database_instance": prepared._database_instance(),
        "status": status,
        "free_space_band": free_band,
        "wal_band": wal_band,
        "state_directory": "available" if available else "unavailable",
        "writeability": "writable" if writable else "read_only",
        "backup_target": "ready" if targets["ready"] else "not_ready" if targets["configured"] else "not_configured",
        "backup_target_count": min(128, targets["configured"]),
        "backup_target_ready_count": min(128, targets["ready"]),
        "policies": {name: policy_material(policy) for name, policy in policies.items()},
    }


def storage_source_revision() -> int:
    return prepared.semantic_revision("system.storage_pressure", _storage_material())


def collect_storage_pressure() -> dict[str, Any]:
    started = time.monotonic()
    material = _storage_material()
    status = str(material["status"])
    summary = {
        "normal": "Storage looks good.",
        "watch": "Storage is getting low.",
        "elevated": "Storage is low.",
        "critical": "Storage is critically low.",
        "read_only": "Storage is read-only.",
        "unavailable": "Storage is not available.",
        "unknown": "Storage status is not available.",
    }.get(status, "Storage status needs attention.")
    return {
        **material,
        "summary": summary,
        "generation": prepared.semantic_revision("system.storage_pressure.generation", material),
        "item_count": 3,
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }


def _sqlite_material(*, run_quick_check: bool) -> dict[str, Any]:
    storage = snapshot("system.storage_pressure") or _storage_material()
    try:
        from . import lite_security_maintenance

        marker = lite_security_maintenance.maintenance_state()
    except Exception:
        marker = {}
    marker_material = {
        "active": bool(marker.get("active")),
        "state": _safe_status(marker.get("state")),
        "kind": _safe_status(marker.get("kind")),
        "mode": _safe_status(marker.get("mode")),
        "writers_stopped": bool(marker.get("writers_stopped")),
    }

    def read(conn: sqlite3.Connection) -> dict[str, Any]:
        migration = conn.execute(
            "SELECT COALESCE(MAX(version),0) AS version,COUNT(*) AS count FROM schema_migrations"
        ).fetchone()
        maintenance = conn.execute(
            "SELECT maintenance_id,kind,mode,status FROM security_maintenance_runs "
            "ORDER BY requested_at DESC,maintenance_id DESC LIMIT 1"
        ).fetchone()
        backup = conn.execute(
            "SELECT backup_id,status,schema_version FROM security_database_backups "
            "ORDER BY created_at DESC,backup_id DESC LIMIT 1"
        ).fetchone()
        restore = conn.execute(
            "SELECT restore_id,state FROM security_database_restores "
            "ORDER BY requested_at DESC,restore_id DESC LIMIT 1"
        ).fetchone()
        journal_row = conn.execute("PRAGMA journal_mode").fetchone()
        quick = "not_run"
        if run_quick_check:
            row = conn.execute("PRAGMA quick_check(1)").fetchone()
            quick = str(row[0] if row else "unknown").lower()[:32]
        return {
            "schema_version": int(migration["version"] or 0),
            "migration_count": int(migration["count"] or 0),
            "journal_mode": str(journal_row[0] if journal_row else "unknown").lower()[:16],
            "maintenance": dict(maintenance) if maintenance else {},
            "backup": dict(backup) if backup else {},
            "restore": dict(restore) if restore else {},
            "quick_check": quick,
        }

    try:
        result = _read(read)
    except Exception as exc:
        return {
            "database_instance": prepared._database_instance(),
            "status": "unavailable",
            "error_type": type(exc).__name__,
            "storage_band": storage.get("status", "unknown"),
            "writer": {"running": False, "pressure": "unknown"},
        }
    writer = SQLITE_WRITER.snapshot()
    maintenance = result.get("maintenance") or {}
    maintenance_status = _safe_status(maintenance.get("status"))
    marker_status = "active" if marker_material.get("active") else _safe_status(marker_material.get("state"))
    quick = str(result.get("quick_check") or "not_run")
    storage_band = str(storage.get("status") or "unknown")
    if quick not in {"ok", "not_run"}:
        status = "recovery_required"
    elif maintenance_status in _ACTIVE or marker_status in _ACTIVE:
        status = "maintenance_active"
    elif storage_band in {"critical", "read_only", "unavailable"}:
        status = "storage_pressure"
    elif result.get("journal_mode") != "wal" or not writer.get("running", False):
        status = "degraded"
    else:
        status = "healthy"
    return {
        "database_instance": prepared._database_instance(),
        "status": status,
        "schema_version": int(result.get("schema_version") or 0),
        "migration_count": int(result.get("migration_count") or 0),
        "journal_mode": result.get("journal_mode"),
        "maintenance": {
            "id": str(maintenance.get("maintenance_id") or "")[:120] or None,
            "kind": _safe_status(maintenance.get("kind") or marker_material.get("kind")),
            "mode": _safe_status(maintenance.get("mode") or marker_material.get("mode")),
            "status": "active" if marker_material.get("active") else maintenance_status,
            "writers_stopped": bool(marker_material.get("writers_stopped")),
        },
        "latest_backup": {
            "status": _safe_status((result.get("backup") or {}).get("status")),
            "schema_version": max(0, int((result.get("backup") or {}).get("schema_version") or 0)),
        },
        "latest_restore": {"state": _safe_status((result.get("restore") or {}).get("state"))},
        "quick_check": quick,
        "storage_band": storage_band,
        "wal_band": storage.get("wal_band", "unknown"),
        "writer": {
            "running": bool(writer.get("running")),
            "queue_pressure": "elevated" if int(writer.get("queue_depth") or 0) >= max(1, int(writer.get("queue_capacity") or 1) * 3 // 4) else "normal",
            "rejected_writes": max(0, int(writer.get("rejected_writes") or 0)),
            "rollback_count": max(0, int(writer.get("rollback_count") or 0)),
        },
    }


def sqlite_health_source_revision() -> int:
    current = snapshot("system.sqlite_health") or {}
    material = _sqlite_material(run_quick_check=False)
    material["last_quick_check"] = current.get("quick_check", "not_run")
    return prepared.semantic_revision("system.sqlite_health", material)


def collect_sqlite_health() -> dict[str, Any]:
    started = time.monotonic()
    material = _sqlite_material(run_quick_check=True)
    status = str(material.get("status") or "unknown")
    summary = {
        "healthy": "Database health looks good.",
        "maintenance_active": "Maintenance is running.",
        "storage_pressure": "Database storage needs attention.",
        "degraded": "Database health needs attention.",
        "recovery_required": "Database recovery is required.",
        "unavailable": "Database health is not available.",
    }.get(status, "Database health is unknown.")
    return {
        **material,
        "summary": summary,
        "generation": prepared.semantic_revision("system.sqlite_health.generation", material),
        "item_count": 6,
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }


_ACTIVITY_CURRENT_SEMANTIC_KEYS = (
    "status",
    "summary",
    "active_operations",
    "attention_required",
    "workflows",
    "policy_mode",
    "item_count",
)

_ACTIVITY_HISTORY_SEMANTIC_KEYS = (
    "recent_completed",
    "latest_change",
    "workflows",
    "audit_reference_count",
    "item_count",
)


def _activity_current_semantic_material(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in _ACTIVITY_CURRENT_SEMANTIC_KEYS}


def _activity_history_semantic_material(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in _ACTIVITY_HISTORY_SEMANTIC_KEYS}


def _activity_semantic_material(payload: dict[str, Any]) -> dict[str, Any]:
    """Compatibility semantic material for the composed public response."""

    return {
        "current": _activity_current_semantic_material(payload),
        "history": _activity_history_semantic_material(payload),
    }


def _read_activity_rows() -> dict[str, Any]:
    def read(conn: sqlite3.Connection) -> dict[str, Any]:
        commands = [dict(row) for row in conn.execute(
            "SELECT command_id,entity_type,entity_id,operation_type,status,attention_status,updated_at_epoch_ms "
            "FROM command_lifecycle ORDER BY updated_at_epoch_ms DESC,command_id DESC LIMIT ?",
            (_MAX_RECENT,),
        ).fetchall()]
        app_actions = [dict(row) for row in conn.execute(
            "SELECT operation_id,app_id,action_id,status,updated_at_epoch_ms "
            "FROM app_action_lifecycle ORDER BY updated_at_epoch_ms DESC,operation_id DESC LIMIT ?",
            (_MAX_RECENT,),
        ).fetchall()]
        recovery = [dict(row) for row in conn.execute(
            "SELECT operation_id,operation_type,status,updated_at_epoch_ms "
            "FROM recovery_operations ORDER BY updated_at_epoch_ms DESC,operation_id DESC LIMIT ?",
            (_MAX_RECENT,),
        ).fetchall()]
        security = [dict(row) for row in conn.execute(
            "SELECT run_id,profile,status,COALESCE(completed_at_epoch_ms,updated_at_epoch_ms,requested_at_epoch_ms) AS updated_at_epoch_ms "
            "FROM security_scan_runs ORDER BY updated_at_epoch_ms DESC,run_id DESC LIMIT ?",
            (_MAX_RECENT,),
        ).fetchall()]
        activity_operation_ids = sorted({
            str(value)
            for value in (
                [row.get("command_id") for row in commands]
                + [row.get("operation_id") for row in app_actions]
                + [row.get("operation_id") for row in recovery]
                + [row.get("run_id") for row in security]
            )
            if value
        })
        if activity_operation_ids:
            placeholders = ",".join("?" for _ in activity_operation_ids)
            audit = [dict(row) for row in conn.execute(
                "SELECT operation_id,MAX(created_at_epoch_ms) AS created_at_epoch_ms "
                f"FROM audit_evidence_index WHERE operation_id IN ({placeholders}) "
                "GROUP BY operation_id "
                "ORDER BY MAX(created_at_epoch_ms) DESC,operation_id DESC LIMIT ?",
                (*activity_operation_ids, _MAX_RECENT),
            ).fetchall()]
        else:
            audit = []
        active_counts = {
            "devices": int(conn.execute(
                "SELECT COUNT(*) FROM command_lifecycle WHERE status IN ('queued','published','received','accepted','running')"
            ).fetchone()[0]),
            "apps": int(conn.execute(
                "SELECT COUNT(*) FROM app_action_lifecycle WHERE status IN ('queued','published','received','accepted','running','working','in_progress')"
            ).fetchone()[0]),
            "recovery": int(conn.execute(
                "SELECT COUNT(*) FROM recovery_operations WHERE status IN ('queued','published','received','accepted','running','working','in_progress')"
            ).fetchone()[0]),
            "security": int(conn.execute(
                "SELECT COUNT(*) FROM security_scan_runs WHERE status IN ('accepted','running')"
            ).fetchone()[0]),
        }
        attention_counts = {
            "devices": int(conn.execute(
                "SELECT COUNT(*) FROM command_lifecycle WHERE status IN ('failed','undeliverable','timed_out','error','blocked') AND attention_status='active'"
            ).fetchone()[0]),
            "apps": int(conn.execute(
                "SELECT COUNT(*) FROM app_action_lifecycle WHERE status IN ('failed','undeliverable','timed_out','error','blocked')"
            ).fetchone()[0]),
            "recovery": int(conn.execute(
                "SELECT COUNT(*) FROM recovery_operations WHERE status IN ('failed','undeliverable','timed_out','error','blocked')"
            ).fetchone()[0]),
            "security": int(conn.execute(
                "SELECT COUNT(*) FROM security_scan_runs WHERE status IN ('failed','timed_out','error')"
            ).fetchone()[0]),
        }
        return {
            "commands": commands,
            "apps": app_actions,
            "recovery": recovery,
            "security": security,
            "audit": audit,
            "active_counts": active_counts,
            "attention_counts": attention_counts,
        }

    try:
        return _read(read)
    except Exception:
        return {
            "commands": [],
            "apps": [],
            "recovery": [],
            "security": [],
            "audit": [],
            "active_counts": {},
            "attention_counts": {},
        }


def _activity_domain_rows(rows: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "devices": list(rows.get("commands") or []),
        "apps": list(rows.get("apps") or []),
        "recovery": list(rows.get("recovery") or []),
        "security": list(rows.get("security") or []),
    }


def collect_activity_current() -> dict[str, Any]:
    started = time.monotonic()
    rows = _read_activity_rows()
    active_count = 0
    attention_count = 0
    workflows: dict[str, dict[str, Any]] = {}
    for domain in ("devices", "apps", "recovery", "security"):
        active = max(0, int((rows.get("active_counts") or {}).get(domain) or 0))
        attention = max(0, int((rows.get("attention_counts") or {}).get(domain) or 0))
        active_count += active
        attention_count += attention
        workflows[domain] = {
            "status": "attention" if attention else "active" if active else "idle",
            "active": active,
            "attention": attention,
            "actionable": bool(active or attention),
        }
    status = "attention" if attention_count else "active" if active_count else "healthy"
    summary = (
        "Action needs attention."
        if attention_count
        else "Something is running."
        if active_count
        else "No actions need attention."
    )
    payload = {
        "status": status,
        "summary": summary,
        "active_operations": active_count,
        "attention_required": attention_count,
        "workflows": workflows,
        "policy_mode": "lite_personal",
        "item_count": len(workflows),
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }
    payload["generation"] = prepared.semantic_revision(
        "system.activity_current.generation",
        _activity_current_semantic_material(payload),
    )
    return payload


def collect_activity_history() -> dict[str, Any]:
    started = time.monotonic()
    rows = _read_activity_rows()
    domain_rows = _activity_domain_rows(rows)
    completed_count = 0
    workflows: dict[str, dict[str, Any]] = {}
    latest_candidates: list[dict[str, Any]] = []
    for domain, items in domain_rows.items():
        statuses = Counter(_safe_status(item.get("status")) for item in items)
        completed = sum(statuses.get(name, 0) for name in _TERMINAL)
        completed_count += completed
        latest = items[0] if items else {}
        workflows[domain] = {
            "recent_completed": completed,
            "latest_status": _safe_status(latest.get("status")),
            "latest_summary": prepared._safe_text(
                latest.get("operation_type")
                or latest.get("action_id")
                or latest.get("profile"),
                160,
            ),
        }
        if latest:
            latest_candidates.append({
                "domain": domain,
                "status": _safe_status(latest.get("status")),
                "summary": workflows[domain]["latest_summary"],
                "order": int(latest.get("updated_at_epoch_ms") or 0),
            })
    latest_change = (
        max(latest_candidates, key=lambda item: (item["order"], item["domain"]))
        if latest_candidates
        else None
    )
    payload = {
        "status": "available",
        "summary": "Recent activity is available." if latest_change else "No recent activity.",
        "recent_completed": completed_count,
        "latest_change": (
            {key: value for key, value in latest_change.items() if key != "order"}
            if latest_change
            else None
        ),
        "workflows": workflows,
        "audit_reference_count": min(_MAX_RECENT, len(rows.get("audit") or [])),
        "item_count": sum(len(items) for items in domain_rows.values()),
        "collector_duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "sanitized": True,
    }
    payload["generation"] = prepared.semantic_revision(
        "system.activity_history.generation",
        _activity_history_semantic_material(payload),
    )
    return payload


def compose_activity_summary(
    current: dict[str, Any], history: dict[str, Any]
) -> dict[str, Any]:
    current_workflows = (
        current.get("workflows") if isinstance(current.get("workflows"), dict) else {}
    )
    history_workflows = (
        history.get("workflows") if isinstance(history.get("workflows"), dict) else {}
    )
    workflows: dict[str, dict[str, Any]] = {}
    for domain in sorted(set(current_workflows) | set(history_workflows)):
        workflows[domain] = {
            **(current_workflows.get(domain) or {}),
            **(history_workflows.get(domain) or {}),
        }
    current_revision = int(current.get("projection_revision") or 0)
    history_revision = int(history.get("projection_revision") or 0)
    current_hash = str(current.get("canonical_hash") or "")[:64]
    history_hash = str(history.get("canonical_hash") or "")[:64]
    updated_candidates = [
        str(value)
        for value in (current.get("updated_at"), history.get("updated_at"))
        if value
    ]
    payload = {
        "status": current.get("status") or "unknown",
        "summary": current.get("summary") or "Activity state is not available.",
        "active_operations": int(current.get("active_operations") or 0),
        "attention_required": int(current.get("attention_required") or 0),
        "recent_completed": int(history.get("recent_completed") or 0),
        "latest_change": history.get("latest_change"),
        "workflows": workflows,
        "audit_reference_count": int(history.get("audit_reference_count") or 0),
        "policy_mode": current.get("policy_mode") or "lite_personal",
        "item_count": int(history.get("item_count") or 0),
        "current": current,
        "history": history,
        "current_projection_revision": current_revision,
        "history_projection_revision": history_revision,
        "current_canonical_hash": current_hash,
        "history_canonical_hash": history_hash,
        "projection_revision": max(current_revision, history_revision),
        "source_revision": prepared.semantic_revision(
            "system.activity_summary.composed",
            {
                "current_hash": current_hash,
                "history_hash": history_hash,
                "current_revision": current_revision,
                "history_revision": history_revision,
            },
        ),
        "updated_at": max(updated_candidates) if updated_candidates else "",
        "projection_only": True,
        "sanitized": True,
    }
    payload["generation"] = prepared.semantic_revision(
        "system.activity_summary.generation", _activity_semantic_material(payload)
    )
    return payload


def activity_current_source_revision() -> int:
    payload = collect_activity_current()
    return prepared.semantic_revision(
        "system.activity_current", _activity_current_semantic_material(payload)
    )


def activity_history_source_revision() -> int:
    payload = collect_activity_history()
    return prepared.semantic_revision(
        "system.activity_history", _activity_history_semantic_material(payload)
    )


def activity_source_revision() -> int:
    payload = collect_activity_summary()
    return prepared.semantic_revision(
        "system.activity_summary", _activity_semantic_material(payload)
    )


def collect_activity_summary() -> dict[str, Any]:
    return compose_activity_summary(
        collect_activity_current(), collect_activity_history()
    )

def builder_for(domain: str) -> Callable[[], dict[str, Any]]:
    builders = {
        "system.telemetry_thresholds": collect_telemetry_thresholds,
        "system.storage_pressure": collect_storage_pressure,
        "system.sqlite_health": collect_sqlite_health,
        "system.activity_current": collect_activity_current,
        "system.activity_history": collect_activity_history,
        "system.activity_summary": collect_activity_summary,
    }
    try:
        return builders[domain]
    except KeyError as exc:
        raise ValueError("unsupported Phase 3C projection domain") from exc


def source_revision_for(domain: str) -> Callable[[], int]:
    callbacks = {
        "system.telemetry_thresholds": telemetry_source_revision,
        "system.storage_pressure": storage_source_revision,
        "system.sqlite_health": sqlite_health_source_revision,
        "system.activity_current": activity_current_source_revision,
        "system.activity_history": activity_history_source_revision,
        "system.activity_summary": activity_source_revision,
    }
    try:
        return callbacks[domain]
    except KeyError as exc:
        raise ValueError("unsupported Phase 3C projection domain") from exc


def project(domain: str, payload: dict[str, Any]) -> prepared.ProjectionCommitResult:
    semantic_selector = None
    if domain == "system.activity_current":
        semantic_selector = _activity_current_semantic_material
    elif domain == "system.activity_history":
        semantic_selector = _activity_history_semantic_material
    result = prepared.commit_projection_if_changed(
        domain=domain,
        payload=payload,
        semantic_selector=semantic_selector,
    )
    if result.changed:
        _counter(domain, "semantic_change_count")
        if domain in {
            "system.telemetry_thresholds",
            "system.storage_pressure",
            "system.sqlite_health",
        }:
            prepared.mark_dirty(
                "system.health",
                "system.status",
                reason="phase3c_projection_committed",
            )
        elif domain == "system.activity_current":
            prepared.mark_dirty(
                "system.status", reason="activity_current_committed"
            )
    else:
        _counter(domain, "canonical_unchanged_count")
    return result


def _job(domain: str):
    from .lite_semantic_revisions import contract_for
    from .projection_scheduler import ProjectionJob

    parent, key = domain.split(".", 1)
    contract = contract_for(parent, key)
    if contract is None or not callable(contract.source_revision):
        raise RuntimeError(f"missing mandatory semantic revision contract for {domain}")
    return ProjectionJob(
        domain=domain,
        builder=builder_for(domain),
        projector=lambda payload, selected=domain: project(selected, payload),
        priority=contract.priority,
        work_class=contract.work_class,
        deadline_seconds=contract.deadline_seconds,
        optional=True,
        source_revision=contract.source_revision,
        max_probe_seconds=contract.max_probe_seconds,
        quiet_window_seconds=contract.quiet_window_seconds,
    )


def register_jobs() -> None:
    from .projection_scheduler import PROJECTION_SCHEDULER

    for domain in PHASE3C_DOMAINS:
        PROJECTION_SCHEDULER.register(_job(domain))


def _expanded_activity_domains(domains: tuple[str, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for domain in domains:
        if domain == "system.activity_summary":
            output.extend(("system.activity_current", "system.activity_history"))
        else:
            output.append(domain)
    return tuple(dict.fromkeys(output))


def mark_dirty(*domains: str, reason: str = "event") -> None:
    from .projection_scheduler import PROJECTION_SCHEDULER

    selected = _expanded_activity_domains(domains or PHASE3C_DOMAINS)
    register_jobs()
    for domain in selected:
        if domain not in PHASE3C_DOMAINS:
            continue
        _counter(domain, "dirty_event_count")
        if reason.startswith("reconcile") or reason == "startup":
            _counter(domain, "reconciliation_count")
        else:
            _counter(domain, "event_driven_update_count")
        PROJECTION_SCHEDULER.mark_dirty(
            domain,
            job=_job(domain),
            force_followup=False,
            reason=reason,
        )


def schedule_startup_warmup() -> dict[str, bool]:
    result: dict[str, bool] = {}
    register_jobs()
    for domain in PHASE3C_DOMAINS:
        try:
            mark_dirty(domain, reason="startup")
            result[domain] = True
        except Exception:
            result[domain] = False
    return result


def diagnostics() -> dict[str, Any]:
    from .projection_scheduler import PROJECTION_SCHEDULER

    rows: dict[str, Any] = {}
    for domain in PHASE3C_DOMAINS:
        item = snapshot(domain) or {}
        scheduler = PROJECTION_SCHEDULER.status(domain)
        with _COUNTER_LOCK:
            counters = dict(_COUNTERS.get(domain, Counter()))
        semantic_changes = int(counters.get("semantic_change_count") or 0)
        rows[domain] = {
            **scheduler,
            "prepared": bool(item),
            "status": item.get("status", "missing"),
            "stored_source_revision": int(item.get("source_revision") or 0),
            "projection_revision": int(item.get("projection_revision") or 0),
            "canonical_hash": str(item.get("canonical_hash") or "")[:64],
            "payload_bytes": len(
                json.dumps(
                    item, sort_keys=True, separators=(",", ":"), default=str
                ).encode("utf-8")
            ) if item else 0,
            "item_count": int(item.get("item_count") or 0),
            "collector_duration_ms": float(item.get("collector_duration_ms") or 0.0),
            "sample_count": int(item.get("item_count") or 0)
            if domain == "system.telemetry_thresholds"
            else 0,
            "threshold_transition_count": semantic_changes
            if domain in {"system.telemetry_thresholds", "system.storage_pressure"}
            else 0,
            "aggregate_row_count": int(item.get("item_count") or 0)
            if domain in {"system.activity_current", "system.activity_history"}
            else 0,
            "query_plan_status": "indexed_contract_tested",
            **counters,
        }
    semantic_events = prepared.semantic_change_events(
        ["system.activity_current", "system.activity_history"], limit=64
    )
    return {
        "domains": rows,
        "activity_summary": snapshot("system.activity_summary") or {},
        "semantic_change_timeline": semantic_events,
        "database_instance": prepared._database_instance(),
        "payload_budget_bytes": prepared._MAX_PAYLOAD_BYTES,
        "policy_version": POLICY_VERSION,
        "sanitized": True,
    }
