"""Deterministic, low-power System Health incident intelligence.

Runtime observations enter only from worker-owned committed projections. HTTP reads
never collect live process state or run migrations. Recovery execution remains
with existing supervisors/agents/workers, not this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from contextlib import closing
from ..db.connection import begin_immediate, connection, open_fast_read_connection

ACTIVE = frozenset({"detected", "diagnosing", "diagnosed", "repair_available", "repairing", "verifying", "blocked", "failed", "manual_attention_required"})
UNHEALTHY = frozenset({"errored", "read_only", "recovery_required", "watch", "elevated", "storage_pressure", "degraded", "unavailable", "unhealthy", "critical", "offline", "stopped", "missing", "errored", "failed", "attention", "pressure", "agent_stopped_without_supervisor"})
HEALTHY = frozenset({"normal", "healthy", "online", "ready", "running", "connected"})
UNKNOWN = frozenset({"unknown", "stale", "unverified", "pending", "unsupported", "not_ready"})
OBSERVATION_MAX_AGE_SECONDS = 300
MAX_HISTORY = 2000
# Contract edges describe dependencies, not proof of a live connection.
DEPENDENCY_EDGES = (
    {"upstream": "nats", "downstream": "worker", "authority": "verified_contract", "summary": "Commands use NATS/JetStream."},
    {"upstream": "nats", "downstream": "agent", "authority": "verified_contract", "summary": "Device agents use the command/event bus."},
    {"upstream": "caddy", "downstream": "app", "authority": "verified_contract", "summary": "Registered apps use backend-managed same-origin Caddy routes."},
    {"upstream": "worker", "downstream": "security", "authority": "verified_contract", "summary": "Safety scans use worker execution."},
    {"upstream": "processes", "downstream": "api", "authority": "inferred", "summary": "Process availability can affect API readiness."},
    {"upstream": "remote_access", "downstream": "agent", "authority": "inferred", "summary": "Connectivity can affect remote device reachability."},
)
# Explicitly descriptive: these are owned by existing runtime guardians.
REPAIR_CATALOG = (
    {"operation_id": "runtime.consumer.reconnect", "risk_class": "A", "execution_owner": "nats_worker_watchdog", "availability": "externally_managed", "summary": "Worker watchdog owns durable-consumer recovery."},
    {"operation_id": "device.agent.recover", "risk_class": "A", "execution_owner": "node_supervisor", "availability": "externally_managed", "summary": "Device supervisor owns eligible stopped-agent recovery."},
    {"operation_id": "app.repair", "risk_class": "B", "execution_owner": "existing_app_action", "availability": "guided_existing_flow", "summary": "Review app repair inside the existing Apps Manage flow."},
    {"operation_id": "runtime.configuration.restore", "risk_class": "B", "execution_owner": "runtime_reconciler", "availability": "not_enabled", "summary": "No automatic configuration overwrite is enabled."},
    {"operation_id": "recovery.database.restore", "risk_class": "C", "execution_owner": "recovery", "availability": "never_automatic", "summary": "Database restore requires the existing preview and confirmation workflow."},
)
SOURCE_NAMES = {
    "system.health": "system", "system.nats_remote": "nats",
    "system.processes": "processes", "system.agent": "agent",
    "system.supervisor": "supervisor", "system.remote_access": "remote_access",
    "system.telemetry_thresholds": "telemetry", "system.storage_pressure": "storage",
    "system.sqlite_health": "sqlite", "security.progress": "security",
}
CONTROLLED_RECOVERY_OPERATION = "runtime.consumer.reconnect"


def controlled_recovery_enabled() -> bool:
    """Return true only for an explicitly isolated qualification candidate.

    The adapter is implemented in the worker owner, but activation requires
    both a qualification environment and a separate opt-in. Production and
    the installed Server Phone therefore remain autonomous-watchdog only.
    """
    return (
        os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"
        and os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER") == "1"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe(value: Any, limit: int = 180) -> str:
    # Never store raw payloads, URLs, paths, credentials or free-form error traces.
    value = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    if any(character in value for character in ("=", "/", "\\", "@", "<", ">")):
        return ""
    return "".join(c for c in value if 32 <= ord(c) <= 126)[:limit]


# Projections contain lists of typed records, never iterable device names.
# Reject unsafe identities but allow legitimately short identifiers.
_TARGET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}")


def _target_id(value: Any, limit: int = 100) -> str:
    if not isinstance(value, str) or len(value) > limit:
        return ""
    return value if _TARGET_ID.fullmatch(value) else ""


def _records(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    entries = payload.get(field)
    if not isinstance(entries, list):
        return []
    return [item for item in entries[:64] if isinstance(item, dict)]


def _status(value: Any) -> str:
    normalized = _safe(value, 32).lower()
    return normalized if normalized in UNHEALTHY | HEALTHY | UNKNOWN | {"watch", "elevated", "recovering", "maintenance", "active", "read_only"} else "unknown"


def _identity(source: str, target: str) -> str:
    return _identity_for_generation(source, target, 0)


def _identity_for_generation(source: str, target: str, enrollment_generation: int = 0) -> str:
    # Generation 1 retains the historical incident identifier. A future
    # explicitly authorized generation gets a distinct identity, so late
    # observations cannot mutate the previous enrollment's incident.
    generation = int(enrollment_generation or 0)
    suffix = f":enrollment:{generation}" if source in DEVICE_SOURCES and generation > 1 else ""
    material = f"{source}:{target}:health{suffix}".encode("utf-8")
    return "health-" + hashlib.sha256(material).hexdigest()[:24]


def _event(conn: sqlite3.Connection, incident_id: str, generation: int, kind: str, summary: str) -> None:
    conn.execute(
        "INSERT INTO lite_system_health_events (incident_id,generation,event_type,created_at,safe_summary) VALUES (?,?,?,?,?)",
        (incident_id, generation, kind, _now(), _safe(summary, 180)),
    )


def _prune(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM lite_system_health_events WHERE id NOT IN (SELECT id FROM lite_system_health_events ORDER BY id DESC LIMIT 4000)")
    conn.execute("DELETE FROM lite_system_health_repair_attempts WHERE repair_id NOT IN (SELECT repair_id FROM lite_system_health_repair_attempts ORDER BY requested_at DESC LIMIT 2000)")
    conn.execute("DELETE FROM lite_system_health_recovery_requests WHERE request_id NOT IN (SELECT request_id FROM lite_system_health_recovery_requests ORDER BY requested_at DESC LIMIT 2000)")
    conn.execute(
        "DELETE FROM lite_system_health_incidents WHERE state='resolved' AND incident_id NOT IN "
        "(SELECT incident_id FROM lite_system_health_incidents ORDER BY last_seen_at DESC LIMIT ?) "
        "AND incident_id NOT IN (SELECT incident_id FROM lite_system_health_repair_attempts)",
        (MAX_HISTORY,),
    )


# Only these sources are device-scoped; shared system.agent observations use
# source="system" and must never be filtered as a fleet member.
DEVICE_SOURCES = ("agent", "supervisor", "telemetry")
MEMBERSHIP_JOIN = " LEFT JOIN device_enrollment_registry m ON m.device_id=i.target_id AND i.source IN ('agent','supervisor','telemetry') "
OBSERVATION_JOIN = " LEFT JOIN lite_system_health_observations o ON o.source=i.source AND o.target_id=i.target_id AND (i.source NOT IN ('agent','supervisor','telemetry') OR COALESCE(o.enrollment_generation,0)=COALESCE(i.enrollment_generation,0)) "
MEMBERSHIP_STATE = """CASE WHEN i.source NOT IN ('agent','supervisor','telemetry') THEN 'shared'
    WHEN m.device_id IS NULL THEN 'unknown'
    WHEN COALESCE(i.enrollment_generation, 0) != COALESCE(m.enrollment_generation, 1) THEN 'historical_generation'
    WHEN m.protected_server_host=1 AND m.removal_status!='active' THEN 'protected_conflict'
    WHEN m.removal_status='active' THEN 'active'
    WHEN m.removal_status IN ('retired','removed') THEN m.removal_status
    ELSE 'unknown' END"""
MONITORED = "(" + MEMBERSHIP_STATE + ") IN ('shared','active','protected_conflict')"


def _device_memberships(conn: sqlite3.Connection, observations: list) -> dict[str, tuple[str, int]]:
    ids = sorted({target for source, target, _, _ in observations if source in DEVICE_SOURCES})
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        "SELECT device_id,removal_status,enrollment_status,protected_server_host,enrollment_generation "
        "FROM device_enrollment_registry WHERE device_id IN (" + placeholders + ")", ids,
    )
    return {
        row["device_id"]: (
            "active" if row["removal_status"] == "active" else "unknown",
            max(1, int(row["enrollment_generation"] or 1)),
        )
        for row in rows
    }


def _observation_rows(where: str = "", limit: int = 128) -> list[dict[str, Any]]:
    return _read(
        "SELECT i.source,i.target_id,CASE WHEN (" + MEMBERSHIP_STATE + ")='protected_conflict' "
        "THEN 'unknown' ELSE i.status END AS status,i.observed_at "
        "FROM lite_system_health_observations i" + MEMBERSHIP_JOIN +
        " WHERE " + MONITORED + (" AND " + where if where else "") +
        " ORDER BY i.source,i.target_id LIMIT ?", (limit,),
    )


def _observations(domain: str, payload: dict[str, Any]):
    source = SOURCE_NAMES.get(domain)
    if not source or not isinstance(payload, dict):
        return
    if domain == "system.health":
        components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
        for target in ("agent", "api", "nats", "processes", "remote_access",
                       "sqlite", "storage", "supervisor", "telemetry"):
            if target not in components:
                continue
            value = components[target]
            if target in {"api", "nats", "processes", "agent", "supervisor", "remote_access", "storage", "sqlite", "telemetry"}:
                yield ("system", target, _status(value), "Component health requires review.")
        return
    if domain in {"system.agent", "system.supervisor"}:
        for item in _records(payload, "items"):
            target = _target_id(item.get("device_id"))
            if not target:
                continue
            raw = item.get("connection_state") if domain == "system.agent" else item.get("state")
            if domain == "system.agent" and item.get("command_deliverable") is False:
                raw = "offline" if raw not in UNKNOWN else "unknown"
            yield (source, target, _status(raw), "Device connection or agent needs review.")
        return
    if domain == "system.processes":
        from . import lite_app_registry
        registered = {
            lite_app_registry.app_definition(app_id).process: app_id
            for app_id in lite_app_registry.app_ids()
        }
        for item in _records(payload, "items"):
            target = _target_id(item.get("name"))
            status = _status(item.get("status"))
            if target and item.get("expected"):
                yield (source, target, status, "Required process needs attention.")
            # Optional app process missing can simply mean not installed.
            # Only observe running/previously detected app processes.
            if target in registered and status not in {"missing", "unknown"}:
                yield ("app", registered[target], status, "Registered app process needs review.")
        return
    if domain == "system.telemetry_thresholds":
        for item in _records(payload, "devices"):
            device_id = _target_id(item.get("device_id"))
            if device_id:
                yield (source, device_id, _status(item.get("status")), "Device resource or connectivity signal needs review.")
        return
    if domain == "system.nats_remote":
        yield (source, "jetstream", _status(payload.get("status")), "Command delivery needs attention.")
        for name, item in sorted((payload.get("durable_consumer_health") if isinstance(payload.get("durable_consumer_health"), dict) else {}).items(), key=lambda pair: str(pair[0])):
            consumer_id = _target_id(name, 60)
            if consumer_id and isinstance(item, dict) and isinstance(item.get("healthy"), bool):
                yield (source, "consumer:" + consumer_id, "healthy" if item["healthy"] else "degraded", "Command consumer readiness needs attention.")
        return
    yield (source, source, _status(payload.get("status")), "System health signal needs review.")


def ingest_projection(domain: str, payload: dict[str, Any]) -> int:
    """Call only after a worker-owned projection commit; never from a GET."""
    if not isinstance(payload, dict):
        return 0
    observations = list(_observations(domain, payload) or [])
    if not observations:
        return 0
    revision = _safe(payload.get("generation") or payload.get("revision"), 64)
    now = _now()
    changed = 0
    with connection() as conn:
        with begin_immediate(conn):
            memberships = _device_memberships(conn, observations[:64])
            for source, target, status, summary in observations[:64]:
                # Retirement is terminal in the enrollment store. Never mutate a
                # historical incident based on a late heartbeat or stale projection.
                membership_status, enrollment_generation = memberships.get(target, ("unknown", 0))
                if not target or (source in DEVICE_SOURCES and membership_status != "active"):
                    continue
                current = conn.execute(
                    "SELECT status,source_revision,enrollment_generation FROM lite_system_health_observations WHERE source=? AND target_id=?",
                    (source, target),
                ).fetchone()
                if current and current["status"] == status and current["source_revision"] == revision and int(current["enrollment_generation"] or 0) == enrollment_generation:
                    continue
                conn.execute(
                    "INSERT INTO lite_system_health_observations (source,target_id,status,observed_at,source_revision,summary,enrollment_generation) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(source,target_id) DO UPDATE SET status=excluded.status,observed_at=excluded.observed_at,"
                    "source_revision=excluded.source_revision,summary=excluded.summary,enrollment_generation=excluded.enrollment_generation",
                    (source, target, status, now, revision, summary, enrollment_generation),
                )
                incident_id = _identity_for_generation(source, target, enrollment_generation)
                prior = conn.execute("SELECT * FROM lite_system_health_incidents WHERE incident_id=?", (incident_id,)).fetchone()
                if status in UNHEALTHY:
                    severity = "critical" if status in {"critical", "unavailable", "unhealthy"} else "warning"
                    if prior:
                        reopened = prior["state"] == "resolved"
                        generation = prior["generation"] + (1 if reopened else 0)
                        conn.execute(
                            "UPDATE lite_system_health_incidents SET state=?,severity=?,generation=?,recurrence_count=recurrence_count+?,"
                            "observation_count=observation_count+1,last_seen_at=?,resolved_at=NULL,evidence_revision=?,summary=?,suspected_cause='',verified_cause='' WHERE incident_id=?",
                            ("detected" if reopened else prior["state"], severity, generation, int(reopened), now, revision, summary, incident_id),
                        )
                        if reopened:
                            _event(conn, incident_id, generation, "reopened", summary)
                    else:
                        conn.execute(
                            "INSERT INTO lite_system_health_incidents "
                            "(incident_id,source,target_id,kind,state,severity,first_seen_at,last_seen_at,evidence_revision,summary,enrollment_generation) "
                            "VALUES (?,?,?,'health','detected',?,?,?,?,?,?)",
                            (incident_id, source, target, severity, now, now, revision, summary, enrollment_generation),
                        )
                        _event(conn, incident_id, 1, "detected", summary)
                    changed += 1
                elif status in HEALTHY and prior and prior["state"] in ACTIVE:
                    conn.execute(
                        "UPDATE lite_system_health_incidents SET state='resolved',last_seen_at=?,resolved_at=?,"
                        "evidence_revision=?,observation_count=observation_count+1 WHERE incident_id=?",
                        (now, now, revision, incident_id),
                    )
                    _event(conn, incident_id, prior["generation"], "observed_healthy", "Fresh projection reports healthy; no repair is implied.")
                    changed += 1
                # An unknown/stale observation never resolves an incident.
            if changed:
                _prune(conn)
    return changed


def _read(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        with closing(open_fast_read_connection()) as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except (FileNotFoundError, sqlite3.OperationalError):
        return []


def incidents(*, include_resolved: bool = False, limit: int = 40, offset: int = 0) -> dict[str, Any]:
    limit, offset = max(1, min(int(limit), 100)), max(0, min(int(offset), 10000))
    where = "" if include_resolved else "WHERE i.state != 'resolved' AND " + MONITORED
    items = _read(
        "SELECT i.*, o.status AS latest_observation_status, o.observed_at AS latest_observed_at, "
        + MEMBERSHIP_STATE + " AS membership_state, m.retired_at AS membership_retired_at, m.registry_revision AS membership_revision, m.enrollment_generation AS membership_enrollment_generation, m.device_name AS membership_device_name "
        "FROM lite_system_health_incidents i" + OBSERVATION_JOIN + MEMBERSHIP_JOIN
        + where + " ORDER BY i.last_seen_at DESC, i.incident_id LIMIT ? OFFSET ?",
        (limit + 1, offset),
    )
    return {"items": [public_incident(item) for item in items[:limit]], "limit": limit, "offset": offset, "next_offset": offset + limit if len(items) > limit else None}


def public_incident(item: dict[str, Any]) -> dict[str, Any]:
    if not item:
        return {}
    result = dict(item)
    result["evidence_freshness"] = freshness(item.get("last_seen_at"))
    result["cause_confidence"] = "unconfirmed" if not item.get("verified_cause") else "verified"
    observation_freshness = freshness(item.get("latest_observed_at"))
    result["observation_freshness"] = observation_freshness
    # An unresolved incident is current only with a fresh unhealthy observation.
    # An unconfirmed or healthy signal cannot silently close a historical event.
    result["concern_state"] = (
        "resolved_observation" if item.get("state") == "resolved"
        else "current_concern" if observation_freshness == "current"
        and item.get("latest_observation_status") in UNHEALTHY
        else "saved_concern"
    )
    membership = item.get("membership_state", "unknown")
    result["current_monitoring"] = membership in {"active", "shared", "protected_conflict"}
    result["device_label"] = _safe(result.pop("membership_device_name", ""), 80) or None
    result["enrollment_generation"] = max(0, int(item.get("enrollment_generation") or 0))
    result["membership_enrollment_generation"] = max(0, int(item.get("membership_enrollment_generation") or 0))
    if membership in {"retired", "removed", "unknown", "historical_generation"}:
        result["concern_state"] = "historical_record"
    elif membership == "protected_conflict":
        result["concern_state"] = "saved_concern"
        result["observation_freshness"] = "unknown"
    target_id = str(result.get("target_id") or "")
    result["repair_available"] = bool(
        controlled_recovery_enabled()
        and result.get("current_monitoring")
        and result.get("source") == "nats"
        and (target_id == "jetstream" or target_id.startswith("consumer:"))
    )
    result["repair_guidance"] = (
        "Review and request the governed worker-owned recovery action."
        if result["repair_available"]
        else "Review the existing protected recovery action for this component."
    )
    return result


def freshness(timestamp: str | None) -> str:
    if not timestamp:
        return "unknown"
    try:
        observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        return "current" if 0 <= age <= OBSERVATION_MAX_AGE_SECONDS else "stale"
    except (TypeError, ValueError):
        return "unknown"


def incident(incident_id: str) -> dict[str, Any] | None:
    rows = _read(
        "SELECT i.*, o.status AS latest_observation_status, o.observed_at AS latest_observed_at, "
        + MEMBERSHIP_STATE + " AS membership_state, m.retired_at AS membership_retired_at, m.registry_revision AS membership_revision, m.enrollment_generation AS membership_enrollment_generation, m.device_name AS membership_device_name "
        "FROM lite_system_health_incidents i" + OBSERVATION_JOIN + MEMBERSHIP_JOIN + " WHERE i.incident_id=? LIMIT 1",
        (incident_id,),
    )
    return public_incident(rows[0]) if rows else None


def summary() -> dict[str, Any]:
    # Aggregate before limiting any history page. The registry PK supports the
    # membership join; no per-incident database reads or live probes are needed.
    unhealthy_values = ",".join("'" + value + "'" for value in sorted(UNHEALTHY))
    healthy_values = ",".join("'" + value + "'" for value in sorted(HEALTHY))
    recent_signal = "(julianday(i.observed_at) BETWEEN julianday('now')-300.0/86400 AND julianday('now'))"
    signal_stats = _read(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN " + recent_signal + " AND i.status IN (" + healthy_values + ") AND (" + MEMBERSHIP_STATE + ")!='protected_conflict' THEN 1 ELSE 0 END) AS healthy, "
        "SUM(CASE WHEN " + recent_signal + " AND i.status IN (" + unhealthy_values + ") AND (" + MEMBERSHIP_STATE + ")!='protected_conflict' THEN 1 ELSE 0 END) AS unhealthy, "
        "SUM(CASE WHEN " + recent_signal + " AND (" + MEMBERSHIP_STATE + ")!='protected_conflict' THEN 1 ELSE 0 END) AS fresh "
        "FROM lite_system_health_observations i" + MEMBERSHIP_JOIN + " WHERE " + MONITORED
    )
    stats = signal_stats[0] if signal_stats else {}
    total = stats.get("total") or 0
    healthy = stats.get("healthy") or 0
    unhealthy = stats.get("unhealthy") or 0
    fresh = stats.get("fresh") or 0
    unknown_count = total - healthy - unhealthy
    is_current = "(julianday(o.observed_at) BETWEEN julianday('now')-300.0/86400 AND julianday('now') AND o.status IN (" + unhealthy_values + ") AND (" + MEMBERSHIP_STATE + ")!='protected_conflict')"
    incident_stats = _read(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN i.severity='critical' THEN 1 ELSE 0 END) AS critical, "
        "SUM(CASE WHEN " + is_current + " THEN 1 ELSE 0 END) AS current, "
        "SUM(CASE WHEN " + is_current + " AND i.severity='critical' THEN 1 ELSE 0 END) AS current_critical "
        "FROM lite_system_health_incidents i" + OBSERVATION_JOIN + MEMBERSHIP_JOIN +
        " WHERE i.state!='resolved' AND " + MONITORED
    )
    counts = incident_stats[0] if incident_stats else {}
    active = counts.get("total") or 0
    current = counts.get("current") or 0
    saved_count = active - current
    historical = _read("SELECT COUNT(*) AS total FROM lite_system_health_incidents i" + MEMBERSHIP_JOIN + " WHERE NOT " + MONITORED)
    historical_count = historical[0]["total"] if historical else 0
    recent = _read("SELECT i.incident_id,i.state,i.summary,i.resolved_at FROM lite_system_health_incidents i" + MEMBERSHIP_JOIN + " WHERE i.state='resolved' AND " + MONITORED + " ORDER BY i.resolved_at DESC LIMIT 5")
    status = ("unknown" if not total or not fresh else
              "attention" if unhealthy or current else
              "unknown" if unknown_count or saved_count else "healthy")
    return {
        "status": status, "checked_at": _now(), "data_source": "persisted_projection",
        "observed_services": total, "healthy_services": healthy,
        "historical_device_records": historical_count,
        # Legacy fields preserve unresolved-incident semantics for old clients.
        "active_problems": active, "critical_problems": counts.get("critical") or 0,
        "current_problems": current, "saved_problems": saved_count,
        "current_critical_problems": counts.get("current_critical") or 0,
        "unresolved_critical_problems": counts.get("critical") or 0,
        "unknown_services": unknown_count, "automatic_repairs_running": 0,
        "recent_verified_recoveries": 0,  # Healthy observation is not verified repair recovery.
        "recent_resolutions": recent,
        "freshness": "current" if fresh else "stale" if total else "unavailable",
        "summary": "No authoritative health observations yet." if not total else
                   "One or more services need attention." if status == "attention" else
                   "Health evidence is incomplete or stale." if status == "unknown" else
                   "Observed services are healthy.",
    }


def history(limit: int = 30, offset: int = 0) -> dict[str, Any]:
    result = incidents(include_resolved=True, limit=limit, offset=offset)
    result["repairs"] = _read(
        "SELECT repair_id,incident_id,operation_id,risk_class,execution_state,verification_state,"
        "requested_at,completed_at,safe_summary,outcome FROM lite_system_health_repair_attempts "
        "ORDER BY requested_at DESC,repair_id DESC LIMIT ? OFFSET ?",
        (max(1, min(limit, 100)), max(0, min(offset, 10000))),
    )
    result["recovery_requests"] = _read(
        "SELECT request_id,incident_id,incident_generation,enrollment_generation,operation_id,status,"
        "execution_state,verification_state,requested_at,updated_at,completed_at,safe_summary,outcome,terminal_reason "
        "FROM lite_system_health_recovery_requests ORDER BY requested_at DESC,request_id DESC LIMIT ? OFFSET ?",
        (max(1, min(limit, 100)), max(0, min(offset, 10000))),
    )
    return result


def dependency_graph() -> dict[str, Any]:
    observations = _observation_rows()
    nodes = []
    for row in observations:
        nodes.append({**row, "freshness": freshness(row["observed_at"]), "authority": "verified_runtime" if freshness(row["observed_at"]) == "current" else "unknown"})
    return {"nodes": nodes, "edges": list(DEPENDENCY_EDGES), "description": "Contract edges are not live connectivity proof."}


def resource_intelligence() -> dict[str, Any]:
    rows = _observation_rows("i.source IN ('storage','telemetry','sqlite')", 32)
    return {"signals": [{**r, "freshness": freshness(r["observed_at"])} for r in rows],
            "forecast": "not_enough_information", "model": "deterministic_only",
            "explanation": "Current trend history does not support a reliable forecast."}


def knowledge() -> dict[str, Any]:
    rows = _read("SELECT i.source,i.target_id,SUM(i.recurrence_count) AS recurrences,COUNT(*) AS incidents FROM lite_system_health_incidents i" + MEMBERSHIP_JOIN + " WHERE " + MONITORED + " GROUP BY i.source,i.target_id ORDER BY recurrences DESC LIMIT 32")
    return {"recurring_components": rows, "diagnostics": "deterministic", "ai_provider": "disabled", "evidence": "sanitized_summary_only"}


def policy() -> dict[str, Any]:
    return {"automatic_execution": "existing_independent_guardians_only", "engine_auto_repair": False,
            "mode": "fail_closed", "repair_catalog": list(REPAIR_CATALOG),
            "cooldown": "owned_by_existing_executor", "resource_budget": "owned_by_existing_executor",
            "controlled_recovery_adapter": {
                "implemented": True,
                "enabled": controlled_recovery_enabled(),
                "default_enabled": False,
                "operation_id": CONTROLLED_RECOVERY_OPERATION,
                "execution_owner": "worker_recovery_watchdog",
                "verification": "fresh_consumer_generation_and_health",
                "activation_scope": "qualification_only",
            },
            "explanation": "The allowlisted recovery adapter is candidate-only and disabled by default; existing guardians remain authoritative."}


def diagnose(incident_id: str) -> dict[str, Any] | None:
    found = incident(incident_id)
    if not found:
        return None
    related = [edge for edge in DEPENDENCY_EDGES if edge["downstream"] == found["source"]]
    upstream = [r for r in _observation_rows()
                if r["source"] in {edge["upstream"] for edge in related} and r["status"] in UNHEALTHY
                and freshness(r["observed_at"]) == "current"]
    return {
        "incident_id": incident_id, "generation": found["generation"],
        "evidence_freshness": found["evidence_freshness"],
        "observed_symptom": found["summary"], "suspected_cause": "A shared upstream dependency may be affected." if upstream else "Not established",
        "verified_cause": None, "cause_confidence": "inferred" if upstream else "unknown",
        "affected_component": found["target_id"],
        "supporting_signals": [{"source": r["source"], "status": r["status"], "target_id": r["target_id"]} for r in upstream[:8]],
        "repair_available": False, "safe_next_step": "Use the existing protected Devices, Apps or Recovery action when its current readiness permits.",
        "what_changes": "Nothing. Diagnosis reads persisted evidence only.",
        "what_does_not_change": "No service restart, configuration update, or data change.",
    }


# No new executor is activated. Persisted decisions distinguish diagnosis,
# denial and verified recovery rather than treating a command acceptance as success.
def record_diagnosis(incident_id: str) -> dict[str, Any] | None:
    assessed = diagnose(incident_id)
    if assessed is None:
        return None
    diagnosis_id = "diagnosis-" + uuid.uuid4().hex
    with connection() as conn:
        with begin_immediate(conn):
            conn.execute(
                "INSERT INTO lite_system_health_diagnoses "
                "(diagnosis_id,incident_id,incident_generation,created_at,symptom,suspected_cause,"
                "confidence,evidence_freshness,recommended_action) VALUES (?,?,?,?,?,?,?,?,?)",
                (diagnosis_id, incident_id, assessed["generation"], _now(),
                 _safe(assessed["observed_symptom"]), _safe(assessed["suspected_cause"]),
                 assessed["cause_confidence"], assessed["evidence_freshness"],
                 "Use reviewed existing recovery controls."),
            )
            _event(conn, incident_id, assessed["generation"], "diagnosed",
                   "Evidence-based diagnosis recorded; no repair was executed.")
            conn.execute(
                "DELETE FROM lite_system_health_diagnoses WHERE diagnosis_id NOT IN "
                "(SELECT diagnosis_id FROM lite_system_health_diagnoses ORDER BY created_at DESC LIMIT 2000)"
            )
    return {**assessed, "diagnosis_id": diagnosis_id, "recorded": True}


def repair_preflight(incident_id: str, operation_id: str, expected_generation: int) -> dict[str, Any] | None:
    found = incident(incident_id)
    if found is None:
        return None
    candidate = next((item for item in REPAIR_CATALOG if item["operation_id"] == operation_id), None)
    reasons: list[str] = []
    if candidate is None:
        reasons.append("operation_not_allowlisted")
    if found["generation"] != expected_generation:
        reasons.append("incident_generation_changed")
    if found["membership_state"] in {"retired", "removed", "historical_generation"}:
        reasons.append("device_no_longer_enrolled")
    elif found["membership_state"] == "unknown":
        reasons.append("device_membership_unknown")
    elif found["membership_state"] == "protected_conflict":
        reasons.append("protected_host_membership_conflict")
    if found["state"] == "resolved":
        reasons.append("incident_already_resolved")
    if found["evidence_freshness"] != "current" or found["observation_freshness"] != "current":
        reasons.append("evidence_not_current")
    if found.get("latest_observation_status") not in UNHEALTHY:
        reasons.append("unhealthy_evidence_not_confirmed")
    if operation_id != CONTROLLED_RECOVERY_OPERATION:
        reasons.append("operation_not_supported_by_controlled_adapter")
    elif not controlled_recovery_enabled():
        reasons.append("system_health_recovery_disabled")
    return {
        "incident_id": incident_id, "incident_generation": found["generation"],
        "operation_id": _safe(operation_id, 80), "risk_class": candidate["risk_class"] if candidate else "unknown",
        "allowed": not reasons, "status": "preflight_checked" if not reasons else "blocked",
        "reasons": reasons,
        "requires_confirmation": bool(candidate and candidate["risk_class"] != "A"),
        "requires_authorization": True, "requires_fresh_evidence": True,
        "max_retries": 2 if not reasons else 0, "cooldown_state": "ready" if not reasons else "not_applicable",
        "single_flight_state": "available" if not reasons else "not_applicable",
        "verification": "not_started", "execution": "not_started",
        "guidance": ("This device is no longer monitored; review its history." if not found["current_monitoring"] else
                     "Use the already governed Apps, Devices or Recovery action if it is currently offered."),
    }


def _public_recovery_request(row: dict[str, Any]) -> dict[str, Any]:
    """Expose lifecycle state while keeping digests, actor ids and evidence bounded."""
    item = dict(row)
    for field in ("idempotency_digest", "request_digest", "actor_id", "policy_decision_id", "before_evidence_json", "after_evidence_json"):
        item.pop(field, None)
    for field in ("before_evidence_json", "after_evidence_json"):
        raw = row.get(field)
        if raw:
            try:
                item[field.removesuffix("_json")] = json.loads(raw)
            except (TypeError, ValueError):
                item[field.removesuffix("_json")] = {}
    item["sanitized"] = True
    return item


def admit_controlled_recovery(
    incident_id: str,
    operation_id: str,
    expected_generation: int,
    idempotency_key: str,
    *,
    confirm: bool,
    auth_context: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any] | None:
    """Durably admit one allowlisted request; the worker remains the executor."""
    found = incident(incident_id)
    if found is None:
        return None
    assessment = repair_preflight(incident_id, operation_id, expected_generation)
    if assessment is None:
        return None
    if not assessment["allowed"]:
        return {**assessment, "status": "blocked", "recorded": False}
    actor = (auth_context or {}).get("actor") or {}
    actor_id = str(actor.get("identity_id") or "")[:120]
    actor_type = str(actor.get("type") or "unknown")[:32]
    if not actor_id or actor_id == "anonymous":
        return {**assessment, "status": "blocked", "reasons": ["actor_identity_required"], "recorded": False}
    digest = hashlib.sha256(str(idempotency_key).encode("utf-8")).hexdigest()
    request_material = {
        "incident_id": incident_id,
        "incident_generation": int(expected_generation),
        "enrollment_generation": int(found.get("enrollment_generation") or 0),
        "operation_id": operation_id,
        "target_id": str(found.get("target_id") or ""),
        "actor_id": actor_id,
        "actor_type": actor_type,
        "confirm": bool(confirm),
    }
    request_digest = hashlib.sha256(json.dumps(request_material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    now = _now()
    # A short deadline and bounded retry budget prevent immortal queued work.
    deadline = (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat(timespec="seconds").replace("+00:00", "Z")
    allowed = bool(decision.get("allow"))
    approval = decision.get("approval") if isinstance(decision.get("approval"), dict) else {}
    approval_id = str(
        decision.get("continuation_approval_id") or approval.get("approval_id") or ""
    )[:120]
    approval_required = str(decision.get("reason_code") or "") == "approval_required"
    status = "approval_required" if approval_required else "admitted" if allowed else "denied"
    execution_state = "queued" if allowed else "not_started"
    authorization_state = "approval_required" if approval_required else "authorized" if allowed else "denied"
    safe_summary = (
        "Governed durable recovery request recorded."
        if allowed else
        "Independent approval is required before recovery can be admitted."
        if approval_required else
        "Recovery request was denied before execution."
    )
    with connection() as conn:
        with begin_immediate(conn):
            previous = conn.execute(
                "SELECT * FROM lite_system_health_recovery_requests WHERE idempotency_digest=?",
                (digest,),
            ).fetchone()
            if previous is not None:
                same = (
                    previous["request_digest"] == request_digest
                    and previous["actor_id"] == actor_id
                    and int(previous["incident_generation"]) == int(expected_generation)
                )
                if not same:
                    return {**assessment, "status": "blocked", "reasons": ["idempotency_conflict"], "recorded": False}
                # An Enterprise approval is a durable continuation, not a new
                # request. Once the exact approval is revalidated by OPA, move
                # the same idempotent request into the existing owner queue.
                if previous["status"] == "approval_required" and allowed:
                    promoted = conn.execute(
                        """UPDATE lite_system_health_recovery_requests
                           SET status='admitted',execution_state='queued',authorization_state='authorized',
                               approval_id=?,policy_revision=?,policy_decision_id=?,updated_at=?,available_at=?,
                               safe_summary=?,outcome='queued',terminal_reason=''
                           WHERE request_id=? AND status='approval_required'""",
                        (
                            str(decision.get("continuation_approval_id") or approval_id)[:120],
                            str(decision.get("policy_revision") or "")[:80],
                            str(decision.get("decision_id") or "")[:120],
                            now, now,
                            "Independent approval revalidated; recovery queued for the existing worker owner.",
                            previous["request_id"],
                        ),
                    ).rowcount
                    if promoted:
                        conn.execute(
                            """UPDATE lite_system_health_repair_attempts
                               SET execution_state='queued',authorization_state='authorized',safe_summary=?,outcome='queued'
                               WHERE repair_id=?""",
                            ("Independent approval revalidated; recovery queued for the existing worker owner.", previous["request_id"]),
                        )
                        _event(conn, incident_id, int(expected_generation), "recovery_approved", "Independent approval revalidated; recovery queued for the existing worker owner.")
                        previous = conn.execute(
                            "SELECT * FROM lite_system_health_recovery_requests WHERE request_id=?",
                            (previous["request_id"],),
                        ).fetchone()
                return {**assessment, "request": _public_recovery_request(dict(previous)), "recorded": True, "idempotent_replay": True}
            active = conn.execute(
                "SELECT * FROM lite_system_health_recovery_requests WHERE incident_id=? AND operation_id=? "
                "AND status IN ('requested','preflight_checked','approval_required','approved','admitted','accepted','executing','awaiting_verification') "
                "ORDER BY requested_at LIMIT 1",
                (incident_id, operation_id),
            ).fetchone()
            if active is not None:
                return {**assessment, "status": "blocked", "reasons": ["single_flight_in_progress"],
                        "request": _public_recovery_request(dict(active)), "recorded": False}
            request_id = "recovery-" + uuid.uuid4().hex
            conn.execute(
                """INSERT INTO lite_system_health_recovery_requests(
                   request_id,incident_id,incident_generation,enrollment_generation,operation_id,
                   target_type,target_id,target_revision,idempotency_digest,request_digest,
                   actor_id,actor_type,policy_revision,policy_decision_id,authorization_state,approval_id,
                   status,execution_state,verification_state,requested_at,updated_at,available_at,deadline_at,
                   attempt,max_attempts,safe_summary,outcome,terminal_reason
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    request_id, incident_id, int(expected_generation), int(found.get("enrollment_generation") or 0),
                    operation_id, "system_health_incident", str(found.get("target_id") or ""),
                    f"{incident_id}:{expected_generation}:{int(found.get('enrollment_generation') or 0)}",
                    digest, request_digest, actor_id, actor_type, str(decision.get("policy_revision") or "")[:80],
                    str(decision.get("decision_id") or "")[:120], authorization_state, approval_id,
                    status, execution_state, "not_started", now, now, now, deadline, 0, 2,
                    safe_summary, "approval_required" if approval_required else "not_executed" if not allowed else "queued", "approval_required" if approval_required else ""),
            )
            conn.execute(
                """INSERT INTO lite_system_health_repair_attempts(
                   repair_id,incident_id,incident_generation,idempotency_key,operation_id,risk_class,
                   execution_state,authorization_state,preflight_state,verification_state,requested_at,
                   requested_by,safe_summary,outcome
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (request_id, incident_id, int(expected_generation), digest, operation_id, assessment["risk_class"],
                 execution_state, authorization_state, "passed", "not_started", now, actor_type,
                 safe_summary, "approval_required" if approval_required else "not_executed" if not allowed else "queued"),
            )
            _event(
                conn,
                incident_id,
                int(expected_generation),
                "recovery_requested" if allowed else "recovery_approval_required" if approval_required else "recovery_denied",
                safe_summary,
            )
            created = conn.execute(
                "SELECT * FROM lite_system_health_recovery_requests WHERE request_id=?", (request_id,)
            ).fetchone()
    return {**assessment, "request": _public_recovery_request(dict(created)), "recorded": True, "idempotent_replay": False}


def _claim_controlled_recovery(durable: str) -> dict[str, Any] | None:
    now = _now()
    with connection() as conn:
        with begin_immediate(conn):
            row = conn.execute(
                "SELECT * FROM lite_system_health_recovery_requests WHERE status='admitted' AND available_at<=? AND deadline_at>? ORDER BY requested_at LIMIT 1",
                (now, now),
            ).fetchone()
            if row is None:
                return None
            if row["target_id"] not in {"jetstream", "consumer:" + durable}:
                conn.execute(
                    "UPDATE lite_system_health_recovery_requests SET status='blocked',execution_state='blocked',authorization_state='stale',updated_at=?,completed_at=?,terminal_reason=?,safe_summary=? WHERE request_id=?",
                    (now, now, "target_not_allowlisted", "Recovery target is not the configured worker consumer.", row["request_id"]),
                )
                return None
            current = conn.execute(
                """SELECT i.state,i.generation,i.enrollment_generation,i.source,i.target_id,
                          o.status AS observation_status,o.observed_at
                   FROM lite_system_health_incidents i
                   LEFT JOIN lite_system_health_observations o
                     ON o.source=i.source AND o.target_id=i.target_id
                    AND (i.source NOT IN ('agent','supervisor','telemetry')
                         OR COALESCE(o.enrollment_generation,0)=COALESCE(i.enrollment_generation,0))
                   WHERE i.incident_id=?""",
                (row["incident_id"],),
            ).fetchone()
            if (
                current is None
                or current["state"] == "resolved"
                or int(current["generation"]) != int(row["incident_generation"])
                or int(current["enrollment_generation"] or 0) != int(row["enrollment_generation"] or 0)
                or current["source"] != "nats"
                or current["target_id"] != row["target_id"]
                or current["observation_status"] not in UNHEALTHY
            ):
                conn.execute(
                    "UPDATE lite_system_health_recovery_requests SET status='blocked',execution_state='blocked',authorization_state='stale',updated_at=?,completed_at=?,terminal_reason=?,safe_summary=? WHERE request_id=?",
                    (now, now, "target_state_changed", "The incident or its fresh evidence changed before execution.", row["request_id"]),
                )
                return None
            conn.execute(
                "UPDATE lite_system_health_recovery_requests SET status='executing',execution_state='running',verification_state='pending',attempt=attempt+1,updated_at=?,lease_until=? WHERE request_id=? AND status='admitted'",
                (now, (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat(timespec="seconds").replace("+00:00", "Z"), row["request_id"]),
            )
            claimed = conn.execute("SELECT * FROM lite_system_health_recovery_requests WHERE request_id=?", (row["request_id"],)).fetchone()
    return dict(claimed) if claimed else None


def _finish_controlled_recovery(request_id: str, *, status: str, execution_state: str, verification_state: str,
                                before: dict[str, Any], after: dict[str, Any], outcome: str, reason: str) -> None:
    now = _now()
    safe_before = json.dumps(before, sort_keys=True, separators=(",", ":"))[:4096]
    safe_after = json.dumps(after, sort_keys=True, separators=(",", ":"))[:4096]
    with connection() as conn:
        with begin_immediate(conn):
            conn.execute(
                """UPDATE lite_system_health_recovery_requests
                   SET status=?,execution_state=?,verification_state=?,updated_at=?,completed_at=?,lease_until=NULL,
                       before_evidence_json=?,after_evidence_json=?,safe_summary=?,outcome=?,terminal_reason=?
                   WHERE request_id=?""",
                (status, execution_state, verification_state, now, now, safe_before, safe_after,
                 "Controlled recovery completed with independently checked worker evidence." if status == "verified" else "Controlled recovery did not establish verified recovery.",
                 outcome[:80], reason[:120], request_id),
            )
            conn.execute(
                """UPDATE lite_system_health_repair_attempts
                   SET execution_state=?,verification_state=?,completed_at=?,safe_summary=?,outcome=? WHERE repair_id=?""",
                (execution_state, verification_state, now,
                 "Controlled recovery completed with independently checked worker evidence." if status == "verified" else "Controlled recovery did not establish verified recovery.",
                 outcome[:80], request_id),
            )


def _schedule_controlled_recovery_retry(request_id: str, *, before: dict[str, Any], after: dict[str, Any], reason: str) -> bool:
    """Keep retries finite and delayed without interrupting an active callback."""
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        cooldown = max(2, min(60, int(os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_COOLDOWN_SECONDS", "10"))))
    except ValueError:
        cooldown = 10
    available = (now_dt + timedelta(seconds=cooldown)).isoformat(timespec="seconds").replace("+00:00", "Z")
    with connection() as conn:
        with begin_immediate(conn):
            row = conn.execute("SELECT attempt,max_attempts,deadline_at FROM lite_system_health_recovery_requests WHERE request_id=?", (request_id,)).fetchone()
            if not row or int(row["attempt"]) >= int(row["max_attempts"] or 0) or str(row["deadline_at"] or "") <= now:
                return False
            conn.execute(
                """UPDATE lite_system_health_recovery_requests
                   SET status='admitted',execution_state='queued',verification_state='pending',updated_at=?,
                       available_at=?,lease_until=NULL,before_evidence_json=?,after_evidence_json=?,
                       safe_summary=?,outcome='retry_scheduled',terminal_reason=? WHERE request_id=?""",
                (now, available, json.dumps(before, sort_keys=True, separators=(",", ":"))[:4096],
                 json.dumps(after, sort_keys=True, separators=(",", ":"))[:4096],
                 "Recovery remains bounded and will be retried after a cooldown.", reason[:120], request_id),
            )
            conn.execute(
                "UPDATE lite_system_health_repair_attempts SET execution_state='queued',verification_state='pending',safe_summary=?,outcome='retry_scheduled' WHERE repair_id=?",
                ("Recovery remains bounded and will be retried after a cooldown.", request_id),
            )
    return True


async def process_controlled_recovery_requests(bus: Any, durable: str) -> int:
    """Worker-watchdog adapter; never starts a process or creates a consumer."""
    if not controlled_recovery_enabled():
        return 0
    request = _claim_controlled_recovery(durable)
    if not request:
        return 0
    before_raw = bus.durable_consumer_status(durable) or {}
    before = {
        "durable": durable, "generation": int(before_raw.get("generation") or 0),
        "healthy": bool(before_raw.get("healthy")), "callback_inflight": bool(before_raw.get("callback_inflight")),
        "checked_at": _now(), "source": "worker_recovery_owner",
    }
    if before["callback_inflight"]:
        _finish_controlled_recovery(request["request_id"], status="blocked", execution_state="blocked",
                                    verification_state="unavailable", before=before, after={},
                                    outcome="manual_attention_required", reason="active_callback_not_interrupted")
        return 1
    accepted = False
    try:
        accepted = bool(await bus.ensure_durable_consumer(durable, force=True))
    except Exception as exc:
        after = {"durable": durable, "checked_at": _now(), "source": "worker_recovery_owner", "error_type": type(exc).__name__}
        if _schedule_controlled_recovery_retry(request["request_id"], before=before, after=after, reason="recovery_owner_error"):
            return 1
        _finish_controlled_recovery(request["request_id"], status="execution_failed", execution_state="failed",
                                    verification_state="unavailable", before=before, after=after,
                                    outcome="execution_failed", reason="recovery_owner_error")
        return 1
    if accepted:
        # Keep the owner hand-off observable before the independent evidence
        # check. The final state is still unverified until the fresh snapshot
        # below proves a new consumer generation and healthy callback state.
        with connection() as conn:
            with begin_immediate(conn):
                conn.execute(
                    """UPDATE lite_system_health_recovery_requests
                       SET status='awaiting_verification',execution_state='accepted',verification_state='pending',
                           updated_at=?,safe_summary=? WHERE request_id=? AND status='executing'""",
                    (_now(), "Accepted by the existing worker recovery owner; awaiting fresh verification.", request["request_id"]),
                )
                _event(conn, request["incident_id"], int(request["incident_generation"]), "recovery_accepted", "Existing worker recovery owner accepted the request; fresh verification is pending.")
    after_raw = bus.durable_consumer_status(durable) or {}
    after = {
        "durable": durable, "generation": int(after_raw.get("generation") or 0),
        "healthy": bool(after_raw.get("healthy")), "callback_inflight": bool(after_raw.get("callback_inflight")),
        "checked_at": _now(), "source": "worker_recovery_owner",
    }
    verified = accepted and after["healthy"] and not after["callback_inflight"] and after["generation"] > before["generation"]
    if not verified and _schedule_controlled_recovery_retry(
        request["request_id"], before=before, after=after,
        reason="fresh_independent_verification_not_established",
    ):
        return 1
    _finish_controlled_recovery(
        request["request_id"],
        status="verified" if verified else "verification_failed",
        execution_state="succeeded" if accepted else "failed",
        verification_state="verified" if verified else "failed",
        before=before, after=after,
        outcome="verified_recovery" if verified else "verification_failed",
        reason="fresh_consumer_generation_and_health" if verified else "fresh_independent_verification_not_established",
    )
    return 1


def record_repair_denial(incident_id: str, operation_id: str, expected_generation: int,
                         idempotency_key: str, actor_class: str) -> dict[str, Any] | None:
    assessment = repair_preflight(incident_id, operation_id, expected_generation)
    if assessment is None:
        return None
    actor_class = actor_class if actor_class in {"human", "service", "test"} else "unknown"
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    denial_id = "denial-" + uuid.uuid4().hex
    with connection() as conn:
        with begin_immediate(conn):
            previous = conn.execute(
                "SELECT incident_id,incident_generation,operation_id,actor_class,reason_code FROM lite_system_health_repair_denials "
                "WHERE idempotency_digest=?", (digest,)
            ).fetchone()
            if previous is not None:
                if (previous["incident_id"] != incident_id or previous["operation_id"] != operation_id
                        or previous["incident_generation"] != expected_generation or previous["actor_class"] != actor_class):
                    return {**assessment, "reasons": ["idempotency_conflict"], "recorded": False}
                return {**assessment, "reasons": [previous["reason_code"]], "recorded": True,
                        "idempotent_replay": True}
            reason = assessment["reasons"][0]
            conn.execute(
                "INSERT INTO lite_system_health_repair_denials "
                "(denial_id,incident_id,incident_generation,idempotency_digest,operation_id,"
                "risk_class,denied_at,actor_class,reason_code,safe_summary) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (denial_id, incident_id, assessment["incident_generation"], digest,
                 _safe(operation_id, 80), assessment["risk_class"], _now(),
                 actor_class if actor_class in {"human", "service", "test"} else "unknown",
                 reason, "Repair was blocked; no execution occurred."),
            )
            _event(conn, incident_id, assessment["incident_generation"], "repair_blocked",
                   "Controlled recovery was blocked before execution.")
            conn.execute(
                "DELETE FROM lite_system_health_repair_denials WHERE denial_id NOT IN "
                "(SELECT denial_id FROM lite_system_health_repair_denials ORDER BY denied_at DESC LIMIT 2000)"
            )
    return {**assessment, "recorded": True, "idempotent_replay": False}


def decision_history(incident_id: str, *, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 50))
    return {
        "events": _read(
            "SELECT generation,event_type,created_at,safe_summary FROM lite_system_health_events "
            "WHERE incident_id=? ORDER BY id DESC LIMIT ?", (incident_id, limit),
        ),
        "repairs": _read(
            "SELECT repair_id,incident_generation,operation_id,execution_state,verification_state,"
            "requested_at,completed_at,safe_summary,outcome FROM lite_system_health_repair_attempts "
            "WHERE incident_id=? ORDER BY requested_at DESC LIMIT ?", (incident_id, limit),
        ),
        "removal_receipts": _read(
            "SELECT r.receipt_id,r.removal_status,r.reason_code,r.created_at "
            "FROM lite_system_health_incidents i JOIN device_removal_receipts r ON r.device_id=i.target_id "
            "WHERE i.incident_id=? AND i.source IN ('agent','supervisor','telemetry') "
            "AND r.sanitized=1 ORDER BY r.created_at_epoch_ms DESC,r.receipt_id DESC LIMIT ?",
            (incident_id, limit),
        ),
        "diagnoses": _read(
            "SELECT diagnosis_id,incident_id,incident_generation,created_at,suspected_cause,"
            "confidence,evidence_freshness,recommended_action FROM lite_system_health_diagnoses "
            "WHERE incident_id=? ORDER BY created_at DESC LIMIT ?",
            (incident_id, max(1, min(limit, 50))),
        ),
        "repair_denials": _read(
            "SELECT denial_id,incident_id,incident_generation,operation_id,risk_class,"
            "denied_at,actor_class,reason_code,safe_summary FROM lite_system_health_repair_denials "
            "WHERE incident_id=? ORDER BY denied_at DESC LIMIT ?",
            (incident_id, max(1, min(limit, 50))),
        ),
        "recovery_requests": _read(
            "SELECT request_id,incident_id,incident_generation,enrollment_generation,operation_id,status,"
            "execution_state,verification_state,requested_at,updated_at,completed_at,safe_summary,outcome,terminal_reason "
            "FROM lite_system_health_recovery_requests WHERE incident_id=? ORDER BY requested_at DESC LIMIT ?",
            (incident_id, max(1, min(limit, 50))),
        ),
    }


def configuration_drift() -> dict[str, Any]:
    """Read only expected-vs-observed status; never read PM2/Caddy config on GET."""
    from . import lite_phase3b_projections as prepared
    processes = prepared.snapshot("system.processes") or {}
    observations = []
    for item in (processes.get("items") or [])[:64]:
        if not isinstance(item, dict) or item.get("expected") is not True:
            continue
        status = _status(item.get("status"))
        if status not in HEALTHY:
            observations.append({
                "component": _safe(item.get("name"), 80),
                "observed_status": status,
                "classification": "observed_mismatch_unverified",
                "approved_change": "unknown",
                "auto_reconcile": False,
                "explanation": "A current process observation does not establish authorized configuration drift.",
            })
    return {"observations": observations, "classification": "requires_review" if observations else
            "not_established", "repair_enabled": False,
            "source": "persisted_process_projection", "raw_configuration_exposed": False}


def app_diagnostics(app_id: str) -> dict[str, Any] | None:
    from . import lite_app_registry, lite_phase3b_projections as prepared
    definition = lite_app_registry.maybe_app_definition(app_id)
    if definition is None:
        return None
    observed = prepared.snapshot("system.processes") or {}
    matches = [item for item in observed.get("items") or [] if
               isinstance(item, dict) and item.get("name") == definition.process]
    state = _status(matches[0].get("status")) if matches else "unknown"
    return {"app_id": definition.id, "app_label": definition.name,
            "process_status": state, "process_observation": "persisted",
            "route_status": "unknown", "database_status": "unknown",
            "media_scanned": False, "repair_authority": "existing_app_actions",
            "auto_repair_available": False,
            "summary": "Review the current app health and approved repair options in Apps Manage."}
