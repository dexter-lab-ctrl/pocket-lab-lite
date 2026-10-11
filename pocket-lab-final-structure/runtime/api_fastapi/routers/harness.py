from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..services import lite_harness
from ..services import lite_invites, qualification_context

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
    target_device_id: str | None = Field(default=None, min_length=1, max_length=128)
    ttl_seconds: int | None = Field(default=None, ge=30, le=300)


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str = Field(min_length=36, max_length=40)
    signing_payload: str = Field(min_length=100, max_length=4096)
    signature: str = Field(min_length=80, max_length=100)
    principal_id: str | None = Field(default=None, min_length=3, max_length=80)
    profile: str | None = Field(default=None, min_length=1, max_length=64)
    ttl_seconds: int | None = Field(default=None, ge=60, le=3600)


class RecoveryAuthorizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup_id: str = Field(min_length=1, max_length=120)
    preview_id: str = Field(min_length=1, max_length=120)
    target_schema: int = Field(ge=1, le=999)
    confirm: bool = False


class BootstrapGrantRequest(BaseModel):
    """Public inputs for the operator-approved assurance bootstrap."""

    model_config = ConfigDict(extra="forbid")

    principal_id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9._-]{2,79}$")
    public_key: str = Field(min_length=40, max_length=64)


class BootstrapChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: str = Field(min_length=36, max_length=40, pattern=r"^hbg-[0-9a-f]{32}$")


class BootstrapCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str = Field(min_length=36, max_length=40, pattern=r"^hbc-[0-9a-f]{32}$")
    grant_id: str = Field(min_length=36, max_length=40, pattern=r"^hbg-[0-9a-f]{32}$")
    principal_id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9._-]{2,79}$")
    public_key: str = Field(min_length=40, max_length=64)
    signature: str = Field(min_length=80, max_length=100)
    ttl_seconds: int | None = Field(default=None, ge=60, le=3600)


class QualificationEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
    device_roles: list[str] = Field(min_length=1, max_length=2)


def _require_direct(request: Request) -> None:
    if not lite_harness.is_direct_local_request(request):
        raise HTTPException(
            status_code=401,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "harness_transport_rejected", "message": "The harness requires direct loopback transport.", "sanitized": True},
        )


def _require_bootstrap_direct(request: Request) -> None:
    _require_direct(request)
    if lite_harness.harness_headers_present(request):
        raise HTTPException(
            status_code=401,
            headers={"Cache-Control": "no-store"},
            detail={
                "reason_code": "bootstrap_transport_rejected",
                "message": "Bootstrap authority cannot be supplied through harness or proxy headers.",
                "sanitized": True,
            },
        )


def _raise(exc: lite_harness.HarnessError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
        detail={"reason_code": exc.reason_code, "message": exc.message, "sanitized": True},
    ) from exc


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post("/qualification/enroll", status_code=201)
async def qualification_enroll(
    payload: QualificationEnrollmentRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Enroll one synthetic device through the normal invite/bootstrap path.

    This bridge is unavailable outside the isolated qualification context and
    is bound to the single fleet-role harness target.  The raw invite token is
    returned only to the direct-loopback controller so it can exercise the
    existing bootstrap endpoint; it is never written to evidence or state.
    """
    _require_direct(request)
    try:
        auth = lite_harness.authenticate_request(request)
        lite_harness.enforce_capability(
            auth,
            action_id="qualification.device.enroll",
            target_type="device",
            target_id=payload.node_id,
        )
        qualification_context.assert_safe()
        result = lite_invites.create_lite_invite(
            hostname=payload.node_id,
            device_roles=payload.device_roles,
            authorization=auth,
            return_qualification_token=True,
        )
        await lite_invites.publish_invite_evidence(result)
        token = str(result.get("qualification_token") or "")
        if not token:
            raise lite_harness.HarnessError(
                "qualification_enrollment_unavailable",
                "The isolated qualification invite did not produce a bounded bootstrap token.",
                status_code=503,
            )
        _no_store(response)
        return {
            "status": "enrollment_ready",
            "node_id": payload.node_id,
            "device_roles": [str(item)[:32] for item in (result.get("invite") or {}).get("device_roles") or []],
            "qualification_token": token,
            "sanitized": True,
        }
    except lite_harness.HarnessError as exc:
        _raise(exc)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=422,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "qualification_enrollment_invalid", "message": str(exc)[:240], "sanitized": True},
        ) from exc


@router.post("/bootstrap/grants", status_code=201)
def bootstrap_grant(
    payload: BootstrapGrantRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Create a process-ephemeral, key-bound grant after operator startup approval."""
    _require_bootstrap_direct(request)
    try:
        result = lite_harness.create_bootstrap_grant(
            principal_id=payload.principal_id,
            public_key=payload.public_key,
        )
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/bootstrap/challenge")
def bootstrap_challenge(
    payload: BootstrapChallengeRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    _require_bootstrap_direct(request)
    try:
        result = lite_harness.issue_bootstrap_challenge(grant_id=payload.grant_id)
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/bootstrap/complete", status_code=201)
def bootstrap_complete(
    payload: BootstrapCompleteRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    _require_bootstrap_direct(request)
    try:
        result = lite_harness.complete_bootstrap(
            challenge_id=payload.challenge_id,
            grant_id=payload.grant_id,
            principal_id=payload.principal_id,
            public_key=payload.public_key,
            signature=payload.signature,
            ttl_seconds=payload.ttl_seconds,
        )
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


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


@router.post("/principal/revoke")
def revoke_authenticated_principal(request: Request, response: Response) -> dict[str, Any]:
    """Allow a bootstrap-created assurance principal to revoke itself.

    This is intentionally narrower than provisioning-token revocation: the
    signed session must be direct-loopback, bound to the assurance profile, and
    hold the server-owned cleanup capability.
    """
    _require_direct(request)
    try:
        auth = lite_harness.authenticate_request(request)
        auth_profile = str((auth.get("harness") or {}).get("profile") or "").strip().casefold()
        lite_harness.enforce_capability(
            auth,
            action_id=(
                "qualification.cleanup"
                if auth_profile == lite_harness.HARNESS_UI_PERFORMANCE_PROFILE
                else "security.assurance.cleanup"
            ),
            target_type="security_assurance",
            target_id="local-server",
        )
        result = lite_harness.revoke_authenticated_principal(auth)
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/browser/bridge")
def browser_bridge(request: Request, response: Response) -> dict[str, Any]:
    """Create a process-ephemeral bridge for a physical qualification browser."""
    _require_direct(request)
    try:
        auth = lite_harness.authenticate_request(request)
        lite_harness.enforce_capability(
            auth,
            action_id="qualification.browser_bridge",
            target_type="qualification_browser",
            target_id="local-server",
        )
        result = lite_harness.create_browser_bridge(auth)
    except lite_harness.HarnessError as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/recovery/authorize", status_code=201)
def recovery_authorize(
    payload: RecoveryAuthorizeRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Issue a narrow one-use receipt for the offline main-database handoff."""
    _require_direct(request)
    try:
        auth = lite_harness.authenticate_request(request)
        lite_harness.enforce_capability(
            auth,
            action_id="recovery.authorize",
            target_type="recovery",
            target_id=payload.backup_id,
            operation_id=payload.preview_id,
        )
        result = lite_harness.issue_recovery_receipt(
            auth,
            backup_id=payload.backup_id,
            preview_id=payload.preview_id,
            target_schema=payload.target_schema,
            confirm=payload.confirm,
        )
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
            target_device_id=payload.target_device_id,
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
