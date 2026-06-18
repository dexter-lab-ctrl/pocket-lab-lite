from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from .. import deps
from contracts import utc_now_iso
from runbooks.engine import RunbookEngine
from runbooks.registry import RunbookRegistry
from runbooks.store import RunbookExecutionStore

from .approval_policy import resolve_runbook_approval_decision
from .governance_settings import get_governance_settings

EmitFn = Callable[[str, str, dict[str, Any]], Awaitable[None]]


def runbook_store() -> RunbookExecutionStore:
    return RunbookExecutionStore(Path(deps.settings().state_dir) / "runbook_executions")


def runbook_registry() -> RunbookRegistry:
    return RunbookRegistry()


async def execute_runbook_command(command: dict[str, Any], emit: EmitFn) -> dict[str, Any]:
    registry = runbook_registry()
    runbook_name = str(command.get("runbook") or command.get("runbook_name") or "").strip()
    runbook = registry.get(runbook_name) if runbook_name else None
    if runbook is not None:
        decision = resolve_runbook_approval_decision(
            runbook=runbook,
            command=command,
            governance_settings=get_governance_settings(),
        )
        if decision.get("decision") == "auto_approved":
            command = {
                **command,
                "approved": True,
                "approved_by": decision.get("approved_by") or "local-policy",
                "approval_role": decision.get("approval_role") or "local-owner",
                "approval_mode": "automatic",
                "reason": decision.get("reason"),
            }
            execution_id = str(command.get("execution_id") or command.get("job_id") or "")
            await emit(
                "pocketlab.events.runbook.auto_approved",
                "runbook.auto_approved",
                {
                    "execution_id": execution_id,
                    "runbook": runbook.name,
                    "approval_mode": "automatic",
                    "approved_by": command["approved_by"],
                    "approval_role": command["approval_role"],
                    "reason": command.get("reason"),
                },
            )
            await emit(
                "pocketlab.audit.runbook.auto_approved",
                "runbook.auto_approved",
                {
                    "execution_id": execution_id,
                    "runbook": runbook.name,
                    "approval_mode": "automatic",
                    "approved_by": command["approved_by"],
                    "approval_role": command["approval_role"],
                    "reason": command.get("reason"),
                },
            )

    engine = RunbookEngine(
        registry=registry,
        store=runbook_store(),
        operation_service=deps.operation_service(),
        emit=emit,
    )
    return await engine.execute(command)



ROLE_ORDER = [
    "viewer",
    "operator",
    "release_manager",
    "security_reviewer",
    "platform_admin",
]


def _approval_role_allowed(required: str | None, actual: str | None) -> bool:
    required_role = str(required or "operator").strip().lower()
    actual_role = str(actual or "operator").strip().lower()

    if actual_role == "platform_admin":
        return True

    if required_role in ROLE_ORDER and actual_role in ROLE_ORDER:
        return ROLE_ORDER.index(actual_role) >= ROLE_ORDER.index(required_role)

    return actual_role == required_role


async def approve_runbook_command(command: dict[str, Any], emit: EmitFn) -> dict[str, Any]:
    """Approve a runbook execution inside the worker and resume remaining steps."""
    execution_id = str(command.get("execution_id") or command.get("job_id") or "").strip()
    approved_by = str(command.get("approved_by") or "").strip()
    approval_role = str(command.get("approval_role") or "operator").strip()
    reason = command.get("reason")

    if not execution_id:
        raise ValueError("runbook approval command missing execution_id")

    store = runbook_store()
    execution = store.get(execution_id)
    if not execution:
        raise KeyError(f"Runbook execution not found: {execution_id}")

    if str(execution.get("status") or "").lower() != "approval_required":
        return execution

    registry = runbook_registry()
    runbook_name = str(execution.get("runbook") or "").strip()
    runbook = registry.get(runbook_name)
    if runbook is None:
        raise ValueError(f"unknown runbook: {runbook_name}")

    policy = dict(runbook.spec.get("policy") or {})
    minimum_role = str(policy.get("minimumRole") or "operator").strip()

    if not _approval_role_allowed(minimum_role, approval_role):
        store.update(
            execution_id,
            status="failed",
            approved=False,
            approval_role=approval_role,
            approval_required_role=minimum_role,
            rejection_reason="approval role does not satisfy runbook policy",
            finished_at=utc_now_iso(),
        )
        await emit(
            "pocketlab.events.runbook.failed",
            "runbook.failed",
            {
                "execution_id": execution_id,
                "runbook": runbook_name,
                "status": "failed",
                "reason": "approval role does not satisfy runbook policy",
                "approval_role": approval_role,
                "required_role": minimum_role,
            },
        )
        return store.get(execution_id) or execution

    store.update(
        execution_id,
        approved=True,
        approved_by=approved_by,
        approval_role=approval_role,
        reason=reason,
        status="approved",
        finished_at=None,
    )

    store.append_event(
        execution_id,
        {
            "type": "runbook.approved",
            "message": "Runbook approved",
            "approved_by": approved_by,
            "approval_role": approval_role,
            "reason": reason,
        },
    )

    await emit(
        "pocketlab.events.runbook.approved",
        "runbook.approved",
        {
            "execution_id": execution_id,
            "runbook": runbook_name,
            "approved_by": approved_by,
            "approval_role": approval_role,
            "reason": reason,
            "status": "approved",
        },
    )

    await emit(
        "pocketlab.audit.runbook.approved",
        "runbook.approved",
        {
            "execution_id": execution_id,
            "runbook": runbook_name,
            "approved_by": approved_by,
            "approval_role": approval_role,
            "reason": reason,
            "status": "approved",
        },
    )

    engine = RunbookEngine(
        registry=registry,
        store=store,
        operation_service=deps.operation_service(),
        emit=emit,
    )
    return await engine.resume(execution_id)


async def reject_runbook_command(command: dict[str, Any], emit: EmitFn) -> dict[str, Any]:
    """Reject a runbook execution inside the worker and mark it failed."""
    execution_id = str(command.get("execution_id") or command.get("job_id") or "").strip()
    rejected_by = str(command.get("rejected_by") or "").strip()
    reason = command.get("reason")

    if not execution_id:
        raise ValueError("runbook rejection command missing execution_id")

    store = runbook_store()
    execution = store.get(execution_id)
    if not execution:
        raise KeyError(f"Runbook execution not found: {execution_id}")

    if str(execution.get("status") or "").lower() != "approval_required":
        return execution

    runbook_name = str(execution.get("runbook") or "").strip()

    store.update(
        execution_id,
        approved=False,
        rejected=True,
        rejected_by=rejected_by,
        reason=reason,
        status="failed",
        finished_at=utc_now_iso(),
    )

    store.append_event(
        execution_id,
        {
            "type": "runbook.rejected",
            "message": "Runbook rejected",
            "rejected_by": rejected_by,
            "reason": reason,
        },
    )

    await emit(
        "pocketlab.events.runbook.rejected",
        "runbook.rejected",
        {
            "execution_id": execution_id,
            "runbook": runbook_name,
            "rejected_by": rejected_by,
            "reason": reason,
            "status": "rejected",
        },
    )

    await emit(
        "pocketlab.audit.runbook.rejected",
        "runbook.rejected",
        {
            "execution_id": execution_id,
            "runbook": runbook_name,
            "rejected_by": rejected_by,
            "reason": reason,
            "status": "rejected",
        },
    )

    await emit(
        "pocketlab.events.runbook.failed",
        "runbook.failed",
        {
            "execution_id": execution_id,
            "runbook": runbook_name,
            "status": "failed",
            "reason": reason,
        },
    )

    return store.get(execution_id) or execution
