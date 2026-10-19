"""Single-use, server-owned Owner approvals for bounded operations.

This module is intentionally separate from the Enterprise continuation
approval table and from the qualification harness.  A registered automation
client is an authenticated requester, not an Owner; only a real Pocket Lab
human Owner can approve; and the executor remains the existing worker-backed
Photo Backup implementation.

The only registered production handler in this version is
``photo_backup.bounded_acceptance.v1``.  There is no generic command, URL,
path, NATS subject, or API-forwarding escape hatch here.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .. import deps
from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import (
    fleet_registry,
    lite_enterprise_governance,
    lite_enterprise_identity,
    lite_identity_auth,
    lite_photo_backup,
    lite_photo_backup_destinations,
)


OPERATION_TYPE = "photo_backup.bounded_acceptance.v1"
CONTRACT_VERSION = 1
DESTINATION_ID = lite_photo_backup_destinations.CURRENT_DESTINATION_ID
OWNER_APPROVAL_PURPOSE = "owner.operations.approve"
CLIENT_REGISTRATION_PURPOSE = "owner.operations.client.register"
CLIENT_CHALLENGE_TTL_SECONDS = 120
PAIRING_TTL_SECONDS = 15 * 60
REQUEST_CHALLENGE_TTL_SECONDS = 120
APPROVAL_TTL_SECONDS = 15 * 60
EXECUTION_TTL_SECONDS = 40 * 60
MAX_ACTIVE_CHALLENGES = 4
MAX_CHALLENGE_FAILURES = 5
TERMINAL_STATUSES = {"completed", "rejected", "expired", "cancelled", "failed", "blocked"}
ACTIVE_STATUSES = {"pending_approval", "approved", "executing", "verifying"}
_CLIENT_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_CHALLENGE_ID_RE = re.compile(r"^oo-challenge-[a-f0-9]{24}$")
_OPERATION_ID_RE = re.compile(r"^oo-[a-f0-9]{24}$")
_PAIRING_ID_RE = re.compile(r"^ocp-[a-f0-9]{24}$")
_SIGNATURE_MAX = 160
_PUBLIC_KEY_MAX = 96
_SECRET_MARKERS = ("password", "token", "secret", "private", "credential", "bearer", "cookie")


class OwnerOperationError(RuntimeError):
    """A safe, user-facing rejection from the operation contract."""

    def __init__(self, reason_code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.reason_code = str(reason_code)[:80]
        self.message = str(message)[:240]
        self.status_code = int(status_code)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    material = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _safe_id(value: Any, *, kind: str = "id") -> str:
    candidate = str(value or "").strip()
    if kind == "client" and not _CLIENT_ID_RE.fullmatch(candidate):
        raise OwnerOperationError("client_id_invalid", "The registered client identity is not valid.", 422)
    if kind == "challenge" and not _CHALLENGE_ID_RE.fullmatch(candidate):
        raise OwnerOperationError("challenge_invalid", "The client challenge is not valid.", 422)
    if kind == "operation" and not _OPERATION_ID_RE.fullmatch(candidate):
        raise OwnerOperationError("operation_invalid", "The operation identity is not valid.", 422)
    if kind == "pairing" and not _PAIRING_ID_RE.fullmatch(candidate):
        raise OwnerOperationError("pairing_invalid", "The pairing identity is not valid.", 422)
    return candidate


def _b64decode(value: Any, *, expected_length: int, field: str) -> bytes:
    encoded = str(value or "").strip()
    if not encoded or len(encoded) > _SIGNATURE_MAX:
        raise OwnerOperationError(f"{field}_invalid", f"The {field.replace('_', ' ')} is not valid.", 422)
    try:
        decoded = base64.urlsafe_b64decode(encoded + ("=" * (-len(encoded) % 4)))
    except (ValueError, binascii.Error) as exc:
        raise OwnerOperationError(f"{field}_invalid", f"The {field.replace('_', ' ')} is not valid.", 422) from exc
    if len(decoded) != expected_length:
        raise OwnerOperationError(f"{field}_invalid", f"The {field.replace('_', ' ')} is not valid.", 422)
    return decoded


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _public_key_bytes(value: Any) -> bytes:
    if len(str(value or "").strip()) > _PUBLIC_KEY_MAX:
        raise OwnerOperationError("public_key_invalid", "The public key is not valid.", 422)
    return _b64decode(value, expected_length=32, field="public_key")


def _signature_bytes(value: Any) -> bytes:
    return _b64decode(value, expected_length=64, field="signature")


def _validate_text(value: Any, *, name: str, maximum: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise OwnerOperationError(f"{name}_invalid", f"The {name.replace('_', ' ')} is required.", 422)
    if len(text) > maximum or any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise OwnerOperationError(f"{name}_invalid", f"The {name.replace('_', ' ')} is not valid.", 422)
    return text


def _validate_reason(value: Any) -> str:
    reason = _validate_text(value, name="reason", maximum=240)
    lowered = reason.casefold()
    if "://" in lowered or reason.startswith(("/", "~", "\\")) or any(marker in lowered for marker in _SECRET_MARKERS):
        raise OwnerOperationError("reason_invalid", "The request reason cannot contain credentials or paths.", 422)
    return reason


def normalize_descriptor(descriptor: Any, *, expected_client_id: str | None = None) -> dict[str, Any]:
    """Validate and canonicalize the only production operation descriptor."""
    if not isinstance(descriptor, dict):
        raise OwnerOperationError("descriptor_invalid", "The operation descriptor must be an object.", 422)
    required = {"contract_version", "operation", "requester_id", "target_node_id", "scope", "reason", "idempotency_key"}
    if set(descriptor) != required:
        raise OwnerOperationError("descriptor_fields_invalid", "The operation descriptor contains unsupported fields.", 422)
    if type(descriptor.get("contract_version")) is not int or descriptor["contract_version"] != CONTRACT_VERSION:
        raise OwnerOperationError("contract_version_unsupported", "The operation contract version is not supported.", 422)
    if descriptor.get("operation") != OPERATION_TYPE:
        raise OwnerOperationError("operation_unsupported", "This operation type is not enabled.", 422)
    client_id = _safe_id(descriptor.get("requester_id"), kind="client")
    if expected_client_id and client_id != expected_client_id:
        raise OwnerOperationError("requester_mismatch", "The descriptor requester does not match the registered client.", 403)
    raw_node = _validate_text(descriptor.get("target_node_id"), name="target_node_id", maximum=80)
    target_node_id = fleet_registry.normalize_node_id(raw_node)
    if target_node_id == "unknown-node":
        raise OwnerOperationError("target_invalid", "The operation target device is not valid.", 422)
    scope = descriptor.get("scope")
    expected_scope = {
        "fixture": "one_server_generated_jpeg",
        "collection": "pictures",
        "repeat": "same_fixture_once",
    }
    if not isinstance(scope, dict) or set(scope) != set(expected_scope) or scope != expected_scope:
        raise OwnerOperationError("scope_invalid", "Only one generated Pictures test photo with one safe repeat is supported.", 422)
    idempotency_key = _validate_text(descriptor.get("idempotency_key"), name="idempotency_key", maximum=128)
    if not _IDEMPOTENCY_RE.fullmatch(idempotency_key):
        raise OwnerOperationError("idempotency_key_invalid", "The idempotency key is not valid.", 422)
    return {
        "contract_version": CONTRACT_VERSION,
        "operation": OPERATION_TYPE,
        "requester_id": client_id,
        "target_node_id": target_node_id,
        "scope": expected_scope,
        "reason": _validate_reason(descriptor.get("reason")),
        "idempotency_key": idempotency_key,
    }


def _target_binding(node_id: str) -> dict[str, Any]:
    normalized = fleet_registry.normalize_node_id(node_id)
    agent = fleet_registry.get_agent(normalized)
    if not isinstance(agent, dict):
        raise OwnerOperationError("target_not_found", "The requested device is not enrolled.", 409)
    if lite_photo_backup._is_protected_server(agent):
        raise OwnerOperationError("protected_server_target", "The Server Phone cannot be used as the source device.", 409)
    identity_status = str(agent.get("identity_status") or "").casefold()
    if identity_status != "verified":
        raise OwnerOperationError("target_identity_unverified", "The source device identity is not verified.", 409)
    try:
        identity_revision = int(agent.get("identity_revision") or 0)
    except (TypeError, ValueError):
        identity_revision = 0
    if identity_revision < 1:
        raise OwnerOperationError("target_identity_unverified", "The source device identity is not ready.", 409)
    label = str(agent.get("name") or agent.get("hostname") or normalized).strip()[:80] or normalized
    binding = {
        "node_id": normalized,
        "identity_status": "verified",
        "identity_revision": identity_revision,
        "identity_verified_at": str(agent.get("identity_verified_at") or "")[:64],
    }
    return {"node_id": normalized, "label": label, "identity_revision": identity_revision, "binding": binding, "binding_digest": _digest(binding)}


def _destination_binding() -> dict[str, Any]:
    adapter = lite_photo_backup_destinations.adapter(DESTINATION_ID)
    return {
        "destination_id": DESTINATION_ID,
        "contract_version": int(adapter and lite_photo_backup_destinations.SCHEMA_VERSION),
        "display_name": "PhotoPrism on this server",
    }


def _ensure_db() -> None:
    apply_migrations()


def _client_row(conn: Any, client_id: str, *, active: bool = True) -> Any:
    row = conn.execute("SELECT * FROM owner_operation_clients WHERE client_id=?", (client_id,)).fetchone()
    if not row:
        raise OwnerOperationError("client_unknown", "The registered automation client is not recognized.", 401)
    if active:
        expires = _parse_iso(row["expires_at"])
        if str(row["status"] or "") != "active" or (expires and expires <= _now()):
            raise OwnerOperationError("client_revoked", "The registered automation client is no longer active.", 403)
    return row


def _record_event(
    tx: Any,
    *,
    operation_id: str,
    actor_type: str,
    actor_id: str = "",
    event_type: str,
    reason_code: str = "",
    summary: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    tx.execute(
        """INSERT INTO owner_operation_events(
               operation_id,occurred_at,actor_type,actor_id,event_type,reason_code,summary,evidence_json
           ) VALUES (?,?,?,?,?,?,?,?)""",
        (
            operation_id,
            _iso(),
            actor_type,
            str(actor_id or "")[:120],
            str(event_type)[:80],
            str(reason_code or "")[:80],
            str(summary)[:240],
            _canonical(evidence or {}),
        ),
    )


def _audit_human(tx: Any, *, human_id: str, session_id: str, event_type: str, reason_code: str, summary: str, operation_id: str) -> None:
    lite_identity_auth._audit(
        tx,
        human_id=human_id,
        session_id=session_id,
        event_type=event_type,
        reason_code=reason_code,
        summary=summary,
        correlation_id=operation_id,
    )


def _owner_context(
    auth_context: dict[str, Any],
    *,
    assurance: bool = False,
    assurance_purpose: str = OWNER_APPROVAL_PURPOSE,
) -> tuple[dict[str, Any], str, str, dict[str, Any] | None]:
    context = lite_enterprise_identity.enrich_auth_context(auth_context or {})
    if deps.is_qualification_owner_context(context):
        raise OwnerOperationError("synthetic_owner_forbidden", "Qualification authentication cannot approve production operations.", 403)
    actor = context.get("actor") or {}
    session = context.get("session") or {}
    authorization = context.get("authorization") or {}
    human_id = str(actor.get("identity_id") or "")
    session_id = str(session.get("session_id") or "")
    if actor.get("type") != "human" or not human_id or not session_id or session.get("authenticated") is not True:
        raise OwnerOperationError("human_session_required", "A signed-in Owner session is required.", 401)
    if authorization.get("enterprise_enabled"):
        if authorization.get("role") != "Owner" or authorization.get("membership_active") is not True:
            raise OwnerOperationError("owner_required", "Only an active Owner can approve this operation.", 403)
    else:
        with connection() as conn:
            row = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at ASC LIMIT 1").fetchone()
        if not row or str(row["human_id"]) != human_id:
            raise OwnerOperationError("owner_required", "Only the local Pocket Lab Owner can approve this operation.", 403)
    assurance_item = None
    if assurance:
        try:
            lite_enterprise_governance.require_recent_assurance(context, assurance_purpose)
        except lite_enterprise_governance.GovernanceError as exc:
            raise OwnerOperationError(exc.reason_code, exc.message, exc.status_code) from exc
        for item in session.get("assurance") or []:
            if isinstance(item, dict) and item.get("purpose") == assurance_purpose:
                assurance_item = item
                break
        if not assurance_item:
            raise OwnerOperationError("owner_step_up_required", "Confirm this protected change with your passkey first.", 428)
    return context, human_id, session_id, assurance_item


def _challenge_binding_digest(binding: dict[str, Any]) -> str:
    return _digest(binding)


def _issue_challenge(
    *,
    client_id: str,
    purpose: str,
    binding: dict[str, Any],
    operation_id: str | None = None,
    require_active_client: bool,
    ttl_seconds: int,
) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    binding_json = _canonical(binding)
    binding_digest = _challenge_binding_digest(binding)
    now = _now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    challenge_id = f"oo-challenge-{secrets.token_hex(12)}"
    nonce = secrets.token_urlsafe(32)
    signing_payload = {
        "contract": "owner-operation-client-proof.v1",
        "challenge_id": challenge_id,
        "client_id": client_id,
        "purpose": purpose,
        "binding_digest": binding_digest,
        "nonce": nonce,
        "issued_at": _iso(now),
        "expires_at": _iso(expires_at),
        "operation_id": str(operation_id or ""),
    }
    signing_payload_json = _canonical(signing_payload)
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            if require_active_client:
                _client_row(tx, client_id)
            active = tx.execute(
                "SELECT COUNT(*) AS count FROM owner_operation_challenges WHERE client_id=? AND consumed_at IS NULL AND expires_at>?",
                (client_id, _iso(now)),
            ).fetchone()
            if int(active["count"] or 0) >= MAX_ACTIVE_CHALLENGES:
                raise OwnerOperationError("challenge_rate_limited", "Too many active client challenges. Try again shortly.", 429)
            tx.execute(
                """INSERT INTO owner_operation_challenges(
                       challenge_id,client_id,purpose,operation_id,binding_json,binding_digest,
                       signing_payload_json,nonce_hash,issued_at,expires_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    challenge_id,
                    client_id,
                    purpose,
                    operation_id,
                    binding_json,
                    binding_digest,
                    signing_payload_json,
                    _digest(nonce),
                    _iso(now),
                    _iso(expires_at),
                ),
            )
    return {
        "status": "challenge_issued",
        "challenge_id": challenge_id,
        "client_id": client_id,
        "purpose": purpose,
        "expires_at": _iso(expires_at),
        "signing_payload": signing_payload_json,
        "sanitized": True,
    }


