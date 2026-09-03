from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations

ROLES = frozenset({"Owner", "Admin", "Operator", "Viewer", "Auditor"})
MEMBERSHIP_STATUSES = frozenset({"active", "removed"})
ROLE_CATALOG: dict[str, dict[str, str]] = {
    "Owner": {"label": "Owner", "summary": "Full Pocket Lab authority without peer approval. Root-level changes can still require passkey confirmation and never bypass hard safety guards."},
    "Admin": {"label": "Admin", "summary": "Broad delegated administration. Admins can manage normal operations and lower-privilege access; protected actions can require independent review."},
    "Operator": {"label": "Operator", "summary": "Day-to-day operational access with review for protected changes."},
    "Auditor": {"label": "Auditor", "summary": "Read-only governance, policy and evidence review."},
    "Viewer": {"label": "Viewer", "summary": "Read-only workspace access without administrative authority."},
}


class EnterpriseIdentityError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 403):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit(tx: sqlite3.Connection, *, human_id: str | None, event_type: str, reason_code: str, summary: str, correlation_id: str | None = None) -> None:
    tx.execute(
        """INSERT INTO identity_audit_events(occurred_at,human_id,session_id,event_type,reason_code,summary,correlation_id)
           VALUES (?,?,?,?,?,?,?)""",
        (_now(), human_id, None, event_type[:80], reason_code[:80], summary[:240], (correlation_id or uuid.uuid4().hex)[:80]),
    )


