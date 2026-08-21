from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..services import lite_policy_lifecycle, lite_policy_analysis, lite_policy_opa, lite_policy_approvals

router = APIRouter(prefix="/api/lite/enterprise/rules", tags=["lite-enterprise-rules"])


class RevisionRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=48)
    parameters: dict[str, Any] = Field(default_factory=dict)
    change_summary: str = Field(min_length=1, max_length=240)


class ActivationRequest(BaseModel):
    revision_id: str = Field(min_length=1, max_length=80)


class SimulationRequest(BaseModel):
    revision_id: str = Field(min_length=1, max_length=80)
    action_id: str = Field(min_length=1, max_length=120)
    target_id: str = Field(min_length=1, max_length=160)
    mode: str = Field(default="real_derived", max_length=20)
    scenario: dict[str, bool] | None = None


class ApprovalTransitionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=12)


class TemporaryExceptionRequest(BaseModel):
    app_id: str = Field(min_length=1, max_length=160)
    device_id: str = Field(min_length=1, max_length=160)
    human_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=240)
    duration_minutes: int = Field(ge=1, le=60)


def _call(response: Response, callback: Any) -> Any:
    try:
        result = callback()
    except (lite_policy_lifecycle.PolicyLifecycleError, lite_policy_analysis.PolicyAnalysisError, lite_policy_approvals.ApprovalError) as exc:
        raise HTTPException(status_code=exc.status_code, headers={"Cache-Control": "no-store"}, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/revisions")
def revisions(request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_lifecycle.list_revisions(auth_context=deps.require_auth(request, write=False)))


@router.post("/revisions", status_code=201)
def create_revision(payload: RevisionRequest, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_lifecycle.create_revision(auth_context=deps.require_auth(request, write=True), template_id=payload.template_id, parameters=payload.parameters, change_summary=payload.change_summary))


@router.get("/revisions/{revision_id}")
def revision(revision_id: str, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_lifecycle.read_revision(auth_context=deps.require_auth(request, write=False), revision_id=revision_id))


@router.get("/revisions/{left_revision_id}/compare/{right_revision_id}")
def compare(left_revision_id: str, right_revision_id: str, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_lifecycle.compare_revisions(
        auth_context=deps.require_auth(request, write=False),
        left_revision_id=left_revision_id,
        right_revision_id=right_revision_id,
    ))


@router.post("/activations", status_code=202)
def activate(payload: ActivationRequest, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_lifecycle.request_activation(auth_context=deps.require_auth(request, write=True), revision_id=payload.revision_id, correlation_id=uuid.uuid4().hex))


@router.post("/rollbacks", status_code=202)
def rollback(request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_lifecycle.request_rollback(auth_context=deps.require_auth(request, write=True), correlation_id=uuid.uuid4().hex))


@router.get("/activations/{operation_id}")
def operation(operation_id: str, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_lifecycle.read_operation(auth_context=deps.require_auth(request, write=False), operation_id=operation_id))


@router.get("/health")
def health(request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_analysis.health(auth_context=deps.require_auth(request, write=False)))


@router.get("/approvals")
def approvals(request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_approvals.list_approvals(auth_context=deps.require_auth(request, write=False)))


@router.get("/approvals/{approval_id}")
def approval(approval_id: str, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_approvals.read_approval(auth_context=deps.require_auth(request, write=False), approval_id=approval_id))


@router.post("/approvals/{approval_id}")
def transition_approval(approval_id: str, payload: ApprovalTransitionRequest, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_approvals.transition(auth_context=deps.require_auth(request, write=True), approval_id=approval_id, action=payload.action))


@router.get("/exceptions")
def exceptions(request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_approvals.list_exceptions(auth_context=deps.require_auth(request, write=False)))


@router.post("/exceptions", status_code=201)
def create_exception(payload: TemporaryExceptionRequest, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_approvals.create_exception(
        auth_context=deps.require_auth(request, write=True), app_id=payload.app_id, device_id=payload.device_id,
        human_id=payload.human_id, reason=payload.reason, duration_minutes=payload.duration_minutes,
    ))


@router.post("/exceptions/{exception_id}/revoke")
def revoke_exception(exception_id: str, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_approvals.revoke_exception(auth_context=deps.require_auth(request, write=True), exception_id=exception_id))


@router.post("/simulations")
def simulate(payload: SimulationRequest, request: Request, response: Response) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_analysis.simulate(auth_context=deps.require_auth(request, write=False), revision_id=payload.revision_id, action_id=payload.action_id, target_id=payload.target_id, mode=payload.mode, scenario=payload.scenario))


@router.get("/analysis")
def analysis(request: Request, response: Response, revision_id: str | None = None) -> dict[str, Any]:
    return _call(response, lambda: lite_policy_analysis.analyze(auth_context=deps.require_auth(request, write=False), revision_id=revision_id))


@router.get("/decisions")
def decisions(request: Request, response: Response, action_id: str = "", allowed: bool | None = None, reason_code: str = "", policy_revision: str = "", target_type: str = "", limit: int = 50, cursor: int | None = None) -> dict[str, Any]:
    def _list() -> dict[str, Any]:
        lite_policy_analysis._authorize(deps.require_auth(request, write=False), frozenset({"Owner", "Admin", "Operator", "Auditor"}))
        return lite_policy_opa.list_decisions(action_id=action_id, allowed=allowed, reason_code=reason_code, policy_revision=policy_revision, target_type=target_type, limit=limit, cursor=cursor)
    return _call(response, _list)


@router.get("/decisions/{decision_id}")
def decision(decision_id: str, request: Request, response: Response) -> dict[str, Any]:
    def _read() -> dict[str, Any]:
        lite_policy_analysis._authorize(deps.require_auth(request, write=False), frozenset({"Owner", "Admin", "Operator", "Auditor"}))
        result = lite_policy_opa.decision_detail(decision_id)
        if not result:
            raise lite_policy_analysis.PolicyAnalysisError("policy_decision_not_found", "That Safety Rules decision is no longer available.", status_code=404)
        return result
    return _call(response, _read)
