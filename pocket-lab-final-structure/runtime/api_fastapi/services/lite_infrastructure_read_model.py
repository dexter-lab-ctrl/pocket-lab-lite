"""Bounded infrastructure presentation from existing SQLite projections.

No collectors, filesystem enumeration, probes, migrations, command dispatch
or policy mutations are invoked by these reads. Only enumerated fields leave
the projection store. Unknown values and old observations remain explicit.
"""
from __future__ import annotations

import json
from typing import Any

from . import lite_system_health as health

DOMAINS = (
    "system.health", "system.status", "system.processes", "system.nats_remote", "system.agent", "system.supervisor",
    "system.remote_access", "system.storage_pressure", "system.sqlite_health",
    "system.telemetry_thresholds", "system.activity_current",
    "system.activity_history", "security.summary", "security.progress",
)
STATUS = frozenset({
    "healthy", "normal", "ready", "online", "running", "connected", "available",
    "degraded", "attention", "watch", "elevated", "critical", "unavailable",
    "unhealthy", "offline", "stopped", "errored", "failed", "missing",
    "unknown", "unsupported", "not_ready", "read_only", "writable",
    "storage_pressure", "recovery_required", "maintenance_active", "maintenance",
    "active", "idle", "queued", "accepted", "working", "in_progress", "pending",
    "cancelled", "succeeded", "blocked", "undeliverable", "timed_out",
    "verified", "not_verified", "not_configured", "not_run", "ok", "wal",
    "partial", "stale", "saved", "expired", "completed", "disabled", "stable", "converging", "repairing", "mismatch",
})
SERVICE_IDENTITIES = (
    ("api", "Control API", "pocket-api", "api", "system.health"),
    ("nats", "Command service", "pocket-nats", "nats", "system.nats_remote"),
    ("worker", "Background worker", "pocket-worker", None, "system.processes"),
    ("gateway", "Web gateway", "caddy-proxy", None, "system.processes"),
    ("policy", "Security policy engine", "pocket-opa", None, "system.processes"),
    ("agent", "Server node agent", "pocket-node-agent", "agent", "system.agent"),
    ("monitoring", "Device monitoring", "pocket-telemetry", "telemetry", "system.health"),
    ("supervisor", "Core supervisor", "pocketlab-core-supervisor", "supervisor", "system.supervisor"),
    ("guardian", "External runtime guardian", None, None, "system.health"),
)


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _items(value: Any, limit: int = 64) -> list[dict]:
    return [item for item in value[:limit] if isinstance(item, dict)] if isinstance(value, list) else []


def _enum(value: Any) -> str:
    return value if isinstance(value, str) and value in STATUS else "unknown"


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 2_000_000_000 else None


def _flag(value: Any) -> str:
    return "ready" if value is True else "not_ready" if value is False else "unknown"


def _freshness(row: dict) -> str:
    return health.freshness(row.get("updated_at"))


def _field(row: dict, label: str, value: Any) -> dict:
    return {"label": label, "status": _enum(value), "freshness": _freshness(row)}


def _number(row: dict, label: str, value: Any) -> dict:
    return {"label": label, "count": _count(value), "freshness": _freshness(row)}


def _snapshots() -> dict[str, dict]:
    # Do not call phase3b.snapshot: it may initialize schema on the API path.
    # Select only known domains from the same existing committed projection table.
    rows = health._read(
        "SELECT domain,status,payload_json,updated_at FROM phase3b_current_state "
        "WHERE domain IN (" + ",".join("?" for _ in DOMAINS) + ")",
        DOMAINS,
    )
    result = {}
    for row in rows:
        try:
            raw = row.get("payload_json")
            if not isinstance(raw, str) or len(raw) > 65536:
                continue
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        result[row["domain"]] = {**payload, "status": row.get("status"), "updated_at": row.get("updated_at")}
    return result


