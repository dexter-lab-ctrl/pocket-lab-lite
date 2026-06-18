from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from .. import deps
from ..services.action_queue import submit_domain_command

router = APIRouter(tags=["catalog"])


@router.get("/api/catalog.json")
def catalog(request: Request) -> list[dict]:
    deps.require_auth(request)
    return deps.core.build_catalog_view()


@router.get("/api/catalog/refresh")
def catalog_refresh_get(request: Request) -> dict:
    deps.require_auth(request)
    from fastapi import HTTPException

    raise HTTPException(status_code=405, detail="Use POST for catalog refresh")


@router.post("/api/catalog/refresh", status_code=202)
async def catalog_refresh(background_tasks: BackgroundTasks, request: Request) -> dict:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.catalog.refresh",
        "catalog.refresh.requested",
        {},
    )
