from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..services import lite_harness

router = APIRouter(prefix="/api/lite/harness", tags=["lite-harness"])


class PrincipalRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9._-]{2,79}$")
    display_name: str = Field(min_length=1, max_length=120)
    public_key: str = Field(min_length=40, max_length=64)
    profiles: list[str] = Field(
        min_length=1,
        max_length=7,
        validation_alias=AliasChoices("profiles", "allowed_profiles"),
        serialization_alias="profiles",
    )
    algorithm: str = Field(default="ed25519", min_length=1, max_length=32)
    expires_in_seconds: int = Field(default=86400, ge=60, le=604800)


class ChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_id: str = Field(min_length=3, max_length=80)
    purpose: str = Field(min_length=1, max_length=80)
    profile: str = Field(min_length=1, max_length=64)
    target_scope: str = Field(default=lite_harness.HARNESS_TARGET_SCOPE, min_length=3, max_length=64)
    ttl_seconds: int | None = Field(default=None, ge=30, le=300)


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str = Field(min_length=36, max_length=40)
    signing_payload: str = Field(min_length=100, max_length=4096)
    signature: str = Field(min_length=80, max_length=100)
    principal_id: str | None = Field(default=None, min_length=3, max_length=80)
    profile: str | None = Field(default=None, min_length=1, max_length=64)
    ttl_seconds: int | None = Field(default=None, ge=60, le=3600)


def _require_direct(request: Request) -> None:
    if not lite_harness.is_direct_local_request(request):
        raise HTTPException(
            status_code=401,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "harness_transport_rejected", "message": "The harness requires direct loopback transport.", "sanitized": True},
        )


def _raise(exc: lite_harness.HarnessError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
        detail={"reason_code": exc.reason_code, "message": exc.message, "sanitized": True},
    ) from exc


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/capabilities")
def capabilities(request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    _no_store(response)
    return lite_harness.profile_manifest()


@router.get("/status")
def status(request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    _no_store(response)
    try:
        return lite_harness.status_projection()
    except lite_harness.HarnessError as exc:
        _raise(exc)
    raise AssertionError("unreachable")


@router.post("/principals", status_code=201)
def register_principal(payload: PrincipalRegistrationRequest, request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    if not lite_harness.provisioning_allowed(request):
        _raise(lite_harness.HarnessError("harness_provisioning_rejected", "Synthetic-principal provisioning was not authorized.", status_code=401))
    try:
        result = lite_harness.register_principal(
            principal_id=payload.principal_id,
            display_name=payload.display_name,
            public_key=payload.public_key,
            profiles=payload.profiles,
            algorithm=payload.algorithm,
            expires_in_seconds=payload.expires_in_seconds,
        )
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/principals/{principal_id}/revoke")
@router.delete("/principals/{principal_id}")
def revoke_principal(principal_id: str, request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    if not lite_harness.provisioning_allowed(request):
        _raise(lite_harness.HarnessError("harness_provisioning_rejected", "Synthetic-principal revocation was not authorized.", status_code=401))
    try:
        result = lite_harness.revoke_principal(principal_id)
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/challenge")
def challenge(payload: ChallengeRequest, request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    try:
        result = lite_harness.issue_challenge(
            principal_id=payload.principal_id,
            purpose=payload.purpose,
            profile=payload.profile,
            target_scope=payload.target_scope,
            ttl_seconds=payload.ttl_seconds,
        )
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/session", status_code=201)
def session(payload: SessionRequest, request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    try:
        result = lite_harness.create_session(
            challenge_id=payload.challenge_id,
            signing_payload=payload.signing_payload,
            signature=payload.signature,
            principal_id=payload.principal_id,
            profile=payload.profile,
            ttl_seconds=payload.ttl_seconds,
        )
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.get("/session/{session_id}")
def session_status(session_id: str, request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    try:
        result = lite_harness.session_status(
            token=request.headers.get(lite_harness.HARNESS_SESSION_HEADER, ""),
            session_id=session_id,
        )
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.delete("/session/{session_id}")
def revoke_session(session_id: str, request: Request, response: Response) -> dict[str, Any]:
    _require_direct(request)
    try:
        result = lite_harness.revoke_session(
            token=request.headers.get(lite_harness.HARNESS_SESSION_HEADER, ""),
            session_id=session_id,
        )
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result
