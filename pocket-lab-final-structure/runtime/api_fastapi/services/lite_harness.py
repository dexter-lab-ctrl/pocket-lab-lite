"""Backend-owned synthetic-principal qualification and maintenance harness.

The harness is deliberately separate from human Identity, the normal service
API-token path, the browser, and the developer MCP. It is a short-lived,
loopback-only admission layer for explicitly enabled qualification runtimes.
The module owns profile resolution and cryptographic verification; callers
never supply roles, capabilities, or Owner authority.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations

HARNESS_SESSION_HEADER = "x-pocket-lab-harness-session"
HARNESS_TARGET_SCOPE = "local_server_host_only"
HARNESS_RUNTIME_ENVIRONMENT = "qualification"
HARNESS_AUTH_METHOD = "harness_session"
HARNESS_PROVISIONING_HEADER = "x-pocket-lab-harness-provisioning"
HARNESS_PROVISIONING_TOKEN_HEADER = "x-pocket-lab-harness-provisioning-token"

_PRINCIPAL_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
_PURPOSE_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,79}$")
_TARGET_SCOPE_RE = re.compile(r"^[a-z][a-z0-9._-]{2,63}$")
_B64U_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_PRODUCTION_ENVIRONMENTS = frozenset({"production", "release", "prod"})
_DESTRUCTIVE_ACTIONS = frozenset({
    "device.remove",
    "restore.apply",
    "backup.location.manage",
    "rules.activate",
    "rules.rollback",
})


class HarnessError(RuntimeError):
    """Sanitized harness failure that is safe to expose as an API reason."""

    def __init__(self, reason_code: str, message: str, *, status_code: int = 403):
        super().__init__(message)
        self.reason_code = str(reason_code or "harness_rejected")[:80]
        self.message = str(message or "The harness request was rejected.")[:240]
        self.status_code = int(status_code)


class HarnessConfigurationError(HarnessError):
    """Fatal startup configuration error."""


_PROFILE_DATA: dict[str, dict[str, Any]] = {
    "debug-observer": {
        "principal_class": "debug",
        "environment_scope": HARNESS_RUNTIME_ENVIRONMENT,
        "availability": "qualification-only",
        "capabilities": (
            "status.read", "fleet.read", "recovery.read", "security.read",
            "identity.read_sanitized", "rules.read", "diagnostics.read",
            "projection.read", "evidence.read_sanitized",
        ),
        "destructive_capabilities": (),
    },
    "test-runner": {
        "principal_class": "test",
        "environment_scope": HARNESS_RUNTIME_ENVIRONMENT,
        "availability": "qualification-only",
        "capabilities": ("diagnostics.read", "test.safe", "projection.refresh", "health.probe"),
        "destructive_capabilities": (),
    },
    "security-qualifier": {
        "principal_class": "qualification",
        "environment_scope": HARNESS_RUNTIME_ENVIRONMENT,
        "availability": "qualification-only",
        "capabilities": (
            "security.read", "security.scan.quick", "security.scan.full",
            "security.scan.app", "security.evidence.read",
        ),
        "destructive_capabilities": (),
    },
    "recovery-qualifier": {
        "principal_class": "qualification",
        "environment_scope": HARNESS_RUNTIME_ENVIRONMENT,
        "availability": "qualification-only",
        "capabilities": (
            "recovery.read", "backup.create", "backup.verify", "restore.preview",
        ),
        "destructive_capabilities": (),
    },
    "release-qualifier": {
        "principal_class": "qualification",
        "environment_scope": HARNESS_RUNTIME_ENVIRONMENT,
        "availability": "qualification-only",
        "capabilities": (
            "release.read", "health.probe", "diagnostics.read", "evidence.read_sanitized",
        ),
        "destructive_capabilities": (),
    },
    "maintenance-runner": {
        "principal_class": "maintenance",
        "environment_scope": "maintenance",
        "availability": "deferred",
        "capabilities": (
            "status.read", "diagnostics.read", "agent.restart", "projection.refresh",
            "backup.verify", "health.probe",
        ),
        "destructive_capabilities": (),
    },
    "qualification-owner": {
        "principal_class": "qualification",
        "environment_scope": HARNESS_RUNTIME_ENVIRONMENT,
        "availability": "qualification-only",
        "capabilities": (
            "qualification.read", "status.read", "fleet.read", "recovery.read",
            "security.read", "diagnostics.read", "evidence.read_sanitized",
            "health.probe", "backup.create", "backup.verify", "backup.location.manage",
            "restore.preview", "restore.apply", "device.remove", "catalog.install",
            "identity.passkey.revoke", "rules.read", "rules.simulate", "rules.draft",
            "rules.activate", "rules.rollback",
        ),
        "destructive_capabilities": ("device.remove", "restore.apply", "backup.location.manage", "rules.activate", "rules.rollback"),
    },
}
PROFILE_DATA: Mapping[str, Mapping[str, Any]] = MappingProxyType({
    name: MappingProxyType({
        **profile,
        "capabilities": tuple(profile["capabilities"]),
        "destructive_capabilities": tuple(profile["destructive_capabilities"]),
    })
    for name, profile in _PROFILE_DATA.items()
})

_ACTION_CAPABILITY: Mapping[str, str] = MappingProxyType({
    "catalog.install": "catalog.install",
    "device.remove": "device.remove",
    "identity.passkey.revoke": "identity.passkey.revoke",
    "security.read": "security.read",
    "security.scan.quick": "security.scan.quick",
    "security.scan.full": "security.scan.full",
    "security.scan.app": "security.scan.app",
    "security.evidence.read": "security.evidence.read",
    "backup.create": "backup.create",
    "backup.verify": "backup.verify",
    "backup.location.manage": "backup.location.manage",
    "restore.preview": "restore.preview",
    "restore.apply": "restore.apply",
    "rules.draft": "rules.draft",
    "rules.activate": "rules.activate",
    "rules.rollback": "rules.rollback",
    "rules.read": "rules.read",
    "rules.simulate": "rules.simulate",
})


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
    except (TypeError, ValueError):
        value = default
    return min(max(value, minimum), maximum)


def _flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().casefold() in {"1", "true", "yes", "on"}


def environment() -> str:
    return os.environ.get("POCKETLAB_ENVIRONMENT", "development").strip().casefold() or "development"


def harness_enabled() -> bool:
    return _flag("POCKETLAB_HARNESS_ENABLED")


def destructive_enabled() -> bool:
    return _flag("POCKETLAB_HARNESS_DESTRUCTIVE")


def qualification_owner_enabled() -> bool:
    return _flag("POCKETLAB_QUALIFICATION_OWNER")


def _runtime_id() -> str:
    configured = os.environ.get("POCKETLAB_HARNESS_RUNTIME_ID", "").strip()
    if configured:
        if not _TARGET_SCOPE_RE.fullmatch(configured):
            raise HarnessConfigurationError(
                "harness_runtime_id_invalid",
                "The configured harness runtime identity is invalid.",
                status_code=503,
            )
        return configured[:64]
    try:
        from .. import deps

        state = str(deps.settings().state_dir.resolve())
    except Exception:
        state = "pocketlab-default-runtime"
    return "runtime-" + hashlib.sha256(state.encode("utf-8")).hexdigest()[:32]


def validate_startup_configuration(*, environment_name: str | None = None) -> dict[str, Any]:
    """Fail closed for unsafe harness flags before normal app startup."""
    env = str(environment_name or environment()).strip().casefold() or "development"
    harness = harness_enabled()
    destructive = destructive_enabled()
    owner = qualification_owner_enabled()
    test_bypass = _flag("POCKETLAB_TEST_AUTH_BYPASS")
    unsafe_flags = harness or destructive or owner or test_bypass
    if env in _PRODUCTION_ENVIRONMENTS and unsafe_flags:
        raise HarnessConfigurationError(
            "harness_forbidden_in_production",
            "Production runtime refuses synthetic harness, qualification-owner, and test-bypass authority.",
            status_code=503,
        )
    if harness and env != HARNESS_RUNTIME_ENVIRONMENT:
        raise HarnessConfigurationError(
            "harness_environment_required",
            "Synthetic harness authority requires the explicit qualification environment.",
            status_code=503,
        )
    if destructive and not (harness and env == HARNESS_RUNTIME_ENVIRONMENT):
        raise HarnessConfigurationError(
            "destructive_harness_requires_qualification",
            "Destructive harness authority requires an enabled qualification runtime.",
            status_code=503,
        )
    if owner and env != HARNESS_RUNTIME_ENVIRONMENT:
        raise HarnessConfigurationError(
            "qualification_owner_requires_qualification",
            "Qualification Owner authority requires the explicit qualification environment.",
            status_code=503,
        )
    return {
        "valid": True,
        "environment": env,
        "enabled": harness and env == HARNESS_RUNTIME_ENVIRONMENT,
        "destructive": destructive and harness and env == HARNESS_RUNTIME_ENVIRONMENT,
        "qualification_owner": owner and env == HARNESS_RUNTIME_ENVIRONMENT,
        "test_bypass": test_bypass and env not in _PRODUCTION_ENVIRONMENTS,
    }


def _require_enabled() -> None:
    validate_startup_configuration()
    if not (harness_enabled() and environment() == HARNESS_RUNTIME_ENVIRONMENT):
        raise HarnessError(
            "harness_disabled",
            "The synthetic qualification harness is not enabled on this runtime.",
            status_code=401,
        )


def is_direct_local_request(request: Any) -> bool:
    host = str(getattr(getattr(request, "client", None), "host", "") or "").strip().casefold()
    if host not in {"127.0.0.1", "::1", "localhost"}:
        return False
    return not any(
        str(request.headers.get(name, "")).strip()
        for name in (
            "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded", "via",
        )
    )


def harness_headers_present(request: Any) -> bool:
    return any(str(name).casefold().startswith("x-pocket-lab-harness-") for name in request.headers.keys())


def provisioning_allowed(request: Any) -> bool:
    if not is_direct_local_request(request):
        return False
    if request.headers.get(HARNESS_PROVISIONING_HEADER, "").strip() != "1":
        return False
    configured = os.environ.get("POCKETLAB_HARNESS_PROVISIONING_TOKEN", "").strip()
    supplied = request.headers.get(HARNESS_PROVISIONING_TOKEN_HEADER, "").strip()
    return bool(configured and supplied and hmac.compare_digest(supplied, configured))


def _safe_principal_id(value: str) -> str:
    result = str(value or "").strip().casefold()
    if not _PRINCIPAL_ID_RE.fullmatch(result):
        raise HarnessError("principal_id_invalid", "The synthetic principal identifier is invalid.", status_code=422)
    return result


def _safe_purpose(value: str) -> str:
    result = str(value or "").strip().casefold()
    if not _PURPOSE_RE.fullmatch(result):
        raise HarnessError("harness_purpose_invalid", "The harness purpose is invalid.", status_code=422)
    return result


def _safe_scope(value: str) -> str:
    result = str(value or "").strip().casefold()
    if result != HARNESS_TARGET_SCOPE or not _TARGET_SCOPE_RE.fullmatch(result):
        raise HarnessError("harness_target_mismatch", "Only the local server-host target scope is supported.", status_code=403)
    return result


def _b64u_decode(value: str, *, expected_lengths: set[int]) -> bytes:
    raw = str(value or "").strip()
    if len(raw) > 512 or not _B64U_RE.fullmatch(raw):
        raise ValueError("invalid base64url")
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, base64.binascii.Error):
        raise ValueError("invalid base64url") from None
    if len(decoded) not in expected_lengths:
        raise ValueError("invalid base64url length")
    return decoded


def _b64u_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _hash_opaque(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _profile(name: str) -> Mapping[str, Any]:
    value = PROFILE_DATA.get(str(name or "").strip().casefold())
    if value is None:
        raise HarnessError("harness_profile_unknown", "The requested harness capability profile is not registered.", status_code=403)
    return value


def profile_manifest() -> dict[str, Any]:
    return {
        "version": "1",
        "target_scope": HARNESS_TARGET_SCOPE,
        "profiles": {
            name: {
                "principal_class": str(profile["principal_class"]),
                "environment_scope": str(profile["environment_scope"]),
                "availability": str(profile["availability"]),
                "capabilities": list(profile["capabilities"]),
                "destructive_capabilities": list(profile["destructive_capabilities"]),
            }
            for name, profile in PROFILE_DATA.items()
        },
        "production_maintenance": "deferred",
    }


def _profile_for_runtime(name: str) -> Mapping[str, Any]:
    profile = _profile(name)
    if str(profile["availability"]) == "deferred":
        raise HarnessError(
            "maintenance_activation_deferred",
            "Production maintenance-principal activation remains deferred until its runtime boundary is qualified.",
            status_code=403,
        )
    if str(profile["environment_scope"]) != environment():
        raise HarnessError("harness_environment_mismatch", "The profile is not valid for this runtime environment.", status_code=403)
    return profile


def _principal_class(profiles: list[str]) -> str:
    classes = {str(_profile(name)["principal_class"]) for name in profiles}
    if len(classes) != 1:
        raise HarnessError(
            "principal_profiles_incompatible",
            "A synthetic principal may register profiles from one principal class only.",
            status_code=422,
        )
    return next(iter(classes))


def _insert_audit(
    tx: Any,
    *,
    event_type: str,
    reason_code: str,
    principal_id: str | None = None,
    principal_class: str | None = None,
    harness_session_id: str | None = None,
    purpose: str | None = None,
    capability: str | None = None,
    target_scope: str | None = None,
    operation_id: str | None = None,
    result: str = "rejected",
    summary: str,
    correlation_id: str | None = None,
) -> None:
    tx.execute(
        """INSERT INTO harness_audit_events(
               occurred_at,event_type,reason_code,principal_id,principal_class,
               harness_session_id,purpose,capability,target_scope,environment,
               operation_id,result,summary,correlation_id
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _iso(), str(event_type)[:80], str(reason_code)[:80],
            str(principal_id or "")[:80] or None, str(principal_class or "")[:40] or None,
            str(harness_session_id or "")[:100] or None, str(purpose or "")[:80] or None,
            str(capability or "")[:120] or None, str(target_scope or "")[:64] or None,
            environment()[:32], str(operation_id or "")[:100] or None, str(result)[:32],
            str(summary)[:240], str(correlation_id or uuid.uuid4().hex)[:80],
        ),
    )
    retention = _bounded_int("POCKETLAB_HARNESS_AUDIT_RETENTION", 1000, 100, 10000)
    tx.execute(
        "DELETE FROM harness_audit_events WHERE event_id NOT IN (SELECT event_id FROM harness_audit_events ORDER BY event_id DESC LIMIT ?)",
        (retention,),
    )