def issue_registration_challenge(auth_context: dict[str, Any], *, client_id: str, public_key: str) -> dict[str, Any]:
    _owner_context(auth_context, assurance=False)
    client_id = _safe_id(client_id, kind="client")
    key_bytes = _public_key_bytes(public_key)
    fingerprint = f"sha256:{hashlib.sha256(key_bytes).hexdigest()}"
    binding = {
        "registration_mode": "owner",
        "client_id": client_id,
        "public_key": _b64encode(key_bytes),
        "fingerprint": fingerprint,
    }
    return _issue_challenge(
        client_id=client_id,
        purpose="client_registration",
        binding=binding,
        require_active_client=False,
        ttl_seconds=CLIENT_CHALLENGE_TTL_SECONDS,
    )


def _challenge_failure(tx: Any, row: Any, reason_code: str, message: str, status_code: int = 401) -> None:
    failures = int(row["failed_attempts"] or 0) + 1
    consumed_at = _iso() if failures >= MAX_CHALLENGE_FAILURES else None
    tx.execute(
        "UPDATE owner_operation_challenges SET failed_attempts=?,consumed_at=COALESCE(consumed_at,?) WHERE challenge_id=? AND consumed_at IS NULL",
        (failures, consumed_at, row["challenge_id"]),
    )
    raise OwnerOperationError(reason_code, message, status_code)


def _consume_signed_challenge(
    tx: Any,
    *,
    challenge_id: str,
    purpose: str,
    client_id: str,
    public_key: bytes,
    signature: bytes,
    binding: dict[str, Any],
    operation_id: str | None = None,
) -> Any:
    row = tx.execute(
        "SELECT * FROM owner_operation_challenges WHERE challenge_id=? LIMIT 1",
        (challenge_id,),
    ).fetchone()
    if not row:
        raise OwnerOperationError("challenge_unknown", "The client challenge is not recognized.", 401)
    if row["purpose"] != purpose or row["client_id"] != client_id or (operation_id and row["operation_id"] != operation_id):
        _challenge_failure(tx, row, "challenge_binding_invalid", "The client challenge is bound to a different request.")
    if row["consumed_at"]:
        raise OwnerOperationError("challenge_replayed", "The client challenge has already been used.", 409)
    expires_at = _parse_iso(row["expires_at"])
    if not expires_at or expires_at <= _now():
        _challenge_failure(tx, row, "challenge_expired", "The client challenge has expired.", 401)
    expected_binding = _canonical(binding)
    if expected_binding != str(row["binding_json"] or ""):
        _challenge_failure(tx, row, "request_binding_invalid", "The signed request scope did not match the issued challenge.", 409)
    if _digest(str(json.loads(str(row["signing_payload_json"] or "{}")).get("nonce") or "")) != str(row["nonce_hash"] or ""):
        _challenge_failure(tx, row, "challenge_invalid", "The client challenge is not valid.", 401)
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, str(row["signing_payload_json"]).encode("utf-8"))
    except (InvalidSignature, ValueError) as exc:
        _challenge_failure(tx, row, "signature_invalid", "The client signature was not accepted.", 401)
        raise AssertionError("unreachable") from exc
    tx.execute(
        "UPDATE owner_operation_challenges SET consumed_at=? WHERE challenge_id=? AND consumed_at IS NULL",
        (_iso(), challenge_id),
    )
    if tx.execute("SELECT changes() AS count").fetchone()["count"] != 1:
        raise OwnerOperationError("challenge_replayed", "The client challenge has already been used.", 409)
    return row


def register_client(
    auth_context: dict[str, Any],
    *,
    client_id: str,
    display_name: str,
    public_key: str,
    challenge_id: str,
    signature: str,
) -> dict[str, Any]:
    _context, human_id, session_id, _assurance = _owner_context(
        auth_context,
        assurance=True,
        assurance_purpose=CLIENT_REGISTRATION_PURPOSE,
    )
    client_id = _safe_id(client_id, kind="client")
    display_name = _validate_text(display_name, name="display_name", maximum=120)
    key_bytes = _public_key_bytes(public_key)
    canonical_key = _b64encode(key_bytes)
    fingerprint = f"sha256:{hashlib.sha256(key_bytes).hexdigest()}"
    challenge_id = _safe_id(challenge_id, kind="challenge")
    signature_bytes = _signature_bytes(signature)
    binding = {
        "registration_mode": "owner",
        "client_id": client_id,
        "public_key": canonical_key,
        "fingerprint": fingerprint,
    }
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _consume_signed_challenge(
                tx,
                challenge_id=challenge_id,
                purpose="client_registration",
                client_id=client_id,
                public_key=key_bytes,
                signature=signature_bytes,
                binding=binding,
            )
            existing = tx.execute("SELECT * FROM owner_operation_clients WHERE client_id=?", (client_id,)).fetchone()
            if existing:
                if existing["public_key_fingerprint"] != fingerprint:
                    raise OwnerOperationError("client_id_conflict", "That client identity is already bound to another key.", 409)
                if existing["status"] != "active":
                    raise OwnerOperationError("client_revoked", "A revoked client identity cannot be silently reactivated.", 403)
                result = _client_projection(existing)
                result["idempotent"] = True
                return result
            duplicate_key = tx.execute(
                "SELECT client_id FROM owner_operation_clients WHERE public_key_fingerprint=? LIMIT 1",
                (fingerprint,),
            ).fetchone()
            if duplicate_key:
                raise OwnerOperationError("public_key_registered", "That public key is already registered to another client.", 409)
            now = _iso()
            tx.execute(
                """INSERT INTO owner_operation_clients(
                       client_id,display_name,public_key,public_key_fingerprint,capabilities_json,
                       status,created_by_human_id,created_at
                   ) VALUES (?,?,?,?,?,?,?,?)""",
                (client_id, display_name, canonical_key, fingerprint, _canonical([OPERATION_TYPE]), "active", human_id, now),
            )
            _audit_human(
                tx,
                human_id=human_id,
                session_id=session_id,
                event_type="owner_operation.client_registered",
                reason_code="owner_confirmed",
                summary="A bounded automation client was registered with server-owned capability scope.",
                operation_id=f"client:{client_id}",
            )
            row = tx.execute("SELECT * FROM owner_operation_clients WHERE client_id=?", (client_id,)).fetchone()
            return _client_projection(row)


def _pairing_row(conn: Any, pairing_id: str) -> Any:
    pairing_id = _safe_id(pairing_id, kind="pairing")
    row = conn.execute(
        "SELECT * FROM owner_operation_client_pairings WHERE pairing_id=? LIMIT 1",
        (pairing_id,),
    ).fetchone()
    if not row:
        raise OwnerOperationError("pairing_not_found", "The automation-client pairing was not found.", 404)
    return row


def _pairing_event(
    tx: Any,
    *,
    pairing_id: str,
    actor_type: str,
    actor_id: str = "",
    event_type: str,
    reason_code: str = "",
    summary: str,
) -> None:
    tx.execute(
        """INSERT INTO owner_operation_client_pairing_events(
               pairing_id,occurred_at,actor_type,actor_id,event_type,reason_code,summary
           ) VALUES (?,?,?,?,?,?,?)""",
        (
            pairing_id,
            _iso(),
            actor_type,
            str(actor_id or "")[:120],
            str(event_type)[:80],
            str(reason_code or "")[:80],
            str(summary)[:240],
        ),
    )


def _pairing_binding(*, client_id: str, display_name: str, canonical_key: str, fingerprint: str) -> dict[str, Any]:
    return {
        "registration_mode": "pairing",
        "client_id": client_id,
        "display_name": display_name,
        "public_key": canonical_key,
        "fingerprint": fingerprint,
        "capabilities": [OPERATION_TYPE],
    }