def _services(snapshots: dict) -> list[dict]:
    processes = snapshots.get("system.processes", {})
    system = snapshots.get("system.health", {})
    nats = snapshots.get("system.nats_remote", {})
    components = _dict(system.get("components"))
    runtime = _dict(snapshots.get("system.status", {}).get("runtime"))
    runtime_services = {item.get("process"):item for item in _items(runtime.get("services")) if isinstance(item.get("process"),str)}
    runtime_stamp = {"updated_at":runtime.get("observed_at")}
    # Only fixed managed-service names; no arbitrary process labels or PIDs.
    known = {item.get("service_id") or item.get("name"): item for item in _items(processes.get("items"), 128)
             if isinstance(item.get("service_id") or item.get("name"), str)}
    output = []
    for key, label, process, component, domain in SERVICE_IDENTITIES:
        row = snapshots.get(domain, {})
        process_row = known.get(process, {})
        state = _enum(process_row.get("status")) if process_row else "unknown"
        process_freshness = _freshness(processes) if process_row else "unknown"
        readiness = _enum(row.get("status")) if component and domain in {"system.agent","system.supervisor"} else _enum(components.get(component)) if component else "unknown"
        if key in {"agent","supervisor"}:
            # Aggregate fleet observations cannot establish the server-specific readiness.
            readiness = "unknown"
        if key == "nats":
            readiness = _enum(nats.get("status"))
        # Process online is not functional readiness. A stopped known process
        # is a valid observation, but only independent component evidence
        # may show operational readiness.
        owner = runtime_services.get(process,{})
        if owner and _freshness(runtime_stamp) == "current":
            readiness = _enum(owner.get("health"))
            row = runtime_stamp
        status = readiness
        if process_freshness == "current" and state in {"stopped", "errored", "failed", "missing"}:
            status = state
            row = processes
        output.append({
            "id": key, "label": label, "status": status,
            "freshness": _freshness(row) if status != "unknown" else "unknown",
            "process_status": state, "process_freshness": process_freshness,
            "functional_readiness": readiness,
            "configuration_match": _flag(owner.get("desired_state_match")) if owner else "unknown",
            "configuration_freshness": _freshness(runtime_stamp) if owner else "unknown",
            "restart_budget_remaining": _count(owner.get("restart_budget_remaining")) if owner else None,
        })
    return output


def _backup_readiness(storage: dict, sqlite: dict) -> list[dict]:
    # Same prepared source tables and completion clock used by
    # ControlPlaneProjectionStore.recovery_projection_snapshot; no initialize().
    rows = health._read(
        "SELECT status,verification_status,created_at,verified_at "
        "FROM backup_manifest_index ORDER BY updated_at_epoch_ms DESC,backup_id DESC LIMIT 1"
    )
    completion = health._read(
        "SELECT last_completed_at FROM projection_refresh_state WHERE domain=? LIMIT 1",
        ("recovery.summary",),
    )
    stamp = {"updated_at": completion[0].get("last_completed_at")} if completion else {}
    backup = rows[0] if rows else {}
    latest = _dict(sqlite.get("latest_backup"))
    return [
        _field(stamp, "Latest workspace backup", backup.get("status")),
        _field(stamp, "Backup integrity", backup.get("verification_status")),
        _field(storage, "Backup destination", storage.get("backup_target")),
        _field(sqlite, "Database backup", latest.get("status")),
        _number(sqlite, "Current database schema", sqlite.get("schema_version")),
        _number(sqlite, "Backup database schema", latest.get("schema_version")),
        _field({}, "Restore rehearsal", "unknown"),
        _field({}, "Restore compatibility", "unknown"),
        _field({}, "Rollback readiness", "unknown"),
    ]


