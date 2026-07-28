from __future__ import annotations

from fastapi import APIRouter, Request

from .. import deps
from ..services.action_queue import submit_domain_command
from ..services.release_runtime import read_release_status

router = APIRouter(tags=["release"])


@router.get("/api/release/workflow.json")
@router.get("/api/release/workflow")
def release_workflow(request: Request) -> dict:
    deps.require_auth(request)
    return deps.core.build_release_workflow(deps.core.ROOT_DIR)


@router.get("/api/lite/release")
@router.get("/api/release/self-update/status")
def release_status(request: Request) -> dict:
    deps.require_auth(request)
    status = read_release_status()
    status["orchestration"] = {
        "prepared": True,
        "latest": {
            "command_id": status.get("active_command_id") or "",
            "status": status.get("status"),
            "phase": status.get("phase"),
            "operation": status.get("active_operation") or "",
        },
        "runs": [],
    }
    return status


@router.post("/api/lite/release/check", status_code=202)
@router.post("/api/release/self-update/check", status_code=202)
async def release_check(request: Request) -> dict:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.release.check",
        "release.check.requested",
        {},
    )


@router.post("/api/lite/release/apply", status_code=202)
@router.post("/api/release/self-update/apply", status_code=202)
async def release_apply(request: Request) -> dict:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.release.apply",
        "release.apply.requested",
        {"force": False},
    )
