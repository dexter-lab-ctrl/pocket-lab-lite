"""Deterministic, low-power System Health incident intelligence.

Runtime observations enter only from worker-owned committed projections. HTTP reads
never collect live process state or run migrations. Recovery execution remains
with existing supervisors/agents/workers, not this module.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any

from ..db.connection import begin_immediate, open_connection, open_fast_read_connection

ACTIVE = frozenset({"detected", "diagnosing", "diagnosed", "repair_available", "repairing", "verifying", "blocked", "failed", "manual_attention_required"})
UNHEALTHY = frozenset({"degraded", "unavailable", "unhealthy", "critical", "offline", "stopped", "missing", "errored", "failed", "attention", "pressure"})
HEALTHY = frozenset({"healthy", "online", "ready", "running", "connected"})
UNKNOWN = frozenset({"unknown", "stale", "unverified", "pending", "unsupported", "not_ready"})
OBSERVATION_MAX_AGE_SECONDS = 300
MAX_HISTORY = 2000
# Contract edges describe dependencies, not proof of a live connection.
DEPENDENCY_EDGES = (
    {"upstream": "nats", "downstream": "worker", "authority": "verified_contract", "summary": "Commands use NATS/JetStream."},
    {"upstream": "nats", "downstream": "agent", "authority": "verified_contract", "summary": "Device agents use the command/event bus."},
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe(value: Any, limit: int = 180) -> str:
    # Never store raw payloads, URLs, paths, credentials or free-form error traces.
    value = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    if any(character in value for character in ("=", "/", "\\", "@", "<", ">")):
        return ""
    return "".join(c for c in value if 32 <= ord(c) <= 126)[:limit]


def _status(value: Any) -> str:
    normalized = _safe(value, 32).lower()
    return normalized if normalized in UNHEALTHY | HEALTHY | UNKNOWN | {"watch", "elevated", "recovering", "maintenance", "active", "read_only"} else "unknown"


def _identity(source: str, target: str) -> str:
    material = f"{source}:{target}:health".encode("utf-8")
    return "health-" + hashlib.sha256(material).hexdigest()[:24]


def _event(conn: sqlite3.Connection, incident_id: str, generation: int, kind: str, summary: str) -> None:
    conn.execute(
        "INSERT INTO lite_system_health_events (incident_id,generation,event_type,created_at,safe_summary) VALUES (?,?,?,?,?)",
        (incident_id, generation, kind, _now(), _safe(summary, 180)),
    )


def _prune(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM lite_system_health_events WHERE id NOT IN (SELECT id FROM lite_system_health_events ORDER BY id DESC LIMIT 4000)")
    conn.execute("DELETE FROM lite_system_health_repair_attempts WHERE repair_id NOT IN (SELECT repair_id FROM lite_system_health_repair_attempts ORDER BY requested_at DESC LIMIT 2000)")
    conn.execute(
        "DELETE FROM lite_system_health_incidents WHERE state='resolved' AND incident_id NOT IN "
        "(SELECT incident_id FROM lite_system_health_incidents ORDER BY last_seen_at DESC LIMIT ?)",
        (MAX_HISTORY,),
    )


def _observations(domain: str, payload: dict[str, Any]):
    source = SOURCE_NAMES.get(domain)
    if not source or not isinstance(payload, dict):
        return
    if domain == "system.health":
        for target, value in sorted((payload.get("components") or {}).items()):
            if target in {"api", "nats", "processes", "agent", "supervisor", "remote_access", "storage", "sqlite", "telemetry"}:
                yield ("system", target, _status(value), "Component health requires review.")
        return
    if domain in {"system.agent", "system.supervisor"}:
        for item in (payload.get("items") or [])[:64]:
            if not isinstance(item, dict):
                continue
            target = _safe(item.get("device_id"), 100)
            if not target:
                continue
            raw = item.get("connection_state") if domain == "system.agent" else item.get("state")
            if domain == "system.agent" and item.get("command_deliverable") is False:
                raw = "offline" if raw not in UNKNOWN else "unknown"
            yield (source, target, _status(raw), "Device connection or agent needs review.")
        return
    if domain == "system.processes":
        for item in (payload.get("items") or [])[:64]:
            if isinstance(item, dict) and item.get("expected"):
                target = _safe(item.get("name"), 100)
                if target:
                    yield (source, target, _status(item.get("status")), "Required process needs attention.")
        return
    if domain == "system.nats_remote":
        yield (source, "jetstream", _status(payload.get("status")), "Command delivery needs attention.")
        for name, item in sorted((payload.get("durable_consumer_health") or {}).items()):
            if isinstance(item, dict):
                yield (source, "consumer:" + _safe(name, 60), "healthy" if item.get("healthy") else "degraded", "Command consumer readiness needs attention.")
        return
    yield (source, source, _status(payload.get("status")), "System health signal needs review.")


def ingest_projection(domain: str, payload: dict[str, Any]) -> int:
    """Call only after a worker-owned projection commit; never from a GET."""
    observations = list(_observations(domain, payload) or [])
    if not observations:
        return 0
    revision = _safe(payload.get("generation") or payload.get("revision"), 64)
    now = _now()
    changed = 0
    with open_connection() as conn:
        with begin_immediate(conn):
            for source, target, status, summary in observations[:64]:
                if not target:
                    continue
                current = conn.execute(
                    "SELECT status,source_revision FROM lite_system_health_observations WHERE source=? AND target_id=?",
                    (source, target),
                ).fetchone()
                if current and current["status"] == status and current["source_revision"] == revision:
                    continue
                conn.execute(
                    "INSERT INTO lite_system_health_observations (source,target_id,status,observed_at,source_revision,summary) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(source,target_id) DO UPDATE SET status=excluded.status,observed_at=excluded.observed_at,"
                    "source_revision=excluded.source_revision,summary=excluded.summary",
                    (source, target, status, now, revision, summary),
                )
                incident_id = _identity(source, target)
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
                            "(incident_id,source,target_id,kind,state,severity,first_seen_at,last_seen_at,evidence_revision,summary) "
                            "VALUES (?,?,?,'health','detected',?,?,?,?,?)",
                            (incident_id, source, target, severity, now, now, revision, summary),
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
        with open_fast_read_connection() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except (FileNotFoundError, sqlite3.OperationalError):
        return []


def incidents(*, include_resolved: bool = False, limit: int = 40, offset: int = 0) -> dict[str, Any]:
    limit, offset = max(1, min(int(limit), 100)), max(0, min(int(offset), 10000))
    where = "" if include_resolved else "WHERE state != 'resolved'"
    items = _read(f"SELECT * FROM lite_system_health_incidents {where} ORDER BY last_seen_at DESC, incident_id LIMIT ? OFFSET ?", (limit, offset))
    return {"items": [public_incident(item) for item in items], "limit": limit, "offset": offset, "next_offset": offset + len(items) if len(items) == limit else None}


def public_incident(item: dict[str, Any]) -> dict[str, Any]:
    if not item:
        return {}
    result = dict(item)
    result["evidence_freshness"] = freshness(item.get("last_seen_at"))
    result["cause_confidence"] = "unconfirmed" if not item.get("verified_cause") else "verified"
    result["repair_available"] = False  # Explicitly off until owned command handlers are qualified.
    result["repair_guidance"] = "Review the existing protected recovery action for this component."
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
    rows = _read("SELECT * FROM lite_system_health_incidents WHERE incident_id=? LIMIT 1", (incident_id,))
    return public_incident(rows[0]) if rows else None


def summary() -> dict[str, Any]:
    signals = _read("SELECT source,target_id,status,observed_at FROM lite_system_health_observations ORDER BY source,target_id LIMIT 256")
    active = _read("SELECT state,severity FROM lite_system_health_incidents WHERE state!='resolved' LIMIT 256")
    recent = _read("SELECT incident_id,state,summary,resolved_at FROM lite_system_health_incidents WHERE state='resolved' ORDER BY resolved_at DESC LIMIT 5")
    fresh = [s for s in signals if freshness(s["observed_at"]) == "current"]
    healthy = sum(1 for s in fresh if s["status"] in HEALTHY)
    unhealthy = sum(1 for s in fresh if s["status"] in UNHEALTHY)
    unknown_count = len(signals) - len(fresh) + sum(s["status"] not in (HEALTHY | UNHEALTHY) for s in fresh)
    status = "unknown" if not signals or not fresh else "attention" if unhealthy or active else "unknown" if unknown_count else "healthy"
    return {
        "status": status, "checked_at": _now(), "data_source": "persisted_projection",
        "observed_services": len(signals), "healthy_services": healthy,
        "active_problems": len(active), "critical_problems": sum(a["severity"] == "critical" for a in active),
        "unknown_services": unknown_count, "automatic_repairs_running": 0,
        "recent_verified_recoveries": 0,  # Healthy observation is not verified repair recovery.
        "recent_resolutions": recent,
        "freshness": "current" if fresh else "stale" if signals else "unavailable",
        "summary": "No authoritative health observations yet." if not signals else
                   "One or more services need attention." if status == "attention" else
                   "Health evidence is incomplete or stale." if status == "unknown" else
                   "Observed services are healthy.",
    }


def history(limit: int = 30, offset: int = 0) -> dict[str, Any]:
    result = incidents(include_resolved=True, limit=limit, offset=offset)
    result["repairs"] = _read(
        "SELECT repair_id,incident_id,operation_id,risk_class,execution_state,verification_state,"
        "requested_at,completed_at,safe_summary,outcome FROM lite_system_health_repair_attempts ORDER BY requested_at DESC LIMIT ?",
        (max(1, min(limit, 100)),),
    )
    return result


def dependency_graph() -> dict[str, Any]:
    observations = _read("SELECT source,target_id,status,observed_at FROM lite_system_health_observations ORDER BY source,target_id LIMIT 128")
    nodes = []
    for row in observations:
        nodes.append({**row, "freshness": freshness(row["observed_at"]), "authority": "verified_runtime" if freshness(row["observed_at"]) == "current" else "unknown"})
    return {"nodes": nodes, "edges": list(DEPENDENCY_EDGES), "description": "Contract edges are not live connectivity proof."}


def resource_intelligence() -> dict[str, Any]:
    rows = _read("SELECT source,target_id,status,observed_at FROM lite_system_health_observations WHERE source IN ('storage','telemetry','sqlite') LIMIT 32")
    return {"signals": [{**r, "freshness": freshness(r["observed_at"])} for r in rows],
            "forecast": "not_enough_information", "model": "deterministic_only",
            "explanation": "Current trend history does not support a reliable forecast."}


def knowledge() -> dict[str, Any]:
    rows = _read("SELECT source,target_id,SUM(recurrence_count) AS recurrences,COUNT(*) AS incidents FROM lite_system_health_incidents GROUP BY source,target_id ORDER BY recurrences DESC LIMIT 32")
    return {"recurring_components": rows, "diagnostics": "deterministic", "ai_provider": "disabled", "evidence": "sanitized_summary_only"}


def policy() -> dict[str, Any]:
    return {"automatic_execution": "existing_independent_guardians_only", "engine_auto_repair": False,
            "mode": "fail_closed", "repair_catalog": list(REPAIR_CATALOG),
            "cooldown": "owned_by_existing_executor", "resource_budget": "owned_by_existing_executor",
            "explanation": "No new automatic restart or destructive repair path is enabled."}


def diagnose(incident_id: str) -> dict[str, Any] | None:
    found = incident(incident_id)
    if not found:
        return None
    related = [edge for edge in DEPENDENCY_EDGES if edge["downstream"] == found["source"]]
    upstream = [r for r in _read("SELECT source,target_id,status,observed_at FROM lite_system_health_observations LIMIT 128")
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
