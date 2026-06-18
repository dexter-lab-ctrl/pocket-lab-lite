from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from .. import deps
from ..schemas.operations import OperationRequest
from ..services.nats_bus import BUS
from ..services.action_queue import submit_operation_command, submit_domain_command

router = APIRouter(tags=["operations"])


@router.get("/api/operations")
def operations(request: Request) -> dict:
    deps.require_auth(request)
    return {"operations": list(deps.operation_service().registry.operations.keys())}


@router.get("/api/operations/runs")
def operation_runs(request: Request) -> dict:
    deps.require_auth(request)
    return {"runs": deps.operation_service().list(limit=50)}


@router.get("/api/operations/health")
def operation_health(request: Request) -> dict:
    deps.require_auth(request)
    return {"status": "ok", "tasks": list(deps.operation_service().tasks.tasks.keys())}


@router.get("/api/operations/{job_id}/status")
def operation_status(job_id: str, request: Request) -> dict:
    deps.require_auth(request)
    return deps.status_response(job_id)


@router.get("/api/operations/{job_id}")
def operation_job(job_id: str, request: Request) -> dict:
    deps.require_auth(request)
    return deps.job_response(job_id)


@router.post("/api/operations/execute", status_code=202)
async def execute_operation(
    payload: OperationRequest | Dict[str, Any],
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict:
    deps.require_auth(request, write=True)
    raw = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    op_request = deps.normalize_operation_request(raw)
    if not op_request.operation:
        raise HTTPException(status_code=400, detail="Missing operation")

    # Phase 6: route domain-shaped operations through explicit command handlers
    # so tabs receive meaningful fleet/drift/vault events instead of only generic
    # operation events. Generic GitOps/blueprint/backup operations still use the
    # canonical operation worker path.
    params_value = raw.get("params") or {}
    params = dict(params_value) if isinstance(params_value, dict) else {}

    target_value = raw.get("target") or {}
    if isinstance(target_value, dict):
        target = dict(target_value)
    elif isinstance(target_value, str):
        target = {"name": target_value}
    else:
        target = {}
    if op_request.operation == "fleet_join":
        return await submit_domain_command(
            "pocketlab.commands.fleet.join",
            "fleet.join.requested",
            {
                "role": params.get("role") or target.get("ref") or "compute",
                "hostname": params.get("hostname"),
            },
        )
    if op_request.operation == "drift_scan":
        return await submit_domain_command(
            "pocketlab.commands.drift.scan",
            "drift.scan.requested",
            {
                "scope": params.get("scope") or "all",
                "ref": target.get("ref") or "workspace",
                "action": "scan",
            },
        )
    if op_request.operation == "rotate_secret":
        return await submit_domain_command(
            "pocketlab.commands.vault.rotate",
            "vault.rotate.requested",
            {
                "target": params.get("target") or target.get("ref") or "secret",
                "lease_duration": params.get("lease_duration") or params.get("ttl"),
                "value": params.get("value"),
            },
        )
    if op_request.operation == "secret_read_dynamic":
        return await submit_domain_command(
            "pocketlab.commands.vault.dynamic_secret",
            "vault.dynamic_secret.requested",
            {"target": params.get("target") or target.get("ref") or "default"},
        )
    return await submit_operation_command(op_request, raw)


@router.post("/api/operations/preview")
def preview_operation(
    payload: OperationRequest | Dict[str, Any],
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict:
    deps.require_auth(request, write=True)
    raw = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    op_request = deps.normalize_operation_request(raw)
    preview = deps.operation_service().preview(op_request)
    background_tasks.add_task(
        BUS.publish_json,
        "pocketlab.events.operation.previewed",
        "operation.previewed",
        {
            "operation": preview.get("operation"),
            "task_id": preview.get("task_id"),
            "target": preview.get("target"),
            "estimated_effect": preview.get("estimated_effect"),
        },
    )
    return preview
