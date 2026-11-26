from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import deps

router = APIRouter(tags=["gitops"])


def _retired(request: Request) -> dict:
    deps.require_auth(request)
    raise HTTPException(
        status_code=410,
        detail={
            "status": "retired",
            "accepted": False,
            "executed": False,
            "reason_code": "legacy_gitops_api_retired",
            "replacement": "Native release, drift, and System Health APIs",
            "historical_record_preserved": True,
            "sanitized": True,
        },
    )


@router.get(
    "/api/pipeline_status.json",
    status_code=410,
    response_model=None,
    responses={410: {"description": "Legacy GitOps route retired."}},
)
def pipeline_status(request: Request) -> dict:
    return _retired(request)


@router.get(
    "/api/gitops/health.json",
    status_code=410,
    response_model=None,
    responses={410: {"description": "Legacy GitOps route retired."}},
)
def gitops_health(request: Request) -> dict:
    return _retired(request)


@router.get(
    "/api/git_history.json",
    status_code=410,
    response_model=None,
    responses={410: {"description": "Legacy GitOps route retired."}},
)
def git_history(request: Request) -> dict:
    return _retired(request)
