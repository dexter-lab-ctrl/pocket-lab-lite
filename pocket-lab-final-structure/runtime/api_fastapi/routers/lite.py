from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid

from typing import Any, Literal

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .. import deps
from ..db.connection import database_path
from ..schemas.operations import OperationRequest
from ..services.action_queue import ensure_worker_execution_ready, submit_domain_command, submit_operation_command
from ..services import fleet_registry, lite_app_actions, lite_app_lifecycle, lite_app_profiles, lite_app_storage, lite_app_backup, lite_app_backup_targets, lite_app_operations, lite_app_update, lite_backup, lite_catalog, lite_invites, lite_status, lite_security, lite_catalog_live, lite_photoprism_media, lite_evidence_receipts, lite_gate_faults, lite_storage_guard, lite_lifecycle_diagnostics, lite_database_recovery, lite_security_maintenance, lite_recovery_subprojections, lite_core_projections, lite_phase3b_projections, lite_phase3c_projections, lite_identity_auth, lite_policy_opa, lite_policy_approvals
from ..services.lite_control_plane_store import (
    CONTROL_PLANE,
    DeviceAwarenessError,
    DeviceProfileUpdateError,
    PreparedProjectionUnavailable,
    PreparedRead,
)
from ..services.runtime_diagnostics import RUNTIME_DIAGNOSTICS
from ..services.request_limits import request_limit_snapshot
from ..services.workload_admission import (
    AdmissionQueueFull,
    AdmissionShutdown,
    AdmissionTimeout,
    ExecutorUnavailable,
    OperationDeadlineExceeded,
    WORKLOAD_ADMISSION,
    WorkloadAdmissionError,
    workload_classification_snapshot,
)

router = APIRouter(prefix="/api/lite", tags=["lite"])
_LOGGER = logging.getLogger(__name__)
async def _record_admission_outcome(
    *, operation: str, outcome: str, reason: str, retryable: bool, admission_class: str
) -> None:
    """Best-effort sanitized audit evidence without recursive admission."""
    payload = {
        "operation": str(operation or "lite_control")[:80],
        "outcome": str(outcome or "rejected")[:24],
        "reason": str(reason or "control_plane_busy")[:64],
        "retryable": bool(retryable),
        "capacity_class": str(admission_class or "unknown")[:48],
        "captured_at": deps.now_utc_iso(),
        "sanitized": True,
    }
    try:
        from ..services.nats_bus import BUS

        await asyncio.wait_for(
            BUS.publish_json(
                "pocketlab.audit.lite.control.rejected",
                "lite.control.rejected",
                payload,
            ),
            timeout=0.5,
        )
    except Exception as exc:
        _LOGGER.warning(
            "pocketlab.admission.audit_degraded operation=%s error_type=%s",
            payload["operation"],
            type(exc).__name__,
        )


async def _raise_admission_http_error(exc: WorkloadAdmissionError, operation: str) -> None:
    await _record_admission_outcome(
        operation=operation,
        outcome="rejected",
        reason=exc.reason,
        retryable=exc.retryable,
        admission_class=exc.admission_class.value,
    )
    status_code = 503
    message = exc.safe_message or "Pocket Lab is busy. Try again shortly."
    raise HTTPException(
        status_code=status_code,
        headers={"Retry-After": "2", "Cache-Control": "no-store"},
        detail={
            "status": "busy",
            "accepted": False,
            "reason": exc.reason,
            "retryable": bool(exc.retryable),
            "operation": operation,
            "message": message,
            "sanitized": True,
        },
    )

def _lite_payload_dict(payload):
    """Return a request model as a dict on both Pydantic v1 and v2."""
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if hasattr(payload, "dict"):
        return payload.dict()
    return {}


def _request_source(request: Request) -> str:
    return str(request.client.host if request.client else "unknown")[:80]


def _raise_identity_error(exc: lite_identity_auth.IdentityError) -> None:
    headers = {"Cache-Control": "no-store"}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    raise HTTPException(
        status_code=exc.status_code,
        headers=headers,
        detail={"reason_code": exc.reason_code, "message": exc.message},
    ) from exc


