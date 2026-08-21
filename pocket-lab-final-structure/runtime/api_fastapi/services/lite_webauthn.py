from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import struct
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import lite_identity_auth

# WebAuthn level-2 compatible, dependency-free ES256/P-256 verifier. Pocket Lab
# requests attestation="none" and stores only the credential public key/counter.
P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
P256_A = P256_P - 3
P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
P256_G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)

OWNER_CLAIM_COOKIE = os.environ.get("POCKETLAB_IDENTITY_OWNER_CLAIM_COOKIE_NAME", "__Host-pocketlab_owner_claim")
CHALLENGE_TTL_SECONDS = 180
OWNER_CLAIM_TTL_SECONDS = 600
OWNER_AUTHORITY_TTL_SECONDS = 300
STEP_UP_TTL_SECONDS = 300


def owner_claim_cookie_name() -> str:
    if lite_identity_auth.cookie_secure():
        return OWNER_CLAIM_COOKIE
    return os.environ.get("POCKETLAB_IDENTITY_INSECURE_OWNER_CLAIM_COOKIE_NAME", "pocketlab_owner_claim")


def owner_authority_ttl_seconds() -> int:
    return _bounded_int("POCKETLAB_IDENTITY_OWNER_AUTHORITY_TTL_SECONDS", OWNER_AUTHORITY_TTL_SECONDS, 60, 900)


def owner_claim_cookie_secure() -> bool:
    return lite_identity_auth.cookie_secure()


class WebAuthnError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.reason_code = str(reason_code)[:80]
        self.message = str(message)[:240]
        self.status_code = int(status_code)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return min(max(value, minimum), maximum)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(value: str) -> bytes:
    text = str(value or "").strip()
    padding = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode((text + padding).encode("ascii"))
    except Exception as exc:
        raise WebAuthnError("webauthn_encoding_invalid", "Passkey data could not be decoded.", status_code=422) from exc


