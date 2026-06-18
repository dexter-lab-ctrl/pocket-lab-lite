from __future__ import annotations

import asyncio
import uuid
from typing import Any, Awaitable, Callable

from contracts import OperationRequest, OperationTarget, utc_now_iso

from .models import RunbookDefinition, RunbookStep
from .registry import RunbookRegistry
from .store import RunbookExecutionStore

EmitFn = Callable[[str, str, dict[str, Any]], Awaitable[None]]


SENSITIVE_KEYS = {"api_key", "authorization", "password", "private_key", "secret", "token", "value"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                redacted[str(key)] = "<redacted>"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _merge_params(base: dict[str, Any], step_params: dict[str, Any]) -> dict[str, Any]:
    merged = dict(step_params)
    overrides = base.get("stepParams") if isinstance(base.get("stepParams"), dict) else {}
    if isinstance(overrides, dict):
        merged.update(overrides)
    return merged


class RunbookEngine:
    def __init__(
        self,
        *,
        registry: RunbookRegistry,
        store: RunbookExecutionStore,
        operation_service: Any,
        emit: EmitFn,
    ):
        self.registry = registry
        self.store = store
        self.operation_service = operation_service
        self.emit = emit

    async def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        runbook_name = str(command.get("runbook") or command.get("runbook_name") or "").strip()
        if not runbook_name:
            raise ValueError("runbook command is missing runbook name")

        runbook = self.registry.get(runbook_name)
        if runbook is None:
            raise ValueError(f"unknown runbook: {runbook_name}")

        execution_id = str(command.get("execution_id") or command.get("job_id") or uuid.uuid4().hex)
        trace_id = str(command.get("trace_id") or execution_id)
        params = dict(command.get("params") or {})
        dry_run = bool(command.get("dry_run", False))
        approved = command.get("approved") is True
        approved_by = str(command.get("approved_by") or "").strip()
        requested_by = str(command.get("requested_by") or "api").strip()

        execution = self.store.create(
            {
                "execution_id": execution_id,
                "runbook": runbook.name,
                "title": runbook.title,
                "status": "started",
                "requested_by": requested_by,
                "approved": approved,
                "approved_by": approved_by,
                "dry_run": dry_run,
                "trace_id": trace_id,
                "params": params,
                "source_file": runbook.source_file,
            }
        )

        await self._event(
            "pocketlab.events.runbook.started",
            "runbook.started",
            execution_id,
            {
                "runbook": runbook.name,
                "title": runbook.title,
                "requested_by": requested_by,
                "dry_run": dry_run,
            },
        )

        if self._approval_required(runbook) and not approved:
            self.store.update(execution_id, status="approval_required")
            self.store.append_event(
                execution_id,
                {
                    "type": "runbook.approval_required",
                    "message": "Runbook requires approval before execution.",
                },
            )
            await self._event(
                "pocketlab.events.runbook.approval_required",
                "runbook.approval_required",
                execution_id,
                {
                    "runbook": runbook.name,
                    "status": "approval_required",
                    "reason": "approval required by runbook metadata",
                },
            )
            return self.store.get(execution_id) or execution

        try:
            for index, step in enumerate(runbook.steps, start=1):
                step_result = await self._execute_step(
                    runbook=runbook,
                    step=step,
                    index=index,
                    execution_id=execution_id,
                    params=params,
                    dry_run=dry_run,
                )
                if step_result.get("status") != "succeeded":
                    self.store.update(execution_id, status="failed", finished_at=utc_now_iso())
                    await self._event(
                        "pocketlab.events.runbook.failed",
                        "runbook.failed",
                        execution_id,
                        {
                            "runbook": runbook.name,
                            "failed_step": step.name,
                            "operation": step.operation,
                            "status": "failed",
                        },
                    )
                    return self.store.get(execution_id) or execution

            self.store.update(execution_id, status="succeeded", finished_at=utc_now_iso())
            await self._event(
                "pocketlab.events.runbook.succeeded",
                "runbook.succeeded",
                execution_id,
                {"runbook": runbook.name, "status": "succeeded"},
            )
            await self._event(
                "pocketlab.audit.runbook.executed",
                "runbook.executed",
                execution_id,
                {
                    "runbook": runbook.name,
                    "status": "succeeded",
                    "requested_by": requested_by,
                    "approved_by": approved_by,
                    "dry_run": dry_run,
                },
            )
            return self.store.get(execution_id) or execution
        except Exception as exc:
            self.store.update(execution_id, status="failed", finished_at=utc_now_iso(), error=str(exc))
            await self._event(
                "pocketlab.events.runbook.failed",
                "runbook.failed",
                execution_id,
                {"runbook": runbook.name, "status": "failed", "error": str(exc)},
            )
            raise


    async def resume(self, execution_id: str) -> dict[str, Any]:
        """Resume an approval-gated runbook from the next pending step.

        The execution must already exist in the runbook execution store. This
        method is worker-owned and intentionally does not create a new execution.
        It avoids replaying completed steps by deriving the next pending step
        from step journal entries that reached status='succeeded'.
        """
        execution = self.store.get(execution_id)
        if not execution:
            raise KeyError(f"Runbook execution not found: {execution_id}")

        current_status = str(execution.get("status") or "").lower()
        if current_status in {"succeeded", "failed", "cancelled"}:
            return execution

        runbook_name = str(execution.get("runbook") or "").strip()
        if not runbook_name:
            raise ValueError("stored runbook execution is missing runbook name")

        runbook = self.registry.get(runbook_name)
        if runbook is None:
            raise ValueError(f"unknown runbook: {runbook_name}")

        completed_indexes: set[int] = set()
        for entry in execution.get("steps") or []:
            if str(entry.get("status") or "").lower() != "succeeded":
                continue
            try:
                completed_indexes.add(int(entry.get("step_index") or entry.get("index") or 0))
            except (TypeError, ValueError):
                continue

        next_index = 1
        if completed_indexes:
            next_index = max(completed_indexes) + 1

        self.store.update(execution_id, status="resumed", finished_at=None)

        await self._event(
            "pocketlab.events.runbook.resumed",
            "runbook.resumed",
            execution_id,
            {
                "runbook": runbook.name,
                "status": "resumed",
                "next_step_index": next_index,
            },
        )

        params = dict(execution.get("params") or {})
        dry_run = bool(execution.get("dry_run", False))
        requested_by = str(execution.get("requested_by") or "api")
        approved_by = str(execution.get("approved_by") or "")

        try:
            for index, step in enumerate(runbook.steps, start=1):
                if index < next_index:
                    continue

                step_result = await self._execute_step(
                    runbook=runbook,
                    step=step,
                    index=index,
                    execution_id=execution_id,
                    params=params,
                    dry_run=dry_run,
                )

                if step_result.get("status") != "succeeded":
                    self.store.update(execution_id, status="failed", finished_at=utc_now_iso())
                    await self._event(
                        "pocketlab.events.runbook.failed",
                        "runbook.failed",
                        execution_id,
                        {
                            "runbook": runbook.name,
                            "failed_step": step.name,
                            "operation": step.operation,
                            "status": "failed",
                        },
                    )
                    return self.store.get(execution_id) or execution

            self.store.update(execution_id, status="succeeded", finished_at=utc_now_iso())

            await self._event(
                "pocketlab.events.runbook.succeeded",
                "runbook.succeeded",
                execution_id,
                {"runbook": runbook.name, "status": "succeeded"},
            )

            await self._event(
                "pocketlab.audit.runbook.executed",
                "runbook.executed",
                execution_id,
                {
                    "runbook": runbook.name,
                    "status": "succeeded",
                    "requested_by": requested_by,
                    "approved_by": approved_by,
                    "dry_run": dry_run,
                    "resumed": True,
                },
            )

            return self.store.get(execution_id) or execution
        except Exception as exc:
            self.store.update(
                execution_id,
                status="failed",
                finished_at=utc_now_iso(),
                error=str(exc),
            )
            await self._event(
                "pocketlab.events.runbook.failed",
                "runbook.failed",
                execution_id,
                {"runbook": runbook.name, "status": "failed", "error": str(exc)},
            )
            raise

    def _approval_required(self, runbook: RunbookDefinition) -> bool:
        return runbook.requires_approval or any(step.requires_approval for step in runbook.steps)

    async def _execute_step(
        self,
        *,
        runbook: RunbookDefinition,
        step: RunbookStep,
        index: int,
        execution_id: str,
        params: dict[str, Any],
        dry_run: bool,
    ) -> dict[str, Any]:
        if not step.operation:
            raise ValueError(f"runbook {runbook.name} step {step.name} is missing operation")

        target = dict(step.target or {})
        target_type = str(target.get("type") or "runbook")
        target_ref = str(target.get("ref") or runbook.name)

        op_request = OperationRequest(
            operation=step.operation,
            target=OperationTarget(type=target_type, ref=target_ref),
            params=_merge_params(params, step.params),
            dry_run=dry_run,
            source=f"runbook:{runbook.name}",
        )

        submitted = self.operation_service.submit_queued(op_request)
        operation_job_id = str(submitted.get("job_id"))

        self.store.append_step(
            execution_id,
            {
                "index": index,
                "name": step.name,
                "operation": step.operation,
                "operation_job_id": operation_job_id,
                "status": "started",
            },
        )

        await self._event(
            "pocketlab.events.runbook.step_started",
            "runbook.step_started",
            execution_id,
            {
                "runbook": runbook.name,
                "step": step.name,
                "step_index": index,
                "operation": step.operation,
                "operation_job_id": operation_job_id,
            },
        )

        result = await asyncio.to_thread(self.operation_service.run_existing, operation_job_id)
        status = str(result.get("status") or "unknown")

        step_payload = {
            "runbook": runbook.name,
            "step": step.name,
            "step_index": index,
            "operation": step.operation,
            "operation_job_id": operation_job_id,
            "operation_status": status,
            "exit_code": result.get("exit_code"),
            "error": result.get("error"),
        }

        if status == "succeeded":
            self.store.append_step(execution_id, {**step_payload, "status": "succeeded"})
            await self._event(
                "pocketlab.events.runbook.step_succeeded",
                "runbook.step_succeeded",
                execution_id,
                step_payload,
            )
            return {"status": "succeeded", "operation_job_id": operation_job_id}

        self.store.append_step(execution_id, {**step_payload, "status": "failed"})
        await self._event(
            "pocketlab.events.runbook.step_failed",
            "runbook.step_failed",
            execution_id,
            step_payload,
        )
        return {"status": "failed", "operation_job_id": operation_job_id, "error": result.get("error")}

    async def _event(
        self,
        subject: str,
        event_type: str,
        execution_id: str,
        data: dict[str, Any],
    ) -> None:
        self.store.append_event(
            execution_id,
            {
                "type": event_type,
                "subject": subject,
                "data": _redact(data),
            },
        )
        await self.emit(subject, event_type, {"execution_id": execution_id, **_redact(data)})
