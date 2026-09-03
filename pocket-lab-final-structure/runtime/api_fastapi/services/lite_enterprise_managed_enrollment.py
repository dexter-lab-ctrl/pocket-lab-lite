"""Owner/Admin-authorized WebAuthn enrollment for Enterprise people.

The browser never receives a Pocket Lab enrollment token. An authorized Owner
or Admin starts a bounded WebAuthn registration ceremony for an already-created
invited identity. The platform authenticator (including supported cross-device
WebAuthn flows) handles credential transfer; Pocket Lab stores only the public
credential material and sanitized lifecycle evidence.
"""
from __future__ import annotations

from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import lite_enterprise_enrollment, lite_identity_auth, lite_webauthn

PURPOSE = "enterprise_person_register"


class ManagedEnrollmentError(RuntimeError):
    def __init__(self, reason_code: str, message: str, status_code: int = 403):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


def _manager_and_target(auth_context: dict[str, Any], human_id: str) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    try:
        context, actor_id, manager_role = lite_enterprise_enrollment._manager(auth_context)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        raise ManagedEnrollmentError(exc.reason_code, exc.message, exc.status_code) from exc
    session_id = str(((context.get("session") or {}).get("session_id") or ""))
    if not session_id:
        raise ManagedEnrollmentError("human_session_required", "A signed-in human session is required.", 401)
    with connection() as conn:
        try:
            person = lite_enterprise_enrollment._manageable_target(
                conn,
                actor_id=actor_id,
                manager_role=manager_role,
                human_id=str(human_id)[:120],
            )
        except lite_enterprise_enrollment.EnrollmentError as exc:
            raise ManagedEnrollmentError(exc.reason_code, exc.message, exc.status_code) from exc
    if person["status"] != "invited":
        raise ManagedEnrollmentError(
            "enterprise_person_not_waiting",
            "Passkey setup is available only while this person is waiting to join.",
            409,
        )
    return context, actor_id, session_id, person


def registration_options(*, auth_context: dict[str, Any], human_id: str, origin: str) -> dict[str, Any]:
    apply_migrations()
    _context, _actor_id, session_id, person = _manager_and_target(auth_context, human_id)
    normalized_origin, rp_id = lite_webauthn._normalize_origin(origin)
    user_handle = lite_webauthn._get_or_create_user_handle(person["human_id"])
    challenge, _ = lite_webauthn._challenge(
        purpose=PURPOSE,
        rp_id=rp_id,
        origin=normalized_origin,
        human_id=person["human_id"],
        session_id=session_id,
    )
    exclude = [
        {"type": "public-key", "id": item["credential_id"]}
        for item in lite_webauthn._active_credentials(person["human_id"])
    ]
    return {
        "publicKey": {
            "challenge": challenge,
            "rp": {"name": "Pocket Lab Lite", "id": rp_id},
            "user": {
                "id": user_handle,
                "name": person["username"],
                "displayName": person["display_name"],
            },
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
            "timeout": 120000,
            "attestation": "none",
            "authenticatorSelection": {
                "residentKey": "preferred",
                "userVerification": "required",
            },
            "excludeCredentials": exclude,
        },
        "origin": normalized_origin,
        "rp_id": rp_id,
        "person": {
            "human_id": person["human_id"],
            "display_name": person["display_name"],
            "username": person["username"],
            "role": person.get("role"),
        },
        "summary": "Use the platform passkey prompt to set up this person. Pocket Lab does not display an enrollment token.",
    }


def complete_registration(
    *,
    auth_context: dict[str, Any],
    human_id: str,
    origin: str,
    challenge: str,
    payload: dict[str, Any],
    friendly_name: str,
) -> dict[str, Any]:
    apply_migrations()
    _context, actor_id, session_id, person = _manager_and_target(auth_context, human_id)
    normalized_origin, rp_id = lite_webauthn._normalize_origin(origin)
    try:
        lite_webauthn._consume_challenge(
            raw_challenge=challenge,
            purpose=PURPOSE,
            rp_id=rp_id,
            origin=normalized_origin,
            human_id=person["human_id"],
            session_id=session_id,
        )
        material = lite_webauthn._registration_material(
            payload,
            challenge=challenge,
            origin=normalized_origin,
            rp_id=rp_id,
        )
    except lite_webauthn.WebAuthnError as exc:
        raise ManagedEnrollmentError(exc.reason_code, exc.message, exc.status_code) from exc

    now = lite_enterprise_enrollment._iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current = tx.execute(
                "SELECT status FROM human_identities WHERE human_id=?",
                (person["human_id"],),
            ).fetchone()
            if not current or current["status"] != "invited":
                raise ManagedEnrollmentError(
                    "enterprise_person_not_waiting",
                    "This person is no longer waiting to join.",
                    409,
                )
            if tx.execute(
                "SELECT 1 FROM webauthn_credentials WHERE credential_id=?",
                (material["credential_id_text"],),
            ).fetchone():
                raise ManagedEnrollmentError("passkey_already_registered", "That passkey is already registered.", 409)
            credential = lite_webauthn._insert_credential(
                tx,
                human_id=person["human_id"],
                material=material,
                friendly_name=friendly_name,
                transports=payload.get("transports"),
                attachment=payload.get("authenticatorAttachment"),
            )
            tx.execute(
                "UPDATE human_identities SET status='active',updated_at=? WHERE human_id=? AND status='invited'",
                (now, person["human_id"]),
            )
            tx.execute(
                "UPDATE enterprise_memberships SET status='active',authorization_version=authorization_version+1,updated_at=?,updated_by_human_id=? WHERE human_id=?",
                (now, actor_id, person["human_id"]),
            )
            # Any provisional claim rows created by earlier branch iterations are
            # revoked and remain non-secret audit metadata only.
            tx.execute(
                "UPDATE human_enrollment_claims SET revoked_at=?,authority_hash=NULL,authority_expires_at=NULL WHERE human_id=? AND completed_at IS NULL AND revoked_at IS NULL",
                (now, person["human_id"]),
            )
            lite_identity_auth._audit(
                tx,
                human_id=person["human_id"],
                session_id=session_id,
                event_type="person.activated",
                reason_code="enterprise_managed_passkey_enrollment",
                summary="Enterprise person activated with an authorized WebAuthn enrollment.",
                correlation_id=person["human_id"],
            )
            lite_identity_auth._audit(
                tx,
                human_id=person["human_id"],
                session_id=session_id,
                event_type="passkey.enrolled",
                reason_code="enterprise_managed_passkey_enrollment",
                summary="Enterprise passkey enrolled without exposing an enrollment token.",
                correlation_id=person["human_id"],
            )
            updated = lite_enterprise_enrollment._person(tx, person["human_id"])
    return {
        "person": updated,
        "credential": credential,
        "summary": "Passkey set up. This person can now sign in with their own Pocket Lab identity and create recovery codes after sign-in.",
    }