def _set_identity_cookie(response: Response, session_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=lite_identity_auth.cookie_name(),
        value=session_token,
        max_age=lite_identity_auth.session_cookie_max_age(),
        httponly=True,
        secure=lite_identity_auth.cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key=lite_identity_auth.csrf_cookie_name(),
        value=csrf_token,
        max_age=lite_identity_auth.session_cookie_max_age(),
        httponly=False,
        secure=lite_identity_auth.cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_identity_cookie(response: Response) -> None:
    response.delete_cookie(
        key=lite_identity_auth.cookie_name(),
        httponly=True,
        secure=lite_identity_auth.cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.delete_cookie(
        key=lite_identity_auth.csrf_cookie_name(),
        secure=lite_identity_auth.cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _identity_projection(request: Request) -> dict[str, Any]:
    auth_context = deps.resolve_auth_context(request)
    projection = lite_identity_auth.identity_projection(auth_context)
    projection["identity_classes"] = {
        "human": {"label": "Owner", "managed_by": "Identity", "configured": bool(projection.get("owner"))},
        "device": {"label": "Device identities", "managed_by": "Devices", "summary": "Device enrollment identity remains protected by the Devices flow."},
        "service": {
            "label": "Service identities",
            "managed_by": "FastAPI runtime",
            "api_token_configured": bool(deps.settings().api_token.strip()),
            "summary": "Service access is separate from the human owner session.",
        },
    }
    return projection


async def _enforce_lite_policy(
    *,
    auth_context: dict[str, Any],
    action_id: str,
    target_type: str,
    target_id: str,
    target_revision: str,
    target: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            lite_policy_opa.evaluate_authorization,
            auth_context=auth_context,
            action_id=action_id,
            target_type=target_type,
            target_id=target_id,
            target_revision=target_revision,
            target=target,
            request_context={"source": "lite_api"},
            correlation_id=correlation_id,
        )
    except lite_policy_opa.PolicyDecisionError as exc:
        decision = exc.decision or {}
        raise HTTPException(
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
            detail={
                "status": "blocked",
                "accepted": False,
                "reason_code": exc.reason_code,
                "message": exc.message,
                "decision_id": decision.get("decision_id"),
                "policy_revision": decision.get("policy_revision"),
                "approval": decision.get("approval"),
            },
        ) from exc



def _security_compact_headers(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "ETag": lite_security.compact_response_etag(payload),
        "Cache-Control": "no-cache",
    }


def _security_compact_response(request: Request, payload: dict[str, Any]) -> Response:
    headers = _security_compact_headers(payload)
    if lite_security.if_none_match_matches(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)


def _recovery_compact_response(request: Request, payload: dict[str, Any]) -> Response:
    headers = {
        "ETag": lite_security.compact_response_etag(payload),
        "Cache-Control": "no-cache",
        "X-PocketLab-View-Model": str(payload.get("view_model") or "recovery-summary-r3-v1"),
    }
    if lite_security.if_none_match_matches(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)


def _control_plane_prepared_response(
    request: Request, prepared: PreparedRead, *, view_model: str
) -> Response:
    payload = dict(prepared.payload)
    semantic_source_revision = int(payload.get("source_revision") or 0)
    stored_projection_revision = int(payload.get("projection_revision") or 0)
    scheduler_generation = int(payload.get("generation") or 0)
    payload.update({
        "projection_age_ms": int(prepared.projection_age_ms),
        "read_degraded": bool(prepared.read_degraded),
        "refresh_pending": bool(prepared.refresh_pending),
        # Compatibility alias: Phase 3B endpoints expose the semantic source
        # revision rather than the in-memory ETag/cache revision.
        "source_revision": semantic_source_revision or int(prepared.source_revision),
        "semantic_source_revision": semantic_source_revision,
        "stored_projection_revision": stored_projection_revision,
        "scheduler_generation": scheduler_generation,
        "retry_after_seconds": int(prepared.retry_after_seconds),
        "retry_after_ms": int(prepared.retry_after_ms),
        "degraded_reason": str(prepared.degraded_reason or ""),
        "data_source": str(prepared.data_source or "prepared_sqlite"),
        "load_state": str(prepared.load_state or "normal"),
    })
    timing = prepared.timing
    headers = {
        "ETag": prepared.etag,
        "Cache-Control": "no-cache",
        "X-PocketLab-View-Model": view_model,
        "Server-Timing": ", ".join(
            f"{name};dur={max(0.0, float(duration)):.2f}"
            for name, duration in (
                ("connection", timing.get("connection_acquisition_ms", 0.0)),
                ("sqlite", timing.get("sqlite_query_ms", 0.0)),
                ("projection", timing.get("projection_build_ms", 0.0)),
                ("serialization", timing.get("serialization_ms", 0.0)),
            )
        ),
        "X-PocketLab-Projection-Age-Ms": str(int(prepared.projection_age_ms)),
        "X-PocketLab-Source-Revision": str(int(payload["source_revision"])),
        "X-PocketLab-Projection-Revision": str(stored_projection_revision),
        "X-PocketLab-Scheduler-Generation": str(scheduler_generation),
        "X-PocketLab-Read-Degraded": "true" if prepared.read_degraded else "false",
        "X-PocketLab-Refresh-Pending": "true" if prepared.refresh_pending else "false",
        "X-PocketLab-Load-State": str(prepared.load_state or "normal"),
        "X-PocketLab-Data-Source": str(prepared.data_source or "prepared_sqlite"),
    }
    if prepared.retry_after_seconds:
        headers["Retry-After"] = str(max(1, int(prepared.retry_after_seconds)))
    if lite_security.if_none_match_matches(
        request.headers.get("if-none-match"), prepared.etag
    ):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)


def _projection_warming_response(*, domain: str, view_model: str) -> JSONResponse:
    retry_after = "2"
    return JSONResponse(
        status_code=503,
        content={
            "status": "warming",
            "summary": "Pocket Lab is refreshing this saved view. Try again shortly.",
            "domain": domain,
            "retryable": True,
            "read_degraded": True,
            "refresh_pending": True,
            "retry_after_seconds": int(retry_after),
            "retry_after_ms": int(retry_after) * 1000,
            "degraded_reason": "prepared_projection_warming",
            "data_source": "none",
            "load_state": "warming",
        },
        headers={
            "Retry-After": retry_after,
            "Cache-Control": "no-store",
            "X-PocketLab-View-Model": view_model,
            "X-PocketLab-Read-Degraded": "true",
            "X-PocketLab-Refresh-Pending": "true",
        },
    )


def _timed_projection_stage(
    timings: dict[str, float], name: str, callback: Any
) -> Any:
    started = time.monotonic()
    try:
        return callback()
    finally:
        timings[name] = round(max(0.0, (time.monotonic() - started) * 1000.0), 3)


def _control_plane_history_response(
    request: Request, payload: dict[str, Any], *, domain: str, key: str
) -> Response:
    revision = int(payload.get("source_revision") or 0)
    etag = CONTROL_PLANE.revision_etag(domain, key, revision)
    headers = {
        "ETag": etag,
        "Cache-Control": "no-cache",
        "X-PocketLab-Source-Revision": str(revision),
        "Server-Timing": ", ".join(
            (
                f"connection;dur={max(0.0, float(payload.get('connection_wait_ms') or 0.0)):.2f}",
                f"sqlite;dur={max(0.0, float(payload.get('sqlite_query_ms') or 0.0)):.2f}",
            )
        ),
    }
    if lite_security.if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)


def _record_security_submission_timing(
    response: Response,
    *,
    run_id: str,
    started: float,
    auth_done: float,
    reservation_done: float,
    publish_done: float | None = None,
    lifecycle_committed: float | None = None,
    deduplicated: bool = False,
    reservation_timing: dict[str, float] | None = None,
    publish_timing: dict[str, float] | None = None,
    lifecycle_timing: dict[str, float] | None = None,
) -> None:
    """Expose sanitized stage timings without leaking command payload data."""
    end = lifecycle_committed or publish_done or reservation_done
    reservation_timing = reservation_timing or {}
    publish_timing = publish_timing or {}
    lifecycle_timing = lifecycle_timing or {}
    stages = {
        "auth": max(0.0, (auth_done - started) * 1000),
        "reservation_queue": float(reservation_timing.get("queue_wait_ms", 0.0)),
        "reservation_execution": float(reservation_timing.get("execution_ms", 0.0)),
        "reservation_connection_wait": float(reservation_timing.get("stage_connection_wait_ms", 0.0)),
        "reservation_connection_path_resolve": float(reservation_timing.get("stage_connection_path_resolve_ms", 0.0)),
        "reservation_connection_sqlite_connect": float(reservation_timing.get("stage_connection_sqlite_connect_ms", 0.0)),
        "reservation_connection_pragma_setup": float(reservation_timing.get("stage_connection_pragma_setup_ms", 0.0)),
        "reservation_begin_wait": float(reservation_timing.get("stage_begin_wait_ms", 0.0)),
        "reservation_active_lookup": float(reservation_timing.get("stage_active_lookup_ms", 0.0)),
        "reservation_recent_lookup": float(reservation_timing.get("stage_recent_lookup_ms", 0.0)),
        "reservation_write": float(reservation_timing.get("stage_write_ms", 0.0)),
        "reservation_commit": float(reservation_timing.get("stage_commit_ms", 0.0)),
        "reservation_result_build": float(reservation_timing.get("stage_result_build_ms", 0.0)),
        "reservation": max(0.0, (reservation_done - auth_done) * 1000),
        "nats_payload_prepare": float(publish_timing.get("payload_prepare_ms", 0.0)),
        "nats_readiness_wait": float(publish_timing.get("readiness_wait_ms", 0.0)),
        "nats_command_prepare": float(publish_timing.get("command_prepare_ms", 0.0)),
        "nats_command_send": float(publish_timing.get("command_send_ms", 0.0)),
        "nats_command_ack_wait": float(publish_timing.get("command_ack_wait_ms", 0.0)),
        "nats_command_record_memory": float(publish_timing.get("command_record_memory_ms", 0.0)),
        "nats_command_workflow_enqueue": float(publish_timing.get("command_workflow_enqueue_ms", 0.0)),
        "nats_command_post_ack": float(publish_timing.get("command_post_ack_ms", 0.0)),
        "nats_command_broker": float(publish_timing.get("command_broker_ms", 0.0)),
        "nats_command_reconnect": float(publish_timing.get("command_reconnect_ms", 0.0)),
        "nats_evidence_payload_prepare": float(publish_timing.get("evidence_payload_prepare_ms", 0.0)),
        "nats_evidence_prepare": float(publish_timing.get("evidence_prepare_ms", 0.0)),
        "nats_evidence_send": float(publish_timing.get("evidence_send_ms", 0.0)),
        "nats_evidence_ack_wait": float(publish_timing.get("evidence_ack_wait_ms", 0.0)),
        "nats_evidence_record_memory": float(publish_timing.get("evidence_record_memory_ms", 0.0)),
        "nats_evidence_workflow_enqueue": float(publish_timing.get("evidence_workflow_enqueue_ms", 0.0)),
        "nats_evidence_post_ack": float(publish_timing.get("evidence_post_ack_ms", 0.0)),
        "nats_evidence_broker": float(publish_timing.get("evidence_broker_ms", 0.0)),
        "nats_evidence_reconnect": float(publish_timing.get("evidence_reconnect_ms", 0.0)),
        "nats_publish_execution": float(publish_timing.get("execution_ms", 0.0)),
        "publish": max(0.0, ((publish_done or reservation_done) - reservation_done) * 1000),
        "lifecycle_queue": float(lifecycle_timing.get("queue_wait_ms", 0.0)),
        "lifecycle_execution": float(lifecycle_timing.get("execution_ms", 0.0)),
        "lifecycle_connection_wait": float(lifecycle_timing.get("stage_connection_wait_ms", 0.0)),
        "lifecycle_connection_path_resolve": float(lifecycle_timing.get("stage_connection_path_resolve_ms", 0.0)),
        "lifecycle_connection_sqlite_connect": float(lifecycle_timing.get("stage_connection_sqlite_connect_ms", 0.0)),
        "lifecycle_connection_pragma_setup": float(lifecycle_timing.get("stage_connection_pragma_setup_ms", 0.0)),
        "lifecycle_begin_wait": float(lifecycle_timing.get("stage_begin_wait_ms", 0.0)),
        "lifecycle_lookup": float(lifecycle_timing.get("stage_lookup_ms", 0.0)),
        "lifecycle_write": float(lifecycle_timing.get("stage_write_ms", 0.0)),
        "lifecycle_transaction_commit": float(lifecycle_timing.get("stage_commit_ms", 0.0)),
        "lifecycle_result_build": float(lifecycle_timing.get("stage_result_build_ms", 0.0)),
        "lifecycle_commit": max(0.0, ((lifecycle_committed or publish_done or reservation_done) - (publish_done or reservation_done)) * 1000),
        "total": max(0.0, (end - started) * 1000),
    }
    response.headers["Server-Timing"] = ", ".join(
        f"{name};dur={duration:.2f}" for name, duration in stages.items()
    )
    timing_log = (
        _LOGGER.warning if stages["total"] >= 3000
        else _LOGGER.info if stages["total"] >= 1000
        else _LOGGER.debug
    )
    timing_log(
        "Security scan submission timing run_id=%s deduplicated=%s "
        "auth_ms=%.2f reservation_queue_ms=%.2f reservation_execution_ms=%.2f "
        "reservation_process_cpu_ms=%.2f reservation_connection_wait_ms=%.2f "
        "reservation_connection_path_resolve_ms=%.2f reservation_connection_sqlite_connect_ms=%.2f "
        "reservation_connection_pragma_setup_ms=%.2f reservation_begin_wait_ms=%.2f reservation_active_lookup_ms=%.2f "
        "reservation_recent_lookup_ms=%.2f reservation_write_ms=%.2f "
        "reservation_commit_ms=%.2f reservation_result_build_ms=%.2f "
        "nats_payload_prepare_ms=%.2f command_encoded_bytes=%.0f evidence_encoded_bytes=%.0f "
        "nats_readiness_wait_ms=%.2f nats_command_prepare_ms=%.2f "
        "nats_command_send_ms=%.2f nats_command_ack_wait_ms=%.2f "
        "nats_command_record_memory_ms=%.2f nats_command_workflow_enqueue_ms=%.2f nats_command_post_ack_ms=%.2f nats_command_broker_ms=%.2f nats_command_reconnect_ms=%.2f "
        "nats_evidence_payload_prepare_ms=%.2f nats_evidence_prepare_ms=%.2f "
        "nats_evidence_send_ms=%.2f nats_evidence_ack_wait_ms=%.2f "
        "nats_evidence_record_memory_ms=%.2f nats_evidence_workflow_enqueue_ms=%.2f nats_evidence_post_ack_ms=%.2f nats_evidence_broker_ms=%.2f nats_evidence_reconnect_ms=%.2f "
        "lifecycle_queue_ms=%.2f lifecycle_execution_ms=%.2f "
        "lifecycle_process_cpu_ms=%.2f lifecycle_connection_wait_ms=%.2f "
        "lifecycle_connection_path_resolve_ms=%.2f lifecycle_connection_sqlite_connect_ms=%.2f "
        "lifecycle_connection_pragma_setup_ms=%.2f lifecycle_begin_wait_ms=%.2f "
        "lifecycle_lookup_ms=%.2f lifecycle_write_ms=%.2f lifecycle_transaction_commit_ms=%.2f "
        "lifecycle_result_build_ms=%.2f total_ms=%.2f",
        run_id, deduplicated, stages["auth"], stages["reservation_queue"],
        stages["reservation_execution"], float(reservation_timing.get("process_cpu_ms", 0.0)),
        stages["reservation_connection_wait"], stages["reservation_connection_path_resolve"],
        stages["reservation_connection_sqlite_connect"], stages["reservation_connection_pragma_setup"],
        stages["reservation_begin_wait"],
        stages["reservation_active_lookup"], stages["reservation_recent_lookup"],
        stages["reservation_write"], stages["reservation_commit"],
        stages["reservation_result_build"], stages["nats_payload_prepare"],
        float(publish_timing.get("command_encoded_bytes", 0.0)),
        float(publish_timing.get("evidence_encoded_bytes", 0.0)),
        stages["nats_readiness_wait"], stages["nats_command_prepare"],
        stages["nats_command_send"], stages["nats_command_ack_wait"],
        stages["nats_command_record_memory"], stages["nats_command_workflow_enqueue"],
        stages["nats_command_post_ack"], stages["nats_command_broker"],
        stages["nats_command_reconnect"], stages["nats_evidence_payload_prepare"],
        stages["nats_evidence_prepare"], stages["nats_evidence_send"],
        stages["nats_evidence_ack_wait"], stages["nats_evidence_record_memory"],
        stages["nats_evidence_workflow_enqueue"], stages["nats_evidence_post_ack"],
        stages["nats_evidence_broker"], stages["nats_evidence_reconnect"], stages["lifecycle_queue"],
        stages["lifecycle_execution"], float(lifecycle_timing.get("process_cpu_ms", 0.0)),
        stages["lifecycle_connection_wait"], stages["lifecycle_connection_path_resolve"],
        stages["lifecycle_connection_sqlite_connect"], stages["lifecycle_connection_pragma_setup"],
        stages["lifecycle_begin_wait"], stages["lifecycle_lookup"], stages["lifecycle_write"],
        stages["lifecycle_transaction_commit"], stages["lifecycle_result_build"], stages["total"],
    )



def _security_sse_payload(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "security.scan.heartbeat")
    data = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    lines: list[str] = []
    event_id = event.get("event_id")
    if event_type != "security.scan.heartbeat" and isinstance(event_id, int) and event_id > 0:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {data}")
    return "\n".join(lines) + "\n\n"


def _bounded_stream_number(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


async def _security_events_generator(request: Request):
    replay_limit = int(
        _bounded_stream_number(
            "POCKETLAB_SECURITY_PROGRESS_REPLAY_LIMIT", 200, 1, 500
        )
    )
    active_poll_seconds = _bounded_stream_number(
        "POCKETLAB_SECURITY_PROGRESS_SSE_ACTIVE_POLL_SECONDS", 1.25, 0.5, 5.0
    )
    idle_poll_seconds = max(
        active_poll_seconds,
        _bounded_stream_number(
            "POCKETLAB_SECURITY_PROGRESS_SSE_IDLE_POLL_SECONDS", 3.0, 1.0, 10.0
        ),
    )
    heartbeat_seconds = _bounded_stream_number(
        "POCKETLAB_SECURITY_PROGRESS_SSE_HEARTBEAT_SECONDS", 20.0, 15.0, 25.0
    )
    plan = lite_security.security_event_replay(
        request.headers.get("last-event-id"), replay_limit=replay_limit
    )
    last_sent_id = max(0, int(plan.get("resume_event_id") or 0))
    last_real_event_at = time.monotonic()
    active_scan = False
    emitted_initial_event = False

    for event in plan.get("events") or []:
        if await request.is_disconnected():
            return
        event_id = int(event.get("event_id") or 0)
        if event_id and event_id < last_sent_id:
            continue
        if event_id:
            last_sent_id = event_id
        active_scan = bool(event.get("active_scan"))
        last_real_event_at = time.monotonic()
        emitted_initial_event = True
        yield _security_sse_payload(event)

    if not emitted_initial_event:
        yield _security_sse_payload(lite_security.security_progress_heartbeat())
        last_real_event_at = time.monotonic()

    while True:
        if await request.is_disconnected():
            break
        rows = lite_security.list_security_progress_events_after(
            last_sent_id, limit=replay_limit
        )
        if rows:
            for row in rows:
                event = lite_security.security_progress_event_from_persisted(row)
                event_id = int(event.get("event_id") or 0)
                if event_id <= last_sent_id:
                    continue
                last_sent_id = event_id
                active_scan = bool(event.get("active_scan"))
                last_real_event_at = time.monotonic()
                yield _security_sse_payload(event)
            continue
        if (time.monotonic() - last_real_event_at) >= heartbeat_seconds:
            yield _security_sse_payload(lite_security.security_progress_heartbeat())
            last_real_event_at = time.monotonic()
        await asyncio.sleep(active_poll_seconds if active_scan else idle_poll_seconds)


def _lite_revision_sse_payload(event: dict[str, Any]) -> str:
    event_id = int(event.get("event_id") or 0)
    event_type = str(event.get("type") or "lite.revision.changed")[:80]
    data = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    lines = []
    if event_id > 0:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {data}")
    return "\n".join(lines) + "\n\n"


def _lite_revision_reset(
    reason: str, window: dict[str, Any], snapshot: dict[str, Any] | None = None
) -> dict[str, Any]:
    snapshot = snapshot or CONTROL_PLANE.revisions()
    return {
        "type": "lite.revision.reset",
        "event_id": int(window.get("latest_event_id") or 0),
        "database_instance": str(snapshot.get("database_instance") or ""),
        "reason": str(reason or "domain_state_changed")[:80],
        "revisions": snapshot.get("revisions") or {},
        "projection_version": int(snapshot.get("projection_version") or 1),
        "occurred_at": deps.now_utc_iso(),
        "sanitized": True,
    }


def _parse_lite_revision_cursor(value: Any) -> tuple[int, bool]:
    text = str(value or "").strip()
    if not text:
        return 0, False
    if len(text) > 32 or not text.isdigit():
        return 0, True
    try:
        cursor = int(text)
    except ValueError:
        return 0, True
    if cursor < 0 or cursor > 9_223_372_036_854_775_000:
        return 0, True
    return cursor, False


async def _lite_revision_events_generator(request: Request):
    poll_seconds = _bounded_stream_number(
        "POCKETLAB_LITE_REVISION_SSE_POLL_SECONDS", 1.5, 0.5, 10.0
    )
    keepalive_seconds = _bounded_stream_number(
        "POCKETLAB_LITE_REVISION_SSE_KEEPALIVE_SECONDS", 20.0, 15.0, 30.0
    )
    replay_limit = int(
        _bounded_stream_number(
            "POCKETLAB_LITE_REVISION_SSE_REPLAY_LIMIT", 100, 1, 100
        )
    )
    cursor, malformed = _parse_lite_revision_cursor(
        request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    )
    window = await asyncio.to_thread(CONTROL_PLANE.revision_event_window)
    instance = str(window.get("database_instance") or "")
    oldest = int(window.get("oldest_event_id") or 0)
    latest = int(window.get("latest_event_id") or 0)
    reset_reason = ""
    if malformed:
        reset_reason = "malformed_cursor"
    elif cursor > latest:
        reset_reason = "cursor_ahead"
    elif cursor > 0 and oldest > 0 and cursor < oldest - 1:
        reset_reason = "cursor_too_old"
    if reset_reason:
        snapshot = await asyncio.to_thread(CONTROL_PLANE.revisions)
        yield _lite_revision_sse_payload(
            _lite_revision_reset(reset_reason, window, snapshot)
        )
        cursor = latest

    last_keepalive = time.monotonic()
    while True:
        if await request.is_disconnected():
            return
        current_window = await asyncio.to_thread(CONTROL_PLANE.revision_event_window)
        current_instance = str(current_window.get("database_instance") or "")
        if current_instance != instance:
            snapshot = await asyncio.to_thread(CONTROL_PLANE.revisions)
            yield _lite_revision_sse_payload(
                _lite_revision_reset(
                    "database_instance_changed", current_window, snapshot
                )
            )
            instance = current_instance
            cursor = int(current_window.get("latest_event_id") or 0)
            last_keepalive = time.monotonic()
            continue
        events = await asyncio.to_thread(
            CONTROL_PLANE.revision_events_after, cursor, limit=replay_limit
        )
        if events:
            for event in events:
                if await request.is_disconnected():
                    return
                event_id = int(event.get("event_id") or 0)
                if event_id <= cursor:
                    continue
                cursor = event_id
                yield _lite_revision_sse_payload(event)
            last_keepalive = time.monotonic()
            continue
        if time.monotonic() - last_keepalive >= keepalive_seconds:
            yield ": keepalive\n\n"
            last_keepalive = time.monotonic()
        await asyncio.sleep(poll_seconds)


def _lite_revisions_response(request: Request, payload: dict[str, Any]) -> Response:
    etag = CONTROL_PLANE.revisions_etag(payload)
    headers = {
        "ETag": etag,
        "Cache-Control": "no-cache",
        "X-PocketLab-Database-Instance": str(payload.get("database_instance") or "")[:32],
        "X-PocketLab-Projection-Version": str(int(payload.get("projection_version") or 1)),
        "Server-Timing": (
            f"connection;dur={max(0.0, float(payload.get('connection_wait_ms') or 0.0)):.2f}, "
            f"sqlite;dur={max(0.0, float(payload.get('sqlite_query_ms') or 0.0)):.2f}"
        ),
    }
    if lite_security.if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)


class LiteCatalogInstallRequest(BaseModel):
    app_id: str = Field(default="", description="Catalog app id")
    target_node_id: str | None = Field(default=None, description="Target Lite device id. PhotoPrism is server-host only in this release.")
    version: str | None = None
    dry_run: bool = False
    requested_by: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class LiteCatalogRemoveRequest(BaseModel):
    app_id: str = Field(default="", description="Catalog app or blueprint id")
    confirm: bool = False
    requested_by: str | None = None


class LitePhotoPrismStorageMappingRequest(BaseModel):
    source_type: Literal["phone_media", "managed_media", "storage_device"] = "phone_media"
    label: str | None = None
    source_path: str = Field(default="", description="Approved Pocket Lab media folder path")
    target: Literal["import", "originals"] = "import"
    mode: Literal["read_only", "read_write"] = "read_only"
    device_id: str | None = None
    device_name: str | None = None


class LiteIdentityRotateRequest(BaseModel):
    target: str = "default"
    value: str | None = None
    lease_duration: str | None = None


class LiteIdentitySetupRequest(BaseModel):
    username: str = Field(default="owner", min_length=1, max_length=64)
    display_name: str = Field(default="Pocket Lab Owner", max_length=120)
    password: str = Field(min_length=12, max_length=256)
    setup_token: str = Field(min_length=1, max_length=512)


class LiteIdentityLoginRequest(BaseModel):
    username: str = Field(default="owner", min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LiteIdentityPasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class LiteIdentityRecoveryRequest(BaseModel):
    username: str = Field(default="owner", min_length=1, max_length=64)
    recovery_code: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=256)


class LiteSecurityScanRequest(BaseModel):
    scope: str = "local"
    reason: str | None = None
    profile: str = "quick"
    app_id: str | None = None


class LiteAppSecurityCheckRequest(BaseModel):
    reason: str | None = None


class LiteLifecycleDiagnosticsRequest(BaseModel):
    challenge_id: str = ""
    report: dict[str, Any] = Field(default_factory=dict)


class LiteAppBackupRequest(BaseModel):
    mode: Literal["config_only", "config_and_index", "full_with_media"] = "config_only"
    reason: str | None = None


class LiteAppRestorePreviewRequest(BaseModel):
    backup_id: str | None = None
    reason: str | None = None


class LiteAppUpdateRequest(BaseModel):
    reason: str | None = None


class LiteAppRestoreRequest(BaseModel):
    backup_id: str | None = None
    preview_id: str | None = None
    confirm: bool = False


class LiteAppActionRequest(BaseModel):
    reason: str | None = None
    target_device_id: str | None = None
    confirm: bool = False
    preserve_media: bool = True
    preserve_backups: bool = True
    preserve_evidence: bool = True
    preserve_storage_mappings: bool = True


class LiteAddDeviceRequest(BaseModel):
    role: Literal["compute", "storage"] = Field(
        default="compute",
        description="Lite device role: compute for App Host or storage for Storage Node",
    )
    hostname: str | None = None


class LiteDeviceDisplayModelRequest(BaseModel):
    consumer_model_name: str | None = Field(
        default=None,
        description="Optional display-only consumer device model; clear with null or an empty value.",
        max_length=80,
    )
    expected_profile_revision: int | None = Field(
        default=None,
        ge=0,
        description="Deprecated compatibility revision; display-label concurrency uses the expected label when provided.",
    )
    expected_consumer_model_name: str | None = Field(
        default=None,
        description="Optional display-label value originally shown to the user; empty string means no friendly label.",
        max_length=80,
    )


class LiteRemoveDeviceRequest(BaseModel):
    device_id: str = Field(default="", description="Lite device id to remove from saved records")
    confirm: bool = False
    reason: str | None = None
    requested_by: str | None = None
    assessment_revision: str = Field(default="", max_length=80)
    expected_awareness_revision: int | None = Field(default=None, ge=0)


class LiteInviteRevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=220)