def _configuration(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM enterprise_configuration WHERE configuration_id=1").fetchone()
    return dict(row) if row else {"enabled": 0, "authorization_version": 1, "updated_at": None}


def _local_owner_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
    return str(row["human_id"]) if row else None


def local_owner_id() -> str | None:
    apply_migrations()
    with connection() as conn:
        return _local_owner_id(conn)


def _role(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate not in ROLES:
        raise EnterpriseIdentityError("enterprise_role_invalid", "Select a recognized Pocket Lab role.", status_code=422)
    return candidate


def _membership_status(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate not in MEMBERSHIP_STATUSES:
        raise EnterpriseIdentityError("enterprise_membership_status_invalid", "Select a recognized membership status.", status_code=422)
    return candidate


def _actor_id(auth_context: dict[str, Any]) -> str:
    actor = auth_context.get("actor") or {}
    if actor.get("type") != "human" or not actor.get("identity_id"):
        raise EnterpriseIdentityError("human_session_required", "A signed-in human session is required.")
    return str(actor["identity_id"])


def enrich_auth_context(auth_context: dict[str, Any]) -> dict[str, Any]:
    actor = dict(auth_context.get("actor") or {})
    if actor.get("type") != "human" or not actor.get("identity_id"):
        return auth_context
    try:
        with connection() as conn:
            configuration = _configuration(conn)
            enabled = bool(configuration.get("enabled"))
            membership = conn.execute(
                "SELECT role,status,authorization_version FROM enterprise_memberships WHERE human_id=?",
                (str(actor["identity_id"]),),
            ).fetchone()
            local_owner = _local_owner_id(conn)
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        return auth_context
    membership_data = dict(membership) if membership else None
    active_membership = bool(membership_data and membership_data["status"] == "active")
    resolved_role = membership_data["role"] if enabled and active_membership else ("Owner" if actor["identity_id"] == local_owner else None)
    result = dict(auth_context)
    result["authorization"] = {
        "enterprise_enabled": enabled,
        "role": resolved_role,
        "membership_active": active_membership if enabled else actor["identity_id"] == local_owner,
        "authorization_version": int(membership_data["authorization_version"]) if membership_data else 1,
        "identity_class": "enterprise_member" if enabled and active_membership else "local_owner",
        "owner_authority": resolved_role == "Owner",
    }
    return result


def _topology(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """SELECT m.role,COUNT(*) AS count FROM enterprise_memberships m
           JOIN human_identities h ON h.human_id=m.human_id
           WHERE m.status='active' AND h.status='active' GROUP BY m.role"""
    ).fetchall()
    counts = {role: 0 for role in ROLES}
    for row in rows:
        if row["role"] in counts:
            counts[str(row["role"])] = int(row["count"] or 0)
    invited = conn.execute("SELECT COUNT(*) AS count FROM human_identities WHERE status='invited'").fetchone()
    return {
        "owners": counts["Owner"],
        "admins": counts["Admin"],
        "operators": counts["Operator"],
        "auditors": counts["Auditor"],
        "viewers": counts["Viewer"],
        "invited": int(invited["count"] or 0) if invited else 0,
        "independent_approvers": counts["Owner"] + counts["Admin"],
    }


def enterprise_projection(auth_context: dict[str, Any] | None = None) -> dict[str, Any]:
    apply_migrations()
    with connection() as conn:
        configuration = _configuration(conn)
        enabled = bool(configuration.get("enabled"))
        actor_id = str(((auth_context or {}).get("actor") or {}).get("identity_id") or "")
        membership = conn.execute("SELECT role,status,authorization_version FROM enterprise_memberships WHERE human_id=?", (actor_id,)).fetchone() if actor_id else None
        topology = _topology(conn)
    member = dict(membership) if membership else {}
    return {
        "enabled": enabled,
        "authorization_version": int(configuration.get("authorization_version") or 1),
        "current_membership": {
            "role": member.get("role"),
            "active": bool(member and member.get("status") == "active"),
            "authorization_version": int(member.get("authorization_version") or 1),
        } if enabled else None,
        "roles": sorted(ROLES),
        "role_catalog": [{"id": role, **ROLE_CATALOG[role]} for role in ("Owner", "Admin", "Operator", "Auditor", "Viewer")],
        "topology": topology,
        "updated_at": configuration.get("updated_at"),
    }


def _require_enterprise_owner(tx: sqlite3.Connection, auth_context: dict[str, Any]) -> str:
    actor_id = _actor_id(auth_context)
    if not bool(_configuration(tx).get("enabled")):
        raise EnterpriseIdentityError("enterprise_mode_disabled", "Enterprise Mode is not enabled for this Pocket Lab.", status_code=404)
    membership = tx.execute("SELECT role,status FROM enterprise_memberships WHERE human_id=?", (actor_id,)).fetchone()
    human = tx.execute("SELECT status FROM human_identities WHERE human_id=?", (actor_id,)).fetchone()
    if not membership or not human or human["status"] != "active" or membership["status"] != "active" or membership["role"] != "Owner":
        raise EnterpriseIdentityError("enterprise_owner_required", "An active Enterprise Owner session is required.")
    return actor_id


def _manager(tx: sqlite3.Connection, auth_context: dict[str, Any]) -> tuple[str, str]:
    actor_id = _actor_id(auth_context)
    if not bool(_configuration(tx).get("enabled")):
        raise EnterpriseIdentityError("enterprise_mode_disabled", "Enterprise Mode is not enabled for this Pocket Lab.", status_code=404)
    membership = tx.execute("SELECT role,status FROM enterprise_memberships WHERE human_id=?", (actor_id,)).fetchone()
    human = tx.execute("SELECT status FROM human_identities WHERE human_id=?", (actor_id,)).fetchone()
    role = str(membership["role"] or "") if membership else ""
    if not membership or not human or human["status"] != "active" or membership["status"] != "active" or role not in {"Owner", "Admin"}:
        raise EnterpriseIdentityError("enterprise_people_role_required", "Owner or Admin access is required to manage people.")
    return actor_id, role


def _invalidate_authorization(tx: sqlite3.Connection, human_id: str, *, reason: str) -> None:
    now = _now()
    tx.execute("UPDATE human_identities SET auth_version=auth_version+1,updated_at=? WHERE human_id=?", (now, human_id))
    tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason=? WHERE human_id=? AND revoked_at IS NULL", (now, reason[:80], human_id))


def _invalidate_all_authorization(tx: sqlite3.Connection, *, reason: str) -> None:
    now = _now()
    tx.execute("UPDATE human_identities SET auth_version=auth_version+1,updated_at=? WHERE status='active'", (now,))
    tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason=? WHERE revoked_at IS NULL", (now, reason[:80]))


def _invalidate_continuations(tx: sqlite3.Connection, human_id: str, reason: str) -> None:
    now = _now()
    try:
        pending = tx.execute("SELECT approval_id,correlation_id FROM policy_approvals WHERE status IN ('pending','approved') AND (initiating_human_id=? OR approved_by_human_id=?)", (human_id, human_id)).fetchall()
        tx.execute("UPDATE policy_approvals SET status='cancelled',cancelled_at=?,cancelled_by_human_id=? WHERE status IN ('pending','approved') AND (initiating_human_id=? OR approved_by_human_id=?)", (now, human_id, human_id, human_id))
        for item in pending:
            tx.execute("INSERT INTO policy_continuation_events(occurred_at,kind,subject_id,actor_human_id,event_type,reason_code,summary,correlation_id) VALUES (?,?,?,?,?,?,?,?)", (now, "approval", item["approval_id"], human_id, "approval.invalidated", reason[:80], "Approval invalidated because Identity authority changed.", item["correlation_id"]))
        exceptions = tx.execute("SELECT exception_id FROM policy_temporary_exceptions WHERE status='active' AND (human_id=? OR created_by_human_id=?)", (human_id, human_id)).fetchall()
        tx.execute("UPDATE policy_temporary_exceptions SET status='revoked',revoked_at=?,revoked_by_human_id=? WHERE status='active' AND (human_id=? OR created_by_human_id=?)", (now, human_id, human_id, human_id))
        for item in exceptions:
            tx.execute("INSERT INTO policy_continuation_events(occurred_at,kind,subject_id,actor_human_id,event_type,reason_code,summary,correlation_id) VALUES (?,?,?,?,?,?,?,?)", (now, "exception", item["exception_id"], human_id, "exception.invalidated", reason[:80], "Temporary access invalidated because Identity authority changed.", item["exception_id"]))
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise


def _close_enterprise_continuations(tx: sqlite3.Connection, actor_id: str) -> dict[str, int]:
    now = _now(); approvals = 0; exceptions = 0
    try:
        approval_rows = tx.execute("SELECT approval_id,correlation_id FROM policy_approvals WHERE status IN ('pending','approved')").fetchall()
        approvals = len(approval_rows)
        tx.execute("UPDATE policy_approvals SET status='cancelled',cancelled_at=?,cancelled_by_human_id=? WHERE status IN ('pending','approved')", (now, actor_id))
        for row in approval_rows:
            tx.execute("INSERT INTO policy_continuation_events(occurred_at,kind,subject_id,actor_human_id,event_type,reason_code,summary,correlation_id) VALUES (?,?,?,?,?,?,?,?)", (now, "approval", row["approval_id"], actor_id, "approval.cancelled", "enterprise_disabled", "Approval cancelled because Enterprise Mode was disabled.", row["correlation_id"]))
        exception_rows = tx.execute("SELECT exception_id FROM policy_temporary_exceptions WHERE status='active'").fetchall()
        exceptions = len(exception_rows)
        tx.execute("UPDATE policy_temporary_exceptions SET status='revoked',revoked_at=?,revoked_by_human_id=? WHERE status='active'", (now, actor_id))
        for row in exception_rows:
            tx.execute("INSERT INTO policy_continuation_events(occurred_at,kind,subject_id,actor_human_id,event_type,reason_code,summary,correlation_id) VALUES (?,?,?,?,?,?,?,?)", (now, "exception", row["exception_id"], actor_id, "exception.revoked", "enterprise_disabled", "Temporary access revoked because Enterprise Mode was disabled.", row["exception_id"]))
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
    return {"approvals_cancelled": approvals, "exceptions_revoked": exceptions}


def mode_preview(*, auth_context: dict[str, Any], enabled: bool) -> dict[str, Any]:
    apply_migrations(); actor_id = _actor_id(auth_context)
    with connection() as conn:
        current = bool(_configuration(conn).get("enabled"))
        if current:
            _require_enterprise_owner(conn, auth_context)
        elif _local_owner_id(conn) != actor_id:
            raise EnterpriseIdentityError("local_owner_required", "Only the local Pocket Lab Owner can change workspace mode.")
        topology = _topology(conn)
        pending = conn.execute("SELECT COUNT(*) AS count FROM policy_approvals WHERE status IN ('pending','approved')").fetchone()
        active_exceptions = conn.execute("SELECT COUNT(*) AS count FROM policy_temporary_exceptions WHERE status='active'").fetchone()
    target = bool(enabled)
    changes = ["All active sessions will be signed out so the new authorization model takes effect."]
    if current and not target:
        changes += ["Enterprise memberships are retained but stop granting authority in Personal Mode.", "Pending approvals will be cancelled.", "Active temporary exceptions will be revoked.", "Only the local Owner can sign in while Personal Mode is active."]
    elif not current and target:
        changes += ["The local Owner becomes an active Enterprise Owner.", "Previously retained memberships become authoritative again when their people are active.", "Role and Rules capability views become available."]
    return {"current_mode": "enterprise" if current else "personal", "target_mode": "enterprise" if target else "personal", "changes": changes, "topology": topology, "pending_approvals": int(pending["count"] or 0) if pending else 0, "active_exceptions": int(active_exceptions["count"] or 0) if active_exceptions else 0}


def set_enterprise_enabled(*, auth_context: dict[str, Any], enabled: bool, correlation_id: str | None = None) -> dict[str, Any]:
    apply_migrations(); actor_id = _actor_id(auth_context); now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current = _configuration(tx); was_enabled = bool(current.get("enabled"))
            if was_enabled:
                _require_enterprise_owner(tx, auth_context)
            elif _local_owner_id(tx) != actor_id:
                raise EnterpriseIdentityError("local_owner_required", "Only the local Pocket Lab Owner can enable Enterprise Mode.")
            if was_enabled == bool(enabled):
                return enterprise_projection(auth_context)
            cleanup = {"approvals_cancelled": 0, "exceptions_revoked": 0}
            if enabled:
                tx.execute("""INSERT INTO enterprise_configuration(configuration_id,enabled,authorization_version,enabled_at,created_at,updated_at,updated_by_human_id)
                              VALUES (1,1,1,?,?,?,?)
                              ON CONFLICT(configuration_id) DO UPDATE SET enabled=1,authorization_version=enterprise_configuration.authorization_version+1,enabled_at=excluded.enabled_at,disabled_at=NULL,updated_at=excluded.updated_at,updated_by_human_id=excluded.updated_by_human_id""", (now, now, now, actor_id))
                tx.execute("""INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id)
                              VALUES (?, 'Owner', 'active',1,?,?,?,?)
                              ON CONFLICT(human_id) DO UPDATE SET role='Owner',status='active',authorization_version=enterprise_memberships.authorization_version+1,updated_at=excluded.updated_at,updated_by_human_id=excluded.updated_by_human_id""", (actor_id, now, now, actor_id, actor_id))
                event, reason, summary = "enterprise_mode.enabled", "enterprise_enabled", "Enterprise Mode enabled by the local Owner."
            else:
                cleanup = _close_enterprise_continuations(tx, actor_id)
                tx.execute("UPDATE enterprise_configuration SET enabled=0,authorization_version=authorization_version+1,disabled_at=?,updated_at=?,updated_by_human_id=? WHERE configuration_id=1", (now, now, actor_id))
                event, reason, summary = "enterprise_mode.disabled", "enterprise_disabled", "Enterprise Mode disabled by an Enterprise Owner. Memberships were retained for reversible re-enable."
            _invalidate_all_authorization(tx, reason=reason)
            _audit(tx, human_id=actor_id, event_type=event, reason_code=reason, summary=summary, correlation_id=correlation_id)
    result = enterprise_projection(None); result["continuations"] = cleanup
    return result


def list_members(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _manager(tx, auth_context)
            rows = tx.execute("""SELECT m.human_id,h.display_name,h.username_normalized,h.status AS identity_status,m.role,m.status,m.authorization_version,m.created_at,m.updated_at
                                 FROM enterprise_memberships m JOIN human_identities h ON h.human_id=m.human_id
                                 ORDER BY CASE m.role WHEN 'Owner' THEN 0 WHEN 'Admin' THEN 1 ELSE 2 END,m.created_at""").fetchall()
    return {"members": [dict(row) for row in rows], "roles": sorted(ROLES), "role_catalog": [{"id": role, **ROLE_CATALOG[role]} for role in ("Owner", "Admin", "Operator", "Auditor", "Viewer")]}


def set_membership(*, auth_context: dict[str, Any], human_id: str, role: str, membership_status: str, correlation_id: str | None = None) -> dict[str, Any]:
    apply_migrations(); target_id = str(human_id or "").strip()[:120]
    if not target_id:
        raise EnterpriseIdentityError("enterprise_member_invalid", "Select a valid Pocket Lab identity.", status_code=422)
    normalized_role = _role(role); normalized_status = _membership_status(membership_status); now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            actor_id, actor_role = _manager(tx, auth_context)
            target = tx.execute("SELECT human_id,status FROM human_identities WHERE human_id=?", (target_id,)).fetchone()
            if not target or target["status"] == "removed":
                raise EnterpriseIdentityError("enterprise_member_unknown", "That local identity is not available for Enterprise membership.", status_code=404)
            prior = tx.execute("SELECT role,status FROM enterprise_memberships WHERE human_id=?", (target_id,)).fetchone()
            prior_role = str(prior["role"] or "") if prior else ""
            if actor_role == "Admin" and (normalized_role in {"Owner", "Admin"} or prior_role in {"Owner", "Admin"}):
                raise EnterpriseIdentityError("enterprise_owner_authority_required", "Only an Owner can create or change Owner and Admin access.")
            removing_owner = bool(prior and prior_role == "Owner" and prior["status"] == "active" and (normalized_role != "Owner" or normalized_status != "active"))
            if removing_owner:
                owners = tx.execute("""SELECT COUNT(*) AS count FROM enterprise_memberships m JOIN human_identities h ON h.human_id=m.human_id
                                       WHERE m.role='Owner' AND m.status='active' AND h.status='active'""").fetchone()
                if int(owners["count"] or 0) <= 1:
                    raise EnterpriseIdentityError("enterprise_final_owner_protected", "Pocket Lab must retain one active Enterprise Owner.", status_code=409)
            tx.execute("""INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id)
                          VALUES (?,?,?,1,?,?,?,?)
                          ON CONFLICT(human_id) DO UPDATE SET role=excluded.role,status=excluded.status,authorization_version=enterprise_memberships.authorization_version+1,updated_at=excluded.updated_at,updated_by_human_id=excluded.updated_by_human_id""", (target_id, normalized_role, normalized_status, now, now, actor_id, actor_id))
            _invalidate_authorization(tx, target_id, reason="enterprise_membership_changed")
            _invalidate_continuations(tx, target_id, "enterprise_membership_changed")
            event = "role.changed" if prior and prior_role != normalized_role else "membership.changed"
            _audit(tx, human_id=target_id, event_type=event, reason_code="enterprise_membership_changed", summary="Enterprise membership or role changed by an authorized administrator.", correlation_id=correlation_id)
            row = tx.execute("SELECT human_id,role,status,authorization_version,created_at,updated_at FROM enterprise_memberships WHERE human_id=?", (target_id,)).fetchone()
    return {"member": dict(row)}
