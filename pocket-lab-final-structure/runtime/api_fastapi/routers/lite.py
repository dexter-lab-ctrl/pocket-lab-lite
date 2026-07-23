from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import threading
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
from ..services import fleet_registry, lite_app_actions, lite_app_lifecycle, lite_app_profiles, lite_app_storage, lite_app_backup, lite_app_backup_targets, lite_app_operations, lite_app_update, lite_backup, lite_catalog, lite_invites, lite_status, lite_security, lite_catalog_live, lite_photoprism_media, lite_evidence_receipts, lite_gate_faults, lite_storage_guard, lite_lifecycle_diagnostics, lite_database_recovery, lite_security_maintenance, lite_recovery_subprojections
from ..services.lite_control_plane_store import (
    CONTROL_PLANE,
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
_RECOVERY_BASE_LOCK = threading.Lock()
_RECOVERY_BASE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="pocketlab-recovery-base"
)
_RECOVERY_BASE_VALUE: tuple[dict[str, Any], float] | None = None
_RECOVERY_BASE_FUTURE: concurrent.futures.Future[Any] | None = None
_RECOVERY_BASE_FAILURES = 0
_RECOVERY_BASE_NEXT_ALLOWED = 0.0
_WARMUP_LOCK = threading.Lock()
_WARMUP_THREAD: threading.Thread | None = None


def _recovery_base_done(future: concurrent.futures.Future[Any]) -> None:
    global _RECOVERY_BASE_VALUE, _RECOVERY_BASE_FUTURE
    global _RECOVERY_BASE_FAILURES, _RECOVERY_BASE_NEXT_ALLOWED
    try:
        value = future.result()
        if not isinstance(value, dict):
            raise TypeError("Recovery base must return a mapping")
    except Exception as exc:
        with _RECOVERY_BASE_LOCK:
            _RECOVERY_BASE_FAILURES = min(8, _RECOVERY_BASE_FAILURES + 1)
            _RECOVERY_BASE_NEXT_ALLOWED = time.monotonic() + min(300.0, 2.0 ** _RECOVERY_BASE_FAILURES)
            _RECOVERY_BASE_FUTURE = None
        _LOGGER.warning(
            "pocketlab.recovery_base.refresh_degraded error_type=%s", type(exc).__name__
        )
        return
    with _RECOVERY_BASE_LOCK:
        _RECOVERY_BASE_VALUE = (value, time.monotonic())
        _RECOVERY_BASE_FAILURES = 0
        _RECOVERY_BASE_NEXT_ALLOWED = time.monotonic() + 60.0
        _RECOVERY_BASE_FUTURE = None


def _recovery_base_subprojection() -> dict[str, Any]:
    global _RECOVERY_BASE_FUTURE
    prepared_summary = CONTROL_PLANE.prepared_payload("recovery:summary")
    if prepared_summary is not None:
        return prepared_summary
    now = time.monotonic()
    with _RECOVERY_BASE_LOCK:
        cached = _RECOVERY_BASE_VALUE
        future = _RECOVERY_BASE_FUTURE
        if cached is not None and now - cached[1] <= 300.0:
            return dict(cached[0])
        if future is None and now >= _RECOVERY_BASE_NEXT_ALLOWED:
            future = _RECOVERY_BASE_EXECUTOR.submit(lite_status.lite_recovery_details)
            _RECOVERY_BASE_FUTURE = future
            future.add_done_callback(_recovery_base_done)
    if future is not None:
        try:
            result = future.result(timeout=1.5)
            if isinstance(result, dict):
                return dict(result)
        except concurrent.futures.TimeoutError:
            pass
        except Exception:
            pass
    if cached is not None:
        result = dict(cached[0])
        result["read_degraded"] = True
        result["refresh_pending"] = future is not None
        return result
    return {
        "status": "degraded",
        "summary": "Recovery details are refreshing.",
        "read_degraded": True,
        "refresh_pending": future is not None,
    }




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
    payload.update({
        "projection_age_ms": int(prepared.projection_age_ms),
        "read_degraded": bool(prepared.read_degraded),
        "refresh_pending": bool(prepared.refresh_pending),
        "source_revision": int(prepared.source_revision),
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
        "X-PocketLab-Source-Revision": str(int(prepared.source_revision)),
        "X-PocketLab-Read-Degraded": "true" if prepared.read_degraded else "false",
        "X-PocketLab-Refresh-Pending": "true" if prepared.refresh_pending else "false",
    }
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
        description="Optional optimistic-concurrency revision from the current safe device profile.",
    )


