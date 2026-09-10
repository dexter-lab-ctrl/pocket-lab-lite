# ruff: noqa: E402
from __future__ import annotations

import os
import hmac
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

# FastAPI and the NATS worker share framework-neutral core services from runtime/core.
# Keep those modules importable without requiring installation as a Python package on Android/Termux.
RUNTIME_DIR = pathlib.Path(__file__).resolve().parents[1]
CORE_DIR = RUNTIME_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import control_plane_core as core  # noqa: E402
from operations.registry import (
    normalize_operation_request as normalize_operation_request,
)  # noqa: E402,F401


def settings() -> Any:
    return core.SETTINGS


def operation_service() -> Any:
    return core.OP_SERVICE


def ensure_release_updater() -> Any:
    if core.AUTO_UPDATER is None:
        core.AUTO_UPDATER = core.ReleaseAutoUpdater(
            state_dir=core.SETTINGS.state_dir,
            operation_service=core.OP_SERVICE,
            refresh_catalog=core.build_catalog_view,
            current_tag=os.environ.get("POCKETLAB_LITE_RELEASE_TAG", ""),
            github_repo=os.environ.get(
                "POCKETLAB_LITE_RELEASE_REPO", "dexter-lab-ctrl/pocket-lab-lite"
            ),
            poll_interval=core._env_int(
                "POCKETLAB_RELEASE_STABLE_INTERVAL_SECONDS", 12 * 3600
            ),
            auto_apply=core._env_bool("POCKETLAB_AUTO_RELEASE_APPLY", False),
        )
    return core.AUTO_UPDATER


def now_utc_iso() -> str:
    return core.now_utc_iso()