def _hash(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _normalize_origin(origin: str) -> tuple[str, str]:
    raw = str(origin or "").strip().rstrip("/")
    try:
        parsed = urlsplit(raw)
        hostname = (parsed.hostname or "").strip().rstrip(".").casefold()
        port = parsed.port
    except ValueError as exc:
        raise WebAuthnError("webauthn_origin_invalid", "This address cannot be used for passkeys.", status_code=422) from exc
    if not hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise WebAuthnError("webauthn_origin_invalid", "This address cannot be used for passkeys.", status_code=422)
    localhost = hostname == "localhost" or hostname.endswith(".localhost")
    try:
        ipaddress.ip_address(hostname)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False
    if is_ip_literal:
        raise WebAuthnError(
            "webauthn_hostname_required",
            "Passkeys require the Pocket Lab HTTPS hostname rather than a raw IP address.",
            status_code=422,
        )
    secure = parsed.scheme == "https"
    if not secure and not (parsed.scheme == "http" and localhost):
        raise WebAuthnError("webauthn_secure_origin_required", "Passkeys require HTTPS. Localhost is allowed for development.", status_code=422)
    default_port = (parsed.scheme == "https" and port in {None, 443}) or (parsed.scheme == "http" and port in {None, 80})
    authority = f"[{hostname}]" if ":" in hostname else hostname
    normalized = f"{parsed.scheme}://{authority}" + ("" if default_port else f":{port}")
    return normalized, hostname


def _origin_from_request(origin_header: str | None, host_header: str | None, forwarded_proto: str | None = None) -> tuple[str, str]:
    if origin_header:
        return _normalize_origin(origin_header)
    host = str(host_header or "").strip()
    proto = str(forwarded_proto or "").split(",", 1)[0].strip().lower()
    if not proto:
        proto = "https" if lite_identity_auth.cookie_secure() else "http"
    return _normalize_origin(f"{proto}://{host}")


def _rp_id_valid_for_origin(rp_id: str, origin_host: str) -> bool:
    rp = str(rp_id or "").strip().rstrip(".").casefold()
    host = str(origin_host or "").strip().rstrip(".").casefold()
    if not rp or not host:
        return False
    if rp == host:
        return True
    if host.endswith("." + rp):
        return True
    return False


def _installation_id() -> str:
    configured = os.environ.get("POCKETLAB_INSTALLATION_ID", "").strip()
    if configured:
        return configured[:120]
    # Stable-but-non-secret installation binding from state location. It is never
    # returned as authentication material and does not replace the random claim.
    state = os.environ.get("POCKETLAB_STATE_DIR", "").strip() or str(os.path.expanduser("~/.pocket_lab/state"))
    return hashlib.sha256(state.encode("utf-8")).hexdigest()[:32]


def issue_owner_claim(*, origin: str, ttl_seconds: int | None = None) -> dict[str, Any]:
    apply_migrations()
    if lite_identity_auth.owner_exists():
        raise WebAuthnError("identity_owner_exists", "Pocket Lab already has an owner.", status_code=409)
    normalized_origin, rp_id = _normalize_origin(origin)
    if not _rp_id_valid_for_origin(rp_id, urlsplit(normalized_origin).hostname or ""):
        raise WebAuthnError("webauthn_rp_id_invalid", "Passkey RP ID does not match the Pocket Lab address.", status_code=422)
    raw_claim = secrets.token_urlsafe(32)
    claim_id = f"claim-{uuid.uuid4().hex}"
    now = _now()
    ttl = ttl_seconds if ttl_seconds is not None else _bounded_int("POCKETLAB_IDENTITY_OWNER_CLAIM_TTL_SECONDS", OWNER_CLAIM_TTL_SECONDS, 60, 1800)
    ttl = min(max(int(ttl), 60), 1800)
    expires = _iso(now + timedelta(seconds=ttl))
    user_handle = _b64url(secrets.token_bytes(32))
    with connection() as conn:
        with begin_immediate(conn) as tx:
            if tx.execute("SELECT 1 FROM human_identities WHERE status='active' LIMIT 1").fetchone():
                raise WebAuthnError("identity_owner_exists", "Pocket Lab already has an owner.", status_code=409)
            tx.execute(
                """INSERT INTO owner_claims(
                       claim_id,claim_hash,installation_id,rp_id,origin,webauthn_user_handle,created_at,expires_at
                   ) VALUES (?,?,?,?,?,?,?,?)""",
                (claim_id, _hash(raw_claim), _installation_id(), rp_id, normalized_origin, user_handle, _iso(now), expires),
            )
            lite_identity_auth._audit(
                tx, human_id=None, session_id=None, event_type="owner_claim.issued",
                reason_code="trusted_local_admin", summary="A short-lived owner claim was issued.", correlation_id=claim_id,
            )
    return {
        "claim_id": claim_id,
        "claim": raw_claim,
        "origin": normalized_origin,
        "rp_id": rp_id,
        "expires_at": expires,
        "claim_url": f"{normalized_origin}/?owner_claim={raw_claim}",
    }


def consume_owner_claim(*, raw_claim: str, origin: str) -> dict[str, Any]:
    apply_migrations()
    normalized_origin, origin_host = _normalize_origin(origin)
    if not raw_claim:
        raise WebAuthnError("owner_claim_invalid", "Owner claim could not be verified.", status_code=401)
    now = _now()
    authority = secrets.token_urlsafe(32)
    authority_expires = _iso(now + timedelta(seconds=_bounded_int("POCKETLAB_IDENTITY_OWNER_AUTHORITY_TTL_SECONDS", OWNER_AUTHORITY_TTL_SECONDS, 60, 900)))
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT * FROM owner_claims WHERE claim_hash=? LIMIT 1", (_hash(raw_claim),)).fetchone()
            if not row:
                raise WebAuthnError("owner_claim_invalid", "Owner claim could not be verified.", status_code=401)
            claim = dict(row)
            expires = _parse_iso(claim.get("expires_at"))
            if claim.get("consumed_at") or claim.get("completed_at"):
                raise WebAuthnError("owner_claim_reused", "This owner claim was already used.", status_code=409)
            if expires is None or now >= expires:
                raise WebAuthnError("owner_claim_expired", "This owner claim expired. Create a new one locally.", status_code=410)
            if claim.get("installation_id") != _installation_id():
                raise WebAuthnError("owner_claim_installation_mismatch", "Owner claim does not belong to this Pocket Lab installation.", status_code=403)
            if claim.get("origin") != normalized_origin or not _rp_id_valid_for_origin(claim.get("rp_id"), origin_host):
                raise WebAuthnError("owner_claim_origin_mismatch", "Open the owner claim on the Pocket Lab address it was created for.", status_code=403)
            if tx.execute("SELECT 1 FROM human_identities WHERE status='active' LIMIT 1").fetchone():
                raise WebAuthnError("identity_owner_exists", "Pocket Lab already has an owner.", status_code=409)
            tx.execute(
                "UPDATE owner_claims SET consumed_at=?,authority_hash=?,authority_expires_at=? WHERE claim_id=? AND consumed_at IS NULL",
                (_iso(now), _hash(authority), authority_expires, claim["claim_id"]),
            )
            if tx.total_changes < 1:
                raise WebAuthnError("owner_claim_reused", "This owner claim was already used.", status_code=409)
            lite_identity_auth._audit(
                tx, human_id=None, session_id=None, event_type="owner_claim.consumed",
                reason_code="claim_verified", summary="Owner claim was verified for passkey setup.", correlation_id=claim["claim_id"],
            )
    return {"authority": authority, "expires_at": authority_expires, "status": "claim_verified"}


def _claim_from_authority(authority: str, origin: str) -> dict[str, Any]:
    normalized_origin, origin_host = _normalize_origin(origin)
    now = _now()
    with connection() as conn:
        row = conn.execute("SELECT * FROM owner_claims WHERE authority_hash=? LIMIT 1", (_hash(authority),)).fetchone()
    if not row:
        raise WebAuthnError("owner_claim_authority_invalid", "Owner setup authority is no longer valid.", status_code=401)
    claim = dict(row)
    expires = _parse_iso(claim.get("authority_expires_at"))
    if claim.get("completed_at") or expires is None or now >= expires:
        raise WebAuthnError("owner_claim_authority_expired", "Owner setup authority expired. Create a new owner claim locally.", status_code=410)
    if claim.get("origin") != normalized_origin or not _rp_id_valid_for_origin(claim.get("rp_id"), origin_host):
        raise WebAuthnError("owner_claim_origin_mismatch", "Owner setup must stay on the original Pocket Lab address.", status_code=403)
    return claim


def _challenge(*, purpose: str, rp_id: str, origin: str, human_id: str | None = None, session_id: str | None = None, owner_claim_id: str | None = None) -> tuple[str, str]:
    raw = _b64url(secrets.token_bytes(32))
    challenge_id = f"challenge-{uuid.uuid4().hex}"
    now = _now()
    expires = _iso(now + timedelta(seconds=_bounded_int("POCKETLAB_IDENTITY_WEBAUTHN_CHALLENGE_TTL_SECONDS", CHALLENGE_TTL_SECONDS, 60, 600)))
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO webauthn_challenges(
                       challenge_id,challenge_hash,purpose,human_id,session_id,owner_claim_id,rp_id,origin,created_at,expires_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (challenge_id, _hash(raw), purpose, human_id, session_id, owner_claim_id, rp_id, origin, _iso(now), expires),
            )
            tx.execute("DELETE FROM webauthn_challenges WHERE expires_at<? OR consumed_at IS NOT NULL", (_iso(now - timedelta(hours=1)),))
    return raw, challenge_id


def _consume_challenge(*, raw_challenge: str, purpose: str, rp_id: str, origin: str, human_id: str | None = None, session_id: str | None = None, owner_claim_id: str | None = None) -> dict[str, Any]:
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT * FROM webauthn_challenges WHERE challenge_hash=? LIMIT 1", (_hash(raw_challenge),)).fetchone()
            if not row:
                raise WebAuthnError("webauthn_challenge_invalid", "Passkey challenge could not be verified.", status_code=401)
            item = dict(row)
            expires = _parse_iso(item.get("expires_at"))
            matches = (
                item.get("purpose") == purpose and item.get("rp_id") == rp_id and item.get("origin") == origin
                and (human_id is None or item.get("human_id") == human_id)
                and (session_id is None or item.get("session_id") == session_id)
                and (owner_claim_id is None or item.get("owner_claim_id") == owner_claim_id)
            )
            if not matches:
                raise WebAuthnError("webauthn_challenge_scope_mismatch", "Passkey challenge does not match this action.", status_code=403)
            if item.get("consumed_at"):
                raise WebAuthnError("webauthn_challenge_replayed", "That passkey challenge was already used.", status_code=409)
            if expires is None or now >= expires:
                raise WebAuthnError("webauthn_challenge_expired", "Passkey challenge expired. Try again.", status_code=410)
            tx.execute("UPDATE webauthn_challenges SET consumed_at=? WHERE challenge_id=? AND consumed_at IS NULL", (_iso(now), item["challenge_id"]))
            if tx.total_changes < 1:
                raise WebAuthnError("webauthn_challenge_replayed", "That passkey challenge was already used.", status_code=409)
    return item


def _get_or_create_user_handle(human_id: str) -> str:
    with connection() as conn:
        row = conn.execute("SELECT user_handle FROM webauthn_users WHERE human_id=?", (human_id,)).fetchone()
        if row:
            return row["user_handle"]
        handle = _b64url(secrets.token_bytes(32))
        try:
            with begin_immediate(conn) as tx:
                tx.execute("INSERT INTO webauthn_users(human_id,user_handle,created_at) VALUES (?,?,?)", (human_id, handle, _iso()))
        except Exception:
            row = conn.execute("SELECT user_handle FROM webauthn_users WHERE human_id=?", (human_id,)).fetchone()
            if row:
                return row["user_handle"]
            raise
    return handle


def _active_credentials(human_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM webauthn_credentials WHERE human_id=? AND revoked_at IS NULL ORDER BY created_at", (human_id,)).fetchall()
    return [dict(row) for row in rows]


def owner_claim_registration_options(*, authority: str, origin: str, username: str = "owner", display_name: str = "Pocket Lab Owner") -> dict[str, Any]:
    claim = _claim_from_authority(authority, origin)
    challenge, _ = _challenge(purpose="owner_claim_register", rp_id=claim["rp_id"], origin=claim["origin"], owner_claim_id=claim["claim_id"])
    return {
        "publicKey": {
            "challenge": challenge,
            "rp": {"name": "Pocket Lab Lite", "id": claim["rp_id"]},
            "user": {"id": claim["webauthn_user_handle"], "name": str(username or "owner")[:64], "displayName": str(display_name or "Pocket Lab Owner")[:120]},
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
            "timeout": 120000,
            "attestation": "none",
            "authenticatorSelection": {"residentKey": "preferred", "userVerification": "required"},
        },
        "origin": claim["origin"],
        "rp_id": claim["rp_id"],
        "expires_in_seconds": _bounded_int("POCKETLAB_IDENTITY_WEBAUTHN_CHALLENGE_TTL_SECONDS", CHALLENGE_TTL_SECONDS, 60, 600),
    }


def registration_options(*, human_id: str, session_id: str, origin: str) -> dict[str, Any]:
    normalized_origin, rp_id = _normalize_origin(origin)
    user_handle = _get_or_create_user_handle(human_id)
    challenge, _ = _challenge(purpose="register", rp_id=rp_id, origin=normalized_origin, human_id=human_id, session_id=session_id)
    exclude = [{"type": "public-key", "id": item["credential_id"]} for item in _active_credentials(human_id)]
    with connection() as conn:
        human = conn.execute("SELECT username_normalized,display_name FROM human_identities WHERE human_id=? AND status='active'", (human_id,)).fetchone()
    if not human:
        raise WebAuthnError("identity_session_invalid", "Sign in again to continue.", status_code=401)
    return {
        "publicKey": {
            "challenge": challenge,
            "rp": {"name": "Pocket Lab Lite", "id": rp_id},
            "user": {"id": user_handle, "name": human["username_normalized"], "displayName": human["display_name"]},
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
            "timeout": 120000,
            "attestation": "none",
            "authenticatorSelection": {"residentKey": "preferred", "userVerification": "required"},
            "excludeCredentials": exclude,
        },
        "origin": normalized_origin,
        "rp_id": rp_id,
    }


def login_options(*, origin: str) -> dict[str, Any]:
    apply_migrations()
    normalized_origin, rp_id = _normalize_origin(origin)
    with connection() as conn:
        owner = conn.execute("SELECT human_id FROM human_identities WHERE status='active' ORDER BY created_at LIMIT 1").fetchone()
        if not owner:
            raise WebAuthnError("identity_setup_required", "Create the Pocket Lab owner first.", status_code=409)
        creds = conn.execute("SELECT credential_id FROM webauthn_credentials WHERE human_id=? AND revoked_at IS NULL ORDER BY created_at", (owner["human_id"],)).fetchall()
    if not creds:
        raise WebAuthnError("passkey_unavailable", "No passkey is available. Use Advanced sign-in or recovery.", status_code=409)
    challenge, _ = _challenge(purpose="login", rp_id=rp_id, origin=normalized_origin, human_id=owner["human_id"])
    return {
        "publicKey": {
            "challenge": challenge,
            "rpId": rp_id,
            "allowCredentials": [{"type": "public-key", "id": row["credential_id"]} for row in creds],
            "userVerification": "required",
            "timeout": 120000,
        },
        "origin": normalized_origin,
        "rp_id": rp_id,
    }


def step_up_options(*, human_id: str, session_id: str, origin: str, purpose: str) -> dict[str, Any]:
    normalized_origin, rp_id = _normalize_origin(origin)
    creds = _active_credentials(human_id)
    if not creds:
        raise WebAuthnError("passkey_unavailable", "Add a passkey before using passkey step-up.", status_code=409)
    bounded_purpose = str(purpose or "sensitive_action")[:80]
    challenge, _ = _challenge(purpose=f"step_up:{bounded_purpose}", rp_id=rp_id, origin=normalized_origin, human_id=human_id, session_id=session_id)
    return {
        "publicKey": {
            "challenge": challenge,
            "rpId": rp_id,
            "allowCredentials": [{"type": "public-key", "id": item["credential_id"]} for item in creds],
            "userVerification": "required",
            "timeout": 120000,
        },
        "purpose": bounded_purpose,
        "origin": normalized_origin,
        "rp_id": rp_id,
    }


# ---- Minimal CBOR + ES256 verifier -------------------------------------------------

def _cbor_read(data: bytes, offset: int = 0) -> tuple[Any, int]:
    if offset >= len(data):
        raise WebAuthnError("webauthn_cbor_invalid", "Passkey data is incomplete.", status_code=422)
    first = data[offset]
    offset += 1
    major = first >> 5
    add = first & 31
    if add < 24:
        length = add
    elif add == 24:
        length, offset = data[offset], offset + 1
    elif add == 25:
        length = struct.unpack(">H", data[offset:offset + 2])[0]; offset += 2
    elif add == 26:
        length = struct.unpack(">I", data[offset:offset + 4])[0]; offset += 4
    elif add == 27:
        length = struct.unpack(">Q", data[offset:offset + 8])[0]; offset += 8
    else:
        raise WebAuthnError("webauthn_cbor_invalid", "Unsupported passkey encoding.", status_code=422)
    if major == 0:
        return length, offset
    if major == 1:
        return -1 - length, offset
    if major == 2:
        end = offset + length
        if end > len(data): raise WebAuthnError("webauthn_cbor_invalid", "Passkey data is incomplete.", status_code=422)
        return data[offset:end], end
    if major == 3:
        end = offset + length
        if end > len(data): raise WebAuthnError("webauthn_cbor_invalid", "Passkey data is incomplete.", status_code=422)
        try: return data[offset:end].decode("utf-8"), end
        except UnicodeDecodeError as exc: raise WebAuthnError("webauthn_cbor_invalid", "Passkey text encoding is invalid.", status_code=422) from exc
    if major == 4:
        result = []
        for _ in range(length):
            item, offset = _cbor_read(data, offset); result.append(item)
        return result, offset
    if major == 5:
        result = {}
        for _ in range(length):
            key, offset = _cbor_read(data, offset); value, offset = _cbor_read(data, offset); result[key] = value
        return result, offset
    if major == 7:
        if add == 20: return False, offset
        if add == 21: return True, offset
        if add == 22: return None, offset
    raise WebAuthnError("webauthn_cbor_invalid", "Unsupported passkey encoding.", status_code=422)


def _client_data(client_data_b64: str, *, expected_type: str, expected_challenge: str, expected_origin: str) -> bytes:
    raw = _unb64url(client_data_b64)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise WebAuthnError("webauthn_client_data_invalid", "Passkey client data is invalid.", status_code=422) from exc
    if data.get("type") != expected_type:
        raise WebAuthnError("webauthn_type_mismatch", "Passkey response type does not match this action.", status_code=403)
    if data.get("challenge") != expected_challenge:
        raise WebAuthnError("webauthn_challenge_mismatch", "Passkey response challenge does not match.", status_code=403)
    if data.get("origin") != expected_origin or data.get("crossOrigin") is True:
        raise WebAuthnError("webauthn_origin_mismatch", "Passkey response came from a different Pocket Lab address.", status_code=403)
    return raw


def _parse_authenticator_data(auth_data: bytes, rp_id: str, *, require_attested: bool) -> dict[str, Any]:
    if len(auth_data) < 37:
        raise WebAuthnError("webauthn_authenticator_data_invalid", "Passkey authenticator data is incomplete.", status_code=422)
    if not hmac.compare_digest(auth_data[:32], hashlib.sha256(rp_id.encode("utf-8")).digest()):
        raise WebAuthnError("webauthn_rp_id_mismatch", "Passkey does not belong to this Pocket Lab address.", status_code=403)
    flags = auth_data[32]
    if not (flags & 0x01) or not (flags & 0x04):
        raise WebAuthnError("webauthn_user_verification_required", "Passkey user verification is required.", status_code=403)
    sign_count = struct.unpack(">I", auth_data[33:37])[0]
    result: dict[str, Any] = {"flags": flags, "sign_count": sign_count}
    if require_attested:
        if not (flags & 0x40) or len(auth_data) < 55:
            raise WebAuthnError("webauthn_attested_data_missing", "Passkey registration data is incomplete.", status_code=422)
        offset = 53
        credential_length = struct.unpack(">H", auth_data[offset:offset + 2])[0]
        offset += 2
        credential_id = auth_data[offset:offset + credential_length]
        offset += credential_length
        cose, _ = _cbor_read(auth_data, offset)
        if not isinstance(cose, dict) or cose.get(1) != 2 or cose.get(3) != -7 or cose.get(-1) != 1:
            raise WebAuthnError("webauthn_algorithm_unsupported", "Pocket Lab currently supports ES256 passkeys.", status_code=422)
        x, y = cose.get(-2), cose.get(-3)
        if not isinstance(x, bytes) or not isinstance(y, bytes) or len(x) != 32 or len(y) != 32:
            raise WebAuthnError("webauthn_public_key_invalid", "Passkey public key is invalid.", status_code=422)
        result.update({"credential_id": credential_id, "public_key_x": x, "public_key_y": y})
    return result


def _point_add(p1: tuple[int, int] | None, p2: tuple[int, int] | None) -> tuple[int, int] | None:
    if p1 is None: return p2
    if p2 is None: return p1
    x1, y1 = p1; x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P256_P == 0: return None
    if p1 == p2:
        slope = ((3 * x1 * x1 + P256_A) * pow(2 * y1, -1, P256_P)) % P256_P
    else:
        slope = ((y2 - y1) * pow((x2 - x1) % P256_P, -1, P256_P)) % P256_P
    x3 = (slope * slope - x1 - x2) % P256_P
    y3 = (slope * (x1 - x3) - y1) % P256_P
    return x3, y3


def _point_mul(k: int, point: tuple[int, int]) -> tuple[int, int] | None:
    result = None
    addend: tuple[int, int] | None = point
    while k:
        if k & 1: result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result


def _decode_der_signature(signature: bytes) -> tuple[int, int]:
    try:
        if len(signature) < 8 or signature[0] != 0x30:
            raise ValueError
        idx = 1
        seq_len = signature[idx]; idx += 1
        if seq_len & 0x80:
            count = seq_len & 0x7F
            seq_len = int.from_bytes(signature[idx:idx + count], "big"); idx += count
        if idx + seq_len != len(signature) or signature[idx] != 0x02:
            raise ValueError
        idx += 1; r_len = signature[idx]; idx += 1; r = int.from_bytes(signature[idx:idx + r_len], "big"); idx += r_len
        if signature[idx] != 0x02: raise ValueError
        idx += 1; s_len = signature[idx]; idx += 1; s = int.from_bytes(signature[idx:idx + s_len], "big"); idx += s_len
        if idx != len(signature) or not (1 <= r < P256_N and 1 <= s < P256_N): raise ValueError
        return r, s
    except (IndexError, ValueError) as exc:
        raise WebAuthnError("webauthn_signature_invalid", "Passkey signature is invalid.", status_code=401) from exc


def _verify_es256(public_x: bytes, public_y: bytes, message: bytes, signature: bytes) -> bool:
    x = int.from_bytes(public_x, "big"); y = int.from_bytes(public_y, "big")
    if not (0 < x < P256_P and 0 < y < P256_P) or (y * y - (x * x * x + P256_A * x + P256_B)) % P256_P != 0:
        return False
    r, s = _decode_der_signature(signature)
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    w = pow(s, -1, P256_N)
    point = _point_add(_point_mul((z * w) % P256_N, P256_G), _point_mul((r * w) % P256_N, (x, y)))
    return point is not None and point[0] % P256_N == r


def _registration_material(payload: dict[str, Any], *, challenge: str, origin: str, rp_id: str) -> dict[str, Any]:
    client_raw = _client_data(str(payload.get("clientDataJSON") or ""), expected_type="webauthn.create", expected_challenge=challenge, expected_origin=origin)
    attestation = _unb64url(str(payload.get("attestationObject") or ""))
    decoded, consumed = _cbor_read(attestation, 0)
    if consumed != len(attestation) or not isinstance(decoded, dict) or decoded.get("fmt") != "none" or not isinstance(decoded.get("authData"), bytes):
        raise WebAuthnError("webauthn_attestation_unsupported", "Pocket Lab accepts privacy-preserving none attestation only.", status_code=422)
    parsed = _parse_authenticator_data(decoded["authData"], rp_id, require_attested=True)
    raw_id = _unb64url(str(payload.get("rawId") or payload.get("id") or ""))
    if not raw_id or not hmac.compare_digest(raw_id, parsed["credential_id"]):
        raise WebAuthnError("webauthn_credential_mismatch", "Passkey credential identifier does not match registration data.", status_code=403)
    return {**parsed, "credential_id_text": _b64url(raw_id), "client_hash": hashlib.sha256(client_raw).digest()}


def _assertion_material(payload: dict[str, Any], *, challenge: str, origin: str, rp_id: str, credential: dict[str, Any]) -> dict[str, Any]:
    client_raw = _client_data(str(payload.get("clientDataJSON") or ""), expected_type="webauthn.get", expected_challenge=challenge, expected_origin=origin)
    auth_data = _unb64url(str(payload.get("authenticatorData") or ""))
    parsed = _parse_authenticator_data(auth_data, rp_id, require_attested=False)
    signature = _unb64url(str(payload.get("signature") or ""))
    if not _verify_es256(_unb64url(credential["public_key_x"]), _unb64url(credential["public_key_y"]), auth_data + hashlib.sha256(client_raw).digest(), signature):
        raise WebAuthnError("webauthn_assertion_invalid", "Passkey assertion was not accepted.", status_code=401)
    stored = int(credential.get("sign_count") or 0); current = int(parsed["sign_count"])
    if stored and current and current <= stored:
        raise WebAuthnError("webauthn_counter_replay", "Passkey counter did not advance. Use another sign-in method and review this credential.", status_code=409)
    return parsed


def _insert_credential(tx, *, human_id: str, material: dict[str, Any], friendly_name: str, transports: list[str] | None = None, attachment: str | None = None) -> dict[str, Any]:
    name = str(friendly_name or "Passkey").strip()[:80] or "Passkey"
    credential_id = material["credential_id_text"]
    tx.execute(
        """INSERT INTO webauthn_credentials(
               credential_id,human_id,friendly_name,public_key_x,public_key_y,algorithm,sign_count,
               transports_json,authenticator_attachment,created_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (credential_id, human_id, name, _b64url(material["public_key_x"]), _b64url(material["public_key_y"]), -7,
         int(material.get("sign_count") or 0), json.dumps([str(item)[:32] for item in (transports or [])[:8]]), str(attachment or "")[:40] or None, _iso()),
    )
    return {"credential_id": credential_id, "friendly_name": name}


def complete_owner_claim_registration(*, authority: str, origin: str, challenge: str, payload: dict[str, Any], username: str, display_name: str, friendly_name: str = "Primary passkey") -> dict[str, Any]:
    claim = _claim_from_authority(authority, origin)
    _consume_challenge(raw_challenge=challenge, purpose="owner_claim_register", rp_id=claim["rp_id"], origin=claim["origin"], owner_claim_id=claim["claim_id"])
    material = _registration_material(payload, challenge=challenge, origin=claim["origin"], rp_id=claim["rp_id"])
    human_id = f"human-{uuid.uuid4().hex}"
    now = _iso()
    normalized_username = lite_identity_auth._normalize_username(username)
    display = str(display_name or "Pocket Lab Owner").strip()[:120] or "Pocket Lab Owner"
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current_claim = tx.execute("SELECT * FROM owner_claims WHERE claim_id=?", (claim["claim_id"],)).fetchone()
            if not current_claim or current_claim["completed_at"] or tx.execute("SELECT 1 FROM human_identities WHERE status='active' LIMIT 1").fetchone():
                raise WebAuthnError("identity_owner_exists", "Pocket Lab already has an owner or this claim was completed.", status_code=409)
            tx.execute("INSERT INTO human_identities(human_id,username_normalized,display_name,status,auth_version,created_at,updated_at,last_authenticated_at) VALUES (?,?,?,?,?,?,?,?)",
                       (human_id, normalized_username, display, "active", 1, now, now, now))
            tx.execute("INSERT INTO webauthn_users(human_id,user_handle,created_at) VALUES (?,?,?)", (human_id, claim["webauthn_user_handle"], now))
            credential = _insert_credential(tx, human_id=human_id, material=material, friendly_name=friendly_name, transports=payload.get("transports"), attachment=payload.get("authenticatorAttachment"))
            session = lite_identity_auth._insert_session(tx, human={"human_id": human_id, "auth_version": 1}, method="passkey")
            tx.execute("UPDATE owner_claims SET completed_at=?,authority_hash=NULL,authority_expires_at=NULL WHERE claim_id=?", (now, claim["claim_id"]))
            lite_identity_auth._audit(tx, human_id=human_id, session_id=session["session_id"], event_type="owner.created", reason_code="owner_claim_passkey", summary="Pocket Lab owner created with a passkey.", correlation_id=claim["claim_id"])
            lite_identity_auth._audit(tx, human_id=human_id, session_id=session["session_id"], event_type="passkey.enrolled", reason_code="owner_claim_passkey", summary="Primary owner passkey enrolled.", correlation_id=claim["claim_id"])
    recovery = lite_identity_auth.regenerate_recovery_codes(human_id=human_id, session_id=session["session_id"])
    return {"human_id": human_id, "credential": credential, "session": session, "recovery_codes": recovery["codes"], "claim_id": claim["claim_id"]}


def complete_registration(*, human_id: str, session_id: str, origin: str, challenge: str, payload: dict[str, Any], friendly_name: str) -> dict[str, Any]:
    normalized_origin, rp_id = _normalize_origin(origin)
    _consume_challenge(raw_challenge=challenge, purpose="register", rp_id=rp_id, origin=normalized_origin, human_id=human_id, session_id=session_id)
    material = _registration_material(payload, challenge=challenge, origin=normalized_origin, rp_id=rp_id)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            if tx.execute("SELECT 1 FROM webauthn_credentials WHERE credential_id=?", (material["credential_id_text"],)).fetchone():
                raise WebAuthnError("passkey_already_registered", "That passkey is already registered.", status_code=409)
            credential = _insert_credential(tx, human_id=human_id, material=material, friendly_name=friendly_name, transports=payload.get("transports"), attachment=payload.get("authenticatorAttachment"))
            lite_identity_auth._audit(tx, human_id=human_id, session_id=session_id, event_type="passkey.enrolled", reason_code="passkey_registration", summary="Owner passkey enrolled.")
    return credential


def _credential_for_assertion(credential_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT c.*,h.status AS human_status,h.auth_version,h.username_normalized,h.display_name FROM webauthn_credentials c JOIN human_identities h ON h.human_id=c.human_id WHERE c.credential_id=? AND c.revoked_at IS NULL LIMIT 1", (credential_id,)).fetchone()
    if not row or row["human_status"] != "active":
        raise WebAuthnError("passkey_unknown", "Passkey is not registered or has been revoked.", status_code=401)
    return dict(row)


def complete_login(*, origin: str, challenge: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_origin, rp_id = _normalize_origin(origin)
    credential_id = str(payload.get("rawId") or payload.get("id") or "")
    credential = _credential_for_assertion(credential_id)
    _consume_challenge(raw_challenge=challenge, purpose="login", rp_id=rp_id, origin=normalized_origin, human_id=credential["human_id"])
    assertion = _assertion_material(payload, challenge=challenge, origin=normalized_origin, rp_id=rp_id, credential=credential)
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE webauthn_credentials SET sign_count=?,last_used_at=? WHERE credential_id=?", (max(int(credential.get("sign_count") or 0), int(assertion["sign_count"])), now, credential_id))
            human = {"human_id": credential["human_id"], "auth_version": credential["auth_version"]}
            session = lite_identity_auth._insert_session(tx, human=human, method="passkey")
            tx.execute("UPDATE human_identities SET last_authenticated_at=?,updated_at=? WHERE human_id=?", (now, now, credential["human_id"]))
            lite_identity_auth._audit(tx, human_id=credential["human_id"], session_id=session["session_id"], event_type="session.signed_in", reason_code="passkey_verified", summary="Owner signed in with a passkey.")
    return {"human": {"human_id": credential["human_id"], "username": credential["username_normalized"], "display_name": credential["display_name"]}, **session}


def complete_step_up(*, human_id: str, session_id: str, origin: str, purpose: str, challenge: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_origin, rp_id = _normalize_origin(origin)
    credential_id = str(payload.get("rawId") or payload.get("id") or "")
    credential = _credential_for_assertion(credential_id)
    if credential["human_id"] != human_id:
        raise WebAuthnError("passkey_wrong_owner", "Passkey does not belong to the signed-in owner.", status_code=403)
    bounded_purpose = str(purpose or "sensitive_action")[:80]
    _consume_challenge(raw_challenge=challenge, purpose=f"step_up:{bounded_purpose}", rp_id=rp_id, origin=normalized_origin, human_id=human_id, session_id=session_id)
    assertion = _assertion_material(payload, challenge=challenge, origin=normalized_origin, rp_id=rp_id, credential=credential)
    now = _now(); expires = _iso(now + timedelta(seconds=_bounded_int("POCKETLAB_IDENTITY_STEP_UP_TTL_SECONDS", STEP_UP_TTL_SECONDS, 60, 900)))
    assurance_id = f"assurance-{uuid.uuid4().hex}"
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE webauthn_credentials SET sign_count=?,last_used_at=? WHERE credential_id=?", (max(int(credential.get("sign_count") or 0), int(assertion["sign_count"])), _iso(now), credential_id))
            tx.execute("DELETE FROM auth_session_assurance WHERE session_id=? AND purpose=?", (session_id, bounded_purpose))
            tx.execute("INSERT INTO auth_session_assurance(assurance_id,session_id,credential_id,purpose,satisfied_at,expires_at,created_at) VALUES (?,?,?,?,?,?,?)", (assurance_id, session_id, credential_id, bounded_purpose, _iso(now), expires, _iso(now)))
            lite_identity_auth._audit(tx, human_id=human_id, session_id=session_id, event_type="assurance.satisfied", reason_code="passkey_step_up", summary="Passkey step-up completed for a sensitive action.", correlation_id=assurance_id)
    return {"status": "satisfied", "purpose": bounded_purpose, "expires_at": expires, "credential_id": credential_id}


def valid_assurance(session_id: str) -> list[dict[str, Any]]:
    now = _iso()
    try:
        with connection() as conn:
            rows = conn.execute("SELECT purpose,credential_id,satisfied_at,expires_at FROM auth_session_assurance WHERE session_id=? AND expires_at>? ORDER BY satisfied_at DESC", (session_id, now)).fetchall()
    except Exception:
        return []
    return [dict(row) for row in rows]


def list_credentials(human_id: str) -> list[dict[str, Any]]:
    try:
        with connection() as conn:
            rows = conn.execute("SELECT credential_id,friendly_name,transports_json,authenticator_attachment,created_at,last_used_at,revoked_at FROM webauthn_credentials WHERE human_id=? ORDER BY created_at DESC LIMIT 20", (human_id,)).fetchall()
    except Exception:
        return []
    result = []
    for row in rows:
        item = dict(row)
        try: transports = json.loads(item.pop("transports_json") or "[]")
        except Exception: transports = []
        item["transports"] = transports
        item["active"] = not bool(item.get("revoked_at"))
        result.append(item)
    return result


def rename_credential(*, human_id: str, credential_id: str, friendly_name: str, session_id: str) -> dict[str, Any]:
    name = str(friendly_name or "").strip()[:80]
    if not name:
        raise WebAuthnError("passkey_name_invalid", "Choose a name for this passkey.", status_code=422)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT credential_id FROM webauthn_credentials WHERE credential_id=? AND human_id=? AND revoked_at IS NULL", (credential_id, human_id)).fetchone()
            if not row: raise WebAuthnError("passkey_unknown", "Passkey is not registered or has been revoked.", status_code=404)
            tx.execute("UPDATE webauthn_credentials SET friendly_name=? WHERE credential_id=?", (name, credential_id))
            lite_identity_auth._audit(tx, human_id=human_id, session_id=session_id, event_type="passkey.renamed", reason_code="owner_request", summary="Owner passkey renamed.")
    return {"credential_id": credential_id, "friendly_name": name, "status": "renamed"}


def revoke_credential(*, human_id: str, credential_id: str, session_id: str, correlation_id: str) -> dict[str, Any]:
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT credential_id FROM webauthn_credentials WHERE credential_id=? AND human_id=? AND revoked_at IS NULL", (credential_id, human_id)).fetchone()
            if not row: raise WebAuthnError("passkey_unknown", "Passkey is not registered or has been revoked.", status_code=404)
            active_count = tx.execute("SELECT COUNT(*) AS count FROM webauthn_credentials WHERE human_id=? AND revoked_at IS NULL", (human_id,)).fetchone()["count"]
            password = tx.execute("SELECT 1 FROM human_credentials WHERE human_id=? AND kind='password' AND disabled_at IS NULL LIMIT 1", (human_id,)).fetchone()
            if int(active_count) <= 1 and not password:
                raise WebAuthnError("passkey_last_sign_in_method", "Add another passkey before removing the last passkey.", status_code=409)
            tx.execute("UPDATE webauthn_credentials SET revoked_at=? WHERE credential_id=?", (_iso(), credential_id))
            lite_identity_auth._audit(tx, human_id=human_id, session_id=session_id, event_type="passkey.revoked", reason_code="owner_request", summary="Owner passkey revoked.", correlation_id=correlation_id)
    return {"credential_id": credential_id, "status": "revoked", "summary": "Passkey removed."}


def owner_claim_status(*, authority: str, origin: str) -> dict[str, Any]:
    try:
        claim = _claim_from_authority(authority, origin)
    except WebAuthnError as exc:
        return {"active": False, "status": exc.reason_code, "summary": exc.message}
    return {
        "active": True,
        "status": "claim_verified",
        "expires_at": claim.get("authority_expires_at"),
        "rp_id": claim.get("rp_id"),
        "summary": "Owner claim verified. Create a passkey to finish setup.",
    }
