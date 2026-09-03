"""Enterprise human enrollment and person lifecycle for Pocket Lab Lite.

Claims are short-lived, one-time and stored only as hashes.  Passkey crypto is
reused from the existing dependency-free WebAuthn verifier.  This service never
places raw claims, session tokens, recovery codes or private key material into
persistent UI state or audit evidence.
"""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import lite_enterprise_identity, lite_identity_auth, lite_webauthn

CLAIM_TTL_SECONDS = 15 * 60
AUTHORITY_TTL_SECONDS = 5 * 60


class EnrollmentError(RuntimeError):
    def __init__(self, reason_code: str, message: str, status_code: int = 403):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _hash(value: str) -> str:
    return lite_identity_auth._hash_opaque(str(value or ""))


def _manager(auth_context: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    context = lite_enterprise_identity.enrich_auth_context(auth_context)
    actor = context.get("actor") or {}
    authorization = context.get("authorization") or {}
    actor_id = str(actor.get("identity_id") or "")
    role = str(authorization.get("role") or "")
    if actor.get("type") != "human" or not actor_id:
        raise EnrollmentError("human_session_required", "A signed-in human session is required.", 401)
    if not authorization.get("enterprise_enabled"):
        raise EnrollmentError("enterprise_mode_required", "People management is available in Enterprise Mode.", 404)
    if not authorization.get("membership_active") or role not in {"Owner", "Admin"}:
        raise EnrollmentError("enterprise_people_role_required", "Owner or Admin access is required to manage people.")
    return context, actor_id, role


def _normalize_role(role: str, manager_role: str) -> str:
    candidate = str(role or "").strip()
    if candidate not in lite_enterprise_identity.ROLES:
        raise EnrollmentError("enterprise_role_invalid", "Select a recognized Pocket Lab role.", 422)
    if manager_role == "Admin" and candidate in {"Owner", "Admin"}:
        raise EnrollmentError("enterprise_owner_authority_required", "Only an Owner can create or change Owner and Admin access.")
    return candidate


def _person(conn: Any, human_id: str) -> dict[str, Any]:
    row = conn.execute(
        """SELECT h.human_id,h.username_normalized,h.display_name,h.status,h.created_at,h.updated_at,h.last_authenticated_at,
                  m.role,m.status AS membership_status,m.authorization_version
           FROM human_identities h
           LEFT JOIN enterprise_memberships m ON m.human_id=h.human_id
           WHERE h.human_id=?""",
        (human_id,),
    ).fetchone()
    if not row:
        raise EnrollmentError("enterprise_person_unknown", "That person is not available.", 404)
    item = dict(row)
    passkeys = conn.execute(
        "SELECT COUNT(*) AS count FROM webauthn_credentials WHERE human_id=? AND revoked_at IS NULL",
        (human_id,),
    ).fetchone()
    sessions = conn.execute(
        "SELECT COUNT(*) AS count FROM auth_sessions WHERE human_id=? AND revoked_at IS NULL AND absolute_expires_at>?",
        (human_id, _iso()),
    ).fetchone()
    recovery = conn.execute(
        """SELECT COUNT(*) AS count FROM recovery_codes c
           JOIN recovery_code_batches b ON b.batch_id=c.batch_id
           WHERE b.human_id=? AND b.invalidated_at IS NULL AND c.consumed_at IS NULL""",
        (human_id,),
    ).fetchone()
    invite = conn.execute(
        """SELECT claim_id,created_at,expires_at,consumed_at,completed_at,revoked_at
           FROM human_enrollment_claims WHERE human_id=? ORDER BY created_at DESC LIMIT 1""",
        (human_id,),
    ).fetchone()
    item.update({
        "username": item.pop("username_normalized"),
        "active_passkeys": int(passkeys["count"] or 0) if passkeys else 0,
        "active_sessions": int(sessions["count"] or 0) if sessions else 0,
        "recovery_codes_remaining": int(recovery["count"] or 0) if recovery else 0,
        "invite": dict(invite) if invite else None,
    })
    return item


def _active_owner_count(conn: Any) -> int:
    row = conn.execute(
        """SELECT COUNT(*) AS count FROM enterprise_memberships m
           JOIN human_identities h ON h.human_id=m.human_id
           WHERE m.role='Owner' AND m.status='active' AND h.status='active'"""
    ).fetchone()
    return int(row["count"] or 0) if row else 0


def _protect_final_owner(conn: Any, human_id: str) -> None:
    row = conn.execute(
        """SELECT m.role,m.status,h.status AS human_status
           FROM human_identities h LEFT JOIN enterprise_memberships m ON m.human_id=h.human_id
           WHERE h.human_id=?""",
        (human_id,),
    ).fetchone()
    if row and row["role"] == "Owner" and row["membership_status" if "membership_status" in row.keys() else "status"] == "active" and row["human_status"] == "active" and _active_owner_count(conn) <= 1:
        raise EnrollmentError("enterprise_final_owner_protected", "Pocket Lab must retain one active Enterprise Owner.", 409)


def _invalidate_person(tx: Any, human_id: str, reason: str) -> None:
    now = _iso()
    tx.execute("UPDATE human_identities SET auth_version=auth_version+1,updated_at=? WHERE human_id=?", (now, human_id))
    tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason=? WHERE human_id=? AND revoked_at IS NULL", (now, reason[:80], human_id))
    try:
        tx.execute(
            """UPDATE policy_approvals SET status='cancelled',cancelled_at=?,cancelled_by_human_id=?
               WHERE status IN ('pending','approved') AND (initiating_human_id=? OR approved_by_human_id=?)""",
            (now, human_id, human_id, human_id),
        )
        tx.execute(
            """UPDATE policy_temporary_exceptions SET status='revoked',revoked_at=?,revoked_by_human_id=?
               WHERE status='active' AND (human_id=? OR created_by_human_id=?)""",
            (now, human_id, human_id, human_id),
        )
    except Exception:
        # Additive rollout safety: identity/session invalidation remains the hard
        # boundary even if continuation tables are from a newer migration set.
        pass


def _new_claim(tx: Any, *, human_id: str, created_by: str, role: str, origin: str) -> dict[str, Any]:
    normalized_origin, rp_id = lite_webauthn._normalize_origin(origin)
    raw_claim = secrets.token_urlsafe(32)
    claim_id = "person-claim-" + uuid.uuid4().hex
    now = _now()
    expires = _iso(now + timedelta(seconds=CLAIM_TTL_SECONDS))
    user_handle = lite_webauthn._b64url(secrets.token_bytes(32))
    tx.execute("UPDATE human_enrollment_claims SET revoked_at=? WHERE human_id=? AND completed_at IS NULL AND revoked_at IS NULL", (_iso(now), human_id))
    tx.execute(
        """INSERT INTO human_enrollment_claims(
               claim_id,claim_hash,human_id,created_by_human_id,requested_role,installation_id,rp_id,origin,
               webauthn_user_handle,created_at,expires_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (claim_id, _hash(raw_claim), human_id, created_by, role, lite_webauthn._installation_id(), rp_id, normalized_origin, user_handle, _iso(now), expires),
    )
    return {
        "claim_id": claim_id,
        "claim": raw_claim,
        "expires_at": expires,
        "claim_url": f"{normalized_origin}/?person_claim={raw_claim}",
    }


def create_person(*, auth_context: dict[str, Any], username: str, display_name: str, role: str, origin: str) -> dict[str, Any]:
    apply_migrations()
    _, actor_id, manager_role = _manager(auth_context)
    requested_role = _normalize_role(role, manager_role)
    normalized = lite_identity_auth._normalize_username(username)
    display = str(display_name or "Pocket Lab person").strip()[:120] or "Pocket Lab person"
    human_id = "human-" + uuid.uuid4().hex
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            if tx.execute("SELECT 1 FROM human_identities WHERE username_normalized=?", (normalized,)).fetchone():
                raise EnrollmentError("identity_username_exists", "That sign-in name is already used.", 409)
            tx.execute(
                "INSERT INTO human_identities(human_id,username_normalized,display_name,status,auth_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (human_id, normalized, display, "invited", 1, now, now),
            )
            tx.execute(
                """INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id)
                   VALUES (?,?, 'active',1,?,?,?,?)""",
                (human_id, requested_role, now, now, actor_id, actor_id),
            )
            invite = _new_claim(tx, human_id=human_id, created_by=actor_id, role=requested_role, origin=origin)
            lite_identity_auth._audit(tx, human_id=human_id, session_id=None, event_type="person.invited", reason_code="enterprise_owner_invite" if manager_role == "Owner" else "enterprise_admin_invite", summary="A short-lived Enterprise person enrollment was created.", correlation_id=invite["claim_id"])
            person = _person(tx, human_id)
    return {"person": person, "invite": invite, "summary": "Person invited. Share the one-time connect link privately before it expires."}


def list_people(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations(); _manager(auth_context)
    with connection() as conn:
        rows = conn.execute("SELECT human_id FROM human_identities ORDER BY created_at ASC").fetchall()
        people = [_person(conn, str(row["human_id"])) for row in rows]
    return {"people": people, "roles": sorted(lite_enterprise_identity.ROLES)}


def read_person(*, auth_context: dict[str, Any], human_id: str) -> dict[str, Any]:
    apply_migrations(); _manager(auth_context)
    with connection() as conn:
        return {"person": _person(conn, str(human_id)[:120])}


def regenerate_invite(*, auth_context: dict[str, Any], human_id: str, origin: str) -> dict[str, Any]:
    apply_migrations()
    _, actor_id, manager_role = _manager(auth_context)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            person = _person(tx, str(human_id)[:120])
            if person["status"] != "invited":
                raise EnrollmentError("enterprise_invite_not_pending", "Only a person who is waiting to join can receive a new enrollment link.", 409)
            _normalize_role(str(person.get("role") or "Viewer"), manager_role)
            invite = _new_claim(tx, human_id=person["human_id"], created_by=actor_id, role=str(person.get("role") or "Viewer"), origin=origin)
            lite_identity_auth._audit(tx, human_id=person["human_id"], session_id=None, event_type="person.invite_regenerated", reason_code="enterprise_invite_regenerated", summary="A replacement Enterprise enrollment link was created.", correlation_id=invite["claim_id"])
    return {"person": person, "invite": invite, "summary": "Replacement connect link created. The previous link no longer works."}


def _manageable_target(tx: Any, *, actor_id: str, manager_role: str, human_id: str) -> dict[str, Any]:
    person = _person(tx, str(human_id)[:120])
    if manager_role == "Admin" and str(person.get("role") or "") in {"Owner", "Admin"}:
        raise EnrollmentError("enterprise_owner_authority_required", "Only an Owner can manage Owner or Admin identities.")
    if actor_id == person["human_id"] and manager_role != "Owner":
        raise EnrollmentError("enterprise_self_management_forbidden", "Use your own passkey, session and recovery controls for your account.", 409)
    return person


def suspend_person(*, auth_context: dict[str, Any], human_id: str) -> dict[str, Any]:
    apply_migrations(); _, actor_id, manager_role = _manager(auth_context)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            person = _manageable_target(tx, actor_id=actor_id, manager_role=manager_role, human_id=human_id)
            _protect_final_owner(tx, person["human_id"])
            if person["status"] != "active":
                raise EnrollmentError("enterprise_person_not_active", "Only an active person can be suspended.", 409)
            _invalidate_person(tx, person["human_id"], "enterprise_person_suspended")
            tx.execute("UPDATE human_identities SET status='suspended',updated_at=? WHERE human_id=?", (_iso(), person["human_id"]))
            lite_identity_auth._audit(tx, human_id=person["human_id"], session_id=None, event_type="person.suspended", reason_code="enterprise_person_suspended", summary="Enterprise access suspended by an authorized administrator.")
            updated = _person(tx, person["human_id"])
    return {"person": updated, "summary": "Access suspended. Existing sessions can no longer authorize requests."}


def reactivate_person(*, auth_context: dict[str, Any], human_id: str) -> dict[str, Any]:
    apply_migrations(); _, actor_id, manager_role = _manager(auth_context)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            person = _manageable_target(tx, actor_id=actor_id, manager_role=manager_role, human_id=human_id)
            if person["status"] != "suspended":
                raise EnrollmentError("enterprise_person_not_suspended", "Only a suspended person can be reactivated.", 409)
            tx.execute("UPDATE human_identities SET status='active',auth_version=auth_version+1,updated_at=? WHERE human_id=?", (_iso(), person["human_id"]))
            lite_identity_auth._audit(tx, human_id=person["human_id"], session_id=None, event_type="person.reactivated", reason_code="enterprise_person_reactivated", summary="Enterprise access reactivated by an authorized administrator.")
            updated = _person(tx, person["human_id"])
    return {"person": updated, "summary": "Access reactivated. The person can sign in again with an active credential."}


def reset_access(*, auth_context: dict[str, Any], human_id: str, origin: str) -> dict[str, Any]:
    apply_migrations(); _, actor_id, manager_role = _manager(auth_context)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            person = _manageable_target(tx, actor_id=actor_id, manager_role=manager_role, human_id=human_id)
            _protect_final_owner(tx, person["human_id"])
            _invalidate_person(tx, person["human_id"], "enterprise_access_reset")
            now = _iso()
            tx.execute("UPDATE webauthn_credentials SET revoked_at=? WHERE human_id=? AND revoked_at IS NULL", (now, person["human_id"]))
            tx.execute("UPDATE human_credentials SET disabled_at=? WHERE human_id=? AND disabled_at IS NULL", (now, person["human_id"]))
            tx.execute("UPDATE recovery_code_batches SET invalidated_at=? WHERE human_id=? AND invalidated_at IS NULL", (now, person["human_id"]))
            tx.execute("UPDATE human_identities SET status='invited',updated_at=? WHERE human_id=?", (now, person["human_id"]))
            invite = _new_claim(tx, human_id=person["human_id"], created_by=actor_id, role=str(person.get("role") or "Viewer"), origin=origin)
            lite_identity_auth._audit(tx, human_id=person["human_id"], session_id=None, event_type="person.access_reset", reason_code="enterprise_access_reset", summary="Enterprise sign-in methods were reset and a new one-time enrollment was created.", correlation_id=invite["claim_id"])
            updated = _person(tx, person["human_id"])
    return {"person": updated, "invite": invite, "summary": "Access reset. Old sign-in methods were revoked and a new one-time connect link was created."}


def remove_person(*, auth_context: dict[str, Any], human_id: str) -> dict[str, Any]:
    apply_migrations(); _, actor_id, manager_role = _manager(auth_context)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            person = _manageable_target(tx, actor_id=actor_id, manager_role=manager_role, human_id=human_id)
            _protect_final_owner(tx, person["human_id"])
            _invalidate_person(tx, person["human_id"], "enterprise_person_removed")
            now = _iso()
            tx.execute("UPDATE human_enrollment_claims SET revoked_at=? WHERE human_id=? AND completed_at IS NULL AND revoked_at IS NULL", (now, person["human_id"]))
            tx.execute("UPDATE webauthn_credentials SET revoked_at=? WHERE human_id=? AND revoked_at IS NULL", (now, person["human_id"]))
            tx.execute("UPDATE human_credentials SET disabled_at=? WHERE human_id=? AND disabled_at IS NULL", (now, person["human_id"]))
            tx.execute("UPDATE enterprise_memberships SET status='removed',authorization_version=authorization_version+1,updated_at=?,updated_by_human_id=? WHERE human_id=?", (now, actor_id, person["human_id"]))
            tx.execute("UPDATE human_identities SET status='removed',updated_at=? WHERE human_id=?", (now, person["human_id"]))
            lite_identity_auth._audit(tx, human_id=person["human_id"], session_id=None, event_type="person.removed", reason_code="enterprise_person_removed", summary="Enterprise person access removed; audit history was retained.")
            updated = _person(tx, person["human_id"])
    return {"person": updated, "summary": "Person removed from active access. Identity and audit history are retained."}


def consume_claim(*, raw_claim: str, origin: str) -> dict[str, Any]:
    apply_migrations()
    normalized_origin, origin_host = lite_webauthn._normalize_origin(origin)
    now = _now(); authority = secrets.token_urlsafe(32)
    authority_expires = _iso(now + timedelta(seconds=AUTHORITY_TTL_SECONDS))
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT * FROM human_enrollment_claims WHERE claim_hash=? LIMIT 1", (_hash(raw_claim),)).fetchone()
            if not row:
                raise EnrollmentError("person_claim_invalid", "This connect link could not be verified.", 401)
            claim = dict(row)
            if claim.get("revoked_at") or claim.get("completed_at"):
                raise EnrollmentError("person_claim_unavailable", "This connect link is no longer available.", 409)
            if str(claim.get("expires_at") or "") <= _iso(now):
                raise EnrollmentError("person_claim_expired", "This connect link expired. Ask an Owner or Admin for a new one.", 410)
            if claim.get("installation_id") != lite_webauthn._installation_id():
                raise EnrollmentError("person_claim_installation_mismatch", "This connect link belongs to another Pocket Lab.")
            if claim.get("origin") != normalized_origin or not lite_webauthn._rp_id_valid_for_origin(str(claim.get("rp_id") or ""), origin_host):
                raise EnrollmentError("person_claim_origin_mismatch", "Open this connect link on the Pocket Lab address it was created for.")
            human = tx.execute("SELECT status FROM human_identities WHERE human_id=?", (claim["human_id"],)).fetchone()
            if not human or human["status"] != "invited":
                raise EnrollmentError("person_claim_identity_unavailable", "This invited identity is no longer waiting to join.", 409)
            tx.execute("UPDATE human_enrollment_claims SET consumed_at=?,authority_hash=?,authority_expires_at=? WHERE claim_id=?", (_iso(now), _hash(authority), authority_expires, claim["claim_id"]))
    return {"authority": authority, "expires_at": authority_expires, "status": "claim_verified"}


def _claim_from_authority(authority: str, origin: str) -> dict[str, Any]:
    normalized_origin, origin_host = lite_webauthn._normalize_origin(origin)
    with connection() as conn:
        row = conn.execute("SELECT * FROM human_enrollment_claims WHERE authority_hash=? LIMIT 1", (_hash(authority),)).fetchone()
    if not row:
        raise EnrollmentError("person_claim_authority_invalid", "Enrollment authority is no longer valid.", 401)
    claim = dict(row)
    if claim.get("revoked_at") or claim.get("completed_at") or str(claim.get("authority_expires_at") or "") <= _iso():
        raise EnrollmentError("person_claim_authority_expired", "Enrollment confirmation expired. Ask for a new connect link.", 410)
    if claim.get("origin") != normalized_origin or not lite_webauthn._rp_id_valid_for_origin(str(claim.get("rp_id") or ""), origin_host):
        raise EnrollmentError("person_claim_origin_mismatch", "Enrollment must stay on the original Pocket Lab address.")
    return claim


def claim_status(*, authority: str, origin: str) -> dict[str, Any]:
    try:
        claim = _claim_from_authority(authority, origin)
    except EnrollmentError as exc:
        return {"active": False, "status": exc.reason_code, "summary": exc.message}
    with connection() as conn:
        person = _person(conn, str(claim["human_id"]))
    return {"active": True, "status": "claim_verified", "expires_at": claim["authority_expires_at"], "person": {"display_name": person["display_name"], "username": person["username"], "role": person.get("role")}, "summary": "Connect link verified. Create a passkey to finish joining Pocket Lab."}


def enrollment_options(*, authority: str, origin: str) -> dict[str, Any]:
    claim = _claim_from_authority(authority, origin)
    with connection() as conn:
        human = conn.execute("SELECT username_normalized,display_name,status FROM human_identities WHERE human_id=?", (claim["human_id"],)).fetchone()
    if not human or human["status"] != "invited":
        raise EnrollmentError("person_claim_identity_unavailable", "This identity is no longer waiting to join.", 409)
    challenge, _ = lite_webauthn._challenge(purpose="person_claim_register", rp_id=claim["rp_id"], origin=claim["origin"], human_id=claim["human_id"], owner_claim_id=claim["claim_id"])
    return {"publicKey": {"challenge": challenge, "rp": {"name": "Pocket Lab Lite", "id": claim["rp_id"]}, "user": {"id": claim["webauthn_user_handle"], "name": human["username_normalized"], "displayName": human["display_name"]}, "pubKeyCredParams": [{"type": "public-key", "alg": -7}], "timeout": 120000, "attestation": "none", "authenticatorSelection": {"residentKey": "preferred", "userVerification": "required"}}, "origin": claim["origin"], "rp_id": claim["rp_id"]}


def complete_enrollment(*, authority: str, origin: str, challenge: str, payload: dict[str, Any], friendly_name: str) -> dict[str, Any]:
    claim = _claim_from_authority(authority, origin)
    lite_webauthn._consume_challenge(raw_challenge=challenge, purpose="person_claim_register", rp_id=claim["rp_id"], origin=claim["origin"], human_id=claim["human_id"], owner_claim_id=claim["claim_id"])
    material = lite_webauthn._registration_material(payload, challenge=challenge, origin=claim["origin"], rp_id=claim["rp_id"])
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current = tx.execute("SELECT * FROM human_enrollment_claims WHERE claim_id=?", (claim["claim_id"],)).fetchone()
            human = tx.execute("SELECT * FROM human_identities WHERE human_id=?", (claim["human_id"],)).fetchone()
            if not current or current["completed_at"] or current["revoked_at"] or not human or human["status"] != "invited":
                raise EnrollmentError("person_claim_unavailable", "This enrollment is no longer available.", 409)
            if tx.execute("SELECT 1 FROM webauthn_credentials WHERE credential_id=?", (material["credential_id_text"],)).fetchone():
                raise EnrollmentError("passkey_already_registered", "That passkey is already registered.", 409)
            tx.execute("INSERT OR IGNORE INTO webauthn_users(human_id,user_handle,created_at) VALUES (?,?,?)", (claim["human_id"], claim["webauthn_user_handle"], now))
            credential = lite_webauthn._insert_credential(tx, human_id=claim["human_id"], material=material, friendly_name=friendly_name, transports=payload.get("transports"), attachment=payload.get("authenticatorAttachment"))
            tx.execute("UPDATE human_identities SET status='active',last_authenticated_at=?,updated_at=? WHERE human_id=?", (now, now, claim["human_id"]))
            tx.execute("UPDATE enterprise_memberships SET status='active',authorization_version=authorization_version+1,updated_at=? WHERE human_id=?", (now, claim["human_id"]))
            refreshed = tx.execute("SELECT human_id,auth_version FROM human_identities WHERE human_id=?", (claim["human_id"],)).fetchone()
            session = lite_identity_auth._insert_session(tx, human=dict(refreshed), method="passkey")
            tx.execute("UPDATE human_enrollment_claims SET completed_at=?,authority_hash=NULL,authority_expires_at=NULL WHERE claim_id=?", (now, claim["claim_id"]))
            lite_identity_auth._audit(tx, human_id=claim["human_id"], session_id=session["session_id"], event_type="person.activated", reason_code="enterprise_passkey_enrollment", summary="Enterprise person activated with a passkey.", correlation_id=claim["claim_id"])
            lite_identity_auth._audit(tx, human_id=claim["human_id"], session_id=session["session_id"], event_type="passkey.enrolled", reason_code="enterprise_passkey_enrollment", summary="Enterprise passkey enrolled.", correlation_id=claim["claim_id"])
    recovery = lite_identity_auth.regenerate_recovery_codes(human_id=claim["human_id"], session_id=session["session_id"])
    return {"credential": credential, "session": session, "recovery_codes": recovery["codes"], "summary": "Access activated. Save the recovery codes somewhere private."}


def login_options(*, origin: str, username: str = "") -> dict[str, Any]:
    apply_migrations()
    normalized_origin, rp_id = lite_webauthn._normalize_origin(origin)
    with connection() as conn:
        config = conn.execute("SELECT enabled FROM enterprise_configuration WHERE configuration_id=1").fetchone()
        enterprise_enabled = bool(config and config["enabled"])
        selected_human_id = ""
        if username:
            try:
                normalized = lite_identity_auth._normalize_username(username)
            except lite_identity_auth.IdentityError as exc:
                raise EnrollmentError(exc.reason_code, exc.message, exc.status_code) from exc
            human = conn.execute("SELECT human_id,status FROM human_identities WHERE username_normalized=?", (normalized,)).fetchone()
            if not human or human["status"] != "active":
                raise EnrollmentError("identity_login_failed", "Sign-in details were not accepted.", 401)
            selected_human_id = str(human["human_id"])
        if enterprise_enabled:
            query = """SELECT c.credential_id,c.human_id FROM webauthn_credentials c
                       JOIN human_identities h ON h.human_id=c.human_id
                       JOIN enterprise_memberships m ON m.human_id=h.human_id
                       WHERE c.revoked_at IS NULL AND h.status='active' AND m.status='active'"""
            args: tuple[Any, ...] = ()
            if selected_human_id:
                query += " AND h.human_id=?"; args = (selected_human_id,)
            creds = conn.execute(query + " ORDER BY c.created_at", args).fetchall()
        else:
            owner = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
            owner_id = str(owner["human_id"]) if owner else ""
            if selected_human_id and selected_human_id != owner_id:
                raise EnrollmentError("identity_login_failed", "Sign-in details were not accepted.", 401)
            selected_human_id = owner_id
            creds = conn.execute("SELECT credential_id,human_id FROM webauthn_credentials WHERE human_id=? AND revoked_at IS NULL ORDER BY created_at", (owner_id,)).fetchall() if owner_id else []
    if not creds:
        raise EnrollmentError("passkey_unavailable", "No active passkey is available for that sign-in.", 409)
    purpose = f"login_human:{selected_human_id}" if selected_human_id else "login_human"
    challenge, _ = lite_webauthn._challenge(purpose=purpose, rp_id=rp_id, origin=normalized_origin, human_id=None)
    return {"publicKey": {"challenge": challenge, "rpId": rp_id, "allowCredentials": [{"type": "public-key", "id": row["credential_id"]} for row in creds], "userVerification": "required", "timeout": 120000}, "origin": normalized_origin, "rp_id": rp_id, "login_scope": "named" if selected_human_id else "workspace"}


def complete_login(*, origin: str, challenge: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_origin, rp_id = lite_webauthn._normalize_origin(origin)
    credential_id = str(payload.get("rawId") or payload.get("id") or "")
    credential = lite_webauthn._credential_for_assertion(credential_id)
    purpose_named = f"login_human:{credential['human_id']}"
    try:
        lite_webauthn._consume_challenge(raw_challenge=challenge, purpose=purpose_named, rp_id=rp_id, origin=normalized_origin, human_id=None)
    except lite_webauthn.WebAuthnError as named_error:
        if named_error.reason_code != "webauthn_challenge_scope_mismatch":
            raise EnrollmentError(named_error.reason_code, named_error.message, named_error.status_code) from named_error
        try:
            lite_webauthn._consume_challenge(raw_challenge=challenge, purpose="login_human", rp_id=rp_id, origin=normalized_origin, human_id=None)
        except lite_webauthn.WebAuthnError as exc:
            raise EnrollmentError(exc.reason_code, exc.message, exc.status_code) from exc
    assertion = lite_webauthn._assertion_material(payload, challenge=challenge, origin=normalized_origin, rp_id=rp_id, credential=credential)
    now = _iso()
    with connection() as conn:
        config = conn.execute("SELECT enabled FROM enterprise_configuration WHERE configuration_id=1").fetchone()
        enterprise_enabled = bool(config and config["enabled"])
        if enterprise_enabled:
            membership = conn.execute("SELECT status FROM enterprise_memberships WHERE human_id=?", (credential["human_id"],)).fetchone()
            if not membership or membership["status"] != "active":
                raise EnrollmentError("enterprise_membership_required", "This person's Enterprise access is not active.")
        else:
            owner = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
            if not owner or str(owner["human_id"]) != credential["human_id"]:
                raise EnrollmentError("personal_mode_owner_required", "Only the local Owner can sign in while Personal Mode is active.")
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE webauthn_credentials SET sign_count=?,last_used_at=? WHERE credential_id=?", (max(int(credential.get("sign_count") or 0), int(assertion["sign_count"])), now, credential_id))
            human = tx.execute("SELECT human_id,auth_version,username_normalized,display_name FROM human_identities WHERE human_id=? AND status='active'", (credential["human_id"],)).fetchone()
            if not human:
                raise EnrollmentError("identity_login_failed", "Sign-in details were not accepted.", 401)
            session = lite_identity_auth._insert_session(tx, human=dict(human), method="passkey")
            tx.execute("UPDATE human_identities SET last_authenticated_at=?,updated_at=? WHERE human_id=?", (now, now, credential["human_id"]))
            lite_identity_auth._audit(tx, human_id=credential["human_id"], session_id=session["session_id"], event_type="session.signed_in", reason_code="passkey_verified", summary="Pocket Lab person signed in with a passkey.")
    return {"human": {"human_id": human["human_id"], "username": human["username_normalized"], "display_name": human["display_name"]}, **session}


def unified_identity_projection(auth_context: dict[str, Any] | None) -> dict[str, Any]:
    base = lite_identity_auth.identity_projection(auth_context)
    actor_id = str(((auth_context or {}).get("actor") or {}).get("identity_id") or "")
    if not actor_id:
        base["person"] = None
        return base
    with connection() as conn:
        local_owner = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
        if local_owner and str(local_owner["human_id"]) == actor_id:
            owner = base.get("owner") if isinstance(base.get("owner"), dict) else {}
            base["person"] = {"human_id": actor_id, "username": owner.get("username"), "display_name": owner.get("display_name"), "status": owner.get("status", "active"), "role": (base.get("enterprise") or {}).get("current_membership", {}).get("role") or "Owner", "is_local_owner": True}
            return base
        human = conn.execute("SELECT * FROM human_identities WHERE human_id=? AND status='active'", (actor_id,)).fetchone()
        if not human:
            base["person"] = None
            base["authenticated"] = False
            return base
        enterprise = lite_enterprise_identity.enterprise_projection(auth_context)
        membership = enterprise.get("current_membership") or {}
        now = _now()
        sessions = []
        for row in conn.execute("SELECT session_id,auth_method,created_at,last_seen_at,idle_expires_at,absolute_expires_at,revoked_at FROM auth_sessions WHERE human_id=? ORDER BY created_at DESC LIMIT 20", (actor_id,)):
            item = dict(row); idle = lite_identity_auth._parse_iso(item.get("idle_expires_at")); absolute = lite_identity_auth._parse_iso(item.get("absolute_expires_at"))
            item["active"] = not item.get("revoked_at") and idle is not None and absolute is not None and now < idle and now < absolute
            item["current"] = item["session_id"] == str(((auth_context or {}).get("session") or {}).get("session_id") or "")
            sessions.append(item)
        passkeys = []
        for row in conn.execute("SELECT credential_id,friendly_name,transports_json,authenticator_attachment,created_at,last_used_at,revoked_at FROM webauthn_credentials WHERE human_id=? ORDER BY created_at DESC LIMIT 20", (actor_id,)):
            item = dict(row)
            try: item["transports"] = json.loads(item.pop("transports_json") or "[]")
            except Exception: item["transports"] = []
            item["active"] = not bool(item.get("revoked_at")); passkeys.append(item)
        batch = conn.execute("SELECT batch_id,generation FROM recovery_code_batches WHERE human_id=? AND invalidated_at IS NULL ORDER BY generation DESC LIMIT 1", (actor_id,)).fetchone()
        recovery = {"configured": False, "remaining": 0, "generation": 0}
        if batch:
            remaining = conn.execute("SELECT COUNT(*) AS count FROM recovery_codes WHERE batch_id=? AND consumed_at IS NULL", (batch["batch_id"],)).fetchone()
            recovery = {"configured": True, "remaining": int(remaining["count"] or 0), "generation": int(batch["generation"])}
        activity = [dict(row) for row in conn.execute("SELECT occurred_at,event_type,reason_code,summary,correlation_id FROM identity_audit_events WHERE human_id=? ORDER BY event_id DESC LIMIT 20", (actor_id,))]
        password_configured = conn.execute("SELECT 1 FROM human_credentials WHERE human_id=? AND kind='password' AND disabled_at IS NULL LIMIT 1", (actor_id,)).fetchone() is not None
    session_context = (auth_context or {}).get("session") or {}
    return {
        "status": "ready",
        "summary": "Your access is protected by server-side identity, role and Safety Rules checks.",
        "setup_required": False,
        "authenticated": True,
        "owner": {"configured": True, "status": "active"},
        "person": {"human_id": actor_id, "username": human["username_normalized"], "display_name": human["display_name"], "status": human["status"], "role": membership.get("role"), "is_local_owner": False, "password_configured": password_configured},
        "session": {"session_id": session_context.get("session_id"), "authenticated": True, "auth_method": session_context.get("auth_method"), "idle_expires_at": session_context.get("idle_expires_at"), "absolute_expires_at": session_context.get("absolute_expires_at"), "expiry_mode": "fixed", "assurance": session_context.get("assurance") or []},
        "sessions": sessions,
        "passkeys": passkeys,
        "recovery": recovery,
        "recent_activity": activity,
        "sign_in_methods": {"password": password_configured, "passkey": any(item["active"] for item in passkeys), "oidc": False},
        "enterprise": enterprise,
        "session_expiry_mode": "fixed",
        "updated_at": _iso(),
    }
