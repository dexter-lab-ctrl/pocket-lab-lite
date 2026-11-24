"""Bounded System Health control authority. No credentials are persisted here."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.connection import connection, begin_immediate
from . import lite_system_health as health


def _future(value: Any) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def preferences() -> dict:
    rows = health._read("SELECT revision,recovery_mode,resource_mode,updated_at FROM lite_system_health_preferences WHERE singleton_id=1")
    return rows[0] if rows else {"revision": 0, "recovery_mode": "monitor", "resource_mode": "balanced", "updated_at": None}


def _human_authority(conn, actor_id: str, session_id: str) -> dict | None:
    row = conn.execute(
        """SELECT s.revoked_at,s.idle_expires_at,s.absolute_expires_at,s.auth_version,
                  h.auth_version AS current_auth_version,h.status
           FROM auth_sessions s JOIN human_identities h ON h.human_id=s.human_id
           WHERE s.session_id=? AND h.human_id=?""", (session_id, actor_id)
    ).fetchone()
    if not row or row["revoked_at"] or row["status"] != "active" or row["auth_version"] != row["current_auth_version"] or not _future(row["idle_expires_at"]) or not _future(row["absolute_expires_at"]):
        return None
    configuration = conn.execute("SELECT enabled FROM enterprise_configuration WHERE configuration_id=1").fetchone()
    member = conn.execute("SELECT role,status,authorization_version FROM enterprise_memberships WHERE human_id=?", (actor_id,)).fetchone()
    owner = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
    enabled = bool(configuration and configuration["enabled"])
    role = member["role"] if enabled and member and member["status"] == "active" else "Owner" if owner and owner["human_id"] == actor_id else None
    return {"role": role, "authorization_version": member["authorization_version"] if member else 1,
            "enterprise_enabled": enabled, "owner_authority": role == "Owner",
            "membership_active": bool(member and member["status"] == "active") if enabled else role == "Owner"}


def require_owner(conn, context: dict) -> str:
    actor, session = context.get("actor") or {}, context.get("session") or {}
    if actor.get("type") != "human" or not session.get("authenticated"):
        raise PermissionError("owner_required")
    actor_id = str(actor.get("identity_id") or "")
    authority = _human_authority(conn, actor_id, str(session.get("session_id") or ""))
    if not authority or authority["role"] != "Owner":
        raise PermissionError("owner_required")
    return actor_id


def audit(conn, actor_id: str, event: str, subject: str = "") -> None:
    conn.execute("INSERT INTO lite_system_health_control_audit(actor_id,event_type,subject_id,occurred_at) VALUES (?,?,?,?)",
                 (actor_id, event, subject, health._now()))
    # Bounded operational audit; existing identity/policy audit remains independent.
    conn.execute("DELETE FROM lite_system_health_control_audit WHERE event_id NOT IN (SELECT event_id FROM lite_system_health_control_audit ORDER BY event_id DESC LIMIT 2000)")


def save_preferences(context: dict, *, expected_revision: int, recovery_mode: str, resource_mode: str) -> dict:
    if recovery_mode not in {"monitor", "assisted"} or resource_mode not in {"balanced", "low_power", "maintenance"}:
        raise ValueError("invalid_preference")
    # Preferences are intent only; they cannot promote an unqualified adapter
    # or change scheduler behavior before the owner's qualified policy exists.
    with connection() as conn:
        with begin_immediate(conn):
            actor = require_owner(conn, context)
            row = conn.execute("SELECT revision FROM lite_system_health_preferences WHERE singleton_id=1").fetchone()
            current = int(row["revision"]) if row else 0
            if current != expected_revision:
                raise ValueError("preference_revision_changed")
            conn.execute("""INSERT INTO lite_system_health_preferences VALUES (1,?,?,?,?)
                            ON CONFLICT(singleton_id) DO UPDATE SET revision=excluded.revision,
                            recovery_mode=excluded.recovery_mode,resource_mode=excluded.resource_mode,updated_at=excluded.updated_at""",
                         (current+1, recovery_mode, resource_mode, health._now()))
            audit(conn, actor, "preferences_changed")
    return preferences()


def bind_request(conn, request_id: str, context: dict, confirmed: bool) -> None:
    actor, session, auth = context.get("actor") or {}, context.get("session") or {}, context.get("authorization") or {}
    session_id = session.get("session_id") if actor.get("type") == "human" else (context.get("harness") or {}).get("session_id")
    role = auth.get("role")
    if not session_id or role not in {"Owner", "Admin", "Operator"} or not session.get("authenticated"):
        raise PermissionError("durable_authority_required")
    conn.execute("""INSERT INTO lite_system_health_request_authority VALUES (?,?,?,?,?,?)
                    ON CONFLICT(request_id) DO UPDATE SET session_id=excluded.session_id,actor_role=excluded.actor_role,
                    authorization_version=excluded.authorization_version,enterprise_enabled=excluded.enterprise_enabled,confirmed=excluded.confirmed""",
                 (request_id, str(session_id), role, int(auth.get("authorization_version") or 1), int(bool(auth.get("enterprise_enabled"))), int(confirmed)))


def _current_context(conn, request: dict) -> dict | None:
    binding = conn.execute("SELECT * FROM lite_system_health_request_authority WHERE request_id=?", (request["request_id"],)).fetchone()
    if not binding or not binding["confirmed"]:
        return None
    actor_id, kind = request["actor_id"], request["actor_type"]
    if kind == "human":
        auth = _human_authority(conn, actor_id, binding["session_id"])
        if not auth or auth["role"] != binding["actor_role"] or auth["authorization_version"] != binding["authorization_version"] or auth["enterprise_enabled"] != bool(binding["enterprise_enabled"]):
            return None
        return {"actor": {"identity_id": actor_id, "type": "human"}, "session": {"authenticated": True}, "authorization": auth}
    if kind != "qualification":
        return None
    from . import lite_harness
    if not lite_harness.harness_enabled() or not lite_harness.qualification_owner_enabled() or lite_harness.environment() != lite_harness.HARNESS_RUNTIME_ENVIRONMENT:
        return None
    row = conn.execute("""SELECT s.*,p.display_name,p.enabled AS principal_enabled,p.revoked_at AS principal_revoked_at,
                                 p.expires_at AS principal_expires_at
                          FROM harness_sessions s JOIN synthetic_principals p ON p.principal_id=s.principal_id
                          WHERE s.harness_session_id=? AND s.principal_id=?""", (binding["session_id"], actor_id)).fetchone()
    if not row or row["status"] != "active" or not row["principal_enabled"] or row["principal_revoked_at"] or not _future(row["expires_at"]) or not _future(row["principal_expires_at"]) or row["capability_profile"] != "qualification-owner":
        return None
    return lite_harness._session_context(dict(row))


def _approval_valid(conn, request: dict, context: dict) -> bool:
    if not request["approval_id"]:
        return False
    row = conn.execute("""SELECT a.*,m.role AS approver_role,m.status AS approver_membership,h.status AS approver_status
                          FROM policy_approvals a JOIN enterprise_memberships m ON m.human_id=a.approved_by_human_id
                          JOIN human_identities h ON h.human_id=a.approved_by_human_id WHERE a.approval_id=?""",
                       (request["approval_id"],)).fetchone()
    return bool(row and row["status"] == "consumed" and _future(row["expires_at"])
                and row["initiating_human_id"] == request["actor_id"]
                and row["initiating_role"] == context["authorization"]["role"]
                and row["initiating_authorization_version"] == context["authorization"]["authorization_version"]
                and row["action_id"] == "system_health.recovery" and row["target_type"] == request["target_type"]
                and row["target_id"] == request["incident_id"] and row["target_revision"] == request["target_revision"]
                and row["request_fingerprint"] == request["target_revision"] and row["policy_revision"] == request["policy_revision"]
                and row["approved_by_human_id"] != request["actor_id"] and row["approver_role"] in {"Owner","Admin"}
                and row["approver_membership"] == "active" and row["approver_status"] == "active")


def revalidate(request: dict) -> bool:
    """Recheck persisted session, consumed approval, exact policy and live OPA.

    Do not call evaluate_authorization for consumed continuations: that function
    would create another approval. Build a server-owned continuation fact only
    from the exact consumed row, and use the existing loopback OPA contract.
    """
    from . import lite_policy_opa as opa, lite_harness
    try:
        with connection() as conn:
            context = _current_context(conn, request)
            if not context:
                return False
            approval = _approval_valid(conn, request, context) if request["approval_id"] else False
            if request["approval_id"] and not approval:
                return False
            decision = conn.execute("""SELECT 1 FROM policy_decisions WHERE decision_id=? AND actor_id=? AND actor_type=?
                AND action_id='system_health.recovery' AND target_type=? AND target_id=? AND target_revision=? AND policy_revision=? AND allow=1""",
                (request["policy_decision_id"],request["actor_id"],request["actor_type"],request["target_type"],request["incident_id"],request["target_revision"],request["policy_revision"])).fetchone()
            if not decision:
                return False
        lite_harness.enforce_capability(context, action_id="system_health.recovery", target_type=request["target_type"],
                                      target_id=request["incident_id"], destructive=False, operation_id=request["operation_id"])
        opa._require_loopback_opa()
        consistent, _, observed = opa._policy_consistency()
        if not consistent or (observed or opa._safe_revision()) != request["policy_revision"]:
            return False
        doc = opa.build_authorization_input(auth_context=context, action_id="system_health.recovery",
            target_type=request["target_type"], target_id=request["incident_id"], target_revision=request["target_revision"],
            target={"scope":"local_server_host_only","operation_id":request["operation_id"],"adapter_enabled":True,
                    "preflight_valid":True,"incident_generation":request["incident_generation"],"enrollment_generation":request["enrollment_generation"],"confirmed":True},
            request_context={"confirmation_present":True,"idempotency_key_present":True})
        doc["continuation"] = {"matching_independent_approval":approval,"matching_temporary_exception":False}
        status, payload = opa._http_json("POST", opa.OPA_DECISION_PATH, {"input":doc})
        result = opa._validate_result(payload.get("result")) if status == 200 else {}
        if result.get("allow") is not True or (observed or result.get("policy_revision")) != request["policy_revision"]:
            return False
        # Re-read identity after network evaluation to narrow revocation races.
        with connection() as conn:
            return bool(_current_context(conn,request) and (not approval or _approval_valid(conn,request,context)))
    except Exception:
        return False


def cancel_request(context: dict, request_id: str) -> dict:
    with connection() as conn:
        with begin_immediate(conn):
            actor = require_owner(conn, context)
            row = conn.execute("SELECT * FROM lite_system_health_recovery_requests WHERE request_id=?", (request_id,)).fetchone()
            if not row:
                raise LookupError("request_not_found")
            if row["status"] == "cancelled":
                return health._public_recovery_request(dict(row))
            if row["status"] not in {"requested","preflight_checked","approval_required","approved","admitted"} or row["attempt"] != 0:
                raise ValueError("execution_already_started")
            now = health._now()
            conn.execute("""UPDATE lite_system_health_recovery_requests SET status='cancelled',execution_state='cancelled',
                            updated_at=?,completed_at=?,outcome='cancelled',terminal_reason='owner_cancelled',safe_summary='Cancelled before execution.'
                            WHERE request_id=?""", (now,now,request_id))
            conn.execute("""UPDATE lite_system_health_repair_attempts SET execution_state='cancelled',completed_at=?,outcome='cancelled',
                            safe_summary='Cancelled before execution.' WHERE repair_id=?""",(now,request_id))
            health._event(conn,row["incident_id"],row["incident_generation"],"recovery_cancelled","Owner cancelled before execution.")
            audit(conn,actor,"recovery_cancelled",request_id)
            return health._public_recovery_request(dict(conn.execute("SELECT * FROM lite_system_health_recovery_requests WHERE request_id=?",(request_id,)).fetchone()))
