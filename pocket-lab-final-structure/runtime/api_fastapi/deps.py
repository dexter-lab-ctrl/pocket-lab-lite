# ruff: noqa: E402
from __future__ import annotations

import os
import hmac
import json
import pathlib
import sys
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


def bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    scheme, credentials = get_authorization_scheme_param(auth)
    if scheme.lower() == "bearer" and credentials:
        return credentials.strip()
    return request.headers.get("x-pocket-lab-token", "").strip()


def resolve_auth_context(request: Request, *, write: bool = False) -> Dict[str, Any]:
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
        return {
            **session_context,
            "auth_method": str((session_context.get("session") or {}).get("auth_method") or "session"),
        }

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
