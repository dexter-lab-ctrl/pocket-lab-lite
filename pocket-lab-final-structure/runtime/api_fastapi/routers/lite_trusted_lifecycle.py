"""Authenticated same-origin lifecycle review and consent records."""
import re

from fastapi import APIRouter, HTTPException, Request, Response

from .. import deps
from ..services import lite_lifecycle_authority as lifecycle
from ..services import lite_policy_opa

router = APIRouter(prefix="/api/lite/lifecycle", tags=["lite-trusted-lifecycle"])


def _call(request, response, operation, *args, write=False):
    response.headers["Cache-Control"] = "no-store"
    context = deps.require_auth(request, write=write)
    try:
        return operation(context, *args)
    except PermissionError as exc:
        raise HTTPException(403, detail={"reason_code": (str(exc) if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", str(exc)) else "lifecycle_review_required"), "message": "Current Owner authority is required."}) from exc
    except lite_policy_opa.PolicyDecisionError as exc:
        raise HTTPException(exc.status_code, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc
    except ValueError as exc:
        raise HTTPException(409, detail={"reason_code": (str(exc) if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", str(exc)) else "lifecycle_review_required"), "message": "Review the current lifecycle state before continuing."}) from exc


@router.get("/summary")
def summary(request: Request, response: Response):
    return _call(request, response, lifecycle.summary)


@router.post("/preferences/review")
def review_preferences(payload: lifecycle.PreferenceRequest, request: Request, response: Response):
    return _call(request, response, lifecycle.preview, "lifecycle.preferences.manage", payload, write=True)


@router.put("/preferences")
def preferences(payload: lifecycle.PreferenceRequest, request: Request, response: Response):
    return _call(request, response, lifecycle.save_profile, payload, write=True)


@router.post("/boundary/review")
def review_boundary(payload: lifecycle.GrantRequest, request: Request, response: Response):
    return _call(request, response, lifecycle.preview, "lifecycle.authority.manage", payload, write=True)


@router.post("/boundary")
def issue_boundary(payload: lifecycle.GrantRequest, request: Request, response: Response):
    return _call(request, response, lifecycle.issue, payload, write=True)


@router.post("/boundary/revoke")
def revoke_boundary(payload: lifecycle.RevokeRequest, request: Request, response: Response):
    return _call(request, response, lifecycle.revoke, payload, write=True)
