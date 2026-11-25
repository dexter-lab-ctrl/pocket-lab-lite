"""Fixed maintenance operations via existing NATS domain command owner.

Admission rows bind an authenticated Owner, current policy and exact preview.
Never execute from an HTTP request or replay an uncertain owner execution.
"""
from __future__ import annotations

import hashlib
import fcntl
from contextlib import contextmanager
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import deps
from ..db.connection import connection, begin_immediate
from . import lite_infrastructure_authority as authority
from . import lite_system_health as health
from . import lite_security_maintenance as maintenance
from . import lite_policy_opa as opa
from . import lite_infrastructure_operations as ops

OPERATIONS = ops.MAINTENANCE_OPERATIONS
SUBJECT = "pocketlab.commands.lite.system_health.maintenance"
ACTION = "system_health.maintenance"


def enabled(operation: str) -> bool:
    return ops.maintenance_enabled(operation)


def _public(row: dict) -> dict:
    try:
        evidence = json.loads(row.get("evidence_json") or "{}")
    except (ValueError,TypeError):
        evidence = {}
    evidence.pop("service_evidence_id",None)
    return {key: row.get(key) for key in ("command_id","operation_id","preview_id","status","requested_at","expires_at","completed_at")} | {"evidence": evidence, "resolution": row.get("disposition"), "sanitized": True}


def history() -> list[dict]:
    return [_public(row) for row in health._read("SELECT a.*,r.disposition FROM lite_system_health_maintenance_admissions a LEFT JOIN lite_system_health_maintenance_resolutions r USING(command_id) ORDER BY requested_at DESC,command_id DESC LIMIT 20")]


