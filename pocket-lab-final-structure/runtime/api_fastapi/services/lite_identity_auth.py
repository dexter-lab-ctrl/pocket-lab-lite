from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations

COOKIE_NAME = os.environ.get("POCKETLAB_IDENTITY_COOKIE_NAME", "__Host-pocketlab_session")


def cookie_name() -> str:
    secure = os.environ.get("POCKETLAB_IDENTITY_COOKIE_SECURE", "1").strip().lower() not in {"0", "false", "no", "off"}
    if secure:
        return COOKIE_NAME
    return os.environ.get("POCKETLAB_IDENTITY_INSECURE_COOKIE_NAME", "pocketlab_session")


def cookie_secure() -> bool:
    return os.environ.get("POCKETLAB_IDENTITY_COOKIE_SECURE", "1").strip().lower() not in {"0", "false", "no", "off"}


def csrf_cookie_name() -> str:
    if cookie_secure():
        return os.environ.get("POCKETLAB_IDENTITY_CSRF_COOKIE_NAME", "__Host-pocketlab_csrf")
    return os.environ.get("POCKETLAB_IDENTITY_INSECURE_CSRF_COOKIE_NAME", "pocketlab_csrf")


def session_cookie_max_age() -> int:
    return _bounded_int("POCKETLAB_IDENTITY_SESSION_ABSOLUTE_SECONDS", SESSION_ABSOLUTE_SECONDS_DEFAULT, 3600, 30 * 24 * 60 * 60)
PASSWORD_ALGORITHM = "scrypt"
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256
SESSION_IDLE_SECONDS_DEFAULT = 8 * 60 * 60
SESSION_ABSOLUTE_SECONDS_DEFAULT = 7 * 24 * 60 * 60
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_BYTES = 10
_LOGIN_LOCK = threading.Lock()
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}


class IdentityError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 400, retry_after: int = 0):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code
        self.retry_after = max(0, int(retry_after))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


def _normalize_username(value: str) -> str:
    normalized = "-".join(part for part in str(value or "").strip().casefold().replace("_", "-").split("-") if part)
    if not normalized or len(normalized) > 64:
        raise IdentityError("identity_username_invalid", "Choose a valid owner name.", status_code=422)
    if any(not (char.isalnum() or char in {"-", "."}) for char in normalized):
        raise IdentityError("identity_username_invalid", "Choose a valid owner name.", status_code=422)
    return normalized


def _validate_password(value: str) -> str:
    password = str(value or "")
    if "\x00" in password or len(password) < PASSWORD_MIN_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        raise IdentityError(
            "identity_password_invalid",
            f"Password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters.",
            status_code=422,
        )
    return password


def _scrypt_parameters() -> dict[str, int]:
    return {
        "n": _bounded_int("POCKETLAB_IDENTITY_SCRYPT_N", 16384, 4096, 65536),
        "r": _bounded_int("POCKETLAB_IDENTITY_SCRYPT_R", 8, 1, 16),
        "p": _bounded_int("POCKETLAB_IDENTITY_SCRYPT_P", 1, 1, 4),
        "dklen": 32,
    }


def _password_record(password: str) -> tuple[str, str, str]:
    password = _validate_password(password)
    params = _scrypt_parameters()
    salt = secrets.token_bytes(16)
    verifier = hashlib.scrypt(password.encode("utf-8"), salt=salt, **params)
    return (
        base64.urlsafe_b64encode(verifier).decode("ascii"),
        base64.urlsafe_b64encode(salt).decode("ascii"),
        json.dumps(params, sort_keys=True, separators=(",", ":")),
    )


