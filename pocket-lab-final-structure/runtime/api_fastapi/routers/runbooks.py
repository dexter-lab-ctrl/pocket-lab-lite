from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import deps
from ..services.action_queue import (
    submit_runbook_command,
    submit_runbook_approval,
    submit_runbook_rejection,
)
from ..services.runbook_commands import runbook_registry, runbook_store

router = APIRouter(tags=["runbooks"])


class RunbookExecuteRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    approved: bool = False
    approved_by: str | None = None
    reason: str | None = None
    requested_by: str | None = None


class RunbookApprovalRequest(BaseModel):
    approved_by: str | None = None
    approval_role: str | None = None
    reason: str | None = None


class RunbookRejectionRequest(BaseModel):
    rejected_by: str | None = None
    reason: str | None = None


@router.get("/api/runbooks")
def list_runbooks(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return {"runbooks": [runbook.as_public_dict() for runbook in runbook_registry().list()]}


@router.get("/api/runbooks/executions")
def list_runbook_executions(request: Request, limit: int = 50) -> dict[str, Any]:
    deps.require_auth(request)
    return {"executions": runbook_store().list(limit=limit)}


@router.get("/api/runbooks/executions/{execution_id}")
def get_runbook_execution(execution_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    execution = runbook_store().get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Runbook execution not found: {execution_id}")
    return execution


@router.get("/api/runbooks/{name}")
def get_runbook(name: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    runbook = runbook_registry().get(name)
    if runbook is None:
        raise HTTPException(status_code=404, detail=f"Runbook not found: {name}")
    return runbook.as_public_dict()


@router.post("/api/runbooks/{name}/execute", status_code=202)
async def execute_runbook(
    name: str,
    payload: RunbookExecuteRequest,
    request: Request,
) -> dict[str, Any]:
    deps.require_auth(request, write=True)

    runbook = runbook_registry().get(name)
    if runbook is None:
        raise HTTPException(status_code=404, detail=f"Runbook not found: {name}")

    execution_id = uuid.uuid4().hex
    requested_by = payload.requested_by or "api"

    raw = {
        "execution_id": execution_id,
        "runbook": runbook.name,
        "params": payload.params,
        "dry_run": payload.dry_run,
        "approved": payload.approved,
        "approved_by": payload.approved_by,
        "reason": payload.reason,
        "requested_by": requested_by,
    }

    return await submit_runbook_command(raw)



@router.post("/api/runbooks/executions/{execution_id}/approve", status_code=202)
async def approve_runbook_execution(
    execution_id: str,
    payload: RunbookApprovalRequest,
    request: Request,
) -> dict[str, Any]:
    """Approve a pending runbook execution and queue worker-owned resume."""
    deps.require_auth(request, write=True)
    raw = {
        "execution_id": execution_id,
        "approved_by": payload.approved_by,
        "approval_role": payload.approval_role or "operator",
        "reason": payload.reason,
    }
    return await submit_runbook_approval(raw)


@router.post("/api/runbooks/executions/{execution_id}/reject", status_code=202)
async def reject_runbook_execution(
    execution_id: str,
    payload: RunbookRejectionRequest,
    request: Request,
) -> dict[str, Any]:
    """Reject a pending runbook execution and queue worker-owned failure update."""
    deps.require_auth(request, write=True)
    raw = {
        "execution_id": execution_id,
        "rejected_by": payload.rejected_by,
        "reason": payload.reason,
    }
    return await submit_runbook_rejection(raw)
