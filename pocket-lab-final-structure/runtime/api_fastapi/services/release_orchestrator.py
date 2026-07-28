from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

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
    command_id = str(command.get("command_id") or command.get("trace_id") or "").strip() or uuid.uuid4().hex
    force = bool(command.get("force", False))
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
        {"command_id": command_id, "workflow": "release.apply", "status": "running"},
        trace_id=command_id,
    )

    lease = await release_runtime.begin_release_apply(command_id)
    if not lease.claimed:
        current = release_runtime.read_release_status()
        status = "success" if lease.deduplicated and current.get("last_terminal_status") == "succeeded" else "deferred"
        return {
            **current,
            "runtime_status": current.get("status"),
            "status": status,
            "command_id": command_id,
            "workflow": "release.apply",
            "coalesced": bool(lease.coalesced),
            "deduplicated": bool(lease.deduplicated),
            "retry_after_seconds": lease.retry_after_seconds,
        }

    current_state: Dict[str, Any] = {}
    subprocess_metrics: Dict[str, Any] = {}
    operations: list[Dict[str, Any]] = []
    staged: Dict[str, Any] = {}
    promoted = False
    failure_stage = "checking"
    rollback_status = ""
    try:
        await _stage_started(
            command_id,
            "check",
            "Check for updates",
            detail="Checking the verified Pocket Lab Lite release source",
        )
        current_state, subprocess_metrics = await release_runtime.check_for_apply(lease)
        operations.append({"operation": "lite_release_check", "stage": "check", "status": "succeeded"})
        await _stage_completed(
            command_id,
            "check",
            "Check for updates",
            result={
                "latest_tag": current_state.get("latest_tag"),
                "update_available": bool(current_state.get("update_available")),
                "manifest_verified": bool(current_state.get("manifest_verified")),
            },
        )
        if not current_state.get("repository_match"):
            raise release_runtime.ReleaseRuntimeError("release_product_unverified")
        if not current_state.get("manifest_verified"):
            raise release_runtime.ReleaseRuntimeError("release_manifest_unverified")
        if not current_state.get("update_available") and not force:
            state = release_runtime.finalize_release_apply(
                lease,
                {
                    **current_state,
                    "phase": "current",
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
                "skipped": True,
            }
            _update_run(command_id, status="completed", completed_at=deps.now_utc_iso(), result=result)
            return result

        if not release_runtime.renew_release_lease(lease, lease_seconds=1800):
            raise release_runtime.ReleaseStaleResult("release_apply_lease_lost")

        failure_stage = "staging"
        release_runtime.update_release_stage(lease, phase="downloading")
        await _stage_started(
            command_id,
            "staging",
            "Download and verify update",
            detail="Downloading, checking, and preparing the PWA in a private staging area",
        )
        staged, subprocess_metrics = await release_runtime.execute_release_subprocess(
            "stage", release_runtime.build_stage_request(current_state, lease)
        )
        operations.append({"operation": "lite_artifact_stage", "stage": "staging", "status": "succeeded"})
        await _stage_completed(
            command_id,
            "staging",
            "Download and verify update",
            result={
                "release_tag": staged.get("release_tag"),
                "manifest_verified": bool(staged.get("manifest_verified")),
                "artifact_verified": bool(staged.get("artifact_verified")),
            },
        )
        if not release_runtime.renew_release_lease(lease, lease_seconds=1800):
            raise release_runtime.ReleaseStaleResult("release_apply_lease_lost")

        failure_stage = "promotion"
        release_runtime.update_release_stage(lease, phase="installing")
        await _stage_started(
            command_id,
            "promotion",
            "Install update",
            detail="Switching the versioned PWA pointer after complete staging",
        )
        promotion, subprocess_metrics = await release_runtime.execute_release_subprocess(
            "promote", release_runtime.build_promote_request(staged)
        )
        promoted = True
        operations.append({"operation": "lite_pwa_promote", "stage": "promotion", "status": "succeeded"})
        await _stage_completed(
            command_id,
            "promotion",
            "Install update",
            result={
                "release_tag": promotion.get("release_tag"),
                "rollback_available": bool(promotion.get("rollback_available")),
            },
        )
        if not release_runtime.renew_release_lease(lease, lease_seconds=1800):
            raise release_runtime.ReleaseStaleResult("release_apply_lease_lost")

        failure_stage = "validation"
        release_runtime.update_release_stage(lease, phase="validating")
        await _stage_started(
            command_id,
            "validation",
            "Check the update",
            detail="Confirming the new PWA and prepared API remain healthy",
        )
        validation, subprocess_metrics = await release_runtime.execute_release_subprocess(
            "validate",
            release_runtime.build_validate_request(
                {**staged, "pm2_restart_baseline": promotion.get("pm2_restart_baseline") or {}}
            ),
        )
        operations.append({"operation": "lite_release_validate", "stage": "validation", "status": "succeeded"})
        await _stage_completed(
            command_id,
            "validation",
            "Check the update",
            result={"release_tag": validation.get("release_tag"), "validation_status": "passed"},
        )

        manifest = ((current_state.get("latest_release") or {}).get("manifest") or {})
        identity = release_runtime.record_release_install(
            release_tag=str(staged.get("release_tag") or ""),
            source_repository=str(current_state.get("verified_repository") or ""),
            source_commit=str(manifest.get("source_commit") or ""),
            artifact_sha256=str(staged.get("artifact_sha256") or ""),
        )
        latest_tag = str(staged.get("release_tag") or "")
        state = release_runtime.finalize_release_apply(
            lease,
            {
                **current_state,
                "phase": "installed",
                "current_tag": latest_tag,
                "latest_tag": latest_tag,
                "comparison": "equal",
                "update_available": False,
                "install_mode": "release",
                "installed_release_tag": latest_tag,
                "installed_source_commit": identity.get("source_commit"),
                "manifest_verified": True,
                "artifact_verified": True,
                "staging_status": "ready",
                "promotion_status": "installed",
                "rollback_available": bool(promotion.get("rollback_available")),
                "last_failure_stage": "",
                "last_rollback_status": "",
                "applied_release": {
                    "tag_name": latest_tag,
                    "source_commit": identity.get("source_commit"),
                    "artifact_sha256": identity.get("artifact_sha256"),
                    "installed_at": identity.get("installed_at"),
                    "verified": True,
                },
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
        _update_run(command_id, status="completed", completed_at=deps.now_utc_iso(), result=result)
        await _publish(
            "pocketlab.events.release.applied",
            "release.applied",
            {
                "command_id": command_id,
                "latest_tag": latest_tag,
                "projection_revision": state.get("projection_revision"),
                "sanitized": True,
            },
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.audit.release.applied",
            "release.applied",
            {"command_id": command_id, "latest_tag": latest_tag, "sanitized": True},
            trace_id=command_id,
        )
        return result
    except Exception as exc:
        failure_code = str(getattr(exc, "code", "") or str(exc) or type(exc).__name__)[:80]
        if promoted:
            try:
                rollback, rollback_metrics = await release_runtime.execute_release_subprocess(
                    "rollback", release_runtime.build_rollback_request()
                )
                subprocess_metrics = rollback_metrics
                rollback_status = str(rollback.get("rollback_status") or "rolled_back")
                restored = str(rollback.get("restored_release_tag") or "")
                if restored:
                    validation_request = release_runtime.build_validate_request(
                        {
                            "release_tag": restored,
                            "install_mode": "release" if restored.startswith("lite-") else "source",
                            "archive": {},
                        }
                    )
                    await release_runtime.execute_release_subprocess("validate", validation_request)
                await _publish(
                    "pocketlab.audit.release.rolled_back",
                    "release.rolled_back",
                    {
                        "command_id": command_id,
                        "rollback_status": rollback_status,
                        "failure_stage": failure_stage,
                        "failure_code": failure_code,
                        "sanitized": True,
                    },
                    trace_id=command_id,
                )
            except Exception:
                rollback_status = "rollback_failed"
        try:
            state = release_runtime.fail_release_apply(
                lease,
                failure_code,
                subprocess_metrics=subprocess_metrics,
                failure_stage=failure_stage,
                rollback_status=rollback_status,
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
                "failure_stage": failure_stage,
                "rollback_status": rollback_status,
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
            "failure_stage": failure_stage,
            "rollback_status": rollback_status,
            "operations": operations,
        }
