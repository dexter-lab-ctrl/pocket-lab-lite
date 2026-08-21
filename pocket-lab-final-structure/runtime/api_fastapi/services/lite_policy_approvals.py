"""Server-owned P3.1 continuations: independent approvals and narrow exceptions."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import lite_enterprise_identity

APPROVAL_PURPOSE = "policy.approval.device.remove"
APPROVER_ROLES = frozenset({"Owner", "Admin"})
REQUESTER_ROLES = frozenset({"Owner", "Admin", "Operator"})
EXCEPTION_ROLES = frozenset({"Owner", "Admin"})


class ApprovalError(RuntimeError):
    def __init__(self, reason_code: str, message: str, status_code: int = 403):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _actor_context(auth_context: dict[str, Any], *, roles: frozenset[str] | None = None) -> tuple[dict[str, Any], str, str]:
    context = lite_enterprise_identity.enrich_auth_context(auth_context)
    actor = context.get("actor") or {}
    authorization = context.get("authorization") or {}
    actor_id = str(actor.get("identity_id") or "").strip()
    role = str(authorization.get("role") or "")
    if actor.get("type") != "human" or not actor_id:
        raise ApprovalError("human_session_required", "A signed-in human session is required.")
    if not authorization.get("enterprise_enabled"):
        raise ApprovalError("enterprise_mode_required", "This continuation is available only in Enterprise Mode.", 404)
    if not authorization.get("membership_active"):
        raise ApprovalError("enterprise_membership_required", "An active Enterprise membership is required.")
    if roles is not None and role not in roles:
        raise ApprovalError("enterprise_rules_role_required", "Your current Enterprise role is not authorized.")
    return context, actor_id, role


def _event(tx: Any, *, kind: str, subject_id: str, actor_human_id: str | None, event_type: str, reason_code: str, summary: str, correlation_id: str) -> None:
    tx.execute(
        """INSERT INTO policy_continuation_events(occurred_at,kind,subject_id,actor_human_id,event_type,reason_code,summary,correlation_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (_iso(), kind, subject_id, actor_human_id, event_type[:80], reason_code[:80], summary[:240], correlation_id[:80]),
    )


def _public_approval(row: Any) -> dict[str, Any]:
    item = dict(row)
    for field in ("initiating_human_id", "approved_by_human_id", "rejected_by_human_id", "cancelled_by_human_id"):
        item.pop(field, None)
    try:
        item["required_approver_roles"] = json.loads(item.pop("required_approver_roles_json", "[]"))
    except (TypeError, ValueError):
        item["required_approver_roles"] = []
    return item


def _public_exception(row: Any) -> dict[str, Any]:
    item = dict(row)
    for field in ("human_id", "created_by_human_id", "revoked_by_human_id"):
        item.pop(field, None)
    return item


def _approved_assurance(context: dict[str, Any]) -> bool:
    now = _iso()
    return any(isinstance(item, dict) and item.get("purpose") == APPROVAL_PURPOSE and str(item.get("expires_at") or "") > now for item in ((context.get("session") or {}).get("assurance") or []))