def _pairing_projection(row: Any) -> dict[str, Any]:
    if not row:
        return {"status": "unknown", "sanitized": True}
    status = str(row["status"] or "unknown")
    expires_at = _parse_iso(row["expires_at"])
    if status == "pending" and expires_at and expires_at <= _now():
        status = "expired"
    return {
        "status": status,
        "pairing_id": str(row["pairing_id"]),
        "client_id": str(row["client_id"]),
        "display_name": str(row["display_name"]),
        "public_key_fingerprint": str(row["public_key_fingerprint"]),
        "capabilities": [OPERATION_TYPE],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "reviewed_at": row["reviewed_at"],
        "registered_at": row["registered_at"],
        "terminal_reason": row["terminal_reason"] or None,
        "updated_at": row["updated_at"],
        "sanitized": True,
    }


def _pairing_events(conn: Any, pairing_id: str) -> list[dict[str, Any]]:
    return [
        {
            "occurred_at": row["occurred_at"],
            "event_type": row["event_type"],
            "reason_code": row["reason_code"],
            "summary": row["summary"],
        }
        for row in conn.execute(
            """SELECT occurred_at,event_type,reason_code,summary
               FROM owner_operation_client_pairing_events
               WHERE pairing_id=? ORDER BY event_id DESC LIMIT 20""",
            (pairing_id,),
        )
    ]


def issue_client_pairing_challenge(*, client_id: str, display_name: str, public_key: str) -> dict[str, Any]:
    """Issue proof material for a candidate; it grants no operation authority."""
    client_id = _safe_id(client_id, kind="client")
    display_name = _validate_text(display_name, name="display_name", maximum=120)
    key_bytes = _public_key_bytes(public_key)
    canonical_key = _b64encode(key_bytes)
    fingerprint = f"sha256:{hashlib.sha256(key_bytes).hexdigest()}"
    binding = _pairing_binding(
        client_id=client_id,
        display_name=display_name,
        canonical_key=canonical_key,
        fingerprint=fingerprint,
    )
    _ensure_db()
    with connection() as conn:
        active_client = conn.execute(
            "SELECT status FROM owner_operation_clients WHERE client_id=? LIMIT 1",
            (client_id,),
        ).fetchone()
        if active_client:
            raise OwnerOperationError(
                "client_id_registered",
                "That automation-client identity is already registered or was revoked.",
                409,
            )
        duplicate = conn.execute(
            """SELECT pairing_id,status FROM owner_operation_client_pairings
               WHERE public_key_fingerprint=? AND status IN ('pending','registered') LIMIT 1""",
            (fingerprint,),
        ).fetchone()
        if duplicate and str(duplicate["status"]) == "registered":
            raise OwnerOperationError("public_key_registered", "That public key is already registered.", 409)
    return _issue_challenge(
        client_id=client_id,
        purpose="client_registration",
        binding=binding,
        require_active_client=False,
        ttl_seconds=CLIENT_CHALLENGE_TTL_SECONDS,
    )


