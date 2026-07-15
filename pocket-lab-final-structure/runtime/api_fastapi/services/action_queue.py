from __future__ import annotations

import os
import uuid
import time
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException

from .. import deps
from ..services.nats_bus import BUS

OperationRequestLike = Any
DomainFallback = Callable[[Dict[str, Any]], Dict[str, Any]]


def worker_mode() -> str:
    return os.environ.get("POCKETLAB_WORKER_EXECUTION", "worker").strip().lower()


def worker_execution_enabled() -> bool:
    mode = worker_mode()
    if mode in {"0", "false", "no", "off", "direct", "inprocess"}:
        if os.environ.get("POCKETLAB_ALLOW_INPROCESS_EXECUTION", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Direct in-process execution is disabled in production. Use NATS/JetStream worker execution.",
                "execution_mode": "forbidden",
                "bus": BUS.status(),
            },
        )
    if not BUS.connected:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "NATS/JetStream is required for write operations and is not connected",
                "execution_mode": "unavailable",
                "bus": BUS.status(),
            },
        )
    return True


async def ensure_worker_execution_ready() -> bool:
    mode = worker_mode()
    if mode in {"0", "false", "no", "off", "direct", "inprocess"}:
        return worker_execution_enabled()
    if not BUS.connected:
        try:
            await BUS.start()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "NATS/JetStream is required for write operations and is not connected",
                    "execution_mode": "unavailable",
                    "detail": str(exc),
                    "bus": BUS.status(),
                },
            ) from exc
    return worker_execution_enabled()


async def _publish_with_reconnect(subject: str, event_type: str, payload: Dict[str, Any], *, trace_id: str | None = None) -> None:
    try:
        await BUS.publish_json(subject, event_type, payload, trace_id=trace_id)
        return
    except Exception:
        # A phone sleep/wake or NATS listener restart can leave the FastAPI bus
        # object marked disconnected after the first publish attempt. Try one
        # bounded reconnect before surfacing a structured failure to the API.
        await BUS.start()
        await BUS.publish_json(subject, event_type, payload, trace_id=trace_id)


def operation_command_payload(
    submitted: Dict[str, Any], raw: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "job_id": submitted.get("job_id"),
        "operation": submitted.get("operation"),
        "task_id": submitted.get("task_id"),
        "target": raw.get("target") or {},
        "params": raw.get("params") or {},
        "dry_run": bool(raw.get("dry_run", False)),
        "trace_id": submitted.get("job_id"),
    }


def runbook_command_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    execution_id = str(raw.get("execution_id") or raw.get("job_id") or uuid.uuid4().hex)
    return {
        "execution_id": execution_id,
        "job_id": execution_id,
        "runbook": raw.get("runbook"),
        "params": raw.get("params") or {},
        "dry_run": bool(raw.get("dry_run", False)),
        "approved": raw.get("approved") is True,
        "approved_by": raw.get("approved_by"),
        "reason": raw.get("reason"),
        "requested_by": raw.get("requested_by") or "api",
        "trace_id": raw.get("trace_id") or execution_id,
    }


async def submit_operation_command(
    op_request: OperationRequestLike, raw: Dict[str, Any]
) -> Dict[str, Any]:
    """Submit an operation through the canonical Phase 5 path.

    FastAPI only creates a queued run and publishes a durable NATS/JetStream
    command.  The worker owns execution.  Production mode fails closed when
    NATS/JetStream is unavailable.
    """
    await ensure_worker_execution_ready()
    submitted = deps.operation_service().submit_queued(op_request)
    command = operation_command_payload(submitted, raw)
    await BUS.publish_json(
        "pocketlab.events.operation.created",
        "operation.created",
        command,
        trace_id=submitted.get("job_id"),
    )
    await BUS.publish_json(
        "pocketlab.commands.operation.execute",
        "operation.execute.requested",
        command,
        trace_id=submitted.get("job_id"),
    )
    submitted.update(
        {
            "status": "queued",
            "accepted": True,
            "execution_mode": "worker",
            "command_subject": "pocketlab.commands.operation.execute",
            "bus": BUS.status(),
        }
    )
    return submitted