def infrastructure() -> dict:
    snapshots = _snapshots()
    system = snapshots.get("system.health", {})
    nats = snapshots.get("system.nats_remote", {})
    remote = snapshots.get("system.remote_access", {})
    storage = snapshots.get("system.storage_pressure", {})
    sqlite = snapshots.get("system.sqlite_health", {})
    activity = snapshots.get("system.activity_current", {})
    history = snapshots.get("system.activity_history", {})
    telemetry = snapshots.get("system.telemetry_thresholds", {})
    security = snapshots.get("security.summary", {})
    progress = snapshots.get("security.progress", {})
    writer = _dict(sqlite.get("writer"))
    maintenance = _dict(sqlite.get("maintenance"))
    network = [
        _field(remote, "Remote access", remote.get("status")),
        _field(remote, "Tailscale daemon", _flag(remote.get("running"))),
        _field(remote, "Tailnet readiness", _flag(remote.get("ready"))),
        _field(remote, "Authentication readiness", _flag(remote.get("authenticated"))),
        _field(remote, "Trusted address reported", _flag(remote.get("tailnet_ip_present"))),
        _field(nats, "Local command connectivity", _flag(nats.get("connected"))),
        _field(nats, "JetStream availability", _flag(nats.get("jetstream_enabled"))),
        _field(remote, "Tailnet command connectivity", _flag(remote.get("nats_reachable"))),
        _field(nats, "Secondary command route", _flag(nats.get("secondary_ready"))),
        _field({}, "Local network reachability", "unknown"),
        _field({}, "Secure access certificates", "unknown"),
    ]
    runtime = _dict(snapshots.get("system.status",{}).get("runtime"))
    runtime_stamp = {"updated_at":runtime.get("observed_at")}
    logs = _dict(runtime.get("log_policy"))
    storage_rows = [
        _field(storage, "Storage pressure", storage.get("status")),
        _field(storage, "Available space band", storage.get("free_space_band")),
        _field(storage, "Workspace directory", storage.get("state_directory")),
        _field(storage, "Workspace write access", storage.get("writeability")),
        _field(storage, "WAL pressure", storage.get("wal_band")),
        _number(storage, "Total capacity (MiB)", storage.get("total_capacity_mib")),
        _number(storage, "Available capacity (MiB)", storage.get("free_capacity_mib")),
        _number(storage, "Database WAL (MiB)", storage.get("wal_size_mib")),
        _number(runtime_stamp, "Managed log bytes", logs.get("pm2_log_bytes")),
        _number(runtime_stamp, "Managed log ceiling (bytes)", logs.get("pm2_log_ceiling_bytes")),
        _field(runtime_stamp, "Managed log policy", _flag(logs.get("within_policy"))),
        _number({}, "Reclaimable storage (bytes)", None),
    ]
    database = [
        _field(sqlite, "Database health", sqlite.get("status")),
        _field(sqlite, "Integrity check", sqlite.get("quick_check")),
        _field(sqlite, "Journal mode", sqlite.get("journal_mode")),
        _field(sqlite, "WAL pressure", sqlite.get("wal_band")),
        _field(sqlite, "Write queue pressure", writer.get("queue_pressure")),
        _field(sqlite, "Maintenance", maintenance.get("status")),
        _field(sqlite, "Latest restore", _dict(sqlite.get("latest_restore")).get("state")),
    ]
    # No counts are represented as zero if the collector did not establish
    # counts_available. No inferred cancellation or replay state is presented.
    active = activity.get("counts_available") is True
    past = history.get("counts_available") is True
    workflows = [
        _number(activity, "Working", activity.get("active_operations") if active else None),
        _number(activity, "Waiting", activity.get("queued_operations") if active else None),
        _number(activity, "Stale operation records", activity.get("stale_operations") if active else None),
        _number(activity, "Needs attention", activity.get("attention_required") if active else None),
        _number(history, "Completed in recorded window", history.get("recent_completed") if past else None),
        _number(history, "Earlier failures", history.get("historical_failures") if past else None),
    ]
    resource = [
        _field(telemetry, "Resource signals", telemetry.get("status")),
        _field(storage, "Storage protection", storage.get("status")),
        _field(system, "Maintenance", "active" if system.get("maintenance_active") is True else "idle" if system.get("maintenance_active") is False else "unknown"),
        _field(telemetry, "Battery", _dict(telemetry.get("capabilities")).get("battery")),
        _field(telemetry, "Charging", _dict(telemetry.get("capabilities")).get("charging")),
        _field({}, "Resource preference", "unknown"),
    ]
    policy_rows = health._read("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1")
    policy_pending = health._read("SELECT 1 FROM policy_activation_operations WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain') LIMIT 1")
    policy = policy_rows[0] if policy_rows else {}
    policy_record = "unknown" if not policy.get("active_revision_id") else "ready" if policy.get("active_revision_id")==policy.get("known_good_revision_id") and not policy_pending else "not_ready"
    security_rows = [
        _field(security, "Safety evidence", security.get("status")),
        _field(progress, "Safety operation", progress.get("status")),
        _field({}, "Active policy integrity", "unknown"),
        _field({"updated_at":health._now()} if policy else {}, "Durable policy pointer agreement (not loaded policy proof)", policy_record),
        _field({}, "Vulnerability database freshness", "unknown"),
        _field({}, "System clock reliability", "unknown"),
    ]
    from . import lite_infrastructure_authority as authority
    preferences = authority.preferences()
    return {
        "source": "committed_sqlite_projections",
        "services": _services(snapshots), "network": network,
        "storage": storage_rows, "database": database,
        "workflows": workflows, "resources": resource, "security": security_rows,
        "backup": _backup_readiness(storage, sqlite),
        "cleanup": {
            "available": False, "estimated_bytes": None,
            "protected": ["Personal files and media", "Active databases and application data",
                          "Protected backups and audit evidence", "Current logs and recovery artifacts"],
            "reason": "A qualified owner-bound cleanup manifest and execution contract are required.",
        },
        "resource_policy": {
            "available": False, "proposed_modes": ["balanced", "low_power", "maintenance"],
            "preference": preferences["resource_mode"], "preference_revision": preferences["revision"],
            "essential_services_protected": True,
            "reason": "Preference is recorded separately from effective scheduler behavior.",
        },
        "retry_available": False, "cancellation_available": False,
        "configuration": [_field(runtime_stamp, "Desired runtime state", runtime.get("state"))],
        "sanitized": True,
    }


