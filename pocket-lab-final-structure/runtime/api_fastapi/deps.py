# ruff: noqa: E402
from __future__ import annotations

import os
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
            current_tag=os.environ.get("POCKETLAB_RELEASE_TAG", "v1.0.0"),
            github_repo=os.environ.get(
                "POCKETLAB_GITHUB_REPO", "dexter-lab-ctrl/pocket-lab"
            ),
            poll_interval=core._env_int("POCKETLAB_RELEASE_POLL_SECONDS", 180),
            auto_apply=core._env_bool("POCKETLAB_AUTO_RELEASE_APPLY", True),
        )
        core.AUTO_UPDATER.start()
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


def require_auth(request: Request, *, write: bool = False) -> None:
    # Unit/contract tests use an explicit bypass header so backend tests can
    # exercise operation validation and NATS-required behavior without needing
    # a real user token. This is inert in production unless both the env var
    # and test-only header are deliberately present.
    if (
        os.environ.get("POCKETLAB_TEST_AUTH_BYPASS") == "1"
        and request.headers.get("x-pocket-lab-test") == "1"
    ):
        return
    cfg = settings()
    token = cfg.api_token.strip()
    if write and not token and cfg.allow_local_write and loopback_client(request):
        return
    if not token:
        if not write or loopback_client(request):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    if bearer_token(request) == token:
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def status_response(job_id: str) -> Dict[str, Any]:
    job = operation_service().get(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Operation job not found: {job_id}"
        )
    return {
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
    }


def job_response(job_id: str) -> Dict[str, Any]:
    job = operation_service().get(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Operation job not found: {job_id}"
        )
    return job
