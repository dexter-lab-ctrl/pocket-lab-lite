from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..services import (
    lite_enterprise_enrollment,
    lite_enterprise_governance,
    lite_enterprise_identity,
    lite_enterprise_managed_enrollment,
    lite_identity_auth,
)

router = APIRouter(prefix="/api/lite/enterprise", tags=["lite-enterprise-identity"])


class EnterpriseModeRequest(BaseModel):
    enabled: bool


class EnterpriseMembershipRequest(BaseModel):
    role: str = Field(min_length=1, max_length=16)
    status: str = Field(default="active", min_length=1, max_length=16)


class PersonCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=16)


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
    if isinstance(
        exc,
        (
            lite_enterprise_identity.EnterpriseIdentityError,
            lite_enterprise_enrollment.EnrollmentError,
            lite_enterprise_managed_enrollment.ManagedEnrollmentError,
            lite_enterprise_governance.GovernanceError,
        ),
    ):
        raise HTTPException(
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": exc.reason_code, "message": exc.message},
        ) from exc
    raise exc


def _request_origin(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin:
        return origin
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def _set_identity_cookie(response: Response, session_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=lite_identity_auth.cookie_name(),
        value=session_token,
        max_age=lite_identity_auth.session_cookie_max_age(),
        httponly=True,
        secure=lite_identity_auth.cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key=lite_identity_auth.csrf_cookie_name(),
        value=csrf_token,
        max_age=lite_identity_auth.session_cookie_max_age(),
        httponly=False,
        secure=lite_identity_auth.cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _without_invite_secret(result: dict[str, Any], *, summary: str) -> dict[str, Any]:
    safe = dict(result or {})
    safe.pop("invite", None)
    safe["summary"] = summary
    safe["enrollment_method"] = "managed_webauthn"
    return safe


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
        raise HTTPException(
            status_code=401,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "authentication_required", "message": "Sign in before viewing Enterprise identity controls."},
        )
    result = lite_enterprise_identity.enterprise_projection(auth)
    if not result["enabled"]:
        raise HTTPException(
            status_code=404,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "enterprise_mode_disabled", "message": "Enterprise Mode is not enabled for this Pocket Lab."},
        )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/identity/mode/preview")