def request_client_pairing(
    *,
    client_id: str,
    display_name: str,
    public_key: str,
    challenge_id: str,
    signature: str,
) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    display_name = _validate_text(display_name, name="display_name", maximum=120)
    key_bytes = _public_key_bytes(public_key)
    canonical_key = _b64encode(key_bytes)
    fingerprint = f"sha256:{hashlib.sha256(key_bytes).hexdigest()}"
    challenge_id = _safe_id(challenge_id, kind="challenge")
    signature_bytes = _signature_bytes(signature)
    binding = _pairing_binding(
        client_id=client_id,
        display_name=display_name,
        canonical_key=canonical_key,
        fingerprint=fingerprint,
    )
    binding_digest = _digest(binding)
    _ensure_db()
    now = _now()
    expires_at = now + timedelta(seconds=PAIRING_TTL_SECONDS)
    pairing_id = f"ocp-{secrets.token_hex(12)}"
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _consume_signed_challenge(
                tx,
                challenge_id=challenge_id,
                purpose="client_registration",
                client_id=client_id,
                public_key=key_bytes,
                signature=signature_bytes,
                binding=binding,
            )
            existing_client = tx.execute(
                "SELECT status FROM owner_operation_clients WHERE client_id=? LIMIT 1",
                (client_id,),
            ).fetchone()
            if existing_client:
                raise OwnerOperationError(
                    "client_id_registered",
                    "That automation-client identity is already registered or was revoked.",
                    409,
                )
            duplicate = tx.execute(
                """SELECT * FROM owner_operation_client_pairings
                   WHERE public_key_fingerprint=? AND status IN ('pending','registered') LIMIT 1""",
                (fingerprint,),
            ).fetchone()
            if duplicate and (
                str(duplicate["client_id"]) != client_id
                or str(duplicate["display_name"]) != display_name
                or str(duplicate["pairing_binding_digest"]) != binding_digest
            ):
                raise OwnerOperationError("public_key_pending", "That public key is already paired to another candidate.", 409)
            if duplicate:
                result = _pairing_projection(duplicate)
                result["idempotent"] = True
                return result
            pending_client = tx.execute(
                "SELECT pairing_id FROM owner_operation_client_pairings WHERE client_id=? AND status='pending' LIMIT 1",
                (client_id,),
            ).fetchone()
            if pending_client:
                raise OwnerOperationError("client_id_pending", "That automation-client identity already has a pending pairing.", 409)
            try:
                tx.execute(
                    """INSERT INTO owner_operation_client_pairings(
                           pairing_id,client_id,display_name,public_key,public_key_fingerprint,
                           capabilities_json,pairing_binding_digest,status,created_at,expires_at,updated_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pairing_id,
                        client_id,
                        display_name,
                        canonical_key,
                        fingerprint,
                        _canonical([OPERATION_TYPE]),
                        binding_digest,
                        "pending",
                        _iso(now),
                        _iso(expires_at),
                        _iso(now),
                    ),
                )
            except Exception as exc:
                raise OwnerOperationError("pairing_conflict", "The automation-client pairing could not be recorded safely.", 409) from exc
            _pairing_event(
                tx,
                pairing_id=pairing_id,
                actor_type="requester",
                actor_id=client_id,
                event_type="pairing_requested",
                reason_code="proof_verified",
                summary="A cryptographically verified automation-client pairing is waiting for Owner review.",
            )
            result = _pairing_projection(tx.execute("SELECT * FROM owner_operation_client_pairings WHERE pairing_id=?", (pairing_id,)).fetchone())
            result["idempotent"] = False
            return result


def client_pairing_policy_target(pairing_id: str) -> dict[str, Any]:
    _mark_expired_pairings()
    _ensure_db()
    with connection() as conn:
        row = _pairing_row(conn, pairing_id)
    status = _pairing_projection(row)["status"]
    return {
        "type": "owner_operation_client_pairing",
        "id": str(row["pairing_id"]),
        "revision": str(row["pairing_binding_digest"]),
        "state": {
            "registration_mode": "pairing",
            "client_id": str(row["client_id"]),
            "public_key_fingerprint": str(row["public_key_fingerprint"]),
            "capabilities": [OPERATION_TYPE],
            "status": status,
            "expires_at": str(row["expires_at"]),
            "pairing_binding_digest": str(row["pairing_binding_digest"]),
        },
    }


def client_policy_target(client_id: str, *, mode: str = "revoke") -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    _ensure_db()
    with connection() as conn:
        row = _client_row(conn, client_id, active=False)
    return {
        "type": "owner_operation_client",
        "id": client_id,
        "revision": str(row["public_key_fingerprint"]),
        "state": {
            "registration_mode": mode,
            "client_id": client_id,
            "public_key_fingerprint": str(row["public_key_fingerprint"]),
            "capabilities": [OPERATION_TYPE],
            "status": str(row["status"]),
        },
    }


def approve_client_pairing(auth_context: dict[str, Any], pairing_id: str) -> dict[str, Any]:
    _context, human_id, session_id, assurance_item = _owner_context(
        auth_context,
        assurance=True,
        assurance_purpose=CLIENT_REGISTRATION_PURPOSE,
    )
    pairing_id = _safe_id(pairing_id, kind="pairing")
    _mark_expired_pairings()
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _pairing_row(tx, pairing_id)
            if row["status"] != "pending":
                raise OwnerOperationError("pairing_not_pending", "This automation-client pairing is no longer waiting for registration.", 409)
            if (_parse_iso(row["expires_at"]) or _now()) <= _now():
                tx.execute(
                    "UPDATE owner_operation_client_pairings SET status='expired',terminal_reason='pairing_expired',updated_at=? WHERE pairing_id=? AND status='pending'",
                    (_iso(), pairing_id),
                )
                _pairing_event(tx, pairing_id=pairing_id, actor_type="system", event_type="expired", reason_code="pairing_expired", summary="The automation-client pairing expired before Owner registration.")
                raise OwnerOperationError("pairing_expired", "This automation-client pairing has expired.", 409)
            key_bytes = _public_key_bytes(row["public_key"])
            fingerprint = f"sha256:{hashlib.sha256(key_bytes).hexdigest()}"
            binding = _pairing_binding(
                client_id=str(row["client_id"]),
                display_name=str(row["display_name"]),
                canonical_key=_b64encode(key_bytes),
                fingerprint=fingerprint,
            )
            if fingerprint != str(row["public_key_fingerprint"]) or _digest(binding) != str(row["pairing_binding_digest"]):
                tx.execute(
                    "UPDATE owner_operation_client_pairings SET status='rejected',terminal_reason='pairing_binding_invalid',updated_at=? WHERE pairing_id=? AND status='pending'",
                    (_iso(), pairing_id),
                )
                _pairing_event(tx, pairing_id=pairing_id, actor_type="system", event_type="rejected", reason_code="pairing_binding_invalid", summary="The pairing binding could not be revalidated and was stopped safely.")
                raise OwnerOperationError("pairing_binding_invalid", "The pairing binding is no longer valid.", 409)
            existing = tx.execute(
                "SELECT * FROM owner_operation_clients WHERE client_id=? OR public_key_fingerprint=? LIMIT 1",
                (str(row["client_id"]), fingerprint),
            ).fetchone()
            if existing:
                raise OwnerOperationError("client_id_conflict", "That client identity or public key is already registered.", 409)
            now = _now()
            try:
                tx.execute(
                    """INSERT INTO owner_operation_clients(
                           client_id,display_name,public_key,public_key_fingerprint,capabilities_json,
                           status,created_by_human_id,created_at
                       ) VALUES (?,?,?,?,?,?,?,?)""",
                    (str(row["client_id"]), str(row["display_name"]), _b64encode(key_bytes), fingerprint, _canonical([OPERATION_TYPE]), "active", human_id, now),
                )
            except Exception as exc:
                raise OwnerOperationError("client_id_conflict", "The client could not be registered without a duplicate identity.", 409) from exc
            assurance_ref = _assurance_reference(assurance_item)
            updated = tx.execute(
                """UPDATE owner_operation_client_pairings
                   SET status='registered',reviewed_by_human_id=?,reviewed_at=?,approval_assurance_ref=?,registered_at=?,updated_at=?
                   WHERE pairing_id=? AND status='pending'""",
                (human_id, now, assurance_ref, now, now, pairing_id),
            )
            if updated.rowcount != 1:
                raise OwnerOperationError("pairing_decision_race", "The pairing decision was already handled by another request.", 409)
            _pairing_event(tx, pairing_id=pairing_id, actor_type="owner", actor_id=human_id, event_type="registered", reason_code="owner_confirmed", summary="Owner registered the exact cryptographically verified automation client.")
            _audit_human(
                tx,
                human_id=human_id,
                session_id=session_id,
                event_type="owner_operation.client_pairing_registered",
                reason_code="owner_confirmed",
                summary="Owner registered a bounded automation client after passkey confirmation.",
                operation_id=f"pairing:{pairing_id}",
            )
            client = tx.execute("SELECT * FROM owner_operation_clients WHERE client_id=?", (str(row["client_id"]),)).fetchone()
            pairing = _pairing_projection(tx.execute("SELECT * FROM owner_operation_client_pairings WHERE pairing_id=?", (pairing_id,)).fetchone())
            return {"status": "registered", "pairing": pairing, "client": _client_projection(client, include_fingerprint=True), "sanitized": True}


def reject_client_pairing(auth_context: dict[str, Any], pairing_id: str, *, reason: str = "owner_rejected") -> dict[str, Any]:
    _context, human_id, session_id, _assurance = _owner_context(auth_context, assurance=False)
    pairing_id = _safe_id(pairing_id, kind="pairing")
    safe_reason = _validate_text(reason, name="reason", maximum=80)
    _mark_expired_pairings()
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _pairing_row(tx, pairing_id)
            if row["status"] != "pending":
                raise OwnerOperationError("pairing_not_pending", "This automation-client pairing is no longer waiting for a decision.", 409)
            updated = tx.execute(
                "UPDATE owner_operation_client_pairings SET status='rejected',terminal_reason=?,reviewed_by_human_id=?,reviewed_at=?,updated_at=? WHERE pairing_id=? AND status='pending'",
                (safe_reason, human_id, _iso(), _iso(), pairing_id),
            )
            if updated.rowcount != 1:
                raise OwnerOperationError("pairing_decision_race", "The pairing decision was already handled.", 409)
            _pairing_event(tx, pairing_id=pairing_id, actor_type="owner", actor_id=human_id, event_type="rejected", reason_code=safe_reason, summary="Owner rejected the automation-client pairing.")
            _audit_human(tx, human_id=human_id, session_id=session_id, event_type="owner_operation.client_pairing_rejected", reason_code=safe_reason, summary="Owner rejected a bounded automation-client pairing request.", operation_id=f"pairing:{pairing_id}")
            return _pairing_projection(tx.execute("SELECT * FROM owner_operation_client_pairings WHERE pairing_id=?", (pairing_id,)).fetchone())


def issue_client_pairing_cancel_challenge(*, client_id: str, pairing_id: str) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    pairing_id = _safe_id(pairing_id, kind="pairing")
    _mark_expired_pairings()
    _ensure_db()
    with connection() as conn:
        row = _pairing_row(conn, pairing_id)
        if row["client_id"] != client_id:
            raise OwnerOperationError("pairing_forbidden", "The pairing is not available to this requester.", 403)
        if row["status"] != "pending":
            raise OwnerOperationError("pairing_not_cancellable", "The pairing is already terminal.", 409)
    return _issue_challenge(
        client_id=client_id,
        purpose="cancel",
        binding={"registration_mode": "pairing_cancel", "pairing_id": pairing_id, "status_at_issue": "pending"},
        operation_id=pairing_id,
        require_active_client=False,
        ttl_seconds=REQUEST_CHALLENGE_TTL_SECONDS,
    )


def cancel_client_pairing(*, client_id: str, pairing_id: str, challenge_id: str, signature: str) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    pairing_id = _safe_id(pairing_id, kind="pairing")
    challenge_id = _safe_id(challenge_id, kind="challenge")
    signature_bytes = _signature_bytes(signature)
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _pairing_row(tx, pairing_id)
            if row["client_id"] != client_id:
                raise OwnerOperationError("pairing_forbidden", "The pairing is not available to this requester.", 403)
            if row["status"] != "pending":
                raise OwnerOperationError("pairing_not_cancellable", "The pairing is already terminal.", 409)
            _consume_signed_challenge(
                tx,
                challenge_id=challenge_id,
                purpose="cancel",
                client_id=client_id,
                public_key=_public_key_bytes(row["public_key"]),
                signature=signature_bytes,
                binding={"registration_mode": "pairing_cancel", "pairing_id": pairing_id, "status_at_issue": "pending"},
                operation_id=pairing_id,
            )
            tx.execute(
                "UPDATE owner_operation_client_pairings SET status='cancelled',terminal_reason='requester_cancelled',updated_at=? WHERE pairing_id=? AND status='pending'",
                (_iso(), pairing_id),
            )
            _pairing_event(tx, pairing_id=pairing_id, actor_type="requester", actor_id=client_id, event_type="cancelled", reason_code="requester_cancelled", summary="The requester cancelled the pending automation-client pairing.")
            return _pairing_projection(tx.execute("SELECT * FROM owner_operation_client_pairings WHERE pairing_id=?", (pairing_id,)).fetchone())


def issue_client_pairing_observer_challenge(*, client_id: str, pairing_id: str) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    pairing_id = _safe_id(pairing_id, kind="pairing")
    _mark_expired_pairings()
    _ensure_db()
    with connection() as conn:
        row = _pairing_row(conn, pairing_id)
        if row["client_id"] != client_id:
            raise OwnerOperationError("pairing_not_found", "The pairing is not available to this requester.", 404)
        status = _pairing_projection(row)["status"]
    return _issue_challenge(
        client_id=client_id,
        purpose="observe",
        binding={"registration_mode": "pairing_observe", "pairing_id": pairing_id, "status_at_issue": status},
        operation_id=pairing_id,
        require_active_client=False,
        ttl_seconds=REQUEST_CHALLENGE_TTL_SECONDS,
    )


def observe_client_pairing(*, client_id: str, pairing_id: str, challenge_id: str, signature: str) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    pairing_id = _safe_id(pairing_id, kind="pairing")
    challenge_id = _safe_id(challenge_id, kind="challenge")
    signature_bytes = _signature_bytes(signature)
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _pairing_row(tx, pairing_id)
            if row["client_id"] != client_id:
                raise OwnerOperationError("pairing_forbidden", "The pairing is not available to this requester.", 403)
            status = _pairing_projection(row)["status"]
            _consume_signed_challenge(
                tx,
                challenge_id=challenge_id,
                purpose="observe",
                client_id=client_id,
                public_key=_public_key_bytes(row["public_key"]),
                signature=signature_bytes,
                binding={"registration_mode": "pairing_observe", "pairing_id": pairing_id, "status_at_issue": status},
                operation_id=pairing_id,
            )
            result = _pairing_projection(row)
            if result["status"] == "registered":
                client = tx.execute("SELECT * FROM owner_operation_clients WHERE client_id=?", (client_id,)).fetchone()
                result["client"] = _client_projection(client, include_fingerprint=True)
            result["events"] = _pairing_events(tx, pairing_id)
            return result


def _mark_expired_pairings() -> int:
    _ensure_db()
    now = _iso()
    changed = 0
    with connection() as conn:
        with begin_immediate(conn) as tx:
            rows = tx.execute(
                "SELECT pairing_id FROM owner_operation_client_pairings WHERE status='pending' AND expires_at<=?",
                (now,),
            ).fetchall()
            for row in rows:
                pairing_id = str(row["pairing_id"])
                updated = tx.execute(
                    "UPDATE owner_operation_client_pairings SET status='expired',terminal_reason='pairing_expired',updated_at=? WHERE pairing_id=? AND status='pending'",
                    (now, pairing_id),
                )
                if updated.rowcount == 1:
                    _pairing_event(tx, pairing_id=pairing_id, actor_type="system", event_type="expired", reason_code="pairing_expired", summary="The automation-client pairing expired before Owner registration.")
                    changed += 1
    return changed


def revoke_client(auth_context: dict[str, Any], *, client_id: str, reason: str = "owner_revoked") -> dict[str, Any]:
    _context, human_id, session_id, _assurance = _owner_context(
        auth_context,
        assurance=True,
        assurance_purpose=CLIENT_REGISTRATION_PURPOSE,
    )
    client_id = _safe_id(client_id, kind="client")
    safe_reason = _validate_text(reason, name="reason", maximum=80)
    _ensure_db()
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _client_row(tx, client_id, active=False)
            if row["status"] == "revoked":
                return {"status": "revoked", "client_id": client_id, "idempotent": True, "sanitized": True}
            tx.execute(
                "UPDATE owner_operation_clients SET status='revoked',revoked_at=?,revoke_reason=? WHERE client_id=? AND status='active'",
                (now, safe_reason, client_id),
            )
            tx.execute(
                "UPDATE owner_operation_challenges SET consumed_at=? WHERE client_id=? AND consumed_at IS NULL",
                (now, client_id),
            )
            affected = tx.execute(
                "SELECT operation_id,status FROM owner_approved_operations WHERE requester_client_id=? AND status IN ('pending_approval','approved','executing','verifying')",
                (client_id,),
            ).fetchall()
            tx.execute(
                "UPDATE owner_approved_operations SET status=CASE WHEN status IN ('pending_approval','approved') THEN 'cancelled' ELSE status END,terminal_reason='requester_revoked',updated_at=? WHERE requester_client_id=? AND status IN ('pending_approval','approved','executing','verifying')",
                (now, client_id),
            )
            for item in affected:
                _record_event(
                    tx,
                    operation_id=str(item["operation_id"]),
                    actor_type="system",
                    actor_id=client_id,
                    event_type="cancel_requested",
                    reason_code="requester_revoked",
                    summary="The registered requester was revoked; the bounded workflow cannot continue.",
                )
            _audit_human(
                tx,
                human_id=human_id,
                session_id=session_id,
                event_type="owner_operation.client_revoked",
                reason_code=safe_reason,
                summary="A registered bounded automation client was revoked.",
                operation_id=f"client:{client_id}",
            )
    return {"status": "revoked", "client_id": client_id, "sanitized": True}


def _client_projection(row: Any, *, include_fingerprint: bool = False) -> dict[str, Any]:
    if not row:
        return {"status": "unknown", "sanitized": True}
    result = {
        "status": str(row["status"] or "unknown"),
        "client_id": str(row["client_id"]),
        "display_name": str(row["display_name"]),
        "capabilities": [OPERATION_TYPE],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "revoked_at": row["revoked_at"],
        "sanitized": True,
    }
    if include_fingerprint:
        result["public_key_fingerprint"] = str(row["public_key_fingerprint"])
    return result


def issue_request_challenge(*, client_id: str, descriptor: Any) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    normalized = normalize_descriptor(descriptor, expected_client_id=client_id)
    target = _target_binding(normalized["target_node_id"])
    binding = {
        "descriptor": normalized,
        "target_binding_digest": target["binding_digest"],
        "target_identity_revision": target["identity_revision"],
    }
    return _issue_challenge(
        client_id=client_id,
        purpose="request",
        binding=binding,
        require_active_client=True,
        ttl_seconds=REQUEST_CHALLENGE_TTL_SECONDS,
    )


def issue_observer_challenge(*, client_id: str, operation_id: str, purpose: str = "observe") -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    operation_id = _safe_id(operation_id, kind="operation")
    if purpose not in {"observe", "cancel"}:
        raise OwnerOperationError("challenge_purpose_invalid", "The client challenge purpose is not supported.", 422)
    _ensure_db()
    with connection() as conn:
        row = conn.execute(
            "SELECT operation_id,requester_client_id,status FROM owner_approved_operations WHERE operation_id=? LIMIT 1",
            (operation_id,),
        ).fetchone()
        if not row or row["requester_client_id"] != client_id:
            raise OwnerOperationError("operation_not_found", "The operation is not available to this client.", 404)
        if purpose == "cancel" and row["status"] not in {"pending_approval", "approved"}:
            raise OwnerOperationError("operation_not_cancellable", "The operation is already executing or terminal.", 409)
    return _issue_challenge(
        client_id=client_id,
        purpose=purpose,
        binding={"operation_id": operation_id, "status_at_issue": str(row["status"])},
        operation_id=operation_id,
        require_active_client=True,
        ttl_seconds=REQUEST_CHALLENGE_TTL_SECONDS,
    )


def _operation_row(conn: Any, operation_id: str) -> Any:
    operation_id = _safe_id(operation_id, kind="operation")
    row = conn.execute(
        """SELECT o.*,c.display_name AS requester_display_name,c.status AS requester_status,c.expires_at AS requester_expires_at
           FROM owner_approved_operations o
           JOIN owner_operation_clients c ON c.client_id=o.requester_client_id
           WHERE o.operation_id=? LIMIT 1""",
        (operation_id,),
    ).fetchone()
    if not row:
        raise OwnerOperationError("operation_not_found", "The operation was not found.", 404)
    return row


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _parse_evidence(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError):
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _scope(row: Any) -> dict[str, Any]:
    try:
        value = json.loads(str(row["scope_json"] or "{}"))
    except (TypeError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def _operation_disclosures(row: Any) -> list[str]:
    return [
        "Targets the selected Secondary Phone only.",
        "Uses PhotoPrism originals on this server as the fixed destination.",
        "May create the persistent destination identity anchor if it is absent.",
        "Creates one server-issued synthetic JPEG in the fixed Pictures scope.",
        "The destination test photo may remain as retained backup media.",
        "Performs one safe idempotent repeat of the same fixture.",
        f"Approval expires at {row['approval_deadline']} and cannot become a permanent backup permission.",
        "No personal pictures, arbitrary paths, URLs, commands, or collection-wide backup are included.",
    ]


def _target_label(node_id: str) -> str:
    """Return a server-owned display label without widening the target scope."""
    try:
        agent = fleet_registry.get_agent(str(node_id))
        if isinstance(agent, dict):
            return str(agent.get("name") or agent.get("hostname") or node_id).strip()[:80] or str(node_id)
    except Exception:
        pass
    return str(node_id)


def _public_operation(row: Any, *, audience: str = "owner") -> dict[str, Any]:
    evidence = _parse_evidence(row["evidence_json"])
    status = str(row["status"] or "unknown")
    approval_deadline = _parse_iso(row["approval_deadline"])
    execution_deadline = _parse_iso(row["execution_deadline"])
    if status == "pending_approval" and approval_deadline and approval_deadline <= _now():
        status = "expired"
    elif status in {"approved", "executing", "verifying"} and execution_deadline and execution_deadline <= _now() and str(row["execution_stage"] or "") in {"awaiting_initial", "dispatching_initial"}:
        status = "blocked"
    result = {
        "operation_id": row["operation_id"],
        "contract_version": int(row["contract_version"]),
        "operation": row["operation_type"],
        "status": status,
        "requester_id": row["requester_client_id"] if audience == "owner" else None,
        "requester_display_name": row["requester_display_name"] if audience == "owner" else "Registered qualification client",
        "target_node_id": row["target_node_id"],
        "target_label": _target_label(str(row["target_node_id"])),
        "destination": "PhotoPrism on this server",
        "scope": _scope(row),
        "reason": row["reason"],
        "approval_deadline": row["approval_deadline"],
        "approved_at": row["approved_at"],
        "execution_deadline": row["execution_deadline"],
        "execution_stage": row["execution_stage"],
        "backup_id": row["backup_id"],
        "repeat_backup_id": row["repeat_backup_id"],
        "terminal_reason": row["terminal_reason"] or None,
        "disclosures": _operation_disclosures(row),
        "evidence": evidence,
        "updated_at": row["updated_at"],
        "sanitized": True,
    }
    if audience == "owner":
        result["requester_active"] = row["requester_status"] == "active"
    return result


def _event_projection(conn: Any, operation_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT occurred_at,event_type,reason_code,summary FROM owner_operation_events WHERE operation_id=? ORDER BY event_id DESC LIMIT 20",
        (operation_id,),
    ):
        items.append({
            "occurred_at": row["occurred_at"],
            "event_type": row["event_type"],
            "reason_code": row["reason_code"],
            "summary": row["summary"],
        })
    return items


def _mark_expired_operations() -> int:
    _ensure_db()
    now = _iso()
    changed = 0
    with connection() as conn:
        with begin_immediate(conn) as tx:
            rows = tx.execute(
                "SELECT operation_id FROM owner_approved_operations WHERE status='pending_approval' AND approval_deadline<=?",
                (now,),
            ).fetchall()
            for row in rows:
                operation_id = str(row["operation_id"])
                updated = tx.execute(
                    "UPDATE owner_approved_operations SET status='expired',terminal_reason='approval_expired',execution_stage='terminal',updated_at=? WHERE operation_id=? AND status='pending_approval'",
                    (now, operation_id),
                )
                if updated.rowcount == 1:
                    _record_event(tx, operation_id=operation_id, actor_type="system", event_type="expired", reason_code="approval_expired", summary="Owner approval expired before use.")
                    changed += 1
            # A durable dispatch claim is intentionally left for the worker
            # reconciler.  It may already have a Photo Backup job binding, so
            # the async handler must get a chance to request the existing
            # cancellation path before terminalizing it.
            rows = tx.execute(
                "SELECT operation_id FROM owner_approved_operations WHERE status='approved' AND execution_deadline IS NOT NULL AND execution_deadline<=? AND execution_stage='awaiting_initial'",
                (now,),
            ).fetchall()
            for row in rows:
                operation_id = str(row["operation_id"])
                updated = tx.execute(
                    "UPDATE owner_approved_operations SET status='blocked',terminal_reason='execution_deadline_expired',execution_stage='terminal',updated_at=? WHERE operation_id=? AND status='approved' AND execution_stage='awaiting_initial'",
                    (now, operation_id),
                )
                if updated.rowcount == 1:
                    _record_event(tx, operation_id=operation_id, actor_type="system", event_type="blocked", reason_code="execution_deadline_expired", summary="The approved workflow stopped before a bounded transfer could start.")
                    changed += 1
    return changed


def owner_projection(auth_context: dict[str, Any]) -> dict[str, Any]:
    _owner_context(auth_context, assurance=False)
    _ensure_db()
    with connection() as conn:
        rows = conn.execute(
            """SELECT o.*,c.display_name AS requester_display_name,c.status AS requester_status,c.expires_at AS requester_expires_at
               FROM owner_approved_operations o JOIN owner_operation_clients c ON c.client_id=o.requester_client_id
               WHERE o.status IN ('pending_approval','approved','executing','verifying')
                  OR o.updated_at >= strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day')
               ORDER BY o.created_at DESC LIMIT 20""",
        ).fetchall()
        operations = []
        for row in rows:
            item = _public_operation(row, audience="owner")
            item["events"] = _event_projection(conn, row["operation_id"])
            operations.append(item)
        clients = [
            _client_projection(row, include_fingerprint=True)
            for row in conn.execute(
                "SELECT * FROM owner_operation_clients ORDER BY created_at DESC LIMIT 50"
            )
        ]
        pairings = []
        for row in conn.execute(
            """SELECT * FROM owner_operation_client_pairings
               WHERE status='pending' OR updated_at >= strftime('%Y-%m-%dT%H:%M:%SZ','now','-7 day')
               ORDER BY created_at DESC LIMIT 50"""
        ):
            item = _pairing_projection(row)
            item["events"] = _pairing_events(conn, row["pairing_id"])
            pairings.append(item)
    return {
        "status": "ok",
        "operations": operations,
        "clients": clients,
        "pairings": pairings,
        "updated_at": _iso(),
        "sanitized": True,
    }


def require_owner_read(auth_context: dict[str, Any]) -> None:
    _owner_context(auth_context, assurance=False)


def approval_policy_target(operation_id: str) -> dict[str, Any]:
    _mark_expired_operations()
    _ensure_db()
    with connection() as conn:
        row = _operation_row(conn, operation_id)
    return {
        "type": "owner_operation",
        "id": str(row["operation_id"]),
        "revision": str(row["scope_digest"]),
        "state": {
            "contract_version": int(row["contract_version"]),
            "operation": str(row["operation_type"]),
            "status": str(row["status"]),
            "target_node_id": str(row["target_node_id"]),
            "target_binding_digest": str(row["target_binding_digest"]),
            "destination_id": str(row["destination_id"]),
            "destination_contract_version": int(row["destination_contract_version"]),
            "scope_digest": str(row["scope_digest"]),
            "approval_deadline": str(row["approval_deadline"]),
        },
    }


def request_operation(*, client_id: str, descriptor: Any, challenge_id: str, signature: str) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    normalized = normalize_descriptor(descriptor, expected_client_id=client_id)
    target = _target_binding(normalized["target_node_id"])
    key_bytes: bytes
    challenge_id = _safe_id(challenge_id, kind="challenge")
    signature_bytes = _signature_bytes(signature)
    _ensure_db()
    now = _now()
    approval_deadline = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
    scope_digest = _digest(normalized["scope"])
    with connection() as conn:
        with begin_immediate(conn) as tx:
            client = _client_row(tx, client_id)
            key_bytes = _public_key_bytes(client["public_key"])
            binding = {
                "descriptor": normalized,
                "target_binding_digest": target["binding_digest"],
                "target_identity_revision": target["identity_revision"],
            }
            _consume_signed_challenge(
                tx,
                challenge_id=challenge_id,
                purpose="request",
                client_id=client_id,
                public_key=key_bytes,
                signature=signature_bytes,
                binding=binding,
            )
            existing = tx.execute(
                "SELECT o.*,c.display_name AS requester_display_name,c.status AS requester_status,c.expires_at AS requester_expires_at FROM owner_approved_operations o JOIN owner_operation_clients c ON c.client_id=o.requester_client_id WHERE o.requester_client_id=? AND o.idempotency_key=? LIMIT 1",
                (client_id, normalized["idempotency_key"]),
            ).fetchone()
            if existing:
                if str(existing["descriptor_json"] or "") != _canonical(normalized):
                    raise OwnerOperationError("idempotency_conflict", "The idempotency key is already bound to a different operation.", 409)
                return {**_public_operation(existing), "idempotent": True}
            operation_id = f"oo-{secrets.token_hex(12)}"
            tx.execute(
                """INSERT INTO owner_approved_operations(
                       operation_id,contract_version,operation_type,requester_client_id,target_node_id,
                       target_identity_revision,target_binding_digest,destination_id,destination_contract_version,
                       descriptor_json,scope_json,scope_digest,reason,idempotency_key,status,created_at,
                       approval_deadline,execution_stage,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    operation_id,
                    CONTRACT_VERSION,
                    OPERATION_TYPE,
                    client_id,
                    target["node_id"],
                    target["identity_revision"],
                    target["binding_digest"],
                    DESTINATION_ID,
                    lite_photo_backup_destinations.SCHEMA_VERSION,
                    _canonical(normalized),
                    _canonical(normalized["scope"]),
                    scope_digest,
                    normalized["reason"],
                    normalized["idempotency_key"],
                    "pending_approval",
                    _iso(now),
                    _iso(approval_deadline),
                    "awaiting_approval",
                    _iso(now),
                ),
            )
            tx.execute("UPDATE owner_operation_clients SET last_used_at=? WHERE client_id=?", (_iso(now), client_id))
            _record_event(
                tx,
                operation_id=operation_id,
                actor_type="requester",
                actor_id=client_id,
                event_type="created",
                reason_code="pending_owner_approval",
                summary="A bounded Photo Backup acceptance request is waiting for Owner review.",
                evidence={"contract_version": CONTRACT_VERSION, "operation": OPERATION_TYPE, "scope": normalized["scope"]},
            )
            row = _operation_row(tx, operation_id)
            return _public_operation(row)


