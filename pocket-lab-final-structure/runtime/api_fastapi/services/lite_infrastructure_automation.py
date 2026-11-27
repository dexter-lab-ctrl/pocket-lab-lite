"""One selective Risk A candidate: refresh optional activity history.
The existing worker/scheduler remains the execution owner. Only the fixed
activity-history projection is source-qualified; no automatic cleanup,
restart, restore or arbitrary command is admitted.
"""
from __future__ import annotations
from datetime import datetime, timezone
import os
import uuid
from ..db.connection import connection,begin_immediate
from . import lite_system_health as health
from . import lite_infrastructure_authority as authority
from . import lite_infrastructure_operations as ops
from . import lite_policy_opa as opa

OP="projection.reconcile"
ACTION="system_health.automatic"
DOMAIN="system.activity_history"
TRIGGER_PREFIX="reconcile_system_health_automatic"


def _owner_versions(conn,owner_id: str) -> tuple | None:
    human=conn.execute("SELECT auth_version,status FROM human_identities WHERE human_id=?",(owner_id,)).fetchone()
    member=conn.execute("SELECT role,status,authorization_version FROM enterprise_memberships WHERE human_id=?",(owner_id,)).fetchone()
    config=conn.execute("SELECT enabled,authorization_version FROM enterprise_configuration WHERE configuration_id=1").fetchone()
    if not human or human["status"]!="active":
        return None
    if config and config["enabled"]:
        if not member or member["role"]!="Owner" or member["status"]!="active":
            return None
    else:
        local=conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
        if not local or local["human_id"]!=owner_id:
            return None
    return (human["auth_version"],member["authorization_version"] if member else 1,config["authorization_version"] if config else 1)


def _stored() -> dict:
    rows=health._read("SELECT * FROM lite_system_health_automation_policy WHERE singleton_id=1")
    return rows[0] if rows else {}


def _gate() -> bool:
    if not ops.automatic_gate_open():
        return False
    # The existing scheduler remains the owner.  This second gate is the
    # separately recorded optional-capability activation; candidate consent or
    # a release signature alone cannot open it.
    from . import lite_lifecycle_capability_activation as activation
    try:
        from ..db.connection import read_connection
        with read_connection() as conn:
            return activation.execution_enabled(conn)
    except Exception:
        return False


def _trigger_reason(attempt_id: str) -> str:
    # The scheduler sanitizes this bounded identifier without removing the
    # separator, so a later read can prove which durable attempt requested the
    # observed refresh instead of accepting an unrelated scheduled refresh.
    return f"{TRIGGER_PREFIX}:{attempt_id}"


def public() -> dict:
    row=_stored()
    recent=health._read("SELECT attempt_id,operation_id,status,requested_at,completed_at FROM lite_system_health_automation_attempts ORDER BY requested_at DESC LIMIT 20")
    gate_open = _gate()
    preference_enabled = bool(row.get("enabled"))
    latest = recent[0] if recent else {}
    fence = ops.activation_fence_status("automatic")
    reasons = [] if gate_open else list(fence.get("reason_codes") or [])
    if not gate_open and os.environ.get("POCKETLAB_ENVIRONMENT","").casefold() != "qualification" and os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC") != "1":
        reasons.append("automatic_runtime_opt_in_required")
    if not preference_enabled:
        reasons.append("owner_preference_required")
    return {"revision":row.get("revision",0),"preference_enabled":preference_enabled,
        "operation_id":OP,"source_qualified":OP in ops.PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS,
        "activation_gate_open":gate_open,"runtime_enabled":bool(gate_open and preference_enabled),
        "owner_preferred":preference_enabled,"activation_confirmation":{
            key:fence[key] for key in ("valid","required","runtime_revision","reason_codes","sanitized")
        },
        "effective_execution_confirmed":bool(latest and latest.get("status")=="verified"),
        "execution_state":latest.get("status") if latest else "idle",
        "reason_codes":list(dict.fromkeys(reasons)),
        "recent":recent,
        "sanitized":True}