def loopback_client(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost"}


QUALIFICATION_OWNER_ID = "qualification-owner"
QUALIFICATION_OWNER_AUTH_METHOD = "qualification_owner"


def _qualification_owner_enabled() -> bool:
    """Return true only for the explicitly isolated qualification runtime.

    The qualification principal is intentionally not a normal authentication
    method.  It requires both the existing test gate and a separate owner gate,
    and it is only valid when the runtime identifies itself as a qualification
    consumer.  Production/bootstrap defaults leave all three gates disabled.
    """
    return (
        os.environ.get("POCKETLAB_TEST_AUTH_BYPASS") == "1"
        and os.environ.get("POCKETLAB_QUALIFICATION_OWNER") == "1"
        and os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"
    )


def _qualification_request_requested(request: Request) -> bool:
    # On a qualification consumer, the test marker is itself a request to use
    # the synthetic path.  Outside that environment only an explicit marker is
    # treated as such, so ordinary authentication remains unchanged.
    return bool(
        request.headers.get("x-pocket-lab-qualification")
        or (
            os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"
            and request.headers.get("x-pocket-lab-test")
        )
    )


def _qualification_request_is_direct_local(request: Request) -> bool:
    # Caddy is a local peer from FastAPI's perspective, so require the absence
    # of its forwarded-request proof as well as the actual direct peer.  The
    # Caddy contract strips the qualification markers before proxying.
    return loopback_client(request) and not any(
        request.headers.get(name, "").strip()
        for name in ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto")
    )


def qualification_owner_context() -> Dict[str, Any]:
    """Build the ephemeral synthetic Owner context used by qualification only."""
    now = datetime.now(timezone.utc)
    assurance = {
        "purpose": "policy.rules.activate",
        "credential_id": "qualification-owner-step-up",
        "satisfied_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }
    return {
        "actor": {
            "identity_id": QUALIFICATION_OWNER_ID,
            "type": "qualification",
            "display_name": "Qualification Owner",
        },
        "session": {
            "authenticated": True,
            "auth_method": QUALIFICATION_OWNER_AUTH_METHOD,
            # This is an ephemeral qualification proof, not a real credential.
            # It exists only behind the three explicit qualification gates so
            # the normal governed Rules source-sync path can be exercised.
            "assurance": [assurance],
        },
        "auth_method": QUALIFICATION_OWNER_AUTH_METHOD,
        "authorization": {
            "role": "Owner",
            "owner_authority": True,
            "membership_active": True,
            "identity_class": "qualification_principal",
            "enterprise_enabled": False,
            "authorization_version": 1,
        },
    }


def is_qualification_owner_context(auth_context: Dict[str, Any] | None) -> bool:
    """Recognize only the exact ephemeral qualification principal contract."""
    context = auth_context or {}
    actor = context.get("actor") or {}
    session = context.get("session") or {}
    authorization = context.get("authorization") or {}
    return bool(
        _qualification_owner_enabled()
        and actor.get("identity_id") == QUALIFICATION_OWNER_ID
        and actor.get("type") == "qualification"
        and actor.get("display_name") == "Qualification Owner"
        and session.get("authenticated") is True
        and session.get("auth_method") == QUALIFICATION_OWNER_AUTH_METHOD
        and context.get("auth_method") == QUALIFICATION_OWNER_AUTH_METHOD
        and authorization.get("role") == "Owner"
        and authorization.get("owner_authority") is True
        and authorization.get("membership_active") is True
        and authorization.get("identity_class") == "qualification_principal"
        and authorization.get("enterprise_enabled") is False
    )


def _reject_qualification_request(*, status_code: int = status.HTTP_401_UNAUTHORIZED) -> None:
    raise HTTPException(
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": "qualification_authentication_required",
            "message": "The isolated qualification authentication proof is not enabled for this request.",
            "sanitized": True,
        },
    )


def bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    scheme, credentials = get_authorization_scheme_param(auth)
    if scheme.lower() == "bearer" and credentials:
        return credentials.strip()
    return request.headers.get("x-pocket-lab-token", "").strip()


def resolve_auth_context(request: Request, *, write: bool = False) -> Dict[str, Any]:
    if _qualification_request_requested(request):
        if not (
            _qualification_owner_enabled()
            and request.headers.get("x-pocket-lab-test") == "1"
            and request.headers.get("x-pocket-lab-qualification") == "1"
            and _qualification_request_is_direct_local(request)
            and not request.headers.get("x-role", "").strip()
        ):
            _reject_qualification_request()
        return qualification_owner_context()

    # Never let a test marker silently fall back to the ordinary test actor on
    # a qualification consumer.  This proves the qualification proof is
    # required while retaining ordinary real-session/service authentication.
    if (
        os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"
        and request.headers.get("x-pocket-lab-test") == "1"
    ):
        _reject_qualification_request()

    if (
        os.environ.get("POCKETLAB_TEST_AUTH_BYPASS") == "1"
        and request.headers.get("x-pocket-lab-test") == "1"
    ):
        return {
            "actor": {"identity_id": "test-harness", "type": "test", "display_name": "Test Harness"},
            "session": {"authenticated": True, "auth_method": "test_bypass"},
            "auth_method": "test_bypass",
        }

    from .services import lite_identity_auth

    session_token = request.cookies.get(lite_identity_auth.cookie_name(), "")
    session_context = lite_identity_auth.authenticate_session_token(session_token) if session_token else None
    if session_context:
        if write:
            csrf = request.headers.get("x-pocket-lab-csrf", "").strip()
            if not lite_identity_auth.csrf_matches(session_context, csrf):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"reason_code": "csrf_required", "message": "Refresh the page and try again."},
                )
        context = {
            **session_context,
            "auth_method": str((session_context.get("session") or {}).get("auth_method") or "session"),
        }
        # Enterprise role and membership are resolved from SQLite for every
        # request.  No request field, cookie value, or browser state is an
        # authorization input.
        from .services import lite_enterprise_identity

        return lite_enterprise_identity.enrich_auth_context(context)

    cfg = settings()
    configured_token = cfg.api_token.strip()
    supplied = bearer_token(request)
    if configured_token and supplied and hmac.compare_digest(supplied, configured_token):
        return {
            "actor": {"identity_id": "api-token", "type": "service", "display_name": "Pocket Lab API client"},
            "session": {"authenticated": True, "auth_method": "api_token"},
            "auth_method": "api_token",
        }

    if not write:
        return {
            "actor": {"identity_id": "anonymous", "type": "anonymous", "display_name": "Signed out"},
            "session": {"authenticated": False, "auth_method": ""},
            "auth_method": "anonymous",
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"reason_code": "authentication_required", "message": "Sign in before making this change."},
    )


def require_auth(request: Request, *, write: bool = False) -> Dict[str, Any]:
    return resolve_auth_context(request, write=write)


def _safe_operation_projection(payload: Dict[str, Any]) -> Dict[str, Any]:
    from .services.lite_security_policy import redact_value

    def _redact_text_projection(value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            return redact_value(value)
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return redact_value(value)
        redacted = redact_value(parsed)
        try:
            return json.dumps(redacted, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError):
            return "***REDACTED***"

    clean = redact_value(payload)
    for key in ("stdout", "stderr"):
        if key in payload:
            clean[key] = _redact_text_projection(payload.get(key))
    if str(payload.get("operation") or "") == "rotate_secret":
        artifacts = dict(clean.get("artifacts") or {}) if isinstance(clean.get("artifacts"), dict) else {}
        if "value" in artifacts:
            artifacts["value"] = "***REDACTED***"
        clean["artifacts"] = artifacts
    return clean


def status_response(job_id: str) -> Dict[str, Any]:
    job = operation_service().get(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Operation job not found: {job_id}"
        )
    return _safe_operation_projection({
        "job_id": job.get("job_id"),
        "operation": job.get("operation"),
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "stdout": job.get("stdout"),
        "stderr": job.get("stderr"),
        "artifacts": job.get("artifacts", {}),
        "events": job.get("events", []),
        "task_id": job.get("task_id"),
    })


def job_response(job_id: str) -> Dict[str, Any]:
    job = operation_service().get(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Operation job not found: {job_id}"
        )
    return _safe_operation_projection(dict(job))
