from __future__ import annotations

from fastapi import APIRouter, Request

from .. import deps
from ..services.observability_status import get_observability_status_snapshot

router = APIRouter(tags=["observability"])


@router.get("/api/observability/status")
async def observability_status(request: Request) -> dict:
    """Return a bounded live status snapshot for the local observability stack."""
    deps.require_auth(request)
    return await get_observability_status_snapshot(use_cache=True)
