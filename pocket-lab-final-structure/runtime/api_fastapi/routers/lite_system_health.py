"""System Health API: authenticated, persisted reads, no browser-side execution."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import deps
from ..services import lite_policy_approvals, lite_policy_opa, lite_system_health as health
from ..services import lite_harness

router = APIRouter(prefix="/api/lite/system-health", tags=["lite-system-health"])


def _require_authenticated(request: Request, *, write: bool = False):
    # The generic Lite dependency permits anonymous *read* access to
    # non-sensitive public status. Canonical incidents/device identities and
    # diagnostic decisions require an authenticated session or service actor.
    context = deps.require_auth(request, write=write)
    if not (context.get("session") or {}).get("authenticated"):
        raise HTTPException(401, detail={"reason_code": "authentication_required",
                                         "message": "Sign in to review System Health."})
    return context



class RepairRequest(BaseModel):
    model_config = {"extra": "forbid"}
    operation_id: str = Field(min_length=1, max_length=80)
    expected_generation: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=128)
    confirm: bool = False


@router.get("/summary")
def system_health_summary(request: Request):
    _require_authenticated(request)
    return health.summary()


@router.get("/incidents")
def system_health_incidents(request: Request, include_resolved: bool = False,
                            limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000)):
    _require_authenticated(request)
    return health.incidents(include_resolved=include_resolved, limit=limit, offset=offset)


@router.get("/incidents/{incident_id}")
def system_health_incident(incident_id: str, request: Request):
    _require_authenticated(request)
    item = health.incident(incident_id)
    if item is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    return item


@router.get("/history")
def system_health_history(request: Request, limit: int = Query(30, ge=1, le=100),
                          offset: int = Query(0, ge=0, le=10000)):
    _require_authenticated(request)
    return health.history(limit, offset)


@router.get("/dependencies")
def system_health_dependencies(request: Request):
    _require_authenticated(request)
    return health.dependency_graph()


@router.get("/resources")
def system_health_resources(request: Request):
    _require_authenticated(request)
    return health.resource_intelligence()


@router.get("/infrastructure")
def system_health_infrastructure(request: Request):
    _require_authenticated(request)
    from ..services import lite_infrastructure_read_model as infrastructure
    return infrastructure.infrastructure()


@router.get("/intelligence")
def system_health_intelligence(request: Request):
    _require_authenticated(request)
    return health.knowledge()


@router.get("/configuration-drift")
def system_health_configuration_drift(request: Request):
    _require_authenticated(request)
    return health.configuration_drift()


@router.get("/apps/{app_id}")
def system_health_app_diagnostics(app_id: str, request: Request):
    _require_authenticated(request)
    result = health.app_diagnostics(app_id)
    if result is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "App diagnostic contract is unavailable."})
    return result


@router.get("/policies")
def system_health_policies(request: Request):
    _require_authenticated(request)
    return health.policy()


@router.get("/repairs")
def system_health_repairs(request: Request):
    _require_authenticated(request)
    current = health.policy()
    return {
        "operations": current["repair_catalog"],
        "new_executor_enabled": False,
        "controlled_recovery_adapter": current["controlled_recovery_adapter"],
    }


@router.post("/incidents/{incident_id}/diagnose")
def system_health_diagnose(incident_id: str, request: Request):
    # State-changing audit of diagnosis is explicitly authenticated.
    _require_authenticated(request, write=True)
    found = health.incident(incident_id)
    if found is not None and not found["current_monitoring"]:
        raise HTTPException(409, detail={"reason_code": "historical_record", "summary": "Review earlier evidence; this device is no longer monitored."})
    result = health.record_diagnosis(incident_id)
    if result is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    return result


@router.get("/incidents/{incident_id}/decisions")
def system_health_decisions(incident_id: str, request: Request, limit: int = Query(20, ge=1, le=50)):
    _require_authenticated(request)
    if health.incident(incident_id) is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    return health.decision_history(incident_id, limit=limit)


@router.post("/incidents/{incident_id}/preflight")
def system_health_preflight(incident_id: str, payload: RepairRequest, request: Request):
    _require_authenticated(request, write=True)
    result = health.repair_preflight(incident_id, payload.operation_id, payload.expected_generation)
    if result is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    return result


@router.post("/incidents/{incident_id}/repair", status_code=202)
def system_health_repair(incident_id: str, payload: RepairRequest, request: Request):
    context = _require_authenticated(request, write=True)
    found = health.incident(incident_id)
    if found is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    replay = health.recovery_request_replay(
        incident_id, payload.operation_id, payload.expected_generation, payload.idempotency_key,
        confirm=payload.confirm, auth_context=context,
    )
    if replay is not None:
        if replay.get("reasons"):
            raise HTTPException(409, detail={"status": "blocked", "reason_code": replay["reasons"][0], "summary": "The idempotency key is bound to a different recovery request."})
        return {"status": "admitted", "request": replay.get("request"), "summary": "The existing durable recovery request was returned.", "idempotent_replay": True}
    if found["generation"] != payload.expected_generation:
        raise HTTPException(409, detail={"status": "blocked", "reason_code": "incident_generation_changed", "summary": "Status changed. Diagnose again before attempting repair."})
    preflight = health.repair_preflight(incident_id, payload.operation_id, payload.expected_generation)
    if preflight is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    if not preflight["allowed"]:
        result = health.record_repair_denial(
            incident_id, payload.operation_id, payload.expected_generation,
            payload.idempotency_key,
            str(((context or {}).get("actor") or {}).get("type") or "unknown"),
        )
        raise HTTPException(
            409,
            detail={
                "status": "blocked", "reason_code": (result or {}).get("reasons", preflight["reasons"])[0],
                "summary": "Recovery is not enabled for this candidate or the evidence is no longer eligible.",
                "recorded": bool((result or {}).get("recorded")),
            },
        )
    try:
        lite_harness.enforce_capability(
            context,
            action_id="system_health.recovery",
            target_type="system_health_incident",
            target_id=incident_id,
            destructive=False,
            operation_id=payload.operation_id,
        )
        decision = lite_policy_opa.evaluate_authorization(
            auth_context=context,
            action_id="system_health.recovery",
            target_type="system_health_incident",
            target_id=incident_id,
            target_revision=f"{incident_id}:{payload.expected_generation}:{int(found.get('enrollment_generation') or 0)}",
            target={
                "scope": "local_server_host_only",
                # `evaluate_authorization` wraps this target under the
                # canonical OPA `target.state` field.  Keep the supplied
                # state flat here so the policy sees the exact operation,
                # generation and preflight facts instead of a nested
                # target.state.state shape.
                "operation_id": payload.operation_id,
                "adapter_enabled": True,
                "preflight_valid": True,
                "incident_generation": int(payload.expected_generation),
                "enrollment_generation": int(found.get("enrollment_generation") or 0),
                "confirmed": bool(payload.confirm),
            },
            request_context={"confirmation_present": bool(payload.confirm), "idempotency_key_present": True},
        )
    except lite_harness.HarnessError as exc:
        raise HTTPException(exc.status_code, detail={"status": "denied", "reason_code": exc.reason_code, "summary": exc.message}) from exc
    except lite_policy_opa.PolicyDecisionError as exc:
        decision = exc.decision or {"allow": False, "reason_code": exc.reason_code}
        if exc.reason_code not in {"approval_required"}:
            raise HTTPException(exc.status_code, detail={"status": "denied", "reason_code": exc.reason_code, "summary": exc.message}) from exc
    continuation_id = decision.get("continuation_approval_id") if decision.get("allow") else None
    if continuation_id:
        try:
            lite_policy_approvals.consume_matching(
                auth_context=context,
                approval_id=str(continuation_id),
                action_id="system_health.recovery",
                target_type="system_health_incident",
                target_id=incident_id,
                target_revision=f"{incident_id}:{payload.expected_generation}:{int(found.get('enrollment_generation') or 0)}",
                policy_revision=str(decision.get("policy_revision") or ""),
                request_fingerprint=f"{incident_id}:{payload.expected_generation}:{int(found.get('enrollment_generation') or 0)}",
            )
        except lite_policy_approvals.ApprovalError as exc:
            raise HTTPException(exc.status_code, detail={"status": "blocked", "reason_code": exc.reason_code, "summary": exc.message}) from exc
    result = health.admit_controlled_recovery(
        incident_id, payload.operation_id, payload.expected_generation, payload.idempotency_key,
        confirm=payload.confirm, auth_context=context, decision=decision,
    )
    if result is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    if result.get("reasons"):
        raise HTTPException(409, detail={"status": "blocked", "reason_code": result["reasons"][0], "summary": "The recovery request was blocked before execution."})
    if decision.get("reason_code") == "approval_required":
        raise HTTPException(409, detail={"status": "approval_required", "request": result.get("request"), "summary": "Independent Enterprise approval is required before recovery can be admitted."})
    return {"status": "admitted", "request": result.get("request"), "summary": "Recovery was admitted to the existing worker recovery owner."}
