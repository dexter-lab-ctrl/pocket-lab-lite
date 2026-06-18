from __future__ import annotations

from fastapi import APIRouter, Request

from .. import deps

router = APIRouter(tags=["gitops"])


@router.get("/api/pipeline_status.json")
def pipeline_status(request: Request) -> list[dict]:
    deps.require_auth(request)
    return deps.core.build_pipeline_status()


@router.get("/api/gitops/health.json")
def gitops_health(request: Request) -> dict:
    deps.require_auth(request)
    return {
        "repo": str(deps.settings().iac_dir),
        "ready": deps.settings().iac_dir.exists(),
        "git": deps.core.build_git_history(),
    }


@router.get("/api/git_history.json")
def git_history(request: Request) -> list[dict]:
    deps.require_auth(request)
    return deps.core.build_git_history()
