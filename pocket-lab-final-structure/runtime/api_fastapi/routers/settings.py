from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import deps
from ..services.governance_settings import (
    get_governance_settings,
    update_governance_settings,
)

router = APIRouter(tags=["settings"])


class GovernanceSettingsRequest(BaseModel):
    governanceMode: str = Field(default="personal", pattern="^(personal|enterprise)$")
    enterpriseModeEnabled: bool | None = None


@router.get("/api/settings/governance")
def get_governance(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return get_governance_settings()


@router.put("/api/settings/governance")
def update_governance(
    payload: GovernanceSettingsRequest,
    request: Request,
) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    try:
        return update_governance_settings({"governanceMode": payload.governanceMode})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