def correlate(items: list[dict], edges: list[dict]) -> list[dict]:
    """Bounded correlation hints, never verified root cause or suppression."""
    candidates = [item for item in items[:100] if item.get("concern_state") == "current_concern"
                  and item.get("current_monitoring") is True]
    def source(item: dict) -> str:
        return item.get("target_id") if item.get("source") == "system" else item.get("source")
    result = []
    for edge in edges[:32]:
        if edge.get("authority") not in {"verified_contract", "inferred", "verified_runtime"}:
            continue
        upstream = [item for item in candidates if source(item) == edge.get("upstream")]
        downstream = [item for item in candidates if source(item) == edge.get("downstream")]
        if not upstream or not downstream:
            continue
        result.append({
            "upstream": edge["upstream"], "downstream": edge["downstream"],
            "relationship_authority": edge["authority"], "cause_confidence": "inferred",
            "upstream_count": len(upstream), "downstream_count": len(downstream),
            "summary": "Related current concerns may share a dependency; review upstream evidence first.",
        })
    return result


def reliability() -> dict:
    # Existing request evidence only. Limit to a recent bounded page; absence
    # of records is not proof of uptime or successful recovery.
    rows = health._read(
        "SELECT status,execution_state,verification_state,requested_at,completed_at "
        "FROM lite_system_health_recovery_requests ORDER BY requested_at DESC,request_id DESC LIMIT 100"
    )
    verified = sum(row["status"] == "verified" and row["verification_state"] == "verified"
                   and row["execution_state"] == "succeeded" for row in rows)
    terminal = sum(row["status"] in {"verified", "execution_failed", "verification_failed", "verification_unavailable",
                                    "manual_attention_required"} for row in rows)
    from datetime import datetime
    durations = []
    for row in rows:
        if row["status"] != "verified" or row["verification_state"] != "verified" or row["execution_state"] != "succeeded":
            continue
        try:
            elapsed = (datetime.fromisoformat(row["completed_at"].replace("Z","+00:00")) - datetime.fromisoformat(row["requested_at"].replace("Z","+00:00"))).total_seconds()
            if 0 <= elapsed <= 3600:
                durations.append(elapsed)
        except (TypeError, ValueError, AttributeError):
            continue
    from . import lite_infrastructure_reliability as samples
    observed = samples.statistics()
    return {
        "scope": "latest_100_governed_requests", "sample_count": len(rows),
        "verified_count": verified, "terminal_execution_count": terminal,
        "verification_rate": round(verified / terminal, 4) if terminal else None,
        "observed_availability": observed["observed_availability"], "observation_coverage": observed["observation_coverage"],
        "sampled_reliability": observed,
        "mean_recovery_seconds": None, "automatic_recovery_rate": None,
        "mean_verified_request_elapsed_seconds": round(sum(durations)/len(durations), 1) if durations else None,
        "verified_request_timing_samples": len(durations),
        "reason": "Sampled availability excludes missing and unknown observations; it is not continuous uptime.",
    }
