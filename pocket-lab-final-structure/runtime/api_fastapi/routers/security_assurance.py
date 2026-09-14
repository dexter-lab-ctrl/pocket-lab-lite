from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from .. import deps
from ..services import lite_harness
from ..services import lite_assurance_faults
from ..services import lite_policy_source_sync
from ..services import lite_security_assurance as assurance
from ..services.action_queue import submit_domain_command


router = APIRouter(
    prefix="/api/lite/harness/security-assurance",
    tags=["lite-security-assurance"],
)

RUN_ID_PATTERN = r"^assurance-[0-9a-f]{32}$"
SCENARIO_PATTERN = r"^[A-Za-z][A-Za-z0-9._-]{0,79}$"


class AssuranceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9._-]{0,79}$")
    scenario_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=SCENARIO_PATTERN)
    baseline_run_id: str | None = Field(default=None, min_length=42, max_length=42, pattern=RUN_ID_PATTERN)


class FaultControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(default=False)


class PolicySyncRequest(BaseModel):
    """The qualification policy-sync request intentionally has no inputs."""

    model_config = ConfigDict(extra="forbid")


def _direct(request: Request) -> None:
    if not lite_harness.is_direct_local_request(request):
        raise HTTPException(
            status_code=401,
            headers={"Cache-Control": "no-store"},
            detail={
                "reason_code": "harness_transport_rejected",
                "message": "Runtime assurance requires direct loopback transport.",
                "sanitized": True,
            },
        )


def _raise(exc: assurance.AssuranceError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": exc.reason_code,
            "message": exc.message,
            "sanitized": True,
        },
    ) from exc


def _raise_policy(exc: lite_policy_source_sync.PolicySourceSyncError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": exc.reason_code,
            "message": exc.message,
            "sanitized": True,
        },
    ) from exc


def _raise_fault(exc: lite_assurance_faults.FaultControlError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
        detail={
            "reason_code": exc.reason_code,
            "message": exc.message,
            "sanitized": True,
        },
    ) from exc


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _enforce_capability(auth: dict[str, Any], action_id: str) -> None:
    try:
        lite_harness.enforce_capability(
            auth,
            action_id=action_id,
            target_type="security_assurance",
            target_id="local-server",
        )
    except lite_harness.HarnessError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
            detail={
                "reason_code": exc.reason_code,
                "message": exc.message,
                "sanitized": True,
            },
        ) from exc


def _assurance_auth(request: Request, action_id: str, *, write: bool) -> dict[str, Any]:
    _direct(request)
    auth = deps.require_auth(request, write=write)
    harness = auth.get("harness") if isinstance(auth, dict) else None
    if not isinstance(harness, dict):
        raise HTTPException(
            status_code=403,
            headers={"Cache-Control": "no-store"},
            detail={
                "reason_code": "harness_session_required",
                "message": "Runtime assurance requires a signed synthetic harness session.",
                "sanitized": True,
            },
        )
    if (
        harness.get("profile") != assurance.ASSURANCE_PROFILE
        or harness.get("purpose") != assurance.ASSURANCE_PURPOSE
        or harness.get("target_scope") != assurance.ASSURANCE_TARGET_SCOPE
        or harness.get("principal_class") != "qualification"
        or not harness.get("qualification_environment")
    ):
        raise HTTPException(
            status_code=403,
            headers={"Cache-Control": "no-store"},
            detail={
                "reason_code": "assurance_session_binding_mismatch",
                "message": "The signed session is not bound to the runtime assurance profile.",
                "sanitized": True,
            },
        )
    _enforce_capability(auth, action_id)
    return auth


def _owned_run(run_id: str, auth: dict[str, Any]) -> dict[str, Any]:
    try:
        run = assurance.get_run(run_id)
    except assurance.AssuranceError as exc:
        _raise(exc)
    if not run:
        raise HTTPException(
            status_code=404,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "run_not_found", "message": "The assurance run was not found.", "sanitized": True},
        )
    harness = auth.get("harness") or {}
    if str(run.get("principal_id") or "") != str(harness.get("principal_id") or ""):
        raise HTTPException(
            status_code=404,
            headers={"Cache-Control": "no-store"},
            detail={"reason_code": "run_not_found", "message": "The assurance run was not found.", "sanitized": True},
        )
    return run


