from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import deps

router = APIRouter(tags=["observability"])


@router.get(
    "/api/observability/status",
    status_code=410,
    response_model=None,
    responses={410: {"description": "Legacy observability route retired."}},
)
def observability_status(request: Request) -> dict:
    """Retain a deterministic compatibility response for the retired route."""
    deps.require_auth(request)
    raise HTTPException(
        status_code=410,
        detail={
            "status": "retired",
            "accepted": False,
            "executed": False,
            "reason_code": "legacy_observability_stack_retired",
            "replacement": "/api/lite/system/health and /api/lite/diagnostics/runtime",
            "historical_record_preserved": True,
            "sanitized": True,
        },
    )