class LitePolicyApplyRequest(BaseModel):
    protection_enabled: bool = False
    reason: str | None = None


class LiteBackupRequest(BaseModel):
    include_event_journal: bool = True
    include_app_data: bool = False
    reason: str | None = None
    dry_run: bool = False


class LiteBackupVerifyRequest(BaseModel):
    backup_id: str = "latest"
    reason: str | None = None


class LiteRestorePreviewRequest(BaseModel):
    backup_id: str = "latest"
    reason: str | None = None


class LiteRestoreRequest(BaseModel):
    backup_id: str | None = None
    backup_ref: str = "latest"
    preview_id: str | None = None
    confirm: bool = False
    dry_run: bool = False


class LiteDatabaseBackupRequest(BaseModel):
    reason: str | None = None


class LiteDatabaseRestoreRequest(BaseModel):
    model_config = {"extra": "forbid"}

    backup_id: str
    preview_id: str
    confirm: bool = False


class LiteRetentionRequest(BaseModel):
    dry_run: bool = True
    max_batches: int = Field(default=1, ge=1, le=100)


class LiteCheckpointRequest(BaseModel):
    mode: Literal["passive", "truncate"] = "passive"
    confirm_controlled: bool = False


def _operation_payload(operation: str, target: dict[str, Any], params: dict[str, Any], *, dry_run: bool = False) -> tuple[OperationRequest, dict[str, Any]]:
    raw = {
        "operation": operation,
        "target": target,
        "params": params,
        "dry_run": dry_run,
        "source": "lite-api",
    }
    return deps.normalize_operation_request(raw), raw


def _safe_duplicate_conflict_payload(conflict: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": conflict.get("device_id"),
        "device_name": conflict.get("device_name"),
        "role": conflict.get("role"),
        "status": conflict.get("status"),
        "connection": conflict.get("connection"),
        "source": conflict.get("source"),
        "can_remove_old_record": bool(conflict.get("can_remove_old_record")),
    }


def _duplicate_device_detail(conflict: dict[str, Any]) -> dict[str, Any]:
    status = str(conflict.get("status") or "unknown").lower()
    connection = str(conflict.get("connection") or "unknown").lower()
    can_remove = bool(conflict.get("can_remove_old_record"))
    if connection == "online" or status in {"healthy", "active", "online", "ready"}:
        message = "This device is already connected. Use a different name if this is another phone."
    elif status in {"pending", "invited"} or connection == "waiting":
        message = "An invite for this device is already in progress. Use the existing invite or wait for the device to connect."
    elif status in {"joining", "accepted"} or connection == "joining":
        message = "This device is already joining. Use the existing invite or wait for the device to connect."
    elif can_remove:
        message = "An old device record already uses this name. Remove the old device record before creating a new invite."
    else:
        message = "Choose a different name, or refresh the Devices list before trying again."
    return {
        "status": "duplicate_device",
        "summary": "A device with this name already exists.",
        "message": message,
        "existing_device": _safe_duplicate_conflict_payload(conflict),
        "safe_next_actions": [
            "Use a different device name",
            "Refresh the Devices list",
            "Remove the old device record if it is no longer used",
        ],
    }


def _candidate_device_name(payload: LiteAddDeviceRequest) -> str:
    if (payload.hostname or "").strip():
        return str(payload.hostname).strip()
    role_info = lite_invites.role_metadata(payload.role)
    return f"Pocket Lab {role_info['role_label']}"


def _phase3b_prepared_read(request: Request, projection_domain: str, *, view_model: str) -> Response:
    parent, key = projection_domain.split(".", 1)
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain=parent,
            key=key,
            snapshot_builder=lambda: lite_phase3b_projections.snapshot(projection_domain),
            builder=lite_phase3b_projections.builder_for(projection_domain),
            projector=lambda payload: lite_phase3b_projections.project(projection_domain, payload),
            stale_after_ms=15_000 if projection_domain in {"security.progress", "system.nats_remote"} else 30_000,
            max_stale_ms=5 * 60_000,
            deadline_seconds=10.0,
            priority=20,
            work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain=projection_domain, view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


def _phase3c_prepared_read(request: Request, projection_domain: str, *, view_model: str) -> Response:
    parent, key = projection_domain.split(".", 1)
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain=parent,
            key=key,
            snapshot_builder=lambda: lite_phase3c_projections.snapshot(projection_domain),
            builder=lite_phase3c_projections.builder_for(projection_domain),
            projector=lambda payload: lite_phase3c_projections.project(projection_domain, payload),
            stale_after_ms=60_000,
            max_stale_ms=10 * 60_000,
            deadline_seconds=10.0,
            priority=30,
            work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain=projection_domain, view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


def _phase3c_activity_summary_read(request: Request) -> Response:
    reads: dict[str, PreparedRead] = {}
    for projection_domain in ("system.activity_current", "system.activity_history"):
        parent, key = projection_domain.split(".", 1)
        try:
            reads[projection_domain] = CONTROL_PLANE.prepared_only_read(
                domain=parent,
                key=key,
                snapshot_builder=lambda selected=projection_domain: lite_phase3c_projections.snapshot(selected),
                builder=lite_phase3c_projections.builder_for(projection_domain),
                projector=lambda payload, selected=projection_domain: lite_phase3c_projections.project(selected, payload),
                stale_after_ms=60_000,
                max_stale_ms=10 * 60_000,
                deadline_seconds=10.0,
                priority=30,
                work_class="io",
            )
        except PreparedProjectionUnavailable:
            if projection_domain == "system.activity_current":
                return _projection_warming_response(
                    domain=projection_domain,
                    view_model="lite-activity-summary-phase3c-v2",
                )
    current_read = reads["system.activity_current"]
    history_read = reads.get("system.activity_history")
    payload = lite_phase3c_projections.compose_activity_summary(
        dict(current_read.payload),
        dict(history_read.payload) if history_read is not None else {},
    )
    payload["history_available"] = history_read is not None
    payload["projection_only"] = True
    timing_keys = (
        "connection_acquisition_ms",
        "sqlite_query_ms",
        "projection_build_ms",
        "serialization_ms",
    )
    timing = {
        key: float(current_read.timing.get(key, 0.0))
        + float(history_read.timing.get(key, 0.0) if history_read else 0.0)
        for key in timing_keys
    }
    composed = PreparedRead(
        payload=payload,
        etag=lite_security.compact_response_etag(
            {
                "current": current_read.etag,
                "history": history_read.etag if history_read else "missing",
            }
        ),
        source_revision=int(payload.get("source_revision") or 0),
        projection_age_ms=max(
            int(current_read.projection_age_ms),
            int(history_read.projection_age_ms) if history_read else 0,
        ),
        read_degraded=bool(
            current_read.read_degraded
            or history_read is None
            or (history_read.read_degraded if history_read else False)
        ),
        refresh_pending=bool(
            current_read.refresh_pending
            or (history_read.refresh_pending if history_read else True)
        ),
        retry_after_seconds=max(
            int(current_read.retry_after_seconds),
            int(history_read.retry_after_seconds) if history_read else 2,
        ),
        timing=timing,
    )
    return _control_plane_prepared_response(
        request, composed, view_model="lite-activity-summary-phase3c-v2"
    )


@router.get("/status")
def get_lite_status(request: Request) -> Response:
    deps.require_auth(request)
    response = _phase3b_prepared_read(
        request, "system.status", view_model="lite-status-phase3b-v1"
    )
    if response.status_code == 503:
        return JSONResponse(
            content=lite_status.default_lite_status_state(),
            headers={
                "Cache-Control": "no-cache",
                "Retry-After": "2",
                "X-PocketLab-View-Model": "lite-status-phase3b-v1",
                "X-PocketLab-Read-Degraded": "true",
                "X-PocketLab-Refresh-Pending": "true",
            },
        )
    return response