async def _publish_run(run: dict[str, Any], *, suite_id: str, scenario_id: str | None = None) -> dict[str, Any]:
    """Publish only the server-constructed assurance envelope."""
    command = {
        "run_id": run["run_id"],
        "command_id": run["run_id"],
        "trace_id": run["run_id"],
        "suite_id": suite_id,
        "scenario_id": scenario_id if scenario_id is not None else run.get("scenario_id"),
        "baseline_run_id": run.get("baseline_run_id"),
        "profile": assurance.ASSURANCE_PROFILE,
        "purpose": assurance.ASSURANCE_PURPOSE,
        "target_scope": assurance.ASSURANCE_TARGET_SCOPE,
        "runtime_id": run.get("runtime_id"),
        "revision_sha": run.get("revision_sha"),
        "principal_id": run.get("principal_id"),
        "session_id": run.get("harness_session_id"),
    }
    try:
        queued = await submit_domain_command(
            assurance.ASSURANCE_SUBJECT,
            "security.assurance.requested",
            command,
            trace_id=str(run["run_id"]),
        )
    except Exception:
        return assurance.record_blocked_run(
            str(run["run_id"]),
            failure_code="command_publish_failed",
            preflight_result=run.get("preflight") if isinstance(run.get("preflight"), dict) else {},
        )
    return {
        **run,
        "status": "QUEUED",
        "command_id": queued.get("command_id") or run["run_id"],
        "command_subject": assurance.ASSURANCE_SUBJECT,
        "execution_mode": "worker",
        "sanitized": True,
    }


@router.get("/capabilities")
def capabilities(request: Request, response: Response) -> dict[str, Any]:
    _direct(request)
    _no_store(response)
    return assurance.list_capabilities()


@router.get("/suites")
def suites(request: Request, response: Response) -> dict[str, Any]:
    _direct(request)
    _no_store(response)
    try:
        return assurance.list_suites()
    except assurance.AssuranceError as exc:
        _raise(exc)
    raise AssertionError("unreachable")


@router.get("/preflight")
async def preflight(
    request: Request,
    response: Response,
    suite_id: str = Query(default="smoke", min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9._-]{0,79}$"),
) -> dict[str, Any]:
    _assurance_auth(request, "security.assurance.read", write=False)
    _no_store(response)
    try:
        result = await asyncio.to_thread(assurance.preflight, suite_id)
    except assurance.AssuranceError as exc:
        _raise(exc)
    return result


@router.get("/policy-sync/status")
def policy_sync_status(request: Request, response: Response) -> dict[str, Any]:
    _assurance_auth(request, "security.assurance.read", write=False)
    _no_store(response)
    try:
        return {"source": lite_policy_source_sync.public_state(), "sanitized": True}
    except lite_policy_source_sync.PolicySourceSyncError as exc:
        _raise_policy(exc)
    raise AssertionError("unreachable")


@router.post("/policy-sync", status_code=status.HTTP_202_ACCEPTED)
def policy_sync(payload: PolicySyncRequest, request: Request, response: Response) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.policy_sync", write=True)
    _no_store(response)
    harness = auth.get("harness") or {}
    try:
        return lite_policy_source_sync.request_assurance_source_sync(
            auth_context=auth,
            correlation_id=str(harness.get("session_id") or "")[:100] or None,
        )
    except lite_policy_source_sync.PolicySourceSyncError as exc:
        _raise_policy(exc)
    raise AssertionError("unreachable")


@router.get("/faults")
def faults(request: Request, response: Response) -> dict[str, Any]:
    _direct(request)
    _no_store(response)
    try:
        return lite_assurance_faults.list_faults()
    except lite_assurance_faults.FaultControlError as exc:
        _raise_fault(exc)
    raise AssertionError("unreachable")


