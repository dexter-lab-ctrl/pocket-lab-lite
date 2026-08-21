from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..services import lite_identity_auth, lite_policy_opa, lite_webauthn

router = APIRouter(prefix="/api/lite", tags=["lite-identity-p1"])


class LiteOwnerClaimIssueRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=512)
    ttl_seconds: int | None = Field(default=None, ge=60, le=1800)


class LiteOwnerClaimConsumeRequest(BaseModel):
    claim: str = Field(min_length=20, max_length=512)


class LiteOwnerClaimPasskeyOptionsRequest(BaseModel):
    username: str = Field(default="owner", min_length=1, max_length=64)
    display_name: str = Field(default="Pocket Lab Owner", max_length=120)


class LitePasskeyVerifyRequest(BaseModel):
    challenge: str = Field(min_length=20, max_length=512)
    credential: dict[str, Any] = Field(default_factory=dict)
    friendly_name: str = Field(default="Passkey", max_length=80)
    username: str = Field(default="owner", min_length=1, max_length=64)
    display_name: str = Field(default="Pocket Lab Owner", max_length=120)


class LitePasskeyRenameRequest(BaseModel):
    friendly_name: str = Field(min_length=1, max_length=80)


class LitePasskeyStepUpRequest(BaseModel):
    purpose: str = Field(default="identity.passkey.revoke", min_length=1, max_length=80)


class LitePasskeyStepUpVerifyRequest(BaseModel):
    purpose: str = Field(default="identity.passkey.revoke", min_length=1, max_length=80)
    challenge: str = Field(min_length=20, max_length=512)
    credential: dict[str, Any] = Field(default_factory=dict)


def _raise_webauthn_error(exc: lite_webauthn.WebAuthnError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
        detail={"reason_code": exc.reason_code, "message": exc.message},
    ) from exc


