"""Existing core supervisor actions; independent reconciler readiness evidence.

No restart is initiated here. PM2 process identity is hashed internally and never
returned. A process replacement between action and verification is unavailable,
not a verified recovery.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

from ..db.connection import connection, begin_immediate
from . import lite_system_health as health

SERVICE_OPERATIONS = {
    "pocket-nats":"runtime.nats.recover",
    "pocket-api":"runtime.api.recover",
    "pocket-worker":"runtime.worker.recover",
    "pocket-telemetry":"runtime.telemetry.recover",
    "pocket-node-agent":"runtime.server_agent.recover",
    "caddy-proxy":"runtime.gateway.recover",
    "pocket-opa":"runtime.policy.recover",
}


def process_instance(item: dict) -> str | None:
    env = item.get("pm2_env")
    if not isinstance(env,dict):
        return None
    pid, uptime, generation = item.get("pid"), env.get("pm_uptime"), env.get("restart_time")
    if type(pid) is not int or pid<=0 or type(uptime) is not int or uptime<=0 or type(generation) is not int or generation<0 or env.get("status")!="online":
        return None
    return hashlib.sha256(f"{pid}:{uptime}:{generation}".encode()).hexdigest()


def record_actions(actions: list, processes: list) -> None:
    if not actions:
        return
    known = {item.get("name"):item for item in processes if isinstance(item,dict) and isinstance(item.get("name"),str)}
    rows = []
    for action in actions[:16]:
        if not isinstance(action,dict) or action.get("event")!="restart_attempted" or action.get("acted") is not True:
            continue
        service=action.get("service")
        if service not in SERVICE_OPERATIONS:
            continue
        instance=process_instance(known.get(service,{}))
        generation=action.get("restart_generation")
        if not instance or type(generation) is not int or generation<=0:
            continue
        key=hashlib.sha256(f"{service}:{instance}:{generation}".encode()).hexdigest()
        rows.append((key,service,SERVICE_OPERATIONS[service],instance,generation,health._now()))
    if not rows:
        return
    with connection() as conn:
        with begin_immediate(conn):
            conn.executemany("""INSERT OR IGNORE INTO lite_system_health_service_owner_evidence
                (evidence_id,service_id,operation_id,process_instance_digest,owner_generation,completed_at,verification_state)
                VALUES(?,?,?,?,?,?,'pending')""",rows)
            conn.execute("""DELETE FROM lite_system_health_service_owner_evidence WHERE verification_state!='pending'
              AND evidence_id NOT IN(SELECT evidence_id FROM lite_system_health_service_owner_evidence ORDER BY completed_at DESC,evidence_id DESC LIMIT 1000)""")


def verify_runtime_contract(contract: dict, processes: list) -> None:
    rows=health._read("""SELECT evidence_id,service_id,process_instance_digest,completed_at
        FROM lite_system_health_service_owner_evidence WHERE verification_state='pending' ORDER BY completed_at LIMIT 32""")
    if not rows:
        return
    known={item.get("name"):item for item in processes if isinstance(item,dict) and isinstance(item.get("name"),str)}
    services={item.get("process"):item for item in contract.get("services",[])[:64] if isinstance(item,dict)}
    stamp=contract.get("observed_at")
    cutoff=(datetime.now(timezone.utc)-timedelta(seconds=300)).isoformat(timespec="seconds").replace("+00:00","Z")
    changes=[]
    for row in rows:
        instance=process_instance(known.get(row["service_id"],{}))
        service=services.get(row["service_id"],{})
        status=None
        if row["completed_at"]<=cutoff or (instance and instance!=row["process_instance_digest"]):
            status="unavailable"
        elif instance==row["process_instance_digest"] and service.get("stable") is True and service.get("health")=="ready" and health.freshness(stamp)=="current" and stamp>row["completed_at"]:
            status="verified"
        if status:
            changes.append((status,health._now() if status=="verified" else None,row["evidence_id"]))
    if changes:
        with connection() as conn:
            with begin_immediate(conn):
                conn.executemany("""UPDATE lite_system_health_service_owner_evidence SET verification_state=?,verified_at=?
                    WHERE evidence_id=? AND verification_state='pending'""",changes)


def history(limit: int=30) -> list[dict]:
    return health._read("""SELECT service_id,operation_id,completed_at,verification_state,verified_at
        FROM lite_system_health_service_owner_evidence ORDER BY completed_at DESC,evidence_id DESC LIMIT ?""",(max(1,min(limit,100)),))