def save(context: dict, *, expected_revision: int, enabled: bool, confirm: bool) -> dict:
    if not confirm:
        raise ValueError("confirmation_required")
    with connection() as conn:
        owner=authority.require_owner(conn,context)
        versions=_owner_versions(conn,owner)
    if not versions:
        raise PermissionError("owner_required")
    decision=opa.evaluate_authorization(auth_context=context,action_id="system_health.maintenance",
        target_type="system_health_maintenance",target_id="automatic-policy",
        target_revision=str(expected_revision),target={"operation_id":"automation.policy.update","adapter_enabled":True,"confirmed":True},
        request_context={"confirmation_present":True})
    with connection() as conn:
        with begin_immediate(conn):
            owner=authority.require_owner(conn,context)
            if _owner_versions(conn,owner)!=versions:
                raise ValueError("authority_changed")
            current=conn.execute("SELECT revision FROM lite_system_health_automation_policy WHERE singleton_id=1").fetchone()
            rev=current["revision"] if current else 0
            if rev!=expected_revision:
                raise ValueError("preference_revision_changed")
            next_revision = rev + 1
            conn.execute("""INSERT INTO lite_system_health_automation_policy
                (singleton_id,revision,enabled,owner_id,owner_auth_version,membership_version,
                 configuration_version,policy_revision,decision_id,updated_at)
                VALUES(1,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(singleton_id) DO UPDATE SET revision=excluded.revision,enabled=excluded.enabled,
                owner_id=excluded.owner_id,owner_auth_version=excluded.owner_auth_version,membership_version=excluded.membership_version,
                configuration_version=excluded.configuration_version,policy_revision=excluded.policy_revision,
                decision_id=excluded.decision_id,updated_at=excluded.updated_at""",
                (next_revision,int(enabled),owner,*versions,decision["policy_revision"],decision["decision_id"],health._now()))
            ops.write_activation_fence(
                conn,
                "automatic",
                confirmed=bool(enabled),
                reference_revision=next_revision,
                now=health._now(),
            )
            authority.audit(conn,owner,"preferences_changed","automatic_projection_reconciliation")
    return public()


def _projection() -> dict:
    rows=health._read("SELECT last_completed_at,last_error_type,last_trigger_reason,execution_owner FROM projection_refresh_state WHERE domain=?",(DOMAIN,))
    return rows[0] if rows else {}


def _projection_evidence(attempt: dict, projection: dict | None = None) -> bool:
    """Accept completion only from this attempt's scheduler dispatch."""
    projection = projection if projection is not None else _projection()
    completed = projection.get("last_completed_at")
    if not completed or completed <= str(attempt.get("requested_at") or "") or projection.get("last_error_type"):
        return False
    if projection.get("last_trigger_reason") != _trigger_reason(str(attempt.get("attempt_id") or "")):
        return False
    owner = str(projection.get("execution_owner") or "")
    if os.environ.get("POCKETLAB_ENVIRONMENT","").casefold() == "qualification":
        return owner in {"worker", "unknown", "test", "direct", "oneshot"}
    return owner == "worker"


def _elapsed(stamp: str | None) -> float | None:
    try:
        return (datetime.now(timezone.utc)-datetime.fromisoformat(stamp.replace("Z","+00:00"))).total_seconds()
    except (AttributeError,TypeError,ValueError):
        return None