async def submit_domain_command(
    subject: str,
    event_type: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    fallback: Optional[DomainFallback] = None,
    trace_id: str | None = None,
    timing_sink: dict[str, float] | None = None,
) -> Dict[str, Any]:
    """Submit a non-operation domain command through durable NATS/JetStream only."""
    payload = dict(data or {})
    command_id = str(
        payload.get("command_id") or payload.get("job_id") or uuid.uuid4().hex
    )
    payload.setdefault("command_id", command_id)
    payload.setdefault("trace_id", trace_id or command_id)

    operation_started = time.monotonic()
    ready_started = time.monotonic()
    await ensure_worker_execution_ready()
    ready_done = time.monotonic()
    try:
        command_started = time.monotonic()
        await _publish_with_reconnect(subject, event_type, payload, trace_id=payload["trace_id"])
        command_done = time.monotonic()
        evidence_started = time.monotonic()
        await _publish_with_reconnect(
            "pocketlab.events.command.queued",
            "command.queued",
            {"command_id": command_id, "command_subject": subject, **payload},
            trace_id=payload["trace_id"],
        )
        evidence_done = time.monotonic()
        if timing_sink is not None:
            timing_sink.update({
                "readiness_wait_ms": max(0.0, (ready_done - ready_started) * 1000.0),
                "command_publish_ms": max(0.0, (command_done - command_started) * 1000.0),
                "evidence_publish_ms": max(0.0, (evidence_done - evidence_started) * 1000.0),
                "execution_ms": max(0.0, (evidence_done - ready_done) * 1000.0),
                "total_ms": max(0.0, (evidence_done - operation_started) * 1000.0),
            })
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "NATS/JetStream command publish failed",
                "execution_mode": "unavailable",
                "command_subject": subject,
                "detail": str(exc),
                "bus": BUS.status(),
            },
        ) from exc
    return {
        "status": "queued",
        "accepted": True,
        "job_id": command_id,
        "command_id": command_id,
        "command_subject": subject,
        "execution_mode": "worker",
        "bus": BUS.status(),
    }

async def submit_runbook_command(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Submit a runbook execution through durable NATS/JetStream.

    FastAPI validates and publishes only. The worker owns execution and each
    runbook step is executed as a typed operation inside the worker boundary.
    """
    await ensure_worker_execution_ready()
    command = runbook_command_payload(raw)
    await BUS.publish_json(
        "pocketlab.events.runbook.queued",
        "runbook.queued",
        command,
        trace_id=command["trace_id"],
    )
    await BUS.publish_json(
        "pocketlab.commands.runbook.execute",
        "runbook.execute.requested",
        command,
        trace_id=command["trace_id"],
    )
    return {
        "status": "queued",
        "accepted": True,
        "job_id": command["execution_id"],
        "execution_id": command["execution_id"],
        "runbook": command.get("runbook"),
        "command_subject": "pocketlab.commands.runbook.execute",
        "execution_mode": "worker",
        "bus": BUS.status(),
    }




def runbook_approval_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Construct the canonical runbook approval command payload."""
    execution_id = str(raw.get("execution_id") or raw.get("job_id") or "").strip()
    trace_id = str(raw.get("trace_id") or execution_id)
    return {
        "execution_id": execution_id,
        "job_id": execution_id,
        "approved_by": raw.get("approved_by"),
        "approval_role": raw.get("approval_role") or "operator",
        "reason": raw.get("reason"),
        "trace_id": trace_id,
    }


def runbook_rejection_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Construct the canonical runbook rejection command payload."""
    execution_id = str(raw.get("execution_id") or raw.get("job_id") or "").strip()
    trace_id = str(raw.get("trace_id") or execution_id)
    return {
        "execution_id": execution_id,
        "job_id": execution_id,
        "rejected_by": raw.get("rejected_by"),
        "reason": raw.get("reason"),
        "trace_id": trace_id,
    }


async def submit_runbook_approval(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Submit a runbook approval request through durable NATS/JetStream."""
    await ensure_worker_execution_ready()
    command = runbook_approval_payload(raw)

    await BUS.publish_json(
        "pocketlab.events.runbook.approval_queued",
        "runbook.approval_queued",
        command,
        trace_id=command["trace_id"],
    )

    await BUS.publish_json(
        "pocketlab.commands.runbook.approve",
        "runbook.approve.requested",
        command,
        trace_id=command["trace_id"],
    )

    return {
        "status": "queued",
        "accepted": True,
        "execution_id": command["execution_id"],
        "job_id": command["execution_id"],
        "command_subject": "pocketlab.commands.runbook.approve",
        "execution_mode": "worker",
        "bus": BUS.status(),
    }


async def submit_runbook_rejection(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Submit a runbook rejection request through durable NATS/JetStream."""
    await ensure_worker_execution_ready()
    command = runbook_rejection_payload(raw)

    await BUS.publish_json(
        "pocketlab.events.runbook.rejection_queued",
        "runbook.rejection_queued",
        command,
        trace_id=command["trace_id"],
    )

    await BUS.publish_json(
        "pocketlab.commands.runbook.reject",
        "runbook.reject.requested",
        command,
        trace_id=command["trace_id"],
    )

    return {
        "status": "queued",
        "accepted": True,
        "execution_id": command["execution_id"],
        "job_id": command["execution_id"],
        "command_subject": "pocketlab.commands.runbook.reject",
        "execution_mode": "worker",
        "bus": BUS.status(),
    }
