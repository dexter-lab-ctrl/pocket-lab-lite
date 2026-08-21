from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations

ROLES = frozenset({"Owner", "Admin", "Operator", "Viewer", "Auditor"})
MEMBERSHIP_STATUSES = frozenset({"active", "removed"})


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
    row = conn.execute(
        "SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    return str(row["human_id"]) if row else None


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
    """Attach only server-resolved enterprise authorization facts to a session context."""
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
    }
    return result


def enterprise_projection(auth_context: dict[str, Any] | None = None) -> dict[str, Any]:
    apply_migrations()
    with connection() as conn:
        configuration = _configuration(conn)
        enabled = bool(configuration.get("enabled"))
        actor_id = str(((auth_context or {}).get("actor") or {}).get("identity_id") or "")
        membership = conn.execute(
            "SELECT role,status,authorization_version FROM enterprise_memberships WHERE human_id=?", (actor_id,)
        ).fetchone() if actor_id else None
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
        "updated_at": configuration.get("updated_at"),
    }


def _require_enterprise_owner(tx: sqlite3.Connection, auth_context: dict[str, Any]) -> str:
    actor_id = _actor_id(auth_context)
    if not bool(_configuration(tx).get("enabled")):
        raise EnterpriseIdentityError("enterprise_mode_disabled", "Enterprise Mode is not enabled for this Pocket Lab.", status_code=404)
    membership = tx.execute(
        "SELECT role,status FROM enterprise_memberships WHERE human_id=?", (actor_id,)
    ).fetchone()
    if not membership or membership["status"] != "active" or membership["role"] != "Owner":
        raise EnterpriseIdentityError("enterprise_owner_required", "An active Enterprise Owner session is required.")
    return actor_id


def _invalidate_authorization(tx: sqlite3.Connection, human_id: str, *, reason: str) -> None:
    now = _now()
    tx.execute("UPDATE human_identities SET auth_version=auth_version+1,updated_at=? WHERE human_id=?", (now, human_id))
    tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason=? WHERE human_id=? AND revoked_at IS NULL", (now, reason[:80], human_id))


def _invalidate_all_authorization(tx: sqlite3.Connection, *, reason: str) -> None:
    """A mode flip changes authority for every member, not only its author."""
    now = _now()
    tx.execute("UPDATE human_identities SET auth_version=auth_version+1,updated_at=? WHERE status='active'", (now,))
    tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason=? WHERE revoked_at IS NULL", (now, reason[:80]))


def set_enterprise_enabled(*, auth_context: dict[str, Any], enabled: bool, correlation_id: str | None = None) -> dict[str, Any]:
    apply_migrations()
    actor_id = _actor_id(auth_context)
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current = _configuration(tx)
            if bool(current.get("enabled")):
                _require_enterprise_owner(tx, auth_context)
            elif _local_owner_id(tx) != actor_id:
                raise EnterpriseIdentityError("local_owner_required", "Only the local Pocket Lab Owner can enable Enterprise Mode.")
            if bool(current.get("enabled")) == bool(enabled):
                return enterprise_projection(auth_context)
            if enabled:
                tx.execute(
                    """INSERT INTO enterprise_configuration(configuration_id,enabled,authorization_version,enabled_at,created_at,updated_at,updated_by_human_id)
                       VALUES (1,1,1,?,?,?,?)
                       ON CONFLICT(configuration_id) DO UPDATE SET enabled=1,authorization_version=enterprise_configuration.authorization_version+1,
                       enabled_at=excluded.enabled_at,disabled_at=NULL,updated_at=excluded.updated_at,updated_by_human_id=excluded.updated_by_human_id""",
                    (now, now, now, actor_id),
                )
                tx.execute(
                    """INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id)
                       VALUES (?, 'Owner', 'active', 1, ?, ?, ?, ?)
                       ON CONFLICT(human_id) DO UPDATE SET role='Owner',status='active',authorization_version=enterprise_memberships.authorization_version+1,
                       updated_at=excluded.updated_at,updated_by_human_id=excluded.updated_by_human_id""",
                    (actor_id, now, now, actor_id, actor_id),
                )
                event, reason, summary = "enterprise_mode.enabled", "enterprise_enabled", "Enterprise Mode enabled by the local Owner."
            else:
                tx.execute(
                    "UPDATE enterprise_configuration SET enabled=0,authorization_version=authorization_version+1,disabled_at=?,updated_at=?,updated_by_human_id=? WHERE configuration_id=1",
                    (now, now, actor_id),
                )
                event, reason, summary = "enterprise_mode.disabled", "enterprise_disabled", "Enterprise Mode disabled by an Enterprise Owner."
            _invalidate_all_authorization(tx, reason=reason)
            _audit(tx, human_id=actor_id, event_type=event, reason_code=reason, summary=summary, correlation_id=correlation_id)
    return enterprise_projection(None)