def _revalidate_operation_target(row: Any) -> dict[str, Any]:
    target = _target_binding(str(row["target_node_id"]))
    if target["binding_digest"] != str(row["target_binding_digest"] or "") or target["identity_revision"] != int(row["target_identity_revision"] or 0):
        raise OwnerOperationError("target_identity_changed", "The approved device identity changed, so the operation was stopped.", 409)
    return target


def _assurance_reference(assurance_item: dict[str, Any] | None) -> str:
    if not assurance_item:
        return ""
    return _digest({
        "purpose": assurance_item.get("purpose"),
        "satisfied_at": assurance_item.get("satisfied_at"),
        "expires_at": assurance_item.get("expires_at"),
    })


def approve_operation(auth_context: dict[str, Any], operation_id: str) -> dict[str, Any]:
    _context, human_id, session_id, assurance_item = _owner_context(auth_context, assurance=True)
    operation_id = _safe_id(operation_id, kind="operation")
    _mark_expired_operations()
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _operation_row(tx, operation_id)
            if row["status"] != "pending_approval":
                raise OwnerOperationError("approval_not_pending", "This operation is no longer waiting for approval.", 409)
            if (_parse_iso(row["approval_deadline"]) or _now()) <= _now():
                tx.execute("UPDATE owner_approved_operations SET status='expired',terminal_reason='approval_expired',execution_stage='terminal',updated_at=? WHERE operation_id=? AND status='pending_approval'", (_iso(), operation_id))
                _record_event(tx, operation_id=operation_id, actor_type="system", event_type="expired", reason_code="approval_expired", summary="Owner approval expired before it was used.")
                raise OwnerOperationError("approval_expired", "This approval request has expired.", 409)
            target_error = None
            try:
                _revalidate_operation_target(row)
            except OwnerOperationError as exc:
                # Commit the fail-closed terminal transition before returning
                # the error. Raising inside begin_immediate would roll the
                # blocked evidence back and leave the request approvable.
                tx.execute("UPDATE owner_approved_operations SET status='blocked',terminal_reason=?,execution_stage='terminal',updated_at=? WHERE operation_id=? AND status='pending_approval'", (exc.reason_code, _iso(), operation_id))
                _record_event(tx, operation_id=operation_id, actor_type="system", event_type="blocked", reason_code=exc.reason_code, summary=exc.message)
                result_row = _operation_row(tx, operation_id)
                target_error = exc
            if target_error:
                pass
            else:
                _client_row(tx, str(row["requester_client_id"]))
                now = _now()
                updated = tx.execute(
                    """UPDATE owner_approved_operations
                       SET status='approved',approved_by_human_id=?,approved_at=?,approval_assurance_ref=?,
                           execution_deadline=?,execution_stage='awaiting_initial',updated_at=?
                       WHERE operation_id=? AND status='pending_approval'""",
                    (human_id, _iso(now), _assurance_reference(assurance_item), _iso(now + timedelta(seconds=EXECUTION_TTL_SECONDS)), _iso(now), operation_id),
                )
                if updated.rowcount != 1:
                    raise OwnerOperationError("approval_race", "The approval was already handled by another request.", 409)
                _record_event(tx, operation_id=operation_id, actor_type="owner", actor_id=human_id, event_type="approved", reason_code="owner_confirmed", summary="A real Owner approved the exact bounded workflow.", evidence={"assurance": "passkey_step_up", "scope_digest": row["scope_digest"]})
                _audit_human(tx, human_id=human_id, session_id=session_id, event_type="owner_operation.approved", reason_code="owner_confirmed", summary="Owner approved one bounded Photo Backup acceptance workflow.", operation_id=operation_id)
                result_row = _operation_row(tx, operation_id)
    if target_error:
        raise target_error
    return _public_operation(result_row)