@router.post("/faults/{fault_id}", status_code=status.HTTP_202_ACCEPTED)
def execute_fault(
    fault_id: str,
    payload: FaultControlRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.fault_control", write=True)
    _no_store(response)
    try:
        return lite_assurance_faults.execute_fault(
            fault_id=fault_id,
            auth_context=auth,
            confirm=payload.confirm,
        )
    except lite_assurance_faults.FaultControlError as exc:
        _raise_fault(exc)
    raise AssertionError("unreachable")


@router.get("/runs")
def runs(
    request: Request,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.read", write=False)
    _no_store(response)
    principal_id = str((auth.get("harness") or {}).get("principal_id") or "")
    result = [
        item for item in assurance.list_runs(limit=100)
        if str(item.get("principal_id") or "") == principal_id
    ][:limit]
    return {"runs": result, "limit": limit, "sanitized": True}


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    payload: AssuranceRunRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.run", write=True)
    if payload.scenario_id:
        _enforce_capability(auth, "security.assurance.threat_scenario")
    if payload.baseline_run_id:
        _enforce_capability(auth, "security.assurance.baseline")
    _no_store(response)
    try:
        suite = assurance.suite_def(payload.suite_id)
        selected_scenarios = assurance._scenario_items_for_suite(suite, payload.scenario_id)
        canonical_scenario_id = str(selected_scenarios[0].get("id") or "") if payload.scenario_id else None
        preflight_result = await asyncio.to_thread(assurance.preflight, payload.suite_id)
        revision = str(preflight_result.get("revision") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise assurance.AssuranceError(
                "revision_unavailable",
                "The runtime revision could not be verified.",
                status_code=503,
            )
        harness = auth.get("harness") or {}
        baseline_id = payload.baseline_run_id
        if baseline_id:
            baseline = assurance.get_run(baseline_id)
            if (
                not baseline
                or str(baseline.get("suite_id") or "") != str(suite["id"])
                or str(baseline.get("status") or "").upper() not in {"PASS", "FAIL", "PARTIAL"}
                or str(baseline.get("principal_id") or "") != str(harness.get("principal_id") or "")
                or str(baseline.get("scenario_id") or "") != str(canonical_scenario_id or "")
            ):
                raise assurance.AssuranceError(
                    "baseline_invalid",
                    "The requested assurance baseline is not a compatible terminal run.",
                    status_code=400,
                )
        run = assurance.create_run(
            suite_id=str(suite["id"]),
            scenario_id=canonical_scenario_id,
            baseline_run_id=baseline_id,
            principal_id=str(harness.get("principal_id") or ""),
            session_id=str(harness.get("session_id") or ""),
            revision_sha=revision,
            preflight_result=preflight_result,
        )
        if run.get("idempotent_reuse"):
            return {
                **run,
                "command_subject": assurance.ASSURANCE_SUBJECT,
                "execution_mode": "worker",
                "sanitized": True,
            }
        if preflight_result.get("status") != "ready":
            return assurance.record_blocked_run(
                str(run["run_id"]),
                failure_code="preflight_blocked",
                preflight_result=preflight_result,
            )
        published = await _publish_run(
            run,
            suite_id=str(suite["id"]),
            scenario_id=canonical_scenario_id,
        )
        return {**published, "preflight": preflight_result, "sanitized": True}
    except assurance.AssuranceError as exc:
        _raise(exc)
    raise AssertionError("unreachable")


@router.get("/runs/{run_id}")
def run_status(run_id: str, request: Request, response: Response) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.read", write=False)
    _no_store(response)
    return _owned_run(run_id, auth)


@router.get("/runs/{run_id}/findings")
def findings(run_id: str, request: Request, response: Response) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.read", write=False)
    _no_store(response)
    _owned_run(run_id, auth)
    return {"run_id": run_id, "findings": assurance.list_findings(run_id), "sanitized": True}


@router.get("/runs/{run_id}/events")
def events(
    run_id: str,
    request: Request,
    response: Response,
    after: int = Query(default=0, ge=0, le=10_000_000),
) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.read", write=False)
    _no_store(response)
    _owned_run(run_id, auth)
    try:
        return assurance.run_events(run_id, after_sequence=after)
    except assurance.AssuranceError as exc:
        _raise(exc)
    raise AssertionError("unreachable")


@router.post("/runs/{run_id}/resume")
async def resume(run_id: str, request: Request, response: Response) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.run", write=True)
    _no_store(response)
    _owned_run(run_id, auth)
    try:
        resumed = assurance.resume_run(run_id)
        if resumed.get("resume_action") != "requeued":
            return {**resumed, "execution_mode": "worker", "sanitized": True}
        suite_id = str(resumed.get("suite_id") or "")
        scenario_id = str(resumed.get("scenario_id") or "") or None
        return await _publish_run(resumed, suite_id=suite_id, scenario_id=scenario_id)
    except assurance.AssuranceError as exc:
        _raise(exc)
    raise AssertionError("unreachable")


@router.get("/runs/{run_id}/report")
def report(run_id: str, request: Request, response: Response) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.report", write=False)
    _no_store(response)
    _owned_run(run_id, auth)
    return assurance.read_report(run_id)


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, request: Request, response: Response) -> dict[str, Any]:
    auth = _assurance_auth(request, "security.assurance.cancel", write=True)
    _no_store(response)
    harness = auth.get("harness") or {}
    try:
        return assurance.request_cancel(
            run_id,
            principal_id=str(harness.get("principal_id") or ""),
            session_id=str(harness.get("session_id") or ""),
        )
    except assurance.AssuranceError as exc:
        _raise(exc)
    raise AssertionError("unreachable")
