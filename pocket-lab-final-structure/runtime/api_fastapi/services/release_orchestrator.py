from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from contracts import OperationRequest, OperationTarget  # type: ignore
from .. import deps
from .nats_bus import BUS
from . import release_runtime

SENSITIVE_KEYS = {"api_key", "token", "password", "secret", "value"}


def _safe(data: Dict[str, Any]) -> Dict[str, Any]:
    safe: Dict[str, Any] = {}
    for key, value in data.items():
        safe[key] = "***" if key in SENSITIVE_KEYS else value
    return safe


async def _publish(
    subject: str, event_type: str, data: Dict[str, Any], *, trace_id: str | None = None
) -> None:
    await BUS.publish_json(subject, event_type, _safe(data), trace_id=trace_id)


def _state_path() -> Path:
    return deps.settings().state_dir / "release_orchestration.json"


def _read_state() -> Dict[str, Any]:
    return deps.core.read_json_file(_state_path(), {"runs": []})


def _write_state(state: Dict[str, Any]) -> None:
    deps.core.write_json_file(_state_path(), state)


def _update_run(command_id: str, **fields: Any) -> Dict[str, Any]:
    state = _read_state()
    runs = list(state.get("runs") or [])
    idx = next(
        (i for i, item in enumerate(runs) if str(item.get("command_id")) == command_id),
        None,
    )
    now = deps.now_utc_iso()
    if idx is None:
        record = {
            "command_id": command_id,
            "created_at": now,
            "updated_at": now,
            "stages": [],
        }
        runs.insert(0, record)
        idx = 0
    record = dict(runs[idx])
    record.update(fields)
    record["updated_at"] = now
    runs[idx] = record
    state["runs"] = runs[:50]
    state["latest"] = record
    _write_state(state)
    return record


def _update_stage(command_id: str, stage_id: str, **fields: Any) -> Dict[str, Any]:
    record = _update_run(command_id)
    stages = list(record.get("stages") or [])
    idx = next(
        (i for i, item in enumerate(stages) if str(item.get("id")) == stage_id), None
    )
    now = deps.now_utc_iso()
    if idx is None:
        stage = {"id": stage_id, "created_at": now, "updated_at": now}
        stages.append(stage)
        idx = len(stages) - 1
    stage = dict(stages[idx])
    stage.update(fields)
    stage["updated_at"] = now
    stages[idx] = stage
    return _update_run(command_id, stages=stages)


def release_orchestration_status() -> Dict[str, Any]:
    state = _read_state()
    state.setdefault("runs", [])
    state.setdefault("latest", {})
    return state


async def _stage_started(
    command_id: str,
    stage_id: str,
    title: str,
    *,
    detail: str = "",
    trace_id: str | None = None,
) -> None:
    _update_stage(
        command_id,
        stage_id,
        title=title,
        status="running",
        started_at=deps.now_utc_iso(),
        detail=detail,
    )
    await _publish(
        "pocketlab.events.release.stage.started",
        "release.stage.started",
        {
            "command_id": command_id,
            "stage": stage_id,
            "title": title,
            "detail": detail,
            "status": "running",
        },
        trace_id=trace_id or command_id,
    )


async def _stage_completed(
    command_id: str,
    stage_id: str,
    title: str,
    *,
    result: Optional[Dict[str, Any]] = None,
    trace_id: str | None = None,
) -> None:
    payload = {
        "command_id": command_id,
        "stage": stage_id,
        "title": title,
        "status": "completed",
        "result": result or {},
    }
    _update_stage(
        command_id,
        stage_id,
        status="completed",
        completed_at=deps.now_utc_iso(),
        result=result or {},
    )
    await _publish(
        "pocketlab.events.release.stage.completed",
        "release.stage.completed",
        payload,
        trace_id=trace_id or command_id,
    )


