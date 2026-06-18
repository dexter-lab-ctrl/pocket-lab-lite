from __future__ import annotations

from fastapi import APIRouter, Request

from .. import deps
from ..services.workflow_engine import WORKFLOW_ENGINE

router = APIRouter(tags=["workflows"])


@router.get("/api/workflows/status")
def workflow_status(request: Request) -> dict:
    deps.require_auth(request)
    return WORKFLOW_ENGINE.status()


@router.get("/api/workflows")
def list_workflows(
    request: Request, status: str = "", include_terminal: bool = True, limit: int = 100
) -> dict:
    deps.require_auth(request)
    return {
        "workflows": WORKFLOW_ENGINE.list_workflows(
            status=status, include_terminal=include_terminal, limit=limit
        ),
        "engine": WORKFLOW_ENGINE.status(),
    }


@router.get("/api/workflows/events")
def workflow_events(request: Request, workflow_id: str = "", limit: int = 250) -> dict:
    deps.require_auth(request)
    return {
        "events": WORKFLOW_ENGINE.iter_events(
            workflow_id=workflow_id or None, limit=limit
        )
    }


@router.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str, request: Request) -> dict:
    deps.require_auth(request)
    return WORKFLOW_ENGINE.reconstruct(workflow_id)


@router.post("/api/workflows/rebuild")
def rebuild_workflows(request: Request) -> dict:
    deps.require_auth(request, write=True)
    return WORKFLOW_ENGINE.rebuild_all()


@router.get("/api/workflows/recovery/plan")
def workflow_recovery_plan(
    request: Request, stale_seconds: int | None = None, limit: int = 100
) -> dict:
    deps.require_auth(request)
    return WORKFLOW_ENGINE.recovery_plan(stale_seconds=stale_seconds, limit=limit)


@router.post("/api/workflows/recover")
async def recover_workflows(
    request: Request,
    stale_seconds: int | None = None,
    limit: int = 25,
    dry_run: bool = False,
) -> dict:
    deps.require_auth(request, write=True)
    return await WORKFLOW_ENGINE.recover(
        stale_seconds=stale_seconds, limit=limit, dry_run=dry_run
    )


@router.post("/api/workflows/{workflow_id}/replay")
async def replay_workflow(
    workflow_id: str, request: Request, as_new: bool = True
) -> dict:
    deps.require_auth(request, write=True)
    return await WORKFLOW_ENGINE.replay_workflow(workflow_id, as_new=as_new)


@router.get("/api/workflows/{workflow_id}/command")
def workflow_command(workflow_id: str, request: Request) -> dict:
    deps.require_auth(request)
    command = WORKFLOW_ENGINE.command_for_workflow(workflow_id)
    if not command:
        return {"workflow_id": workflow_id, "command": None, "replayable": False}
    return {"workflow_id": workflow_id, "command": command, "replayable": True}