def preview_enterprise_mode(enabled: bool, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_identity.mode_preview(
            auth_context=deps.require_auth(request, write=False),
            enabled=enabled,
        )
    except lite_enterprise_identity.EnterpriseIdentityError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/identity/mode")
def update_enterprise_mode(payload: EnterpriseModeRequest, request: Request, response: Response) -> dict[str, Any]:
    auth = deps.require_auth(request, write=True)
    try:
        lite_enterprise_governance.require_recent_assurance(auth, "enterprise.mode.change")
        result = lite_enterprise_identity.set_enterprise_enabled(
            auth_context=auth,
            enabled=payload.enabled,
            correlation_id=uuid.uuid4().hex,
        )
    except (lite_enterprise_identity.EnterpriseIdentityError, lite_enterprise_governance.GovernanceError) as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/identity/members")
def enterprise_members(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_identity.list_members(
            auth_context=deps.require_auth(request, write=False)
        )
    except lite_enterprise_identity.EnterpriseIdentityError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/identity/members/{human_id}")
def update_enterprise_member(
    human_id: str,
    payload: EnterpriseMembershipRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_enterprise_identity.set_membership(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
            role=payload.role,
            membership_status=payload.status,
            correlation_id=uuid.uuid4().hex,
        )
    except lite_enterprise_identity.EnterpriseIdentityError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people", status_code=201)
def create_enterprise_person(
    payload: PersonCreateRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.create_person(
            auth_context=deps.require_auth(request, write=True),
            username=payload.username,
            display_name=payload.display_name,
            role=payload.role,
            origin=_request_origin(request),
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return _without_invite_secret(
        result,
        summary="Person created. Use Set up passkey to finish enrollment without exposing a Pocket Lab token.",
    )


@router.get("/identity/people")
def enterprise_people(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.list_people(
            auth_context=deps.require_auth(request, write=False)
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/identity/people/{human_id}")
def enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.read_person(
            auth_context=deps.require_auth(request, write=False),
            human_id=human_id,
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/passkey/options")
def enterprise_person_managed_passkey_options(
    human_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_enterprise_managed_enrollment.registration_options(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
            origin=_request_origin(request),
        )
    except lite_enterprise_managed_enrollment.ManagedEnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/passkey/verify", status_code=201)
def enterprise_person_managed_passkey_verify(
    human_id: str,
    payload: PersonPasskeyVerifyRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_enterprise_managed_enrollment.complete_registration(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
            origin=_request_origin(request),
            challenge=payload.challenge,
            payload=payload.credential,
            friendly_name=payload.friendly_name,
        )
    except lite_enterprise_managed_enrollment.ManagedEnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/invite")
def legacy_enterprise_person_invite(
    human_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    # Authenticate/authorize before returning the compatibility response. The
    # endpoint intentionally never generates or returns an enrollment token.
    try:
        lite_enterprise_enrollment.read_person(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    raise HTTPException(
        status_code=410,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": "enterprise_connect_links_retired",
            "message": "Pocket Lab no longer exposes person connect tokens. Use Set up passkey for managed WebAuthn enrollment.",
        },
    )


@router.post("/identity/people/{human_id}/suspend")
def suspend_enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.suspend_person(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/reactivate")
def reactivate_enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.reactivate_person(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/people/{human_id}/reset-access")
def reset_enterprise_person_access(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.reset_access(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
            origin=_request_origin(request),
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return _without_invite_secret(
        result,
        summary="Sign-in reset. Old credentials were revoked; use Set up passkey to enroll a new credential without exposing a token.",
    )


@router.delete("/identity/people/{human_id}")
def remove_enterprise_person(human_id: str, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.remove_person(
            auth_context=deps.require_auth(request, write=True),
            human_id=human_id,
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/enrollment/consume")
def legacy_person_claim_consume(request: Request) -> dict[str, Any]:
    # No body model is intentionally declared: Pocket Lab does not parse or
    # reflect a legacy bearer claim. This branch was never released with that
    # contract, so callers receive an explicit safe migration response.
    raise HTTPException(
        status_code=410,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": "enterprise_connect_links_retired",
            "message": "Person connect tokens are not exposed. Ask an Owner or Admin to use Set up passkey.",
        },
    )


@router.get("/identity/enrollment/status")
def legacy_person_claim_status(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return {
        "active": False,
        "status": "enterprise_connect_links_retired",
        "summary": "Person enrollment is managed by an authorized Owner or Admin through WebAuthn.",
    }


@router.post("/identity/enrollment/passkey/options")
def legacy_person_claim_passkey_options() -> dict[str, Any]:
    raise HTTPException(
        status_code=410,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": "enterprise_connect_links_retired",
            "message": "Use the authorized person passkey setup flow instead.",
        },
    )


@router.post("/identity/enrollment/passkey/verify")
def legacy_person_claim_passkey_verify() -> dict[str, Any]:
    raise HTTPException(
        status_code=410,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": "enterprise_connect_links_retired",
            "message": "Use the authorized person passkey setup flow instead.",
        },
    )


@router.post("/identity/passkeys/login/options")
def enterprise_passkey_login_options(
    payload: HumanPasskeyLoginOptionsRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_enterprise_enrollment.login_options(
            origin=_request_origin(request),
            username=payload.username,
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/passkeys/login/verify")
def enterprise_passkey_login_verify(
    payload: HumanPasskeyLoginVerifyRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        session = lite_enterprise_enrollment.complete_login(
            origin=_request_origin(request),
            challenge=payload.challenge,
            payload=payload.credential,
        )
    except lite_enterprise_enrollment.EnrollmentError as exc:
        _raise(exc)
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    auth = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_enterprise_enrollment.unified_identity_projection(auth)
    projection["csrf_token"] = session["csrf_token"]
    return projection
