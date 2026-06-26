from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Iterable

from contracts import OperationRequest, OperationTarget  # type: ignore
from .. import deps
from .nats_bus import BUS

SENSITIVE_KEYS = {"api_key", "token", "password", "secret", "value"}


def _safe(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: ("***" if k in SENSITIVE_KEYS else v) for k, v in data.items()}


async def _publish(
    subject: str, event_type: str, data: Dict[str, Any], *, trace_id: str | None = None
) -> None:
    await BUS.publish_json(subject, event_type, _safe(data), trace_id=trace_id)


def _command_id(command: Dict[str, Any]) -> str:
    return str(
        command.get("command_id")
        or command.get("job_id")
        or command.get("trace_id")
        or ""
    ).strip()


def _targets(command: Dict[str, Any]) -> list[str]:
    value = command.get("targets") or command.get("target") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(v) for v in value]
    return []


def _run_typed_operation(
    command_id: str, operation: str, target: Dict[str, Any], params: Dict[str, Any]
) -> Dict[str, Any]:
    request = OperationRequest(
        operation=operation,
        target=OperationTarget(
            type=str(target.get("type") or "repo"), ref=str(target.get("ref") or "")
        ),
        params=dict(params or {}),
        dry_run=bool(params.get("dry_run", False)),
    )
    submitted = deps.operation_service().submit_queued(
        request, job_id=command_id or None
    )
    return deps.operation_service().run_existing(str(submitted["job_id"]))


def _drift_mutation(action: str, targets: list[str]) -> Dict[str, Any]:
    state = deps.core.load_drift_state()
    jobs = list(state.get("jobs", []))
    wanted = {str(v).lower() for v in targets}
    changed = 0
    for job in jobs:
        matches = (
            not wanted
            or str(job.get("target")).lower() in wanted
            or str(job.get("job_id")).lower() in wanted
        )
        if not matches:
            continue
        changed += 1
        if action == "approve":
            job["approval_state"] = "approved"
            job["updated_at"] = deps.now_utc_iso()
        elif action == "apply":
            job["status"] = "healthy"
            job["approval_state"] = "applied"
            job["updated_at"] = deps.now_utc_iso()
            job.setdefault("result", {})["applied"] = True
        elif action == "ignore":
            job["approval_state"] = "ignored"
            job["updated_at"] = deps.now_utc_iso()
    updated = deps.core.update_drift_from_jobs(jobs)
    return {
        "status": "success",
        "action": action,
        "changed": changed,
        "summary": updated["summary"],
        "metrics": updated["metrics"],
        "jobs": updated["jobs"],
        "selected": list(wanted),
    }