def _verify_password(password: str, credential: dict[str, Any]) -> bool:
    try:
        if credential.get("algorithm") != PASSWORD_ALGORITHM:
            return False
        params = json.loads(str(credential.get("parameters_json") or "{}"))
        salt = base64.urlsafe_b64decode(str(credential.get("salt") or "").encode("ascii"))
        expected = base64.urlsafe_b64decode(str(credential.get("verifier") or "").encode("ascii"))
        actual = hashlib.scrypt(str(password or "").encode("utf-8"), salt=salt, **params)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _hash_opaque(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _session_bounds(now: datetime | None = None) -> tuple[str, str]:
    current = now or _now()
    idle_seconds = _bounded_int(
        "POCKETLAB_IDENTITY_SESSION_IDLE_SECONDS", SESSION_IDLE_SECONDS_DEFAULT, 300, 7 * 24 * 60 * 60
    )
    absolute_seconds = _bounded_int(
        "POCKETLAB_IDENTITY_SESSION_ABSOLUTE_SECONDS",
        SESSION_ABSOLUTE_SECONDS_DEFAULT,
        3600,
        30 * 24 * 60 * 60,
    )
    absolute_seconds = max(absolute_seconds, idle_seconds)
    return _iso(current + timedelta(seconds=idle_seconds)), _iso(current + timedelta(seconds=absolute_seconds))


def _audit(tx, *, human_id: str | None, session_id: str | None, event_type: str, reason_code: str, summary: str, correlation_id: str | None = None) -> None:
    tx.execute(
        """INSERT INTO identity_audit_events(
               occurred_at,human_id,session_id,event_type,reason_code,summary,correlation_id
           ) VALUES (?,?,?,?,?,?,?)""",
        (
            _iso(),
            human_id,
            session_id,
            str(event_type)[:80],
            str(reason_code)[:80],
            str(summary)[:240],
            str(correlation_id or uuid.uuid4().hex)[:80],
        ),
    )
    retention = _bounded_int("POCKETLAB_IDENTITY_AUDIT_RETENTION", 500, 50, 5000)
    tx.execute(
        "DELETE FROM identity_audit_events WHERE event_id NOT IN (SELECT event_id FROM identity_audit_events ORDER BY event_id DESC LIMIT ?)",
        (retention,),
    )


def initialize_identity_runtime() -> dict[str, Any]:
    apply_migrations()
    bootstrap_password = os.environ.get("POCKETLAB_IDENTITY_BOOTSTRAP_PASSWORD", "")
    if not bootstrap_password:
        return {"initialized": True, "bootstrapped": False}
    with connection() as conn:
        row = conn.execute("SELECT human_id FROM human_identities LIMIT 1").fetchone()
    if row:
        return {"initialized": True, "bootstrapped": False}
    username = os.environ.get("POCKETLAB_IDENTITY_BOOTSTRAP_USERNAME", "owner")
    display_name = os.environ.get("POCKETLAB_IDENTITY_BOOTSTRAP_DISPLAY_NAME", "Pocket Lab Owner")
    _create_owner(username=username, display_name=display_name, password=bootstrap_password, event_reason="environment_bootstrap")
    return {"initialized": True, "bootstrapped": True}


def owner_exists() -> bool:
    apply_migrations()
    with connection() as conn:
        return conn.execute("SELECT 1 FROM human_identities WHERE status='active' LIMIT 1").fetchone() is not None


def _create_owner(*, username: str, display_name: str, password: str, event_reason: str) -> dict[str, Any]:
    normalized = _normalize_username(username)
    display = str(display_name or "Pocket Lab Owner").strip()[:120] or "Pocket Lab Owner"
    verifier, salt, parameters = _password_record(password)
    human_id = f"human-{uuid.uuid4().hex}"
    credential_id = f"cred-{uuid.uuid4().hex}"
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            if tx.execute("SELECT 1 FROM human_identities LIMIT 1").fetchone():
                raise IdentityError("identity_owner_exists", "Pocket Lab already has an owner.", status_code=409)
            tx.execute(
                "INSERT INTO human_identities(human_id,username_normalized,display_name,status,auth_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (human_id, normalized, display, "active", 1, now, now),
            )
            tx.execute(
                "INSERT INTO human_credentials(credential_id,human_id,kind,verifier,salt,algorithm,parameters_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (credential_id, human_id, "password", verifier, salt, PASSWORD_ALGORITHM, parameters, now),
            )
            _audit(
                tx,
                human_id=human_id,
                session_id=None,
                event_type="owner.created",
                reason_code=event_reason,
                summary="Pocket Lab owner identity created.",
            )
    return {"human_id": human_id, "username": normalized, "display_name": display, "status": "active"}


def setup_owner(*, username: str, display_name: str, password: str, setup_token: str) -> dict[str, Any]:
    configured = os.environ.get("POCKETLAB_IDENTITY_SETUP_TOKEN", "")
    if not configured:
        raise IdentityError(
            "identity_setup_unavailable",
            "Owner setup is not enabled. Configure a one-time setup token on the server.",
            status_code=503,
        )
    if not hmac.compare_digest(str(setup_token or ""), configured):
        raise IdentityError("identity_setup_rejected", "Owner setup could not be verified.", status_code=401)
    return _create_owner(username=username, display_name=display_name, password=password, event_reason="one_time_setup")


def _credential_for_human(conn, human_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM human_credentials WHERE human_id=? AND kind='password' AND disabled_at IS NULL ORDER BY created_at DESC LIMIT 1",
        (human_id,),
    ).fetchone()
    return dict(row) if row else None


def _owner_by_username(conn, username: str) -> dict[str, Any] | None:
    try:
        normalized = _normalize_username(username)
    except IdentityError:
        return None
    row = conn.execute(
        "SELECT * FROM human_identities WHERE username_normalized=? AND status='active' LIMIT 1",
        (normalized,),
    ).fetchone()
    return dict(row) if row else None


def _rate_key(username: str, source: str) -> str:
    return hashlib.sha256(f"{str(username).casefold()}|{source}".encode("utf-8")).hexdigest()


def _check_rate_limit(username: str, source: str) -> None:
    window = _bounded_int("POCKETLAB_IDENTITY_LOGIN_WINDOW_SECONDS", 300, 30, 3600)
    maximum = _bounded_int("POCKETLAB_IDENTITY_LOGIN_MAX_ATTEMPTS", 8, 3, 50)
    now = time.monotonic()
    key = _rate_key(username, source)
    with _LOGIN_LOCK:
        attempts = [value for value in _LOGIN_ATTEMPTS.get(key, []) if now - value < window]
        _LOGIN_ATTEMPTS[key] = attempts
        if len(attempts) >= maximum:
            retry = max(1, int(window - (now - attempts[0])))
            raise IdentityError("identity_login_throttled", "Sign-in is temporarily limited. Try again shortly.", status_code=429, retry_after=retry)


def _record_failed_login(username: str, source: str) -> None:
    key = _rate_key(username, source)
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.setdefault(key, []).append(time.monotonic())
        _LOGIN_ATTEMPTS[key] = _LOGIN_ATTEMPTS[key][-50:]


def _clear_failed_login(username: str, source: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(_rate_key(username, source), None)


def _new_session_values() -> tuple[str, str, str, str]:
    session_id = f"sess-{uuid.uuid4().hex}"
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    return session_id, token, csrf, _hash_opaque(token)


def _insert_session(tx, *, human: dict[str, Any], method: str) -> dict[str, Any]:
    session_id, token, csrf, token_hash = _new_session_values()
    now = _now()
    idle_expiry, absolute_expiry = _session_bounds(now)
    tx.execute(
        """INSERT INTO auth_sessions(
               session_id,token_hash,csrf_hash,human_id,auth_version,auth_method,
               created_at,last_seen_at,idle_expires_at,absolute_expires_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            session_id,
            token_hash,
            _hash_opaque(csrf),
            human["human_id"],
            int(human["auth_version"]),
            method,
            _iso(now),
            _iso(now),
            idle_expiry,
            absolute_expiry,
        ),
    )
    session_history = _bounded_int("POCKETLAB_IDENTITY_SESSION_HISTORY", 100, 20, 1000)
    tx.execute(
        """DELETE FROM auth_sessions WHERE human_id=? AND revoked_at IS NOT NULL AND session_id NOT IN (
               SELECT session_id FROM auth_sessions WHERE human_id=? ORDER BY created_at DESC LIMIT ?
           )""",
        (human["human_id"], human["human_id"], session_history),
    )
    return {
        "session_id": session_id,
        "session_token": token,
        "csrf_token": csrf,
        "idle_expires_at": idle_expiry,
        "absolute_expires_at": absolute_expiry,
        "auth_method": method,
    }


def login(*, username: str, password: str, source: str = "") -> dict[str, Any]:
    apply_migrations()
    _check_rate_limit(username, source)
    with connection() as conn:
        human = _owner_by_username(conn, username)
        credential = _credential_for_human(conn, human["human_id"]) if human else None
    if not human or not credential or not _verify_password(password, credential):
        _record_failed_login(username, source)
        # Keep authentication failure generic and timing less distinguishable.
        if not credential:
            dummy = _password_record("pocket-lab-dummy-password")
            _verify_password(password, {"algorithm": PASSWORD_ALGORITHM, "verifier": dummy[0], "salt": dummy[1], "parameters_json": dummy[2]})
        raise IdentityError("identity_login_failed", "Sign-in details were not accepted.", status_code=401)
    _clear_failed_login(username, source)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current = tx.execute("SELECT * FROM human_identities WHERE human_id=? AND status='active'", (human["human_id"],)).fetchone()
            if not current:
                raise IdentityError("identity_login_failed", "Sign-in details were not accepted.", status_code=401)
            current_human = dict(current)
            session = _insert_session(tx, human=current_human, method="password")
            now = _iso()
            tx.execute("UPDATE human_identities SET last_authenticated_at=?,updated_at=? WHERE human_id=?", (now, now, current_human["human_id"]))
            _audit(tx, human_id=current_human["human_id"], session_id=session["session_id"], event_type="session.signed_in", reason_code="password_verified", summary="Owner signed in.")
    return {"human": {"human_id": human["human_id"], "username": human["username_normalized"], "display_name": human["display_name"]}, **session}


def _session_row_from_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    with connection() as conn:
        row = conn.execute(
            """SELECT s.*,h.username_normalized,h.display_name,h.status AS human_status,h.auth_version AS current_auth_version
               FROM auth_sessions s JOIN human_identities h ON h.human_id=s.human_id
               WHERE s.token_hash=? LIMIT 1""",
            (_hash_opaque(token),),
        ).fetchone()
    if not row:
        return None
    session = dict(row)
    now = _now()
    idle = _parse_iso(session.get("idle_expires_at"))
    absolute = _parse_iso(session.get("absolute_expires_at"))
    if session.get("revoked_at") or session.get("human_status") != "active":
        return None
    if int(session.get("auth_version") or 0) != int(session.get("current_auth_version") or -1):
        return None
    if idle is None or absolute is None or now >= idle or now >= absolute:
        return None
    return session


def authenticate_session_token(token: str) -> dict[str, Any] | None:
    session = _session_row_from_token(token)
    if not session:
        return None
    assurance: list[dict[str, Any]] = []
    try:
        with connection() as conn:
            rows = conn.execute(
                """SELECT purpose,credential_id,satisfied_at,expires_at
                   FROM auth_session_assurance
                   WHERE session_id=? AND expires_at>? ORDER BY satisfied_at DESC LIMIT 12""",
                (session["session_id"], _iso()),
            ).fetchall()
            assurance = [dict(row) for row in rows]
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
    return {
        "actor": {
            "identity_id": session["human_id"],
            "type": "human",
            "display_name": session["display_name"],
        },
        "session": {
            "session_id": session["session_id"],
            "authenticated": True,
            "auth_method": session["auth_method"],
            "csrf_hash": session["csrf_hash"],
            "idle_expires_at": session["idle_expires_at"],
            "absolute_expires_at": session["absolute_expires_at"],
            "expiry_mode": "fixed",
            "assurance": assurance,
        },
    }


def csrf_matches(auth_context: dict[str, Any], csrf_token: str) -> bool:
    expected = str((auth_context.get("session") or {}).get("csrf_hash") or "")
    return bool(expected and csrf_token and hmac.compare_digest(expected, _hash_opaque(csrf_token)))


def revoke_session(*, human_id: str, session_id: str, reason: str = "owner_revoked") -> bool:
    apply_migrations()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT session_id FROM auth_sessions WHERE session_id=? AND human_id=? AND revoked_at IS NULL", (session_id, human_id)).fetchone()
            if not row:
                return False
            tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason=? WHERE session_id=?", (_iso(), reason[:80], session_id))
            _audit(tx, human_id=human_id, session_id=session_id, event_type="session.revoked", reason_code=reason, summary="Owner session revoked.")
            return True


def revoke_other_sessions(*, human_id: str, current_session_id: str) -> int:
    apply_migrations()
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            rows = tx.execute("SELECT session_id FROM auth_sessions WHERE human_id=? AND session_id<>? AND revoked_at IS NULL", (human_id, current_session_id)).fetchall()
            tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason='owner_revoke_others' WHERE human_id=? AND session_id<>? AND revoked_at IS NULL", (now, human_id, current_session_id))
            _audit(tx, human_id=human_id, session_id=current_session_id, event_type="session.others_revoked", reason_code="owner_revoke_others", summary="Other owner sessions revoked.")
            return len(rows)


def logout(*, human_id: str, session_id: str) -> bool:
    return revoke_session(human_id=human_id, session_id=session_id, reason="owner_logout")


def change_password(*, human_id: str, session_id: str, current_password: str, new_password: str) -> dict[str, Any]:
    _validate_password(new_password)
    apply_migrations()
    with connection() as conn:
        human_row = conn.execute("SELECT * FROM human_identities WHERE human_id=? AND status='active'", (human_id,)).fetchone()
        credential = _credential_for_human(conn, human_id)
    if not human_row or not credential or not _verify_password(current_password, credential):
        raise IdentityError("identity_current_password_invalid", "Current password was not accepted.", status_code=401)
    verifier, salt, parameters = _password_record(new_password)
    new_token = secrets.token_urlsafe(32)
    new_csrf = secrets.token_urlsafe(24)
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current = tx.execute("SELECT * FROM human_identities WHERE human_id=? AND status='active'", (human_id,)).fetchone()
            if not current:
                raise IdentityError("identity_session_invalid", "Sign in again to continue.", status_code=401)
            new_version = int(current["auth_version"] or 0) + 1
            tx.execute("UPDATE human_credentials SET disabled_at=? WHERE human_id=? AND kind='password' AND disabled_at IS NULL", (now, human_id))
            tx.execute(
                "INSERT INTO human_credentials(credential_id,human_id,kind,verifier,salt,algorithm,parameters_json,created_at,rotated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"cred-{uuid.uuid4().hex}", human_id, "password", verifier, salt, PASSWORD_ALGORITHM, parameters, now, now),
            )
            tx.execute("UPDATE human_identities SET auth_version=?,updated_at=? WHERE human_id=?", (new_version, now, human_id))
            credential_history = _bounded_int("POCKETLAB_IDENTITY_CREDENTIAL_HISTORY", 5, 1, 20)
            tx.execute(
                """DELETE FROM human_credentials WHERE human_id=? AND disabled_at IS NOT NULL AND credential_id NOT IN (
                       SELECT credential_id FROM human_credentials WHERE human_id=? AND disabled_at IS NOT NULL ORDER BY created_at DESC LIMIT ?
                   )""",
                (human_id, human_id, credential_history),
            )
            tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason='password_changed' WHERE human_id=? AND session_id<>? AND revoked_at IS NULL", (now, human_id, session_id))
            idle_expiry, absolute_expiry = _session_bounds()
            updated = tx.execute(
                """UPDATE auth_sessions SET token_hash=?,csrf_hash=?,auth_version=?,last_seen_at=?,idle_expires_at=?,absolute_expires_at=?
                   WHERE session_id=? AND human_id=? AND revoked_at IS NULL""",
                (_hash_opaque(new_token), _hash_opaque(new_csrf), new_version, now, idle_expiry, absolute_expiry, session_id, human_id),
            )
            if updated.rowcount != 1:
                raise IdentityError("identity_session_invalid", "Sign in again to continue.", status_code=401)
            _audit(tx, human_id=human_id, session_id=session_id, event_type="credential.password_changed", reason_code="owner_confirmed", summary="Owner password changed and other sessions were revoked.")
    return {"session_token": new_token, "csrf_token": new_csrf, "session_id": session_id, "auth_version": new_version, "idle_expires_at": idle_expiry, "absolute_expires_at": absolute_expiry}


def _new_recovery_code() -> str:
    raw = base64.b32encode(secrets.token_bytes(RECOVERY_CODE_BYTES)).decode("ascii").rstrip("=")
    return "-".join(raw[index:index + 4] for index in range(0, len(raw), 4))


def regenerate_recovery_codes(*, human_id: str, session_id: str) -> dict[str, Any]:
    apply_migrations()
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    now = _iso()
    batch_id = f"recovery-{uuid.uuid4().hex}"
    with connection() as conn:
        with begin_immediate(conn) as tx:
            human = tx.execute("SELECT human_id FROM human_identities WHERE human_id=? AND status='active'", (human_id,)).fetchone()
            if not human:
                raise IdentityError("identity_session_invalid", "Sign in again to continue.", status_code=401)
            generation_row = tx.execute("SELECT COALESCE(MAX(generation),0)+1 AS next_generation FROM recovery_code_batches WHERE human_id=?", (human_id,)).fetchone()
            generation = int(generation_row["next_generation"] if generation_row else 1)
            tx.execute("UPDATE recovery_code_batches SET invalidated_at=? WHERE human_id=? AND invalidated_at IS NULL", (now, human_id))
            tx.execute("INSERT INTO recovery_code_batches(batch_id,human_id,generation,created_at) VALUES (?,?,?,?)", (batch_id, human_id, generation, now))
            recovery_history = _bounded_int("POCKETLAB_IDENTITY_RECOVERY_BATCH_HISTORY", 10, 1, 50)
            tx.execute(
                """DELETE FROM recovery_code_batches WHERE human_id=? AND invalidated_at IS NOT NULL AND batch_id NOT IN (
                       SELECT batch_id FROM recovery_code_batches WHERE human_id=? AND invalidated_at IS NOT NULL ORDER BY generation DESC LIMIT ?
                   )""",
                (human_id, human_id, recovery_history),
            )
            for code in codes:
                tx.execute("INSERT INTO recovery_codes(code_id,batch_id,code_hash,created_at) VALUES (?,?,?,?)", (f"rcode-{uuid.uuid4().hex}", batch_id, _hash_opaque(code.replace("-", "").casefold()), now))
            _audit(tx, human_id=human_id, session_id=session_id, event_type="recovery.regenerated", reason_code="owner_confirmed", summary="Owner recovery codes regenerated.")
    return {"batch_id": batch_id, "generation": generation, "codes": codes, "created_at": now}


def recover_with_code(*, username: str, recovery_code: str, new_password: str, source: str = "") -> dict[str, Any]:
    _check_rate_limit(username, f"recovery:{source}")
    _validate_password(new_password)
    normalized_code = str(recovery_code or "").replace("-", "").strip().casefold()
    if len(normalized_code) < 12:
        _record_failed_login(username, f"recovery:{source}")
        raise IdentityError("identity_recovery_failed", "Recovery details were not accepted.", status_code=401)
    verifier, salt, parameters = _password_record(new_password)
    code_hash = _hash_opaque(normalized_code)
    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            human = _owner_by_username(tx, username)
            if not human:
                _record_failed_login(username, f"recovery:{source}")
                raise IdentityError("identity_recovery_failed", "Recovery details were not accepted.", status_code=401)
            code = tx.execute(
                """SELECT c.code_id,c.batch_id FROM recovery_codes c
                   JOIN recovery_code_batches b ON b.batch_id=c.batch_id
                   WHERE b.human_id=? AND b.invalidated_at IS NULL AND c.code_hash=? AND c.consumed_at IS NULL LIMIT 1""",
                (human["human_id"], code_hash),
            ).fetchone()
            if not code:
                _record_failed_login(username, f"recovery:{source}")
                raise IdentityError("identity_recovery_failed", "Recovery details were not accepted.", status_code=401)
            consumed = tx.execute("UPDATE recovery_codes SET consumed_at=? WHERE code_id=? AND consumed_at IS NULL", (now, code["code_id"]))
            if consumed.rowcount != 1:
                raise IdentityError("identity_recovery_failed", "Recovery details were not accepted.", status_code=409)
            new_version = int(human["auth_version"] or 0) + 1
            tx.execute("UPDATE human_credentials SET disabled_at=? WHERE human_id=? AND kind='password' AND disabled_at IS NULL", (now, human["human_id"]))
            tx.execute(
                "INSERT INTO human_credentials(credential_id,human_id,kind,verifier,salt,algorithm,parameters_json,created_at,rotated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"cred-{uuid.uuid4().hex}", human["human_id"], "password", verifier, salt, PASSWORD_ALGORITHM, parameters, now, now),
            )
            tx.execute("UPDATE human_identities SET auth_version=?,updated_at=? WHERE human_id=?", (new_version, now, human["human_id"]))
            credential_history = _bounded_int("POCKETLAB_IDENTITY_CREDENTIAL_HISTORY", 5, 1, 20)
            tx.execute(
                """DELETE FROM human_credentials WHERE human_id=? AND disabled_at IS NOT NULL AND credential_id NOT IN (
                       SELECT credential_id FROM human_credentials WHERE human_id=? AND disabled_at IS NOT NULL ORDER BY created_at DESC LIMIT ?
                   )""",
                (human["human_id"], human["human_id"], credential_history),
            )
            tx.execute("UPDATE auth_sessions SET revoked_at=?,revoke_reason='recovery_used' WHERE human_id=? AND revoked_at IS NULL", (now, human["human_id"]))
            current = dict(human)
            current["auth_version"] = new_version
            session = _insert_session(tx, human=current, method="recovery_code")
            _audit(tx, human_id=human["human_id"], session_id=session["session_id"], event_type="recovery.used", reason_code="recovery_code_consumed", summary="Owner recovered access with a one-time code.")
    _clear_failed_login(username, f"recovery:{source}")
    return {"human": {"human_id": human["human_id"], "username": human["username_normalized"], "display_name": human["display_name"]}, **session}


def identity_projection(auth_context: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with connection() as conn:
            owner_row = conn.execute(
                "SELECT human_id,username_normalized,display_name,status,auth_version,created_at,updated_at,last_authenticated_at "
                "FROM human_identities ORDER BY created_at LIMIT 1"
            ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        return {
            "status": "setup_required",
            "summary": "Create the local Pocket Lab owner before protected changes can run.",
            "setup_required": True,
            "authenticated": False,
            "owner": None,
            "session": None,
            "sessions": [],
            "passkeys": [],
            "recovery": {"configured": False, "remaining": 0, "generation": 0},
            "recent_activity": [],
            "sign_in_methods": {"password": True, "passkey": False, "oidc": False},
            "session_expiry_mode": "fixed",
            "updated_at": _iso(),
        }

    owner = dict(owner_row) if owner_row else None
    sessions: list[dict[str, Any]] = []
    passkeys: list[dict[str, Any]] = []
    recovery = {"configured": False, "remaining": 0, "generation": 0}
    activity: list[dict[str, Any]] = []
    password_configured = False
    passkey_available = False
    actor_id = str(((auth_context or {}).get("actor") or {}).get("identity_id") or "")
    current_session_id = str(((auth_context or {}).get("session") or {}).get("session_id") or "")

    if owner:
        try:
            with connection() as conn:
                password_configured = conn.execute(
                    "SELECT 1 FROM human_credentials WHERE human_id=? AND kind='password' AND disabled_at IS NULL LIMIT 1",
                    (owner["human_id"],),
                ).fetchone() is not None
                try:
                    passkey_available = conn.execute(
                        "SELECT 1 FROM webauthn_credentials WHERE human_id=? AND revoked_at IS NULL LIMIT 1",
                        (owner["human_id"],),
                    ).fetchone() is not None
                except sqlite3.OperationalError as exc:
                    if "no such table" not in str(exc).lower():
                        raise
                if actor_id == owner["human_id"]:
                    now = _now()
                    for row in conn.execute(
                        "SELECT session_id,auth_method,created_at,last_seen_at,idle_expires_at,absolute_expires_at,revoked_at "
                        "FROM auth_sessions WHERE human_id=? ORDER BY created_at DESC LIMIT 20",
                        (owner["human_id"],),
                    ):
                        item = dict(row)
                        idle = _parse_iso(item.get("idle_expires_at"))
                        absolute = _parse_iso(item.get("absolute_expires_at"))
                        active = not item.get("revoked_at") and idle is not None and absolute is not None and now < idle and now < absolute
                        assurances = []
                        try:
                            assurances = [dict(value) for value in conn.execute(
                                "SELECT purpose,credential_id,satisfied_at,expires_at FROM auth_session_assurance "
                                "WHERE session_id=? AND expires_at>? ORDER BY satisfied_at DESC LIMIT 8",
                                (item["session_id"], _iso(now)),
                            )]
                        except sqlite3.OperationalError as exc:
                            if "no such table" not in str(exc).lower():
                                raise
                        sessions.append({
                            "session_id": item["session_id"],
                            "auth_method": item["auth_method"],
                            "created_at": item["created_at"],
                            "last_seen_at": item["last_seen_at"],
                            "idle_expires_at": item["idle_expires_at"],
                            "absolute_expires_at": item["absolute_expires_at"],
                            "expiry_mode": "fixed",
                            "active": active,
                            "current": item["session_id"] == current_session_id,
                            "assurance": assurances,
                        })
                    batch = conn.execute(
                        "SELECT batch_id,generation FROM recovery_code_batches WHERE human_id=? AND invalidated_at IS NULL ORDER BY generation DESC LIMIT 1",
                        (owner["human_id"],),
                    ).fetchone()
                    if batch:
                        remaining_row = conn.execute(
                            "SELECT COUNT(*) AS count FROM recovery_codes WHERE batch_id=? AND consumed_at IS NULL",
                            (batch["batch_id"],),
                        ).fetchone()
                        recovery = {
                            "configured": True,
                            "remaining": int(remaining_row["count"] if remaining_row else 0),
                            "generation": int(batch["generation"]),
                        }
                    activity = [dict(row) for row in conn.execute(
                        "SELECT occurred_at,event_type,reason_code,summary,correlation_id FROM identity_audit_events "
                        "WHERE human_id=? ORDER BY event_id DESC LIMIT 20",
                        (owner["human_id"],),
                    )]
                    try:
                        credential_rows = conn.execute(
                            "SELECT credential_id,friendly_name,transports_json,authenticator_attachment,created_at,last_used_at,revoked_at "
                            "FROM webauthn_credentials WHERE human_id=? ORDER BY created_at DESC LIMIT 20",
                            (owner["human_id"],),
                        ).fetchall()
                        for row in credential_rows:
                            item = dict(row)
                            try:
                                transports = json.loads(item.pop("transports_json") or "[]")
                            except Exception:
                                transports = []
                            item["transports"] = transports
                            item["active"] = not bool(item.get("revoked_at"))
                            passkeys.append(item)
                    except sqlite3.OperationalError as exc:
                        if "no such table" not in str(exc).lower():
                            raise
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise

    authenticated = bool(owner and auth_context and ((auth_context.get("actor") or {}).get("identity_id") == owner["human_id"]))
    session_payload = None
    if authenticated:
        session_context = (auth_context or {}).get("session") or {}
        session_payload = {
            "session_id": session_context.get("session_id"),
            "authenticated": True,
            "auth_method": session_context.get("auth_method"),
            "idle_expires_at": session_context.get("idle_expires_at"),
            "absolute_expires_at": session_context.get("absolute_expires_at"),
            "expiry_mode": "fixed",
            "assurance": session_context.get("assurance") or [],
        }
    active_passkeys = [item for item in passkeys if item.get("active")] if authenticated else []
    try:
        from . import lite_enterprise_identity

        enterprise = lite_enterprise_identity.enterprise_projection(auth_context)
    except Exception:
        # Identity remains usable while an additive Enterprise migration is
        # rolling out; Enterprise routes themselves continue to fail closed.
        enterprise = {"enabled": False, "current_membership": None, "roles": [], "updated_at": None}
    return {
        "status": "ready" if owner else "setup_required",
        "summary": "Owner access is protected by server-side sessions." if owner else "Create the local Pocket Lab owner before protected changes can run.",
        "setup_required": owner is None,
        "authenticated": authenticated,
        "owner": None if owner is None else (
            {
                "human_id": owner["human_id"],
                "username": owner["username_normalized"],
                "display_name": owner["display_name"],
                "status": owner["status"],
                "last_authenticated_at": owner["last_authenticated_at"],
                "password_configured": password_configured,
                "password_algorithm": PASSWORD_ALGORITHM if password_configured else None,
            }
            if authenticated else {"configured": True, "status": owner["status"]}
        ),
        "session": session_payload,
        "sessions": sessions,
        "passkeys": passkeys if authenticated else [],
        "recovery": recovery,
        "recent_activity": activity,
        "sign_in_methods": {"password": password_configured or owner is None, "passkey": bool(active_passkeys) if authenticated else passkey_available, "oidc": False},
        "enterprise": enterprise,
        "session_expiry_mode": "fixed",
        "updated_at": _iso(),
    }
