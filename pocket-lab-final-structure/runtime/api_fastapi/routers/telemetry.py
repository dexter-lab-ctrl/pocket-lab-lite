from __future__ import annotations

from fastapi import APIRouter, Request

from .. import deps
from ..services.live_status import LIVE_STATUS

router = APIRouter(tags=["telemetry"])


@router.get("/api/telemetry")
@router.get("/api/telemetry.json")
async def telemetry(request: Request) -> dict:
    deps.require_auth(request)
    return await LIVE_STATUS.sample_telemetry(source="api-read")


@router.get("/api/telemetry/live/status")
def telemetry_live_status(request: Request) -> dict:
    deps.require_auth(request)
    return LIVE_STATUS.status()