@router.get("/system/health")
def get_lite_system_health(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3b_prepared_read(
        request, "system.health", view_model="lite-system-health-phase3b-v1"
    )


@router.get("/system/processes")
def get_lite_system_processes(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3b_prepared_read(
        request, "system.processes", view_model="lite-system-processes-phase3b-v1"
    )


@router.get("/system/agent")
def get_lite_system_agent(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3b_prepared_read(
        request, "system.agent", view_model="lite-system-agent-phase3b-v1"
    )


@router.get("/system/supervisor")
def get_lite_system_supervisor(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3b_prepared_read(
        request, "system.supervisor", view_model="lite-system-supervisor-phase3b-v1"
    )


@router.get("/remote-access/readiness")
def get_lite_remote_access_readiness(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3b_prepared_read(
        request, "system.remote_access", view_model="lite-remote-access-phase3b-v1"
    )


def _nats_readiness_snapshot_fallback(request: Request) -> Response:
    """Serve the last committed sanitized NATS readiness snapshot on read-path faults."""
    payload = lite_phase3b_projections.snapshot("system.nats_remote")
    if not isinstance(payload, dict) or not payload:
        return _projection_warming_response(
            domain="system.nats_remote",
            view_model="lite-nats-readiness-phase3b-v1",
        )
    fallback = dict(payload)
    fallback.update({
        "projection_only": True,
        "read_degraded": True,
        "refresh_pending": True,
        "retry_after_seconds": 2,
        "semantic_source_revision": int(fallback.get("source_revision") or 0),
        "stored_projection_revision": int(fallback.get("projection_revision") or 0),
        "scheduler_generation": int(fallback.get("generation") or 0),
    })
    etag = lite_security.compact_response_etag(fallback)
    headers = {
        "ETag": etag,
        "Cache-Control": "no-cache",
        "Retry-After": "2",
        "X-PocketLab-View-Model": "lite-nats-readiness-phase3b-v1",
        "X-PocketLab-Read-Degraded": "true",
        "X-PocketLab-Refresh-Pending": "true",
        "X-PocketLab-Fallback": "prepared-snapshot",
    }
    if lite_security.if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=fallback, headers=headers)


@router.get("/system/nats-readiness")
def get_lite_nats_readiness(request: Request) -> Response:
    deps.require_auth(request)
    try:
        return _phase3b_prepared_read(
            request, "system.nats_remote", view_model="lite-nats-readiness-phase3b-v1"
        )
    except Exception as exc:
        # NATS readiness is a read-only operator surface. Preserve availability
        # from the last committed sanitized projection instead of leaking a 500
        # when scheduler/cache metadata is temporarily inconsistent.
        _LOGGER.warning(
            "pocketlab.nats_readiness.prepared_read_degraded error_type=%s",
            type(exc).__name__,
        )
        return _nats_readiness_snapshot_fallback(request)


def _build_lite_catalog_projection() -> dict[str, Any]:
    return lite_app_lifecycle.hydrate_catalog_lifecycle(
        lite_catalog_live.hydrate_catalog(lite_catalog.catalog_payload(None))
    )


@router.get("/system/telemetry-thresholds")
def get_lite_telemetry_thresholds(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3c_prepared_read(
        request, "system.telemetry_thresholds", view_model="lite-telemetry-thresholds-phase3c-v1"
    )


@router.get("/system/storage-pressure")
def get_lite_storage_pressure(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3c_prepared_read(
        request, "system.storage_pressure", view_model="lite-storage-pressure-phase3c-v1"
    )


@router.get("/system/sqlite-health")
def get_lite_sqlite_health(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3c_prepared_read(
        request, "system.sqlite_health", view_model="lite-sqlite-health-phase3c-v1"
    )


@router.get("/system/activity-summary")
def get_lite_activity_summary(request: Request) -> Response:
    deps.require_auth(request)
    return _phase3c_activity_summary_read(request)


@router.get("/catalog")
def get_lite_catalog(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "catalog-prepared-e3-v1"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="apps",
            key="catalog",
            snapshot_builder=CONTROL_PLANE.app_catalog_projection_snapshot,
            builder=_build_lite_catalog_projection,
            projector=CONTROL_PLANE.project_app_catalog,
            stale_after_ms=30_000,
            max_stale_ms=5 * 60_000,
            deadline_seconds=8.0,
            priority=45,
            work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="apps", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)



@router.get("/apps/lifecycle")
def get_lite_app_lifecycle_profiles(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "apps-lifecycle-sqlite-p3-v2"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="apps",
            key="lifecycle",
            snapshot_builder=CONTROL_PLANE.app_lifecycle_projection_snapshot,
            builder=lite_app_lifecycle.app_lifecycle_profiles,
            projector=CONTROL_PLANE.project_app_lifecycle,
            stale_after_ms=15_000,
            max_stale_ms=90_000,
            deadline_seconds=8.0,
            priority=40,
            work_class="cpu",
        )
    except (PreparedProjectionUnavailable, TimeoutError):
        return _projection_warming_response(domain="apps", view_model=view_model)
    except Exception as exc:
        _LOGGER.warning(
            "pocketlab.apps.lifecycle.read_degraded error_type=%s",
            type(exc).__name__,
            exc_info=True,
        )
        return _projection_warming_response(domain="apps", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


@router.get("/apps/{app_id}/action-history")
def get_lite_app_action_history(
    app_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str = Query("", max_length=512),
) -> Response:
    deps.require_auth(request)
    try:
        payload = CONTROL_PLANE.app_action_history(app_id, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _control_plane_history_response(
        request, payload, domain="apps", key=f"action-history:{app_id}:{limit}:{cursor}"
    )


@router.get("/apps/lifecycle/{app_id}")
def get_lite_app_lifecycle_profile(app_id: str, request: Request) -> Response:
    deps.require_auth(request)
    app_id = _require_supported_app_id(app_id)
    view_model = "app-lifecycle-prepared-e3-v1"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="apps", key="lifecycle",
            snapshot_builder=CONTROL_PLANE.app_lifecycle_projection_snapshot,
            builder=lite_app_lifecycle.app_lifecycle_profiles,
            projector=CONTROL_PLANE.project_app_lifecycle,
            stale_after_ms=15_000, max_stale_ms=90_000,
            deadline_seconds=8.0, priority=35, work_class="cpu",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="apps", view_model=view_model)
    apps = [item for item in (prepared.payload.get("apps") or prepared.payload.get("items") or []) if isinstance(item, dict)]
    match = next((item for item in apps if str(item.get("app_id") or item.get("id")) == app_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="App lifecycle state is not available.")
    selected = PreparedRead(
        payload=match, etag=prepared.etag, source_revision=prepared.source_revision,
        projection_age_ms=prepared.projection_age_ms, read_degraded=prepared.read_degraded,
        refresh_pending=prepared.refresh_pending, timing=prepared.timing,
        retry_after_seconds=prepared.retry_after_seconds,
    )
    return _control_plane_prepared_response(request, selected, view_model=view_model)


def _require_supported_app_id(app_id: str) -> str:
    normalized = str(app_id or "").strip().lower()
    if normalized not in lite_app_actions.SUPPORTED_APP_IDS:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "PhotoPrism is the first app supported by Pocket Lab Lite."},
        )
    return normalized


def _saved_app_actions(app_id: str) -> dict[str, Any] | None:
    saved = CONTROL_PLANE.app_current_subprojections(app_id)
    if not saved:
        return None
    operations = saved.get("operations") if isinstance(saved.get("operations"), dict) else {}
    if not operations:
        return None
    return {
        **operations, "app_id": app_id, "projection_only": True,
        "updated_at": saved.get("updated_at"),
        "summary": operations.get("summary") or "Showing the latest saved app actions.",
    }


@router.get("/apps/{app_id}/actions")
def get_lite_app_actions(app_id: str, request: Request) -> Response:
    deps.require_auth(request)
    app_id = _require_supported_app_id(app_id)
    view_model = "app-actions-prepared-e3-v1"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="apps", key=f"actions:{app_id}",
            snapshot_builder=lambda: CONTROL_PLANE.app_actions_projection_snapshot(app_id),
            builder=lambda: lite_app_actions.app_actions(app_id),
            projector=lambda payload: lite_core_projections.project_app_actions_payload(app_id, payload),
            stale_after_ms=15_000, max_stale_ms=90_000,
            deadline_seconds=6.0, priority=30, work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="apps", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


@router.get("/apps/{app_id}/evidence")
def get_lite_app_evidence(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    payload = lite_evidence_receipts.app_evidence(app_id)
    payload.update({
        "backend_only": True,
        "debug_only": True,
        "normal_ui_dependency": False,
        "summary": "Backend troubleshooting records are available for support and recovery review. The normal App Catalog UI does not load this endpoint.",
    })
    return payload


def _saved_app_subprojection(app_id: str, name: str) -> dict[str, Any] | None:
    saved = CONTROL_PLANE.app_current_subprojections(app_id)
    if not saved:
        return None
    value = saved.get(name) if isinstance(saved.get(name), dict) else {}
    if not value:
        return None
    if value.get("kind") == "raw" and isinstance(value.get("payload"), dict):
        payload = dict(value["payload"])
    elif value.get("kind") == "profile":
        payload = dict(value.get(name) or {}) if isinstance(value.get(name), dict) else dict(value)
        if name == "backup" and isinstance(value.get("recovery"), dict):
            payload.setdefault("recovery", value["recovery"])
    else:
        payload = dict(value)
    payload.update({
        "app_id": app_id,
        "projection_only": True,
        "updated_at": payload.get("updated_at") or saved.get("updated_at"),
    })
    return payload


@router.get("/apps/{app_id}/update")
def get_lite_app_update_status(app_id: str, request: Request) -> Response:
    deps.require_auth(request)
    app_id = _require_supported_app_id(app_id)
    view_model = "app-update-prepared-e3-v1"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="apps", key=f"update:{app_id}",
            snapshot_builder=lambda: _saved_app_subprojection(app_id, "update"),
            builder=lambda: lite_app_update.update_status(app_id),
            projector=lambda payload: CONTROL_PLANE.update_app_subprojection(app_id, "update", payload),
            stale_after_ms=30_000, max_stale_ms=180_000,
            deadline_seconds=6.0, priority=45, work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="apps", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


@router.get("/apps/{app_id}/update/receipts/{operation_id}")
def get_lite_app_update_receipt(app_id: str, operation_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    receipt = lite_app_update.update_receipt(app_id, operation_id)
    if not receipt:
        raise HTTPException(status_code=404, detail={"status": "not_found", "summary": "Update readiness receipt was not found."})
    return receipt


@router.post("/apps/{app_id}/update/apply", status_code=409)
def apply_lite_app_update(app_id: str, payload: LiteAppUpdateRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_update.apply_update_disabled(app_id)


@router.get("/apps/{app_id}/backup")
def get_lite_app_backup_status(app_id: str, request: Request) -> Response:
    deps.require_auth(request)
    app_id = _require_supported_app_id(app_id)
    view_model = "app-backup-prepared-e3-v1"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="apps", key=f"backup:{app_id}",
            snapshot_builder=lambda: _saved_app_subprojection(app_id, "backup"),
            builder=lambda: lite_app_backup.app_backup_status(app_id),
            projector=lambda payload: CONTROL_PLANE.update_app_subprojection(app_id, "backup", payload),
            stale_after_ms=30_000, max_stale_ms=180_000,
            deadline_seconds=6.0, priority=55, work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="apps", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


@router.post("/apps/{app_id}/backup", status_code=202)
async def start_lite_app_backup(app_id: str, payload: LiteAppBackupRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command = lite_app_backup.app_backup_command(app_id, mode=payload.mode, reason=payload.reason)
    try:
        submitted = await submit_domain_command(
            lite_app_backup.APP_BACKUP_CREATE_SUBJECT,
            "lite.app.backup.queued",
            command,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "app_backup_queue_unavailable",
                "summary": "App backup request could not be queued because the local command bus is not reachable.",
                "detail": str(exc),
            },
        ) from exc
    pending = lite_app_backup.record_backup_request(command)
    submitted.update({
        "accepted": True,
        "status": submitted.get("status") or "queued",
        "app_id": "photoprism",
        "action_id": "backup_app",
        "backup_id": command["backup_id"],
        "mode": command["app_backup_mode"],
        "pending_backup": pending,
        "summary": "Backing up PhotoPrism app settings.",
        "progress": {"phase": "queued", "step": "Backup queued.", "bounded": True},
        "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend record pending."},
    })
    return submitted


@router.get("/apps/{app_id}/backups")
def list_lite_app_backups(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_backup.list_app_backups(app_id)


@router.get("/apps/{app_id}/backups/{backup_id}/receipt")
def get_lite_app_backup_receipt(app_id: str, backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    receipt = lite_app_backup.app_backup_receipt(app_id, backup_id)
    if not receipt:
        raise HTTPException(status_code=404, detail={"status": "not_found", "summary": "App backup receipt was not found."})
    return receipt


@router.post("/apps/{app_id}/restore/preview", status_code=202)
async def start_lite_app_restore_preview(app_id: str, payload: LiteAppRestorePreviewRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command = lite_app_backup.app_restore_preview_command(app_id, backup_id=payload.backup_id or "latest", reason=payload.reason)
    try:
        submitted = await submit_domain_command(
            lite_app_backup.APP_RESTORE_PREVIEW_SUBJECT,
            "lite.app.restore.preview_queued",
            command,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "app_restore_preview_queue_unavailable",
                "summary": "Restore preview could not be queued because the local command bus is not reachable.",
                "detail": str(exc),
            },
        ) from exc
    pending = lite_app_backup.record_restore_preview_request(command)
    submitted.update({
        "accepted": True,
        "status": submitted.get("status") or "queued",
        "app_id": "photoprism",
        "action_id": "preview_restore",
        "backup_id": command["backup_id"],
        "preview_id": command["preview_id"],
        "pending_restore_preview": pending,
        "summary": "Preparing PhotoPrism restore preview.",
        "progress": {"phase": "queued", "step": "Restore preview queued.", "bounded": True},
        "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend record pending."},
    })
    return submitted


@router.get("/apps/{app_id}/restore/previews/{preview_id}")
def get_lite_app_restore_preview(app_id: str, preview_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    preview = lite_app_backup.get_app_restore_preview(app_id, preview_id)
    if not preview:
        raise HTTPException(status_code=404, detail={"status": "not_found", "summary": "App restore preview was not found."})
    return preview


@router.post("/apps/{app_id}/backup/storage-device")
def start_lite_app_backup_to_storage_device(app_id: str, payload: LiteAppActionRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_backup.backup_to_storage_readiness(app_id, payload.target_device_id, reason=payload.reason)


@router.post("/apps/{app_id}/actions/{action_id}")
async def run_lite_app_action(app_id: str, action_id: str, payload: LiteAppActionRequest, request: Request) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    action = lite_app_actions.prepare_action(app_id, action_id, payload=_lite_payload_dict(payload))
    kind = action.get("kind")

    if kind in {"url", "guidance"}:
        return {key: value for key, value in action.items() if key != "kind"}

    if kind == "backup":
        command = action["command"]
        try:
            submitted = await submit_domain_command(
                lite_app_backup.APP_BACKUP_CREATE_SUBJECT,
                "lite.app.backup.queued",
                command,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "app_backup_queue_unavailable",
                    "summary": "App backup request could not be queued because the local command bus is not reachable.",
                    "detail": str(exc),
                },
            ) from exc
        pending = lite_app_backup.record_backup_request(command)
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": "backup_app",
            "backup_id": command["backup_id"],
            "mode": command["app_backup_mode"],
            "pending_backup": pending,
            "summary": "Backing up PhotoPrism app settings.",
            "progress": {"phase": "queued", "step": "Backup queued.", "bounded": True},
            "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend record pending."},
        })
        return submitted

    if kind == "restore_preview":
        command = action["command"]
        try:
            submitted = await submit_domain_command(
                lite_app_backup.APP_RESTORE_PREVIEW_SUBJECT,
                "lite.app.restore.preview_queued",
                command,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "app_restore_preview_queue_unavailable",
                    "summary": "Restore preview could not be queued because the local command bus is not reachable.",
                    "detail": str(exc),
                },
            ) from exc
        pending = lite_app_backup.record_restore_preview_request(command)
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": "preview_restore",
            "backup_id": command["backup_id"],
            "preview_id": command["preview_id"],
            "pending_restore_preview": pending,
            "summary": "Preparing PhotoPrism restore preview.",
            "progress": {"phase": "queued", "step": "Restore preview queued.", "bounded": True},
            "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend record pending."},
        })
        return submitted

    if kind == "update_check":
        command = action["command"]
        subject = action.get("subject") or lite_app_update.APP_UPDATE_CHECK_SUBJECT
        await ensure_worker_execution_ready()
        pending = lite_app_update.record_update_request(command)
        try:
            submitted = await submit_domain_command(
                subject,
                "lite.app.update.check_queued",
                command,
                trace_id=command.get("command_id"),
            )
        except Exception:
            state = lite_app_update._read_state()
            if isinstance(state.get("pending_update_check"), dict) and state["pending_update_check"].get("command_id") == command.get("command_id"):
                state["pending_update_check"] = None
                lite_app_update._write_state(state)
            raise
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": "update_app",
            "operation_id": command["operation_id"],
            "command_id": command["command_id"],
            "pending_update_check": pending,
            "summary": "Checking PhotoPrism update readiness.",
            "progress": pending.get("progress") or {"phase": "queued", "step": "Update check queued.", "bounded": True},
            "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend record pending."},
        })
        return submitted

    if kind == "security_app_check":
        command = action["command"]
        await ensure_worker_execution_ready()
        lite_security.record_queued_run(command)
        try:
            submitted = await submit_domain_command(
                lite_security.policy.COMMAND_SUBJECT,
                "lite.security.app_check.requested",
                command,
                trace_id=command.get("command_id"),
            )
        except Exception:
            lite_security.discard_queued_run(command.get("run_id") or command.get("command_id"))
            raise
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": "check_app",
            "run_id": command.get("run_id"),
            "scan_profile": lite_security.policy.SCAN_PROFILE_APP,
            "summary": "Checking PhotoPrism safety.",
            "progress": {"phase": "queued", "step": "App Check queued.", "bounded": True},
            "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend App Check record pending."},
        })
        return submitted

    if kind == "media":
        command = action["command"]
        try:
            submitted = await submit_domain_command(
                lite_photoprism_media.MEDIA_COMMAND_SUBJECT,
                "lite.app.media.queued",
                command,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "media_action_queue_unavailable",
                    "summary": "PhotoPrism media action could not be queued because the local command bus is not reachable.",
                    "detail": str(exc),
                },
            ) from exc
        operation = lite_photoprism_media.record_operation(command, status="queued")
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": command["action_id"],
            "media_operation": operation,
            "summary": action.get("summary") or operation.get("summary") or "PhotoPrism media action queued.",
            "progress": operation.get("progress") or {"phase": "queued", "step": "Import photos queued.", "bounded": True},
            "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend media record pending."},
        })
        return submitted

    if kind == "app_operation":
        command = action["command"]
        subject = action.get("subject") or lite_app_operations.subject_for_action(command.get("action_id"))
        await ensure_worker_execution_ready()
        operation = lite_app_operations.record_queued_operation(command)
        try:
            submitted = await submit_domain_command(
                subject,
                "lite.app.operation.queued",
                command,
                trace_id=command.get("command_id"),
            )
        except Exception as exc:
            lite_app_operations.mark_operation_failed(command, "App action could not be queued safely.")
            raise
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": command["action_id"],
            "operation": operation,
            "summary": action.get("summary") or operation.get("summary") or "App action queued.",
            "progress": operation.get("progress") or {"phase": "queued", "step": "Request queued.", "bounded": True},
            "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend record pending."},
        })
        return submitted

    if kind == "media_fast_forward":
        response = action.get("response") if isinstance(action.get("response"), dict) else {}
        response.setdefault("accepted", True)
        response.setdefault("status", "skipped")
        response.setdefault("app_id", "photoprism")
        response.setdefault("action_id", "index_photos")
        response.setdefault("fast_forwarded", True)
        return response

    if kind == "cancel_media":
        response = action.get("response") if isinstance(action.get("response"), dict) else {}
        response.setdefault("accepted", True)
        response.setdefault("status", "cancelled")
        response.setdefault("app_id", "photoprism")
        response.setdefault("action_id", "cancel_media")
        return response

    if kind == "install_app":
        command = action["command"]
        policy_revision = hashlib.sha256(
            json.dumps(
                {
                    "app_id": command.get("app_id"),
                    "target_node_id": command.get("target_node_id"),
                    "action_id": "install_app",
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:24]
        policy_decision = await _enforce_lite_policy(
            auth_context=auth_context,
            action_id="catalog.install",
            target_type="app",
            target_id=str(command.get("app_id") or app_id),
            target_revision=policy_revision,
            target={
                "target_node_id": command.get("target_node_id"),
                "dry_run": bool(command.get("dry_run")),
                "already_installed": False,
            },
            correlation_id=str(command.get("operation_id") or uuid.uuid4().hex),
        )
        await ensure_worker_execution_ready()
        lite_catalog.record_install_queued(command)
        try:
            queued = await submit_domain_command(
                lite_catalog.COMMAND_SUBJECT,
                "lite.catalog.install.requested",
                command,
                trace_id=command["operation_id"],
            )
        except Exception:
            lite_catalog.discard_operation(command["operation_id"])
            raise
        queued.update({
            "accepted": True,
            "status": "queued",
            "app_id": "photoprism",
            "action_id": "install_app",
            "operation_id": command["operation_id"],
            "summary": "PhotoPrism install started.",
            "progress": {"phase": "queued", "step": "Install queued.", "bounded": True},
            "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend install record pending."},
            "authorization": {
                "decision_id": policy_decision.get("decision_id"),
                "reason_code": policy_decision.get("reason_code"),
                "policy_revision": policy_decision.get("policy_revision"),
            },
        })
        return queued

    if kind == "backup_to_storage_readiness":
        return action["response"]

    if kind == "backup_to_storage_not_implemented":
        raise HTTPException(status_code=501, detail=action["response"])

    if kind == "remove_not_implemented":
        raise HTTPException(status_code=501, detail=action["response"])

    if kind == "repair_not_implemented":
        raise HTTPException(status_code=501, detail=action["response"])

    raise HTTPException(
        status_code=501,
        detail={
            "status": "not_implemented",
            "summary": "This app action is not implemented yet.",
        },
    )


@router.get("/apps/photoprism/storage-preview")
def get_photoprism_storage_preview(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_storage.photoprism_storage_preview()


@router.get("/apps/photoprism/storage-mappings")
def get_photoprism_storage_mappings(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_storage.list_mappings("photoprism")


@router.post("/apps/photoprism/storage-mappings", status_code=201)
def create_photoprism_storage_mapping(payload: LitePhotoPrismStorageMappingRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_storage.create_mapping(_lite_payload_dict(payload))


@router.delete("/apps/photoprism/storage-mappings/{mapping_id}")
def delete_photoprism_storage_mapping(mapping_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_storage.delete_mapping("photoprism", mapping_id)


@router.post("/catalog/install", status_code=202)
async def install_lite_catalog_item(payload: LiteCatalogInstallRequest, request: Request) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    app_ref = (payload.app_id or "").strip()
    if not app_ref:
        raise HTTPException(status_code=400, detail="Choose an app to install.")
    params = {**payload.params}
    if payload.version:
        params["version"] = payload.version

    command = lite_catalog.install_command(
        app_ref,
        payload.target_node_id,
        requested_by=payload.requested_by,
        dry_run=payload.dry_run,
        params=params,
    )
    if command.get("already_installed"):
        return lite_catalog.already_installed_response(command)

    policy_revision = hashlib.sha256(
        json.dumps(
            {
                "app_id": command.get("app_id"),
                "target_node_id": command.get("target_node_id"),
                "version": params.get("version"),
                "dry_run": bool(payload.dry_run),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]
    policy_decision = await _enforce_lite_policy(
        auth_context=auth_context,
        action_id="catalog.install",
        target_type="app",
        target_id=str(command.get("app_id") or app_ref),
        target_revision=policy_revision,
        target={
            "target_node_id": command.get("target_node_id"),
            "dry_run": bool(payload.dry_run),
            "already_installed": False,
        },
        correlation_id=str(command.get("operation_id") or uuid.uuid4().hex),
    )

    await ensure_worker_execution_ready()
    lite_catalog.record_install_queued(command)
    try:
        queued = await submit_domain_command(
            lite_catalog.COMMAND_SUBJECT,
            "lite.catalog.install.requested",
            command,
            trace_id=command["operation_id"],
        )
    except Exception:
        lite_catalog.discard_operation(command["operation_id"])
        raise
    queued.update(
        {
            "accepted": True,
            "status": "queued",
            "operation_id": command["operation_id"],
            "app_id": lite_catalog.PHOTOPRISM_APP_ID,
            "target_node_id": command["target_node_id"],
            "message": "PhotoPrism install started.",
            "authorization": {
                "decision_id": policy_decision.get("decision_id"),
                "reason_code": policy_decision.get("reason_code"),
                "policy_revision": policy_decision.get("policy_revision"),
            },
        }
    )
    return queued


@router.post("/catalog/remove", status_code=501)
def remove_lite_catalog_item(payload: LiteCatalogRemoveRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    # The uploaded source does not currently prove a remove_blueprint/remove_app typed operation.
    # Keep the endpoint explicit and friendly instead of pretending removal is implemented.
    return {
        "status": "not_implemented",
        "accepted": False,
        "summary": "Remove is not enabled yet because the lite operation contract has not been added.",
        "app_id": payload.app_id,
        "next_step": "Add and validate a remove_blueprint typed operation before enabling this action.",
    }


@router.get("/identity")
def get_lite_identity(request: Request, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return _identity_projection(request)


@router.post("/identity/setup", status_code=201)
def setup_lite_identity(payload: LiteIdentitySetupRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        lite_identity_auth.setup_owner(
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
            setup_token=payload.setup_token,
        )
        session = lite_identity_auth.login(
            username=payload.username,
            password=payload.password,
            source=_request_source(request),
        )
    except lite_identity_auth.IdentityError as exc:
        _raise_identity_error(exc)
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    auth_context = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_identity_auth.identity_projection(auth_context)
    projection["csrf_token"] = session["csrf_token"]
    projection["setup_completed"] = True
    return projection


@router.post("/identity/login")
def login_lite_identity(payload: LiteIdentityLoginRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        session = lite_identity_auth.login(
            username=payload.username,
            password=payload.password,
            source=_request_source(request),
        )
    except lite_identity_auth.IdentityError as exc:
        _raise_identity_error(exc)
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    auth_context = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_identity_auth.identity_projection(auth_context)
    projection["csrf_token"] = session["csrf_token"]
    return projection


@router.post("/identity/logout")
def logout_lite_identity(request: Request, response: Response) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    actor = auth_context.get("actor") or {}
    session = auth_context.get("session") or {}
    if actor.get("type") != "human" or not session.get("session_id"):
        raise HTTPException(status_code=403, detail={"reason_code": "human_session_required", "message": "A signed-in owner session is required."})
    lite_identity_auth.logout(human_id=str(actor["identity_id"]), session_id=str(session["session_id"]))
    _clear_identity_cookie(response)
    return {"status": "signed_out", "summary": "Signed out of Pocket Lab."}


@router.post("/identity/password")
def change_lite_identity_password(payload: LiteIdentityPasswordRequest, request: Request, response: Response) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    actor = auth_context.get("actor") or {}
    session_context = auth_context.get("session") or {}
    if actor.get("type") != "human" or not session_context.get("session_id"):
        raise HTTPException(status_code=403, detail={"reason_code": "human_session_required", "message": "A signed-in owner session is required."})
    try:
        session = lite_identity_auth.change_password(
            human_id=str(actor["identity_id"]),
            session_id=str(session_context["session_id"]),
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except lite_identity_auth.IdentityError as exc:
        _raise_identity_error(exc)
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "changed",
        "summary": "Password changed. Other owner sessions were signed out.",
        "csrf_token": session["csrf_token"],
    }


@router.post("/identity/sessions/revoke-others")
def revoke_other_lite_identity_sessions(request: Request, response: Response) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    actor = auth_context.get("actor") or {}
    session_context = auth_context.get("session") or {}
    if actor.get("type") != "human" or not session_context.get("session_id"):
        raise HTTPException(status_code=403, detail={"reason_code": "human_session_required", "message": "A signed-in owner session is required."})
    count = lite_identity_auth.revoke_other_sessions(
        human_id=str(actor["identity_id"]), current_session_id=str(session_context["session_id"])
    )
    response.headers["Cache-Control"] = "no-store"
    return {"status": "completed", "revoked_sessions": count, "summary": "Other owner sessions were signed out."}


@router.delete("/identity/sessions/{session_id}")
def revoke_lite_identity_session(session_id: str, request: Request, response: Response) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    actor = auth_context.get("actor") or {}
    current = auth_context.get("session") or {}
    if actor.get("type") != "human":
        raise HTTPException(status_code=403, detail={"reason_code": "human_session_required", "message": "A signed-in owner session is required."})
    revoked = lite_identity_auth.revoke_session(human_id=str(actor["identity_id"]), session_id=session_id)
    if not revoked:
        raise HTTPException(status_code=404, detail={"reason_code": "session_not_found", "message": "That session is no longer active."})
    if session_id == current.get("session_id"):
        _clear_identity_cookie(response)
    else:
        response.headers["Cache-Control"] = "no-store"
    return {"status": "revoked", "session_id": session_id, "summary": "Session signed out."}


@router.post("/identity/recovery/regenerate")
def regenerate_lite_identity_recovery(request: Request, response: Response) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    actor = auth_context.get("actor") or {}
    session_context = auth_context.get("session") or {}
    if actor.get("type") != "human" or not session_context.get("session_id"):
        raise HTTPException(status_code=403, detail={"reason_code": "human_session_required", "message": "A signed-in owner session is required."})
    result = lite_identity_auth.regenerate_recovery_codes(
        human_id=str(actor["identity_id"]), session_id=str(session_context["session_id"])
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "generated",
        "generation": result["generation"],
        "codes": result["codes"],
        "created_at": result["created_at"],
        "summary": "New one-time recovery codes were generated. Save them somewhere private; Pocket Lab will not show them again.",
    }


@router.post("/identity/recover")
def recover_lite_identity(payload: LiteIdentityRecoveryRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        session = lite_identity_auth.recover_with_code(
            username=payload.username,
            recovery_code=payload.recovery_code,
            new_password=payload.new_password,
            source=_request_source(request),
        )
    except lite_identity_auth.IdentityError as exc:
        _raise_identity_error(exc)
    _set_identity_cookie(response, session["session_token"], session["csrf_token"])
    auth_context = lite_identity_auth.authenticate_session_token(session["session_token"])
    projection = lite_identity_auth.identity_projection(auth_context)
    projection["csrf_token"] = session["csrf_token"]
    projection["recovered"] = True
    return projection


@router.post(
    "/identity/rotate",
    status_code=410,
    response_description="Legacy Identity secret rotation is retired; use the human Identity password flow.",
)
def rotate_lite_identity(payload: LiteIdentityRotateRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return {
        "status": "retired",
        "accepted": False,
        "reason_code": "legacy_secret_rotation_retired",
        "summary": "Generic secret rotation is no longer used for human sign-in. Use the Identity password flow instead.",
    }


@router.get("/security/summary")
def get_lite_security_summary(request: Request) -> Response:
    deps.require_auth(request)
    return _security_compact_response(request, lite_security.summary_state())


@router.get("/security/freshness")
def get_lite_security_freshness(request: Request) -> Response:
    deps.require_auth(request)
    return _security_compact_response(request, lite_security.split_freshness_state())


@router.get("/security/profiles/{profile}")
async def get_lite_security_profile(
    profile: str, request: Request, app_id: str | None = None
) -> Response:
    deps.require_auth(request)
    normalized_profile = str(profile or "").strip().lower()
    if normalized_profile == "app" and not str(app_id or "").strip():
        raise HTTPException(status_code=400, detail="app_id is required for App Check snapshots.")
    try:
        payload = await lite_security.run_api_maintenance(
            lite_security.split_profile_state,
            profile,
            app_id,
            operation_name="security.profile.reconstruction",
        )
        return _security_compact_response(request, payload)
    except ValueError:
        raise HTTPException(status_code=404, detail="Security profile or app not found.")
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_profile_read")


@router.get("/security/history")
async def get_lite_security_history(
    request: Request, limit: int = 20, cursor: str | None = None
) -> Response:
    deps.require_auth(request)
    try:
        payload = await lite_security.run_api_maintenance(
            lite_security.split_history_state,
            limit=limit,
            cursor=cursor,
            operation_name="security.history.reconstruction",
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Security history cursor.")
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_history_read")
    return _security_compact_response(request, payload)


@router.get("/security/details/{run_id}")
async def get_lite_security_details(run_id: str, request: Request) -> Response:
    deps.require_auth(request)
    try:
        payload = await lite_security.run_api_maintenance(
            lite_security.split_run_details_state,
            run_id,
            operation_name="security.details.reconstruction",
        )
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_details_read")
    if not payload:
        raise HTTPException(status_code=404, detail="Security check details not found.")
    return _security_compact_response(request, payload)


@router.get("/security/evidence/{run_id}/summary")
async def get_lite_security_evidence_summary(run_id: str, request: Request) -> Response:
    deps.require_auth(request)
    try:
        payload = await lite_security.run_api_maintenance(
            lite_security.split_evidence_summary_state,
            run_id,
            operation_name="security.evidence.summary",
        )
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_evidence_summary")
    if not payload:
        raise HTTPException(status_code=404, detail="Security evidence summary not found.")
    return _security_compact_response(request, payload)



@router.get(
    "/security/events",
    response_class=StreamingResponse,
    responses={200: {"description": "Security progress Server-Sent Events stream.", "content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
def get_lite_security_events(request: Request) -> Response:
    deps.require_auth(request)
    return StreamingResponse(
        _security_events_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/security/progress")
async def get_lite_security_progress(request: Request) -> Response:
    # Constant-cost path: authenticate, atomically read one prepared reference,
    # evaluate its precomputed ETag, and return pre-encoded response fragments.
    route_entry = time.perf_counter()
    middleware_entry = float(
        getattr(request.state, "pocketlab_middleware_entry", route_entry)
    )
    deps.require_auth(request)
    auth_complete = time.perf_counter()
    if lite_security.prepared_security_progress_enabled():
        try:
            prepared, projection_age_ms = lite_security.prepared_security_progress()
        except lite_security.SecurityProgressGenerationUnavailable:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "temporarily_unavailable",
                    "summary": "Safety status is recovering after a database change.",
                    "retryable": True,
                    "sanitized": True,
                },
                headers={"Retry-After": "2", "Cache-Control": "no-store"},
            )
        snapshot_complete = time.perf_counter()
        if lite_security.if_none_match_matches(
            request.headers.get("if-none-match"), prepared.etag
        ):
            response = Response(status_code=304, headers=prepared.headers)
        else:
            response = Response(
                content=prepared.body_for_age(projection_age_ms),
                status_code=200,
                headers=prepared.headers,
            )
        response.headers["X-PocketLab-Projection-Age-Ms"] = f"{projection_age_ms:.2f}"
    else:
        payload = lite_security.split_progress_state()
        snapshot_complete = time.perf_counter()
        response = _security_compact_response(request, payload)
        projection_age_ms = float(payload.get("projection_age_ms") or 0.0)
    response_complete = time.perf_counter()
    phases = {
        "middleware_to_route_ms": max(0.0, (route_entry - middleware_entry) * 1000),
        "auth_ms": max(0.0, (auth_complete - route_entry) * 1000),
        "snapshot_read_ms": max(0.0, (snapshot_complete - auth_complete) * 1000),
        "response_build_ms": max(0.0, (response_complete - snapshot_complete) * 1000),
        "route_handler_ms": max(0.0, (response_complete - route_entry) * 1000),
    }
    request.state.pocketlab_progress_timing = phases
    response.headers["Server-Timing"] = ", ".join(
        (
            f"middleware_route;dur={phases['middleware_to_route_ms']:.2f}",
            f"auth;dur={phases['auth_ms']:.2f}",
            f"snapshot;dur={phases['snapshot_read_ms']:.2f}",
            f"response_build;dur={phases['response_build_ms']:.2f}",
            f"route;dur={phases['route_handler_ms']:.2f}",
        )
    )
    return response


def _full_lite_runtime_diagnostics() -> dict[str, Any]:
    payload = RUNTIME_DIAGNOSTICS.snapshot()
    payload["security_progress"] = lite_security.security_progress_runtime_diagnostics()
    payload["workload_admission"] = WORKLOAD_ADMISSION.snapshot()
    payload["workload_classification"] = workload_classification_snapshot()
    payload["request_limits"] = request_limit_snapshot()
    payload["storage_readiness"] = lite_storage_guard.storage_readiness()
    from ..services.idle_efficiency import IDLE_EFFICIENCY
    from ..services.hot_path_profiler import HOT_PATH_PROFILER
    from ..services.live_status import LIVE_STATUS
    from ..services.projection_scheduler import PROJECTION_SCHEDULER
    from ..services.process_runtime import PROCESS_RUNTIME
    from ..services.adaptive_runtime import ADAPTIVE_RUNTIME
    from ..services.lite_semantic_revisions import diagnostics as semantic_revision_diagnostics
    payload["idle_efficiency"] = IDLE_EFFICIENCY.snapshot()
    payload["hot_path"] = HOT_PATH_PROFILER.snapshot()
    payload["live_status"] = LIVE_STATUS.status()
    local_projection_scheduler = PROJECTION_SCHEDULER.diagnostics()
    payload["projection_scheduler_local"] = {
        **local_projection_scheduler,
        "diagnostic_source": "api_process_local",
        "authoritative_execution_registry": False,
    }
    from ..services.runtime_snapshot_store import read_worker_snapshot
    worker_snapshot = read_worker_snapshot() or {}
    worker_projection_scheduler = (
        worker_snapshot.get("projection_scheduler")
        if isinstance(worker_snapshot.get("projection_scheduler"), dict)
        else None
    )
    if worker_projection_scheduler:
        payload["projection_scheduler"] = {
            **worker_projection_scheduler,
            "diagnostic_source": "worker_prepared_sqlite",
            "authoritative_execution_registry": True,
            "snapshot_age_ms": int(worker_snapshot.get("snapshot_age_ms") or 0),
        }
    else:
        payload["projection_scheduler"] = {
            **local_projection_scheduler,
            "diagnostic_source": "api_process_local_fallback",
            "authoritative_execution_registry": False,
            "worker_snapshot_available": False,
        }
    payload["adaptive_runtime"] = ADAPTIVE_RUNTIME.diagnostics()
    payload["process_runtime"] = PROCESS_RUNTIME.snapshot()
    payload["semantic_revisions"] = semantic_revision_diagnostics()
    payload["phase3b_current_state"] = lite_phase3b_projections.diagnostics()
    payload["phase3c_current_state"] = lite_phase3c_projections.diagnostics()
    payload["sanitized"] = True
    return payload


@router.get("/diagnostics/runtime")
async def get_lite_runtime_diagnostics(request: Request) -> Response:
    deps.require_auth(request)
    from ..services.runtime_snapshot_store import encoded_runtime_response

    # The route only snapshots a small lock-protected event-loop summary on the
    # loop. SQLite I/O and response-byte assembly run in the bounded default
    # executor so diagnostics cannot become an event-loop blocking collector.
    runtime_revision, runtime_fragment = RUNTIME_DIAGNOSTICS.compact_runtime_fragment()
    encoded = await asyncio.to_thread(
        encoded_runtime_response, runtime_revision, runtime_fragment
    )
    return Response(
        content=encoded,
        media_type="application/json",
        headers={"Cache-Control": "private, max-age=1"},
    )


@router.get("/diagnostics/runtime/full")
def get_lite_runtime_diagnostics_full(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return _full_lite_runtime_diagnostics()


@router.get("/diagnostics/frontend-lifecycle/challenge")
def get_frontend_lifecycle_diagnostics_challenge(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_lifecycle_diagnostics.challenge()


@router.post("/diagnostics/frontend-lifecycle")
def record_frontend_lifecycle_diagnostics(
    request: Request, payload: LiteLifecycleDiagnosticsRequest
) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_lifecycle_diagnostics.record(payload.challenge_id, payload.report)


@router.get("/security")
async def get_lite_security(request: Request) -> dict[str, Any]:
    deps.require_auth(request)

    def build_details_payload() -> dict[str, Any]:
        state = lite_security.current_state()
        profiles = lite_app_profiles.app_security_profiles()
        lifecycle = lite_app_lifecycle.app_lifecycle_profiles()
        state["protected_apps"] = profiles.get("apps", [])
        state["app_security_profiles"] = profiles
        state["app_lifecycle_profiles"] = lifecycle
        state["details_payload"] = True
        return state

    try:
        return await lite_security.run_api_maintenance(
            build_details_payload,
            operation_name="security.current_state.read",
        )
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_details_read")


@router.post("/security/check", status_code=202)
async def check_lite_security(
    request: Request, response: Response,
    payload: LiteSecurityScanRequest | None = Body(default=None),
) -> dict[str, Any]:
    request_started = time.perf_counter()
    deps.require_auth(request, write=True)
    auth_done = time.perf_counter()
    payload = payload or LiteSecurityScanRequest()
    try:
        profile = lite_security.policy.normalize_scan_profile(payload.profile)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unknown safety check profile. Choose Quick Safety Check, Full Local Check, or App Check.",
        )
    app_id = None
    if profile == lite_security.policy.SCAN_PROFILE_APP:
        if not payload.app_id:
            raise HTTPException(status_code=400, detail="App Check requires an app_id.")
        try:
            app_id = lite_security.policy.normalize_app_id(payload.app_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="App Check is not available for this app yet.")
    storage_readiness = lite_storage_guard.storage_readiness(request)
    if not storage_readiness.get("ready"):
        return JSONResponse(
            status_code=507,
            content=lite_storage_guard.rejection_payload(storage_readiness),
            headers={"Cache-Control": "no-store", "Retry-After": "30"},
        )
    run_id = lite_security.new_run_id()
    reason = payload.reason or (
        "manual app check"
        if profile == lite_security.policy.SCAN_PROFILE_APP
        else "manual full local check"
        if profile == lite_security.policy.SCAN_PROFILE_FULL
        else "manual quick safety check"
    )
    try:
        prepared, reservation_timing = await lite_security.run_api_maintenance_timed(
            lite_security.build_and_reserve_scan_request,
            run_id=run_id,
            scope=payload.scope or "local",
            profile=profile,
            app_id=app_id,
            reason=reason,
            requested_at=deps.now_utc_iso(),
            operation_name="security.scan.reservation",
        )
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_scan")
    command = prepared["command"]
    reservation = prepared["reservation"]
    reservation_timing.update({
        f"stage_{key}": value
        for key, value in (prepared.get("reservation_stages") or {}).items()
    })
    reservation_done = time.perf_counter()
    if not reservation.get("reserved"):
        deduplicated = reservation.get("response") or {
            "status": "queued",
            "accepted": True,
            "deduplicated": True,
            "summary": "A safety check is already in progress.",
        }
        _record_security_submission_timing(
            response, run_id=str(deduplicated.get("run_id") or run_id),
            started=request_started, auth_done=auth_done,
            reservation_done=reservation_done, deduplicated=True,
            reservation_timing=reservation_timing,
        )
        return deduplicated
    # Capture the publication boundary before NATS can deliver the command. The
    # timestamp is persisted only after submit_domain_command succeeds.
    command["command_published_at"] = deps.now_utc_iso()
    publish_timing: dict[str, float] = {}
    try:
        queued = await submit_domain_command(
            lite_security.policy.COMMAND_SUBJECT,
            "lite.security.scan.requested",
            command,
            timing_sink=publish_timing,
        )
    except Exception:
        try:
            await lite_security.run_api_maintenance(
                lite_security.fail_scan_submission,
                run_id,
                operation_name="security.scan.submission_failure_commit",
                admission_timeout_seconds=2.0,
                deadline_seconds=12.0,
            )
        except WorkloadAdmissionError as cleanup_exc:
            _LOGGER.warning(
                "pocketlab.security.submission_cleanup_degraded error_type=%s",
                type(cleanup_exc).__name__,
            )
        raise
    publish_done = time.perf_counter()
    lifecycle_stages: dict[str, float] = {}
    lifecycle_pending = False
    lifecycle_timing: dict[str, float] = {}
    try:
        _result, lifecycle_timing = await lite_security.run_api_maintenance_timed(
            lite_security.finalize_scan_submission,
            command,
            lifecycle_stages,
            operation_name="security.scan.lifecycle_commit",
            admission_timeout_seconds=2.0,
            deadline_seconds=12.0,
            project_compatibility=False,
        )
        lifecycle_timing.update({f"stage_{key}": value for key, value in lifecycle_stages.items()})
        lifecycle_committed = time.perf_counter()
    except (OperationDeadlineExceeded, AdmissionTimeout, AdmissionQueueFull) as exc:
        # The durable command was already published. Do not report a false
        # rejection or cancel the shielded authoritative lifecycle write. The
        # worker receipt path can also advance the reserved SQLite row.
        lifecycle_pending = True
        lifecycle_committed = None
        lifecycle_timing = {
            "admission_class": exc.admission_class.value,
            "result": exc.reason,
        }
        await _record_admission_outcome(
            operation="security_scan_lifecycle",
            outcome="accepted_pending",
            reason=exc.reason,
            retryable=True,
            admission_class=exc.admission_class.value,
        )
    compatibility_pending = lifecycle_pending
    if (
        not lifecycle_pending
        and lite_security._security_store_api().security_store_mode() == "dual"
    ):
        try:
            await lite_security.run_api_maintenance(
                lite_security.project_scan_submission_compatibility,
                command,
                operation_name="security.compatibility.write",
                admission_timeout_seconds=0.25,
                deadline_seconds=10.0,
            )
        except WorkloadAdmissionError as exc:
            compatibility_pending = True
            await _record_admission_outcome(
                operation="security_compatibility_write",
                outcome="accepted_pending",
                reason=exc.reason,
                retryable=True,
                admission_class=exc.admission_class.value,
            )
    queued.update(
        {
            "status": "queued",
            "accepted": True,
            "deduplicated": False,
            "run_id": run_id,
            "command_subject": lite_security.policy.COMMAND_SUBJECT,
            "execution_mode": "worker",
            "summary": lite_security._profile_copy(profile)["queued"],
            "scan_profile": profile,
            "lifecycle_pending": lifecycle_pending,
            "compatibility_pending": compatibility_pending,
            **({"app_id": app_id, "app_label": "PhotoPrism"} if app_id else {}),
        }
    )
    _record_security_submission_timing(
        response, run_id=run_id, started=request_started, auth_done=auth_done,
        reservation_done=reservation_done, publish_done=publish_done,
        lifecycle_committed=lifecycle_committed, reservation_timing=reservation_timing,
        publish_timing=publish_timing, lifecycle_timing=lifecycle_timing,
    )
    # Gate-only fault injection occurs after durable reservation, publication,
    # and authoritative lifecycle commit, but before the HTTP response. It is
    # inert unless a loopback request presents a short-lived token matching an
    # owner-only activation file created by the external Phase 5 gate.
    await lite_gate_faults.maybe_delay_submission_response(request)
    return queued


@router.post("/security/scan", status_code=202)
async def scan_lite_security(
    request: Request, response: Response,
    payload: LiteSecurityScanRequest | None = Body(default=None),
) -> dict[str, Any]:
    # Backward-compatible alias for older Lite UI builds. New UI calls /security/check.
    return await check_lite_security(request, response, payload)


@router.get("/security/runs/{run_id}")
async def get_lite_security_run(run_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    try:
        run = await lite_security.run_api_maintenance(
            lite_security.read_run,
            run_id,
            operation_name="security.details.reconstruction",
        )
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_run_read")
    if not run:
        raise HTTPException(status_code=404, detail="Security check run not found.")
    return run


@router.get("/security/evidence/{run_id}")
async def get_lite_security_evidence(run_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    try:
        payload = await lite_security.run_api_maintenance(
            lite_security.read_evidence,
            run_id,
            operation_name="security.evidence.summary",
        )
    except WorkloadAdmissionError as exc:
        await _raise_admission_http_error(exc, "security_evidence_read")
    if not payload:
        raise HTTPException(status_code=404, detail="Security evidence not found.")
    return payload


@router.get("/security/apps")
def get_lite_security_apps(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_security_profiles()


@router.get("/security/apps/{app_id}")
def get_lite_security_app(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_security_profile(app_id)


@router.post("/security/apps/{app_id}/check", status_code=202)
async def check_lite_security_app(
    app_id: str,
    request: Request,
    response: Response,
    payload: LiteAppSecurityCheckRequest | None = Body(default=None),
) -> dict[str, Any]:
    try:
        normalized_app_id = lite_security.policy.normalize_app_id(app_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="App Check is not available for this app yet.")
    return await check_lite_security(
        request,
        response,
        LiteSecurityScanRequest(
            scope="local",
            profile=lite_security.policy.SCAN_PROFILE_APP,
            app_id=normalized_app_id,
            reason=(payload.reason if payload else None) or "manual app check",
        ),
    )


@router.get("/fleet")
def get_lite_fleet(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "fleet-sqlite-p3-v1"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="fleet",
            key="summary",
            snapshot_builder=CONTROL_PLANE.fleet_projection_snapshot,
            builder=lite_status.lite_fleet,
            projector=CONTROL_PLANE.project_fleet,
            stale_after_ms=5_000,
            max_stale_ms=30_000,
            deadline_seconds=6.0,
            priority=10,
            work_class="critical",
            source_revision=fleet_registry.fleet_source_revision,
            max_probe_seconds=300.0,
            quiet_window_seconds=1.5,
        )
    except (PreparedProjectionUnavailable, TimeoutError):
        return _projection_warming_response(domain="fleet", view_model=view_model)
    except Exception as exc:
        _LOGGER.warning(
            "pocketlab.fleet.read_degraded error_type=%s",
            type(exc).__name__,
            exc_info=True,
        )
        return _projection_warming_response(domain="fleet", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


def _ensure_fleet_awareness_projection() -> bool:
    try:
        CONTROL_PLANE.prepared_only_read(
            domain="fleet", key="summary",
            snapshot_builder=CONTROL_PLANE.fleet_projection_snapshot,
            builder=lite_status.lite_fleet, projector=CONTROL_PLANE.project_fleet,
            stale_after_ms=5_000, max_stale_ms=30_000, deadline_seconds=6.0,
            priority=10, work_class="critical",
        )
        return True
    except PreparedProjectionUnavailable:
        return False


def _recompute_device_removal_assessment(device_id: str) -> dict[str, Any]:
    # Removal authorization must never rely on Dexie, a stale browser response,
    # or a cached prepared assessment. Rebuild the safe backend projection and
    # then read the fenced assessment from SQLite.
    try:
        fleet_payload = lite_status.lite_fleet()
        CONTROL_PLANE.project_fleet(fleet_payload)
        return CONTROL_PLANE.device_removal_assessment(device_id)
    except DeviceAwarenessError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Pocket Lab could not verify device responsibilities. Try again shortly.",
        ) from exc


@router.get("/devices/{device_id}")
def get_lite_device_details(device_id: str, request: Request) -> Response:
    deps.require_auth(request)
    if not _ensure_fleet_awareness_projection():
        return _projection_warming_response(domain="fleet", view_model="device-details-prepared-e3-v1")
    try:
        payload = CONTROL_PLANE.device_details(device_id)
    except DeviceAwarenessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _control_plane_history_response(
        request, payload, domain="fleet", key=f"device:{device_id}"
    )


@router.get("/devices/{device_id}/health")
def get_lite_device_health(device_id: str, request: Request) -> Response:
    deps.require_auth(request)
    if not _ensure_fleet_awareness_projection():
        return _projection_warming_response(domain="fleet", view_model="device-health-prepared-e3-v1")
    try:
        payload = CONTROL_PLANE.device_health(device_id)
    except DeviceAwarenessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _control_plane_history_response(
        request, payload, domain="fleet", key=f"device-health:{device_id}"
    )


@router.get("/devices/{device_id}/health/history")
def get_lite_device_health_history(
    device_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str = Query("", max_length=512),
) -> Response:
    deps.require_auth(request)
    if not _ensure_fleet_awareness_projection():
        return _projection_warming_response(domain="fleet", view_model="device-health-history-prepared-e3-v1")
    try:
        payload = CONTROL_PLANE.device_health_history(
            device_id, limit=limit, cursor=cursor
        )
    except DeviceAwarenessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _control_plane_history_response(
        request, payload, domain="fleet",
        key=f"device-health-history:{device_id}:{limit}:{cursor}",
    )


@router.get("/fleet/health-summary")
def get_lite_fleet_health_summary(request: Request) -> Response:
    deps.require_auth(request)
    if not _ensure_fleet_awareness_projection():
        return _projection_warming_response(domain="fleet", view_model="fleet-health-summary-prepared-e3-v1")
    payload = CONTROL_PLANE.fleet_health_summary()
    return _control_plane_history_response(
        request, payload, domain="fleet", key="health-summary"
    )


@router.get("/devices/{device_id}/history")
def get_lite_device_lifecycle_history(
    device_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str = Query("", max_length=512),
) -> Response:
    deps.require_auth(request)
    if not _ensure_fleet_awareness_projection():
        return _projection_warming_response(domain="fleet", view_model="device-history-prepared-e3-v1")
    try:
        payload = CONTROL_PLANE.device_lifecycle_history(
            device_id, limit=limit, cursor=cursor
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _control_plane_history_response(
        request, payload, domain="fleet",
        key=f"device-history:{device_id}:{limit}:{cursor}",
    )


@router.get("/devices/{device_id}/removal-assessment")
def get_lite_device_removal_assessment(device_id: str, request: Request) -> Response:
    deps.require_auth(request)
    if not _ensure_fleet_awareness_projection():
        return _projection_warming_response(domain="fleet", view_model="device-removal-assessment-prepared-e3-v1")
    try:
        payload = CONTROL_PLANE.device_removal_assessment(device_id)
    except DeviceAwarenessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _control_plane_history_response(
        request, payload, domain="fleet", key=f"removal-assessment:{device_id}"
    )


@router.put("/fleet/devices/{device_id}/display-model")
def update_lite_device_display_model(
    device_id: str,
    payload: LiteDeviceDisplayModelRequest,
    request: Request,
) -> dict[str, Any]:
    deps.require_auth(request)
    try:
        result = CONTROL_PLANE.update_device_consumer_model(
            device_id,
            payload.consumer_model_name,
            expected_profile_revision=payload.expected_profile_revision,
            expected_consumer_model_name=payload.expected_consumer_model_name,
        )
    except DeviceProfileUpdateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    profile = result.get("system_profile") if isinstance(result.get("system_profile"), dict) else {}
    changed = bool(result.get("changed"))
    return {
        "status": "updated" if changed else "unchanged",
        "node_id": device_id,
        "device_id": device_id,
        "changed": changed,
        "revision": int(result.get("revision") or 0),
        "profile_revision": int(result.get("profile_revision") or profile.get("revision") or 0),
        "technical_model": profile.get("technical_model") or "",
        "consumer_model_name": profile.get("consumer_model_name") or "",
        "display_model": profile.get("display_model") or "Device",
        "system_profile": profile,
        "system_health": result.get("system_health") or {},
        "summary": "Device model updated." if changed else "Device model is already up to date.",
    }


@router.get("/revisions")
def get_lite_domain_revisions(request: Request) -> Response:
    deps.require_auth(request)
    return _lite_revisions_response(request, CONTROL_PLANE.revisions())


@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={200: {"description": "Lite revision Server-Sent Events stream.", "content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
def get_lite_revision_events(request: Request) -> Response:
    deps.require_auth(request)
    return StreamingResponse(
        _lite_revision_events_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-PocketLab-Event-Schema": "lite-revision-v1",
        },
    )


@router.get("/fleet/devices/{device_id}/recovery-history")
def get_lite_device_recovery_history(
    device_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str = Query("", max_length=512),
) -> Response:
    deps.require_auth(request)
    try:
        payload = CONTROL_PLANE.device_recovery_history(
            device_id, limit=limit, cursor=cursor
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _control_plane_history_response(
        request, payload, domain="fleet",
        key=f"recovery-history:{device_id}:{limit}:{cursor}",
    )


@router.get("/commands/history")
def get_lite_command_history(
    request: Request,
    entity_type: str = Query("", max_length=40),
    entity_id: str = Query("", max_length=120),
    limit: int = Query(20, ge=1, le=100),
    cursor: str = Query("", max_length=512),
) -> Response:
    deps.require_auth(request)
    try:
        payload = CONTROL_PLANE.command_history(
            entity_type=entity_type, entity_id=entity_id, limit=limit, cursor=cursor
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _control_plane_history_response(
        request, payload, domain="commands",
        key=f"history:{entity_type}:{entity_id}:{limit}:{cursor}",
    )


@router.get("/fleet/invites/latest")
def get_latest_lite_fleet_invite(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    invite = lite_invites.latest_invite()
    return {
        "status": "invite_ready" if invite else "not_found",
        "latest_invite": invite,
        "updated_at": deps.now_utc_iso(),
    }


@router.post("/fleet/invites/{invite_id}/revoke")
def revoke_lite_fleet_invite(
    invite_id: str, payload: LiteInviteRevokeRequest, request: Request
) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    revoked = lite_invites.revoke_invite(invite_id, reason=payload.reason or "")
    if not revoked:
        raise HTTPException(
            status_code=409,
            detail="This invite is no longer pending and cannot be revoked.",
        )
    CONTROL_PLANE.invalidate_domain("fleet")
    return {
        "status": "revoked",
        "invite": revoked,
        "summary": "Pending device invite revoked.",
        "updated_at": deps.now_utc_iso(),
    }


@router.post("/fleet/add-device", status_code=202)
async def add_lite_device(payload: LiteAddDeviceRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    try:
        device_name = _candidate_device_name(payload)
        device_conflict = fleet_registry.find_device_identity_conflict(device_name)
        invite_conflict = lite_invites.find_invite_identity_conflict(device_name)
        conflict = device_conflict or invite_conflict
        if conflict:
            source = str(conflict.get("source") or "device_record") if isinstance(conflict, dict) else "device_record"
            protected = bool(isinstance(conflict, dict) and (conflict.get("protected_server_host") or conflict.get("role") == "server_host"))
            conflict_device_id = str(
                conflict.get("device_id") or conflict.get("node_id") or conflict.get("id") or device_name
            )
            fleet_registry.append_device_lifecycle_event(
                conflict_device_id,
                "protected_host_blocked" if protected else "duplicate_name_blocked",
                reason_code="protected_server_host" if protected else "device_name_in_use",
                summary="Protected server host name cannot be reused." if protected else "Device name is already in use.",
                status="blocked",
            )
            raise HTTPException(status_code=409, detail=_duplicate_device_detail({**conflict, "conflict_source": source}))

        result = lite_invites.create_lite_invite(
            role=payload.role,
            hostname=payload.hostname,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await lite_invites.publish_invite_evidence(result)
    CONTROL_PLANE.invalidate_domain("fleet")
    return {key: value for key, value in result.items() if key != "event"}


@router.post("/fleet/remove-device")
async def remove_lite_device(payload: LiteRemoveDeviceRequest, request: Request) -> dict[str, Any]:
    auth_context = deps.require_auth(request, write=True)
    device_id = (payload.device_id or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="Choose a device to remove.")
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirm removal before removing a saved device record.")

    conflict = fleet_registry.find_device_identity_conflict(device_id)
    if isinstance(conflict, dict) and (
        conflict.get("is_current")
        or str(conflict.get("role") or "").lower() in {"server_host", "server", "control_plane", "control_plane_host"}
    ):
        raise HTTPException(
            status_code=409,
            detail={"status": "removal_blocked", "summary": "Current protected server host cannot be removed."},
        )

    try:
        current_assessment = _recompute_device_removal_assessment(device_id)
        CONTROL_PLANE.validate_device_removal_assessment(
            device_id,
            assessment_revision=payload.assessment_revision,
            expected_awareness_revision=payload.expected_awareness_revision,
        )
    except DeviceAwarenessError as exc:
        detail: dict[str, Any] = {
            "status": "removal_blocked",
            "summary": exc.detail,
            "assessment": exc.assessment or locals().get("current_assessment", {}),
        }
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc

    removal_generation = hashlib.sha256(
        f"{device_id}:{current_assessment.get('assessment_revision')}:{current_assessment.get('awareness_revision')}".encode("utf-8")
    ).hexdigest()[:24]
    policy_decision = await _enforce_lite_policy(
        auth_context=auth_context,
        action_id="device.remove",
        target_type="device",
        target_id=device_id,
        target_revision=str(current_assessment.get("assessment_revision") or removal_generation),
        target={
            "confirmed": True,
            "revision_validated": True,
            "protected_server_host": False,
            "awareness_revision": int(current_assessment.get("awareness_revision") or 0),
            "removal_class": current_assessment.get("removal_class"),
        },
        correlation_id=removal_generation,
    )
    continuation_id = str(policy_decision.get("continuation_approval_id") or "")
    if continuation_id:
        try:
            await asyncio.to_thread(
                lite_policy_approvals.consume_matching,
                auth_context=auth_context,
                approval_id=continuation_id,
                action_id="device.remove",
                target_type="device",
                target_id=device_id,
                policy_revision=str(policy_decision.get("policy_revision") or ""),
            )
        except lite_policy_approvals.ApprovalError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                headers={"Cache-Control": "no-store"},
                detail={"status": "blocked", "accepted": False, "reason_code": exc.reason_code, "message": exc.message},
            ) from exc
    try:
        prepared_details = CONTROL_PLANE.device_details(device_id)
        removal_state = (
            prepared_details.get("device")
            if isinstance(prepared_details.get("device"), dict)
            else {"node_id": device_id, "role": "compute", "status": "offline"}
        )
        fleet_registry.append_device_lifecycle_event(
            device_id, "removal_requested",
            reason_code="confirmed_device_retirement",
            summary="Device retirement was requested after dependency review and explicit confirmation.",
            status="requested", occurred_at=deps.now_utc_iso(),
            command_id=removal_generation,
            dedupe_key=f"{device_id}:removal_requested:{removal_generation}",
            generation_key=removal_generation, current_state=removal_state,
        )
        retirement = CONTROL_PLANE.retire_enrolled_device(
            device_id,
            reason_code=payload.reason or "confirmed_device_retirement",
            assessment_revision=str(current_assessment.get("assessment_revision") or ""),
            awareness_revision=int(current_assessment.get("awareness_revision") or 0),
            requested_by=(payload.requested_by or "authenticated_operator").strip() or "authenticated_operator",
        )
        registry_device = retirement.get("device") if isinstance(retirement.get("device"), dict) else {}
        removal = {
            "status": "removed",
            "device_id": device_id,
            "device_name": registry_device.get("device_name") or removal_state.get("name") or device_id,
            "role": registry_device.get("role") or removal_state.get("role") or "compute",
            "previous_status": removal_state.get("status") or "offline",
            "previous_connection": removal_state.get("connection") or "offline",
            "removed_device_records": 0,
            "removed_from": [],
            "removal_receipt": retirement.get("receipt") or {},
            "updated_at": deps.now_utc_iso(),
        }
        try:
            compatibility_cleanup = fleet_registry.remove_device_records(device_id)
        except fleet_registry.DeviceRemovalError:
            removal["compatibility_cleanup"] = {
                "status": "deferred",
                "summary": "Legacy device-list cleanup was deferred; canonical removal succeeded.",
                "sanitized": True,
            }
        else:
            removal.update(compatibility_cleanup)
            removal["removal_receipt"] = retirement.get("receipt") or {}
            removal["compatibility_cleanup"] = {
                "status": "completed", "sanitized": True
            }
    except DeviceAwarenessError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"status": "removal_blocked", "summary": exc.detail},
        ) from exc
    except fleet_registry.DeviceRemovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    invite_cleanup = lite_invites.remove_invites_for_device(device_id, device=removal)
    removed_invites = int(invite_cleanup.get("removed_invite_records") or 0)
    requested_by = (payload.requested_by or "lite-api").strip() or "lite-api"
    evidence = fleet_registry.append_device_removed_evidence(
        removal,
        removed_invite_records=removed_invites,
        reason=payload.reason,
        requested_by=requested_by,
    )
    await fleet_registry.publish_device_removed_evidence(evidence)
    # The canonical removal_completed lifecycle event, receipt and audit row were
    # committed atomically by retire_enrolled_device(). Compatibility JSON/NATS
    # evidence above is an export only and does not own lifecycle truth.
    CONTROL_PLANE.invalidate_domain("fleet")

    return {
        **removal,
        "removed_invite_records": removed_invites,
        "message": "Old device record removed.",
        "summary": "Old device record removed. The phone was not wiped and Pocket Lab was not uninstalled from that device.",
        "authorization": {
            "decision_id": policy_decision.get("decision_id"),
            "reason_code": policy_decision.get("reason_code"),
            "policy_revision": policy_decision.get("policy_revision"),
        },
        "updated_at": deps.now_utc_iso(),
    }


@router.get("/policy")
async def get_lite_policy(request: Request, response: Response) -> dict[str, Any]:
    deps.require_auth(request)
    response.headers["Cache-Control"] = "no-cache"
    return await asyncio.to_thread(lite_policy_opa.policy_status)


@router.post(
    "/policy/apply",
    status_code=410,
    response_description="Legacy policy mutation is retired; Rules policy activation is repository-owned.",
)
def apply_lite_policy(payload: LitePolicyApplyRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return {
        "status": "retired",
        "accepted": False,
        "reason_code": "generic_policy_toggle_retired",
        "summary": "The old protection toggle is retired. Safety Rules are repository-owned and activated only after OPA validation.",
    }


def _lite_recovery_details_payload() -> dict[str, Any]:
    # Compatibility alias; the shared builder owns CONTROL_PLANE.prepared_payload("apps:lifecycle").
    return lite_core_projections.recovery_details_payload()


def _build_lite_recovery_summary_projection() -> dict[str, Any]:
    return lite_core_projections.recovery_summary_payload()


def schedule_control_plane_projection_warmup() -> dict[str, bool]:
    """Register and submit optional projections through shared worker-safe contracts."""
    # Preserved warm-up order contract: warm_prepared_read key="summary" -> key="lifecycle" -> key="details".
    results = {
        "fleet": False, "apps": False, "recovery_summary": False,
        "recovery_details": False, "phase3b": False, "phase3c": False,
    }
    try:
        core = lite_core_projections.schedule_startup_warmup()
        results.update(core)
        phase3b = lite_phase3b_projections.schedule_startup_warmup()
        results["phase3b"] = bool(phase3b) and all(phase3b.values())
        phase3c = lite_phase3c_projections.schedule_startup_warmup()
        results["phase3c"] = bool(phase3c) and all(phase3c.values())
    except Exception as exc:
        _LOGGER.warning(
            "pocketlab.control_projection.warmup_degraded error_type=%s",
            type(exc).__name__,
        )
    return results


def _refresh_device_health_projection() -> dict[str, Any]:
    try:
        deadline_seconds = max(5.0, min(60.0, float(
            os.environ.get("POCKETLAB_DEVICE_HEALTH_SWEEP_DEADLINE_SECONDS", "20")
        )))
    except (TypeError, ValueError):
        deadline_seconds = 20.0
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="fleet", key="summary",
            snapshot_builder=CONTROL_PLANE.fleet_projection_snapshot,
            builder=lite_status.lite_fleet, projector=CONTROL_PLANE.project_fleet,
            stale_after_ms=0, max_stale_ms=0, deadline_seconds=deadline_seconds,
            priority=15, work_class="critical",
        )
        return {
            "source_revision": prepared.source_revision,
            "projection_age_ms": prepared.projection_age_ms,
            "read_degraded": prepared.read_degraded,
            "refresh_pending": prepared.refresh_pending,
        }
    except PreparedProjectionUnavailable:
        from ..services.projection_scheduler import PROJECTION_SCHEDULER
        status = PROJECTION_SCHEDULER.status("fleet.summary")
        return {
            "source_revision": CONTROL_PLANE.domain_revision("fleet"),
            "projection_age_ms": 0,
            "read_degraded": True,
            "refresh_pending": bool(status.get("refresh_pending")),
        }


def _bounded_startup_delay(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


async def run_staged_startup_workloads(lite_security_module: Any) -> None:
    """Start optional projection work in bounded stages on low-power hosts.

    API, NATS, and live status are already ready before this coroutine starts.
    Each stage is isolated so one optional subsystem cannot block later stages
    or turn startup into a restart loop.
    """
    logger = _LOGGER
    security_delay = _bounded_startup_delay(
        "POCKETLAB_SECURITY_PROJECTION_START_DELAY_SECONDS", 3.0, 0.0, 60.0
    )
    warmup_delay = _bounded_startup_delay(
        "POCKETLAB_CONTROL_PROJECTION_START_DELAY_SECONDS", 12.0, 1.0, 120.0
    )
    health_delay = _bounded_startup_delay(
        "POCKETLAB_DEVICE_HEALTH_START_DELAY_SECONDS", 5.0, 1.0, 120.0
    )
    started_at = asyncio.get_running_loop().time()

    async def wait_until(offset: float) -> None:
        remaining = started_at + offset - asyncio.get_running_loop().time()
        if remaining > 0:
            await asyncio.sleep(remaining)

    try:
        await wait_until(security_delay)
        try:
            with RUNTIME_DIAGNOSTICS.operation("startup.security_projection"):
                await asyncio.to_thread(
                    lite_security_module.start_security_projection_runtime
                )
            lite_phase3b_projections.mark_dirty(
                "security.progress", "security.summary", reason="security_runtime_started"
            )
            logger.info("pocketlab.startup.stage_ready stage=security_projection")
            try:
                reconciliation = await asyncio.to_thread(
                    lite_database_recovery.reconcile_database_restore_projection
                )
                logger.info(
                    "pocketlab.recovery_projection.reconciled status=%s changed=%s",
                    reconciliation.get("status"),
                    reconciliation.get("changed", False),
                )
            except Exception as exc:
                logger.warning(
                    "pocketlab.recovery_projection.reconcile_degraded error_type=%s",
                    type(exc).__name__,
                )
        except Exception as exc:
            logger.warning(
                "pocketlab.startup.stage_degraded stage=security_projection error_type=%s",
                type(exc).__name__,
            )

        await wait_until(health_delay)
        # The consolidated LiveStatus coordinator owns health/fleet reconciliation.
        # Startup only emits one coalesced event hint; no dedicated forever-loop is
        # created for device health.
        from ..services.live_status import LIVE_STATUS
        LIVE_STATUS.register_device_health_sampler(_refresh_device_health_projection)
        LIVE_STATUS.request_sample(
            "health", "fleet", "device_health", reason="startup_device_health"
        )
        await asyncio.sleep(0)
        logger.info("pocketlab.startup.stage_ready stage=device_health_coordinator")

        await wait_until(warmup_delay)
        try:
            with RUNTIME_DIAGNOSTICS.operation("startup.command_reconcile"):
                reconciled = await asyncio.to_thread(
                    CONTROL_PLANE.reconcile_command_lifecycle
                )
            logger.info(
                "pocketlab.command_lifecycle.startup_reconciled count=%s degraded=%s",
                reconciled.get("reconciled_count"),
                reconciled.get("degraded", False),
            )
        except Exception as exc:
            logger.warning(
                "pocketlab.command_lifecycle.startup_degraded error_type=%s",
                type(exc).__name__,
            )
        try:
            with RUNTIME_DIAGNOSTICS.operation("startup.control_projection_warmup"):
                warmup = await asyncio.to_thread(
                    schedule_control_plane_projection_warmup
                )
            logger.info(
                "pocketlab.control_projection.warmup_scheduled apps=%s recovery_summary=%s recovery_details=%s phase3b=%s phase3c=%s",
                warmup.get("apps"),
                warmup.get("recovery_summary"),
                warmup.get("recovery_details"),
                warmup.get("phase3b"),
                warmup.get("phase3c"),
            )
        except Exception as exc:
            logger.warning(
                "pocketlab.startup.stage_degraded stage=control_projection_warmup error_type=%s",
                type(exc).__name__,
            )

    except asyncio.CancelledError:
        raise


async def device_health_projection_sweep_loop(*, skip_startup_delay: bool = False) -> None:
    """Run one bounded fleet health sweep instead of one task per device."""
    if os.environ.get("POCKETLAB_LITE_DISABLE_DEVICE_HEALTH_SWEEP", "").lower() in {
        "1", "true", "yes", "on",
    }:
        return
    try:
        startup_delay = max(
            5.0,
            min(
                120.0,
                float(os.environ.get("POCKETLAB_DEVICE_HEALTH_SWEEP_START_DELAY_SECONDS", "15")),
            ),
        )
    except (TypeError, ValueError):
        startup_delay = 15.0
    try:
        interval = max(
            30.0,
            min(
                900.0,
                float(os.environ.get("POCKETLAB_DEVICE_HEALTH_SWEEP_SECONDS", "60")),
            ),
        )
    except (TypeError, ValueError):
        interval = 60.0
    if not skip_startup_delay:
        await asyncio.sleep(startup_delay)
    while True:
        try:
            with RUNTIME_DIAGNOSTICS.operation("background.device_health_sweep"):
                await asyncio.to_thread(CONTROL_PLANE.reconcile_command_lifecycle)
                result = await asyncio.to_thread(_refresh_device_health_projection)
            _LOGGER.debug(
                "pocketlab.device_health.sweep revision=%s projection_age_ms=%s read_degraded=%s",
                result.get("source_revision"),
                result.get("projection_age_ms"),
                result.get("read_degraded"),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.warning(
                "pocketlab.device_health.sweep_degraded error_type=%s",
                type(exc).__name__,
            )
        await asyncio.sleep(interval)


@router.get("/recovery/summary")
def get_lite_recovery_summary(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "recovery-summary-sqlite-p3-v2"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="recovery", key="summary",
            snapshot_builder=lambda: CONTROL_PLANE.recovery_projection_snapshot(details=False),
            builder=lite_core_projections.recovery_summary_payload,
            projector=CONTROL_PLANE.project_recovery,
            stale_after_ms=10_000, max_stale_ms=60_000,
            deadline_seconds=8.0, priority=50, work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="recovery", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


@router.get("/recovery/details")
def get_lite_recovery_details(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "recovery-details-sqlite-p3-v2"
    try:
        prepared = CONTROL_PLANE.prepared_only_read(
            domain="recovery", key="details",
            snapshot_builder=lambda: CONTROL_PLANE.recovery_projection_snapshot(details=True),
            builder=lite_core_projections.recovery_details_payload, projector=CONTROL_PLANE.project_recovery,
            stale_after_ms=15_000, max_stale_ms=90_000,
            deadline_seconds=10.0, priority=60, work_class="io",
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="recovery", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


@router.get("/recovery/operations")
def get_lite_recovery_operation_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str = Query("", max_length=512),
) -> Response:
    deps.require_auth(request)
    try:
        payload = CONTROL_PLANE.recovery_operation_history(limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _control_plane_history_response(
        request, payload, domain="recovery", key=f"operations:{limit}:{cursor}"
    )


@router.get("/recovery")
def get_lite_recovery(request: Request) -> Response:
    return get_lite_recovery_details(request)


@router.get("/recovery/database")
def get_lite_database_recovery(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_database_recovery.database_recovery_status()


@router.post("/recovery/database/backup", status_code=202)
async def backup_lite_database(payload: LiteDatabaseBackupRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.database.backup",
        "lite.database.backup.queued",
        {
            "command_id": command_id,
            "backup_id": f"db-backup-{command_id}",
            "reason": payload.reason or "manual database backup",
            "requested_by": "lite-api",
        },
    )
    submitted.update(
        {
            "backup_id": f"db-backup-{command_id}",
            "summary": "Pocket Lab database backup queued. The worker will create and verify it online.",
        }
    )
    return submitted


@router.get("/recovery/database/backups")
def list_lite_database_backups(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_database_recovery.list_database_backups()


@router.get("/recovery/database/backups/{backup_id}")
def get_lite_database_backup(backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    payload = lite_database_recovery.get_database_backup(backup_id)
    if not payload:
        raise HTTPException(status_code=404, detail={"status": "not_found", "summary": "Database backup was not found."})
    return payload


@router.post("/recovery/database/backups/{backup_id}/verify", status_code=202)
async def verify_lite_database_backup(backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    if not lite_database_recovery.get_database_backup(backup_id):
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Database backup was not found."},
        )
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.database.backup.verify",
        "lite.database.backup.verify_queued",
        {"command_id": command_id, "backup_id": backup_id, "requested_by": "lite-api"},
    )
    submitted.update({"backup_id": backup_id, "summary": "Database backup verification queued."})
    return submitted


@router.post("/recovery/database/backups/{backup_id}/preview", status_code=202)
async def preview_lite_database_restore(backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    if not lite_database_recovery.get_database_backup(backup_id):
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Database backup was not found."},
        )
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.database.restore.preview",
        "lite.database.restore.preview_queued",
        {"command_id": command_id, "backup_id": backup_id, "requested_by": "lite-api"},
    )
    submitted.update({"backup_id": backup_id, "summary": "Database restore preview queued. No state will be changed."})
    return submitted


@router.get("/recovery/database/restore/previews/{preview_id}")
def get_lite_database_restore_preview(preview_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    payload = lite_database_recovery.get_database_restore_preview(preview_id)
    if not payload:
        raise HTTPException(status_code=404, detail={"status": "not_found", "summary": "Database restore preview was not found."})
    return payload


@router.post("/recovery/database/backups/{backup_id}/restore", status_code=202)
async def restore_lite_database(backup_id: str, payload: LiteDatabaseRestoreRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    if not payload.confirm:
        raise HTTPException(status_code=409, detail={"status": "confirmation_required", "summary": "Restore Pocket Lab requires explicit confirmation."})
    if payload.backup_id != backup_id:
        raise HTTPException(status_code=409, detail={"status": "backup_mismatch", "summary": "The selected backup does not match the restore request."})
    preview = lite_database_recovery.get_database_restore_preview(payload.preview_id)
    if not preview or preview.get("backup_id") != backup_id or preview.get("status") != "ready":
        raise HTTPException(status_code=409, detail={"status": "preview_required", "summary": "Create a ready restore preview for this backup first."})
    if lite_security_maintenance.active_security_scan():
        raise HTTPException(status_code=409, detail={"status": "active_security_scan", "summary": "Restore is blocked while a Safety Check is active."})
    restore_guard = lite_database_recovery.database_recovery_status().get("restore_guard") or {}
    if restore_guard.get("unresolved"):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "restore_recovery_required",
                "summary": "Another database restore must recover before a new restore can start.",
            },
        )
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.database.restore",
        "lite.database.restore.queued",
        {
            "command_id": command_id,
            "restore_id": f"db-restore-{command_id}",
            "backup_id": backup_id,
            "preview_id": payload.preview_id,
            "confirm": True,
            "requested_by": "lite-api",
        },
    )
    submitted.update(
        {
            "restore_id": f"db-restore-{command_id}",
            "backup_id": backup_id,
            "preview_id": payload.preview_id,
            "summary": "Restore queued. Pocket Lab will checkpoint, stage, promote atomically, and validate before commit.",
        }
    )
    return submitted


@router.get("/recovery/database/restore/{restore_id}")
def get_lite_database_restore_run(restore_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    payload = lite_database_recovery.get_database_restore_run(restore_id)
    if not payload:
        raise HTTPException(status_code=404, detail={"status": "not_found", "summary": "Database restore run was not found."})
    return payload


@router.get("/recovery/maintenance")
def get_lite_recovery_maintenance(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_security_maintenance.maintenance_status()


@router.post("/recovery/maintenance/retention", status_code=202)
async def run_lite_recovery_retention(payload: LiteRetentionRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.maintenance.retention",
        "lite.maintenance.retention_queued",
        {
            "command_id": command_id,
            "dry_run": payload.dry_run,
            "max_batches": payload.max_batches,
            "requested_by": "lite-api",
        },
    )
    submitted.update({"mode": "dry_run" if payload.dry_run else "apply", "summary": "Bounded Security retention queued."})
    return submitted


@router.post("/recovery/maintenance/checkpoint", status_code=202)
async def run_lite_recovery_checkpoint(payload: LiteCheckpointRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    if payload.mode == "truncate" and not payload.confirm_controlled:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "confirmation_required",
                "summary": "Truncate checkpoint requires explicit controlled-maintenance confirmation.",
            },
        )
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.maintenance.checkpoint",
        "lite.maintenance.checkpoint_queued",
        {
            "command_id": command_id,
            "operation_id": command_id,
            "mode": payload.mode.upper(),
            "confirm_controlled": bool(payload.confirm_controlled),
            "requested_by": "lite-api",
        },
    )
    submitted.update({"checkpoint_mode": payload.mode, "summary": "SQLite maintenance checkpoint queued."})
    return submitted


@router.get("/recovery/backup-targets")
def get_lite_backup_targets(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_backup_targets.backup_targets()


@router.get("/recovery/apps/{app_id}/backup-targets")
def get_lite_recovery_app_backup_targets(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_backup_targets.app_backup_targets(app_id)


@router.post("/recovery/apps/{app_id}/backup-to-target")
def backup_lite_app_to_target(app_id: str, payload: LiteAppActionRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_backup.backup_to_storage_readiness(
        app_id,
        payload.target_device_id,
        reason=payload.reason,
    )

@router.get("/recovery/apps")
def get_lite_recovery_apps(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_backup_profiles()


@router.get("/recovery/apps/{app_id}")
def get_lite_recovery_app(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_backup_profile(app_id)


@router.post("/recovery/apps/{app_id}/backup", status_code=202)
async def backup_lite_app(app_id: str, payload: LiteAppBackupRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command = lite_app_backup.app_backup_command(app_id, mode=payload.mode, reason=payload.reason)
    try:
        submitted = await submit_domain_command(
            lite_app_backup.APP_BACKUP_CREATE_SUBJECT,
            "lite.app.backup.queued",
            command,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "app_backup_queue_unavailable",
                "summary": "App backup request could not be queued because the local command bus is not reachable.",
                "detail": str(exc),
            },
        ) from exc
    pending = lite_app_backup.record_backup_request(command)
    submitted.update({
        "accepted": True,
        "status": submitted.get("status") or "queued",
        "app_id": "photoprism",
        "backup_id": command["backup_id"],
        "mode": command["app_backup_mode"],
        "pending_backup": pending,
        "summary": "PhotoPrism app backup queued. Config and app metadata are included; media remains excluded unless a supported media backup mode is enabled.",
    })
    return submitted


@router.post("/recovery/apps/{app_id}/restore/preview", status_code=202)
async def preview_lite_app_restore(app_id: str, payload: LiteAppRestorePreviewRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command = lite_app_backup.app_restore_preview_command(app_id, backup_id=payload.backup_id or "latest", reason=payload.reason)
    submitted = await submit_domain_command(
        lite_app_backup.APP_RESTORE_PREVIEW_SUBJECT,
        "lite.app.restore.preview_queued",
        command,
    )
    pending = lite_app_backup.record_restore_preview_request(command)
    submitted.update({
        "accepted": True,
        "status": submitted.get("status") or "queued",
        "app_id": "photoprism",
        "action_id": "preview_restore",
        "backup_id": command["backup_id"],
        "preview_id": command["preview_id"],
        "pending_restore_preview": pending,
        "summary": "Preparing PhotoPrism restore preview.",
        "progress": {"phase": "queued", "step": "Restore preview queued.", "bounded": True},
        "troubleshooting": {"status": "pending", "backend_only": True, "summary": "Backend record pending."},
    })
    return submitted


@router.post("/recovery/apps/{app_id}/restore", status_code=501)
def restore_lite_app(app_id: str, payload: LiteAppRestoreRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_profiles.app_restore_not_implemented(app_id)


@router.post("/recovery/backup", status_code=202)
async def backup_lite(payload: LiteBackupRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command_id = uuid.uuid4().hex
    command = {
        "command_id": command_id,
        "include_event_journal": payload.include_event_journal,
        "include_app_data": payload.include_app_data,
        "reason": payload.reason or "manual backup",
        "dry_run": payload.dry_run,
        "requested_by": "lite-api",
    }
    try:
        submitted = await submit_domain_command(
            "pocketlab.commands.lite.backup.create",
            "lite.backup.queued",
            command,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "backup_queue_unavailable",
                "summary": "Backup request could not be queued because the local command bus is not reachable.",
                "detail": str(exc),
            },
        ) from exc
    pending = lite_backup.record_backup_request(command)
    submitted["backup_id"] = command_id
    submitted["pending_backup"] = pending
    submitted["summary"] = "Backup request queued. The encrypted repository will be initialized automatically if this is the first backup."
    return submitted


@router.get("/recovery/backups")
def list_lite_backups(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    cursor: str = Query(default="", max_length=120),
) -> dict[str, Any]:
    deps.require_auth(request)
    payload = lite_backup.list_backups(limit=limit, cursor=cursor)
    if cursor and payload.get("cursor_found") is False:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "invalid_cursor",
                "summary": "Backup history changed. Refresh history and try again.",
                "sanitized": True,
            },
        )
    return payload


@router.get("/recovery/backups/{backup_id}")
def get_lite_backup(backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    backup = lite_backup.get_backup(backup_id)
    if not backup:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Backup was not found."},
        )
    return backup


@router.get("/recovery/receipts/{backup_id}")
def get_lite_backup_receipt(backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    receipt = lite_backup.get_receipt(backup_id)
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Backup receipt was not found."},
        )
    return receipt


@router.post("/recovery/backups/{backup_id}/verify", status_code=202)
async def verify_lite_backup(backup_id: str, payload: LiteBackupVerifyRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    selected = backup_id or payload.backup_id or "latest"
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.backup.verify",
        "lite.backup.verify_queued",
        {
            "command_id": command_id,
            "backup_id": selected,
            "reason": payload.reason or "manual verification",
            "requested_by": "lite-api",
        },
    )
    submitted["backup_id"] = selected
    submitted["summary"] = "Backup verification queued. The worker will check the manifest, restic snapshot, and repository metadata."
    return submitted


@router.post("/recovery/restore/preview", status_code=202)
async def preview_lite_restore(payload: LiteRestorePreviewRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command_id = uuid.uuid4().hex
    selected = payload.backup_id or "latest"
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.restore.preview",
        "lite.restore.preview_queued",
        {
            "command_id": command_id,
            "backup_id": selected,
            "reason": payload.reason or "manual restore preview",
            "requested_by": "lite-api",
        },
    )
    submitted["backup_id"] = selected
    submitted["summary"] = "Restore preview queued. The worker will inspect the verified backup without changing local state."
    return submitted


@router.get("/recovery/restore/previews/{preview_id}")
def get_lite_restore_preview(preview_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    preview = lite_backup.get_restore_preview(preview_id)
    if not preview:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Restore preview was not found."},
        )
    return preview


@router.get("/recovery/restore/checkpoints/{checkpoint_id}")
def get_lite_restore_checkpoint(checkpoint_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    checkpoint = lite_backup.get_restore_checkpoint(checkpoint_id)
    if not checkpoint:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Restore checkpoint was not found."},
        )
    return checkpoint


@router.get("/recovery/restore/runs/{restore_id}")
def get_lite_restore_run(restore_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    restore_run = lite_backup.get_restore_run(restore_id)
    if not restore_run:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Restore run was not found."},
        )
    return restore_run


@router.post("/recovery/restore", status_code=202)
async def restore_lite(payload: LiteRestoreRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    if not payload.confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "confirmation_required",
                "summary": "Restore can change local state. Confirm the restore before running it.",
            },
        )
    if not payload.preview_id:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "preview_required",
                "summary": "Run Preview Restore and include the preview id before restoring.",
            },
        )
    if not payload.backup_id or payload.backup_id == "latest":
        raise HTTPException(
            status_code=409,
            detail={
                "status": "backup_required",
                "summary": "Restore requires the explicit backup id from the verified preview.",
            },
        )
    preview = lite_backup.get_restore_preview(payload.preview_id)
    if not preview:
        raise HTTPException(
            status_code=404,
            detail={"status": "preview_not_found", "summary": "Restore preview was not found."},
        )
    if preview.get("status") != "ready" or not preview.get("restore_allowed"):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "preview_not_ready",
                "summary": "Create a verified Preview Restore before restoring.",
            },
        )
    command_id = uuid.uuid4().hex
    selected = payload.backup_id
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.restore.apply",
        "lite.restore.apply_queued",
        {
            "command_id": command_id,
            "backup_id": selected,
            "preview_id": payload.preview_id,
            "confirm": True,
            "reason": "manual confirmed restore",
            "requested_by": "lite-api",
        },
    )
    submitted["backup_id"] = selected
    submitted["preview_id"] = payload.preview_id
    submitted["summary"] = "Restore queued. Pocket Lab will create a pre-restore checkpoint before changing Lite state."
    return submitted
