from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..services import lite_enterprise_identity

router = APIRouter(prefix="/api/lite/enterprise", tags=["lite-enterprise-identity"])


class EnterpriseModeRequest(BaseModel):
    enabled: bool


class EnterpriseMembershipRequest(BaseModel):
    role: str = Field(min_length=1, max_length=16)
    status: str = Field(default="active", min_length=1, max_length=16)


def _raise(exc: lite_enterprise_identity.EnterpriseIdentityError) -> None:
    raise HTTPException(status_code=exc.status_code, headers={"Cache-Control": "no-store"}, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc


@router.get("/identity")
def enterprise_identity(request: Request, response: Response) -> dict[str, Any]:
    auth = deps.require_auth(request, write=False)
    if (auth.get("actor") or {}).get("type") != "human":
        raise HTTPException(status_code=401, headers={"Cache-Control": "no-store"}, detail={"reason_code": "authentication_required", "message": "Sign in before viewing Enterprise identity controls."})
    result = lite_enterprise_identity.enterprise_projection(auth)
    if not result["enabled"]:
        raise HTTPException(status_code=404, headers={"Cache-Control": "no-store"}, detail={"reason_code": "enterprise_mode_disabled", "message": "Enterprise Mode is not enabled for this Pocket Lab."})
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/identity/mode")
def update_enterprise_mode(payload: EnterpriseModeRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_identity.set_enterprise_enabled(auth_context=deps.require_auth(request, write=True), enabled=payload.enabled, correlation_id=uuid.uuid4().hex)
    except lite_enterprise_identity.EnterpriseIdentityError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/identity/members")
def enterprise_members(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_identity.list_members(auth_context=deps.require_auth(request, write=False))
    except lite_enterprise_identity.EnterpriseIdentityError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/identity/members/{human_id}")
def update_enterprise_member(human_id: str, payload: EnterpriseMembershipRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_identity.set_membership(auth_context=deps.require_auth(request, write=True), human_id=human_id, role=payload.role, membership_status=payload.status, correlation_id=uuid.uuid4().hex)
    except lite_enterprise_identity.EnterpriseIdentityError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result