def reject_operation(auth_context: dict[str, Any], operation_id: str, *, reason: str = "owner_rejected") -> dict[str, Any]:
    _context, human_id, session_id, _assurance = _owner_context(auth_context, assurance=False)
    operation_id = _safe_id(operation_id, kind="operation")
    safe_reason = _validate_text(reason, name="reason", maximum=80)
    _mark_expired_operations()
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _operation_row(tx, operation_id)
            if row["status"] != "pending_approval":
                raise OwnerOperationError("rejection_not_pending", "This operation is no longer waiting for a decision.", 409)
            updated = tx.execute(
                "UPDATE owner_approved_operations SET status='rejected',terminal_reason=?,execution_stage='terminal',updated_at=? WHERE operation_id=? AND status='pending_approval'",
                (safe_reason, _iso(), operation_id),
            )
            if updated.rowcount != 1:
                raise OwnerOperationError("decision_race", "The operation decision was already handled.", 409)
            _record_event(tx, operation_id=operation_id, actor_type="owner", actor_id=human_id, event_type="rejected", reason_code=safe_reason, summary="Owner rejected the bounded workflow.")
            _audit_human(tx, human_id=human_id, session_id=session_id, event_type="owner_operation.rejected", reason_code=safe_reason, summary="Owner rejected a bounded Photo Backup acceptance request.", operation_id=operation_id)
            result_row = _operation_row(tx, operation_id)
    return _public_operation(result_row)


def cancel_operation(*, client_id: str, operation_id: str, challenge_id: str, signature: str) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    operation_id = _safe_id(operation_id, kind="operation")
    challenge_id = _safe_id(challenge_id, kind="challenge")
    signature_bytes = _signature_bytes(signature)
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _operation_row(tx, operation_id)
            client = _client_row(tx, client_id)
            if row["requester_client_id"] != client_id:
                raise OwnerOperationError("operation_forbidden", "The operation is not available to this client.", 403)
            if row["status"] not in {"pending_approval", "approved"}:
                raise OwnerOperationError("operation_not_cancellable", "The operation is already executing or terminal.", 409)
            binding = {"operation_id": operation_id, "status_at_issue": str(row["status"])}
            _consume_signed_challenge(
                tx,
                challenge_id=challenge_id,
                purpose="cancel",
                client_id=client_id,
                public_key=_public_key_bytes(client["public_key"]),
                signature=signature_bytes,
                binding=binding,
                operation_id=operation_id,
            )
            tx.execute("UPDATE owner_approved_operations SET status='cancelled',terminal_reason='requester_cancelled',execution_stage='terminal',updated_at=? WHERE operation_id=? AND status IN ('pending_approval','approved')", (_iso(), operation_id))
            _record_event(tx, operation_id=operation_id, actor_type="requester", actor_id=client_id, event_type="cancelled", reason_code="requester_cancelled", summary="The registered requester cancelled the bounded workflow.")
            result_row = _operation_row(tx, operation_id)
    return _public_operation(result_row, audience="observer")


def observe_operation(*, client_id: str, operation_id: str, challenge_id: str, signature: str) -> dict[str, Any]:
    client_id = _safe_id(client_id, kind="client")
    operation_id = _safe_id(operation_id, kind="operation")
    challenge_id = _safe_id(challenge_id, kind="challenge")
    signature_bytes = _signature_bytes(signature)
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _operation_row(tx, operation_id)
            if row["requester_client_id"] != client_id:
                raise OwnerOperationError("operation_forbidden", "The operation is not available to this client.", 403)
            client = _client_row(tx, client_id)
            _consume_signed_challenge(
                tx,
                challenge_id=challenge_id,
                purpose="observe",
                client_id=client_id,
                public_key=_public_key_bytes(client["public_key"]),
                signature=signature_bytes,
                binding={"operation_id": operation_id, "status_at_issue": str(row["status"])},
                operation_id=operation_id,
            )
            result = _public_operation(row, audience="observer")
            result["events"] = _event_projection(tx, operation_id)
            return result


def owner_operation(operation_id: str) -> dict[str, Any]:
    _ensure_db()
    with connection() as conn:
        row = _operation_row(conn, operation_id)
        result = _public_operation(row, audience="owner")
        result["events"] = _event_projection(conn, operation_id)
        return result


def identity_projection(auth_context: dict[str, Any]) -> dict[str, Any]:
    """Read-only Identity projection; it never creates or consumes authority."""
    try:
        _owner_context(auth_context, assurance=False)
    except OwnerOperationError:
        return {"status": "not_available", "operations": [], "clients": [], "pairings": [], "sanitized": True}
    try:
        return owner_projection(auth_context)
    except Exception:
        return {"status": "unavailable", "operations": [], "clients": [], "pairings": [], "sanitized": True}


