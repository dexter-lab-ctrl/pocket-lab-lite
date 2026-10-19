from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .. import deps
from ..services import lite_owner_operations, lite_policy_opa

router = APIRouter(prefix="/api/lite/owner-operations", tags=["lite-owner-operations"])


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientChallengeRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    public_key: str = Field(min_length=40, max_length=96)


class ClientPairingChallengeRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    public_key: str = Field(min_length=40, max_length=96)


class ClientPairingRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    public_key: str = Field(min_length=40, max_length=96)
    challenge_id: str = Field(min_length=20, max_length=64)
    signature: str = Field(min_length=80, max_length=160)


class ClientPairingDecisionRequest(_StrictModel):
    reason: str = Field(default="owner_rejected", min_length=1, max_length=80)


class PairingObserverChallengeRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    pairing_id: str = Field(min_length=28, max_length=28)


class PairingCancelChallengeRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    pairing_id: str = Field(min_length=28, max_length=28)


class SignedPairingRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    challenge_id: str = Field(min_length=20, max_length=64)
    signature: str = Field(min_length=80, max_length=160)


class ClientRegistrationRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    public_key: str = Field(min_length=40, max_length=96)
    challenge_id: str = Field(min_length=20, max_length=64)
    signature: str = Field(min_length=80, max_length=160)


class ClientRevokeRequest(_StrictModel):
    reason: str = Field(default="owner_revoked", min_length=1, max_length=80)


class RequestChallengeRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    descriptor: dict[str, Any]


class SignedOperationRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    descriptor: dict[str, Any]
    challenge_id: str = Field(min_length=20, max_length=64)
    signature: str = Field(min_length=80, max_length=160)


class ObserverChallengeRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    operation_id: str = Field(min_length=27, max_length=40)
    purpose: str = Field(default="observe", min_length=1, max_length=16)


class SignedObserverRequest(_StrictModel):
    client_id: str = Field(min_length=3, max_length=80)
    challenge_id: str = Field(min_length=20, max_length=64)
    signature: str = Field(min_length=80, max_length=160)


class RejectOperationRequest(_StrictModel):
    reason: str = Field(default="owner_rejected", min_length=1, max_length=80)