class LiteRemoveDeviceRequest(BaseModel):
    device_id: str = Field(default="", description="Lite device id to remove from saved records")
    confirm: bool = False
    reason: str | None = None
    requested_by: str | None = None


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


@router.get("/status")
async def get_lite_status(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return await lite_status.build_lite_status()


@router.get("/catalog")
def get_lite_catalog(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_lifecycle.hydrate_catalog_lifecycle(lite_catalog_live.hydrate_catalog(lite_catalog.catalog_payload(request)))



@router.get("/apps/lifecycle")
def get_lite_app_lifecycle_profiles(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "apps-lifecycle-sqlite-p3-v2"
    try:
        prepared = CONTROL_PLANE.prepared_read(
            domain="apps",
            key="lifecycle",
            builder=lite_app_lifecycle.app_lifecycle_profiles,
            projector=CONTROL_PLANE.project_apps,
            stale_after_ms=15_000,
            max_stale_ms=90_000,
            deadline_seconds=4.0,
            cold_start_async=True,
            fallback_builder=CONTROL_PLANE.app_projection_snapshot,
        )
    except PreparedProjectionUnavailable:
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
def get_lite_app_lifecycle_profile(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_lifecycle.app_lifecycle_profile(app_id)


@router.get("/apps/{app_id}/actions")
def get_lite_app_actions(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_actions.app_actions(app_id)


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


@router.get("/apps/{app_id}/update")
def get_lite_app_update_status(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_update.update_status(app_id)


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
def get_lite_app_backup_status(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_backup.app_backup_status(app_id)


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
    deps.require_auth(request, write=True)
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
    deps.require_auth(request, write=True)
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
def get_lite_identity(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_status.lite_identity()


@router.post("/identity/rotate", status_code=202)
async def rotate_lite_identity(payload: LiteIdentityRotateRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    data: dict[str, Any] = {"target": payload.target}
    if payload.value is not None:
        data["value"] = payload.value
    if payload.lease_duration:
        data["lease_duration"] = payload.lease_duration
    return await submit_domain_command(
        "pocketlab.commands.vault.rotate",
        "vault.rotate.requested",
        data,
    )


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



@router.get("/security/events")
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


@router.get("/diagnostics/runtime")
def get_lite_runtime_diagnostics(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    payload = RUNTIME_DIAGNOSTICS.snapshot()
    payload["security_progress"] = lite_security.security_progress_runtime_diagnostics()
    payload["workload_admission"] = WORKLOAD_ADMISSION.snapshot()
    payload["workload_classification"] = workload_classification_snapshot()
    payload["request_limits"] = request_limit_snapshot()
    payload["storage_readiness"] = lite_storage_guard.storage_readiness()
    payload["sanitized"] = True
    return payload


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
    prepared = CONTROL_PLANE.prepared_read(
        domain="fleet",
        key="summary",
        builder=lite_status.lite_fleet,
        projector=CONTROL_PLANE.project_fleet,
        stale_after_ms=5_000,
        max_stale_ms=30_000,
        deadline_seconds=4.0,
    )
    return _control_plane_prepared_response(
        request, prepared, view_model="fleet-sqlite-p3-v1"
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


@router.get("/events")
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


@router.post("/fleet/add-device", status_code=202)
async def add_lite_device(payload: LiteAddDeviceRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    try:
        device_name = _candidate_device_name(payload)
        device_conflict = fleet_registry.find_device_identity_conflict(device_name)
        invite_conflict = lite_invites.find_invite_identity_conflict(device_name)
        conflict = device_conflict or invite_conflict
        if conflict:
            raise HTTPException(status_code=409, detail=_duplicate_device_detail(conflict))

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
    deps.require_auth(request, write=True)
    device_id = (payload.device_id or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="Choose a device to remove.")
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirm removal before removing a saved device record.")

    try:
        removal = fleet_registry.remove_device_records(device_id)
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
    CONTROL_PLANE.invalidate_domain("fleet")

    return {
        **removal,
        "removed_invite_records": removed_invites,
        "message": "Old device record removed.",
        "summary": "Old device record removed. The phone was not wiped and Pocket Lab was not uninstalled from that device.",
        "updated_at": deps.now_utc_iso(),
    }


@router.get("/policy")
def get_lite_policy(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_status.lite_policy()


@router.post("/policy/apply", status_code=202)
async def apply_lite_policy(payload: LitePolicyApplyRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.security.configure_opa",
        "security.configure_opa.requested",
        {"enforce_mode": payload.protection_enabled, "reason": payload.reason},
    )


def _lite_recovery_details_payload() -> dict[str, Any]:
    timings: dict[str, float] = {}
    state = _timed_projection_stage(timings, "recovery_base", _recovery_base_subprojection)
    profiles = _timed_projection_stage(timings, "app_backup_profiles", lite_app_lifecycle.cached_app_backup_profiles)
    lifecycle = _timed_projection_stage(
        timings,
        "app_lifecycle_profiles",
        lambda: CONTROL_PLANE.prepared_payload("apps:lifecycle")
        or lite_app_lifecycle.app_lifecycle_profiles(),
    )
    targets = _timed_projection_stage(timings, "backup_targets", lite_recovery_subprojections.backup_targets)
    state["view_model"] = "recovery-details-r3-v1"
    state["app_backups"] = profiles.get("apps", [])
    state["app_backup_profiles"] = profiles
    state["app_lifecycle_profiles"] = lifecycle
    state["backup_targets"] = targets.get("targets", [])
    state["backup_target_profiles"] = targets
    state["database_protection"] = _timed_projection_stage(
        timings, "database_protection", lite_recovery_subprojections.database_protection_details
    )
    state["maintenance"] = _timed_projection_stage(
        timings, "maintenance", lite_recovery_subprojections.maintenance_state
    )
    state["__projection_stage_timing_ms"] = timings
    return state


def _build_lite_recovery_summary_projection() -> dict[str, Any]:
    timings: dict[str, float] = {}
    state = _timed_projection_stage(timings, "recovery_summary", lite_recovery_subprojections.recovery_summary)
    state["database_protection"] = _timed_projection_stage(
        timings, "database_protection_summary", lite_recovery_subprojections.database_protection_summary
    )
    state["maintenance"] = _timed_projection_stage(
        timings, "maintenance", lite_recovery_subprojections.maintenance_state
    )
    state["__projection_stage_timing_ms"] = timings
    return state


def _project_warmup_payload(
    expected_database_path: str,
    projector: Callable[[dict[str, Any]], int],
    payload: dict[str, Any],
) -> int:
    """Prevent delayed warm-ups from projecting into a replaced database."""
    if str(database_path()) != expected_database_path:
        raise PreparedProjectionUnavailable(
            "Projection warm-up database changed before commit"
        )
    return projector(payload)


def _run_staggered_projection_warmup(expected_database_path: str) -> None:
    try:
        startup_delay = max(0.0, min(10.0, float(os.environ.get("POCKETLAB_LITE_PROJECTION_WARMUP_DELAY_SECONDS", "2.0"))))
        if startup_delay:
            threading.Event().wait(startup_delay)
        # A delayed warm-up must never follow a test, restore, or runtime
        # database-path switch into a different SQLite database.
        if str(database_path()) != expected_database_path:
            return
        lite_recovery_subprojections.warm_startup_dependencies()
        if str(database_path()) != expected_database_path:
            return
        CONTROL_PLANE.warm_prepared_read(
            domain="recovery", key="summary",
            builder=_build_lite_recovery_summary_projection,
            projector=lambda payload: _project_warmup_payload(expected_database_path, CONTROL_PLANE.project_recovery, payload), deadline_seconds=4.0,
        )
        CONTROL_PLANE.wait_for_prepared("recovery:summary", 30.0)
        threading.Event().wait(max(0.0, min(5.0, float(os.environ.get("POCKETLAB_LITE_PROJECTION_WARMUP_GAP_SECONDS", "1.0")))))
        CONTROL_PLANE.warm_prepared_read(
            domain="apps", key="lifecycle",
            builder=lite_app_lifecycle.app_lifecycle_profiles,
            projector=lambda payload: _project_warmup_payload(expected_database_path, CONTROL_PLANE.project_apps, payload), deadline_seconds=4.0,
        )
        apps_ready = CONTROL_PLANE.wait_for_prepared("apps:lifecycle", 90.0)
        recovery_ready = CONTROL_PLANE.prepared_payload("recovery:summary") is not None
        if apps_ready and recovery_ready:
            threading.Event().wait(max(0.0, min(5.0, float(os.environ.get("POCKETLAB_LITE_PROJECTION_WARMUP_GAP_SECONDS", "1.0")))))
            CONTROL_PLANE.warm_prepared_read(
                domain="recovery", key="details",
                builder=_lite_recovery_details_payload,
                projector=lambda payload: _project_warmup_payload(expected_database_path, CONTROL_PLANE.project_recovery, payload), deadline_seconds=5.0,
            )
        else:
            _LOGGER.warning(
                "pocketlab.control_projection.warmup_dependency_degraded apps_ready=%s recovery_ready=%s",
                apps_ready, recovery_ready,
            )
    except Exception as exc:
        _LOGGER.warning(
            "pocketlab.control_projection.warmup_degraded error_type=%s", type(exc).__name__
        )


def schedule_control_plane_projection_warmup() -> dict[str, bool]:
    global _WARMUP_THREAD
    if os.environ.get("POCKETLAB_LITE_DISABLE_PROJECTION_WARMUP", "").lower() in {"1", "true", "yes", "on"}:
        return {"apps": False, "recovery_summary": False, "recovery_details": False}
    with _WARMUP_LOCK:
        if _WARMUP_THREAD is not None and _WARMUP_THREAD.is_alive():
            return {"apps": False, "recovery_summary": False, "recovery_details": False}
        expected_database_path = str(database_path())
        _WARMUP_THREAD = threading.Thread(
            target=_run_staggered_projection_warmup,
            args=(expected_database_path,),
            name="pocketlab-staggered-projection-warmup",
            daemon=True,
        )
        _WARMUP_THREAD.start()
    return {"apps": True, "recovery_summary": True, "recovery_details": True}


@router.get("/recovery/summary")
def get_lite_recovery_summary(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "recovery-summary-sqlite-p3-v2"
    try:
        prepared = CONTROL_PLANE.prepared_read(
            domain="recovery",
            key="summary",
            builder=_build_lite_recovery_summary_projection,
            projector=CONTROL_PLANE.project_recovery,
            stale_after_ms=10_000,
            max_stale_ms=60_000,
            deadline_seconds=4.0,
            cold_start_async=True,
            fallback_builder=lambda: CONTROL_PLANE.recovery_projection_snapshot(details=False),
        )
    except PreparedProjectionUnavailable:
        return _projection_warming_response(domain="recovery", view_model=view_model)
    return _control_plane_prepared_response(request, prepared, view_model=view_model)


@router.get("/recovery/details")
def get_lite_recovery_details(request: Request) -> Response:
    deps.require_auth(request)
    view_model = "recovery-details-sqlite-p3-v2"
    try:
        prepared = CONTROL_PLANE.prepared_read(
            domain="recovery",
            key="details",
            builder=_lite_recovery_details_payload,
            projector=CONTROL_PLANE.project_recovery,
            stale_after_ms=15_000,
            max_stale_ms=90_000,
            deadline_seconds=5.0,
            cold_start_async=True,
            fallback_builder=lambda: CONTROL_PLANE.recovery_projection_snapshot(details=True),
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
def get_lite_recovery(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return _lite_recovery_details_payload()


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