def tick() -> None:
    from . import lite_infrastructure_maintenance as maintenance
    from . import lite_security_maintenance as safety
    from . import lite_infrastructure_host_protection as host
    from . import lite_infrastructure_read_model as model
    from . import lite_phase3c_projections as prepared
    # Existing watchdog owns bounded cadence. Pending evidence is reconciled
    # even after gate closure; no work is replayed after a restart.
    pending=health._read("SELECT * FROM lite_system_health_automation_attempts WHERE status='pending' LIMIT 1")
    if pending:
        row=pending[0]
        projection=_projection()
        completed=projection.get("last_completed_at")
        duration=_elapsed(row["requested_at"])
        verified=_projection_evidence(row, projection)
        if verified or (duration is not None and duration>=300):
            with connection() as conn:
                with begin_immediate(conn):
                    conn.execute("UPDATE lite_system_health_automation_attempts SET status=?,completed_at=? WHERE attempt_id=? AND status='pending'",
                        ("verified" if verified else "unavailable",health._now(),row["attempt_id"]))
        return
    if not _gate():
        return
    row=_stored()
    if not row.get("enabled"):
        return
    last=health._read("SELECT status,policy_version,requested_at FROM lite_system_health_automation_attempts ORDER BY requested_at DESC LIMIT 1")
    if last:
        age=_elapsed(last[0]["requested_at"])
        if age is None or age<1800 or (last[0]["status"]=="unavailable" and last[0]["policy_version"]==row["revision"]):
            return
    projection=_projection()
    age=_elapsed(projection.get("last_completed_at"))
    if age is None or age<600 or age>86400:
        return
    try:
        with maintenance._owner_lock():
            with connection() as conn:
                if _owner_versions(conn,row["owner_id"])!=(row["owner_auth_version"],row["membership_version"],row["configuration_version"]):
                    return
                if conn.execute("""SELECT 1 FROM lite_system_health_maintenance_admissions a
                    WHERE status IN ('queued','executing','uncertain') AND NOT EXISTS
                    (SELECT 1 FROM lite_system_health_maintenance_resolutions r WHERE r.command_id=a.command_id) LIMIT 1""").fetchone():
                    return
            snapshots=model._snapshots()
            storage=snapshots.get("system.storage_pressure",{})
            sqlite=snapshots.get("system.sqlite_health",{})
            power=host.snapshot()
            if (model._freshness(storage)!="current" or storage.get("status")!="normal"
                or model._freshness(sqlite)!="current" or sqlite.get("status")!="healthy" or sqlite.get("quick_check")!="ok"
                or health.freshness(power.get("observed_at"))!="current" or power.get("effective_resource_mode")!="balanced"
                or power.get("automatic_pressure") or safety.maintenance_state().get("active") or safety.active_security_scan()):
                return
            policy_state=health._read("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1")
            if not policy_state or policy_state[0]["active_revision_id"]!=row["policy_revision"] or policy_state[0]["known_good_revision_id"]!=row["policy_revision"]:
                return
            context={"actor":{"type":"service","identity_id":"system-health-scheduler"},
                     "session":{"authenticated":True,"auth_method":"internal_worker"}}
            decision=opa.evaluate_authorization(auth_context=context,action_id=ACTION,
                target_type="system_health_projection",target_id=DOMAIN,target_revision=str(row["revision"]),
                target={"operation_id":OP,"adapter_enabled":True,"risk_class":"A","owner_policy_current":True,
                        "evidence_fresh":True})
            if decision["policy_revision"]!=row["policy_revision"] or not _gate():
                return
            if safety.maintenance_state().get("active") or safety.active_security_scan():
                return
            from . import lite_lifecycle_capability_activation as activation
            attempt_id = uuid.uuid4().hex
            claim = activation.claim(attempt_id)
            with connection() as conn:
                with begin_immediate(conn):
                    if conn.execute("SELECT 1 FROM lite_system_health_maintenance_admissions WHERE status IN ('queued','executing') LIMIT 1").fetchone():
                        return
                    current=conn.execute("SELECT * FROM lite_system_health_automation_policy WHERE singleton_id=1").fetchone()
                    if (not current or dict(current)!=row
                            or _owner_versions(conn,row["owner_id"])!=(row["owner_auth_version"],row["membership_version"],row["configuration_version"])
                            or not _gate()):
                        return
                    requested_at = health._now()
                    conn.execute("INSERT INTO lite_system_health_automation_attempts VALUES(?,?,?,'pending',?,NULL,?)",
                        (attempt_id,row["revision"],OP,requested_at,decision["decision_id"]))
                    conn.execute("""DELETE FROM lite_system_health_automation_attempts WHERE status!='pending'
                        AND attempt_id NOT IN (SELECT attempt_id FROM lite_system_health_automation_attempts ORDER BY requested_at DESC LIMIT 200)""")
            # Do not dispatch work that was admitted just before an emergency
            # disable or activation-fence change became visible.
            if not _gate():
                return
            prepared.mark_dirty(DOMAIN,reason=_trigger_reason(attempt_id))
    except (BlockingIOError,opa.PolicyDecisionError):
        return