def _cleanup_expired(tx: Any, *, now: str) -> None:
    parsed_now = _parse_iso(now)
    consumed_cutoff = _iso(parsed_now - timedelta(minutes=10)) if parsed_now else now
    tx.execute(
        "UPDATE harness_sessions SET status='expired' WHERE status='active' AND expires_at<=?",
        (now,),
    )
    tx.execute(
        "DELETE FROM harness_challenges WHERE expires_at<=? OR (consumed_at IS NOT NULL AND consumed_at<=?)",
        (consumed_cutoff, consumed_cutoff),
    )


def _safe_principal(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        profiles = json.loads(str(row.get("allowed_profiles_json") or "[]"))
    except (TypeError, ValueError):
        profiles = []
    if not isinstance(profiles, list):
        profiles = []
    return {
        "principal_id": str(row.get("principal_id") or "")[:80],
        "principal_type": str(row.get("principal_type") or "synthetic_machine")[:32],
        "principal_class": str(row.get("principal_class") or "")[:40],
        "display_name": str(row.get("display_name") or "")[:120],
        "enabled": bool(row.get("enabled")),
        "environment_scope": str(row.get("environment_scope") or "")[:32],
        "target_scope": str(row.get("target_scope") or "")[:64],
        "allowed_profiles": [str(item)[:64] for item in profiles[:8]],
        "default_profile": str(row.get("default_profile") or "")[:64],
        "algorithm": str(row.get("algorithm") or "ed25519")[:32],
        "public_key_fingerprint": str(row.get("public_key_fingerprint") or "")[:80],
        "created_at": row.get("created_at"),
        "expires_at": row.get("expires_at"),
        "last_used_at": row.get("last_used_at"),
        "revoked_at": row.get("revoked_at"),
        "revoked": bool(row.get("revoked_at")),
    }


def register_principal(
    *,
    principal_id: str,
    display_name: str,
    public_key: str,
    profiles: list[str],
    algorithm: str = "ed25519",
    expires_in_seconds: int = 24 * 60 * 60,
) -> dict[str, Any]:
    _require_enabled()
    identifier = _safe_principal_id(principal_id)
    display = str(display_name or "").strip()
    if not display or len(display) > 120 or any(ord(char) < 32 for char in display):
        raise HarnessError("principal_display_name_invalid", "The synthetic principal display name is invalid.", status_code=422)
    if str(algorithm or "").strip().casefold() != "ed25519":
        raise HarnessError("principal_algorithm_unsupported", "Only Ed25519 public-key verification is supported.", status_code=422)
    try:
        public_bytes = _b64u_decode(public_key, expected_lengths={32})
        Ed25519PublicKey.from_public_bytes(public_bytes)
    except ValueError:
        raise HarnessError("principal_public_key_invalid", "The synthetic principal public key is invalid.", status_code=422) from None
    names: list[str] = []
    for item in profiles:
        name = str(item or "").strip().casefold()
        if name not in names:
            names.append(name)
    if not 1 <= len(names) <= 7:
        raise HarnessError("principal_profiles_invalid", "Register at least one and no more than seven capability profiles.", status_code=422)
    for name in names:
        _profile_for_runtime(name)
        if name == "qualification-owner" and not qualification_owner_enabled():
            raise HarnessError(
                "qualification_owner_profile_disabled",
                "The exceptional Qualification Owner profile is not enabled.",
                status_code=403,
            )
    principal_class = _principal_class(names)
    ttl = max(60, min(int(expires_in_seconds), 7 * 24 * 60 * 60))
    now = _now()
    expires = now + timedelta(seconds=ttl)
    fingerprint = "sha256:" + hashlib.sha256(public_bytes).hexdigest()
    allowed_json = _canonical(names)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            if tx.execute("SELECT 1 FROM synthetic_principals WHERE principal_id=?", (identifier,)).fetchone():
                raise HarnessError("principal_exists", "The synthetic principal identifier is already registered.", status_code=409)
            tx.execute(
                """INSERT INTO synthetic_principals(
                       principal_id,principal_type,principal_class,display_name,enabled,
                       environment_scope,target_scope,allowed_profiles_json,default_profile,
                       algorithm,public_key,public_key_fingerprint,created_at,expires_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    identifier, "synthetic_machine", principal_class, display, 1,
                    environment(), HARNESS_TARGET_SCOPE, allowed_json, names[0], "ed25519",
                    _b64u_encode(public_bytes), fingerprint, _iso(now), _iso(expires),
                ),
            )
            _insert_audit(
                tx, event_type="principal_registered", reason_code="principal_registered",
                principal_id=identifier, principal_class=principal_class,
                target_scope=HARNESS_TARGET_SCOPE, result="accepted",
                summary="Synthetic machine principal registered.",
            )
            row = tx.execute("SELECT * FROM synthetic_principals WHERE principal_id=?", (identifier,)).fetchone()
    return _safe_principal(dict(row))


def revoke_principal(principal_id: str, *, reason_code: str = "principal_revoked") -> dict[str, Any]:
    _require_enabled()
    identifier = _safe_principal_id(principal_id)
    apply_migrations()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute("SELECT * FROM synthetic_principals WHERE principal_id=?", (identifier,)).fetchone()
            if not row:
                raise HarnessError("principal_not_found", "The synthetic principal was not found.", status_code=404)
            now = _iso()
            tx.execute(
                "UPDATE synthetic_principals SET enabled=0,revoked_at=?,revoke_reason=? WHERE principal_id=?",
                (now, str(reason_code)[:80], identifier),
            )
            tx.execute(
                "UPDATE harness_sessions SET status='revoked',revoked_at=?,revoke_reason=? WHERE principal_id=? AND status='active'",
                (now, str(reason_code)[:80], identifier),
            )
            _insert_audit(
                tx, event_type="principal_revoked", reason_code=str(reason_code),
                principal_id=identifier, principal_class=str(row["principal_class"]),
                target_scope=str(row["target_scope"]), result="accepted",
                summary="Synthetic machine principal revoked.",
            )
            result = dict(row)
            result.update({"enabled": 0, "revoked_at": now, "revoke_reason": str(reason_code)[:80]})
    return _safe_principal(result)


def issue_challenge(*, principal_id: str, purpose: str, profile: str, target_scope: str = HARNESS_TARGET_SCOPE, ttl_seconds: int | None = None) -> dict[str, Any]:
    _require_enabled()
    identifier = _safe_principal_id(principal_id)
    safe_purpose = _safe_purpose(purpose)
    safe_scope = _safe_scope(target_scope)
    profile_name = str(profile or "").strip().casefold()
    _profile_for_runtime(profile_name)
    if profile_name == "qualification-owner" and not qualification_owner_enabled():
        raise HarnessError("qualification_owner_profile_disabled", "The exceptional Qualification Owner profile is not enabled.", status_code=403)
    ttl = _bounded_int("POCKETLAB_HARNESS_CHALLENGE_TTL_SECONDS", 120, 30, 300) if ttl_seconds is None else max(30, min(int(ttl_seconds), 300))
    now = _now()
    expires = now + timedelta(seconds=ttl)
    challenge_id = "hch-" + uuid.uuid4().hex
    nonce = _b64u_encode(secrets.token_bytes(32))
    payload = {
        "v": 1,
        "principal_id": identifier,
        "challenge_id": challenge_id,
        "nonce": nonce,
        "issued_at": _iso(now),
        "expires_at": _iso(expires),
        "purpose": safe_purpose,
        "profile": profile_name,
        "target_scope": safe_scope,
        "runtime_id": _runtime_id(),
    }
    signing_payload = _canonical(payload)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _cleanup_expired(tx, now=_iso(now))
            row = tx.execute("SELECT * FROM synthetic_principals WHERE principal_id=?", (identifier,)).fetchone()
            if not row:
                raise HarnessError("principal_not_found", "The synthetic principal was not found.", status_code=404)
            expires_at = _parse_iso(row["expires_at"])
            if not row["enabled"] or row["revoked_at"]:
                raise HarnessError("principal_revoked", "The synthetic principal is disabled or revoked.", status_code=403)
            if expires_at is None or expires_at <= now:
                raise HarnessError("principal_expired", "The synthetic principal has expired.", status_code=403)
            if str(row["environment_scope"]) != environment() or str(row["target_scope"]) != safe_scope:
                raise HarnessError("harness_environment_mismatch", "The synthetic principal is scoped to a different runtime.", status_code=403)
            try:
                allowed = json.loads(str(row["allowed_profiles_json"] or "[]"))
            except (TypeError, ValueError):
                allowed = []
            if profile_name not in allowed:
                raise HarnessError("harness_profile_not_allowed", "The requested profile is not allowed for this principal.", status_code=403)
            active = tx.execute(
                "SELECT COUNT(*) AS count FROM harness_challenges WHERE principal_id=? AND consumed_at IS NULL AND expires_at>?",
                (identifier, _iso(now)),
            ).fetchone()
            if int(active["count"] or 0) >= 8:
                raise HarnessError("harness_challenge_limit", "Too many active harness challenges exist for this principal.", status_code=429)
            tx.execute(
                """INSERT INTO harness_challenges(
                       challenge_id,principal_id,nonce_hash,signing_payload_hash,
                       issued_at,expires_at,purpose,requested_profile,target_scope,
                       runtime_id,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    challenge_id, identifier, _hash_opaque(nonce), _hash_opaque(signing_payload),
                    _iso(now), _iso(expires), safe_purpose, profile_name, safe_scope,
                    payload["runtime_id"], _iso(now),
                ),
            )
            _insert_audit(
                tx, event_type="challenge_issued", reason_code="challenge_issued",
                principal_id=identifier, principal_class=str(row["principal_class"]),
                purpose=safe_purpose, capability=profile_name, target_scope=safe_scope,
                result="accepted", summary="Bounded synthetic-principal challenge issued.",
                correlation_id=challenge_id,
            )
    return {
        "challenge_id": challenge_id,
        "principal_id": identifier,
        "profile": profile_name,
        "purpose": safe_purpose,
        "target_scope": safe_scope,
        "runtime_id": payload["runtime_id"],
        "issued_at": payload["issued_at"],
        "expires_at": payload["expires_at"],
        "algorithm": "ed25519",
        "nonce": nonce,
        "signing_payload": signing_payload,
    }


def _session_context(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        capabilities = json.loads(str(row.get("capabilities_json") or "[]"))
    except (TypeError, ValueError):
        capabilities = []
    if not isinstance(capabilities, list):
        capabilities = []
    profile_name = str(row.get("capability_profile") or "")[:64]
    actor_type = "qualification" if profile_name == "qualification-owner" else (
        "maintenance" if str(row.get("principal_class") or "") == "maintenance" else "synthetic_machine"
    )
    owner = profile_name == "qualification-owner"
    assurance = []
    if owner:
        assurance = [{
            "purpose": "policy.rules.activate",
            "credential_id": "harness-session-step-up",
            "satisfied_at": str(row.get("started_at") or "")[:40],
            "expires_at": str(row.get("expires_at") or "")[:40],
        }]
    harness = {
        "enabled": True,
        "session_id": str(row.get("harness_session_id") or "")[:100],
        "principal_id": str(row.get("principal_id") or "")[:80],
        "principal_class": str(row.get("principal_class") or "")[:40],
        "profile": profile_name,
        "purpose": str(row.get("purpose") or "")[:80],
        "capabilities": [str(item)[:120] for item in capabilities[:64]],
        "target_scope": str(row.get("target_scope") or "")[:64],
        "runtime_id": str(row.get("runtime_id") or "")[:64],
        "destructive_allowed": bool(row.get("destructive_allowed")),
        "qualification_environment": environment() == HARNESS_RUNTIME_ENVIRONMENT,
    }
    return {
        "actor": {
            "identity_id": str(row.get("principal_id") or "")[:80],
            "type": actor_type,
            "display_name": str(row.get("display_name") or "Synthetic machine")[:120],
        },
        "session": {
            "authenticated": True,
            "auth_method": HARNESS_AUTH_METHOD,
            "harness_session_id": harness["session_id"],
            "assurance": assurance,
        },
        "auth_method": HARNESS_AUTH_METHOD,
        "authorization": {
            "role": "Owner" if owner else None,
            "owner_authority": owner,
            "membership_active": False,
            "identity_class": "synthetic_machine",
            "enterprise_enabled": False,
            "authorization_version": 1,
            "principal_class": harness["principal_class"],
        },
        "harness": harness,
    }


def _safe_session(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        capabilities = json.loads(str(row.get("capabilities_json") or "[]"))
    except (TypeError, ValueError):
        capabilities = []
    if not isinstance(capabilities, list):
        capabilities = []
    return {
        "harness_session_id": str(row.get("harness_session_id") or "")[:100],
        "principal_id": str(row.get("principal_id") or "")[:80],
        "principal_class": str(row.get("principal_class") or "")[:40],
        "purpose": str(row.get("purpose") or "")[:80],
        "capability_profile": str(row.get("capability_profile") or "")[:64],
        "capabilities": [str(item)[:120] for item in capabilities[:64]],
        "target_scope": str(row.get("target_scope") or "")[:64],
        "started_at": row.get("started_at"),
        "expires_at": row.get("expires_at"),
        "last_used_at": row.get("last_used_at"),
        "destructive_allowed": bool(row.get("destructive_allowed")),
        "status": str(row.get("status") or "")[:20],
        "revoked_at": row.get("revoked_at"),
        "revoke_reason": str(row.get("revoke_reason") or "")[:80],
        "correlation_id": str(row.get("harness_session_id") or "")[:100],
    }


def create_session(
    *,
    challenge_id: str,
    signing_payload: str,
    signature: str,
    principal_id: str | None = None,
    profile: str | None = None,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    _require_enabled()
    safe_challenge_id = str(challenge_id or "").strip()
    if not re.fullmatch(r"^hch-[0-9a-f]{32}$", safe_challenge_id):
        raise HarnessError("challenge_invalid", "The harness challenge is invalid.", status_code=401)
    raw_payload = str(signing_payload or "")
    if len(raw_payload) > 4096:
        raise HarnessError("challenge_invalid", "The harness challenge is invalid.", status_code=401)
    try:
        parsed = json.loads(raw_payload)
        if not isinstance(parsed, dict) or _canonical(parsed) != raw_payload:
            raise ValueError
        signature_bytes = _b64u_decode(signature, expected_lengths={64})
    except (TypeError, ValueError, json.JSONDecodeError):
        raise HarnessError("signature_invalid", "The synthetic-principal signature could not be verified.", status_code=401) from None
    expected_keys = {
        "v", "principal_id", "challenge_id", "nonce", "issued_at", "expires_at",
        "purpose", "profile", "target_scope", "runtime_id",
    }
    if set(parsed) != expected_keys or parsed.get("challenge_id") != safe_challenge_id:
        raise HarnessError("challenge_context_mismatch", "The signed challenge context does not match the issued challenge.", status_code=401)
    if principal_id is not None and str(principal_id).strip().casefold() != str(parsed.get("principal_id") or ""):
        raise HarnessError("challenge_principal_mismatch", "The signed challenge belongs to a different principal.", status_code=401)
    if profile is not None and str(profile).strip().casefold() != str(parsed.get("profile") or ""):
        raise HarnessError("challenge_profile_mismatch", "The signed challenge belongs to a different capability profile.", status_code=401)
    identifier = _safe_principal_id(str(parsed.get("principal_id") or ""))
    profile_name = str(parsed.get("profile") or "").strip().casefold()
    safe_purpose = _safe_purpose(str(parsed.get("purpose") or ""))
    safe_scope = _safe_scope(str(parsed.get("target_scope") or ""))
    now = _now()
    try:
        issued = _parse_iso(str(parsed.get("issued_at") or ""))
        expires = _parse_iso(str(parsed.get("expires_at") or ""))
        if issued is None or expires is None or issued > now or expires <= now or expires - issued > timedelta(minutes=5):
            raise ValueError
    except ValueError:
        raise HarnessError("challenge_expired", "The harness challenge is expired or invalid.", status_code=401) from None
    if str(parsed.get("runtime_id") or "") != _runtime_id():
        raise HarnessError("harness_runtime_mismatch", "The harness challenge belongs to a different runtime.", status_code=401)
    _profile_for_runtime(profile_name)
    if profile_name == "qualification-owner" and not qualification_owner_enabled():
        raise HarnessError("qualification_owner_profile_disabled", "The exceptional Qualification Owner profile is not enabled.", status_code=403)
    nonce = str(parsed.get("nonce") or "")
    try:
        _b64u_decode(nonce, expected_lengths={32})
    except ValueError:
        raise HarnessError("challenge_invalid", "The harness challenge is invalid.", status_code=401) from None
    token = secrets.token_urlsafe(32)
    token_hash = _hash_opaque(token)
    session_id = "hs-" + uuid.uuid4().hex
    session_ttl = _bounded_int("POCKETLAB_HARNESS_SESSION_TTL_SECONDS", 20 * 60, 60, 60 * 60) if ttl_seconds is None else max(60, min(int(ttl_seconds), 60 * 60))
    session_expires = min(now + timedelta(seconds=session_ttl), expires + timedelta(seconds=session_ttl))
    profile_data = PROFILE_DATA[profile_name]
    capabilities = list(profile_data["capabilities"])
    destructive_allowed = bool(
        destructive_enabled()
        and profile_data["destructive_capabilities"]
        and environment() == HARNESS_RUNTIME_ENVIRONMENT
    )
    authentication_failure: HarnessError | None = None
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _cleanup_expired(tx, now=_iso(now))
            challenge = tx.execute("SELECT * FROM harness_challenges WHERE challenge_id=?", (safe_challenge_id,)).fetchone()
            principal = tx.execute("SELECT * FROM synthetic_principals WHERE principal_id=?", (identifier,)).fetchone()
            if not challenge or not principal:
                raise HarnessError("challenge_not_found", "The harness challenge is no longer available.", status_code=401)
            if challenge["consumed_at"] is not None:
                raise HarnessError("challenge_replayed", "The harness challenge has already been consumed.", status_code=401)
            if str(challenge["principal_id"]) != identifier or str(challenge["requested_profile"]) != profile_name or str(challenge["purpose"]) != safe_purpose or str(challenge["target_scope"]) != safe_scope:
                raise HarnessError("challenge_context_mismatch", "The signed challenge context does not match the issued challenge.", status_code=401)
            if str(challenge["runtime_id"]) != str(parsed.get("runtime_id")) or str(challenge["signing_payload_hash"]) != _hash_opaque(raw_payload) or str(challenge["nonce_hash"]) != _hash_opaque(nonce):
                raise HarnessError("challenge_context_mismatch", "The signed challenge context does not match the issued challenge.", status_code=401)
            challenge_expires = _parse_iso(str(challenge["expires_at"]))
            if challenge_expires is None or challenge_expires <= now:
                raise HarnessError("challenge_expired", "The harness challenge is expired or invalid.", status_code=401)
            principal_expiry = _parse_iso(str(principal["expires_at"]))
            if not principal["enabled"] or principal["revoked_at"]:
                raise HarnessError("principal_revoked", "The synthetic principal is disabled or revoked.", status_code=403)
            if principal_expiry is None or principal_expiry <= now:
                raise HarnessError("principal_expired", "The synthetic principal has expired.", status_code=403)
            try:
                Ed25519PublicKey.from_public_bytes(_b64u_decode(str(principal["public_key"]), expected_lengths={32})).verify(signature_bytes, raw_payload.encode("utf-8"))
            except (InvalidSignature, ValueError, TypeError):
                attempts = int(challenge["failed_attempts"] or 0) + 1
                tx.execute(
                    "UPDATE harness_challenges SET failed_attempts=?,consumed_at=CASE WHEN ? >= 5 THEN ? ELSE consumed_at END WHERE challenge_id=?",
                    (attempts, attempts, _iso(now), safe_challenge_id),
                )
                _insert_audit(
                    tx, event_type="authentication_rejected", reason_code="signature_invalid",
                    principal_id=identifier, principal_class=str(principal["principal_class"]),
                    purpose=safe_purpose, capability=profile_name, target_scope=safe_scope,
                    result="rejected", summary="Synthetic-principal signature rejected.",
                    correlation_id=safe_challenge_id,
                )
                authentication_failure = HarnessError(
                    "signature_invalid",
                    "The synthetic-principal signature could not be verified.",
                    status_code=401,
                )
            if authentication_failure is None:
                active_principal = tx.execute(
                    "SELECT COUNT(*) AS count FROM harness_sessions WHERE principal_id=? AND status='active'",
                    (identifier,),
                ).fetchone()
                if int(active_principal["count"] or 0) >= 3:
                    raise HarnessError("harness_session_limit", "This principal has reached its active harness-session limit.", status_code=429)
                active_global = tx.execute("SELECT COUNT(*) AS count FROM harness_sessions WHERE status='active'").fetchone()
                if int(active_global["count"] or 0) >= 8:
                    raise HarnessError("harness_global_session_limit", "The qualification runtime has reached its active session limit.", status_code=429)
                if destructive_allowed and tx.execute("SELECT 1 FROM harness_sessions WHERE status='active' AND destructive_allowed=1 LIMIT 1").fetchone():
                    raise HarnessError("harness_destructive_session_limit", "Only one destructive qualification session may be active at a time.", status_code=429)
                tx.execute("UPDATE harness_challenges SET consumed_at=? WHERE challenge_id=?", (_iso(now), safe_challenge_id))
                tx.execute(
                    """INSERT INTO harness_sessions(
                           harness_session_id,principal_id,principal_class,purpose,
                           capability_profile,capabilities_json,target_scope,runtime_id,
                           token_hash,started_at,expires_at,last_used_at,destructive_allowed,status
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        session_id, identifier, str(principal["principal_class"]), safe_purpose,
                        profile_name, _canonical(capabilities), safe_scope, str(parsed["runtime_id"]),
                        token_hash, _iso(now), _iso(session_expires), _iso(now),
                        1 if destructive_allowed else 0, "active",
                    ),
                )
                tx.execute("UPDATE synthetic_principals SET last_used_at=? WHERE principal_id=?", (_iso(now), identifier))
                _insert_audit(
                    tx, event_type="authentication_succeeded", reason_code="signature_verified",
                    principal_id=identifier, principal_class=str(principal["principal_class"]),
                    harness_session_id=session_id, purpose=safe_purpose, capability=profile_name,
                    target_scope=safe_scope, result="accepted", summary="Synthetic-principal challenge verified.",
                    correlation_id=session_id,
                )
                _insert_audit(
                    tx, event_type="session_created", reason_code="session_created",
                    principal_id=identifier, principal_class=str(principal["principal_class"]),
                    harness_session_id=session_id, purpose=safe_purpose, capability=profile_name,
                    target_scope=safe_scope, result="accepted", summary="Short-lived harness session created.",
                    correlation_id=session_id,
                )
                row = tx.execute(
                    """SELECT s.*,p.display_name FROM harness_sessions s
                       JOIN synthetic_principals p ON p.principal_id=s.principal_id
                       WHERE s.harness_session_id=?""",
                    (session_id,),
                ).fetchone()
    if authentication_failure is not None:
        raise authentication_failure
    return {"session": _safe_session(dict(row)), "session_token": token}


def _load_session(token: str, *, expected_session_id: str | None = None, mutate_expiry: bool = True) -> Mapping[str, Any]:
    _require_enabled()
    raw = str(token or "").strip()
    if not raw or len(raw) > 512:
        raise HarnessError("harness_session_invalid", "The harness session proof is invalid or expired.", status_code=401)
    token_hash = _hash_opaque(raw)
    apply_migrations()
    expiry_failure: HarnessError | None = None
    result: dict[str, Any] | None = None
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute(
                """SELECT s.*,p.display_name,p.enabled AS principal_enabled,p.revoked_at AS principal_revoked_at,p.expires_at AS principal_expires_at
                   FROM harness_sessions s JOIN synthetic_principals p ON p.principal_id=s.principal_id
                   WHERE s.token_hash=? LIMIT 1""",
                (token_hash,),
            ).fetchone()
            if not row or (expected_session_id and str(row["harness_session_id"]) != str(expected_session_id)):
                raise HarnessError("harness_session_invalid", "The harness session proof is invalid or expired.", status_code=401)
            now = _now()
            if str(row["status"]) != "active":
                raise HarnessError("harness_session_revoked", "The harness session is no longer active.", status_code=401)
            session_expiry = _parse_iso(str(row["expires_at"]))
            if session_expiry is None or session_expiry <= now:
                if mutate_expiry:
                    tx.execute("UPDATE harness_sessions SET status='expired',revoke_reason='session_expired' WHERE harness_session_id=?", (row["harness_session_id"],))
                    _insert_audit(
                        tx, event_type="session_expired", reason_code="session_expired",
                        principal_id=str(row["principal_id"]), principal_class=str(row["principal_class"]),
                        harness_session_id=str(row["harness_session_id"]), purpose=str(row["purpose"]),
                        capability=str(row["capability_profile"]), target_scope=str(row["target_scope"]),
                        result="rejected", summary="Expired harness session rejected.",
                        correlation_id=str(row["harness_session_id"]),
                    )
                expiry_failure = HarnessError("harness_session_expired", "The harness session is expired.", status_code=401)
            else:
                principal_expiry = _parse_iso(str(row["principal_expires_at"]))
                if not row["principal_enabled"] or row["principal_revoked_at"]:
                    raise HarnessError("principal_revoked", "The synthetic principal is disabled or revoked.", status_code=401)
                if principal_expiry is None or principal_expiry <= now:
                    raise HarnessError("principal_expired", "The synthetic principal has expired.", status_code=401)
                if mutate_expiry:
                    tx.execute("UPDATE harness_sessions SET last_used_at=? WHERE harness_session_id=?", (_iso(now), row["harness_session_id"]))
                result = dict(row)
    if expiry_failure is not None:
        raise expiry_failure
    if result is None:
        raise HarnessError("harness_session_invalid", "The harness session proof is invalid or expired.", status_code=401)
    return result


def authenticate_request(request: Any) -> dict[str, Any]:
    if not is_direct_local_request(request):
        raise HarnessError("harness_transport_rejected", "Synthetic harness proof is accepted only over direct loopback transport.", status_code=401)
    if not harness_enabled() or environment() != HARNESS_RUNTIME_ENVIRONMENT:
        raise HarnessError("harness_disabled", "The synthetic qualification harness is not enabled on this runtime.", status_code=401)
    if request.headers.get("x-role", "").strip():
        raise HarnessError("harness_role_field_rejected", "Synthetic harness requests cannot select a human role.", status_code=403)
    allowed = {HARNESS_SESSION_HEADER}
    supplied_harness = {str(name).casefold() for name in request.headers.keys() if str(name).casefold().startswith("x-pocket-lab-harness-")}
    if supplied_harness - allowed:
        raise HarnessError("harness_proof_fields_rejected", "Synthetic harness authority is derived only from its verified session proof.", status_code=403)
    row = _load_session(request.headers.get(HARNESS_SESSION_HEADER, ""))
    return _session_context(row)


def session_status(*, token: str, session_id: str) -> dict[str, Any]:
    return _safe_session(_load_session(token, expected_session_id=session_id))


def revoke_session(*, token: str, session_id: str, reason_code: str = "session_revoked") -> dict[str, Any]:
    _load_session(token, expected_session_id=session_id)
    apply_migrations()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            current = tx.execute("SELECT * FROM harness_sessions WHERE harness_session_id=?", (session_id,)).fetchone()
            if not current:
                raise HarnessError("harness_session_not_found", "The harness session was not found.", status_code=404)
            if str(current["status"]) == "active":
                now = _iso()
                tx.execute(
                    "UPDATE harness_sessions SET status='revoked',revoked_at=?,revoke_reason=? WHERE harness_session_id=?",
                    (now, str(reason_code)[:80], session_id),
                )
                _insert_audit(
                    tx, event_type="session_revoked", reason_code=str(reason_code),
                    principal_id=str(current["principal_id"]), principal_class=str(current["principal_class"]),
                    harness_session_id=session_id, purpose=str(current["purpose"]),
                    capability=str(current["capability_profile"]), target_scope=str(current["target_scope"]),
                    result="accepted", summary="Harness session revoked.", correlation_id=session_id,
                )
            result = dict(current)
            result["status"] = "revoked"
            result["revoke_reason"] = str(reason_code)[:80]
    return _safe_session(result)


def enforce_capability(
    auth_context: Mapping[str, Any],
    *,
    action_id: str,
    target_type: str,
    target_id: str,
    destructive: bool | None = None,
    operation_id: str | None = None,
) -> None:
    harness = auth_context.get("harness") if isinstance(auth_context, Mapping) else None
    if not isinstance(harness, Mapping):
        return
    capability = _ACTION_CAPABILITY.get(str(action_id or "").strip())
    principal_id = str(harness.get("principal_id") or "")[:80]
    session_id = str(harness.get("session_id") or "")[:100]
    target_scope = str(harness.get("target_scope") or "")[:64]
    denied: tuple[str, str] | None = None
    if not bool(harness.get("qualification_environment")) or not bool(harness.get("enabled")):
        denied = ("harness_disabled", "The synthetic harness is not active for this operation.")
    elif target_scope != HARNESS_TARGET_SCOPE:
        denied = ("harness_target_mismatch", "The synthetic session is not scoped to the local server host.")
    elif capability is None:
        denied = ("harness_action_unregistered", "The requested action has no registered harness capability.")
    elif capability not in set(harness.get("capabilities") or []):
        denied = ("harness_capability_denied", "The synthetic principal is not authorized for this capability.")
    elif str(target_type or "") == "device" and str(target_id or "") not in {"server", "server-host", "local-server", "pocketlab-server"}:
        denied = ("harness_target_mismatch", "This harness scope does not include secondary device targets.")
    is_destructive = bool(destructive) if destructive is not None else str(action_id or "") in _DESTRUCTIVE_ACTIONS
    if denied is None and is_destructive and not bool(harness.get("destructive_allowed")):
        denied = ("destructive_harness_disabled", "Destructive harness admission requires the independent destructive gate.")
    if denied:
        reason, message = denied
        with connection() as conn:
            with begin_immediate(conn) as tx:
                _insert_audit(
                    tx, event_type="capability_denied", reason_code=reason,
                    principal_id=principal_id, principal_class=str(harness.get("principal_class") or ""),
                    harness_session_id=session_id, purpose=str(harness.get("purpose") or ""),
                    capability=capability or str(action_id or "")[:120], target_scope=target_scope,
                    operation_id=operation_id, result="rejected", summary=message,
                    correlation_id=session_id or None,
                )
        raise HarnessError(reason, message, status_code=403)
    if is_destructive:
        with connection() as conn:
            with begin_immediate(conn) as tx:
                _insert_audit(
                    tx, event_type="destructive_operation_admitted", reason_code="destructive_admitted",
                    principal_id=principal_id, principal_class=str(harness.get("principal_class") or ""),
                    harness_session_id=session_id, purpose=str(harness.get("purpose") or ""),
                    capability=capability, target_scope=target_scope, operation_id=operation_id,
                    result="accepted", summary="Destructive operation passed the harness gate; normal operation safeguards still apply.",
                    correlation_id=session_id or None,
                )


def status_projection() -> dict[str, Any]:
    configured = validate_startup_configuration()
    result: dict[str, Any] = {
        "status": "enabled" if configured["enabled"] else "disabled",
        "enabled": bool(configured["enabled"]),
        "environment": configured["environment"],
        "target_scope": HARNESS_TARGET_SCOPE,
        "destructive_gate": bool(configured["destructive"]),
        "qualification_owner": bool(configured["qualification_owner"]),
        "test_auth_bypass": bool(configured["test_bypass"]),
        "production_maintenance": "deferred",
        "active_sessions": 0,
        "principal_count": 0,
        "sanitized": True,
        "complete": True,
        "truncated": False,
    }
    if not configured["enabled"]:
        return result
    apply_migrations()
    with connection() as conn:
        result["active_sessions"] = int(conn.execute("SELECT COUNT(*) AS count FROM harness_sessions WHERE status='active' AND expires_at>?", (_iso(),)).fetchone()["count"] or 0)
        result["principal_count"] = int(conn.execute("SELECT COUNT(*) AS count FROM synthetic_principals WHERE enabled=1 AND revoked_at IS NULL AND expires_at>?", (_iso(),)).fetchone()["count"] or 0)
    return result


def verify_harness_disabled() -> dict[str, Any]:
    state = status_projection()
    if state["enabled"] or state["destructive_gate"] or state["qualification_owner"] or state["test_auth_bypass"]:
        raise HarnessConfigurationError(
            "harness_not_disabled",
            "The runtime does not satisfy the default-off harness state.",
            status_code=503,
        )
    return state