async def _stage_failed(
    command_id: str,
    stage_id: str,
    title: str,
    error: str,
    *,
    trace_id: str | None = None,
) -> None:
    _update_stage(
        command_id,
        stage_id,
        title=title,
        status="failed",
        failed_at=deps.now_utc_iso(),
        error=error,
    )
    await _publish(
        "pocketlab.events.release.stage.failed",
        "release.stage.failed",
        {
            "command_id": command_id,
            "stage": stage_id,
            "title": title,
            "status": "failed",
            "error": error,
        },
        trace_id=trace_id or command_id,
    )


def _run_operation_sync(
    operation: str,
    target_type: str,
    target_ref: str,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    request = OperationRequest(
        operation=operation,
        target=OperationTarget(type=target_type, ref=target_ref),
        params=dict(params or {}),
        dry_run=False,
    )
    submitted = deps.operation_service().submit_queued(request)
    return deps.operation_service().run_existing(str(submitted["job_id"]))


async def _run_release_operation(
    command_id: str,
    stage_id: str,
    title: str,
    operation: str,
    target_type: str,
    target_ref: str,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    await _stage_started(command_id, stage_id, title, detail=f"Running {operation}")
    run = await asyncio.to_thread(
        _run_operation_sync, operation, target_type, target_ref, params or {}
    )
    status = str(run.get("status") or "unknown").lower()
    result = {
        "operation": operation,
        "job_id": run.get("job_id"),
        "status": status,
        "exit_code": run.get("exit_code"),
        "artifacts": run.get("artifacts") or {},
    }
    if status != "succeeded":
        raise RuntimeError(
            run.get("error") or run.get("stderr") or f"{operation} failed"
        )
    await _stage_completed(command_id, stage_id, title, result=result)
    await _publish(
        f"pocketlab.events.release.{stage_id}",
        f"release.{stage_id}",
        {"command_id": command_id, "stage": stage_id, **result},
        trace_id=command_id,
    )
    return result


async def check_release(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = str(command.get("command_id") or command.get("trace_id") or "").strip()
    if not command_id:
        command_id = uuid.uuid4().hex
    _update_run(
        command_id,
        workflow="release.check",
        status="running",
        started_at=deps.now_utc_iso(),
    )
    await _publish(
        "pocketlab.events.release.workflow.started",
        "release.workflow.started",
        {"command_id": command_id, "workflow": "release.check", "status": "running"},
        trace_id=command_id,
    )
    await _stage_started(
        command_id,
        "metadata_fetch",
        "Fetch release metadata",
        detail="Checking the configured release source in an isolated process",
    )
    result = await release_runtime.run_release_check(
        command_id,
        source=str(command.get("source") or "manual"),
    )
    if result.get("deduplicated"):
        _update_run(
            command_id,
            status="completed" if result.get("last_terminal_status") == "succeeded" else "failed",
            completed_at=deps.now_utc_iso(),
            result=result,
        )
        return {
            **result,
            "runtime_status": result.get("status"),
            "status": "success" if result.get("last_terminal_status") == "succeeded" else "failed",
            "command_id": command_id,
            "workflow": "release.check",
            "deduplicated": True,
        }
    if result.get("coalesced"):
        await _stage_completed(
            command_id,
            "metadata_fetch",
            "Fetch release metadata",
            result={
                "coalesced": True,
                "retry_after_seconds": result.get("retry_after_seconds"),
                "phase": result.get("phase"),
            },
        )
        _update_run(
            command_id,
            status="deferred",
            completed_at=deps.now_utc_iso(),
            result=result,
        )
        return {
            **result,
            "runtime_status": result.get("status"),
            "status": "deferred",
            "command_id": command_id,
            "workflow": "release.check",
        }
    if result.get("status") == "degraded":
        failure_code = str(result.get("last_failure_code") or "release_check_failed")
        await _stage_failed(
            command_id,
            "metadata_fetch",
            "Fetch release metadata",
            failure_code,
        )
        _update_run(
            command_id,
            status="failed",
            failed_at=deps.now_utc_iso(),
            error=failure_code,
            result=result,
        )
        await _publish(
            "pocketlab.events.release.workflow.failed",
            "release.workflow.failed",
            {
                "command_id": command_id,
                "workflow": "release.check",
                "status": "failed",
                "failure_code": failure_code,
                "last_known_good": bool(result.get("last_known_good")),
            },
            trace_id=command_id,
        )
        return {
            **result,
            "runtime_status": result.get("status"),
            "status": "failed",
            "command_id": command_id,
            "workflow": "release.check",
        }
    await _stage_completed(
        command_id,
        "metadata_fetch",
        "Fetch release metadata",
        result={
            "current_tag": result.get("current_tag"),
            "latest_tag": result.get("latest_tag"),
            "update_available": result.get("update_available"),
            "published_at": (result.get("latest_release") or {}).get("published_at"),
            "changed": result.get("changed"),
        },
    )
    subject = (
        "pocketlab.events.release.available"
        if result.get("update_available")
        else "pocketlab.events.release.current"
    )
    event_type = (
        "release.available" if result.get("update_available") else "release.current"
    )
    await _publish(
        subject,
        event_type,
        {
            "command_id": command_id,
            "current_tag": result.get("current_tag"),
            "latest_tag": result.get("latest_tag"),
            "update_available": bool(result.get("update_available")),
            "projection_revision": result.get("projection_revision"),
            "changed": bool(result.get("changed")),
            "sanitized": True,
        },
        trace_id=command_id,
    )
    _update_run(
        command_id,
        status="completed",
        completed_at=deps.now_utc_iso(),
        result=result,
    )
    await _publish(
        "pocketlab.events.release.workflow.completed",
        "release.workflow.completed",
        {
            "command_id": command_id,
            "workflow": "release.check",
            "status": "completed",
            "result": {
                "current_tag": result.get("current_tag"),
                "latest_tag": result.get("latest_tag"),
                "update_available": bool(result.get("update_available")),
                "projection_revision": result.get("projection_revision"),
            },
        },
        trace_id=command_id,
    )
    return {
        **result,
        "runtime_status": result.get("status"),
        "status": "success",
        "command_id": command_id,
        "workflow": "release.check",
    }


async def apply_release(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = str(command.get("command_id") or command.get("trace_id") or "").strip()
    if not command_id:
        command_id = uuid.uuid4().hex
    force = bool(command.get("force", True))
    _update_run(
        command_id,
        workflow="release.apply",
        status="running",
        started_at=deps.now_utc_iso(),
        force=force,
    )
    await _publish(
        "pocketlab.events.release.workflow.started",
        "release.workflow.started",
        {
            "command_id": command_id,
            "workflow": "release.apply",
            "status": "running",
            "force": force,
        },
        trace_id=command_id,
    )

    lease = await release_runtime.begin_release_apply(command_id)
    if not lease.claimed:
        current = release_runtime.read_release_status()
        if lease.deduplicated:
            terminal_status = str(current.get("last_terminal_status") or "failed")
            result = {
                **current,
                "runtime_status": current.get("status"),
                "status": "success" if terminal_status == "succeeded" else "failed",
                "command_id": command_id,
                "workflow": "release.apply",
                "deduplicated": True,
            }
            _update_run(
                command_id,
                status="completed" if terminal_status == "succeeded" else "failed",
                completed_at=deps.now_utc_iso(),
                result=result,
            )
            return result
        result = {
            **current,
            "runtime_status": current.get("status"),
            "status": "deferred",
            "command_id": command_id,
            "workflow": "release.apply",
            "coalesced": True,
            "retry_after_seconds": lease.retry_after_seconds,
        }
        _update_run(
            command_id,
            status="deferred",
            completed_at=deps.now_utc_iso(),
            result=result,
        )
        return result

    operations: list[Dict[str, Any]] = []
    subprocess_metrics: dict[str, Any] = {}
    try:
        await _stage_started(
            command_id,
            "metadata_fetch",
            "Check release",
            detail="Confirming the target release in an isolated process",
        )
        current_state, subprocess_metrics = await release_runtime.check_for_apply(lease)
        await _stage_completed(
            command_id,
            "metadata_fetch",
            "Check release",
            result={
                "current_tag": current_state.get("current_tag"),
                "latest_tag": current_state.get("latest_tag"),
                "update_available": current_state.get("update_available"),
            },
        )
        if not force and not current_state.get("update_available"):
            state = release_runtime.finalize_release_apply(
                lease,
                {
                    **current_state,
                    "phase": "current",
                    "operations": [],
                    "last_known_good": True,
                },
                subprocess_metrics=subprocess_metrics,
            )
            result = {
                **state,
                "runtime_status": state.get("status"),
                "status": "success",
                "command_id": command_id,
                "workflow": "release.apply",
                "skipped": True,
            }
            _update_run(
                command_id,
                status="completed",
                completed_at=deps.now_utc_iso(),
                result=result,
            )
            await _publish(
                "pocketlab.events.release.workflow.completed",
                "release.workflow.completed",
                {
                    "command_id": command_id,
                    "workflow": "release.apply",
                    "status": "completed",
                    "skipped": True,
                },
                trace_id=command_id,
            )
            return result

        release_runtime.update_release_stage(lease, phase="preparing")
        prepare = await _run_release_operation(
            command_id,
            "prepare",
            "Prepare rollback snapshot",
            "release_prepare",
            "backup",
            "release",
            {"scope": "full"},
        )
        prepare["stage"] = "prepare"
        operations.append(prepare)
        if not release_runtime.renew_release_lease(lease, lease_seconds=1800):
            raise release_runtime.ReleaseStaleResult("release_apply_lease_lost")

        release_runtime.update_release_stage(lease, phase="downloading")
        downloaded = await _run_release_operation(
            command_id,
            "download",
            "Download release source",
            "release_sync",
            "repo",
            "pocket_lab_iac",
            {"branch": "main"},
        )
        downloaded["stage"] = "download"
        operations.append(downloaded)
        if not release_runtime.renew_release_lease(lease, lease_seconds=1800):
            raise release_runtime.ReleaseStaleResult("release_apply_lease_lost")

        await _stage_started(
            command_id,
            "catalog_refreshed",
            "Refresh Apps & Services catalog",
            detail="Updating worker-owned catalog records",
        )
        catalog_items = await asyncio.to_thread(deps.core.build_catalog_view)
        await asyncio.to_thread(deps.core.build_catalog_cache, catalog_items)
        catalog_result = {
            "operation": "catalog_refresh",
            "stage": "catalog_refreshed",
            "job_id": None,
            "status": "succeeded",
            "count": len(catalog_items),
        }
        operations.append(catalog_result)
        await _stage_completed(
            command_id,
            "catalog_refreshed",
            "Refresh Apps & Services catalog",
            result=catalog_result,
        )
        await _publish(
            "pocketlab.events.release.catalog_refreshed",
            "release.catalog_refreshed",
            {"command_id": command_id, **catalog_result},
            trace_id=command_id,
        )

        release_runtime.update_release_stage(lease, phase="applying")
        applied = await _run_release_operation(
            command_id,
            "apply",
            "Apply release blueprint",
            "release_deploy",
            "repo",
            "pocket_lab_iac",
            {
                "playbook": "site.yml",
                "source_type": "repo",
                "source": "pocket_lab_iac",
            },
        )
        applied["stage"] = "apply"
        operations.append(applied)
        if not release_runtime.renew_release_lease(lease, lease_seconds=1800):
            raise release_runtime.ReleaseStaleResult("release_apply_lease_lost")

        release_runtime.update_release_stage(lease, phase="verifying")
        verified = await _run_release_operation(
            command_id,
            "verify",
            "Verify applied release",
            "release_verify",
            "drift",
            "workspace",
            {"scope": "all"},
        )
        verified["stage"] = "verify"
        operations.append(verified)
        if not release_runtime.renew_release_lease(lease, lease_seconds=1800):
            raise release_runtime.ReleaseStaleResult("release_apply_lease_lost")

        await _stage_started(
            command_id,
            "health_verified",
            "Verify system health",
            detail="Checking health engine, fleet health, and telemetry",
        )
        health = await asyncio.to_thread(deps.core.build_health_engine_snapshot)
        fleet = await asyncio.to_thread(
            deps.core.build_fleet_health_snapshot, deps.core.load_fleet_nodes()
        )
        telemetry = await asyncio.to_thread(deps.core.telemetry_snapshot)
        health_result = {
            "operation": "health_check",
            "stage": "health_verified",
            "job_id": None,
            "status": "succeeded",
        }
        operations.append(health_result)
        await _stage_completed(
            command_id,
            "health_verified",
            "Verify system health",
            result=health_result,
        )
        await _publish(
            "pocketlab.events.release.health_verified",
            "release.health_verified",
            {
                "command_id": command_id,
                "status": "succeeded",
                "health_status": (health or {}).get("status") if isinstance(health, dict) else "unknown",
                "fleet_status": (fleet or {}).get("status") if isinstance(fleet, dict) else "unknown",
                "telemetry_ready": bool(telemetry),
                "sanitized": True,
            },
            trace_id=command_id,
        )

        latest = current_state.get("latest_release") or {}
        latest_tag = str(
            latest.get("tag_name")
            or current_state.get("latest_tag")
            or current_state.get("current_tag")
            or "unknown"
        )
        state = release_runtime.finalize_release_apply(
            lease,
            {
                **current_state,
                "phase": "applied",
                "current_tag": latest_tag,
                "latest_tag": latest_tag,
                "latest_release": latest,
                "applied_release": {
                    "tag_name": latest_tag,
                    "applied_at": deps.now_utc_iso(),
                },
                "update_available": False,
                "operations": operations,
                "last_known_good": True,
            },
            subprocess_metrics=subprocess_metrics,
        )
        result = {
            **state,
            "runtime_status": state.get("status"),
            "status": "success",
            "command_id": command_id,
            "workflow": "release.apply",
            "operations": operations,
        }
        _update_run(
            command_id,
            status="completed",
            completed_at=deps.now_utc_iso(),
            result=result,
        )
        await _publish(
            "pocketlab.events.release.applied",
            "release.applied",
            {
                "command_id": command_id,
                "latest_tag": latest_tag,
                "operation_count": len(operations),
                "projection_revision": state.get("projection_revision"),
                "sanitized": True,
            },
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.events.release.workflow.completed",
            "release.workflow.completed",
            {
                "command_id": command_id,
                "workflow": "release.apply",
                "status": "completed",
                "latest_tag": latest_tag,
            },
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.audit.release.applied",
            "release.applied",
            {
                "command_id": command_id,
                "latest_tag": latest_tag,
                "operation_count": len(operations),
                "sanitized": True,
            },
            trace_id=command_id,
        )
        return result
    except Exception as exc:
        failure_code = str(getattr(exc, "code", "") or type(exc).__name__)[:80]
        try:
            state = release_runtime.fail_release_apply(
                lease,
                failure_code,
                subprocess_metrics=subprocess_metrics,
            )
        except release_runtime.ReleaseStaleResult:
            state = release_runtime.read_release_status()
        _update_run(
            command_id,
            status="failed",
            failed_at=deps.now_utc_iso(),
            error=failure_code,
            result=state,
        )
        await _publish(
            "pocketlab.events.release.workflow.failed",
            "release.workflow.failed",
            {
                "command_id": command_id,
                "workflow": "release.apply",
                "status": "failed",
                "failure_code": failure_code,
                "operation_count": len(operations),
                "last_known_good": bool(state.get("last_known_good")),
                "sanitized": True,
            },
            trace_id=command_id,
        )
        return {
            **state,
            "runtime_status": state.get("status"),
            "status": "failed",
            "command_id": command_id,
            "workflow": "release.apply",
            "failure_code": failure_code,
            "operations": operations,
        }
