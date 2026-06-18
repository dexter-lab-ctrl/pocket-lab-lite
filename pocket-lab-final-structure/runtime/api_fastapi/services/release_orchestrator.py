from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from contracts import OperationRequest, OperationTarget  # type: ignore
from .. import deps
from .nats_bus import BUS

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
    updater = deps.ensure_release_updater()
    if updater is None:
        raise RuntimeError("Release updater unavailable")

    try:
        await _stage_started(
            command_id,
            "metadata_fetch",
            "Fetch release metadata",
            detail="Checking the configured GitHub release source",
        )
        result = await asyncio.to_thread(updater.check_once)
        await _stage_completed(
            command_id,
            "metadata_fetch",
            "Fetch release metadata",
            result={
                "current_tag": result.get("current_tag"),
                "latest_tag": result.get("latest_tag"),
                "update_available": result.get("update_available"),
                "published_at": (result.get("latest_release") or {}).get(
                    "published_at"
                ),
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
            {"command_id": command_id, **result},
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
                "result": result,
            },
            trace_id=command_id,
        )
        return {
            "status": "success",
            "command_id": command_id,
            "workflow": "release.check",
            **result,
        }
    except Exception as exc:
        _update_run(
            command_id, status="failed", failed_at=deps.now_utc_iso(), error=str(exc)
        )
        await _stage_failed(
            command_id, "metadata_fetch", "Fetch release metadata", str(exc)
        )
        await _publish(
            "pocketlab.events.release.workflow.failed",
            "release.workflow.failed",
            {
                "command_id": command_id,
                "workflow": "release.check",
                "status": "failed",
                "error": str(exc),
            },
            trace_id=command_id,
        )
        raise


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

    updater = deps.ensure_release_updater()
    if updater is None:
        raise RuntimeError("Release updater unavailable")

    operations: list[Dict[str, Any]] = []
    try:
        await _stage_started(
            command_id,
            "metadata_fetch",
            "Fetch release metadata",
            detail="Confirming the latest release before applying",
        )
        current_state = await asyncio.to_thread(updater.check_once)
        await _stage_completed(
            command_id,
            "metadata_fetch",
            "Fetch release metadata",
            result={
                "current_tag": current_state.get("current_tag"),
                "latest_tag": current_state.get("latest_tag"),
                "update_available": current_state.get("update_available"),
            },
        )
        if not force and not current_state.get("update_available"):
            _update_run(
                command_id,
                status="completed",
                completed_at=deps.now_utc_iso(),
                result=current_state,
            )
            await _publish(
                "pocketlab.events.release.workflow.completed",
                "release.workflow.completed",
                {
                    "command_id": command_id,
                    "workflow": "release.apply",
                    "status": "completed",
                    "result": current_state,
                },
                trace_id=command_id,
            )
            return {
                "status": "success",
                "command_id": command_id,
                "workflow": "release.apply",
                "skipped": True,
                **current_state,
            }

        await asyncio.to_thread(
            updater._set_state, phase="applying", error=None
        )  # Existing updater owns the public status file.

        operations.append(
            await _run_release_operation(
                command_id,
                "prepare",
                "Prepare rollback snapshot",
                "release_prepare",
                "backup",
                "release",
                {"scope": "full"},
            )
        )
        operations.append(
            await _run_release_operation(
                command_id,
                "gitops_synced",
                "Sync GitOps source",
                "release_sync",
                "repo",
                "pocket_lab_iac",
                {"branch": "main"},
            )
        )

        await _stage_started(
            command_id,
            "catalog_refreshed",
            "Refresh Apps & Services catalog",
            detail="Updating local catalog records",
        )
        if updater.refresh_catalog is not None:
            await asyncio.to_thread(updater.refresh_catalog)
        catalog_items = deps.core.build_catalog_view()
        deps.core.build_catalog_cache(catalog_items)
        catalog_result = {
            "operation": "catalog_refresh",
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

        operations.append(
            await _run_release_operation(
                command_id,
                "blueprint_deployed",
                "Deploy release blueprint",
                "release_deploy",
                "repo",
                "pocket_lab_iac",
                {
                    "playbook": "site.yml",
                    "source_type": "repo",
                    "source": "pocket_lab_iac",
                },
            )
        )
        operations.append(
            await _run_release_operation(
                command_id,
                "drift_verified",
                "Verify drift",
                "release_verify",
                "drift",
                "workspace",
                {"scope": "all"},
            )
        )

        await _stage_started(
            command_id,
            "health_verified",
            "Verify system health",
            detail="Checking health engine, fleet health, and telemetry",
        )
        health = deps.core.build_health_engine_snapshot()
        fleet = deps.core.build_fleet_health_snapshot(deps.core.load_fleet_nodes())
        telemetry = deps.core.telemetry_snapshot()
        health_result = {
            "operation": "health_check",
            "job_id": None,
            "status": "succeeded",
            "health": health,
            "fleet": fleet,
            "telemetry": telemetry,
        }
        operations.append(health_result)
        await _stage_completed(
            command_id,
            "health_verified",
            "Verify system health",
            result={"operation": "health_check", "status": "succeeded"},
        )
        await _publish(
            "pocketlab.events.release.health_verified",
            "release.health_verified",
            {
                "command_id": command_id,
                "status": "succeeded",
                "health": health,
                "fleet": fleet,
            },
            trace_id=command_id,
        )

        await _stage_started(
            command_id,
            "pwa_refresh_ready",
            "Prepare app refresh",
            detail="Marking the browser app as ready to refresh",
        )
        updater_state = getattr(updater, "_state", None)
        latest = (
            current_state.get("latest_release")
            or (
                getattr(updater_state, "latest_release", {})
                if updater_state is not None
                else {}
            )
            or {}
        )
        latest_tag = str(
            latest.get("tag_name")
            or current_state.get("latest_tag")
            or current_state.get("current_tag")
            or "unknown"
        )
        pwa_result = {
            "operation": "pwa_refresh",
            "job_id": None,
            "status": "succeeded",
            "latest_tag": latest_tag,
        }
        operations.append(pwa_result)
        await _stage_completed(
            command_id, "pwa_refresh_ready", "Prepare app refresh", result=pwa_result
        )
        await _publish(
            "pocketlab.events.release.pwa_refresh_ready",
            "release.pwa_refresh_ready",
            {"command_id": command_id, **pwa_result},
            trace_id=command_id,
        )

        state = await asyncio.to_thread(
            updater._set_state,
            phase="applied",
            current_tag=latest_tag,
            latest_tag=latest_tag,
            latest_release=latest,
            applied_release=latest,
            update_available=False,
            last_applied_at=deps.now_utc_iso(),
            error=None,
            operations=operations,
        )
        result = {
            "status": "success",
            "command_id": command_id,
            "workflow": "release.apply",
            "operations": operations,
            **state,
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
            result,
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.events.release.workflow.completed",
            "release.workflow.completed",
            {
                "command_id": command_id,
                "workflow": "release.apply",
                "status": "completed",
                "result": result,
            },
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.audit.release.applied",
            "release.applied",
            {
                "command_id": command_id,
                "latest_tag": latest_tag,
                "operations": operations,
            },
            trace_id=command_id,
        )
        return result
    except Exception as exc:
        state = await asyncio.to_thread(
            updater._set_state, phase="error", error=str(exc), operations=operations
        )
        _update_run(
            command_id,
            status="failed",
            failed_at=deps.now_utc_iso(),
            error=str(exc),
            result=state,
        )
        await _publish(
            "pocketlab.events.release.workflow.failed",
            "release.workflow.failed",
            {
                "command_id": command_id,
                "workflow": "release.apply",
                "status": "failed",
                "error": str(exc),
                "operations": operations,
            },
            trace_id=command_id,
        )
        raise
