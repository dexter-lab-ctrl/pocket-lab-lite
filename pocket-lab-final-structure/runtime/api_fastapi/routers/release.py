from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from .. import deps
from ..services.nats_bus import BUS
from ..services.action_queue import submit_domain_command

router = APIRouter(tags=["release"])


@router.get("/api/release/workflow.json")
@router.get("/api/release/workflow")
def release_workflow(request: Request) -> dict:
    deps.require_auth(request)
    return deps.core.build_release_workflow(deps.core.ROOT_DIR)


@router.get("/api/release/self-update/status")
def release_status(background_tasks: BackgroundTasks, request: Request) -> dict:
    deps.require_auth(request)
    updater = deps.ensure_release_updater()
    status = (
        updater.status()
        if updater
        else {
            "phase": "idle",
            "current_tag": "unknown",
            "latest_tag": "unknown",
            "update_available": False,
            "auto_apply": False,
            "operations": [],
        }
    )
    try:
        from ..services.release_orchestrator import release_orchestration_status

        status["orchestration"] = release_orchestration_status()
    except Exception:
        status.setdefault("orchestration", {"runs": [], "latest": {}})
    background_tasks.add_task(
        BUS.publish_json, "pocketlab.events.release.status", "release.status", status
    )
    return status


@router.post("/api/release/self-update/check", status_code=202)
async def release_check(background_tasks: BackgroundTasks, request: Request) -> dict:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.release.check",
        "release.check.requested",
        {},
    )


@router.post("/api/release/self-update/apply", status_code=202)
async def release_apply(background_tasks: BackgroundTasks, request: Request) -> dict:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.release.apply",
        "release.apply.requested",
        {"force": True},
    )