def _request_origin(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin:
        return origin
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def _set_owner_claim_cookie(response: Response, authority: str) -> None:
    response.set_cookie(
        key=lite_webauthn.owner_claim_cookie_name(),
        value=authority,
        max_age=lite_webauthn.owner_authority_ttl_seconds(),
        httponly=True,
        secure=lite_webauthn.owner_claim_cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_owner_claim_cookie(response: Response) -> None:
    response.delete_cookie(
        key=lite_webauthn.owner_claim_cookie_name(),
        httponly=True,
        secure=lite_webauthn.owner_claim_cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


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


def _require_human_session(request: Request) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    auth_context = deps.require_auth(request, write=True)
    actor = auth_context.get("actor") or {}
    session = auth_context.get("session") or {}
    if actor.get("type") != "human" or not session.get("session_id"):
        raise HTTPException(
            status_code=403,
            detail={"reason_code": "human_session_required", "message": "A signed-in owner session is required."},
        )
    return auth_context, actor, session


async def _enforce_policy(
    *,
    auth_context: dict[str, Any],
    action_id: str,
    target_type: str,
    target_id: str,
    target_revision: str,
    target: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            lite_policy_opa.evaluate_authorization,
            auth_context=auth_context,
            action_id=action_id,
            target_type=target_type,
            target_id=target_id,
            target_revision=target_revision,
            target=target,
            request_context={"source": "lite_api"},
            correlation_id=correlation_id,
        )
    except lite_policy_opa.PolicyDecisionError as exc:
        decision = exc.decision or {}
        raise HTTPException(
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
            detail={
                "status": "blocked",
                "accepted": False,
                "reason_code": exc.reason_code,
                "message": exc.message,
                "decision_id": decision.get("decision_id"),
                "policy_revision": decision.get("policy_revision"),
            },
        ) from exc


@router.post("/identity/owner-claim", status_code=201)
def issue_lite_owner_claim(payload: LiteOwnerClaimIssueRequest, request: Request, response: Response) -> dict[str, Any]:
    configured = os.environ.get("POCKETLAB_IDENTITY_SETUP_TOKEN", "")
    supplied = request.headers.get("X-Pocket-Lab-Setup-Token", "")
    if not configured:
        raise HTTPException(
            status_code=503,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "identity_setup_unavailable", "message": "Owner claim creation is not enabled on this server."},
        )
    if not supplied or not hmac.compare_digest(supplied, configured):
        raise HTTPException(
            status_code=401,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "identity_setup_rejected", "message": "Owner claim creation could not be verified."},
        )
    try:
        result = lite_webauthn.issue_owner_claim(origin=payload.origin, ttl_seconds=payload.ttl_seconds)
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/owner-claim/consume")
def consume_lite_owner_claim(payload: LiteOwnerClaimConsumeRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_webauthn.consume_owner_claim(raw_claim=payload.claim, origin=_request_origin(request))
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    _set_owner_claim_cookie(response, result["authority"])
    return {
        "status": result["status"],
        "expires_at": result["expires_at"],
        "summary": "Owner claim verified. Create a passkey to finish setup.",
    }


@router.get("/identity/owner-claim/status")
def owner_claim_status(request: Request, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return lite_webauthn.owner_claim_status(
        authority=request.cookies.get(lite_webauthn.owner_claim_cookie_name(), ""),
        origin=_request_origin(request),
    )


@router.post("/identity/owner-claim/passkey/options")
def owner_claim_passkey_options(payload: LiteOwnerClaimPasskeyOptionsRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_webauthn.owner_claim_registration_options(
            authority=request.cookies.get(lite_webauthn.owner_claim_cookie_name(), ""),
            origin=_request_origin(request),
            username=payload.username,
            display_name=payload.display_name,
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/owner-claim/passkey/verify", status_code=201)
def owner_claim_passkey_verify(payload: LitePasskeyVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_webauthn.complete_owner_claim_registration(
            authority=request.cookies.get(lite_webauthn.owner_claim_cookie_name(), ""),
            origin=_request_origin(request),
            challenge=payload.challenge,
            payload=payload.credential,
            username=payload.username,
            display_name=payload.display_name,
            friendly_name=payload.friendly_name,
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    session = result["session"]
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    _clear_owner_claim_cookie(response)
    auth_context = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_identity_auth.identity_projection(auth_context)
    projection["csrf_token"] = session["csrf_token"]
    projection["setup_completed"] = True
    projection["recovery_codes"] = result["recovery_codes"]
    projection["summary"] = "Owner created with a passkey. Save the recovery codes somewhere private."
    return projection


@router.post("/identity/passkeys/login/options")
def passkey_login_options(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_webauthn.login_options(origin=_request_origin(request))
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/passkeys/login/verify")
def passkey_login_verify(payload: LitePasskeyVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        session = lite_webauthn.complete_login(
            origin=_request_origin(request), challenge=payload.challenge, payload=payload.credential
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    auth_context = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_identity_auth.identity_projection(auth_context)
    projection["csrf_token"] = session["csrf_token"]
    return projection


@router.post("/identity/passkeys/registration/options")
def passkey_registration_options(request: Request, response: Response) -> dict[str, Any]:
    _, actor, session = _require_human_session(request)
    try:
        result = lite_webauthn.registration_options(
            human_id=str(actor["identity_id"]),
            session_id=str(session["session_id"]),
            origin=_request_origin(request),
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/passkeys/registration/verify", status_code=201)
def passkey_registration_verify(payload: LitePasskeyVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    _, actor, session = _require_human_session(request)
    try:
        credential = lite_webauthn.complete_registration(
            human_id=str(actor["identity_id"]),
            session_id=str(session["session_id"]),
            origin=_request_origin(request),
            challenge=payload.challenge,
            payload=payload.credential,
            friendly_name=payload.friendly_name,
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return {"status": "created", "credential": credential, "summary": "Passkey added."}


@router.post("/identity/step-up/options")
def passkey_step_up_options(payload: LitePasskeyStepUpRequest, request: Request, response: Response) -> dict[str, Any]:
    _, actor, session = _require_human_session(request)
    try:
        result = lite_webauthn.step_up_options(
            human_id=str(actor["identity_id"]),
            session_id=str(session["session_id"]),
            origin=_request_origin(request),
            purpose=payload.purpose,
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/identity/step-up/verify")
def passkey_step_up_verify(payload: LitePasskeyStepUpVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    _, actor, session = _require_human_session(request)
    try:
        result = lite_webauthn.complete_step_up(
            human_id=str(actor["identity_id"]),
            session_id=str(session["session_id"]),
            origin=_request_origin(request),
            purpose=payload.purpose,
            challenge=payload.challenge,
            payload=payload.credential,
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/identity/passkeys/{credential_id}")
def rename_lite_passkey(credential_id: str, payload: LitePasskeyRenameRequest, request: Request, response: Response) -> dict[str, Any]:
    _, actor, session = _require_human_session(request)
    try:
        result = lite_webauthn.rename_credential(
            human_id=str(actor["identity_id"]),
            credential_id=credential_id,
            friendly_name=payload.friendly_name,
            session_id=str(session["session_id"]),
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.delete("/identity/passkeys/{credential_id}")
async def revoke_lite_passkey(credential_id: str, request: Request, response: Response) -> dict[str, Any]:
    auth_context, actor, session = _require_human_session(request)
    correlation_id = f"passkey-revoke-{uuid.uuid4().hex}"
    decision = await _enforce_policy(
        auth_context=auth_context,
        action_id="identity.passkey.revoke",
        target_type="passkey",
        target_id=credential_id,
        target_revision=hashlib.sha256(credential_id.encode("utf-8")).hexdigest()[:24],
        target={"requested_by_owner": True},
        correlation_id=correlation_id,
    )
    try:
        result = lite_webauthn.revoke_credential(
            human_id=str(actor["identity_id"]),
            credential_id=credential_id,
            session_id=str(session["session_id"]),
            correlation_id=correlation_id,
        )
    except lite_webauthn.WebAuthnError as exc:
        _raise_webauthn_error(exc)
    response.headers["Cache-Control"] = "no-store"
    result["authorization"] = {
        "decision_id": decision.get("decision_id"),
        "reason_code": decision.get("reason_code"),
        "policy_revision": decision.get("policy_revision"),
    }
    return result


@router.get("/policy/templates")
def get_lite_policy_templates(request: Request, response: Response) -> dict[str, Any]:
    deps.require_auth(request)
    response.headers["Cache-Control"] = "no-cache"
    return {
        "templates": lite_policy_opa.policy_templates(),
        "mutation_enabled": False,
        "summary": "Safe templates are server-owned and cannot be edited as free-form Rego in Lite mode.",
    }


@router.get("/policy/decisions/{decision_id}")
def get_lite_policy_decision(decision_id: str, request: Request, response: Response) -> dict[str, Any]:
    deps.require_auth(request)
    detail = lite_policy_opa.decision_detail(decision_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={"reason_code": "policy_decision_not_found", "message": "That Safety Rules decision is no longer available."},
        )
    response.headers["Cache-Control"] = "no-cache"
    return detail
