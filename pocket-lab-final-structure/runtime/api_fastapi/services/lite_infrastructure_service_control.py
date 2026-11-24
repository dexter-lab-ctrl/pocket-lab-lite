"""Fixed stopped-service requests handed to the existing core supervisor."""
from __future__ import annotations
import hashlib
import json
from ..db.connection import connection,begin_immediate
from . import lite_system_health as health

SERVICES={"runtime.telemetry.recover":"pocket-telemetry","runtime.server_agent.recover":"pocket-node-agent"}
STOPPED={"stopped","errored","error"}


def binding(operation: str) -> dict:
    from . import lite_infrastructure_read_model as model
    snapshot=model._snapshots().get("system.processes",{})
    if model._freshness(snapshot)!="current":
        raise ValueError("process_evidence_not_current")
    for item in snapshot.get("items",[])[:128]:
        if item.get("name")==SERVICES[operation] and item.get("status") in STOPPED and type(item.get("restart_generation")) is int:
            return {"service":SERVICES[operation],"state":item["status"],"generation":item["restart_generation"]}
    raise ValueError("stopped_service_not_confirmed")


def process(supervisor,load_processes,observed: dict) -> dict | None:
    from . import lite_infrastructure_maintenance as control
    from . import lite_infrastructure_authority as authority
    from . import lite_security_maintenance as safety
    from . import lite_infrastructure_service_evidence as evidence
    from . import lite_infrastructure_read_model as model
    rows=health._read("""SELECT * FROM lite_system_health_maintenance_admissions
        WHERE status='executing' AND operation_id IN ('runtime.telemetry.recover','runtime.server_agent.recover')
        ORDER BY requested_at LIMIT 1""")
    if not rows:
        return None
    try:
        with control._owner_lock():
            rows=health._read("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=? AND status='executing'",(rows[0]["command_id"],))
            if not rows:
                return None
            row=rows[0]
            state=json.loads(row["evidence_json"])
            if not state.get("supervisor_requested") or state.get("owner_claimed"):
                return None
            command_id=row["command_id"]
            operation=row["operation_id"]
            target=SERVICES[operation]
            def blocked(reason):
                control._finish(command_id,"blocked",{"reason":reason})
                return None
            if not authority._future(row["expires_at"]) or not control._prepared_guard(operation):
                return blocked("preflight_changed")
            if safety.maintenance_state().get("active") or safety.active_security_scan():
                return blocked("maintenance_conflict")
            activity=model._snapshots().get("system.activity_current",{})
            if model._freshness(activity)!="current" or activity.get("counts_available") is not True or activity.get("active_operations")!=0:
                return blocked("active_work_not_excluded")
            with connection() as conn:
                auth=authority._human_authority(conn,row["actor_id"],row["session_id"])
            if not auth or not auth.get("owner_authority"):
                return blocked("execution_authority_unavailable")
            context={"actor":{"identity_id":row["actor_id"],"type":"human"},"session":{"authenticated":True},"authorization":auth}
            try:
                decision=control._policy(context,operation,command_id,command_id)
            except Exception:
                return blocked("policy_unavailable")
            if decision["policy_revision"]!=row["policy_revision"]:
                return blocked("policy_revision_changed")
            if not observed.get("checks",{}).get("nats_tcp_reachable"):
                return blocked("dependency_not_ready")
            current=next((item for item in load_processes() if item.get("name")==target),{})
            env=current.get("pm2_env") or {}
            expected=json.loads(row["candidate_json"])[0]
            if env.get("status") not in STOPPED or env.get("status")!=expected["state"] or env.get("restart_time")!=expected["generation"]:
                return blocked("target_generation_changed")
            with connection() as conn:
                with begin_immediate(conn):
                    if authority._human_authority(conn,row["actor_id"],row["session_id"])!=auth:
                        return None
                    conn.execute("UPDATE lite_system_health_maintenance_admissions SET evidence_json=?,expires_at=? WHERE command_id=? AND status='executing'",
                        (json.dumps({"supervisor_requested":True,"owner_claimed":True}),control._expires(300),command_id))
            if not control.enabled(operation) or safety.maintenance_state().get("active"):
                return blocked("execution_gate_changed")
            action=supervisor.restart_pm2(target,"system_health_owner_request")
            if not action.get("acted"):
                control._finish(command_id,"blocked" if action.get("event")=="restart_suppressed" else "uncertain",{"reason":"owner_restart_not_verified"})
                return action
            processes=load_processes()
            instance=evidence.process_instance(next((item for item in processes if item.get("name")==target),{}))
            generation=action.get("restart_generation")
            if not instance or not isinstance(generation,int):
                control._finish(command_id,"uncertain",{"reason":"process_instance_unavailable"})
                return action
            evidence.record_actions([action],processes)
            key=hashlib.sha256(f"{target}:{instance}:{generation}".encode()).hexdigest()
            with connection() as conn:
                with begin_immediate(conn):
                    conn.execute("UPDATE lite_system_health_maintenance_admissions SET evidence_json=? WHERE command_id=? AND status='executing'",
                        (json.dumps({"supervisor_requested":True,"owner_claimed":True,"service_evidence_id":key}),command_id))
            return action
    except BlockingIOError:
        return None