def _operation_update(
    operation_id: str,
    *,
    updates: dict[str, Any],
    event: tuple[str, str, str, str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed = {
        "status", "execution_stage", "fixture_id", "backup_id", "repeat_backup_id",
        "terminal_reason", "execution_deadline", "updated_at", "evidence_json",
    }
    if set(updates) - allowed:
        raise OwnerOperationError("operation_update_invalid", "The operation state update is not valid.", 500)
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _operation_row(tx, operation_id)
            current_evidence = _parse_evidence(row["evidence_json"])
            if evidence:
                current_evidence.update(evidence)
                updates = {**updates, "evidence_json": _canonical(current_evidence)}
            updates = {**updates, "updated_at": updates.get("updated_at") or _iso()}
            assignments = ",".join(f"{key}=?" for key in updates)
            tx.execute(
                f"UPDATE owner_approved_operations SET {assignments} WHERE operation_id=?",
                (*updates.values(), operation_id),
            )
            if event:
                event_type, reason_code, summary, actor_type = event
                _record_event(tx, operation_id=operation_id, actor_type=actor_type, event_type=event_type, reason_code=reason_code, summary=summary, evidence=evidence)
            return _operation_row(tx, operation_id)


def _claim_dispatch(operation_id: str, *, repeat: bool = False) -> dict[str, Any] | None:
    expected_stage = "awaiting_repeat" if repeat else "awaiting_initial"
    dispatch_stage = "dispatching_repeat" if repeat else "dispatching_initial"
    allowed_statuses = ("verifying",) if repeat else ("approved", "executing")
    _ensure_db()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = _operation_row(tx, operation_id)
            if str(row["execution_stage"]) == dispatch_stage:
                updated_at = _parse_iso(row["updated_at"])
                if updated_at and (_now() - updated_at).total_seconds() < 30:
                    return None
                # A worker/API crash can leave the durable claim in the
                # dispatching state. Reclaim that same operation after a
                # short lease instead of creating a second authorization.
                reclaimed = tx.execute(
                    "UPDATE owner_approved_operations SET updated_at=? WHERE operation_id=? AND status IN ({}) AND execution_stage=?".format(",".join("?" for _ in allowed_statuses)),
                    (_iso(), operation_id, *allowed_statuses, dispatch_stage),
                )
                if reclaimed.rowcount != 1:
                    return None
                return _operation_row(tx, operation_id)
            if str(row["execution_stage"]) != expected_stage or str(row["status"]) not in allowed_statuses:
                return None
            now = _iso()
            updated = tx.execute(
                "UPDATE owner_approved_operations SET status=?,execution_stage=?,updated_at=? WHERE operation_id=? AND status IN ({}) AND execution_stage=?".format(",".join("?" for _ in allowed_statuses)),
                ("executing", dispatch_stage, now, operation_id, *allowed_statuses, expected_stage),
            )
            if updated.rowcount != 1:
                return None
            return _operation_row(tx, operation_id)


def _safe_job_evidence(job: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(job, dict):
        return {"status": "missing", "verdict": "unvalidated"}
    integrity = str(job.get("integrity_mode") or "unknown")
    if integrity not in {"sha256", "size_only", "unknown"}:
        integrity = "unknown"
    status = str(job.get("status") or "unknown")

    def bounded_int(value: Any) -> int:
        try:
            return max(0, min(int(value or 0), 2**63 - 1))
        except (TypeError, ValueError, OverflowError):
            return 0

    return {
        "status": status,
        "source_scope": str(job.get("source_scope") or "")[:64],
        "destination_id": str(job.get("destination_id") or "")[:80],
        "items_transferred": bounded_int(job.get("items_transferred")),
        "bytes_transferred": bounded_int(job.get("bytes_transferred")),
        "integrity_mode": integrity,
        "photo_processing_state": str(job.get("photo_processing_state") or "unreported")[:64],
        "credential_revocation": str(job.get("credential_revoke_status") or "unreported")[:32],
        "reason_code": str(job.get("reason_code") or "")[:80],
        "verdict": "verified_transfer" if status == "completed" and integrity in {"sha256", "size_only"} else "unvalidated",
    }


def _exception_reason(exc: Exception) -> str:
    """Extract only a bounded reason code from an existing service error."""
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return str(detail.get("reason_code") or detail.get("status") or "")[:80]
    return ""


def _indexing_evidence() -> dict[str, Any]:
    # The current repository contract explicitly leaves PhotoPrism's delayed
    # indexing to PhotoPrism and does not expose a narrow authoritative lookup.
    # A WebDAV finalization therefore cannot be promoted to an indexed claim.
    return {
        "status": "unvalidated",
        "reason_code": "photoprism_indexing_not_proven",
        "summary": "Transfer evidence does not prove that PhotoPrism has indexed the test photo.",
    }


async def _request_existing_job_cancellation(row: Any, *, reason: str) -> dict[str, Any]:
    """Ask the existing Photo Backup path to stop one exact durable job.

    This is only a bounded safety cleanup for an expired or revoked operation;
    it does not create a new authorization or expose a general cancel API.
    The backup service still owns credential revocation and the node command.
    """
    if str(row["execution_stage"] or "").startswith("repeat"):
        backup_id = str(row["repeat_backup_id"] or "")
    else:
        backup_id = str(row["backup_id"] or "")
    if not backup_id:
        return {"status": "not_bound"}
    try:
        job = lite_photo_backup.job_status(backup_id)
    except Exception:
        return {"status": "job_unavailable", "backup_id": backup_id}
    if str(job.get("status") or "") in lite_photo_backup.TERMINAL_STATES:
        return {"status": "already_terminal", "backup_id": backup_id}
    try:
        command = lite_photo_backup.make_cancel_command(
            str(row["target_node_id"]),
            reason=f"Owner-approved workflow stopped: {reason}",
            backup_id=backup_id,
        )
    except Exception as exc:
        return {"status": "cancel_unavailable", "backup_id": backup_id, "error_type": type(exc).__name__}
    if command.get("idle"):
        return {"status": "idle", "backup_id": backup_id}
    from .action_queue import submit_domain_command

    try:
        submitted = await submit_domain_command(
            lite_photo_backup.PHOTO_BACKUP_CANCEL_SUBJECT,
            "lite.photo_backup.owner_approved.cancel_requested",
            command,
            trace_id=f"{row['operation_id']}:cancel",
        )
    except Exception as exc:
        return {"status": "cancel_submit_deferred", "backup_id": backup_id, "error_type": type(exc).__name__}
    return {
        "status": "queued",
        "backup_id": backup_id,
        "submission": str(submitted.get("status") or "queued") if isinstance(submitted, dict) else "queued",
    }


def _bound_photo_backup_job(row: Any, backup_id: str, *, repeat: bool = False) -> dict[str, Any]:
    try:
        job = lite_photo_backup.job_status(backup_id)
    except Exception as exc:
        phase = "safe-repeat" if repeat else "initial"
        raise OwnerOperationError(
            "backup_state_missing",
            f"The already-bound {phase} Photo Backup job could not be recovered.",
            409,
        ) from exc
    if (
        str(job.get("node_id") or "") != str(row["target_node_id"] or "")
        or str(job.get("destination_id") or "") != DESTINATION_ID
        or str(job.get("destination_contract_version") or "") != str(lite_photo_backup_destinations.SCHEMA_VERSION)
        or str(job.get("source_fixture_id") or "") != str(row["fixture_id"] or "")
        or str(job.get("source_scope") or "") != lite_photo_backup.ACCEPTANCE_FIXTURE_SCOPE
        or list(job.get("collections") or []) != [lite_photo_backup.ACCEPTANCE_FIXTURE_COLLECTION]
    ):
        phase = "safe-repeat" if repeat else "initial"
        raise OwnerOperationError(
            "backup_binding_invalid",
            f"The already-bound {phase} Photo Backup job no longer matches the approved scope.",
            409,
        )
    return job


async def _dispatch_initial(operation_id: str) -> dict[str, Any] | None:
    row = _claim_dispatch(operation_id)
    if row is None:
        return None
    try:
        if (_parse_iso(row["execution_deadline"]) or _now()) <= _now():
            raise OwnerOperationError("execution_deadline_expired", "The approved execution window expired before dispatch.", 409)
        _client_active_for_execution(row)
        _revalidate_operation_target(row)
        existing_backup_id = str(row["backup_id"] or "")
        if existing_backup_id:
            existing_job = _bound_photo_backup_job(row, existing_backup_id)
            if str(existing_job.get("status") or "") in lite_photo_backup.TERMINAL_STATES:
                return await _reconcile_execution(operation_id)
        fixture_id = str(row["fixture_id"] or "")
        if not fixture_id:
            fixture = lite_photo_backup.prepare_acceptance_fixture(str(row["target_node_id"]))
            fixture_id = str(fixture.get("fixture_id") or "")
            if not fixture_id:
                raise OwnerOperationError("source_fixture_unavailable", "The bounded source fixture was not prepared.", 409)
            # Bind the one fixture before any later admission check can fail.
            # Retries must reconcile this exact fixture instead of issuing a
            # second source object under the same Owner approval.
            _operation_update(
                operation_id,
                updates={"fixture_id": fixture_id},
                evidence={"fixture_scope": lite_photo_backup.ACCEPTANCE_FIXTURE_SCOPE, "fixture_binding": "durable_before_admission"},
            )
            row = {**dict(row), "fixture_id": fixture_id}
        if not fixture_id:
            raise OwnerOperationError("source_fixture_unavailable", "The bounded source fixture was not prepared.", 409)
        command = lite_photo_backup.make_start_command(
            str(row["target_node_id"]),
            [lite_photo_backup.ACCEPTANCE_FIXTURE_COLLECTION],
            reason="Owner-approved bounded Photo Backup acceptance",
            destination_id=DESTINATION_ID,
            acceptance_fixture_id=fixture_id,
            backup_id=existing_backup_id or None,
        )
        command["source_fixture"] = lite_photo_backup.acceptance_fixture_descriptor(str(row["target_node_id"]), fixture_id)
        command.pop("idempotent", None)
        # Persist the durable job binding before publishing. If the API or
        # worker crashes after this point, reconciliation can cancel or
        # safely re-submit this exact job rather than losing its scope.
        dispatch_backup_id = str(command.get("backup_id") or "")
        _operation_update(
            operation_id,
            updates={"fixture_id": fixture_id, "backup_id": dispatch_backup_id},
            evidence={"dispatch_binding": "durable_before_publish"},
        )
        row = {**dict(row), "fixture_id": fixture_id, "backup_id": dispatch_backup_id}
        from .action_queue import submit_domain_command

        await submit_domain_command(
            lite_photo_backup.PHOTO_BACKUP_START_SUBJECT,
            "lite.photo_backup.owner_approved.requested",
            command,
            trace_id=operation_id,
        )
        result_row = _operation_update(
            operation_id,
            updates={"status": "executing", "execution_stage": "initial_dispatched", "fixture_id": fixture_id, "backup_id": str(command.get("backup_id") or "")},
            event=("initial_dispatched", "server_owned_executor", "The bounded fixture was dispatched through the existing Photo Backup worker path.", "executor"),
            evidence={"fixture_scope": lite_photo_backup.ACCEPTANCE_FIXTURE_SCOPE, "dispatch": "nats_jetstream", "destination": DESTINATION_ID},
        )
        return _public_operation(result_row)
    except OwnerOperationError as exc:
        if exc.reason_code in {
            "target_identity_changed",
            "protected_server_target",
            "execution_deadline_expired",
            "client_revoked",
        }:
            cancellation = await _request_existing_job_cancellation(row, reason=exc.reason_code)
            result_row = _operation_update(
                operation_id,
                updates={
                    "status": "cancelled" if exc.reason_code == "client_revoked" else "blocked",
                    "execution_stage": "terminal",
                    "terminal_reason": "requester_revoked" if exc.reason_code == "client_revoked" else exc.reason_code,
                },
                event=("cancelled" if exc.reason_code == "client_revoked" else "blocked", exc.reason_code, exc.message, "system"),
                evidence={"cancellation": cancellation},
            )
        elif exc.reason_code in {"backup_state_missing", "backup_binding_invalid"}:
            result_row = _operation_update(
                operation_id,
                updates={
                    "status": "blocked" if exc.reason_code == "backup_binding_invalid" else "failed",
                    "execution_stage": "terminal",
                    "terminal_reason": exc.reason_code,
                },
                event=("blocked" if exc.reason_code == "backup_binding_invalid" else "failed", exc.reason_code, exc.message, "executor"),
            )
        else:
            result_row = _operation_update(
                operation_id,
                updates={"status": "approved", "execution_stage": "awaiting_initial"},
                event=("dispatch_deferred", exc.reason_code, "The approved operation remains bounded and will retry after the reported prerequisite is resolved.", "system"),
                evidence={"last_dispatch_reason": exc.reason_code},
            )
        return _public_operation(result_row)
    except Exception as exc:
        reason = _exception_reason(exc)
        if str(row["fixture_id"] or "") and reason in {
            "source_fixture_expired",
            "source_fixture_unavailable",
            "backup_state_missing",
            "invalid_backup_id",
            "target_identity_mismatch",
            "destination_identity_mismatch",
            "source_scope_mismatch",
        }:
            terminal_status = "failed" if reason.startswith("source_fixture") or reason == "backup_state_missing" else "blocked"
            result_row = _operation_update(
                operation_id,
                updates={"status": terminal_status, "execution_stage": "terminal", "terminal_reason": reason},
                event=("failed" if terminal_status == "failed" else "blocked", reason, "The bound Photo Backup workflow could not be safely resumed within its original scope.", "executor"),
                evidence={"last_dispatch_reason": reason},
            )
            return _public_operation(result_row)
        result_row = _operation_update(
            operation_id,
            updates={"status": "approved", "execution_stage": "awaiting_initial"},
            event=("dispatch_deferred", "worker_unavailable", "The approved operation remains bounded while the worker path is unavailable.", "system"),
            evidence={"last_dispatch_reason": "worker_unavailable", "last_dispatch_error_type": type(exc).__name__},
        )
        return _public_operation(result_row)


def _client_active_for_execution(row: Any) -> None:
    _ensure_db()
    with connection() as conn:
        _client_row(conn, str(row["requester_client_id"]))


async def _dispatch_repeat(operation_id: str) -> dict[str, Any] | None:
    row = _claim_dispatch(operation_id, repeat=True)
    if row is None:
        return None
    try:
        if (_parse_iso(row["execution_deadline"]) or _now()) <= _now():
            raise OwnerOperationError("execution_deadline_expired", "The approved execution window expired before the safe repeat.", 409)
        _client_active_for_execution(row)
        _revalidate_operation_target(row)
        existing_repeat_backup_id = str(row["repeat_backup_id"] or "")
        if existing_repeat_backup_id:
            existing_job = _bound_photo_backup_job(row, existing_repeat_backup_id, repeat=True)
            if str(existing_job.get("status") or "") in lite_photo_backup.TERMINAL_STATES:
                return await _reconcile_execution(operation_id, repeat=True)
        fixture_id = str(row["fixture_id"] or "")
        if not fixture_id:
            raise OwnerOperationError("source_fixture_unavailable", "The bounded source fixture is unavailable for the safe repeat.", 409)
        command = lite_photo_backup.make_start_command(
            str(row["target_node_id"]),
            [lite_photo_backup.ACCEPTANCE_FIXTURE_COLLECTION],
            reason="Owner-approved bounded Photo Backup safe repeat",
            destination_id=DESTINATION_ID,
            acceptance_fixture_id=fixture_id,
            backup_id=existing_repeat_backup_id or None,
        )
        command["source_fixture"] = lite_photo_backup.acceptance_fixture_descriptor(str(row["target_node_id"]), fixture_id)
        command.pop("idempotent", None)
        repeat_backup_id = str(command.get("backup_id") or "")
        _operation_update(
            operation_id,
            updates={"repeat_backup_id": repeat_backup_id},
            evidence={"repeat_dispatch_binding": "durable_before_publish"},
        )
        row = {**dict(row), "repeat_backup_id": repeat_backup_id}
        from .action_queue import submit_domain_command

        await submit_domain_command(
            lite_photo_backup.PHOTO_BACKUP_START_SUBJECT,
            "lite.photo_backup.owner_approved.repeat_requested",
            command,
            trace_id=operation_id,
        )
        result_row = _operation_update(
            operation_id,
            updates={"status": "verifying", "execution_stage": "repeat_dispatched", "repeat_backup_id": str(command.get("backup_id") or "")},
            event=("repeat_dispatched", "same_fixture_repeat", "The same bounded fixture was dispatched for one safe idempotent repeat.", "executor"),
            evidence={"repeat": "same_fixture_once", "dispatch": "nats_jetstream"},
        )
        return _public_operation(result_row)
    except OwnerOperationError as exc:
        if exc.reason_code in {"execution_deadline_expired", "target_identity_changed", "protected_server_target", "client_revoked"}:
            cancellation = await _request_existing_job_cancellation(row, reason=exc.reason_code)
            result_row = _operation_update(
                operation_id,
                updates={
                    "status": "cancelled" if exc.reason_code == "client_revoked" else "blocked",
                    "execution_stage": "terminal",
                    "terminal_reason": "requester_revoked" if exc.reason_code == "client_revoked" else exc.reason_code,
                },
                event=("cancelled" if exc.reason_code == "client_revoked" else "blocked", exc.reason_code, exc.message, "system"),
                evidence={"cancellation": cancellation},
            )
            return _public_operation(result_row)
        if exc.reason_code in {"backup_state_missing", "backup_binding_invalid"}:
            result_row = _operation_update(
                operation_id,
                updates={
                    "status": "blocked" if exc.reason_code == "backup_binding_invalid" else "failed",
                    "execution_stage": "terminal",
                    "terminal_reason": exc.reason_code,
                },
                event=("blocked" if exc.reason_code == "backup_binding_invalid" else "failed", exc.reason_code, exc.message, "executor"),
            )
            return _public_operation(result_row)
        result_row = _operation_update(
            operation_id,
            updates={"status": "failed", "execution_stage": "terminal", "terminal_reason": exc.reason_code},
            event=("failed", exc.reason_code, exc.message, "executor"),
        )
        return _public_operation(result_row)
    except Exception as exc:
        reason = _exception_reason(exc)
        if reason in {
            "source_fixture_expired",
            "source_fixture_unavailable",
            "backup_state_missing",
            "invalid_backup_id",
            "target_identity_mismatch",
            "destination_identity_mismatch",
            "source_scope_mismatch",
        }:
            terminal_status = "failed" if reason.startswith("source_fixture") or reason == "backup_state_missing" else "blocked"
            result_row = _operation_update(
                operation_id,
                updates={"status": terminal_status, "execution_stage": "terminal", "terminal_reason": reason},
                event=("failed" if terminal_status == "failed" else "blocked", reason, "The bound Photo Backup repeat could not be safely resumed within its original scope.", "executor"),
                evidence={"last_repeat_reason": reason},
            )
            return _public_operation(result_row)
        result_row = _operation_update(
            operation_id,
            updates={"status": "verifying", "execution_stage": "awaiting_repeat"},
            event=("repeat_deferred", "worker_unavailable", "The safe repeat remains bound to the same approval while the worker path is unavailable.", "system"),
            evidence={"last_repeat_reason": "worker_unavailable", "last_repeat_error_type": type(exc).__name__},
        )
        return _public_operation(result_row)


async def _reconcile_execution(operation_id: str, *, repeat: bool = False) -> dict[str, Any] | None:
    _ensure_db()
    with connection() as conn:
        row = _operation_row(conn, operation_id)
    try:
        if (_parse_iso(row["execution_deadline"]) or _now()) <= _now():
            cancellation = await _request_existing_job_cancellation(row, reason="execution_deadline_expired")
            result_row = _operation_update(
                operation_id,
                updates={"status": "blocked", "execution_stage": "terminal", "terminal_reason": "execution_deadline_expired"},
                event=("blocked", "execution_deadline_expired", "The approved workflow reached its bounded execution deadline and was stopped safely.", "system"),
                evidence={"cancellation": cancellation},
            )
            return _public_operation(result_row)
        _client_active_for_execution(row)
        _revalidate_operation_target(row)
    except OwnerOperationError as exc:
        if exc.reason_code not in {"client_revoked", "target_identity_changed", "protected_server_target"}:
            raise
        cancellation = await _request_existing_job_cancellation(row, reason=exc.reason_code)
        result_row = _operation_update(
            operation_id,
            updates={
                "status": "cancelled" if exc.reason_code == "client_revoked" else "blocked",
                "execution_stage": "terminal",
                "terminal_reason": "requester_revoked" if exc.reason_code == "client_revoked" else exc.reason_code,
            },
            event=(
                "cancelled" if exc.reason_code == "client_revoked" else "blocked",
                "requester_revoked" if exc.reason_code == "client_revoked" else exc.reason_code,
                "The bounded workflow was stopped after its authorization or target binding became invalid.",
                "system",
            ),
            evidence={"cancellation": cancellation},
        )
        return _public_operation(result_row)
    backup_id = str((row["repeat_backup_id"] if repeat else row["backup_id"]) or "")
    if not backup_id:
        return None
    try:
        job = lite_photo_backup.job_status(backup_id)
    except Exception:
        job = None
    evidence = _safe_job_evidence(job)
    evidence_key = "repeat_job" if repeat else "initial_job"
    if not job:
        result_row = _operation_update(
            operation_id,
            updates={"status": "failed", "execution_stage": "terminal", "terminal_reason": "backup_state_missing"},
            event=("failed", "backup_state_missing", "The durable Photo Backup job record was not available after dispatch.", "executor"),
            evidence={evidence_key: evidence},
        )
        return _public_operation(result_row)
    if str(job.get("status") or "") not in lite_photo_backup.TERMINAL_STATES:
        return None
    if str(job.get("status") or "") != "completed":
        result_row = _operation_update(
            operation_id,
            updates={"status": "failed", "execution_stage": "terminal", "terminal_reason": str(job.get("reason_code") or "backup_failed")},
            event=("failed", str(job.get("reason_code") or "backup_failed"), "The bounded Photo Backup job did not complete successfully.", "executor"),
            evidence={evidence_key: evidence},
        )
        return _public_operation(result_row)
    if str(job.get("credential_revoke_status") or "") != "revoked":
        return _operation_update(
            operation_id,
            updates={"status": "verifying", "execution_stage": "initial_waiting_for_credential_revocation" if not repeat else "repeat_waiting_for_credential_revocation"},
            event=("verifying", "credential_revocation_pending", "Transfer completed; waiting for the existing credential-revocation cleanup to finish.", "executor"),
            evidence={evidence_key: evidence},
        ) and None
    if repeat:
        result_row = _operation_update(
            operation_id,
            updates={"status": "completed", "execution_stage": "terminal", "terminal_reason": "bounded_acceptance_completed"},
            event=("completed", "bounded_acceptance_completed", "The bounded transfer and one same-fixture repeat completed with sanitized evidence.", "executor"),
            evidence={evidence_key: evidence, "indexing": _indexing_evidence(), "verdict": "completed_transfer_indexing_unvalidated"},
        )
        return _public_operation(result_row)
    result_row = _operation_update(
        operation_id,
        updates={"status": "verifying", "execution_stage": "awaiting_repeat"},
        event=("verifying", "initial_transfer_verified", "The first bounded transfer completed; the safe same-fixture repeat is next.", "executor"),
        evidence={evidence_key: evidence, "indexing": _indexing_evidence()},
    )
    return _public_operation(result_row)


async def dispatch_approved_operation(operation_id: str) -> dict[str, Any] | None:
    """Run only the registered bounded handler after a durable Owner approval."""
    return await _dispatch_initial(_safe_id(operation_id, kind="operation"))


async def reconcile_operations() -> int:
    """Restart-safe worker reconciliation for approved bounded workflows."""
    _mark_expired_operations()
    _mark_expired_pairings()
    _ensure_db()
    with connection() as conn:
        rows = conn.execute(
            "SELECT operation_id,execution_stage,status FROM owner_approved_operations WHERE status IN ('approved','executing','verifying') ORDER BY updated_at LIMIT 50",
        ).fetchall()
    changed = 0
    for row in rows:
        operation_id = str(row["operation_id"])
        stage = str(row["execution_stage"] or "")
        before = str(row["status"] or "")
        if stage in {"awaiting_initial", "dispatching_initial"}:
            await _dispatch_initial(operation_id)
        elif stage in {"initial_dispatched", "initial_waiting_for_credential_revocation"}:
            await _reconcile_execution(operation_id)
        elif stage in {"awaiting_repeat", "dispatching_repeat"}:
            await _dispatch_repeat(operation_id)
        elif stage in {"repeat_dispatched", "repeat_waiting_for_credential_revocation"}:
            await _reconcile_execution(operation_id, repeat=True)
        with connection() as fresh_conn:
            fresh = _operation_row(fresh_conn, operation_id)
        if str(fresh["status"] or "") != before or str(fresh["execution_stage"] or "") != stage:
            changed += 1
    return changed
