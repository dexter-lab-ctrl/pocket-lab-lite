"""System Health API: authenticated, persisted reads, no browser-side execution."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import deps
from ..services import lite_system_health as health

router = APIRouter(prefix="/api/lite/system-health", tags=["lite-system-health"])


class RepairRequest(BaseModel):
    model_config = {"extra": "forbid"}
    operation_id: str = Field(min_length=1, max_length=80)
    expected_generation: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=128)
    confirm: bool = False


@router.get("/summary")
def system_health_summary(request: Request):
    deps.require_auth(request)
    return health.summary()


@router.get("/incidents")
def system_health_incidents(request: Request, include_resolved: bool = False,
                            limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000)):
    deps.require_auth(request)
    return health.incidents(include_resolved=include_resolved, limit=limit, offset=offset)


@router.get("/incidents/{incident_id}")
def system_health_incident(incident_id: str, request: Request):
    deps.require_auth(request)
    item = health.incident(incident_id)
    if item is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    return item


@router.get("/history")
def system_health_history(request: Request, limit: int = Query(30, ge=1, le=100),
                          offset: int = Query(0, ge=0, le=10000)):
    deps.require_auth(request)
    return health.history(limit, offset)


@router.get("/dependencies")
def system_health_dependencies(request: Request):
    deps.require_auth(request)
    return health.dependency_graph()


@router.get("/resources")
def system_health_resources(request: Request):
    deps.require_auth(request)
    return health.resource_intelligence()


@router.get("/intelligence")
def system_health_intelligence(request: Request):
    deps.require_auth(request)
    return health.knowledge()


@router.get("/policies")
def system_health_policies(request: Request):
    deps.require_auth(request)
    return health.policy()


@router.get("/repairs")
def system_health_repairs(request: Request):
    deps.require_auth(request)
    return {"operations": health.policy()["repair_catalog"], "new_executor_enabled": False}


@router.post("/incidents/{incident_id}/diagnose")
def system_health_diagnose(incident_id: str, request: Request):
    # POST is deliberately protected even though the operation is read-only.
    deps.require_auth(request, write=True)
    result = health.diagnose(incident_id)
    if result is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    return result


@router.post("/incidents/{incident_id}/repair", status_code=409)
def system_health_repair(incident_id: str, payload: RepairRequest, request: Request):
    deps.require_auth(request, write=True)
    # Fail closed: do not invent an executor or bypass existing OPA/app authority,
    # supervisor ownership, idempotency or verified recovery criteria.
    found = health.incident(incident_id)
    if found is None:
        raise HTTPException(404, detail={"status": "not_found", "summary": "This problem was not found."})
    if found["generation"] != payload.expected_generation:
        raise HTTPException(409, detail={"status": "blocked", "reason_code": "incident_generation_changed", "summary": "Status changed. Diagnose again before attempting repair."})
    raise HTTPException(409, detail={"status": "blocked", "reason_code": "repair_not_qualified",
                                    "summary": "No new System Health repair executor is enabled. Use the existing protected repair workflow."})