async def handle_catalog_refresh(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    await _publish(
        "pocketlab.events.catalog.refresh_started",
        "catalog.refresh_started",
        {"command_id": command_id},
        trace_id=command_id,
    )
    items = deps.core.build_catalog_view()
    deps.core.build_catalog_cache(items)
    result = {
        "status": "success",
        "command_id": command_id,
        "count": len(items),
        "items": items,
        "updated_at": deps.now_utc_iso(),
    }
    await _publish(
        "pocketlab.events.catalog.refreshed",
        "catalog.refreshed",
        {
            "command_id": command_id,
            "count": len(items),
            "updated_at": result["updated_at"],
        },
        trace_id=command_id,
    )
    return result


async def handle_drift_scan(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    await _publish(
        "pocketlab.events.drift.scan_started",
        "drift.scan_started",
        {"command_id": command_id, "scope": command.get("scope", "all")},
        trace_id=command_id,
    )
    run = await asyncio.to_thread(
        _run_typed_operation,
        command_id,
        "drift_scan",
        {"type": "drift", "ref": str(command.get("ref") or "workspace")},
        {"scope": command.get("scope", "all"), "action": command.get("action", "scan")},
    )
    artifacts = run.get("artifacts") or {}
    if isinstance(artifacts, dict) and artifacts.get("summary"):
        deps.core.save_drift_state(
            {
                "summary": artifacts.get("summary", {}),
                "metrics": artifacts.get("metrics", {}),
                "jobs": artifacts.get("jobs", []),
            }
        )
    state = deps.core.load_drift_state()
    result = {
        "status": run.get("status"),
        "command_id": command_id,
        "job_id": run.get("job_id"),
        "summary": state.get("summary", {}),
        "metrics": state.get("metrics", {}),
        "jobs": state.get("jobs", []),
    }
    if result["summary"].get("drifted", 0) or result["summary"].get("failed", 0):
        await _publish(
            "pocketlab.events.drift.detected",
            "drift.detected",
            result,
            trace_id=command_id,
        )
    await _publish(
        "pocketlab.events.drift.scan_completed",
        "drift.scan_completed",
        result,
        trace_id=command_id,
    )
    return result


async def handle_drift_preview(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    state = deps.core.load_drift_state()
    wanted = {str(v).lower() for v in _targets(command)}
    jobs = list(state.get("jobs", []))
    if wanted:
        jobs = [
            j
            for j in jobs
            if str(j.get("target")).lower() in wanted
            or str(j.get("job_id")).lower() in wanted
        ]
    result = {
        "status": "success",
        "command_id": command_id,
        "summary": state.get("summary", {}),
        "metrics": state.get("metrics", {}),
        "jobs": jobs,
        "selected": list(wanted),
    }
    await _publish(
        "pocketlab.events.drift.previewed",
        "drift.previewed",
        result,
        trace_id=command_id,
    )
    return result


async def handle_drift_mutation(action: str, command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    await _publish(
        f"pocketlab.events.drift.{action}_started",
        f"drift.{action}_started",
        {"command_id": command_id, "targets": _targets(command)},
        trace_id=command_id,
    )
    result = _drift_mutation(action, _targets(command))
    result["command_id"] = command_id
    await _publish(
        f"pocketlab.events.drift.{action}",
        f"drift.{action}",
        result,
        trace_id=command_id,
    )
    return result


async def handle_fleet_join(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    role = str(command.get("role") or "compute")
    hostname = command.get("hostname")
    await _publish(
        "pocketlab.events.fleet.invite_started",
        "fleet.invite_started",
        {"command_id": command_id, "role": role, "hostname": hostname},
        trace_id=command_id,
    )
    run = await asyncio.to_thread(
        _run_typed_operation,
        command_id,
        "fleet_join",
        {"type": "fleet", "ref": role},
        {"role": role, "hostname": hostname},
    )
    artifacts = run.get("artifacts") or {}
    result = {
        "status": run.get("status"),
        "command_id": command_id,
        "job_id": run.get("job_id"),
        "role": role,
        "hostname": hostname,
        "artifacts": artifacts,
    }
    await _publish(
        "pocketlab.events.fleet.invite_created",
        "fleet.invite_created",
        result,
        trace_id=command_id,
    )
    return result


async def handle_fleet_save_tailscale_key(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    secret_ref = Path(str(command.get("secret_ref") or ""))
    secret = deps.core.read_json_file(secret_ref, {}) if secret_ref else {}
    api_key = str(secret.get("api_key") or "")
    if not api_key.startswith("tskey-api-"):
        raise RuntimeError("Invalid or missing Tailscale key in secure command payload")
    deps.core.set_tailscale_api_key(api_key)
    try:
        secret_ref.unlink()
    except Exception:
        pass
    result = {"status": "success", "command_id": command_id, "configured": True}
    await _publish(
        "pocketlab.audit.fleet.tailscale_key_saved",
        "fleet.tailscale_key_saved",
        result,
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.events.fleet.config_updated",
        "fleet.config_updated",
        result,
        trace_id=command_id,
    )
    return result


async def handle_release_check(command: Dict[str, Any]) -> Dict[str, Any]:
    from .release_orchestrator import check_release

    return await check_release(command)


async def handle_release_apply(command: Dict[str, Any]) -> Dict[str, Any]:
    from .release_orchestrator import apply_release

    return await apply_release(command)


async def handle_health_check(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    from .live_status import LIVE_STATUS

    sample = await LIVE_STATUS.sample_all(source="worker-command")
    result = {
        "status": "success",
        "command_id": command_id,
        "health": sample["health"],
        "fleet": sample["fleet"],
        "telemetry": sample["telemetry"],
        "checked_at": sample["sampled_at"],
    }
    await _publish(
        "pocketlab.events.health.check_completed",
        "health.check_completed",
        {
            "command_id": command_id,
            "snapshot": sample["health"],
            "telemetry": sample["telemetry"],
            "fleet": sample["fleet"],
        },
        trace_id=command_id,
    )
    return result


async def handle_security_scan(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    await _publish(
        "pocketlab.events.security.scan_started",
        "security.scan_started",
        {"command_id": command_id},
        trace_id=command_id,
    )
    evaluations = deps.core.build_opa_evaluations()
    deps.core.write_json_file(
        deps.settings().state_dir / "opa_evaluations.json", evaluations
    )
    findings = [
        item
        for item in evaluations
        if str(item.get("decision") or item.get("status") or "").lower()
        in {"deny", "failed", "blocked"}
    ]
    result = {
        "status": "success",
        "command_id": command_id,
        "evaluations": evaluations,
        "findings": findings,
        "count": len(evaluations),
        "findings_count": len(findings),
        "scanned_at": deps.now_utc_iso(),
    }
    for finding in findings[:25]:
        await _publish(
            "pocketlab.events.security.finding",
            "security.finding",
            {"command_id": command_id, "finding": finding},
            trace_id=command_id,
        )
    await _publish(
        "pocketlab.events.security.scan_completed",
        "security.scan_completed",
        {k: v for k, v in result.items() if k != "evaluations"},
        trace_id=command_id,
    )
    return result


async def handle_security_configure_opa(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    state = deps.core.read_json_file(
        deps.settings().state_dir / "opa.json", {"enforce_mode": False}
    )
    state["enforce_mode"] = bool(command.get("enforce_mode", False))
    state["updated_at"] = deps.now_utc_iso()
    deps.core.write_json_file(deps.settings().state_dir / "opa.json", state)
    evaluations = deps.core.build_opa_evaluations()
    deps.core.write_json_file(
        deps.settings().state_dir / "opa_evaluations.json", evaluations
    )
    result = {
        "status": "success",
        "command_id": command_id,
        "enforce_mode": state["enforce_mode"],
        "evaluations": evaluations,
    }
    await _publish(
        "pocketlab.events.security.policy_updated",
        "security.policy_updated",
        {"command_id": command_id, "enforce_mode": state["enforce_mode"]},
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.security.policy_updated",
        "security.policy_updated",
        {"command_id": command_id, "enforce_mode": state["enforce_mode"]},
        trace_id=command_id,
    )
    return result


async def handle_vault_rotate(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    target = str(command.get("target") or command.get("secret") or "secret")
    params = {"target": target}
    if command.get("lease_duration"):
        params["lease_duration"] = command.get("lease_duration")
    if command.get("value"):
        params["value"] = command.get("value")
    run = await asyncio.to_thread(
        _run_typed_operation,
        command_id,
        "rotate_secret",
        {"type": "vault", "ref": target},
        params,
    )
    result = {
        "status": run.get("status"),
        "command_id": command_id,
        "job_id": run.get("job_id"),
        "secret": target,
        "artifacts": run.get("artifacts") or {},
    }
    await _publish(
        "pocketlab.events.vault.secret_rotated",
        "vault.secret_rotated",
        result,
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.vault.secret_rotated",
        "vault.secret_rotated",
        {"command_id": command_id, "secret": target},
        trace_id=command_id,
    )
    return result


async def handle_vault_dynamic_secret(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    target = str(command.get("target") or "default")
    run = await asyncio.to_thread(
        _run_typed_operation,
        command_id,
        "secret_read_dynamic",
        {"type": "vault", "ref": target},
        {"target": target},
    )
    result = {
        "status": run.get("status"),
        "command_id": command_id,
        "job_id": run.get("job_id"),
        "target": target,
        "artifacts": run.get("artifacts") or {},
    }
    await _publish(
        "pocketlab.events.vault.lease_created",
        "vault.lease_created",
        result,
        trace_id=command_id,
    )
    return result


async def handle_lite_catalog_install(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    app_id = str(command.get("app_id") or "photoprism")
    await _publish(
        "pocketlab.events.lite.catalog.install_started",
        "lite.catalog.install_started",
        {"command_id": command_id, "app_id": app_id, "target_node_id": command.get("target_node_id")},
        trace_id=command_id,
    )
    from . import lite_catalog

    try:
        result = await asyncio.to_thread(lite_catalog.run_install, command)
    except Exception as exc:
        await _publish(
            "pocketlab.events.lite.catalog.install_failed",
            "lite.catalog.install_failed",
            {"command_id": command_id, "app_id": app_id, "error": str(exc)},
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.audit.lite.catalog.install_failed",
            "lite.catalog.install_failed",
            {"command_id": command_id, "app_id": app_id, "status": "failed"},
            trace_id=command_id,
        )
        raise

    status = str(result.get("status") or "unknown")
    event_subject = "pocketlab.events.lite.catalog.install_completed" if status == "succeeded" else "pocketlab.events.lite.catalog.install_failed"
    event_type = "lite.catalog.install_completed" if status == "succeeded" else "lite.catalog.install_failed"
    await _publish(
        event_subject,
        event_type,
        {
            "command_id": command_id,
            "operation_id": result.get("operation_id") or command_id,
            "app_id": app_id,
            "status": status,
            "evidence_refs": result.get("evidence_refs") or [],
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.lite.catalog.install_completed" if status == "succeeded" else "pocketlab.audit.lite.catalog.install_failed",
        event_type,
        {"command_id": command_id, "app_id": app_id, "status": status},
        trace_id=command_id,
    )
    return result


async def handle_lite_backup_create(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    await _publish(
        "pocketlab.events.lite.backup.started",
        "lite.backup.started",
        {"command_id": command_id, "engine": "restic"},
        trace_id=command_id,
    )
    from . import lite_backup

    try:
        result = await asyncio.to_thread(lite_backup.create_backup, command)
    except Exception as exc:
        await _publish(
            "pocketlab.events.lite.backup.failed",
            "lite.backup.failed",
            {"command_id": command_id, "error": str(exc)},
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.audit.lite.backup.failed",
            "lite.backup.failed",
            {"command_id": command_id, "status": "failed"},
            trace_id=command_id,
        )
        raise
    await _publish(
        "pocketlab.events.lite.backup.snapshot_created",
        "lite.backup.snapshot_created",
        {
            "command_id": command_id,
            "backup_id": result.get("backup_id"),
            "snapshot_id": result.get("snapshot_id"),
            "manifest_checksum": (result.get("manifest") or {}).get("manifest_checksum"),
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.lite.backup.created",
        "lite.backup.created",
        {
            "command_id": command_id,
            "backup_id": result.get("backup_id"),
            "snapshot_id": result.get("snapshot_id"),
            "evidence_saved": True,
        },
        trace_id=command_id,
    )
    return result


async def handle_lite_backup_verify(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    backup_id = str(command.get("backup_id") or "latest")
    await _publish(
        "pocketlab.events.lite.backup.verify_started",
        "lite.backup.verify_started",
        {"command_id": command_id, "backup_id": backup_id},
        trace_id=command_id,
    )
    from . import lite_backup

    try:
        result = await asyncio.to_thread(
            lite_backup.verify_backup,
            backup_id,
            reason=str(command.get("reason") or "manual verification"),
        )
    except Exception as exc:
        await _publish(
            "pocketlab.events.lite.backup.verify_failed",
            "lite.backup.verify_failed",
            {"command_id": command_id, "backup_id": backup_id, "error": str(exc)},
            trace_id=command_id,
        )
        raise
    await _publish(
        "pocketlab.events.lite.backup.verified",
        "lite.backup.verified",
        {
            "command_id": command_id,
            "backup_id": result.get("backup_id"),
            "status": result.get("status"),
            "manifest_checksum": result.get("manifest_checksum"),
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.lite.backup.verified",
        "lite.backup.verified",
        {"command_id": command_id, "backup_id": result.get("backup_id"), "status": result.get("status")},
        trace_id=command_id,
    )
    return result


async def handle_lite_restore_preview(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    backup_id = str(command.get("backup_id") or "latest")
    await _publish(
        "pocketlab.events.lite.restore.preview_started",
        "lite.restore.preview_started",
        {"command_id": command_id, "backup_id": backup_id},
        trace_id=command_id,
    )
    from . import lite_backup

    try:
        result = await asyncio.to_thread(
            lite_backup.create_restore_preview,
            backup_id,
            reason=str(command.get("reason") or "manual restore preview"),
        )
    except Exception as exc:
        await _publish(
            "pocketlab.events.lite.restore.preview_failed",
            "lite.restore.preview_failed",
            {"command_id": command_id, "backup_id": backup_id, "error": str(exc)},
            trace_id=command_id,
        )
        raise
    await _publish(
        "pocketlab.events.lite.restore.preview_created",
        "lite.restore.preview_created",
        {
            "command_id": command_id,
            "backup_id": result.get("backup_id"),
            "preview_id": result.get("preview_id"),
            "change_count": result.get("change_count"),
            "restore_allowed": result.get("restore_allowed"),
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.lite.restore.preview_created",
        "lite.restore.preview_created",
        {"command_id": command_id, "backup_id": result.get("backup_id"), "preview_id": result.get("preview_id")},
        trace_id=command_id,
    )
    return result


async def handle_lite_restore_apply(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    backup_id = str(command.get("backup_id") or "latest")
    preview_id = str(command.get("preview_id") or "")
    await _publish(
        "pocketlab.events.lite.restore.started",
        "lite.restore.started",
        {"command_id": command_id, "backup_id": backup_id, "preview_id": preview_id},
        trace_id=command_id,
    )
    from . import lite_backup

    try:
        result = await asyncio.to_thread(lite_backup.apply_restore, command)
    except Exception as exc:
        await _publish(
            "pocketlab.events.lite.restore.failed",
            "lite.restore.failed",
            {"command_id": command_id, "backup_id": backup_id, "preview_id": preview_id, "error": str(exc)},
            trace_id=command_id,
        )
        await _publish(
            "pocketlab.audit.lite.restore.failed",
            "lite.restore.failed",
            {"command_id": command_id, "backup_id": backup_id, "preview_id": preview_id, "status": "failed"},
            trace_id=command_id,
        )
        raise
    checkpoint_id = result.get("checkpoint_id")
    await _publish(
        "pocketlab.events.lite.restore.checkpoint_created",
        "lite.restore.checkpoint_created",
        {
            "command_id": command_id,
            "restore_id": result.get("restore_id"),
            "backup_id": result.get("backup_id"),
            "preview_id": result.get("preview_id"),
            "checkpoint_id": checkpoint_id,
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.events.lite.restore.service_restart_checked",
        "lite.restore.service_restart_checked",
        {
            "command_id": command_id,
            "restore_id": result.get("restore_id"),
            "backup_id": result.get("backup_id"),
            "service_restart": result.get("service_restart"),
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.events.lite.restore.health_validated",
        "lite.restore.health_validated",
        {
            "command_id": command_id,
            "restore_id": result.get("restore_id"),
            "backup_id": result.get("backup_id"),
            "health_validation": result.get("health_validation"),
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.events.lite.restore.completed",
        "lite.restore.completed",
        {
            "command_id": command_id,
            "restore_id": result.get("restore_id"),
            "backup_id": result.get("backup_id"),
            "preview_id": result.get("preview_id"),
            "checkpoint_id": checkpoint_id,
            "restored_file_count": result.get("restored_file_count"),
            "status": result.get("status"),
        },
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.lite.restore.completed",
        "lite.restore.completed",
        {
            "command_id": command_id,
            "restore_id": result.get("restore_id"),
            "backup_id": result.get("backup_id"),
            "preview_id": result.get("preview_id"),
            "checkpoint_id": checkpoint_id,
            "restored_file_count": result.get("restored_file_count"),
            "status": result.get("status"),
        },
        trace_id=command_id,
    )
    return result


async def handle_lite_security_scan(command: Dict[str, Any]) -> Dict[str, Any]:
    command_id = _command_id(command)
    run_id = str(command.get("run_id") or command_id)
    await _publish(
        "pocketlab.events.lite.security.scan.started",
        "lite.security.scan.started",
        {"command_id": command_id, "run_id": run_id},
        trace_id=command_id,
    )
    from . import lite_security

    try:
        result = await asyncio.to_thread(lite_security.run_security_scan, command)
    except Exception as exc:
        await _publish(
            "pocketlab.audit.lite.security.scan.failed",
            "lite.security.scan.failed",
            {"command_id": command_id, "run_id": run_id, "status": "failed", "error": str(exc)},
            trace_id=command_id,
        )
        raise

    run = result.get("run") or {}
    state = result.get("state") or {}
    tool_results = run.get("tool_results") or {}
    for tool, payload in tool_results.items():
        status = str((payload or {}).get("status") or "unknown")
        if status == "missing_tool":
            await _publish(
                "pocketlab.events.lite.security.tool_missing",
                "lite.security.tool_missing",
                {"command_id": command_id, "run_id": run_id, "tool": tool},
                trace_id=command_id,
            )
        else:
            await _publish(
                f"pocketlab.events.lite.security.{tool}.completed",
                f"lite.security.{tool}.completed",
                {
                    "command_id": command_id,
                    "run_id": run_id,
                    "tool": tool,
                    "status": status,
                    "finding_count": (payload or {}).get("finding_count", 0),
                },
                trace_id=command_id,
            )

    critical = state.get("critical_issues") or []
    for finding in critical[:10]:
        await _publish(
            "pocketlab.events.lite.security.critical_found",
            "lite.security.critical_found",
            {
                "command_id": command_id,
                "run_id": run_id,
                "finding_id": finding.get("id"),
                "category": finding.get("category"),
                "component": finding.get("component"),
            },
            trace_id=command_id,
        )

    completed_payload = {
        "command_id": command_id,
        "run_id": run_id,
        "status": run.get("status"),
        "score": state.get("score"),
        "critical_count": (state.get("last_run") or {}).get("critical_count", 0),
        "high_count": (state.get("last_run") or {}).get("high_count", 0),
        "medium_count": (state.get("last_run") or {}).get("medium_count", 0),
        "low_count": (state.get("last_run") or {}).get("low_count", 0),
        "partial_results": run.get("partial_results", False),
        "evidence_saved": True,
    }
    await _publish(
        "pocketlab.events.lite.security.scan.completed",
        "lite.security.scan.completed",
        completed_payload,
        trace_id=command_id,
    )
    await _publish(
        "pocketlab.audit.lite.security.scan.completed",
        "lite.security.scan.completed",
        completed_payload,
        trace_id=command_id,
    )
    return {
        "status": run.get("status") or "succeeded",
        "command_id": command_id,
        "run_id": run_id,
        "score": state.get("score"),
        "summary": state.get("summary"),
        "evidence_refs": result.get("evidence_refs") or [],
        "state": state,
    }


HANDLERS = {
    "pocketlab.commands.lite.catalog.install": handle_lite_catalog_install,
    "pocketlab.commands.catalog.refresh": handle_catalog_refresh,
    "pocketlab.commands.drift.scan": handle_drift_scan,
    "pocketlab.commands.drift.rescan": handle_drift_scan,
    "pocketlab.commands.drift.preview": handle_drift_preview,
    "pocketlab.commands.drift.approve": lambda command: handle_drift_mutation(
        "approve", command
    ),
    "pocketlab.commands.drift.apply": lambda command: handle_drift_mutation(
        "apply", command
    ),
    "pocketlab.commands.drift.ignore": lambda command: handle_drift_mutation(
        "ignore", command
    ),
    "pocketlab.commands.fleet.join": handle_fleet_join,
    "pocketlab.commands.fleet.save_tailscale_key": handle_fleet_save_tailscale_key,
    "pocketlab.commands.release.check": handle_release_check,
    "pocketlab.commands.release.apply": handle_release_apply,
    "pocketlab.commands.health.check": handle_health_check,
    "pocketlab.commands.security.scan": handle_security_scan,
    "pocketlab.commands.lite.security.scan": handle_lite_security_scan,
    "pocketlab.commands.security.configure_opa": handle_security_configure_opa,
    "pocketlab.commands.vault.rotate": handle_vault_rotate,
    "pocketlab.commands.vault.dynamic_secret": handle_vault_dynamic_secret,
    "pocketlab.commands.lite.backup.create": handle_lite_backup_create,
    "pocketlab.commands.lite.backup.verify": handle_lite_backup_verify,
    "pocketlab.commands.lite.restore.preview": handle_lite_restore_preview,
    "pocketlab.commands.lite.restore.apply": handle_lite_restore_apply,
}


def supported_subjects() -> list[str]:
    return sorted(HANDLERS.keys())


async def execute_domain_command(
    subject: str, command: Dict[str, Any]
) -> Dict[str, Any]:
    handler = HANDLERS.get(subject)
    if handler is None:
        raise KeyError(f"No domain handler for command subject: {subject}")
    result = await handler(command)
    if not isinstance(result, dict):
        result = {"result": result}
    result.setdefault("command_subject", subject)
    return result
