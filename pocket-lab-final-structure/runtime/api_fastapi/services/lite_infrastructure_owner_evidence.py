"""Record existing watchdog executions without admitting or dispatching work."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from . import lite_system_health as health
from ..db.connection import connection, begin_immediate

MAX_RECORDS = 1000
VERIFICATION_WINDOW_SECONDS = 90


def record_consumer_recovery(*, owner_instance: str, durable: str,
                             before: dict, after: dict, started_at: str) -> str | None:
    # Only the configured worker calls this after recover_durable_consumers
    # returns the actual durable. Never treat an ordinary reconnect as execution.
    previous = before.get("generation")
    generation = after.get("generation")
    if type(previous) is not int or type(generation) is not int or generation <= previous:
        return None
    key = hashlib.sha256(f"{owner_instance}:{durable}:{generation}".encode()).hexdigest()
    incident = health.incident(health._identity_for_generation("nats", "consumer:" + durable))
    incident_id = None
    incident_generation = None
    if incident and incident.get("concern_state") == "current_concern":
        incident_id = incident["incident_id"]
        incident_generation = incident["generation"]
    with connection() as conn:
        with begin_immediate(conn):
            conn.execute(
                """INSERT OR IGNORE INTO lite_system_health_owner_recovery_evidence
                   (evidence_id,operation_id,execution_owner,target_scope,owner_instance,
                    consumer_generation,incident_id,incident_generation,started_at,completed_at,verification_state)
                   VALUES (?,'runtime.consumer.reconnect','nats_worker_watchdog','local_worker_consumer',?,?,?,?,?,?,'pending')""",
                (key, owner_instance, generation, incident_id, incident_generation, started_at, health._now()),
            )
            conn.execute(
                """DELETE FROM lite_system_health_owner_recovery_evidence
                   WHERE verification_state!='pending' AND evidence_id NOT IN (
                   SELECT evidence_id FROM lite_system_health_owner_recovery_evidence
                   ORDER BY completed_at DESC,evidence_id DESC LIMIT ?)""",
                (MAX_RECORDS,),
            )
    return key


def verify_consumer_recoveries(owner_instance: str, status: dict) -> None:
    """A later fetch from the same registered consumer generation is required."""
    now = health._now()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=VERIFICATION_WINDOW_SECONDS)).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = health._read(
        """SELECT evidence_id,owner_instance,consumer_generation,completed_at
           FROM lite_system_health_owner_recovery_evidence
           WHERE verification_state='pending' ORDER BY completed_at LIMIT 32"""
    )
    decisions = []
    for row in rows:
        outcome = None
        if row["owner_instance"] != owner_instance or row["completed_at"] <= cutoff:
            outcome = "unavailable"
        elif status.get("generation") != row["consumer_generation"]:
            outcome = "unavailable"
        elif (status.get("healthy") is True and status.get("task_alive") is True
              and status.get("subscription_present") is True
              and isinstance(status.get("last_fetch_at"), str)
              and health.freshness(status["last_fetch_at"]) == "current"
              and status["last_fetch_at"] > row["completed_at"]):
            outcome = "verified"
        if outcome:
            decisions.append((outcome, now if outcome == "verified" else None, row["evidence_id"]))
    if not decisions:
        return
    with connection() as conn:
        with begin_immediate(conn):
            conn.executemany(
                """UPDATE lite_system_health_owner_recovery_evidence
                   SET verification_state=?,verified_at=?
                   WHERE evidence_id=? AND verification_state='pending'""",
                decisions,
            )


def history(limit: int = 30) -> list[dict]:
    # No internal instance IDs, target identifiers, payloads or hashes.
    return health._read(
        """SELECT operation_id,execution_owner,target_scope,incident_generation,
                  started_at,completed_at,verification_state,verified_at
           FROM lite_system_health_owner_recovery_evidence
           ORDER BY completed_at DESC,evidence_id DESC LIMIT ?""",
        (max(1, min(limit, 100)),),
    )


def summary() -> dict:
    recent = history(30)
    verified = [row for row in recent if row["verification_state"] == "verified"]
    return {
        "source": "existing_worker_watchdog",
        "scope": "latest_30_recorded_automatic_consumer_recoveries",
        "recorded_count": len(recent),
        "verified_count": len(verified),
        "pending_count": sum(row["verification_state"] == "pending" for row in recent),
        "unverified_count": sum(row["verification_state"] in {"failed", "unavailable"} for row in recent),
        "recent_verified": verified[:3],
    }
