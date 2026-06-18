from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from .. import deps
from ..schemas.common import TargetsRequest
from ..services.action_queue import submit_domain_command

router = APIRouter(tags=["drift"])


@router.get("/api/drift/summary")
def drift_summary(request: Request) -> dict:
    deps.require_auth(request)
    return deps.core.load_drift_state().get("summary", {})


@router.get("/api/drift/metrics")
def drift_metrics(request: Request) -> dict:
    deps.require_auth(request)
    return deps.core.load_drift_state().get("metrics", {})


@router.get("/api/drift/jobs")
def drift_jobs(request: Request) -> list[dict]:
    deps.require_auth(request)
    return deps.core.load_drift_state().get("jobs", [])


@router.get("/api/drift/jobs/{job_id}")
def drift_job(job_id: str, request: Request) -> dict:
    deps.require_auth(request)
    job = next(
        (
            item
            for item in deps.core.load_drift_state().get("jobs", [])
            if str(item.get("job_id")) == job_id
        ),
        None,
    )
    if not job:
        raise HTTPException(status_code=404, detail=f"Drift job not found: {job_id}")
    return job


@router.get("/api/drift/jobs/{job_id}/diff")
def drift_job_diff(job_id: str, request: Request) -> dict:
    deps.require_auth(request)
    job = next(
        (
            item
            for item in deps.core.load_drift_state().get("jobs", [])
            if str(item.get("job_id")) == job_id
        ),
        None,
    )
    if not job:
        raise HTTPException(status_code=404, detail=f"Drift job not found: {job_id}")
    return {"job_id": job_id, "diff": job.get("diff", [])}


def _selected(payload: TargetsRequest | dict | None) -> set[str]:
    value = []
    if isinstance(payload, TargetsRequest):
        value = payload.targets or []
    elif isinstance(payload, dict):
        value = payload.get("targets") or []
    if isinstance(value, str):
        value = [value]
    return {str(v).lower() for v in value}


@router.post("/api/drift/{action}", status_code=202)
async def drift_action(
    action: str,
    background_tasks: BackgroundTasks,
    payload: TargetsRequest | None = None,
    request: Request = None,
) -> dict:
    deps.require_auth(request, write=True)
    selected = list(_selected(payload))

    if action in {"scan", "rescan"}:
        return await submit_domain_command(
            f"pocketlab.commands.drift.{action}",
            f"drift.{action}.requested",
            {"action": action, "scope": "all", "ref": "workspace"},
        )

    if action == "preview":
        return await submit_domain_command(
            "pocketlab.commands.drift.preview",
            "drift.preview.requested",
            {"action": action, "targets": selected},
        )

    if action in {"approve", "apply", "ignore"}:
        return await submit_domain_command(
            f"pocketlab.commands.drift.{action}",
            f"drift.{action}.requested",
            {"action": action, "targets": selected},
        )
    raise HTTPException(status_code=404, detail="Not found")
