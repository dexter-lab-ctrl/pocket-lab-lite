from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..services import lite_enterprise_enrollment, lite_enterprise_governance, lite_enterprise_identity, lite_identity_auth

router = APIRouter(prefix="/api/lite/enterprise", tags=["lite-enterprise-identity"])
PERSON_CLAIM_COOKIE = "__Host-pocketlab_person_claim"


class EnterpriseModeRequest(BaseModel):
    enabled: bool


class EnterpriseMembershipRequest(BaseModel):
    role: str = Field(min_length=1, max_length=16)
    status: str = Field(default="active", min_length=1, max_length=16)


class PersonCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=16)


class PersonClaimConsumeRequest(BaseModel):
    claim: str = Field(min_length=20, max_length=512)


class PersonPasskeyVerifyRequest(BaseModel):
    challenge: str = Field(min_length=20, max_length=512)
    credential: dict[str, Any] = Field(default_factory=dict)
    friendly_name: str = Field(default="Primary passkey", min_length=1, max_length=80)


class HumanPasskeyLoginOptionsRequest(BaseModel):
    username: str = Field(default="", max_length=64)


class HumanPasskeyLoginVerifyRequest(BaseModel):
    challenge: str = Field(min_length=20, max_length=512)
    credential: dict[str, Any] = Field(default_factory=dict)


def _raise(exc: Exception) -> None:
    if isinstance(exc, (lite_enterprise_identity.EnterpriseIdentityError, lite_enterprise_enrollment.EnrollmentError, lite_enterprise_governance.GovernanceError)):
        raise HTTPException(status_code=exc.status_code, headers={"Cache-Control": "no-store"}, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc
    raise exc


def _request_origin(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin:
        return origin
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def _person_cookie_name() -> str:
    return PERSON_CLAIM_COOKIE if lite_identity_auth.cookie_secure() else "pocketlab_person_claim"


def _set_person_claim_cookie(response: Response, authority: str) -> None:
    response.set_cookie(key=_person_cookie_name(), value=authority, max_age=300, httponly=True, secure=lite_identity_auth.cookie_secure(), samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"


def _clear_person_claim_cookie(response: Response) -> None:
    response.delete_cookie(key=_person_cookie_name(), httponly=True, secure=lite_identity_auth.cookie_secure(), samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"


def _set_identity_cookie(response: Response, session_token: str, csrf_token: str) -> None:
    response.set_cookie(key=lite_identity_auth.cookie_name(), value=session_token, max_age=lite_identity_auth.session_cookie_max_age(), httponly=True, secure=lite_identity_auth.cookie_secure(), samesite="strict", path="/")
    response.set_cookie(key=lite_identity_auth.csrf_cookie_name(), value=csrf_token, max_age=lite_identity_auth.session_cookie_max_age(), httponly=False, secure=lite_identity_auth.cookie_secure(), samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"


@router.get("/identity/self")
def enterprise_identity_self(request: Request, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return lite_enterprise_enrollment.unified_identity_projection(deps.resolve_auth_context(request))


@router.get("/access")
def enterprise_access(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_governance.access_projection(deps.require_auth(request, write=False))
    except lite_enterprise_governance.GovernanceError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


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


@router.get("/identity/mode/preview")
def preview_enterprise_mode(enabled: bool, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_identity.mode_preview(auth_context=deps.require_auth(request, write=False), enabled=enabled)
    except lite_enterprise_identity.EnterpriseIdentityError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/identity/mode")
def update_enterprise_mode(payload: EnterpriseModeRequest, request: Request, response: Response) -> dict[str, Any]:
    auth = deps.require_auth(request, write=True)
    try:
        lite_enterprise_governance.require_recent_assurance(auth, "enterprise.mode.change")
        result = lite_enterprise_identity.set_enterprise_enabled(auth_context=auth, enabled=payload.enabled, correlation_id=uuid.uuid4().hex)
    except (lite_enterprise_identity.EnterpriseIdentityError, lite_enterprise_governance.GovernanceError) as exc:
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


@router.post("/identity/people", status_code=201)
def create_enterprise_person(payload: PersonCreateRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.create_person(auth_context=deps.require_auth(request, write=True), username=payload.username, display_name=payload.display_name, role=payload.role, origin=_request_origin(request))
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/identity/people")
def enterprise_people(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.list_people(auth_context=deps.require_auth(request, write=False))
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/identity/people/{human_id}")
def enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.read_person(auth_context=deps.require_auth(request, write=False), human_id=human_id)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/invite")
def regenerate_enterprise_person_invite(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.regenerate_invite(auth_context=deps.require_auth(request, write=True), human_id=human_id, origin=_request_origin(request))
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/suspend")
def suspend_enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.suspend_person(auth_context=deps.require_auth(request, write=True), human_id=human_id)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/reactivate")
def reactivate_enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.reactivate_person(auth_context=deps.require_auth(request, write=True), human_id=human_id)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/reset-access")
def reset_enterprise_person_access(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.reset_access(auth_context=deps.require_auth(request, write=True), human_id=human_id, origin=_request_origin(request))
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.delete("/identity/people/{human_id}")
def remove_enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.remove_person(auth_context=deps.require_auth(request, write=True), human_id=human_id)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/enrollment/consume")
def consume_enterprise_person_claim(payload: PersonClaimConsumeRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.consume_claim(raw_claim=payload.claim, origin=_request_origin(request))
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    _set_person_claim_cookie(response, result["authority"])
    return {"status": result["status"], "expires_at": result["expires_at"], "summary": "Connect link verified. Create a passkey to finish joining Pocket Lab."}


@router.get("/identity/enrollment/status")
def enterprise_person_claim_status(request: Request, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return lite_enterprise_enrollment.claim_status(authority=request.cookies.get(_person_cookie_name(), ""), origin=_request_origin(request))


@router.post("/identity/enrollment/passkey/options")
def enterprise_person_passkey_options(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.enrollment_options(authority=request.cookies.get(_person_cookie_name(), ""), origin=_request_origin(request))
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/enrollment/passkey/verify", status_code=201)
def enterprise_person_passkey_verify(payload: PersonPasskeyVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.complete_enrollment(authority=request.cookies.get(_person_cookie_name(), ""), origin=_request_origin(request), challenge=payload.challenge, payload=payload.credential, friendly_name=payload.friendly_name)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    session = result["session"]
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    _clear_person_claim_cookie(response)
    auth = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_enterprise_enrollment.unified_identity_projection(auth)
    projection["csrf_token"] = session["csrf_token"]
    projection["recovery_codes"] = result["recovery_codes"]
    projection["summary"] = result["summary"]
    return projection


@router.post("/identity/passkeys/login/options")
def enterprise_passkey_login_options(payload: HumanPasskeyLoginOptionsRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.login_options(origin=_request_origin(request), username=payload.username)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/passkeys/login/verify")
def enterprise_passkey_login_verify(payload: HumanPasskeyLoginVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        session = lite_enterprise_enrollment.complete_login(origin=_request_origin(request), challenge=payload.challenge, payload=payload.credential)
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    auth = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_enterprise_enrollment.unified_identity_projection(auth)
    projection["csrf_token"] = session["csrf_token"]
    return projection