def _expires(seconds: int) -> str:
    return (datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat(timespec="seconds").replace("+00:00","Z")


def _policy(context: dict, operation: str, target: str, revision: str) -> dict:
    return opa.evaluate_authorization(auth_context=context,action_id=ACTION,target_type="system_health_maintenance",
        target_id=target,target_revision=revision,
        target={"operation_id":operation,"adapter_enabled":enabled(operation),"confirmed":True},
        request_context={"confirmation_present":True,"idempotency_key_present":True})


def _prepared_guard(operation: str) -> bool:
    from . import lite_infrastructure_read_model as model
    snapshots = model._snapshots()
    database = snapshots.get("system.sqlite_health",{})
    storage = snapshots.get("system.storage_pressure",{})
    return bool(enabled(operation) and model._freshness(database)=="current"
                and database.get("quick_check")=="ok" and database.get("status")=="healthy"
                and model._freshness(storage)=="current" and storage.get("writeability")=="writable"
                and storage.get("status") in {"normal","watch","elevated"})


def admit(context: dict, operation: str, preview_id: str, idempotency_key: str, confirm: bool) -> tuple[dict,bool]:
    if not confirm or operation not in OPERATIONS:
        raise ValueError("confirmation_or_operation_invalid")
    previews={"storage.evidence.retention":"storage.evidence.preview","storage.logs.cleanup":"storage.logs.preview","storage.temp.cleanup":"storage.temp.preview"}
    if operation in previews and not preview_id:
        raise ValueError("preview_required")
    if operation not in previews and preview_id:
        raise ValueError("unexpected_preview")
    digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    with connection() as conn:
        actor = authority.require_owner(conn,context)
        old = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE idempotency_digest=?",(digest,)).fetchone()
        if old:
            if old["actor_id"]!=actor or old["operation_id"]!=operation or old["preview_id"]!=preview_id:
                raise ValueError("idempotency_conflict")
            return _public(dict(old)),False
    if not _prepared_guard(operation):
        raise ValueError("maintenance_not_eligible")
    command_id = uuid.uuid4().hex
    revision = preview_id or command_id
    decision = _policy(context,operation,command_id,revision)
    with connection() as conn:
        with begin_immediate(conn):
            actor = authority.require_owner(conn,context)
            old = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE idempotency_digest=?", (digest,)).fetchone()
            if old:
                if old["actor_id"] != actor or old["operation_id"] != operation or old["preview_id"] != preview_id:
                    raise ValueError("idempotency_conflict")
                return _public(dict(old)), False
            # Expire only not-yet-executed admissions. Unknown owner outcomes
            # remain uncertain and are not automatically retried.
            conn.execute("UPDATE lite_system_health_maintenance_admissions SET status='expired',completed_at=? WHERE status='queued' AND expires_at<=?",(health._now(),health._now()))
            if conn.execute("SELECT 1 FROM lite_system_health_maintenance_admissions a WHERE status IN ('queued','executing','uncertain') AND NOT EXISTS (SELECT 1 FROM lite_system_health_maintenance_resolutions r WHERE r.command_id=a.command_id) LIMIT 1").fetchone():
                raise ValueError("maintenance_single_flight")
            if conn.execute("SELECT 1 FROM lite_system_health_automation_attempts WHERE status='pending' LIMIT 1").fetchone():
                raise ValueError("automatic_reconciliation_pending")
            candidate_json = "[]"
            if preview_id:
                preview = conn.execute("""SELECT * FROM lite_system_health_maintenance_admissions
                    WHERE command_id=? AND operation_id=? AND status='verified' AND actor_id=? AND expires_at>?""",
                    (preview_id,previews[operation],actor,health._now())).fetchone()
                if not preview or not json.loads(preview["candidate_json"]):
                    raise ValueError("preview_expired_or_empty")
                if conn.execute("SELECT 1 FROM lite_system_health_maintenance_admissions WHERE preview_id=? AND status IN ('queued','executing','verified','uncertain')",(preview_id,)).fetchone():
                    raise ValueError("preview_already_used")
                candidate_json = preview["candidate_json"]
            elif operation=="recovery.database.rehearse":
                backup=conn.execute("SELECT backup_id,sha256 FROM security_database_backups WHERE status='verified' ORDER BY created_at DESC,backup_id DESC LIMIT 1").fetchone()
                if not backup:
                    raise ValueError("verified_backup_required")
                candidate_json=json.dumps([dict(backup)])
            elif operation=="runtime.configuration.restore":
                from . import lite_infrastructure_configuration as configuration
                candidate_json=json.dumps([configuration.binding()])
            elif operation in {"runtime.telemetry.recover","runtime.server_agent.recover"}:
                from . import lite_infrastructure_service_control as service_control
                candidate_json=json.dumps([service_control.binding(operation)])
            conn.execute("""INSERT INTO lite_system_health_maintenance_admissions
                (command_id,operation_id,actor_id,session_id,policy_revision,decision_id,idempotency_digest,preview_id,status,requested_at,expires_at,candidate_json)
                VALUES(?,?,?,?,?,?,?,?,'queued',?,?,?)""",
                (command_id,operation,actor,context["session"]["session_id"],decision["policy_revision"],decision["decision_id"],digest,preview_id,health._now(),_expires(120),candidate_json))
            row = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=?",(command_id,)).fetchone()
            conn.execute("""DELETE FROM lite_system_health_maintenance_admissions WHERE status IN ('verified','blocked','expired','cancelled')
                AND expires_at<=? AND command_id NOT IN (SELECT command_id FROM lite_system_health_maintenance_admissions ORDER BY requested_at DESC LIMIT 500)""",(health._now(),))
    return _public(dict(row)),True


def _finish(command_id: str,status: str,evidence: dict,candidates: list[str] | None=None) -> dict:
    with connection() as conn:
        with begin_immediate(conn):
            row = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=?",(command_id,)).fetchone()
            if not row:
                raise ValueError("admission_missing")
            if row["status"]=="executing":
                conn.execute("""UPDATE lite_system_health_maintenance_admissions SET status=?,completed_at=?,evidence_json=?,
                    candidate_json=?,expires_at=? WHERE command_id=? AND status='executing'""",
                    (status,health._now(),json.dumps(evidence,separators=(",",":")),json.dumps(candidates or []),_expires(300) if row["operation_id"] in {"storage.evidence.preview","storage.logs.preview","storage.temp.preview"} and status=="verified" else row["expires_at"],command_id))
            row = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=?",(command_id,)).fetchone()
    return _public(dict(row))


@contextmanager
def _owner_lock():
    # Same private state directory on Termux/Linux; no /tmp and no blocking
    # worker on another owner. OS releases the fence on process death.
    path = deps.settings().state_dir / "system-health-maintenance.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def execute(command_id: str) -> dict:
    with _owner_lock():
        return _execute(command_id)


def _execute(command_id: str) -> dict:
    """Called only from domain_commands handler in the existing worker."""
    with connection() as conn:
        with begin_immediate(conn):
            row = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=?",(command_id,)).fetchone()
            if not row:
                raise ValueError("admission_missing")
            if row["status"]!="queued":
                return _public(dict(row))
            if not authority._future(row["expires_at"]):
                conn.execute("UPDATE lite_system_health_maintenance_admissions SET status='expired',completed_at=? WHERE command_id=?",(health._now(),command_id))
                return {"status":"expired","sanitized":True}
            conn.execute("UPDATE lite_system_health_maintenance_admissions SET status='executing' WHERE command_id=?",(command_id,))
            request = dict(row)
    operation = request["operation_id"]
    try:
        with connection() as conn:
            auth = authority._human_authority(conn,request["actor_id"],request["session_id"])
        if not auth or not auth["owner_authority"] or not _prepared_guard(operation):
            return _finish(command_id,"blocked",{"reason":"execution_authority_or_preflight_changed"})
        context = {"actor":{"identity_id":request["actor_id"],"type":"human"},"session":{"authenticated":True},"authorization":auth}
        decision = _policy(context,operation,command_id,request["preview_id"] or command_id)
        if decision["policy_revision"]!=request["policy_revision"]:
            return _finish(command_id,"blocked",{"reason":"policy_revision_changed"})
        with connection() as conn:
            current = authority._human_authority(conn,request["actor_id"],request["session_id"])
            if request["preview_id"]:
                preview = conn.execute("""SELECT candidate_json FROM lite_system_health_maintenance_admissions
                    WHERE command_id=? AND actor_id=? AND operation_id=? AND status='verified' AND expires_at>?""",
                    (request["preview_id"],request["actor_id"],{"storage.evidence.retention":"storage.evidence.preview","storage.logs.cleanup":"storage.logs.preview","storage.temp.cleanup":"storage.temp.preview"}[operation],health._now())).fetchone()
                if not preview or preview["candidate_json"] != request["candidate_json"]:
                    current = None
        if not current or current != auth or not enabled(operation) or maintenance.maintenance_state().get("active") or maintenance.active_security_scan():
            return _finish(command_id,"blocked",{"reason":"maintenance_conflict_or_authority_changed"})
    except Exception:
        return _finish(command_id,"blocked",{"reason":"authorization_or_readiness_unavailable"})
    try:
        if operation=="runtime.configuration.restore":
            with connection() as conn:
                with begin_immediate(conn):
                    conn.execute("UPDATE lite_system_health_maintenance_admissions SET evidence_json=?,expires_at=? WHERE command_id=? AND status='executing'",
                        (json.dumps({"reconciler_requested":True}),_expires(180),command_id))
            return {"status":"executing","command_id":command_id,"sanitized":True}
        if operation in {"runtime.telemetry.recover","runtime.server_agent.recover"}:
            with connection() as conn:
                with begin_immediate(conn):
                    conn.execute("UPDATE lite_system_health_maintenance_admissions SET evidence_json=?,expires_at=? WHERE command_id=? AND status='executing'",
                        (json.dumps({"supervisor_requested":True}),_expires(180),command_id))
            return {"status":"executing","command_id":command_id,"sanitized":True}
        if operation in {"storage.logs.preview","storage.temp.preview","storage.logs.cleanup","storage.temp.cleanup"}:
            from . import lite_infrastructure_cleanup as cleanup
            scope=operation.split(".")[1]
            if operation.endswith(".preview"):
                candidates,evidence=cleanup.preview(scope)
                return _finish(command_id,"verified",evidence,candidates)
            result=cleanup.apply(scope,json.loads(request["candidate_json"]))
            return _finish(command_id,"verified",result)
        if operation=="recovery.database.rehearse":
            from . import lite_database_recovery
            binding=json.loads(request["candidate_json"])[0]
            result=lite_database_recovery.rehearse_database_backup(binding["backup_id"],binding["sha256"])
            return _finish(command_id,"verified" if result["verified"] else "uncertain",result,[binding])
        if operation=="projection.reconcile":
            from . import lite_phase3c_projections
            # Record the dispatch boundary before requesting existing owner work.
            with connection() as conn:
                with begin_immediate(conn):
                    conn.execute("UPDATE lite_system_health_maintenance_admissions SET evidence_json=? WHERE command_id=? AND status='executing'",
                        (json.dumps({"dispatch_at":health._now(),"domain":"system.activity_history"}),command_id))
            lite_phase3c_projections.mark_dirty("system.activity_history",reason="reconcile_system_health")
            return {"status":"executing","command_id":command_id,"sanitized":True}
        if operation=="storage.evidence.preview":
            with connection() as conn:
                candidates = maintenance.reviewed_retention_plan(conn)
            return _finish(command_id,"verified",{"candidate_count":len(candidates),"estimated_bytes":None,"evidence_files_deleted":0},candidates)
        if operation=="storage.evidence.retention":
            result = maintenance.apply_reviewed_retention(operation_id=command_id,candidates=json.loads(request["candidate_json"]))
            return _finish(command_id,"verified" if result["verified"] else "uncertain",result)
        result = maintenance.run_wal_checkpoint(mode="PASSIVE",operation_id=command_id)
        evidence = {key:result.get(key) for key in ("checkpoint_busy","checkpoint_log_frames","checkpointed_frames")}
        verified = (result.get("quick_check")=="ok" and evidence["checkpoint_busy"]==0 and
                    isinstance(evidence["checkpointed_frames"],int) and isinstance(evidence["checkpoint_log_frames"],int)
                    and evidence["checkpointed_frames"]>=evidence["checkpoint_log_frames"]>=0)
        return _finish(command_id,"verified" if verified else "uncertain",evidence|{"quick_check_ok":result.get("quick_check")=="ok"})
    except ValueError as exc:
        if str(exc) in {"retention_preview_changed", "reviewed_candidates_required"}:
            return _finish(command_id,"blocked",{"reason":"reviewed_plan_changed"})
        return _finish(command_id,"uncertain",{"reason":"owner_outcome_not_verified"})
    except Exception:
        return _finish(command_id,"uncertain",{"reason":"owner_outcome_not_verified"})


def reconcile() -> None:
    # Never expire a live owner while it still holds the execution fence.
    try:
        with _owner_lock():
            _reconcile()
    except BlockingIOError:
        return


def _reconcile() -> None:
    # Existing watchdog invokes this at bounded cadence. No replay.
    service_rows=health._read("SELECT command_id,evidence_json FROM lite_system_health_maintenance_admissions WHERE status='executing' AND operation_id IN ('runtime.telemetry.recover','runtime.server_agent.recover') LIMIT 1")
    for row in service_rows:
        key=json.loads(row["evidence_json"]).get("service_evidence_id")
        if key:
            proof=health._read("SELECT verification_state FROM lite_system_health_service_owner_evidence WHERE evidence_id=?",(key,))
            if proof and proof[0]["verification_state"] in {"verified","unavailable"}:
                _finish(row["command_id"],"verified" if proof[0]["verification_state"]=="verified" else "uncertain",{"independent_service_readiness":proof[0]["verification_state"]})
    rows = health._read("SELECT command_id,evidence_json FROM lite_system_health_maintenance_admissions WHERE status='executing' AND operation_id='projection.reconcile' LIMIT 1")
    for row in rows:
        evidence=json.loads(row["evidence_json"])
        completed=health._read("SELECT last_completed_at,last_error_type FROM projection_refresh_state WHERE domain='system.activity_history'")
        if evidence.get("dispatch_at") and completed and not completed[0]["last_error_type"] and str(completed[0]["last_completed_at"] or "")>evidence["dispatch_at"]:
            _finish(row["command_id"],"verified",{"fresh_projection_completed":True})
    rows = health._read("SELECT command_id,status FROM lite_system_health_maintenance_admissions WHERE status IN ('queued','executing') AND expires_at<=? LIMIT 20",(health._now(),))
    if not rows:
        return
    with connection() as conn:
        with begin_immediate(conn):
            for row in rows:
                conn.execute("""UPDATE lite_system_health_maintenance_admissions SET status=?,completed_at=?
                    WHERE command_id=? AND status=? AND expires_at<=?""",
                    ("uncertain" if row["status"]=="executing" else "expired",health._now(),row["command_id"],row["status"],health._now()))


def resolve_uncertain(context: dict, command_id: str, *, confirm: bool) -> dict:
    """Explicit closure after owner review, never an assertion of success."""
    if not confirm:
        raise ValueError("confirmation_required")
    with _owner_lock():
        with connection() as conn:
            actor = authority.require_owner(conn, context)
            row = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=?", (command_id,)).fetchone()
            if not row:
                raise LookupError("request_not_found")
            if row["status"] != "uncertain":
                raise ValueError("not_uncertain")
            existing = conn.execute("SELECT disposition FROM lite_system_health_maintenance_resolutions WHERE command_id=?", (command_id,)).fetchone()
            if existing:
                return _public(dict(row) | dict(existing))
        if maintenance.maintenance_state().get("active") or maintenance.active_security_scan():
            raise ValueError("maintenance_conflict")
        decision = opa.evaluate_authorization(auth_context=context, action_id=ACTION,
            target_type="system_health_maintenance", target_id=command_id,
            target_revision=command_id + ":uncertain", target={"operation_id":"maintenance.uncertain.resolve",
                "confirmed":True, "adapter_enabled":True},
            request_context={"confirmation_present":True})
        with connection() as conn:
            with begin_immediate(conn):
                actor = authority.require_owner(conn, context)
                # Acknowledgement cannot interrupt a running owner. Never
                # update the original execution outcome or reuse its preview.
                row = conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=? AND status='uncertain'", (command_id,)).fetchone()
                if not row:
                    raise ValueError("state_changed")
                conn.execute("""INSERT INTO lite_system_health_maintenance_resolutions
                    VALUES(?,?,?,?,?,'closed_unverified')""",
                    (command_id,actor,decision["decision_id"],decision["policy_revision"],health._now()))
                return _public(dict(row) | {"disposition":"closed_unverified"})


def cancel_queued(context: dict, command_id: str) -> dict:
    with connection() as conn:
        with begin_immediate(conn):
            actor=authority.require_owner(conn,context)
            row=conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=?", (command_id,)).fetchone()
            if not row:
                raise LookupError("request_not_found")
            if row["status"]=="cancelled":
                return _public(dict(row))
            if row["status"]!="queued":
                raise ValueError("execution_already_started")
            conn.execute("UPDATE lite_system_health_maintenance_admissions SET status='cancelled',completed_at=? WHERE command_id=? AND status='queued'",(health._now(),command_id))
            authority.audit(conn,actor,"recovery_cancelled",command_id)
            return _public(dict(conn.execute("SELECT * FROM lite_system_health_maintenance_admissions WHERE command_id=?",(command_id,)).fetchone()))