def _raise(exc: Exception) -> None:
    if isinstance(exc, lite_owner_operations.OwnerOperationError):
        raise HTTPException(
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": exc.reason_code, "message": exc.message, "sanitized": True},
        ) from exc
    raise exc


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post("/client-pairings/challenge")
def issue_client_pairing_challenge(
    payload: ClientPairingChallengeRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.issue_client_pairing_challenge(
            client_id=payload.client_id,
            display_name=payload.display_name,
            public_key=payload.public_key,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/client-pairings", status_code=201)
def request_client_pairing(
    payload: ClientPairingRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.request_client_pairing(
            client_id=payload.client_id,
            display_name=payload.display_name,
            public_key=payload.public_key,
            challenge_id=payload.challenge_id,
            signature=payload.signature,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/client-pairings/observer-challenge")
def issue_client_pairing_observer_challenge(
    payload: PairingObserverChallengeRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.issue_client_pairing_observer_challenge(
            client_id=payload.client_id,
            pairing_id=payload.pairing_id,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/client-pairings/cancel-challenge")
def issue_client_pairing_cancel_challenge(
    payload: PairingCancelChallengeRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.issue_client_pairing_cancel_challenge(
            client_id=payload.client_id,
            pairing_id=payload.pairing_id,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/client-pairings/{pairing_id}/cancel")
def cancel_client_pairing(
    pairing_id: str,
    payload: SignedPairingRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.cancel_client_pairing(
            client_id=payload.client_id,
            pairing_id=pairing_id,
            challenge_id=payload.challenge_id,
            signature=payload.signature,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.get("/client-pairings/{pairing_id}")
def observe_client_pairing(
    pairing_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    client_id = request.headers.get("X-Pocket-Lab-Client-ID", "").strip()
    challenge_id = request.headers.get("X-Pocket-Lab-Client-Challenge", "").strip()
    signature = request.headers.get("X-Pocket-Lab-Client-Signature", "").strip()
    try:
        if not (client_id and challenge_id and signature):
            raise lite_owner_operations.OwnerOperationError("observer_proof_required", "A complete requester proof is required.", 401)
        result = lite_owner_operations.observe_client_pairing(
            client_id=client_id,
            pairing_id=pairing_id,
            challenge_id=challenge_id,
            signature=signature,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/clients/challenge")
def issue_owner_operation_client_challenge(
    payload: ClientChallengeRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        auth = deps.require_auth(request, write=True)
        result = lite_owner_operations.issue_registration_challenge(
            auth,
            client_id=payload.client_id,
            public_key=payload.public_key,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/clients", status_code=201)
def register_owner_operation_client(
    payload: ClientRegistrationRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        auth = deps.require_auth(request, write=True)
        result = lite_owner_operations.register_client(
            auth,
            client_id=payload.client_id,
            display_name=payload.display_name,
            public_key=payload.public_key,
            challenge_id=payload.challenge_id,
            signature=payload.signature,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/clients/pairings/{pairing_id}/approve")
def approve_client_pairing(
    pairing_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        auth = deps.require_auth(request, write=True)
        target = lite_owner_operations.client_pairing_policy_target(pairing_id)
        try:
            lite_policy_opa.evaluate_authorization(
                auth_context=auth,
                action_id="owner.operations.client.register",
                target_type=target["type"],
                target_id=target["id"],
                target_revision=target["revision"],
                target=target["state"],
                request_context={"source": "identity_access", "pairing_id": pairing_id, "decision": "register"},
                correlation_id=pairing_id,
            )
        except lite_policy_opa.PolicyDecisionError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                headers={"Cache-Control": "no-store"},
                detail={"reason_code": exc.reason_code, "message": exc.message, "sanitized": True},
            ) from exc
        result = lite_owner_operations.approve_client_pairing(auth, pairing_id)
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/clients/pairings/{pairing_id}/reject")
def reject_client_pairing(
    pairing_id: str,
    payload: ClientPairingDecisionRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.reject_client_pairing(
            deps.require_auth(request, write=True),
            pairing_id,
            reason=payload.reason,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/clients/{client_id}/revoke")
def revoke_owner_operation_client(
    client_id: str,
    payload: ClientRevokeRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        auth = deps.require_auth(request, write=True)
        target = lite_owner_operations.client_policy_target(client_id)
        try:
            lite_policy_opa.evaluate_authorization(
                auth_context=auth,
                action_id="owner.operations.client.register",
                target_type=target["type"],
                target_id=target["id"],
                target_revision=target["revision"],
                target=target["state"],
                request_context={"source": "identity_access", "client_id": client_id, "decision": "revoke"},
                correlation_id=f"client:{client_id}",
            )
        except lite_policy_opa.PolicyDecisionError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                headers={"Cache-Control": "no-store"},
                detail={"reason_code": exc.reason_code, "message": exc.message, "sanitized": True},
            ) from exc
        result = lite_owner_operations.revoke_client(auth, client_id=client_id, reason=payload.reason)
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/request-challenge")
def issue_owner_operation_request_challenge(
    payload: RequestChallengeRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.issue_request_challenge(
            client_id=payload.client_id,
            descriptor=payload.descriptor,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/requests", status_code=201)
def submit_owner_operation_request(
    payload: SignedOperationRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.request_operation(
            client_id=payload.client_id,
            descriptor=payload.descriptor,
            challenge_id=payload.challenge_id,
            signature=payload.signature,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/observer-challenge")
def issue_owner_operation_observer_challenge(
    payload: ObserverChallengeRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.issue_observer_challenge(
            client_id=payload.client_id,
            operation_id=payload.operation_id,
            purpose=payload.purpose,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/pending/{operation_id}/approve")
async def approve_owner_operation(
    operation_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        auth = deps.require_auth(request, write=True)
        target = lite_owner_operations.approval_policy_target(operation_id)
        try:
            lite_policy_opa.evaluate_authorization(
                auth_context=auth,
                action_id="owner.operations.approve",
                target_type=target["type"],
                target_id=target["id"],
                target_revision=target["revision"],
                target=target["state"],
                request_context={"source": "identity_access", "operation_id": operation_id},
                correlation_id=operation_id,
            )
        except lite_policy_opa.PolicyDecisionError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                headers={"Cache-Control": "no-store"},
                detail={"reason_code": exc.reason_code, "message": exc.message, "sanitized": True},
            ) from exc
        lite_owner_operations.approve_operation(auth, operation_id)
        await lite_owner_operations.dispatch_approved_operation(operation_id)
        result = lite_owner_operations.owner_operation(operation_id)
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/pending/{operation_id}/reject")
def reject_owner_operation(
    operation_id: str,
    payload: RejectOperationRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.reject_operation(
            deps.require_auth(request, write=True),
            operation_id,
            reason=payload.reason,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.get("/pending")
def owner_operation_pending(request: Request, response: Response) -> dict[str, Any]:
    try:
        result = lite_owner_operations.owner_projection(deps.require_auth(request, write=False))
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.post("/{operation_id}/cancel")
def cancel_owner_operation(
    operation_id: str,
    payload: SignedObserverRequest,
    response: Response,
) -> dict[str, Any]:
    try:
        result = lite_owner_operations.cancel_operation(
            client_id=payload.client_id,
            operation_id=operation_id,
            challenge_id=payload.challenge_id,
            signature=payload.signature,
        )
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result


@router.get("/{operation_id}")
def get_owner_operation(
    operation_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    client_id = request.headers.get("X-Pocket-Lab-Client-ID", "").strip()
    challenge_id = request.headers.get("X-Pocket-Lab-Client-Challenge", "").strip()
    signature = request.headers.get("X-Pocket-Lab-Client-Signature", "").strip()
    try:
        if client_id or challenge_id or signature:
            if not (client_id and challenge_id and signature):
                raise lite_owner_operations.OwnerOperationError("observer_proof_required", "A complete registered-client proof is required.", 401)
            result = lite_owner_operations.observe_operation(
                client_id=client_id,
                operation_id=operation_id,
                challenge_id=challenge_id,
                signature=signature,
            )
        else:
            auth = deps.require_auth(request, write=False)
            lite_owner_operations.require_owner_read(auth)
            result = lite_owner_operations.owner_operation(operation_id)
    except Exception as exc:
        _raise(exc)
    _no_store(response)
    return result