def list_members(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _require_enterprise_owner(tx, auth_context)
            rows = tx.execute(
                """SELECT m.human_id,h.display_name,m.role,m.status,m.authorization_version,m.created_at,m.updated_at
                   FROM enterprise_memberships m JOIN human_identities h ON h.human_id=m.human_id
                   ORDER BY CASE m.role WHEN 'Owner' THEN 0 ELSE 1 END,m.created_at"""
            ).fetchall()
    return {"members": [dict(row) for row in rows], "roles": sorted(ROLES)}


def set_membership(*, auth_context: dict[str, Any], human_id: str, role: str, membership_status: str, correlation_id: str | None = None) -> dict[str, Any]:
    apply_migrations()
    target_id = str(human_id or "").strip()[:120]
    if not target_id:
        raise EnterpriseIdentityError("enterprise_member_invalid", "Select a valid Pocket Lab identity.", status_code=422)
    normalized_role = _role(role)
    normalized_status = _membership_status(membership_status)
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            actor_id = _require_enterprise_owner(tx, auth_context)
            target = tx.execute("SELECT human_id,status FROM human_identities WHERE human_id=?", (target_id,)).fetchone()
            if not target or target["status"] != "active":
                raise EnterpriseIdentityError("enterprise_member_unknown", "That local identity is not available for Enterprise membership.", status_code=404)
            prior = tx.execute("SELECT role,status FROM enterprise_memberships WHERE human_id=?", (target_id,)).fetchone()
            removing_owner = bool(prior and prior["role"] == "Owner" and prior["status"] == "active" and (normalized_role != "Owner" or normalized_status != "active"))
            if removing_owner:
                owners = tx.execute("SELECT COUNT(*) AS count FROM enterprise_memberships WHERE role='Owner' AND status='active'").fetchone()
                if int(owners["count"] or 0) <= 1:
                    raise EnterpriseIdentityError("enterprise_final_owner_protected", "Pocket Lab must retain one active Enterprise Owner.", status_code=409)
            tx.execute(
                """INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id)
                   VALUES (?,?,?,1,?,?,?,?)
                   ON CONFLICT(human_id) DO UPDATE SET role=excluded.role,status=excluded.status,
                   authorization_version=enterprise_memberships.authorization_version+1,updated_at=excluded.updated_at,updated_by_human_id=excluded.updated_by_human_id""",
                (target_id, normalized_role, normalized_status, now, now, actor_id, actor_id),
            )
            _invalidate_authorization(tx, target_id, reason="enterprise_membership_changed")
            event = "membership.changed" if not prior else ("role.changed" if prior["role"] != normalized_role else "membership.changed")
            _audit(tx, human_id=target_id, event_type=event, reason_code="enterprise_membership_changed", summary="Enterprise membership or role changed by an Owner.", correlation_id=correlation_id)
            row = tx.execute("SELECT human_id,role,status,authorization_version,created_at,updated_at FROM enterprise_memberships WHERE human_id=?", (target_id,)).fetchone()
    return {"member": dict(row)}