def create_from_decision(*, decision_id: str, initiating_role: str) -> dict[str, Any]:
    """Persist exactly one continuation for a recorded real OPA decision."""
    apply_migrations()
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            decision = tx.execute("SELECT * FROM policy_decisions WHERE decision_id=?", (str(decision_id)[:120],)).fetchone()
            if not decision or decision["reason_code"] != "approval_required" or decision["action_id"] != "device.remove" or int(decision["allow"]):
                raise ApprovalError("approval_provenance_invalid", "Approval requires a real approval-required device-removal decision.", 409)
            if initiating_role not in REQUESTER_ROLES:
                raise ApprovalError("approval_requester_role_invalid", "The originating Enterprise role cannot request this approval.", 403)
            existing = tx.execute("SELECT * FROM policy_approvals WHERE originating_decision_id=?", (decision["decision_id"],)).fetchone()
            if existing:
                return {"approval": _public_approval(existing), "created": False}
            approval_id = "apr-" + uuid.uuid4().hex
            tx.execute(
                """INSERT INTO policy_approvals(approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,
                   initiating_human_id,initiating_role,required_approver_roles_json,required_assurance,policy_revision,status,created_at,expires_at,reason_code,evidence_ref)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (approval_id, decision["decision_id"], decision["correlation_id"], "device.remove", "device", decision["target_id"],
                 decision["actor_id"], initiating_role, json.dumps(sorted(APPROVER_ROLES), separators=(",", ":")), APPROVAL_PURPOSE,
                 decision["policy_revision"], "pending", _iso(now), _iso(now + timedelta(minutes=15)), "approval_required", f"policy:{decision['decision_id']}"),
            )
            _event(tx, kind="approval", subject_id=approval_id, actor_human_id=decision["actor_id"], event_type="approval.requested", reason_code="approval_required", summary="Independent approval requested for a device removal.", correlation_id=decision["correlation_id"])
            row = tx.execute("SELECT * FROM policy_approvals WHERE approval_id=?", (approval_id,)).fetchone()
    return {"approval": _public_approval(row), "created": True}


def list_approvals(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations()
    _, actor_id, role = _actor_context(auth_context)
    with connection() as conn:
        if role in APPROVER_ROLES | {"Auditor"}:
            rows = conn.execute("SELECT * FROM policy_approvals ORDER BY created_at DESC LIMIT 100").fetchall()
        else:
            rows = conn.execute("SELECT * FROM policy_approvals WHERE initiating_human_id=? ORDER BY created_at DESC LIMIT 100", (actor_id,)).fetchall()
    return {"approvals": [_public_approval(row) for row in rows]}


def read_approval(*, auth_context: dict[str, Any], approval_id: str) -> dict[str, Any]:
    apply_migrations()
    _, actor_id, role = _actor_context(auth_context)
    with connection() as conn:
        row = conn.execute("SELECT * FROM policy_approvals WHERE approval_id=?", (str(approval_id)[:120],)).fetchone()
        if not row:
            raise ApprovalError("approval_not_found", "That approval is unavailable.", 404)
        if actor_id != row["initiating_human_id"] and role not in APPROVER_ROLES | {"Auditor"}:
            raise ApprovalError("approval_read_forbidden", "That approval is not available to your current role.")
        events = conn.execute("SELECT occurred_at,event_type,reason_code,summary FROM policy_continuation_events WHERE kind='approval' AND subject_id=? ORDER BY event_id ASC LIMIT 40", (row["approval_id"],)).fetchall()
    return {"approval": _public_approval(row), "history": [dict(event) for event in events]}


def transition(*, auth_context: dict[str, Any], approval_id: str, action: str) -> dict[str, Any]:
    apply_migrations()
    context, actor_id, role = _actor_context(auth_context)
    requested_action = str(action or "").strip()
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT * FROM policy_approvals WHERE approval_id=?", (str(approval_id)[:120],)).fetchone()
            if not row:
                raise ApprovalError("approval_not_found", "That approval is unavailable.", 404)
            if row["status"] != "pending" or row["expires_at"] <= _iso(now):
                tx.execute("UPDATE policy_approvals SET status='expired' WHERE approval_id=? AND status='pending'", (row["approval_id"],))
                raise ApprovalError("approval_unusable", "That approval is no longer pending.", 409)
            if requested_action == "approve":
                if role not in APPROVER_ROLES:
                    raise ApprovalError("approval_approver_role_required", "Only an active Enterprise Owner or Admin can approve this request.")
                if actor_id == row["initiating_human_id"]:
                    raise ApprovalError("approval_self_forbidden", "Independent approval is required.", 409)
                if not _approved_assurance(context):
                    raise ApprovalError("approval_step_up_required", "Confirm this approval with your passkey first.", 428)
                tx.execute("UPDATE policy_approvals SET status='approved',approved_at=?,approved_by_human_id=? WHERE approval_id=? AND status='pending'", (_iso(now), actor_id, row["approval_id"]))
                event_type, message = "approval.approved", "Approved — retry the original action to continue."
            elif requested_action == "reject":
                if role not in APPROVER_ROLES:
                    raise ApprovalError("approval_approver_role_required", "Only an active Enterprise Owner or Admin can reject this request.")
                tx.execute("UPDATE policy_approvals SET status='rejected',rejected_at=?,rejected_by_human_id=? WHERE approval_id=? AND status='pending'", (_iso(now), actor_id, row["approval_id"]))
                event_type, message = "approval.rejected", "Approval rejected."
            elif requested_action == "cancel":
                if actor_id != row["initiating_human_id"]:
                    raise ApprovalError("approval_cancel_forbidden", "Only the initiating user may cancel this approval.")
                tx.execute("UPDATE policy_approvals SET status='cancelled',cancelled_at=?,cancelled_by_human_id=? WHERE approval_id=? AND status='pending'", (_iso(now), actor_id, row["approval_id"]))
                event_type, message = "approval.cancelled", "Approval cancelled."
            else:
                raise ApprovalError("approval_transition_invalid", "That approval action is invalid.", 422)
            _event(tx, kind="approval", subject_id=row["approval_id"], actor_human_id=actor_id, event_type=event_type, reason_code=event_type.replace(".", "_"), summary=message, correlation_id=row["correlation_id"])
            updated = tx.execute("SELECT * FROM policy_approvals WHERE approval_id=?", (row["approval_id"],)).fetchone()
    return {"approval": _public_approval(updated), "message": message}


def matching_approved(*, initiating_human_id: str, action_id: str, target_type: str, target_id: str, policy_revision: str) -> str | None:
    """Return only a server-derived, currently eligible continuation id."""
    apply_migrations()
    now = _iso()
    with connection() as conn:
        row = conn.execute(
            """SELECT a.approval_id FROM policy_approvals a JOIN enterprise_memberships m ON m.human_id=a.approved_by_human_id
               JOIN human_identities h ON h.human_id=a.approved_by_human_id
               WHERE a.initiating_human_id=? AND a.action_id=? AND a.target_type=? AND a.target_id=? AND a.policy_revision=?
                 AND a.status='approved' AND a.expires_at>? AND a.approved_by_human_id<>a.initiating_human_id
                 AND m.status='active' AND m.role IN ('Owner','Admin') AND h.status='active' ORDER BY a.approved_at DESC LIMIT 1""",
            (initiating_human_id[:120], action_id[:120], target_type[:80], target_id[:160], policy_revision[:80], now),
        ).fetchone()
    return str(row["approval_id"]) if row else None


def consume_matching(*, auth_context: dict[str, Any], approval_id: str, action_id: str, target_type: str, target_id: str, policy_revision: str) -> dict[str, Any]:
    """Atomically consume the OPA-matched continuation immediately before execution."""
    apply_migrations()
    _, actor_id, role = _actor_context(auth_context, roles=REQUESTER_ROLES)
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute(
                """SELECT a.* FROM policy_approvals a JOIN enterprise_memberships m ON m.human_id=a.approved_by_human_id
                   JOIN human_identities h ON h.human_id=a.approved_by_human_id
                   WHERE a.approval_id=? AND a.initiating_human_id=? AND a.action_id=? AND a.target_type=? AND a.target_id=? AND a.policy_revision=?
                     AND a.status='approved' AND a.expires_at>? AND a.approved_by_human_id<>a.initiating_human_id
                     AND m.status='active' AND m.role IN ('Owner','Admin') AND h.status='active'""",
                (approval_id[:120], actor_id, action_id[:120], target_type[:80], target_id[:160], policy_revision[:80], now),
            ).fetchone()
            if not row:
                raise ApprovalError("approval_continuation_unavailable", "The independent approval is no longer valid; request a new approval.", 409)
            changed = tx.execute("UPDATE policy_approvals SET status='consumed',consumed_at=? WHERE approval_id=? AND status='approved'", (now, row["approval_id"])).rowcount
            if changed != 1:
                raise ApprovalError("approval_continuation_unavailable", "The independent approval was already used.", 409)
            _event(tx, kind="approval", subject_id=row["approval_id"], actor_human_id=actor_id, event_type="approval.consumed", reason_code="approval_consumed", summary="Approved device removal continuation consumed for one execution attempt.", correlation_id=row["correlation_id"])
    return {"approval_id": approval_id, "consumed": True, "initiating_role": role}


def matching_exception(*, human_id: str, app_id: str, device_id: str, policy_revision: str) -> str | None:
    """Resolve a still-active exact exception; callers pass no browser grant flag."""
    apply_migrations()
    with connection() as conn:
        row = conn.execute(
            """SELECT exception_id FROM policy_temporary_exceptions
               WHERE action_id='catalog.install' AND human_id=? AND app_id=? AND device_id=? AND policy_revision=?
                 AND status='active' AND expires_at>? ORDER BY created_at DESC LIMIT 1""",
            (human_id[:120], app_id[:160], device_id[:160], policy_revision[:80], _iso()),
        ).fetchone()
    return str(row["exception_id"]) if row else None


def _active_revision() -> str:
    from . import lite_policy_opa
    with connection() as conn:
        row = conn.execute("SELECT active_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    revision = str(row["active_revision_id"] or "") if row else ""
    revision = revision or lite_policy_opa._safe_revision()
    if not revision or revision == "unavailable":
        raise ApprovalError("policy_revision_unavailable", "A proved active Safety Rules revision is required.", 503)
    return revision[:80]


def create_exception(*, auth_context: dict[str, Any], app_id: str, device_id: str, human_id: str, reason: str, duration_minutes: int) -> dict[str, Any]:
    apply_migrations()
    _, actor_id, _ = _actor_context(auth_context, roles=EXCEPTION_ROLES)
    safe_app, safe_device, safe_human, safe_reason = str(app_id).strip()[:160], str(device_id).strip()[:160], str(human_id).strip()[:120], str(reason).strip()[:240]
    if not safe_app or not safe_device or not safe_human or not safe_reason or any(value in {"*", "all", "global"} for value in (safe_app.casefold(), safe_device.casefold(), safe_human.casefold())):
        raise ApprovalError("exception_scope_invalid", "An exact app, device, requesting identity, and bounded reason are required.", 422)
    if not 1 <= int(duration_minutes) <= 60:
        raise ApprovalError("exception_expiry_invalid", "Temporary exceptions must expire within 60 minutes.", 422)
    revision, now = _active_revision(), _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            if not tx.execute("SELECT human_id FROM human_identities WHERE human_id=? AND status='active'", (safe_human,)).fetchone():
                raise ApprovalError("exception_identity_unknown", "The requesting identity is not active.", 404)
            exception_id = "exc-" + uuid.uuid4().hex
            tx.execute("INSERT INTO policy_temporary_exceptions(exception_id,action_id,app_id,device_id,human_id,policy_revision,reason,created_by_human_id,status,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (exception_id, "catalog.install", safe_app, safe_device, safe_human, revision, safe_reason, actor_id, "active", _iso(now), _iso(now + timedelta(minutes=int(duration_minutes)))))
            _event(tx, kind="exception", subject_id=exception_id, actor_human_id=actor_id, event_type="exception.created", reason_code="temporary_exception_created", summary="Narrow temporary catalog-install exception created.", correlation_id=exception_id)
            row = tx.execute("SELECT * FROM policy_temporary_exceptions WHERE exception_id=?", (exception_id,)).fetchone()
    return {"exception": _public_exception(row)}


def list_exceptions(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations()
    _actor_context(auth_context, roles=EXCEPTION_ROLES | {"Auditor"})
    with connection() as conn:
        conn.execute("UPDATE policy_temporary_exceptions SET status='expired' WHERE status='active' AND expires_at<=?", (_iso(),))
        rows = conn.execute("SELECT * FROM policy_temporary_exceptions ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"exceptions": [_public_exception(row) for row in rows]}


def revoke_exception(*, auth_context: dict[str, Any], exception_id: str) -> dict[str, Any]:
    apply_migrations()
    _, actor_id, _ = _actor_context(auth_context, roles=EXCEPTION_ROLES)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT * FROM policy_temporary_exceptions WHERE exception_id=?", (str(exception_id)[:120],)).fetchone()
            if not row:
                raise ApprovalError("exception_not_found", "That temporary exception is unavailable.", 404)
            if row["status"] != "active":
                raise ApprovalError("exception_unusable", "That temporary exception is no longer active.", 409)
            tx.execute("UPDATE policy_temporary_exceptions SET status='revoked',revoked_at=?,revoked_by_human_id=? WHERE exception_id=? AND status='active'", (_iso(), actor_id, row["exception_id"]))
            _event(tx, kind="exception", subject_id=row["exception_id"], actor_human_id=actor_id, event_type="exception.revoked", reason_code="temporary_exception_revoked", summary="Temporary catalog-install exception revoked.", correlation_id=row["exception_id"])
            updated = tx.execute("SELECT * FROM policy_temporary_exceptions WHERE exception_id=?", (row["exception_id"],)).fetchone()
    return {"exception": _public_exception(updated)}
