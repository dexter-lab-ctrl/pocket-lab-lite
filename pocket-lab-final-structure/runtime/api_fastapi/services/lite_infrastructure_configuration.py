"""Scoped Caddy desired-state reconciliation; the existing reconciler executes.

No user configuration, shell arguments, arbitrary target, or policy activation.
The approved repository-owned runtime spec must survive the repair unchanged.
"""
from __future__ import annotations
import json
import re
from ..db.connection import connection,begin_immediate
from . import lite_system_health as health

OP="runtime.configuration.restore"
TARGET="caddy-proxy"
REASONS=("pm2_desired_spec_mismatch:caddy-proxy","pm2_desired_launch_mismatch:caddy-proxy")


def binding() -> dict:
    from . import lite_infrastructure_read_model as model
    runtime=model._snapshots().get("system.status",{}).get("runtime") or {}
    if health.freshness(runtime.get("observed_at"))!="current":
        raise ValueError("runtime_evidence_not_current")
    for row in runtime.get("services",[])[:32]:
        if row.get("process")==TARGET and row.get("desired_state_match") is False and row.get("state")=="online":
            generation=row.get("restart_generation")
            if type(generation) is int:
                return {"target":TARGET,"restart_generation":generation}
    raise ValueError("configuration_mismatch_not_confirmed")


def _approved(root) -> tuple[str,str] | None:
    try:
        path=root/"runtime"/"desired-process-specs.json"
        if path.is_symlink() or path.stat().st_size>65536:
            return None
        value=json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema")!="pocketlab.pm2-desired-process-specs/v1" or value.get("sanitized") is not True:
            return None
        result=(value["processes"][TARGET],value["launches"][TARGET])
        return result if all(isinstance(v,str) and re.fullmatch(r"[0-9a-f]{64}",v) for v in result) else None
    except (OSError,ValueError,KeyError,TypeError):
        return None


def process(reconciler, reasons: list[str], lifecycle_active: bool) -> dict | None:
    from . import lite_infrastructure_maintenance as control
    from . import lite_infrastructure_authority as authority
    from . import lite_security_maintenance as safety
    from . import lite_infrastructure_read_model as model
    pending=health._read("SELECT command_id FROM lite_system_health_maintenance_admissions WHERE status='executing' AND operation_id=? LIMIT 1",(OP,))
    if not pending:
        return None
    try:
        with control._owner_lock():
            rows=health._read("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=? AND status='executing'",(pending[0]["command_id"],))
            if not rows:
                return None
            row=rows[0]
            evidence=json.loads(row["evidence_json"])
            if not evidence.get("reconciler_requested") or evidence.get("owner_claimed"):
                return None
            cid=row["command_id"]
            def block(reason):
                control._finish(cid,"blocked",{"reason":reason})
                return None
            if lifecycle_active or safety.maintenance_state().get("active") or safety.active_security_scan() or not authority._future(row["expires_at"]) or not control._prepared_guard(OP):
                return block("configuration_preflight_changed")
            scoped=[reason for reason in reasons if reason in REASONS]
            if not scoped or any(reason not in REASONS for reason in reasons):
                return block("configuration_scope_changed")
            activity=model._snapshots().get("system.activity_current",{})
            if model._freshness(activity)!="current" or activity.get("counts_available") is not True or activity.get("active_operations")!=0:
                return block("active_work_not_excluded")
            try:
                if binding()!=json.loads(row["candidate_json"])[0]:
                    return block("configuration_target_changed")
            except ValueError:
                return block("configuration_target_changed")
            approved=_approved(reconciler.state_dir.parent)
            if not approved:
                return block("approved_spec_unavailable")
            with connection() as conn:
                auth=authority._human_authority(conn,row["actor_id"],row["session_id"])
            if not auth or not auth.get("owner_authority"):
                return block("execution_authority_unavailable")
            context={"actor":{"type":"human","identity_id":row["actor_id"]},"session":{"authenticated":True},"authorization":auth}
            try:
                decision=control._policy(context,OP,cid,cid)
            except Exception:
                return block("policy_unavailable")
            if decision["policy_revision"]!=row["policy_revision"]:
                return block("policy_revision_changed")
            with connection() as conn:
                with begin_immediate(conn):
                    if authority._human_authority(conn,row["actor_id"],row["session_id"])!=auth:
                        return None
                    conn.execute("UPDATE lite_system_health_maintenance_admissions SET evidence_json=?,expires_at=? WHERE command_id=? AND status='executing'",
                        (json.dumps({"owner_claimed":True,"reconciler_requested":True}),control._expires(600),cid))
            if not control.enabled(OP) or safety.maintenance_state().get("active"):
                return block("execution_gate_changed")
            event=reconciler._repair([scoped[0]])
            if not event.get("acted"):
                control._finish(cid,"blocked" if event.get("event")=="runtime_reconcile_suppressed" else "uncertain",{"reason":"owner_reconciliation_not_verified"})
                return event
            with connection() as conn:
                with begin_immediate(conn):
                    conn.execute("UPDATE lite_system_health_maintenance_admissions SET evidence_json=?,candidate_json=? WHERE command_id=? AND status='executing'",
                        (json.dumps({"owner_claimed":True,"reconciler_requested":True,"action_completed_at":health._now()}),json.dumps(list(approved)),cid))
            return event
    except BlockingIOError:
        return None


def verify(root, contract: dict, processes: list) -> None:
    from . import lite_infrastructure_maintenance as control
    from supervisors.pocketlab_runtime_registry import launch_fingerprint
    rows=health._read("SELECT * FROM lite_system_health_maintenance_admissions WHERE status='executing' AND operation_id=? LIMIT 1",(OP,))
    if not rows:
        return
    row=rows[0]
    evidence=json.loads(row["evidence_json"])
    stamp=contract.get("observed_at")
    if not evidence.get("action_completed_at") or health.freshness(stamp)!="current" or stamp<=evidence["action_completed_at"]:
        return
    approved=_approved(root)
    if not approved or list(approved)!=json.loads(row["candidate_json"]):
        control._finish(row["command_id"],"uncertain",{"reason":"approved_spec_changed"})
        return
    service=next((x for x in contract.get("services",[]) if x.get("process")==TARGET),{})
    process=next((x for x in processes if x.get("name")==TARGET),{})
    env=process.get("pm2_env") or {}
    observed=(env.get("POCKETLAB_PROCESS_SPEC_HASH"),launch_fingerprint(str(env.get("pm_exec_path") or ""),str(env.get("exec_interpreter") or "")))
    if service.get("stable") is True and service.get("health")=="ready" and service.get("desired_state_match") is True and observed==approved:
        control._finish(row["command_id"],"verified",{"configuration_match":True,"functional_readiness":True})
