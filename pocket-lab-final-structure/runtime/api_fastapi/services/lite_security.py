from __future__ import annotations

import base64
import copy
import hashlib
import json
import logging
import sqlite3
import threading
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import deps
from . import lite_security_evidence as evidence
from . import lite_security_policy as policy


_LOGGER = logging.getLogger(__name__)
_SQLITE_PROGRESS_SNAPSHOT_LOCK = threading.Lock()
_SQLITE_PROGRESS_SNAPSHOT: dict[str, Any] | None = None
_SQLITE_PROGRESS_SNAPSHOT_DB = ""
_SQLITE_PROGRESS_FAILURES = 0
_SQLITE_PROGRESS_REFRESH_LOCK = threading.Lock()
_SQLITE_PROGRESS_REFRESH_INFLIGHT = False
_SQLITE_PROGRESS_REFRESHED_AT = 0.0
_SQLITE_PROGRESS_REFRESH_INTERVAL_SECONDS = 0.20


def _security_store_api():
    from . import lite_security_store

    return lite_security_store


def _security_repository():
    return _security_store_api().SecuritySQLiteRepository(initialize=True)


def initialize_security_sqlite_runtime(*, reconcile: bool = True) -> dict[str, Any]:
    """Validate rollout settings and initialize SQLite only when configured."""
    store = _security_store_api()
    mode = store.security_store_mode()
    compact_reads = store.sqlite_compact_reads_enabled()
    shadow_read = store.sqlite_shadow_read_enabled()
    result: dict[str, Any] = {
        "mode": mode,
        "compact_reads": compact_reads,
        "shadow_read": shadow_read,
        "reconciled": [],
    }
    if mode in {"dual", "sqlite"} or shadow_read:
        repository = store.SecuritySQLiteRepository(initialize=True)
        if reconcile and mode in {"dual", "sqlite"}:
            reconciled = repository.reconcile_stale_runs()
            result["reconciled"] = reconciled
            if reconciled:
                _project_reconciled_sqlite_runs(repository, reconciled)
        if compact_reads:
            try:
                _refresh_sqlite_progress_snapshot(repository=repository)
                result["progress_snapshot_primed"] = True
            except Exception as exc:
                result["progress_snapshot_primed"] = False
                result["progress_snapshot_error"] = type(exc).__name__
    return policy.redact_value(result)


def _project_reconciled_sqlite_runs(
    repository: Any, reconciled: list[dict[str, Any]]
) -> None:
    """Project conservative startup recovery results after DB commits."""
    for item in reconciled:
        run_id = str(item.get("run_id") or "")
        if not run_id:
            continue
        row = repository.get_run(run_id) or {}
        refs = [
            str(ref.get("relative_path") or "")
            for ref in repository.list_evidence_refs(run_id, limit=100)
            if ref.get("relative_path")
        ]
        try:
            recovery_ref = evidence.write_evidence(
                run_id,
                "startup-recovery.json",
                {
                    "run_id": run_id,
                    "status": "interrupted",
                    "summary": "A stale safety check was released during startup recovery.",
                    "profile": row.get("profile") or policy.SCAN_PROFILE_QUICK,
                    "recovered_at": deps.now_utc_iso(),
                    "sanitized": True,
                },
            )
            if recovery_ref not in refs:
                refs.append(recovery_ref)
        except (OSError, ValueError, TypeError) as exc:
            _LOGGER.warning(
                "Security startup recovery evidence degraded: %s",
                type(exc).__name__,
            )
        tool_results = {
            str(tool.get("tool_name") or "tool"): {
                "status": tool.get("status") or "unknown",
                "finding_count": int(tool.get("finding_count") or 0),
                **(tool.get("metadata") if isinstance(tool.get("metadata"), dict) else {}),
            }
            for tool in repository.list_tool_runs(run_id, limit=100)
        }
        repository.fail_run(
            run_id,
            failure_code="interrupted",
            failure_message=str(
                row.get("failure_message")
                or "The previous safety check was interrupted and can be started again."
            ),
            summary=str(
                row.get("summary")
                or "The previous safety check was interrupted and can be started again."
            ),
            completed_at=row.get("completed_at") or deps.now_utc_iso(),
            partial_results=bool(row.get("partial_results")),
            findings=repository.list_findings(run_id, limit=500),
            evidence_refs=refs,
            tool_results=tool_results,
            metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        )
        projected = _sqlite_run_payload(
            repository, repository.get_run(run_id), include_details=True, include_related=True
        )
        if projected:
            _write_run_projection(projected)
    _, state, _ = _sqlite_state_projection()
    _write_security_state(state)


def _sqlite_lifecycle_enabled() -> bool:
    return _security_store_api().sqlite_lifecycle_writes_enabled()


def _sqlite_compact_reads_enabled() -> bool:
    return _security_store_api().sqlite_compact_reads_enabled()


def _record_projection_status(
    run_id: str | None,
    *,
    component: str,
    degraded: bool,
    reason: str = "",
) -> None:
    if not run_id or not _sqlite_lifecycle_enabled():
        return
    try:
        _security_repository().record_projection_status(
            run_id, component=component, degraded=degraded, reason=reason
        )
    except Exception as exc:
        _LOGGER.warning(
            "Security JSON compatibility status could not be recorded: %s",
            type(exc).__name__,
        )


def _write_run_projection(run: dict[str, Any]) -> dict[str, Any]:
    run_id = str(run.get("run_id") or "")
    try:
        clean = evidence.write_run(run_id, run)
        _record_projection_status(run_id, component="run", degraded=False)
        return clean
    except (OSError, ValueError, TypeError) as exc:
        if not _sqlite_lifecycle_enabled():
            raise
        _record_projection_status(
            run_id,
            component="run",
            degraded=True,
            reason=f"run_projection_{type(exc).__name__}",
        )
        _LOGGER.warning(
            "Security run JSON compatibility projection degraded: %s",
            type(exc).__name__,
        )
        return policy.redact_value(run)


def _dedupe_response_from_reservation(result: Any) -> dict[str, Any]:
    run = result.run if isinstance(getattr(result, "run", None), dict) else {}
    profile = str(run.get("profile") or policy.SCAN_PROFILE_QUICK)
    app_id = str(run.get("app_id") or "")
    if result.reason == "active":
        return policy.redact_value({
            "status": run.get("status") or "running",
            "state": run.get("status") or "running",
            "accepted": True,
            "duplicate": True,
            "deduplicated": True,
            "existing": True,
            "already_running": True,
            "run_id": run.get("run_id") or "",
            "command_id": run.get("command_id") or run.get("run_id") or "",
            "scan_profile": profile,
            "profile": profile,
            **({"app_id": app_id, "app_label": run.get("app_label") or _app_label(app_id)} if app_id else {}),
            "summary": "A safety check is already running.",
        })
    completed_at = _parse_iso_timestamp(run.get("completed_at"))
    elapsed = max(
        0,
        int((datetime.now(timezone.utc) - completed_at).total_seconds()),
    ) if completed_at else 0
    window = _security_store_api().security_recent_completion_seconds()
    return policy.redact_value({
        "status": run.get("status") or "succeeded",
        "state": run.get("status") or "succeeded",
        "accepted": True,
        "duplicate": True,
        "deduplicated": True,
        "recent_duplicate": True,
        "already_completed": True,
        "run_id": run.get("run_id") or "",
        "command_id": run.get("command_id") or run.get("run_id") or "",
        "scan_profile": profile,
        "profile": profile,
        **({"app_id": app_id, "app_label": run.get("app_label") or _app_label(app_id)} if app_id else {}),
        "retry_after_seconds": max(0, window - elapsed),
        "summary": "A safety check just finished. Showing the latest saved result instead of starting another one.",
    })


def reserve_scan_request(command: dict[str, Any]) -> dict[str, Any]:
    """Reserve one backend-owned scan before NATS publication."""
    profile = _scan_profile(command)
    app_id = _scan_app_id(command)
    if not _sqlite_lifecycle_enabled():
        active = active_scan_state(profile, app_id)
        if active:
            return {"reserved": False, "response": active}
        recent = recent_completed_scan_state(profile, app_id)
        if recent:
            return {"reserved": False, "response": recent}
        run = record_queued_run(command)
        return {"reserved": True, "run": run, "response": None}

    repository = _security_repository()
    result = repository.reserve_scan(
        run_id=str(command.get("run_id") or command.get("command_id") or new_run_id()),
        profile=profile,
        app_id=app_id,
        app_label=_app_label(app_id),
        summary=_profile_copy(profile)["queued"],
        requested_at=command.get("requested_at"),
        command_id=str(command.get("command_id") or "") or None,
        correlation_id=str(command.get("correlation_id") or "") or None,
        recent_completion_seconds=_security_store_api().security_recent_completion_seconds(),
    )
    if not result.reserved:
        return {"reserved": False, "response": _dedupe_response_from_reservation(result)}
    return {"reserved": True, "run": result.run, "response": None}


def mark_scan_accepted(command: dict[str, Any]) -> dict[str, Any] | None:
    run_id = str(command.get("run_id") or command.get("command_id") or "")
    if not run_id:
        return None
    if not _sqlite_lifecycle_enabled():
        return evidence.read_run(run_id)
    run = evidence.read_run(run_id) or {}
    if not run:
        return None
    run.update({
        "status": "accepted",
        "accepted_at": deps.now_utc_iso(),
        "updated_at": deps.now_utc_iso(),
    })
    state = build_state(
        run, [], [], status_override="queued", summary_override=run.get("summary")
    )
    _write_security_state(state)
    _write_run_projection(run)
    return run


def fail_scan_submission(run_id: str) -> None:
    if not _sqlite_lifecycle_enabled():
        discard_queued_run(run_id)
        return
    stored = _security_repository().get_run(run_id) or {}
    run = evidence.read_run(run_id) or {
        "run_id": run_id,
        "command_id": stored.get("command_id") or run_id,
        "scan_profile": stored.get("profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": stored.get("app_id") or "",
        "app_label": stored.get("app_label") or "",
        "requested_at": stored.get("requested_at"),
        "started_at": stored.get("started_at"),
        "tool_results": {},
        "execution_timeline": [],
    }
    run.update({
        "status": "failed",
        "summary": "The safety check could not be sent. Try again.",
        "completed_at": deps.now_utc_iso(),
        "failure_code": "submit_failed",
        "failure_message": "The backend worker queue was unavailable.",
    })
    state = build_state(
        run, [], [], status_override="degraded", summary_override=run["summary"]
    )
    _write_security_state(state)
    _write_run_projection(run)


def fail_security_run(run_id: str, exc: Exception | None = None) -> None:
    stored: dict[str, Any] = {}
    if _sqlite_lifecycle_enabled():
        stored = _security_repository().get_run(run_id) or {}
    existing_state = evidence.read_state() or {}
    existing_last_run = (
        existing_state.get("last_run")
        if isinstance(existing_state.get("last_run"), dict)
        else {}
    )
    run = evidence.read_run(run_id) or {
        "run_id": run_id,
        "command_id": stored.get("command_id") or run_id,
        "scan_profile": stored.get("profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": stored.get("app_id") or "",
        "app_label": stored.get("app_label") or "",
        "requested_at": stored.get("requested_at"),
        "started_at": stored.get("started_at"),
        "tool_results": {},
        "execution_timeline": [],
    }
    if existing_last_run.get("run_id") == run_id:
        run.setdefault("tool_results", existing_last_run.get("tool_results") or {})
        run.setdefault("evidence_refs", existing_last_run.get("evidence_refs") or [])
    run.update({
        "status": "failed",
        "summary": "Security check needs review.",
        "completed_at": deps.now_utc_iso(),
        "failure_code": "worker_failed",
        "failure_message": f"Worker failure: {type(exc).__name__}" if exc else "Worker failure.",
    })
    findings = (
        existing_state.get("findings")
        if existing_last_run.get("run_id") == run_id
        and isinstance(existing_state.get("findings"), list)
        else []
    )
    state = build_state(
        run, findings, run.get("evidence_refs") or [],
        status_override="degraded", summary_override=run["summary"],
    )
    _write_security_state(state)
    _write_run_projection(run)


def _shadow_compare_sqlite_state(state: dict[str, Any]) -> None:
    """Run the opt-in S2 comparison without changing JSON-backed responses."""
    shadow_flag = os.environ.get(
        "POCKETLAB_LITE_SECURITY_SQLITE_SHADOW_READ", "0"
    ).strip().lower()
    if shadow_flag in {"", "0", "false", "no", "off"}:
        return
    try:
        from .lite_security_store import shadow_compare_if_enabled

        result = shadow_compare_if_enabled(state)
        if result and not result.get("matched"):
            _LOGGER.warning(
                "Security SQLite shadow comparison mismatch: fields=%s",
                ",".join(result.get("mismatch_fields") or []),
            )
    except Exception as exc:
        # Shadow mode is diagnostic in S2. JSON remains authoritative and a
        # SQLite failure must never blank the Safety Center.
        _LOGGER.warning(
            "Security SQLite shadow comparison skipped: %s", type(exc).__name__
        )


def new_run_id() -> str:
    stamp = deps.now_utc_iso().replace(":", "").replace("+", "Z").replace(".", "-")
    return f"security-{stamp}-{uuid.uuid4().hex[:8]}"


def default_coverage_summary(root: Path | None = None, profile: str | None = None, app_id: str | None = None) -> dict[str, Any]:
    scan_profile = policy.normalize_scan_profile(profile or policy.SCAN_PROFILE_QUICK)
    plan = policy.build_scan_plan(scan_profile, root or policy.repo_root(), app_id=app_id)
    return policy.redact_value({
        "profile": scan_profile,
        **({"app_id": plan.get("app_id"), "app_label": plan.get("app_label")} if plan.get("app_id") else {}),
        "checked_targets": plan.get("checked_targets", []),
        "skipped_targets": plan.get("skipped_targets", []),
        "excluded_groups": plan.get("excluded_groups", []),
        "partial_targets": [],
        "timed_out_targets": [],
        "tool_status": {},
        "source_targets": [
            {key: item.get(key) for key in ("label", "relative", "present", "kind")}
            for item in plan.get("source_targets", [])
        ],
    })


def _scan_profile(command: dict[str, Any] | None = None) -> str:
    try:
        return policy.normalize_scan_profile((command or {}).get("profile"))
    except ValueError:
        return policy.SCAN_PROFILE_QUICK


def _scan_app_id(command: dict[str, Any] | None = None) -> str | None:
    profile = _scan_profile(command)
    if profile != policy.SCAN_PROFILE_APP:
        return None
    try:
        return policy.normalize_app_id((command or {}).get("app_id"))
    except ValueError:
        return None


def _app_label(app_id: str | None = None) -> str | None:
    if not app_id:
        return None
    try:
        return str(policy.app_check_target(app_id).get("app_label") or app_id)
    except ValueError:
        return None


def _profile_copy(profile: str) -> dict[str, str]:
    if profile == policy.SCAN_PROFILE_APP:
        return {
            "name": "App Check",
            "queued": "App Check queued. Pocket Lab will check PhotoPrism while skipping photos, media, backups, logs, and large caches.",
            "running": "App Check running.",
            "complete": "App Check completed.",
            "partial": "App Check completed with partial results.",
            "progress": "Pocket Lab is checking PhotoPrism route, app files, settings, backup metadata, and action state in the backend worker.",
        }
    if profile == policy.SCAN_PROFILE_FULL:
        return {
            "name": "Full Local Check",
            "queued": "Full Local Check queued. Pocket Lab will check this device more deeply while still skipping photos, backups, logs, and large caches.",
            "running": "Full Local Check running.",
            "complete": "Full Local Check completed.",
            "partial": "Full Local Check completed with partial results.",
            "progress": "Pocket Lab is checking Termux, Pocket Lab files, selected PROot Ubuntu areas, PhotoPrism app/config, and backup metadata in the backend worker.",
        }
    return {
        "name": "Quick Safety Check",
        "queued": "Quick safety check queued. Pocket Lab will check basics and skip photos, backups, and large caches.",
        "running": "Quick safety check running.",
        "complete": "Safety check completed.",
        "partial": "Safety check timed out before all checks completed.",
        "progress": "Pocket Lab is checking basics and skipping photos, backups, and large caches in the backend worker.",
    }


def _coverage_from_run(run: dict[str, Any] | None = None) -> dict[str, Any]:
    coverage = (run or {}).get("coverage_summary")
    profile = str((run or {}).get("scan_profile") or policy.SCAN_PROFILE_QUICK)
    return coverage if isinstance(coverage, dict) else default_coverage_summary(profile=profile)


_SECURITY_READ_CACHE_SECONDS = max(1.0, float(os.environ.get("POCKETLAB_LITE_SECURITY_READ_CACHE_SECONDS", "30")))
_SECURITY_READ_CACHE_LIVE_SECONDS = max(0.5, float(os.environ.get("POCKETLAB_LITE_SECURITY_READ_CACHE_LIVE_SECONDS", "2")))
_SECURITY_BACKFILL_PERSIST_SECONDS = max(0.0, float(os.environ.get("POCKETLAB_LITE_SECURITY_BACKFILL_PERSIST_SECONDS", "0.25")))
_CURRENT_STATE_CACHE: dict[str, Any] = {"key": None, "cached_at": 0.0, "data": None, "live": False}
_SECURITY_SUMMARY_CACHE: dict[str, Any] = {"key": None, "cached_at": 0.0, "data": None, "live": False}
_SECURITY_SUMMARY_HISTORY_LIMIT = max(1, int(os.environ.get("POCKETLAB_LITE_SECURITY_SUMMARY_HISTORY_LIMIT", "6")))
_SECURITY_SUMMARY_FINDING_LIMIT = max(0, int(os.environ.get("POCKETLAB_LITE_SECURITY_SUMMARY_FINDING_LIMIT", "3")))
_SECURITY_SPLIT_HISTORY_DEFAULT_LIMIT = max(1, int(os.environ.get("POCKETLAB_LITE_SECURITY_HISTORY_DEFAULT_LIMIT", "20")))
_SECURITY_SPLIT_HISTORY_MAX_LIMIT = max(_SECURITY_SPLIT_HISTORY_DEFAULT_LIMIT, min(100, int(os.environ.get("POCKETLAB_LITE_SECURITY_HISTORY_MAX_LIMIT", "100"))))
_SECURITY_SPLIT_FINDING_LIMIT = max(1, int(os.environ.get("POCKETLAB_LITE_SECURITY_DETAILS_FINDING_LIMIT", "50")))
_SECURITY_SPLIT_PREVIEW_LIMIT = max(1, int(os.environ.get("POCKETLAB_LITE_SECURITY_PROFILE_PREVIEW_LIMIT", "6")))
_SECURITY_RECENT_COMPLETION_DEDUPE_SECONDS = max(5.0, float(os.environ.get("POCKETLAB_LITE_SECURITY_RECENT_COMPLETION_DEDUPE_SECONDS", "45")))
_SECURITY_SPLIT_READ_CACHE: dict[str, dict[str, Any]] = {}
_SECURITY_SPLIT_TTLS = {
    "freshness": (2.0, 1.0),
    "summary": (_SECURITY_READ_CACHE_SECONDS, _SECURITY_READ_CACHE_LIVE_SECONDS),
    "profile": (30.0, 2.0),
    "history": (60.0, 2.0),
    "progress": (3.0, 1.0),
    "details": (60.0, 2.0),
    "evidence_summary": (60.0, 2.0),
}


def _state_file_key() -> tuple[int, int] | None:
    try:
        stat_result = evidence.state_path().stat()
    except OSError:
        return None
    return (int(stat_result.st_mtime_ns), int(stat_result.st_size))


def _is_live_security_state(state: dict[str, Any] | None = None) -> bool:
    payload = state if isinstance(state, dict) else {}
    status = str(payload.get("status") or "").lower()
    progress = payload.get("scan_progress") if isinstance(payload.get("scan_progress"), dict) else {}
    progress_status = str(progress.get("status") or progress.get("phase") or "").lower()
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else {}
    run_status = str(last_run.get("status") or "").lower()
    live_values = {"queued", "running", "working", "in_progress", "accepted", "lynis_running", "trivy_running", "posture_running", "evidence_saving"}
    return status in live_values or progress_status in live_values or run_status in live_values


def _cache_ttl_for_state(state: dict[str, Any] | None = None) -> float:
    return _SECURITY_READ_CACHE_LIVE_SECONDS if _is_live_security_state(state) else _SECURITY_READ_CACHE_SECONDS


def _get_current_state_cache(key: tuple[int, int] | None) -> dict[str, Any] | None:
    if not key or _CURRENT_STATE_CACHE.get("key") != key:
        return None
    cached = _CURRENT_STATE_CACHE.get("data")
    if not isinstance(cached, dict):
        return None
    cached_at = float(_CURRENT_STATE_CACHE.get("cached_at") or 0.0)
    if (time.monotonic() - cached_at) > _cache_ttl_for_state(cached):
        return None
    return copy.deepcopy(cached)


def _set_current_state_cache(key: tuple[int, int] | None, state: dict[str, Any]) -> dict[str, Any]:
    clean = policy.redact_value(state)
    _shadow_compare_sqlite_state(clean)
    if key:
        _CURRENT_STATE_CACHE.update({
            "key": key,
            "cached_at": time.monotonic(),
            "data": copy.deepcopy(clean),
            "live": _is_live_security_state(clean),
        })
    return copy.deepcopy(clean)


def _trim_security_run_for_summary(run: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    trimmed = {
        key: run.get(key)
        for key in (
            "run_id", "status", "summary", "score", "scan_profile", "app_id", "app_label",
            "requested_at", "started_at", "completed_at", "updated_at", "checks_reviewed",
            "checks_count", "items_to_review", "critical_count", "high_count", "medium_count",
            "low_count", "info_count", "sbom_saved", "partial_results",
        )
        if key in run
    }
    if isinstance(run.get("tools"), list):
        trimmed["tools"] = run["tools"][:6]
    if isinstance(run.get("coverage_summary"), dict):
        coverage = run["coverage_summary"]
        trimmed["coverage_summary"] = {
            key: coverage.get(key)
            for key in (
                "profile", "app_id", "app_label", "tool_status", "checked_count", "skipped_count",
                "partial_count", "timed_out_count", "missing_count",
            )
            if key in coverage
        }
        for list_key in ("checked_targets", "skipped_targets", "partial_targets", "timed_out_targets", "missing_targets"):
            if isinstance(coverage.get(list_key), list):
                trimmed["coverage_summary"][list_key] = coverage[list_key][:4]
    if isinstance(run.get("execution_timeline"), list):
        trimmed["execution_timeline"] = run["execution_timeline"][:6]
    if isinstance(run.get("evidence_refs"), list):
        trimmed["evidence_refs"] = [str(ref) for ref in run["evidence_refs"][:5]]
    if isinstance(run.get("tool_results"), dict):
        trimmed["tool_results"] = {
            key: {
                subkey: value.get(subkey)
                for subkey in ("status", "available", "label", "finding_count", "timed_out", "sbom_saved")
                if subkey in value
            }
            for key, value in run["tool_results"].items()
            if isinstance(value, dict)
        }
    return policy.redact_value(trimmed)


def _trim_security_delta_for_summary(delta: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(delta, dict):
        return {"new_count": 0, "resolved_count": 0, "unchanged_count": 0, "new": [], "resolved": [], "unchanged": []}
    trimmed = {
        "new_count": int(delta.get("new_count") or 0),
        "resolved_count": int(delta.get("resolved_count") or 0),
        "unchanged_count": int(delta.get("unchanged_count") or 0),
    }
    for key in ("new", "resolved", "unchanged"):
        values = delta.get(key) if isinstance(delta.get(key), list) else []
        trimmed[key] = values[:_SECURITY_SUMMARY_FINDING_LIMIT]
    return policy.redact_value(trimmed)


def _profile_latest_summary(state: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    profile_latest = state.get("profile_latest") if isinstance(state.get("profile_latest"), dict) else {}
    latest: dict[str, Any] = {}
    for profile in (policy.SCAN_PROFILE_QUICK, policy.SCAN_PROFILE_FULL, policy.SCAN_PROFILE_APP):
        candidate = profile_latest.get(profile) if isinstance(profile_latest.get(profile), dict) else None
        if candidate is None:
            candidate = next((run for run in history if policy.normalize_scan_profile(run.get("scan_profile") or ("app" if run.get("app_id") else "quick")) == profile), None)
        if candidate is not None:
            latest[profile] = _trim_security_run_for_summary(candidate)
    return {key: value for key, value in latest.items() if value}


def _security_summary_from_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = state if isinstance(state, dict) else {}
    last_run = _trim_security_run_for_summary(payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None)
    raw_history = payload.get("history") if isinstance(payload.get("history"), list) else []
    history = [item for item in (_trim_security_run_for_summary(run) for run in raw_history[:_SECURITY_SUMMARY_HISTORY_LIMIT]) if item]
    if not history and last_run:
        history = [last_run]
    profile_latest = _profile_latest_summary(payload, history)
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    critical = payload.get("critical_issues") if isinstance(payload.get("critical_issues"), list) else []
    evidence_refs = payload.get("evidence_refs") if isinstance(payload.get("evidence_refs"), list) else []
    summary = {
        "view_model": "security-summary-f3-v1",
        "status": payload.get("status") or (last_run or {}).get("status") or "unknown",
        "summary": payload.get("summary") or (last_run or {}).get("summary") or "Security summary is available.",
        "score": int(payload.get("score") or (last_run or {}).get("score") or 0),
        "checks_reviewed": int(payload.get("checks_reviewed") or payload.get("checks_count") or (last_run or {}).get("checks_reviewed") or 0),
        "checks_count": int(payload.get("checks_count") or payload.get("checks_reviewed") or (last_run or {}).get("checks_count") or 0),
        "items_to_review": int(payload.get("items_to_review") or len(findings) or 0),
        "findings_count": int(payload.get("findings_count") or len(findings) or 0),
        "evidence_count": len(evidence_refs),
        "scan_profile": payload.get("scan_profile") or (last_run or {}).get("scan_profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": payload.get("app_id") or (last_run or {}).get("app_id") or "",
        "app_label": payload.get("app_label") or (last_run or {}).get("app_label") or "",
        "last_run": last_run,
        "history": history,
        "profile_latest": profile_latest,
        "finding_delta": _trim_security_delta_for_summary(payload.get("finding_delta")),
        "scan_progress": payload.get("scan_progress") if isinstance(payload.get("scan_progress"), dict) else None,
        "coverage_summary": (last_run or {}).get("coverage_summary") or {},
        "execution_timeline": (last_run or {}).get("execution_timeline") or [],
        "tool_results": (last_run or {}).get("tool_results") or {},
        "evidence_refs": [str(ref) for ref in evidence_refs[:5]],
        "critical_issues": critical[:_SECURITY_SUMMARY_FINDING_LIMIT],
        "findings": findings[:_SECURITY_SUMMARY_FINDING_LIMIT],
        "component_posture": payload.get("component_posture")[:6] if isinstance(payload.get("component_posture"), list) else [],
        "guidance": payload.get("guidance")[:4] if isinstance(payload.get("guidance"), list) else policy.GUIDANCE[:4],
        "updated_at": payload.get("updated_at") or (last_run or {}).get("updated_at") or (last_run or {}).get("completed_at"),
        "checked_at": payload.get("checked_at") or payload.get("updated_at") or (last_run or {}).get("completed_at"),
        "revision": _summary_revision(payload),
        "source": "security_summary_json",
        "summary_payload": True,
        "details_endpoint": "/api/lite/security",
        "sanitized": True,
    }
    return policy.redact_value(summary)


def _get_security_summary_cache(key: tuple[int, int] | None) -> dict[str, Any] | None:
    if not key or _SECURITY_SUMMARY_CACHE.get("key") != key:
        return None
    cached = _SECURITY_SUMMARY_CACHE.get("data")
    if not isinstance(cached, dict):
        return None
    cached_at = float(_SECURITY_SUMMARY_CACHE.get("cached_at") or 0.0)
    if (time.monotonic() - cached_at) > _cache_ttl_for_state(cached):
        return None
    return copy.deepcopy(cached)


def _set_security_summary_cache(key: tuple[int, int] | None, state: dict[str, Any]) -> dict[str, Any]:
    clean = policy.redact_value(state)
    if key:
        _SECURITY_SUMMARY_CACHE.update({
            "key": key,
            "cached_at": time.monotonic(),
            "data": copy.deepcopy(clean),
            "live": _is_live_security_state(clean),
        })
    return copy.deepcopy(clean)



def invalidate_security_read_caches() -> None:
    _CURRENT_STATE_CACHE.update({"key": None, "cached_at": 0.0, "data": None, "live": False})
    _SECURITY_SUMMARY_CACHE.update({"key": None, "cached_at": 0.0, "data": None, "live": False})
    _SECURITY_SPLIT_READ_CACHE.clear()


def _bounded_list(value: Any, limit: int) -> list[Any]:
    return policy.redact_value(value[: max(0, limit)] if isinstance(value, list) else [])


def _profile_for_run(run: dict[str, Any] | None = None) -> str:
    payload = run if isinstance(run, dict) else {}
    try:
        return policy.normalize_scan_profile(payload.get("scan_profile") or (policy.SCAN_PROFILE_APP if payload.get("app_id") else policy.SCAN_PROFILE_QUICK))
    except ValueError:
        return policy.SCAN_PROFILE_QUICK


def _revision_token(kind: str, *signals: Any) -> str:
    safe_kind = "".join(ch if ch.isalnum() or ch in "-." else "-" for ch in str(kind or "state").lower()).strip("-") or "state"
    clean_signals = policy.redact_value(signals)
    encoded = json.dumps(clean_signals, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8", "replace")
    return f"security-{safe_kind}-{hashlib.sha256(encoded).hexdigest()[:18]}"


def _run_revision_signals(run: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = run if isinstance(run, dict) else {}
    return {
        key: payload.get(key)
        for key in (
            "run_id", "status", "scan_profile", "app_id", "score", "updated_at", "completed_at",
            "checks_reviewed", "checks_count", "items_to_review", "critical_count", "high_count",
            "medium_count", "low_count", "partial_results", "sbom_saved",
        )
        if key in payload
    }


def _progress_revision(state: dict[str, Any] | None = None) -> str:
    payload = state if isinstance(state, dict) else {}
    progress = payload.get("scan_progress") if isinstance(payload.get("scan_progress"), dict) else {}
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else {}
    return _revision_token(
        "progress",
        progress.get("run_id") or last_run.get("run_id"),
        progress.get("profile") or last_run.get("scan_profile") or payload.get("scan_profile"),
        progress.get("status") or progress.get("phase") or progress.get("stage"),
        progress.get("percent"),
        progress.get("updated_at") or payload.get("updated_at") or last_run.get("updated_at") or last_run.get("completed_at"),
        _is_live_security_state(payload),
    )


def _history_revision(state: dict[str, Any] | None = None) -> str:
    history = _compact_history_index(state if isinstance(state, dict) else {}, limit=_SECURITY_SPLIT_HISTORY_MAX_LIMIT)
    return _revision_token("history", [_run_revision_signals(item) for item in history])


def _profile_revision(profile: str, state: dict[str, Any] | None = None, latest: dict[str, Any] | None = None) -> str:
    payload = state if isinstance(state, dict) else {}
    normalized_profile = _profile_for_run({"scan_profile": profile})
    candidate = latest if isinstance(latest, dict) else None
    if candidate is None:
        profile_latest = payload.get("profile_latest") if isinstance(payload.get("profile_latest"), dict) else {}
        candidate = profile_latest.get(normalized_profile) if isinstance(profile_latest.get(normalized_profile), dict) else None
    if candidate is None:
        candidate = next((item for item in (payload.get("history") if isinstance(payload.get("history"), list) else []) if isinstance(item, dict) and _profile_for_run(item) == normalized_profile), None)
    return _revision_token("profile-" + normalized_profile, _run_revision_signals(candidate), _is_live_security_state(payload) and _profile_for_run(payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None) == normalized_profile)


def _summary_revision(state: dict[str, Any] | None = None) -> str:
    payload = state if isinstance(state, dict) else {}
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else {}
    return _revision_token(
        "summary",
        payload.get("status"), payload.get("score"), payload.get("updated_at"), payload.get("checked_at"),
        payload.get("checks_reviewed"), payload.get("items_to_review"),
        _run_revision_signals(last_run),
        _progress_revision(payload) if _is_live_security_state(payload) else "idle",
    )


def _compact_revision(state: dict[str, Any] | None = None, *, run_id: str | None = None) -> str:
    payload = state if isinstance(state, dict) else {}
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else {}
    return _revision_token("overall", payload.get("updated_at") or payload.get("checked_at"), _run_revision_signals(last_run), run_id or last_run.get("run_id"), _progress_revision(payload) if _is_live_security_state(payload) else "idle")


def compact_response_revision(payload: dict[str, Any] | None = None) -> str:
    data = payload if isinstance(payload, dict) else {}
    revision = str(data.get("revision") or "")
    if revision.startswith("security-"):
        return revision
    return _revision_token("response", data)


def compact_response_etag(payload: dict[str, Any] | None = None) -> str:
    revision = compact_response_revision(payload)
    safe = "".join(ch for ch in revision if ch.isalnum() or ch in "-._:") or _revision_token("etag", revision)
    return f'"{safe}"'


def if_none_match_matches(header_value: str | None, etag: str) -> bool:
    if not header_value:
        return False
    expected = str(etag or "").strip()
    if not expected:
        return False
    for candidate in str(header_value).split(","):
        value = candidate.strip()
        if value == "*":
            return True
        if value.startswith("W/"):
            value = value[2:].strip()
        if value == expected:
            return True
    return False


def _compact_file_key(path: Path, *parts: Any) -> tuple[Any, ...]:
    try:
        stat_result = path.stat()
        file_key: tuple[Any, ...] = (str(path), int(stat_result.st_mtime_ns), int(stat_result.st_size))
    except OSError:
        file_key = (str(path), "missing", 0)
    return (*file_key, *parts)


def _split_cache_ttl(kind: str, payload: dict[str, Any] | None = None) -> float:
    idle, active = _SECURITY_SPLIT_TTLS.get(kind, (_SECURITY_READ_CACHE_SECONDS, _SECURITY_READ_CACHE_LIVE_SECONDS))
    return active if _is_live_security_state(payload) else idle


def _cached_compact_read(kind: str, key: tuple[Any, ...], builder) -> dict[str, Any]:
    cache_key = f"{kind}:{repr(key)}"
    cached = _SECURITY_SPLIT_READ_CACHE.get(cache_key)
    now = time.monotonic()
    if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
        ttl = float(cached.get("ttl") or _split_cache_ttl(kind, cached.get("data")))
        if (now - float(cached.get("cached_at") or 0.0)) <= ttl:
            data = copy.deepcopy(cached["data"])
            data["read_cache"] = {"status": "hit", "source": f"fastapi_{kind}_memory", "ttl_seconds": int(ttl), "cache_key_signals": list(key[-4:])}
            return data
    data = policy.redact_value(builder())
    ttl = _split_cache_ttl(kind, data)
    _SECURITY_SPLIT_READ_CACHE[cache_key] = {"cached_at": now, "ttl": ttl, "data": copy.deepcopy(data)}
    data["read_cache"] = {"status": "miss", "source": f"compact_{kind}", "ttl_seconds": int(ttl), "cache_key_signals": list(key[-4:])}
    return data


def _compact_coverage(coverage: dict[str, Any] | None = None, *, limit: int = _SECURITY_SPLIT_PREVIEW_LIMIT) -> dict[str, Any]:
    payload = coverage if isinstance(coverage, dict) else {}
    compact = {
        key: payload.get(key)
        for key in (
            "profile", "app_id", "app_label", "checked_count", "skipped_count", "partial_count",
            "timed_out_count", "missing_count", "failed_count", "tool_status",
        )
        if key in payload
    }
    for key in ("checked_targets", "skipped_targets", "missing_targets", "partial_targets", "timed_out_targets", "failed_targets", "target_statuses"):
        if isinstance(payload.get(key), list):
            compact[key] = payload[key][:limit]
    return policy.redact_value(compact)


def _compact_tool_results(tool_results: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = tool_results if isinstance(tool_results, dict) else {}
    return policy.redact_value({
        key: {
            subkey: value.get(subkey)
            for subkey in ("status", "available", "label", "finding_count", "timed_out", "sbom_saved", "target_id")
            if isinstance(value, dict) and subkey in value
        }
        for key, value in payload.items()
        if isinstance(value, dict)
    })


def _compact_evidence_summary_from_refs(run_id: str | None, refs: list[Any] | None = None) -> dict[str, Any]:
    evidence_refs = [str(ref) for ref in (refs if isinstance(refs, list) else [])[:10]]
    return policy.redact_value({
        "run_id": run_id or "",
        "evidence_saved": bool(evidence_refs),
        "evidence_count": len(evidence_refs),
        "evidence_refs": evidence_refs,
        "sanitized": True,
        "raw_output_hidden": True,
        "secrets_hidden": True,
        "private_paths_hidden": True,
        "revision": _revision_token("evidence-summary", run_id or "", evidence_refs),
        "source": "security_evidence_summary_json",
    })


def _compact_history_index(state: dict[str, Any] | None = None, *, limit: int | None = None, profile: str | None = None) -> list[dict[str, Any]]:
    payload = state if isinstance(state, dict) else {}
    bounded_limit = max(1, min(int(limit or _SECURITY_SPLIT_HISTORY_DEFAULT_LIMIT), _SECURITY_SPLIT_HISTORY_MAX_LIMIT))
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None
    if not history and last_run:
        history = [last_run]
    normalized_profile = None
    if profile:
        normalized_profile = _profile_for_run({"scan_profile": profile})
    compact: list[dict[str, Any]] = []
    for run in history:
        if not isinstance(run, dict):
            continue
        if normalized_profile and _profile_for_run(run) != normalized_profile:
            continue
        item = _trim_security_run_for_summary(run)
        if item:
            compact.append(item)
        if len(compact) >= bounded_limit:
            break
    return policy.redact_value(compact)


def _profile_state_from_state(profile: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_profile = _profile_for_run({"scan_profile": profile})
    payload = state if isinstance(state, dict) else default_state()
    history = _compact_history_index(payload, limit=_SECURITY_SPLIT_PREVIEW_LIMIT, profile=normalized_profile)
    profile_latest = payload.get("profile_latest") if isinstance(payload.get("profile_latest"), dict) else {}
    latest = profile_latest.get(normalized_profile) if isinstance(profile_latest.get(normalized_profile), dict) else None
    if latest is None:
        last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None
        if _profile_for_run(last_run) == normalized_profile:
            latest = last_run
    if latest is None and history:
        latest = history[0]
    latest_run = _trim_security_run_for_summary(latest) if isinstance(latest, dict) else None
    coverage = (latest_run or {}).get("coverage_summary") or payload.get("coverage_summary") if isinstance(payload, dict) else {}
    evidence_refs = (latest_run or {}).get("evidence_refs") or payload.get("evidence_refs") if isinstance(payload, dict) else []
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) and _profile_for_run(payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None) == normalized_profile else []
    critical = payload.get("critical_issues") if isinstance(payload.get("critical_issues"), list) and _profile_for_run(payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None) == normalized_profile else []
    response = {
        "profile": normalized_profile,
        "view_model": "security-profile-f7-v1",
        "status": (latest_run or {}).get("status") or ("unknown" if latest_run is None else payload.get("status")) or "unknown",
        "summary": (latest_run or {}).get("summary") or _profile_copy(normalized_profile)["name"],
        "score": int((latest_run or {}).get("score") or (payload.get("score") if latest_run else 0) or 0),
        "updated_at": (latest_run or {}).get("updated_at") or (latest_run or {}).get("completed_at") or payload.get("updated_at"),
        "latest_run": latest_run,
        "coverage_summary": _compact_coverage(coverage if isinstance(coverage, dict) else {}),
        "tool_results": _compact_tool_results((latest_run or {}).get("tool_results") if isinstance((latest_run or {}).get("tool_results"), dict) else {}),
        "execution_timeline": _bounded_list((latest_run or {}).get("execution_timeline"), _SECURITY_SPLIT_PREVIEW_LIMIT),
        "finding_delta": _trim_security_delta_for_summary(payload.get("finding_delta") if latest_run else {}),
        "findings": _bounded_list(findings, _SECURITY_SUMMARY_FINDING_LIMIT),
        "critical_issues": _bounded_list(critical, _SECURITY_SUMMARY_FINDING_LIMIT),
        "evidence_summary": _compact_evidence_summary_from_refs((latest_run or {}).get("run_id"), evidence_refs if isinstance(evidence_refs, list) else []),
        "history": history,
        "revision": _profile_revision(normalized_profile, payload, latest_run),
        "source": "security_profile_json",
        "sanitized": True,
    }
    return policy.redact_value(response)


def _freshness_from_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = state if isinstance(state, dict) else default_state()
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    profile_updated_at: dict[str, Any] = {}
    profile_latest = payload.get("profile_latest") if isinstance(payload.get("profile_latest"), dict) else security_profile_latest(history)
    for profile in (policy.SCAN_PROFILE_QUICK, policy.SCAN_PROFILE_FULL, policy.SCAN_PROFILE_APP):
        latest = profile_latest.get(profile) if isinstance(profile_latest.get(profile), dict) else None
        profile_updated_at[profile] = (latest or {}).get("updated_at") or (latest or {}).get("completed_at") or None
    profile_revisions = {
        profile: _profile_revision(profile, payload, profile_latest.get(profile) if isinstance(profile_latest.get(profile), dict) else None)
        for profile in (policy.SCAN_PROFILE_QUICK, policy.SCAN_PROFILE_FULL, policy.SCAN_PROFILE_APP)
    }
    return policy.redact_value({
        "view_model": "security-freshness-f9-v1",
        "status": payload.get("status") or "unknown",
        "revision": _compact_revision(payload),
        "updated_at": payload.get("updated_at"),
        "active_scan": _is_live_security_state(payload),
        "profile_updated_at": profile_updated_at,
        "profile_revisions": profile_revisions,
        "summary_revision": _summary_revision(payload),
        "history_revision": _history_revision(payload),
        "progress_revision": _progress_revision(payload),
        "source": "security_freshness_json",
        "summary_endpoint": "/api/lite/security/summary",
        "details_endpoint": "/api/lite/security",
        "profiles_endpoint": "/api/lite/security/profiles/{profile}",
        "history_endpoint": "/api/lite/security/history?limit=20",
        "progress_endpoint": "/api/lite/security/progress",
        "sanitized": True,
    })


def _progress_from_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = state if isinstance(state, dict) else {}
    progress = payload.get("scan_progress") if isinstance(payload.get("scan_progress"), dict) else {}
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else {}
    active = _is_live_security_state(payload)
    return policy.redact_value({
        "view_model": "security-progress-f7-v1",
        "active_scan": active,
        "run_id": progress.get("run_id") or last_run.get("run_id") or None,
        "profile": progress.get("profile") or last_run.get("scan_profile") or payload.get("scan_profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": progress.get("app_id") or last_run.get("app_id") or payload.get("app_id") or "",
        "stage": progress.get("stage") or progress.get("phase") or last_run.get("status") or payload.get("status") or "idle",
        "status": progress.get("status") or last_run.get("status") or payload.get("status") or "idle",
        "percent": int(progress.get("percent") or 0),
        "message": progress.get("message") or progress.get("summary") or last_run.get("summary") or payload.get("summary") or "Security is idle.",
        "revision": _progress_revision(payload),
        "updated_at": payload.get("updated_at") or last_run.get("updated_at") or last_run.get("completed_at"),
        "source": "security_progress_json",
        "sanitized": True,
    })


def _details_from_run(run_id: str, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
    safe_run_id = evidence.safe_run_id(run_id)
    run = evidence.read_run(safe_run_id)
    payload = state if isinstance(state, dict) else evidence.read_state() or {}
    if run is None:
        last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None
        if isinstance(last_run, dict) and evidence.safe_run_id(str(last_run.get("run_id") or "")) == safe_run_id:
            run = last_run
    if run is None:
        for item in payload.get("history") if isinstance(payload.get("history"), list) else []:
            if isinstance(item, dict) and evidence.safe_run_id(str(item.get("run_id") or "")) == safe_run_id:
                run = item
                break
    if run is None:
        return None
    evidence_payload = evidence.read_evidence_summary(safe_run_id) or {}
    evidence_refs = run.get("evidence_refs") if isinstance(run.get("evidence_refs"), list) else evidence_payload.get("evidence_refs") if isinstance(evidence_payload.get("evidence_refs"), list) else []
    findings = evidence_payload.get("findings") if isinstance(evidence_payload.get("findings"), list) else payload.get("findings") if isinstance(payload.get("findings"), list) and str((payload.get("last_run") or {}).get("run_id") if isinstance(payload.get("last_run"), dict) else "") == str(run.get("run_id")) else []
    critical = [item for item in findings if isinstance(item, dict) and policy.normalize_severity(item.get("severity")) in {"critical", "high"}]
    response = {
        "view_model": "security-details-f7-v1",
        "run_id": run.get("run_id") or safe_run_id,
        "profile": _profile_for_run(run),
        "app_id": run.get("app_id") or "",
        "app_label": run.get("app_label") or "",
        "status": run.get("status") or "unknown",
        "score": int(run.get("score") or evidence_payload.get("score") or 0),
        "summary": run.get("summary") or evidence_payload.get("summary") or "Security check details are available.",
        "updated_at": run.get("updated_at") or run.get("completed_at") or payload.get("updated_at"),
        "execution_timeline": _bounded_list(run.get("execution_timeline"), 20),
        "coverage_summary": _compact_coverage(run.get("coverage_summary") if isinstance(run.get("coverage_summary"), dict) else {}, limit=20),
        "target_statuses": _bounded_list((run.get("coverage_summary") or {}).get("target_statuses") if isinstance(run.get("coverage_summary"), dict) else [], 20),
        "tool_results": _compact_tool_results(run.get("tool_results") if isinstance(run.get("tool_results"), dict) else {}),
        "findings": _bounded_list(findings, _SECURITY_SPLIT_FINDING_LIMIT),
        "critical_issues": _bounded_list(critical, _SECURITY_SUMMARY_FINDING_LIMIT),
        "evidence_summary": _compact_evidence_summary_from_refs(str(run.get("run_id") or safe_run_id), evidence_refs if isinstance(evidence_refs, list) else []),
        "finding_delta": _trim_security_delta_for_summary(payload.get("finding_delta")),
        "revision": _revision_token("details", _run_revision_signals(run), safe_run_id),
        "source": "security_details_json",
        "sanitized": True,
    }
    return policy.redact_value(response)


def _sqlite_tool_results(repository: Any, run_id: str) -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for item in repository.list_tool_runs(run_id):
        name = str(item.get("tool_name") or "tool")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        tools[name] = policy.redact_value({
            "status": item.get("status") or "unknown",
            "finding_count": int(item.get("finding_count") or 0),
            "timed_out": bool(item.get("timed_out")),
            "timeout_reason": item.get("timeout_reason"),
            **metadata,
        })
    return tools


def _sqlite_run_payload(
    repository: Any,
    run: dict[str, Any] | None,
    *,
    include_details: bool = False,
    include_related: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(run, dict) or not run.get("run_id"):
        return None
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    run_id = str(run["run_id"])
    load_related = include_details or include_related
    evidence_rows = (
        repository.list_evidence_refs(run_id, limit=100 if include_details else 10)
        if load_related
        else []
    )
    evidence_refs = [
        str(item.get("relative_path") or "")
        for item in evidence_rows
        if item.get("relative_path")
    ]
    tool_results = _sqlite_tool_results(repository, run_id) if load_related else {}
    payload = {
        "run_id": run_id,
        "status": run.get("status") or "unknown",
        "summary": run.get("summary") or "",
        "score": run.get("score"),
        "scan_profile": run.get("profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": run.get("app_id") or "",
        "app_label": run.get("app_label") or "",
        "requested_at": run.get("requested_at"),
        "accepted_at": run.get("accepted_at"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "updated_at": run.get("updated_at"),
        "revision": int(run.get("revision") or 0),
        "partial_results": bool(run.get("partial_results")),
        "checks_reviewed": int(run.get("checks_reviewed") or 0),
        "items_to_review": int(run.get("items_to_review") or 0),
        "critical_count": int(run.get("critical_count") or 0),
        "high_count": int(run.get("high_count") or 0),
        "medium_count": int(run.get("medium_count") or 0),
        "low_count": int(run.get("low_count") or 0),
        "info_count": int(run.get("info_count") or 0),
        "failure_code": run.get("failure_code"),
        "failure_message": run.get("failure_message"),
        "coverage_summary": metadata.get("coverage_summary") if isinstance(metadata.get("coverage_summary"), dict) else {},
        "execution_timeline": metadata.get("execution_timeline") if isinstance(metadata.get("execution_timeline"), list) else [],
        "finding_delta": metadata.get("finding_delta") if isinstance(metadata.get("finding_delta"), dict) else {},
        "tool_results": tool_results,
        "tools": list(tool_results) or ["lynis", "trivy"],
        "evidence_refs": evidence_refs,
        "evidence_saved": bool(run.get("evidence_saved") or evidence_refs),
    }
    if include_details:
        payload["target_statuses"] = metadata.get("target_statuses") if isinstance(metadata.get("target_statuses"), list) else []
    return policy.redact_value(payload)


def _sqlite_finding_delta(repository: Any, run: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, dict) or not run.get("run_id"):
        return _trim_security_delta_for_summary(None)
    current = repository.list_findings(str(run["run_id"]), limit=_SECURITY_SPLIT_FINDING_LIMIT)
    page = repository.list_runs_page(
        limit=10, profile=str(run.get("profile") or policy.SCAN_PROFILE_QUICK),
        app_id=str(run.get("app_id") or "") or None,
    )
    previous = next(
        (item for item in page.get("runs", []) if item.get("run_id") != run.get("run_id") and item.get("status") in {"succeeded", "degraded"}),
        None,
    )
    previous_findings = repository.list_findings(str(previous["run_id"]), limit=_SECURITY_SPLIT_FINDING_LIMIT) if previous else []
    current_by = {str(item.get("fingerprint") or item.get("finding_key")): item for item in current}
    previous_by = {str(item.get("fingerprint") or item.get("finding_key")): item for item in previous_findings}
    new_items = [item for key, item in current_by.items() if key not in previous_by]
    resolved = [item for key, item in previous_by.items() if key not in current_by]
    ongoing = [item for key, item in current_by.items() if key in previous_by]
    return policy.redact_value({
        "new_count": len(new_items), "resolved_count": len(resolved),
        "unchanged_count": len(ongoing), "new": new_items[:3],
        "resolved": resolved[:3], "unchanged": ongoing[:3],
    })


def _sqlite_state_projection() -> tuple[Any, dict[str, Any], int]:
    repository = _security_repository()
    revision_info = repository.get_domain_revision()
    revision = int(revision_info.get("revision") or 0)
    page = repository.list_runs_page(limit=_SECURITY_SPLIT_HISTORY_MAX_LIMIT)
    runs = page.get("runs") if isinstance(page.get("runs"), list) else []
    active = repository.get_active_scan()
    latest_row = active or (runs[0] if runs else None)
    latest = _sqlite_run_payload(
        repository, latest_row, include_details=True, include_related=True
    )
    history = [
        item
        for item in (_sqlite_run_payload(repository, run) for run in runs)
        if item
    ]
    profile_latest: dict[str, dict[str, Any]] = {}
    for profile in (
        policy.SCAN_PROFILE_QUICK,
        policy.SCAN_PROFILE_FULL,
        policy.SCAN_PROFILE_APP,
    ):
        profile_row = repository.get_latest_run(profile)
        profile_payload = _sqlite_run_payload(
            repository, profile_row, include_related=True
        )
        if profile_payload:
            profile_latest[profile] = profile_payload
    findings = repository.list_findings(str(latest["run_id"]), limit=_SECURITY_SPLIT_FINDING_LIMIT) if latest else []
    refs = latest.get("evidence_refs") if latest else []
    counts = {
        severity: int((latest or {}).get(f"{severity}_count") or 0)
        for severity in policy.SEVERITIES
    }
    score = int((latest or {}).get("score") or policy.score_for_counts(counts)) if latest else 100
    if latest and str(latest.get("status")) in {"queued", "accepted", "running", "working", "in_progress"}:
        state_status = str(latest.get("status"))
        state_summary = str(latest.get("summary") or "Safety check running.")
    elif latest and str(latest.get("status")) == "failed":
        state_status, state_summary = "degraded", str(latest.get("summary") or "Security check needs review.")
    elif latest:
        state_status, mapped = policy.status_for_score(score, counts)
        state_summary = str(latest.get("summary") or mapped)
    else:
        state_status, state_summary = "healthy", "No urgent safety issues found."
    progress = repository.get_progress(str(latest["run_id"])) if latest else None
    state = policy.redact_value({
        "status": state_status, "summary": state_summary, "score": score,
        "last_run": latest, "checks_reviewed": int((latest or {}).get("checks_reviewed") or 0),
        "items_to_review": int((latest or {}).get("items_to_review") or len(findings)),
        "critical_issues": [item for item in findings if policy.normalize_severity(item.get("severity")) in {"critical", "high"}][:_SECURITY_SUMMARY_FINDING_LIMIT],
        "guidance": policy.GUIDANCE, "component_posture": component_posture(findings),
        "scan_profile": (latest or {}).get("scan_profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": (latest or {}).get("app_id") or "", "app_label": (latest or {}).get("app_label") or "",
        "coverage_summary": (latest or {}).get("coverage_summary") or {},
        "findings": findings, "evidence_refs": refs or [], "history": history,
        "profile_latest": profile_latest, "finding_delta": _sqlite_finding_delta(repository, latest_row),
        "execution_timeline": (latest or {}).get("execution_timeline") or [],
        "scan_progress": ({
            "run_id": progress.get("run_id"), "profile": progress.get("profile"),
            "app_id": progress.get("app_id"), "status": progress.get("status"),
            "stage": progress.get("stage"), "percent": progress.get("percent"),
            "message": progress.get("message"), "tool": progress.get("tool"),
            "updated_at": progress.get("updated_at"), "active_scan": progress.get("active_scan"),
            "event_id": progress.get("event_id"),
        } if progress else None),
        "updated_at": revision_info.get("updated_at") or (latest or {}).get("updated_at"),
        "storage_backend": "sqlite",
    })
    return repository, state, revision


def _sqlite_cached_read(kind: str, *signals: Any, builder) -> dict[str, Any]:
    repository = _security_repository()
    revision = int(repository.get_domain_revision().get("revision") or 0)
    started_at = time.perf_counter()
    payload = _cached_compact_read(
        kind, ("sqlite", str(repository.path), revision, *signals), builder
    )
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    log = _LOGGER.warning if elapsed_ms >= 250 else _LOGGER.debug
    log("Security SQLite %s read completed in %.2f ms", kind, elapsed_ms)
    return payload


def _sqlite_compact_state_for_latest(
    repository: Any,
    latest_row: dict[str, Any] | None,
    *,
    history_rows: list[dict[str, Any]] | None = None,
    profile_latest_rows: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    latest = _sqlite_run_payload(repository, latest_row, include_details=True, include_related=True)
    history = [
        item for item in (
            _sqlite_run_payload(repository, row) for row in (history_rows or [])
        ) if item
    ]
    profile_latest = {
        profile: payload
        for profile, row in (profile_latest_rows or {}).items()
        if (payload := _sqlite_run_payload(repository, row, include_related=True))
    }
    findings = (
        repository.list_findings(str(latest["run_id"]), limit=_SECURITY_SPLIT_FINDING_LIMIT)
        if latest else []
    )
    counts = {
        severity: int((latest or {}).get(f"{severity}_count") or 0)
        for severity in policy.SEVERITIES
    }
    score = int((latest or {}).get("score") or policy.score_for_counts(counts)) if latest else 100
    if latest and str(latest.get("status")) in {"queued", "accepted", "running", "working", "in_progress"}:
        state_status = str(latest.get("status"))
        state_summary = str(latest.get("summary") or "Safety check running.")
    elif latest and str(latest.get("status")) == "failed":
        state_status, state_summary = "degraded", str(latest.get("summary") or "Security check needs review.")
    elif latest:
        state_status, mapped = policy.status_for_score(score, counts)
        state_summary = str(latest.get("summary") or mapped)
    else:
        state_status, state_summary = "healthy", "No urgent safety issues found."
    progress = repository.get_progress(str(latest["run_id"])) if latest else None
    revision_info = repository.get_domain_revision()
    return policy.redact_value({
        "status": state_status, "summary": state_summary, "score": score,
        "last_run": latest, "checks_reviewed": int((latest or {}).get("checks_reviewed") or 0),
        "items_to_review": int((latest or {}).get("items_to_review") or len(findings)),
        "critical_issues": [item for item in findings if policy.normalize_severity(item.get("severity")) in {"critical", "high"}][:_SECURITY_SUMMARY_FINDING_LIMIT],
        "guidance": policy.GUIDANCE, "component_posture": component_posture(findings),
        "scan_profile": (latest or {}).get("scan_profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": (latest or {}).get("app_id") or "", "app_label": (latest or {}).get("app_label") or "",
        "coverage_summary": (latest or {}).get("coverage_summary") or {},
        "findings": findings, "evidence_refs": (latest or {}).get("evidence_refs") or [],
        "history": history, "profile_latest": profile_latest,
        "finding_delta": _sqlite_finding_delta(repository, latest_row),
        "execution_timeline": (latest or {}).get("execution_timeline") or [],
        "scan_progress": progress,
        "updated_at": revision_info.get("updated_at") or (latest or {}).get("updated_at"),
        "storage_backend": "sqlite",
    })


def _sqlite_summary_state() -> dict[str, Any]:
    def build() -> dict[str, Any]:
        repository = _security_repository()
        revision = int(repository.get_domain_revision().get("revision") or 0)
        active = repository.get_active_scan()
        latest_row = active or repository.get_latest_run()
        history_rows = repository.list_runs_page(limit=_SECURITY_SUMMARY_HISTORY_LIMIT).get("runs", [])
        profile_rows = {
            profile: row
            for profile in (policy.SCAN_PROFILE_QUICK, policy.SCAN_PROFILE_FULL, policy.SCAN_PROFILE_APP)
            if (row := repository.get_latest_run(profile))
        }
        state = _sqlite_compact_state_for_latest(
            repository, latest_row, history_rows=history_rows, profile_latest_rows=profile_rows
        )
        payload = _security_summary_from_state(state)
        payload.update({
            "revision": _revision_token("sqlite-summary", revision),
            "source": "security_summary_sqlite", "storage_backend": "sqlite",
        })
        return payload
    return _sqlite_cached_read("summary", builder=build)


def _sqlite_progress_payload(progress: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = progress if isinstance(progress, dict) else {}
    revision = int(payload.get("domain_revision") or 0)
    response = policy.redact_value({
        "view_model": "security-progress-f7-v1",
        "active_scan": bool(payload.get("active_scan")),
        "run_id": payload.get("run_id") or None,
        "profile": payload.get("profile") or policy.SCAN_PROFILE_QUICK,
        "app_id": payload.get("app_id") or "",
        "stage": payload.get("stage") or "Waiting",
        "status": payload.get("status") or "idle",
        "percent": int(payload.get("percent") or 0),
        "message": payload.get("message") or "No safety check is running.",
        "updated_at": payload.get("updated_at"),
        "sanitized": True,
        "revision": _revision_token(
            "sqlite-progress", revision, payload.get("run_id"), payload.get("status"),
            payload.get("percent"), payload.get("event_id"),
        ),
        "source": "security_progress_sqlite",
        "storage_backend": "sqlite",
    })
    return response


def _remember_sqlite_progress(payload: dict[str, Any]) -> dict[str, Any]:
    global _SQLITE_PROGRESS_SNAPSHOT, _SQLITE_PROGRESS_SNAPSHOT_DB
    with _SQLITE_PROGRESS_SNAPSHOT_LOCK:
        _SQLITE_PROGRESS_SNAPSHOT = copy.deepcopy(payload)
        try:
            _SQLITE_PROGRESS_SNAPSHOT_DB = str(_security_store_api().database_path())
        except Exception:
            _SQLITE_PROGRESS_SNAPSHOT_DB = ""
    return payload


def _last_known_sqlite_progress(reason: str) -> dict[str, Any] | None:
    with _SQLITE_PROGRESS_SNAPSHOT_LOCK:
        snapshot = copy.deepcopy(_SQLITE_PROGRESS_SNAPSHOT)
    if not snapshot:
        return None
    snapshot["read_degraded"] = True
    snapshot["read_fallback"] = "last_known_sqlite_progress"
    snapshot["read_error_type"] = reason
    snapshot["source"] = "security_progress_sqlite"
    snapshot["storage_backend"] = "sqlite"
    return policy.redact_value(snapshot)


def _refresh_sqlite_progress_snapshot(*, repository: Any | None = None) -> dict[str, Any]:
    """Refresh the process-local live projection from committed SQLite state."""
    global _SQLITE_PROGRESS_FAILURES, _SQLITE_PROGRESS_REFRESHED_AT
    repo = repository or _security_repository()
    progress = repo.get_progress() or {}
    payload = _remember_sqlite_progress(_sqlite_progress_payload(progress))
    _SQLITE_PROGRESS_FAILURES = 0
    _SQLITE_PROGRESS_REFRESHED_AT = time.monotonic()
    return payload


def _refresh_sqlite_progress_snapshot_worker() -> None:
    global _SQLITE_PROGRESS_FAILURES, _SQLITE_PROGRESS_REFRESH_INFLIGHT
    try:
        _refresh_sqlite_progress_snapshot()
    except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as exc:
        _SQLITE_PROGRESS_FAILURES += 1
        _LOGGER.warning(
            "Security SQLite progress background refresh degraded (%s, consecutive=%d)",
            type(exc).__name__,
            _SQLITE_PROGRESS_FAILURES,
        )
    finally:
        with _SQLITE_PROGRESS_REFRESH_LOCK:
            _SQLITE_PROGRESS_REFRESH_INFLIGHT = False


def _schedule_sqlite_progress_refresh() -> None:
    global _SQLITE_PROGRESS_REFRESH_INFLIGHT
    if time.monotonic() - _SQLITE_PROGRESS_REFRESHED_AT < _SQLITE_PROGRESS_REFRESH_INTERVAL_SECONDS:
        return
    with _SQLITE_PROGRESS_REFRESH_LOCK:
        if _SQLITE_PROGRESS_REFRESH_INFLIGHT:
            return
        _SQLITE_PROGRESS_REFRESH_INFLIGHT = True
    threading.Thread(
        target=_refresh_sqlite_progress_snapshot_worker,
        name="pocketlab-security-progress-refresh",
        daemon=True,
    ).start()


def _memory_sqlite_progress_snapshot() -> dict[str, Any] | None:
    try:
        current_db = str(_security_store_api().database_path())
    except Exception:
        current_db = ""
    with _SQLITE_PROGRESS_SNAPSHOT_LOCK:
        if _SQLITE_PROGRESS_SNAPSHOT_DB != current_db:
            return None
        snapshot = copy.deepcopy(_SQLITE_PROGRESS_SNAPSHOT)
    if snapshot is None:
        return None
    snapshot["read_latency_ms"] = 0.0
    snapshot["read_degraded"] = False
    snapshot["read_projection"] = "memory"
    snapshot["projection_age_ms"] = round(
        max(0.0, time.monotonic() - _SQLITE_PROGRESS_REFRESHED_AT) * 1000, 2
    )
    return policy.redact_value(snapshot)


def _sqlite_progress_state() -> dict[str, Any]:
    global _SQLITE_PROGRESS_FAILURES
    snapshot = _memory_sqlite_progress_snapshot()
    if snapshot is not None:
        _schedule_sqlite_progress_refresh()
        return snapshot
    started_at = time.perf_counter()
    try:
        payload = _refresh_sqlite_progress_snapshot()
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        payload["read_latency_ms"] = round(elapsed_ms, 2)
        payload["read_degraded"] = False
        return payload
    except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as exc:
        _SQLITE_PROGRESS_FAILURES += 1
        reason = type(exc).__name__
        fallback = _last_known_sqlite_progress(reason)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        _LOGGER.warning(
            "Security SQLite progress read degraded after %.2f ms (%s, consecutive=%d)",
            elapsed_ms, reason, _SQLITE_PROGRESS_FAILURES,
        )
        if fallback is not None:
            fallback["read_latency_ms"] = round(elapsed_ms, 2)
            fallback["read_failure_count"] = _SQLITE_PROGRESS_FAILURES
            return fallback
        # Startup-only fallback: keep the endpoint bounded while preserving the
        # SQLite source contract. JSON remains compatibility evidence, not the
        # authoritative cutover read.
        json_progress = _progress_from_state(_ensure_compact_state())
        payload = _sqlite_progress_payload(json_progress)
        payload.update({
            "read_degraded": True,
            "read_fallback": "json_bootstrap_snapshot",
            "read_error_type": reason,
            "read_latency_ms": round(elapsed_ms, 2),
            "read_failure_count": _SQLITE_PROGRESS_FAILURES,
        })
        return _remember_sqlite_progress(policy.redact_value(payload))


def _sqlite_freshness_state() -> dict[str, Any]:
    def build() -> dict[str, Any]:
        repository = _security_repository()
        revision_info = repository.get_domain_revision()
        revision = int(revision_info.get("revision") or 0)
        progress = repository.get_progress() or {}
        profile_rows = {
            profile: repository.get_latest_run(profile)
            for profile in (policy.SCAN_PROFILE_QUICK, policy.SCAN_PROFILE_FULL, policy.SCAN_PROFILE_APP)
        }
        profile_updated_at = {
            profile: (row or {}).get("updated_at") or (row or {}).get("completed_at")
            for profile, row in profile_rows.items()
        }
        profile_revisions = {
            profile: _revision_token("sqlite-profile", revision, profile, (row or {}).get("run_id"), (row or {}).get("revision"))
            for profile, row in profile_rows.items()
        }
        return policy.redact_value({
            "view_model": "security-freshness-f9-v1",
            "status": "running" if progress.get("active_scan") else "healthy",
            "revision": _revision_token("sqlite-freshness", revision),
            "updated_at": revision_info.get("updated_at") or progress.get("updated_at"),
            "active_scan": bool(progress.get("active_scan")),
            "profile_updated_at": profile_updated_at,
            "profile_revisions": profile_revisions,
            "summary_revision": _revision_token("sqlite-summary", revision),
            "history_revision": _revision_token("sqlite-history", revision),
            "progress_revision": _revision_token("sqlite-progress", revision, progress.get("run_id"), progress.get("status"), progress.get("percent"), progress.get("event_id")),
            "source": "security_freshness_sqlite",
            "summary_endpoint": "/api/lite/security/summary",
            "details_endpoint": "/api/lite/security",
            "profiles_endpoint": "/api/lite/security/profiles/{profile}",
            "history_endpoint": "/api/lite/security/history?limit=20",
            "progress_endpoint": "/api/lite/security/progress",
            "sanitized": True, "storage_backend": "sqlite",
        })
    return _sqlite_cached_read("freshness", builder=build)


def _sqlite_profile_state(profile: str) -> dict[str, Any]:
    normalized = policy.normalize_scan_profile(profile)
    def build() -> dict[str, Any]:
        repository = _security_repository()
        revision = int(repository.get_domain_revision().get("revision") or 0)
        latest_row = repository.get_latest_run(normalized)
        history_rows = repository.list_runs_page(
            limit=_SECURITY_SPLIT_PREVIEW_LIMIT, profile=normalized
        ).get("runs", [])
        state = _sqlite_compact_state_for_latest(
            repository, latest_row, history_rows=history_rows,
            profile_latest_rows={normalized: latest_row} if latest_row else {},
        )
        payload = _profile_state_from_state(normalized, state)
        payload.update({
            "revision": _revision_token("sqlite-profile", revision, normalized, (payload.get("latest_run") or {}).get("run_id")),
            "source": "security_profile_sqlite", "storage_backend": "sqlite",
        })
        return payload
    return _sqlite_cached_read("profile", normalized, builder=build)


def _encode_history_cursor(cursor: dict[str, Any] | None) -> str | None:
    if not isinstance(cursor, dict) or not cursor.get("run_id"):
        return None
    material = f"{int(cursor.get('epoch_ms') or 0)}:{evidence.safe_run_id(str(cursor['run_id']))}"
    return base64.urlsafe_b64encode(material.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_history_cursor(cursor: str | None) -> tuple[int | None, str | None]:
    token = str(cursor or "").strip()
    if not token:
        return None, None
    try:
        padded = token + "=" * (-len(token) % 4)
        material = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        epoch_text, run_id = material.split(":", 1)
        safe_run_id = evidence.safe_run_id(run_id)
        if safe_run_id == "unknown":
            raise ValueError("invalid run id")
        return int(epoch_text), safe_run_id
    except (ValueError, UnicodeError, base64.binascii.Error) as exc:
        raise ValueError("Invalid Security history cursor") from exc


def _sqlite_history_state(limit: int | None = None, cursor: str | None = None) -> dict[str, Any]:
    bounded = max(1, min(int(limit or _SECURITY_SPLIT_HISTORY_DEFAULT_LIMIT), _SECURITY_SPLIT_HISTORY_MAX_LIMIT))
    def build() -> dict[str, Any]:
        repository = _security_repository()
        revision = int(repository.get_domain_revision().get("revision") or 0)
        cursor_epoch_ms, cursor_run_id = _decode_history_cursor(cursor)
        page = repository.list_runs_page(
            limit=bounded, cursor_epoch_ms=cursor_epoch_ms, cursor_run_id=cursor_run_id
        )
        history = [item for item in (_sqlite_run_payload(repository, run) for run in page.get("runs", [])) if item]
        next_cursor = _encode_history_cursor(page.get("next_cursor"))
        return policy.redact_value({
            "view_model": "security-history-f7-v1", "limit": bounded,
            "max_limit": _SECURITY_SPLIT_HISTORY_MAX_LIMIT, "history": history,
            "has_more": bool(page.get("has_more")), "next_cursor": next_cursor,
            "revision": _revision_token("sqlite-history", revision, bounded, cursor, next_cursor),
            "source": "security_history_sqlite", "storage_backend": "sqlite", "sanitized": True,
        })
    return _sqlite_cached_read("history", bounded, cursor or "", builder=build)


def _sqlite_details_state(run_id: str) -> dict[str, Any] | None:
    safe_run_id = evidence.safe_run_id(run_id)
    def build() -> dict[str, Any]:
        repository = _security_repository()
        revision = int(repository.get_domain_revision().get("revision") or 0)
        row = repository.get_run(safe_run_id)
        run = _sqlite_run_payload(repository, row, include_details=True)
        if not run:
            return {}
        findings = repository.list_findings(safe_run_id, limit=_SECURITY_SPLIT_FINDING_LIMIT)
        critical = [item for item in findings if policy.normalize_severity(item.get("severity")) in {"critical", "high"}]
        refs = run.get("evidence_refs") if isinstance(run.get("evidence_refs"), list) else []
        return policy.redact_value({
            "view_model": "security-details-f7-v1", "run_id": safe_run_id,
            "profile": run.get("scan_profile"), "app_id": run.get("app_id") or "",
            "app_label": run.get("app_label") or "", "status": run.get("status") or "unknown",
            "score": int(run.get("score") or 0), "summary": run.get("summary") or "Security check details are available.",
            "updated_at": run.get("updated_at") or run.get("completed_at"),
            "execution_timeline": _bounded_list(run.get("execution_timeline"), 20),
            "coverage_summary": _compact_coverage(run.get("coverage_summary"), limit=20),
            "target_statuses": _bounded_list(run.get("target_statuses"), 20),
            "tool_results": _compact_tool_results(run.get("tool_results")),
            "findings": _bounded_list(findings, _SECURITY_SPLIT_FINDING_LIMIT),
            "critical_issues": _bounded_list(critical, _SECURITY_SUMMARY_FINDING_LIMIT),
            "evidence_summary": _compact_evidence_summary_from_refs(safe_run_id, refs),
            "finding_delta": _sqlite_finding_delta(repository, row),
            "revision": _revision_token("sqlite-details", revision, safe_run_id, run.get("revision")),
            "source": "security_details_sqlite", "storage_backend": "sqlite", "sanitized": True,
        })
    payload = _sqlite_cached_read("details", safe_run_id, builder=build)
    return payload if payload.get("run_id") else None


def _sqlite_evidence_summary_state(run_id: str) -> dict[str, Any] | None:
    safe_run_id = evidence.safe_run_id(run_id)
    def build() -> dict[str, Any]:
        repository = _security_repository()
        revision = int(repository.get_domain_revision().get("revision") or 0)
        refs = [str(item.get("relative_path") or "") for item in repository.list_evidence_refs(safe_run_id, limit=10) if item.get("relative_path")]
        if not repository.get_run(safe_run_id):
            return {}
        payload = _compact_evidence_summary_from_refs(safe_run_id, refs)
        payload.update({
            "revision": _revision_token("sqlite-evidence", revision, safe_run_id, refs),
            "source": "security_evidence_summary_sqlite", "storage_backend": "sqlite",
        })
        return payload
    payload = _sqlite_cached_read("evidence_summary", safe_run_id, builder=build)
    return payload if payload.get("run_id") else None


def write_compact_security_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = policy.redact_value(state if isinstance(state, dict) else evidence.read_state() or default_state())
    root = evidence.compact_dir()
    summary = _security_summary_from_state(payload)
    summary["revision"] = _summary_revision(payload)
    freshness = _freshness_from_state(payload)
    progress = _progress_from_state(payload)
    history = {"view_model": "security-history-f7-v1", "limit": _SECURITY_SPLIT_HISTORY_DEFAULT_LIMIT, "max_limit": _SECURITY_SPLIT_HISTORY_MAX_LIMIT, "history": _compact_history_index(payload), "revision": _history_revision(payload), "source": "security_history_json", "sanitized": True}
    profiles = {profile: _profile_state_from_state(profile, payload) for profile in (policy.SCAN_PROFILE_QUICK, policy.SCAN_PROFILE_FULL, policy.SCAN_PROFILE_APP)}
    evidence.write_compact_json(root / "security_summary.json", summary)
    evidence.write_compact_json(root / "security_freshness.json", freshness)
    evidence.write_compact_json(root / "security_progress.json", progress)
    evidence.write_compact_json(root / "security_history_index.json", history)
    evidence.write_compact_json(root / "profile_latest.json", {"profiles": {key: value.get("latest_run") for key, value in profiles.items()}, "revision": _compact_revision(payload), "sanitized": True})
    evidence.write_compact_json(root / "coverage_summary_compact.json", _compact_coverage(payload.get("coverage_summary") if isinstance(payload.get("coverage_summary"), dict) else {}))
    for profile, profile_payload in profiles.items():
        evidence.write_compact_json(evidence.compact_profile_path(profile), profile_payload)
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else None
    if last_run and last_run.get("run_id"):
        details = _details_from_run(str(last_run.get("run_id")), payload)
        if details:
            evidence.write_compact_json(evidence.compact_details_path(str(last_run.get("run_id"))), details)
    invalidate_security_read_caches()
    return payload


def _persist_sqlite_state(state: dict[str, Any]) -> dict[str, Any]:
    if not _sqlite_lifecycle_enabled():
        return state
    last_run = state.get("last_run") if isinstance(state.get("last_run"), dict) else None
    if not last_run or not last_run.get("run_id"):
        return state
    repository = _security_repository()
    run_id = str(last_run["run_id"])
    profile = _profile_for_run(last_run)
    app_id = str(last_run.get("app_id") or "") or None
    existing = repository.get_run(run_id)
    if not existing:
        reservation = repository.reserve_scan(
            run_id=run_id, profile=profile, app_id=app_id,
            app_label=str(last_run.get("app_label") or "") or None,
            summary=str(last_run.get("summary") or state.get("summary") or ""),
            requested_at=last_run.get("requested_at") or last_run.get("started_at") or state.get("updated_at"),
            command_id=str(last_run.get("command_id") or run_id), recent_completion_seconds=0,
        )
        if not reservation.reserved and reservation.run.get("run_id") != run_id:
            raise RuntimeError("Security SQLite reservation belongs to another active scan")
        existing = repository.get_run(run_id)
    status = str(last_run.get("status") or "queued").lower().replace("-", "_")
    metadata = {
        "coverage_summary": last_run.get("coverage_summary") or state.get("coverage_summary") or {},
        "execution_timeline": last_run.get("execution_timeline") or state.get("execution_timeline") or [],
        "finding_delta": state.get("finding_delta") or {},
        "target_statuses": last_run.get("target_statuses") or [],
    }
    if status in {"queued", "accepted", "running", "working", "in_progress"}:
        existing_status = str((existing or {}).get("status") or "")
        if status == "queued":
            return state
        if status == "accepted":
            if existing_status == "queued":
                repository.mark_accepted(
                    run_id, accepted_at=last_run.get("accepted_at") or state.get("updated_at"),
                    summary=str(last_run.get("summary") or state.get("summary") or ""),
                )
            return state
        if existing_status in {"queued", "accepted"}:
            repository.mark_running(
                run_id, started_at=last_run.get("started_at") or state.get("updated_at"),
                summary=str(last_run.get("summary") or state.get("summary") or ""),
            )
        progress = state.get("scan_progress") if isinstance(state.get("scan_progress"), dict) else scan_progress_for_run(last_run) or {}
        repository.record_progress(
            run_id, status=status, stage=str(progress.get("stage") or status),
            percent=int(progress.get("percent")) if progress.get("percent") is not None else None,
            message=str(progress.get("message") or state.get("summary") or ""),
            tool=str(progress.get("tool") or "") or None, payload=metadata,
            created_at=progress.get("updated_at") or state.get("updated_at"),
        )
        return state
    findings = state.get("findings") if isinstance(state.get("findings"), list) else []
    refs = state.get("evidence_refs") if isinstance(state.get("evidence_refs"), list) else last_run.get("evidence_refs") if isinstance(last_run.get("evidence_refs"), list) else []
    tools = last_run.get("tool_results") if isinstance(last_run.get("tool_results"), dict) else {}
    counts = {severity: int(last_run.get(f"{severity}_count") or 0) for severity in policy.SEVERITIES}
    if status == "failed":
        repository.fail_run(
            run_id, failure_code=str(last_run.get("failure_code") or "worker_failed"),
            failure_message=str(last_run.get("failure_message") or state.get("summary") or "Security check needs review."),
            summary=str(last_run.get("summary") or state.get("summary") or "Security check needs review."),
            completed_at=last_run.get("completed_at") or state.get("updated_at"),
            partial_results=bool(last_run.get("partial_results")), findings=findings,
            evidence_refs=refs, tool_results=tools, metadata=metadata,
        )
    else:
        repository.complete_run(
            run_id, status="degraded" if status == "degraded" else "cancelled" if status in {"cancelled", "canceled"} else "succeeded",
            summary=str(last_run.get("summary") or state.get("summary") or "Safety check completed."),
            score=int(last_run.get("score") if last_run.get("score") is not None else state.get("score") or 0),
            partial_results=bool(last_run.get("partial_results")),
            completed_at=last_run.get("completed_at") or state.get("updated_at"),
            findings=findings, evidence_refs=refs, tool_results=tools, counts=counts,
            checks_reviewed=int(last_run.get("checks_reviewed") or state.get("checks_reviewed") or 0),
            items_to_review=int(last_run.get("items_to_review") or state.get("items_to_review") or 0),
            metadata=metadata,
        )
    _, canonical_state, _ = _sqlite_state_projection()
    return canonical_state


def _write_security_state(state: dict[str, Any]) -> dict[str, Any]:
    state = _persist_sqlite_state(state)
    if _sqlite_compact_reads_enabled():
        progress = state.get("scan_progress") if isinstance(state.get("scan_progress"), dict) else _progress_from_state(state)
        _remember_sqlite_progress(_sqlite_progress_payload(progress))
    run_id = str(((state.get("last_run") or {}) if isinstance(state.get("last_run"), dict) else {}).get("run_id") or "")
    try:
        clean = evidence.write_state(state)
        write_compact_security_state(clean)
        _record_projection_status(run_id, component="state", degraded=False)
        return clean
    except (OSError, ValueError, TypeError) as exc:
        if not _sqlite_lifecycle_enabled():
            raise
        _record_projection_status(
            run_id,
            component="state",
            degraded=True,
            reason=f"state_projection_{type(exc).__name__}",
        )
        _LOGGER.warning(
            "Security JSON compatibility projection degraded: %s", type(exc).__name__
        )
        invalidate_security_read_caches()
        return policy.redact_value(state)


def _ensure_compact_state() -> dict[str, Any]:
    root = evidence.compact_dir()
    required = [
        root / "security_summary.json",
        root / "security_freshness.json",
        root / "security_progress.json",
        root / "security_history_index.json",
        evidence.compact_profile_path(policy.SCAN_PROFILE_QUICK),
        evidence.compact_profile_path(policy.SCAN_PROFILE_FULL),
        evidence.compact_profile_path(policy.SCAN_PROFILE_APP),
    ]
    state = evidence.read_state()
    if not state:
        compact_summary = evidence.read_compact_json(root / "security_summary.json", {})
        state = {**default_state(), **(compact_summary if isinstance(compact_summary, dict) else {})}
    if not all(path.exists() for path in required):
        write_compact_security_state(state)
    return state



_SECURITY_STREAM_ALLOWED_FIELDS = {
    "type",
    "run_id",
    "profile",
    "app_id",
    "stage",
    "percent",
    "message",
    "status",
    "revision",
    "updated_at",
    "active_scan",
    "summary_revision",
    "profile_revision",
    "history_revision",
    "progress_revision",
}
_SECURITY_STREAM_TERMINAL_STATUSES = {"succeeded", "completed", "degraded", "failed", "cancelled", "canceled"}
_SECURITY_STREAM_LIVE_STATUSES = {"queued", "accepted", "waiting", "running", "working", "in_progress", "lynis_running", "trivy_running", "posture_running", "evidence_saving"}


def _security_stream_event_type(progress: dict[str, Any] | None = None) -> str:
    payload = progress if isinstance(progress, dict) else {}
    status = str(payload.get("status") or "").strip().lower()
    stage = str(payload.get("stage") or "").strip().lower()
    if not payload.get("run_id") and not payload.get("active_scan"):
        return "security.scan.heartbeat"
    if status in {"cancelled", "canceled"}:
        return "security.scan.cancelled"
    if status == "failed":
        return "security.scan.failed"
    if status in {"succeeded", "completed", "degraded"}:
        return "security.scan.completed"
    if status in {"queued", "accepted", "waiting"}:
        return "security.scan.queued"
    if "evidence" in stage or status == "evidence_saving":
        return "security.scan.evidence_saved"
    if status in _SECURITY_STREAM_LIVE_STATUSES or payload.get("active_scan"):
        return "security.scan.progress"
    return "security.scan.heartbeat"


def _security_stream_message(progress: dict[str, Any] | None = None) -> str:
    payload = progress if isinstance(progress, dict) else {}
    event_type = _security_stream_event_type(payload)
    if event_type == "security.scan.completed":
        return "Evidence saved"
    if event_type == "security.scan.failed":
        return "Needs attention"
    if event_type == "security.scan.cancelled":
        return "Connection paused"
    if event_type == "security.scan.queued":
        return "Working"
    message = str(payload.get("message") or "").strip()
    stage = str(payload.get("stage") or "").strip().lower()
    profile = str(payload.get("profile") or "quick").strip().lower()
    if "trivy" in stage or "files" in message.lower():
        return "Checking Pocket Lab files"
    if profile == policy.SCAN_PROFILE_APP:
        return "Checking app safety"
    return message or "Working"


def security_progress_event() -> dict[str, Any]:
    progress = split_progress_state()
    freshness = split_freshness_state()
    profile = str(progress.get("profile") or policy.SCAN_PROFILE_QUICK).strip().lower() or policy.SCAN_PROFILE_QUICK
    profile_revisions = freshness.get("profile_revisions") if isinstance(freshness.get("profile_revisions"), dict) else {}
    event = {
        "type": _security_stream_event_type(progress),
        "run_id": progress.get("run_id") or None,
        "profile": profile,
        "app_id": progress.get("app_id") or None,
        "stage": progress.get("stage") or progress.get("status") or "idle",
        "percent": int(progress.get("percent") or 0),
        "message": _security_stream_message(progress),
        "status": progress.get("status") or "idle",
        "revision": progress.get("revision") or _progress_revision(_ensure_compact_state()),
        "updated_at": progress.get("updated_at") or freshness.get("updated_at"),
        "active_scan": bool(progress.get("active_scan")),
        "summary_revision": freshness.get("summary_revision"),
        "profile_revision": profile_revisions.get(profile),
        "history_revision": freshness.get("history_revision"),
        "progress_revision": freshness.get("progress_revision") or progress.get("revision"),
    }
    clean = policy.redact_value({key: value for key, value in event.items() if key in _SECURITY_STREAM_ALLOWED_FIELDS})
    return clean


def security_progress_event_fingerprint(event: dict[str, Any] | None = None) -> str:
    payload = event if isinstance(event, dict) else {}
    return _revision_token(
        "stream",
        payload.get("type"),
        payload.get("run_id"),
        payload.get("status"),
        payload.get("stage"),
        payload.get("percent"),
        payload.get("revision") or payload.get("progress_revision"),
        payload.get("updated_at"),
    )

def split_freshness_state() -> dict[str, Any]:
    if _sqlite_compact_reads_enabled():
        return _sqlite_freshness_state()
    state = _ensure_compact_state()
    path = evidence.compact_dir() / "security_freshness.json"
    key = _compact_file_key(path, _compact_revision(state), _is_live_security_state(state))
    return _cached_compact_read("freshness", key, lambda: evidence.read_compact_json(path, _freshness_from_state(state)))


def split_profile_state(profile: str) -> dict[str, Any]:
    normalized_profile = policy.normalize_scan_profile(profile)
    if _sqlite_compact_reads_enabled():
        return _sqlite_profile_state(normalized_profile)
    state = _ensure_compact_state()
    path = evidence.compact_profile_path(normalized_profile)
    key = _compact_file_key(path, normalized_profile, _compact_revision(state), _is_live_security_state(state))
    return _cached_compact_read("profile", key, lambda: evidence.read_compact_json(path, _profile_state_from_state(normalized_profile, state)))


def split_history_state(limit: int | None = None, cursor: str | None = None) -> dict[str, Any]:
    if _sqlite_compact_reads_enabled():
        return _sqlite_history_state(limit, cursor)
    bounded_limit = max(1, min(int(limit or _SECURITY_SPLIT_HISTORY_DEFAULT_LIMIT), _SECURITY_SPLIT_HISTORY_MAX_LIMIT))
    state = _ensure_compact_state()
    path = evidence.compact_dir() / "security_history_index.json"
    key = _compact_file_key(path, bounded_limit, _compact_revision(state), _is_live_security_state(state))

    def build() -> dict[str, Any]:
        base = evidence.read_compact_json(path, {})
        history = base.get("history") if isinstance(base, dict) and isinstance(base.get("history"), list) else _compact_history_index(state, limit=bounded_limit)
        return {"view_model": "security-history-f7-v1", "limit": bounded_limit, "max_limit": _SECURITY_SPLIT_HISTORY_MAX_LIMIT, "history": history[:bounded_limit], "has_more": False, "next_cursor": None, "revision": _history_revision(state), "source": "security_history_json", "sanitized": True}

    return _cached_compact_read("history", key, build)


def split_progress_state() -> dict[str, Any]:
    if _sqlite_compact_reads_enabled():
        return _sqlite_progress_state()
    state = _ensure_compact_state()
    path = evidence.compact_dir() / "security_progress.json"
    key = _compact_file_key(path, _compact_revision(state), _is_live_security_state(state))
    return _cached_compact_read("progress", key, lambda: evidence.read_compact_json(path, _progress_from_state(state)))


def active_scan_state(profile: str | None = None, app_id: str | None = None) -> dict[str, Any] | None:
    progress = split_progress_state()
    if not isinstance(progress, dict) or not progress.get("active_scan"):
        return None
    progress_profile = policy.normalize_scan_profile(progress.get("profile") or progress.get("scan_profile") or policy.SCAN_PROFILE_QUICK)
    request_profile = policy.normalize_scan_profile(profile or progress_profile)
    if progress_profile != request_profile:
        return None
    if request_profile == policy.SCAN_PROFILE_APP:
        progress_app_id = str(progress.get("app_id") or "").strip().lower()
        request_app_id = str(app_id or "").strip().lower()
        if request_app_id and progress_app_id and progress_app_id != request_app_id:
            return None
    return policy.redact_value({
        "status": progress.get("status") or "running",
        "state": progress.get("status") or "running",
        "accepted": True,
        "duplicate": True,
        "already_running": True,
        "run_id": progress.get("run_id") or "",
        "command_id": progress.get("run_id") or "",
        "scan_profile": progress_profile,
        "profile": progress_profile,
        **({"app_id": progress.get("app_id"), "app_label": _app_label(progress.get("app_id"))} if progress.get("app_id") else {}),
        "summary": "A safety check is already running.",
        "scan_progress": progress,
    })



def _security_progress_age_seconds(progress: dict[str, Any]) -> float | None:
    value = progress.get("updated_at") or progress.get("completed_at") or progress.get("started_at")
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds())


def recent_completed_scan_state(profile: str | None = None, app_id: str | None = None) -> dict[str, Any] | None:
    progress = split_progress_state()
    if not isinstance(progress, dict) or progress.get("active_scan"):
        return None
    status = str(progress.get("status") or "").strip().lower().replace("-", "_")
    if status not in {"succeeded", "success", "completed", "complete", "done"}:
        return None
    age = _security_progress_age_seconds(progress)
    if age is None or age > _SECURITY_RECENT_COMPLETION_DEDUPE_SECONDS:
        return None
    progress_profile = policy.normalize_scan_profile(progress.get("profile") or progress.get("scan_profile") or policy.SCAN_PROFILE_QUICK)
    request_profile = policy.normalize_scan_profile(profile or progress_profile)
    if progress_profile != request_profile:
        return None
    if request_profile == policy.SCAN_PROFILE_APP:
        progress_app_id = str(progress.get("app_id") or "").strip().lower()
        request_app_id = str(app_id or "").strip().lower()
        if request_app_id and progress_app_id and progress_app_id != request_app_id:
            return None
    return policy.redact_value({
        "status": progress.get("status") or "succeeded",
        "state": progress.get("status") or "succeeded",
        "accepted": True,
        "duplicate": True,
        "recent_duplicate": True,
        "already_completed": True,
        "run_id": progress.get("run_id") or "",
        "command_id": progress.get("run_id") or "",
        "scan_profile": progress_profile,
        "profile": progress_profile,
        **({"app_id": progress.get("app_id"), "app_label": _app_label(progress.get("app_id"))} if progress.get("app_id") else {}),
        "summary": "A safety check just finished. Showing the latest saved result instead of starting another one.",
        "scan_progress": {
            **progress,
            "active_scan": False,
        },
    })



def split_run_details_state(run_id: str) -> dict[str, Any] | None:
    if _sqlite_compact_reads_enabled():
        return _sqlite_details_state(run_id)
    state = _ensure_compact_state()
    safe_run_id = evidence.safe_run_id(run_id)
    path = evidence.compact_details_path(safe_run_id)
    if not path.exists():
        details = _details_from_run(safe_run_id, state)
        if details:
            evidence.write_compact_json(path, details)
    key = _compact_file_key(path, safe_run_id, _compact_revision(state), _is_live_security_state(state))
    return _cached_compact_read("details", key, lambda: evidence.read_compact_json(path, _details_from_run(safe_run_id, state) or {}))


def split_evidence_summary_state(run_id: str) -> dict[str, Any] | None:
    if _sqlite_compact_reads_enabled():
        return _sqlite_evidence_summary_state(run_id)
    state = _ensure_compact_state()
    safe_run_id = evidence.safe_run_id(run_id)
    details_path = evidence.compact_details_path(safe_run_id)
    key = _compact_file_key(details_path, "evidence", safe_run_id, _compact_revision(state), _is_live_security_state(state))

    def build() -> dict[str, Any]:
        details = split_run_details_state(safe_run_id) or {}
        summary = details.get("evidence_summary") if isinstance(details.get("evidence_summary"), dict) else None
        if summary:
            return summary
        run = evidence.read_run(safe_run_id) or {}
        refs = run.get("evidence_refs") if isinstance(run.get("evidence_refs"), list) else []
        return _compact_evidence_summary_from_refs(safe_run_id, refs)

    payload = _cached_compact_read("evidence_summary", key, build)
    return payload if isinstance(payload, dict) and payload.get("run_id") else None

def summary_state() -> dict[str, Any]:
    if _sqlite_compact_reads_enabled():
        return _sqlite_summary_state()
    state = _ensure_compact_state()
    path = evidence.compact_dir() / "security_summary.json"
    key = _compact_file_key(path, _compact_revision(state), _is_live_security_state(state))
    return _cached_compact_read(
        "summary",
        key,
        lambda: evidence.read_compact_json(path, _security_summary_from_state(state)),
    )


def _maybe_persist_current_state_backfill(state: dict[str, Any], *, started_at: float, changed: bool) -> tuple[dict[str, Any], tuple[int, int] | None]:
    if not changed:
        return state, _state_file_key()
    # Persist only after an expensive compatibility backfill. This converts old
    # Security state files into the compact, profile-aware read contract once,
    # instead of rebuilding history/deltas on every GET /api/lite/security.
    elapsed = time.monotonic() - started_at
    if elapsed >= _SECURITY_BACKFILL_PERSIST_SECONDS:
        state = _write_security_state(state)
    return state, _state_file_key()


def default_state() -> dict[str, Any]:
    now = deps.now_utc_iso()
    return {
        "status": "healthy",
        "summary": "No urgent safety issues found.",
        "score": 100,
        "last_run": None,
        "checks_reviewed": 0,
        "items_to_review": 0,
        "critical_issues": [],
        "guidance": policy.GUIDANCE,
        "component_posture": component_posture([]),
        "scan_profile": policy.SCAN_PROFILE_QUICK,
        "coverage_summary": default_coverage_summary(),
        "scan_progress": None,
        "updated_at": now,
    }


def current_state() -> dict[str, Any]:
    started_at = time.monotonic()
    key = _state_file_key()
    cached = _get_current_state_cache(key)
    if cached is not None:
        cached["read_cache"] = {
            "status": "hit",
            "source": "fastapi_memory",
            "ttl_seconds": int(_cache_ttl_for_state(cached)),
        }
        return cached

    state = evidence.read_state()
    if not state:
        fresh = default_state()
        fresh["read_cache"] = {"status": "miss", "source": "default_state", "ttl_seconds": int(_SECURITY_READ_CACHE_SECONDS)}
        return _set_current_state_cache(key, fresh)

    changed = False
    if "guidance" not in state:
        state["guidance"] = policy.GUIDANCE
        changed = True
    if "critical_issues" not in state or not isinstance(state.get("critical_issues"), list):
        state["critical_issues"] = []
        changed = True
    findings = state.get("findings") if isinstance(state.get("findings"), list) else []
    if "component_posture" not in state or not isinstance(state.get("component_posture"), dict):
        state["component_posture"] = component_posture(findings)
        changed = True
    if "scan_profile" not in state:
        state["scan_profile"] = policy.SCAN_PROFILE_QUICK
        changed = True
    if "coverage_summary" not in state or not isinstance(state.get("coverage_summary"), dict):
        last_run_for_coverage = state.get("last_run") if isinstance(state.get("last_run"), dict) else None
        state["coverage_summary"] = _coverage_from_run(last_run_for_coverage)
        changed = True

    last_run = state.get("last_run") if isinstance(state.get("last_run"), dict) else None
    if last_run and not isinstance(state.get("scan_progress"), dict):
        state["scan_progress"] = scan_progress_for_run(last_run)
        changed = True
    elif "scan_progress" not in state:
        state["scan_progress"] = None
        changed = True

    if "history" not in state or not isinstance(state.get("history"), list):
        state["history"] = security_history(
            current_run=last_run,
            current_findings=findings,
            current_evidence_refs=state.get("evidence_refs") or [],
        )
        changed = True
    else:
        # Keep the summary payload bounded without scanning runs/evidence again.
        state["history"] = state["history"][:20]

    if "profile_latest" not in state or not isinstance(state.get("profile_latest"), dict):
        state["profile_latest"] = security_profile_latest(state.get("history") if isinstance(state.get("history"), list) else [])
        changed = True
    if "finding_delta" not in state or not isinstance(state.get("finding_delta"), dict):
        state["finding_delta"] = finding_delta_for_run(last_run, findings)
        changed = True
    if "updated_at" not in state:
        state["updated_at"] = deps.now_utc_iso()
        changed = True

    state, key = _maybe_persist_current_state_backfill(state, started_at=started_at, changed=changed)
    state["read_cache"] = {
        "status": "miss",
        "source": "security_state",
        "ttl_seconds": int(_cache_ttl_for_state(state)),
        "backfill_persisted": bool(changed),
    }
    return _set_current_state_cache(key, state)


def read_run(run_id: str) -> dict[str, Any] | None:
    return evidence.read_run(run_id)


def read_evidence(run_id: str) -> dict[str, Any] | None:
    return evidence.read_evidence_summary(run_id)


def discard_queued_run(run_id: str) -> None:
    if _sqlite_lifecycle_enabled():
        fail_scan_submission(run_id)
        return
    existing = evidence.read_run(run_id)
    if existing and str(existing.get("status") or "") == "queued":
        evidence.delete_run(run_id)
    state = evidence.read_state() or {}
    last_run = state.get("last_run") or {}
    if last_run.get("run_id") == run_id and str(last_run.get("status") or "") == "queued":
        _write_security_state(default_state())


def record_queued_run(command: dict[str, Any]) -> dict[str, Any]:
    run_id = str(command.get("run_id") or command.get("command_id") or new_run_id())
    existing = evidence.read_run(run_id)
    if existing and str(existing.get("status") or "") not in {"", "queued"}:
        return existing
    state = evidence.read_state() or {}
    last_run = state.get("last_run") or {}
    if last_run.get("run_id") == run_id and str(last_run.get("status") or "") not in {"", "queued"}:
        return last_run
    now = deps.now_utc_iso()
    profile = _scan_profile(command)
    app_id = _scan_app_id(command)
    app_label = _app_label(app_id)
    coverage_summary = default_coverage_summary(policy.allowed_scan_root(command.get("scope") or command.get("scan_root")), profile, app_id=app_id)
    run = {
        "run_id": run_id,
        "status": "queued",
        "summary": _profile_copy(profile)["queued"],
        "scan_profile": profile,
        **({"app_id": app_id, "app_label": app_label} if app_id else {}),
        "coverage_summary": coverage_summary,
        "tools": ["lynis", "trivy"],
        "requested_at": command.get("requested_at") or now,
        "started_at": None,
        "completed_at": None,
        "partial_results": False,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
        "tool_results": {},
        "execution_timeline": [],
    }
    run["execution_timeline"] = execution_timeline_for_phase(run, "queued")
    state = build_state(run, [], [], status_override="queued")
    _write_security_state(state)
    _write_run_projection(run)
    return run


def mark_running(command: dict[str, Any]) -> dict[str, Any]:
    run_id = str(command.get("run_id") or command.get("command_id") or new_run_id())
    now = deps.now_utc_iso()
    existing = evidence.read_run(run_id) or {}
    profile = _scan_profile(command)
    app_id = _scan_app_id(command)
    app_label = _app_label(app_id)
    coverage_summary = default_coverage_summary(policy.allowed_scan_root(command.get("scope") or command.get("scan_root")), profile, app_id=app_id)
    run = {
        "run_id": run_id,
        "status": "running",
        "summary": _profile_copy(profile)["running"],
        "scan_profile": profile,
        **({"app_id": app_id, "app_label": app_label} if app_id else {}),
        "coverage_summary": coverage_summary,
        "tools": ["lynis", "trivy"],
        "requested_at": command.get("requested_at") or existing.get("requested_at") or now,
        "started_at": now,
        "completed_at": None,
        "partial_results": False,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
        "tool_results": {},
        "execution_timeline": [],
    }
    run["execution_timeline"] = execution_timeline_for_phase(run, "lynis_running")
    _write_security_state(build_state(run, [], [], status_override="running"))
    _write_run_projection(run)
    return run


def _command_timeout(name: str) -> int:
    return int(policy.TIMEOUTS.get(name, 180))


def _run_command(args: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": policy.redact_text(completed.stdout or ""),
            "stderr": policy.redact_text(completed.stderr or ""),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": policy.redact_text(exc.stdout or ""),
            "stderr": policy.redact_text(exc.stderr or ""),
            "timed_out": True,
            "timeout_seconds": timeout,
        }
    except Exception as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": policy.redact_text(str(exc)), "timed_out": False}


def missing_tool_finding(source: str) -> dict[str, Any]:
    name = source.capitalize()
    return normalize_finding(
        {
            "id": f"{source}-missing-tool",
            "source": source,
            "category": "missing_tool",
            "severity": "medium",
            "component": "Security tools",
            "summary": f"{name} is not available on this device.",
            "recommendation": f"Install {name} to enable {'host posture' if source == 'lynis' else 'vulnerability and dependency'} checks.",
        }
    )


def normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
    now = deps.now_utc_iso()
    severity = policy.normalize_severity(item.get("severity"))
    source = str(item.get("source") or "unknown").lower()
    category = str(item.get("category") or "misconfiguration")
    summary = str(item.get("summary") or "Security finding detected.")
    finding_id = str(item.get("id") or f"{source}-{category}-{uuid.uuid4().hex[:8]}")
    clean = {
        "id": finding_id[:160],
        "source": source,
        "category": category,
        "severity": severity,
        "component": str(item.get("component") or "Pocket Lab Lite"),
        "file": item.get("file"),
        "summary": summary,
        "recommendation": str(item.get("recommendation") or "Review this item and apply the recommended hardening step."),
        "evidence_ref": item.get("evidence_ref"),
        "first_seen": item.get("first_seen") or now,
        "last_seen": item.get("last_seen") or now,
        "status": str(item.get("status") or "open"),
    }
    return policy.redact_value({k: v for k, v in clean.items() if v is not None})


def normalize_lynis_output(result: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if result.get("timed_out"):
        findings.append(
            normalize_finding(
                {
                    "id": "lynis-timeout",
                    "source": "lynis",
                    "category": "host_hardening",
                    "severity": "medium",
                    "component": "Lite API",
                    "summary": "Lynis timed out before all host checks completed.",
                    "recommendation": "Run the safety check again while the device is charging, or increase the Lynis timeout on faster devices.",
                    "evidence_ref": f"security/evidence/{run_id}/lynis-normalized.json",
                }
            )
        )
        return findings

    raw_lines = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}".splitlines()
    seen: set[str] = set()
    for index, line in enumerate(raw_lines):
        text = policy.clean_security_text(line)
        lowered = text.lower()
        if not text or policy.should_skip_lynis_text(text):
            continue
        if not ("warning" in lowered or "suggestion" in lowered or "hardening" in lowered or "[ warning ]" in lowered or "[ suggestion ]" in lowered):
            continue
        dedupe_key = policy.lynis_dedupe_key(text)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        severity = "high" if "warning" in lowered or "[ warning ]" in lowered else "low"
        findings.append(
            normalize_finding(
                {
                    "id": f"lynis-{index}",
                    "source": "lynis",
                    "category": "host_hardening",
                    "severity": severity,
                    "component": _component_for_text(text),
                    "summary": "Host hardening item found.",
                    "recommendation": text[:280],
                    "evidence_ref": f"security/evidence/{run_id}/lynis-normalized.json",
                }
            )
        )
        if len(findings) >= 50:
            break

    if result.get("returncode") not in {0, None} and not findings:
        findings.append(
            normalize_finding(
                {
                    "id": "lynis-nonzero",
                    "source": "lynis",
                    "category": "host_hardening",
                    "severity": "low",
                    "component": "Lite API",
                    "summary": "Lynis completed with a non-zero status.",
                    "recommendation": "Review device compatibility. Lynis can be limited on Android/Termux.",
                    "evidence_ref": f"security/evidence/{run_id}/lynis-normalized.json",
                }
            )
        )
    return findings


def _load_json_text(text: str) -> Any:
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _display_target(target: Any, root: Path | None = None) -> str:
    text = str(target or "").replace("\\", "/")
    if not text:
        return "Security target"
    try:
        candidate = Path(text).expanduser()
        if candidate.is_absolute() and root:
            try:
                return str(candidate.resolve().relative_to(root.resolve())).replace("\\", "/")
            except Exception:
                pass
    except Exception:
        pass
    lowered = text.lower()
    if "photoprism.env" in lowered:
        return "PhotoPrism protected config"
    if "photoprism" in lowered:
        return "PhotoPrism app/config"
    if "proot-distro" in lowered or "rootfs" in lowered:
        return "PROot Ubuntu selected target"
    if text.startswith("/data/data/") or text.startswith("/storage") or text.startswith("/sdcard") or text.startswith("/mnt/sdcard"):
        return Path(text).name or "Local device target"
    return text[:180]


def normalize_trivy_json(payload: Any, run_id: str, *, secret_mode: bool = False, root: Path | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return findings
    for result in payload.get("Results") or []:
        if not isinstance(result, dict):
            continue
        target = str(result.get("Target") or "")
        for vuln in result.get("Vulnerabilities") or []:
            if not isinstance(vuln, dict):
                continue
            fixed = vuln.get("FixedVersion") or vuln.get("FixedVersions") or "a fixed version"
            pkg = vuln.get("PkgName") or vuln.get("PkgID") or "dependency"
            vid = vuln.get("VulnerabilityID") or uuid.uuid4().hex[:8]
            findings.append(
                normalize_finding(
                    {
                        "id": f"trivy-{vid}-{pkg}",
                        "source": "trivy",
                        "category": "dependency_vulnerability",
                        "severity": vuln.get("Severity"),
                        "component": _component_for_text(f"{target} {pkg}"),
                        "file": _display_target(target, root),
                        "summary": "Dependency vulnerability detected.",
                        "recommendation": f"Update {pkg} to {fixed}.",
                        "evidence_ref": f"security/evidence/{run_id}/trivy-normalized.json",
                    }
                )
            )
        for misconfig in result.get("Misconfigurations") or []:
            if not isinstance(misconfig, dict):
                continue
            mid = misconfig.get("ID") or misconfig.get("AVDID") or uuid.uuid4().hex[:8]
            findings.append(
                normalize_finding(
                    {
                        "id": f"trivy-{mid}",
                        "source": "trivy",
                        "category": "misconfiguration",
                        "severity": misconfig.get("Severity"),
                        "component": _component_for_text(f"{target} {misconfig.get('Title') or ''}"),
                        "file": _display_target(target, root),
                        "summary": str(misconfig.get("Title") or "Misconfiguration detected."),
                        "recommendation": str(misconfig.get("Resolution") or "Review and harden this configuration."),
                        "evidence_ref": f"security/evidence/{run_id}/trivy-normalized.json",
                    }
                )
            )
        for secret in result.get("Secrets") or []:
            if not isinstance(secret, dict):
                continue
            sid = secret.get("RuleID") or secret.get("ID") or uuid.uuid4().hex[:8]
            protected = secret_mode and policy.is_protected_runtime_secret(target, root)
            findings.append(
                normalize_finding(
                    {
                        "id": f"trivy-secret-{sid}-{target}",
                        "source": "trivy",
                        "category": "protected_runtime_secret" if protected else "secret_exposure",
                        "severity": "low" if protected else "critical",
                        "component": _component_for_text(target),
                        "file": _display_target(target, root),
                        "summary": "Protected backend runtime secret found." if protected else "Potential secret-like value found.",
                        "recommendation": (
                            "Keep this server-side config locked down, exclude it from frontend assets and normal evidence, and rotate it during planned maintenance if exposure is suspected."
                            if protected
                            else "Move the value to a server-side secret store, rotate it if it was real, and keep it out of frontend assets and normal evidence."
                        ),
                        "evidence_ref": f"security/evidence/{run_id}/trivy-normalized.json",
                        "redacted": True,
                    }
                )
            )
    return findings[:250]


def _component_for_text(text: str) -> str:
    haystack = str(text or "").lower().replace("\\", "/")
    for rule in policy.COMPONENT_RULES:
        if any(match.lower() in haystack for match in rule.matchers):
            return rule.component
    return "Pocket Lab Lite"



def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _estimated_security_seconds(profile: str | None = None) -> int:
    default_value = "1800" if profile == policy.SCAN_PROFILE_FULL else "180"
    env_name = "POCKETLAB_LITE_SECURITY_FULL_ESTIMATED_SECONDS" if profile == policy.SCAN_PROFILE_FULL else "POCKETLAB_LITE_SECURITY_ESTIMATED_SECONDS"
    try:
        configured = int(os.environ.get(env_name, default_value))
    except Exception:
        configured = int(default_value)
    limit = 3600 if profile == policy.SCAN_PROFILE_FULL else 900
    return max(60, min(configured, limit))


def _duration_label(seconds: int | None) -> str:
    if seconds is None:
        return "calculating"
    safe_seconds = max(0, int(seconds))
    if safe_seconds < 10:
        return "less than 10 sec"
    if safe_seconds < 60:
        return f"about {safe_seconds} sec"
    minutes = max(1, round(safe_seconds / 60))
    return f"about {minutes} min"


def scan_progress_for_run(run: dict[str, Any]) -> dict[str, Any] | None:
    status = str(run.get("status") or "").lower()
    if not status:
        return None

    profile = str(run.get("scan_profile") or policy.SCAN_PROFILE_QUICK)
    estimated_total = _estimated_security_seconds(profile)
    started_at = run.get("started_at") or run.get("requested_at")
    started = _parse_iso_timestamp(started_at)
    now = _parse_iso_timestamp(deps.now_utc_iso()) or datetime.now(timezone.utc)
    elapsed = max(0, int((now - started).total_seconds())) if started else 0

    if status == "queued":
        percent = 5
        remaining = estimated_total
        stage = "Waiting for the backend worker"
        step = 1
    elif status == "running":
        percent = max(8, min(95, int(round((elapsed / estimated_total) * 100))))
        remaining = max(0, estimated_total - elapsed)
        stage = "Running Full Local Check" if profile == policy.SCAN_PROFILE_FULL else "Running App Check" if profile == policy.SCAN_PROFILE_APP else "Running Quick Safety Check"
        step = 2
    elif status in {"succeeded", "completed", "degraded", "failed", "cancelled", "canceled"}:
        percent = 100
        remaining = 0
        stage = "Safety check needs review" if status == "failed" else "Safety check complete"
        step = 3
    else:
        percent = 0
        remaining = estimated_total
        stage = "Preparing safety check"
        step = 1

    timeline_progress = execution_timeline_progress(run.get("execution_timeline") or [], status)
    if timeline_progress:
        percent = timeline_progress["percent"]
        step = timeline_progress["step"]
        steps_total = timeline_progress["steps_total"]
        if status not in {"succeeded", "completed", "degraded", "failed", "cancelled", "canceled"}:
            stage = timeline_progress["stage"]
    else:
        steps_total = 3

    return policy.redact_value(
        {
            "status": status,
            "stage": stage,
            "step": step,
            "steps_total": steps_total,
            "started_at": started_at,
            "elapsed_seconds": elapsed,
            "estimated_total_seconds": estimated_total,
            "estimated_remaining_seconds": remaining,
            "estimated_remaining_label": _duration_label(remaining),
            "percent": percent,
            "message": _profile_copy(profile)["progress"],
        }
    )


def _run_time_value(run: dict[str, Any]) -> float:
    for key in ("completed_at", "started_at", "requested_at"):
        parsed = _parse_iso_timestamp(run.get(key))
        if parsed:
            return parsed.timestamp()
    return 0.0


def _finding_key(finding: dict[str, Any]) -> str:
    for key in ("id", "evidence_ref"):
        value = str(finding.get(key) or "").strip()
        if value:
            return value
    return "|".join(
        str(finding.get(key) or "").strip().lower()
        for key in ("source", "category", "component", "file", "summary")
    )


def _finding_delta_item(finding: dict[str, Any]) -> dict[str, Any]:
    return policy.redact_value(
        {
            "id": finding.get("id") or _finding_key(finding),
            "source": finding.get("source"),
            "category": finding.get("category"),
            "severity": policy.normalize_severity(finding.get("severity")),
            "component": finding.get("component"),
            "file": finding.get("file"),
            "summary": finding.get("summary") or "Security finding",
            "recommendation": finding.get("recommendation"),
        }
    )


def _duration_seconds(run: dict[str, Any]) -> int | None:
    started = _parse_iso_timestamp(run.get("started_at") or run.get("requested_at"))
    completed = _parse_iso_timestamp(run.get("completed_at"))
    if not started or not completed:
        return None
    return max(0, int((completed - started).total_seconds()))


def _findings_for_run(run_id: str) -> list[dict[str, Any]]:
    summary = evidence.read_evidence_summary(run_id) or {}
    findings = summary.get("findings")
    return findings if isinstance(findings, list) else []


def _refs_for_run(run: dict[str, Any]) -> list[str]:
    refs = run.get("evidence_refs")
    if isinstance(refs, list):
        return [str(item) for item in refs]
    summary = evidence.read_evidence_summary(str(run.get("run_id") or "")) or {}
    refs = summary.get("evidence_refs")
    return [str(item) for item in refs] if isinstance(refs, list) else []


def _history_entry(run: dict[str, Any], findings: list[dict[str, Any]], evidence_refs: list[str]) -> dict[str, Any]:
    counts = count_findings(findings)
    score = run.get("score")
    if score is None:
        score = policy.score_for_counts(counts)
    try:
        score = int(score)
    except Exception:
        score = policy.score_for_counts(counts)
    status = str(run.get("status") or "unknown").lower()
    return policy.redact_value(
        {
            "run_id": run.get("run_id"),
            "status": status,
            "score": max(0, min(100, score)),
            "started_at": run.get("started_at") or run.get("requested_at"),
            "completed_at": run.get("completed_at"),
            "duration_seconds": _duration_seconds(run),
            "partial_results": bool(run.get("partial_results")),
            "critical_count": counts.get("critical", 0),
            "high_count": counts.get("high", 0),
            "medium_count": counts.get("medium", 0),
            "low_count": counts.get("low", 0),
            "info_count": counts.get("info", 0),
            "items_to_review": len([item for item in findings if policy.normalize_severity(item.get("severity")) != "info"]),
            "evidence_count": len(evidence_refs),
            "evidence_refs": evidence_refs,
            "sbom_saved": any("sbom.cdx.json" in str(ref) for ref in evidence_refs),
            "tools": run.get("tools") or ["lynis", "trivy"],
            "tool_results": run.get("tool_results") if isinstance(run.get("tool_results"), dict) else {},
            "coverage_summary": run.get("coverage_summary") if isinstance(run.get("coverage_summary"), dict) else {},
            "scan_profile": run.get("scan_profile") or policy.SCAN_PROFILE_QUICK,
            "summary": run.get("summary"),
            **({"app_id": run.get("app_id"), "app_label": run.get("app_label")} if run.get("app_id") else {}),
        }
    )


def security_history(
    *,
    current_run: dict[str, Any] | None = None,
    current_findings: list[dict[str, Any]] | None = None,
    current_evidence_refs: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for run in evidence.list_runs(limit=40):
        run_id = str(run.get("run_id") or "")
        if not run_id:
            continue
        entries[run_id] = _history_entry(run, _findings_for_run(run_id), _refs_for_run(run))
    if current_run and current_run.get("run_id"):
        run_id = str(current_run.get("run_id"))
        entries[run_id] = _history_entry(current_run, current_findings or [], current_evidence_refs or _refs_for_run(current_run))
    ordered = sorted(entries.values(), key=lambda item: _run_time_value(item), reverse=True)
    return policy.redact_value(ordered[: max(1, limit)])


def security_profile_latest(history: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in history or security_history(limit=40):
        if not isinstance(item, dict):
            continue
        profile = str(item.get("scan_profile") or policy.SCAN_PROFILE_QUICK).lower()
        if profile not in policy.VALID_SCAN_PROFILES:
            profile = policy.SCAN_PROFILE_QUICK
        current = latest.get(profile)
        if not current or _run_time_value(item) >= _run_time_value(current):
            latest[profile] = item
    return policy.redact_value(latest)


def _previous_completed_run(current_run_id: str | None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    for run in sorted(evidence.list_runs(limit=40), key=_run_time_value, reverse=True):
        run_id = str(run.get("run_id") or "")
        if not run_id or run_id == current_run_id:
            continue
        if str(run.get("status") or "").lower() in {"succeeded", "degraded", "failed"}:
            return run, _findings_for_run(run_id)
    return None, []


def finding_delta_for_run(current_run: dict[str, Any] | None, current_findings: list[dict[str, Any]]) -> dict[str, Any]:
    current_run_id = str((current_run or {}).get("run_id") or "") or None
    previous_run, previous_findings = _previous_completed_run(current_run_id)
    if not previous_run:
        return policy.redact_value(
            {
                "baseline": "first_run",
                "previous_run_id": None,
                "new_count": 0,
                "resolved_count": 0,
                "unchanged_count": len(current_findings),
                "new": [],
                "resolved": [],
                "unchanged": [_finding_delta_item(item) for item in current_findings[:10]],
                "summary": "Baseline established. Future checks will show what changed.",
            }
        )

    current_by_key = {_finding_key(item): item for item in current_findings}
    previous_by_key = {_finding_key(item): item for item in previous_findings}
    new_keys = sorted(set(current_by_key) - set(previous_by_key))
    resolved_keys = sorted(set(previous_by_key) - set(current_by_key))
    unchanged_keys = sorted(set(current_by_key) & set(previous_by_key))
    return policy.redact_value(
        {
            "baseline": "compared",
            "previous_run_id": previous_run.get("run_id"),
            "new_count": len(new_keys),
            "resolved_count": len(resolved_keys),
            "unchanged_count": len(unchanged_keys),
            "new": [_finding_delta_item(current_by_key[key]) for key in new_keys[:10]],
            "resolved": [_finding_delta_item(previous_by_key[key]) for key in resolved_keys[:10]],
            "unchanged": [_finding_delta_item(current_by_key[key]) for key in unchanged_keys[:10]],
            "summary": "No new review items." if not new_keys else f"{len(new_keys)} new review item(s).",
        }
    )


def _timeline_step(key: str, title: str, detail: str, status: str) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "detail": detail,
        "status": status,
    }


def execution_timeline_for_phase(run: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    tool_results = run.get("tool_results") or {}
    profile = str(run.get("scan_profile") or policy.SCAN_PROFILE_QUICK)
    if profile == policy.SCAN_PROFILE_FULL:
        return _full_execution_timeline_for_phase(run, phase)
    if profile == policy.SCAN_PROFILE_APP:
        return _app_execution_timeline_for_phase(run, phase)
    quick_prefix = "Quick " if profile == policy.SCAN_PROFILE_QUICK else ""
    lynis_status = str((tool_results.get("lynis") or {}).get("status") or "").lower()
    trivy_status = str((tool_results.get("trivy") or {}).get("status") or "").lower()
    posture_status = str((tool_results.get("config_posture") or {}).get("status") or "").lower()

    def tool_state(status: str) -> str:
        if status == "completed":
            return "completed"
        if status in {"timed_out", "missing_tool", "partial", "skipped", "skipped_overall_budget"}:
            return "review"
        if status in {"failed", "error"}:
            return "failed"
        return "pending"

    request_status = "completed" if phase in {
        "queued", "lynis_running", "trivy_running", "posture_running", "evidence_saving",
        "completed", "degraded", "failed"
    } else "pending"

    worker_status = "completed" if phase in {
        "lynis_running", "trivy_running", "posture_running", "evidence_saving",
        "completed", "degraded", "failed"
    } else "pending"

    if phase == "lynis_running":
        lynis_step_status = "running"
    elif phase in {"trivy_running", "posture_running", "evidence_saving", "completed", "degraded", "failed"}:
        lynis_step_status = tool_state(lynis_status or "completed")
    else:
        lynis_step_status = "pending"

    if phase == "trivy_running":
        trivy_step_status = "running"
    elif phase in {"posture_running", "evidence_saving", "completed", "degraded", "failed"}:
        trivy_step_status = tool_state(trivy_status or "completed")
    else:
        trivy_step_status = "pending"

    if phase == "posture_running":
        posture_step_status = "running"
    elif phase in {"evidence_saving", "completed", "degraded", "failed"}:
        posture_step_status = tool_state(posture_status or "completed")
    else:
        posture_step_status = "pending"

    if phase == "evidence_saving":
        evidence_status = "running"
    elif phase in {"completed", "degraded", "failed"}:
        evidence_status = "completed"
    else:
        evidence_status = "pending"

    lynis_detail = "Checks host readiness."
    if lynis_status == "completed":
        lynis_detail = "Host readiness checks completed."
    elif lynis_status == "timed_out":
        lynis_detail = "Host readiness partially checked."
    elif lynis_status == "missing_tool":
        lynis_detail = "Lynis is not available on this device."
    elif phase == "lynis_running":
        lynis_detail = "Host readiness is being checked."

    trivy_detail = "Checks Pocket Lab files while skipping photos, backups, caches, and large runtime folders."
    if trivy_status == "completed":
        trivy_detail = "Pocket Lab files, config, secret-like values, and SBOM checks completed."
    elif trivy_status == "partial":
        trivy_detail = "Trivy completed with partial results."
    elif trivy_status == "missing_tool":
        trivy_detail = "Trivy is not available on this device."
    elif phase == "trivy_running":
        trivy_detail = "Pocket Lab files are being checked with Quick Safety exclusions."

    posture_detail = "Checks service/config readiness metadata only."
    if posture_status == "completed":
        posture_detail = "Config posture metadata was checked without dumping raw config."
    elif posture_status in {"partial", "timed_out"}:
        posture_detail = "Config posture metadata was partially checked."
    elif phase == "posture_running":
        posture_detail = "Config posture metadata is being checked."

    evidence_count = len(run.get("evidence_refs") or [])
    evidence_detail = "Sanitized evidence appears after completion."
    if phase == "evidence_saving":
        evidence_detail = "Sanitized evidence is being finalized."
    elif phase in {"completed", "degraded", "failed"}:
        evidence_detail = f"{evidence_count} sanitized file(s) ready." if evidence_count else "Sanitized evidence was finalized."

    return [
        _timeline_step("request_accepted", "Request accepted", "FastAPI accepted the quick safety request.", request_status),
        _timeline_step("worker_picked_up", "Worker picked it up", "The backend worker started the bounded check.", worker_status),
        _timeline_step("lynis_host_check", f"{quick_prefix}host check", lynis_detail, lynis_step_status),
        _timeline_step("trivy_dependency_secret_check", "Pocket Lab files checked", trivy_detail, trivy_step_status),
        _timeline_step("config_posture_check", "Config posture checked", posture_detail, posture_step_status),
        _timeline_step("evidence_saved", "Evidence saved", evidence_detail, evidence_status),
    ]


def execution_timeline_progress(timeline: list[dict[str, Any]], run_status: str) -> dict[str, Any] | None:
    if not isinstance(timeline, list) or not timeline:
        return None

    total = max(1, len(timeline))
    completed_states = {"completed", "review", "failed"}
    units = 0.0
    active_index: int | None = None
    pending_index: int | None = None

    for index, step in enumerate(timeline):
        status = str((step or {}).get("status") or "").lower()
        if status in completed_states:
            units += 1.0
        elif status == "running":
            units += 0.5
            if active_index is None:
                active_index = index
        elif pending_index is None:
            pending_index = index

    status = str(run_status or "").lower()
    all_terminal_steps = all(str((step or {}).get("status") or "").lower() in completed_states for step in timeline)

    if status in {"succeeded", "degraded", "failed"} and all_terminal_steps:
        percent = 100
    else:
        percent = int(round((units / total) * 100))
        if status in {"queued", "running"}:
            percent = max(5, min(95, percent))
        else:
            percent = max(0, min(100, percent))

    current_index = active_index
    if current_index is None:
        current_index = pending_index
    if current_index is None:
        current_index = total - 1

    current = timeline[current_index] if current_index < len(timeline) else {}
    stage = str(current.get("title") or "Security check progress")

    return {
        "percent": percent,
        "step": current_index + 1,
        "steps_total": total,
        "stage": stage,
    }


def _write_intermediate_running_state(
    run: dict[str, Any],
    findings: list[dict[str, Any]],
    evidence_refs: list[str],
) -> None:
    _write_security_state(
        build_state(
            run,
            findings,
            evidence_refs,
            status_override="running",
            summary_override=_profile_copy(str(run.get("scan_profile") or policy.SCAN_PROFILE_QUICK))["running"],
        )
    )
    _write_run_projection(run)


def count_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {severity: 0 for severity in policy.SEVERITIES}
    for finding in findings:
        severity = policy.normalize_severity(finding.get("severity"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def component_posture(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    postures: list[dict[str, Any]] = []
    for rule in policy.COMPONENT_RULES:
        related = [item for item in findings if item.get("component") == rule.component]
        severities = {policy.normalize_severity(item.get("severity")) for item in related}
        if "critical" in severities or "high" in severities:
            status = "needs_attention"
        elif related:
            status = "review"
        else:
            status = "healthy"
        postures.append(
            {
                "component": rule.component,
                "status": status,
                "checks": list(rule.checks),
                "findings": [item.get("id") for item in related[:10]],
            }
        )
    return postures


def build_state(
    run: dict[str, Any],
    findings: list[dict[str, Any]],
    evidence_refs: list[str],
    *,
    status_override: str | None = None,
    summary_override: str | None = None,
) -> dict[str, Any]:
    counts = count_findings(findings)
    score = policy.score_for_counts(counts)
    mapped_status, mapped_summary = policy.status_for_score(score, counts)
    if not status_override and mapped_status == "healthy" and any(item.get("category") == "missing_tool" for item in findings):
        mapped_status = "review"
        mapped_summary = "Needs review"
    status = status_override or mapped_status
    summary = summary_override or ("No urgent safety issues found." if status == "healthy" else mapped_summary)
    if status in {"queued", "running"}:
        summary = summary_override or ("Safety check queued." if status == "queued" else "Safety check running.")
    last_run = {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "tools": run.get("tools") or ["lynis", "trivy"],
        "critical_count": counts.get("critical", 0),
        "high_count": counts.get("high", 0),
        "medium_count": counts.get("medium", 0),
        "low_count": counts.get("low", 0),
        "info_count": counts.get("info", 0),
        "partial_results": bool(run.get("partial_results")),
        "scan_profile": run.get("scan_profile") or policy.SCAN_PROFILE_QUICK,
        **({"app_id": run.get("app_id"), "app_label": run.get("app_label")} if run.get("app_id") else {}),
        "coverage_summary": _coverage_from_run(run),
        "summary": run.get("summary") or summary,
        "score": run.get("score") if run.get("score") is not None else score,
        "updated_at": run.get("updated_at") or run.get("completed_at") or run.get("started_at"),
        "accepted_at": run.get("accepted_at"),
        "requested_at": run.get("requested_at"),
        "checks_reviewed": run.get("checks_reviewed"),
        "items_to_review": run.get("items_to_review"),
        "tool_results": run.get("tool_results") if isinstance(run.get("tool_results"), dict) else {},
        "execution_timeline": run.get("execution_timeline") if isinstance(run.get("execution_timeline"), list) else [],
        "target_statuses": run.get("target_statuses") if isinstance(run.get("target_statuses"), list) else [],
        "evidence_refs": evidence_refs,
        "failure_code": run.get("failure_code"),
        "failure_message": run.get("failure_message"),
    }
    critical = [item for item in findings if policy.normalize_severity(item.get("severity")) == "critical"][:10]
    history = security_history(current_run=run, current_findings=findings, current_evidence_refs=evidence_refs)
    return policy.redact_value(
        {
            "status": status,
            "summary": summary,
            "score": score,
            "last_run": last_run,
            "checks_reviewed": len([name for name in run.get("tools", []) if name in {"lynis", "trivy"}]),
            "items_to_review": len([item for item in findings if policy.normalize_severity(item.get("severity")) != "info"]),
            "critical_issues": critical,
            "guidance": policy.GUIDANCE,
            "component_posture": component_posture(findings),
            "scan_profile": run.get("scan_profile") or policy.SCAN_PROFILE_QUICK,
            **({"app_id": run.get("app_id"), "app_label": run.get("app_label")} if run.get("app_id") else {}),
            "coverage_summary": _coverage_from_run(run),
            "findings": findings[:100],
            "evidence_refs": evidence_refs,
            "history": history,
            "profile_latest": security_profile_latest(history),
            "finding_delta": finding_delta_for_run(run, findings),
            "execution_timeline": run.get("execution_timeline") or execution_timeline_for_phase(
                run,
                "completed" if str(run.get("status") or "").lower() == "succeeded"
                else "degraded" if str(run.get("status") or "").lower() == "degraded"
                else "failed" if str(run.get("status") or "").lower() == "failed"
                else "lynis_running" if str(run.get("status") or "").lower() == "running"
                else "queued"
            ),
            "scan_progress": scan_progress_for_run(run),
            "updated_at": deps.now_utc_iso(),
        }
    )


def _trivy_base_args(root: Path) -> list[str]:
    args = ["trivy", "fs"]
    args.extend(policy.trivy_skip_args(root))
    args.append(str(root))
    return args


def _write_sbom(run_id: str, trivy: str, root: Path) -> str | None:
    out = evidence.evidence_dir(run_id) / "sbom.cdx.json"
    args = [trivy, "fs", "--format", "cyclonedx", "--output", str(out)]
    args.extend(policy.trivy_skip_args(root))
    args.append(str(root))
    result = _run_command(args, cwd=root, timeout=_command_timeout("trivy_sbom"))
    if result.get("ok") and out.exists():
        existing = evidence.read_json(out, {})
        evidence.write_json(out, existing if existing else {"status": "created"})
        return f"security/evidence/{run_id}/sbom.cdx.json"
    return None


def _safe_candidate(root: Path, value: str) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    home = Path.home()
    expanded = raw.replace("$HOME", str(home)).replace("~", str(home), 1)
    candidate = Path(expanded).expanduser()
    if not candidate.is_absolute():
        candidate = (root / expanded).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
    return candidate


def _safe_presence(root: Path, label: str, candidates: list[str]) -> dict[str, Any]:
    checked: list[str] = []
    for value in candidates:
        candidate = _safe_candidate(root, value)
        if not candidate:
            continue
        checked.append(str(candidate).replace(str(Path.home()), "~"))
        try:
            if candidate.exists():
                return {"label": label, "status": "checked", "present": True, "kind": "directory" if candidate.is_dir() else "file", "source": "safe_path_discovery"}
        except OSError:
            continue
    return {"label": label, "status": "partial", "present": False, "kind": "missing", "checked_candidates": len(checked)}


def _proc_cmdline(pid: str | int | None) -> str:
    try:
        raw = Path(f"/proc/{int(pid)}/cmdline").read_bytes()
    except Exception:
        return ""
    return policy.redact_text(raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")).strip()


def _pm2_process_cmdline(process_name: str) -> str:
    pm2 = shutil.which("pm2")
    if not pm2:
        return ""
    pid_result = _run_command([pm2, "pid", process_name], cwd=policy.repo_root(), timeout=5)
    pid = str(pid_result.get("stdout") or "").strip().splitlines()[-1:]
    return _proc_cmdline(pid[0]) if pid else ""


def _discover_nats_config(root: Path) -> dict[str, Any]:
    candidates = [
        "nats/nats-server.conf",
        "pocket-lab-final-structure/nats/nats-server.conf",
        "$HOME/.pocket_lab/nats/nats-server.conf",
    ]
    cmdline = _pm2_process_cmdline("pocket-nats")
    parts = cmdline.split()
    for index, part in enumerate(parts):
        if part in {"-c", "--config"} and index + 1 < len(parts):
            candidates.insert(0, parts[index + 1])
    result = _safe_presence(root, "NATS config posture", candidates)
    if result.get("present"):
        result["summary"] = "NATS config metadata was discovered safely without exposing credentials."
    elif cmdline:
        result["status"] = "partial"
        result["summary"] = "NATS is running, but the config file could not be safely read from discovered metadata."
    return result


def _pm2_summary(root: Path) -> dict[str, Any]:
    pm2 = shutil.which("pm2")
    if not pm2:
        return {"label": "Services summary", "status": "partial", "available": False, "summary": "Service manager metadata is not available."}
    result = _run_command([pm2, "jlist"], cwd=root, timeout=5)
    if result.get("timed_out"):
        return {"label": "Services summary", "status": "timed_out", "available": True, "summary": "Service summary timed out."}
    payload = _load_json_text(result.get("stdout") or "")
    if not isinstance(payload, list):
        return {"label": "Services summary", "status": "partial", "available": True, "summary": "Service summary was not readable."}
    allowed_names = {
        "pocketlab-app-photoprism",
        "pocket-telemetry",
        "pocket-nats",
        "pocket-worker",
        "pocket-node-agent",
        "pocket-api",
        "caddy-proxy",
        "pocketlab-core-supervisor",
    }
    processes = []
    for item in payload[:25]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name not in allowed_names and not name.startswith("pocketlab-agent"):
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        processes.append({
            "name": name,
            "status": str(env.get("status") or item.get("status") or "unknown"),
        })
    online = len([item for item in processes if item.get("status") == "online"])
    return {
        "label": "Services summary",
        "status": "checked" if processes else "partial",
        "available": True,
        "online_count": online,
        "process_count": len(processes),
        "processes": processes[:12],
    }


def _photoprism_route_health() -> dict[str, Any]:
    if str(os.environ.get("POCKETLAB_LITE_SECURITY_CHECK_PHOTOPRISM_ROUTE", "1")).lower() in {"0", "false", "no"}:
        return {"label": "PhotoPrism route health", "status": "skipped", "summary": "Route health probe disabled."}
    request = urllib.request.Request("http://127.0.0.1:8443/apps/photoprism/api/v1/status", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:  # nosec B310 - local same-origin health metadata only
            status_code = int(getattr(response, "status", 0) or 0)
            body = response.read(2048).decode("utf-8", errors="replace")
            payload = _load_json_text(body)
            operational = isinstance(payload, dict) and str(payload.get("status") or "").lower() == "operational"
            return {
                "label": "PhotoPrism route health",
                "status": "checked" if 200 <= status_code < 300 else "partial",
                "route_ready": operational,
                "summary": "PhotoPrism route metadata is operational." if operational else "PhotoPrism route metadata needs review.",
            }
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"label": "PhotoPrism route health", "status": "partial", "route_ready": False, "summary": "PhotoPrism route metadata was not reachable quickly."}


def runtime_config_posture(root: Path) -> dict[str, Any]:
    checks = [
        _pm2_summary(root),
        _safe_presence(root, "Caddy config posture", ["caddy/Caddyfile", "Caddyfile"]),
        _discover_nats_config(root),
        {"label": "Security evidence state", "status": "checked", "present": evidence.security_root().exists(), "summary": "Security evidence directory metadata is available."},
        _photoprism_route_health(),
    ]
    status_values = {str(item.get("status") or "") for item in checks}
    if "timed_out" in status_values:
        status = "timed_out"
    elif "partial" in status_values:
        status = "partial"
    else:
        status = "completed"
    return policy.redact_value({"status": status, "checks": checks})


def _target_label(value: str) -> str:
    text = str(value or "").strip().replace("_", " ")
    return text[:1].upper() + text[1:] if text else "Security target"


def build_coverage_summary(
    plan: dict[str, Any],
    tool_results: dict[str, Any],
    posture: dict[str, Any] | None = None,
    target_statuses: list[dict[str, Any]] | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    profile = str(plan.get("profile") or policy.SCAN_PROFILE_QUICK)
    target_statuses = target_statuses or []
    partial_targets: list[str] = []
    timed_out_targets: list[str] = []
    failed_targets: list[str] = []
    checked_targets: list[str] = []
    missing_targets: list[str] = []
    tool_status: dict[str, str] = {}

    for tool, result in (tool_results or {}).items():
        if not isinstance(result, dict):
            continue
        status = str(result.get("status") or "unknown")
        tool_status[str(tool)] = status
        label = str(result.get("label") or result.get("target_label") or tool)
        if status in {"completed", "checked"}:
            checked_targets.append(label)
        if status in {"partial", "missing_tool", "skipped_overall_budget", "review"}:
            partial_targets.append(label)
        if status in {"timed_out"}:
            timed_out_targets.append(label)
        if status in {"failed", "error"}:
            failed_targets.append(label)

    if isinstance(posture, dict):
        posture_status = str(posture.get("status") or "")
        if posture_status in {"completed", "checked"}:
            checked_targets.append("Runtime config")
        if posture_status in {"partial"}:
            partial_targets.append("Runtime config")
        if posture_status in {"timed_out"}:
            timed_out_targets.append("Runtime config")

    safe_target_statuses: list[dict[str, Any]] = []
    for item in target_statuses:
        if not isinstance(item, dict):
            continue
        label = str(item.get("target_label") or item.get("label") or _target_label(item.get("target_id")))
        status = str(item.get("status") or "unknown")
        if status in {"checked", "completed"}:
            checked_targets.append(label)
        elif status in {"partial", "review"}:
            partial_targets.append(label)
        elif status == "timed_out":
            timed_out_targets.append(label)
        elif status == "missing":
            missing_targets.append(label)
        elif status in {"failed", "error"}:
            failed_targets.append(label)
        safe_target_statuses.append(policy.redact_value({
            "target_id": item.get("target_id"),
            "target_label": label,
            "tool": item.get("tool"),
            "status": status,
            "elapsed_seconds": item.get("elapsed_seconds"),
            "finding_count": item.get("finding_count", 0),
            "evidence_ref": item.get("evidence_ref"),
            "summary": item.get("summary"),
        }))

    for item in plan.get("selected_targets") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or _target_label(item.get("target_id")))
        if item.get("present") is False and item.get("optional"):
            missing_targets.append(label)

    source_targets = [
        {key: item.get(key) for key in ("target_id", "label", "relative", "present", "kind", "optional")}
        for item in plan.get("source_targets", [])
    ]
    base_checked = plan.get("checked_targets", [])
    merged_checked = sorted(set([*map(str, base_checked), *checked_targets]))
    return policy.redact_value({
        "profile": profile,
        **({"app_id": plan.get("app_id"), "app_label": plan.get("app_label")} if plan.get("app_id") else {}),
        "checked_targets": merged_checked,
        "skipped_targets": plan.get("skipped_targets", []),
        "missing_targets": sorted(set(missing_targets)),
        "partial_targets": sorted(set(partial_targets)),
        "timed_out_targets": sorted(set(timed_out_targets)),
        "failed_targets": sorted(set(failed_targets)),
        "excluded_groups": plan.get("excluded_groups", []),
        "tool_status": tool_status,
        "target_statuses": safe_target_statuses,
        "evidence_files_written": [str(item) for item in (evidence_refs or [])],
        "posture_checks": (posture or {}).get("checks", []) if isinstance(posture, dict) else [],
        "source_targets": source_targets,
        "scanner_quality": {
            "profile": profile,
            "backend_owned": True,
            "target_aware": profile in {policy.SCAN_PROFILE_FULL, policy.SCAN_PROFILE_APP},
            "bounded_timeouts": True,
            "sanitized_evidence": True,
            "raw_scanner_output_hidden": True,
            "private_media_skipped": True,
            "browser_execution": False,
        },
    })


def _run_quick_security_scan(command: dict[str, Any]) -> dict[str, Any]:
    run = mark_running(command)
    run_id = str(run["run_id"])
    started = time.monotonic()
    root = policy.allowed_scan_root(command.get("scope") or command.get("scan_root"))
    plan = policy.build_quick_scan_plan(root)
    findings: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}
    evidence_refs: list[str] = []
    partial = False
    posture: dict[str, Any] | None = None
    run["scan_profile"] = policy.SCAN_PROFILE_QUICK
    run["coverage_summary"] = build_coverage_summary(plan, tool_results)

    lynis = shutil.which("lynis")
    if not lynis:
        missing = missing_tool_finding("lynis")
        missing["evidence_ref"] = f"security/evidence/{run_id}/lynis-normalized.json"
        findings.append(missing)
        tool_results["lynis"] = {"status": "missing_tool", "available": False}
    else:
        result = _run_command([lynis, "audit", "system", "--quick", "--no-colors", "--quiet"], cwd=root, timeout=_command_timeout("lynis"))
        normalized = normalize_lynis_output(result, run_id)
        findings.extend(normalized)
        partial = partial or bool(result.get("timed_out"))
        tool_results["lynis"] = {
            "status": "completed" if not result.get("timed_out") else "timed_out",
            "available": True,
            "returncode": result.get("returncode"),
            "finding_count": len(normalized),
        }
    evidence_refs.append(evidence.write_evidence(run_id, "lynis-normalized.json", {"tool": "lynis", "findings": [f for f in findings if f.get("source") == "lynis"]}))
    run["tool_results"] = tool_results
    run["execution_timeline"] = execution_timeline_for_phase(run, "trivy_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    if time.monotonic() - started > policy.TIMEOUTS["overall"]:
        partial = True
        tool_results["trivy"] = {"status": "skipped_overall_budget", "available": bool(shutil.which("trivy")), "finding_count": 0, "sbom_saved": False}
    else:
        trivy = shutil.which("trivy")
        if not trivy:
            missing = missing_tool_finding("trivy")
            missing["evidence_ref"] = f"security/evidence/{run_id}/trivy-normalized.json"
            findings.append(missing)
            tool_results["trivy"] = {"status": "missing_tool", "available": False}
        else:
            vuln_args = [trivy, "fs", "--format", "json", "--scanners", "vuln,misconfig"]
            vuln_args.extend(policy.trivy_skip_args(root))
            vuln_args.append(str(root))
            vuln_result = _run_command(vuln_args, cwd=root, timeout=_command_timeout("trivy_vuln_misconfig"))
            vuln_findings = normalize_trivy_json(_load_json_text(vuln_result.get("stdout") or ""), run_id, root=root)
            findings.extend(vuln_findings)

            secret_args = [trivy, "fs", "--format", "json", "--scanners", "secret"]
            secret_args.extend(policy.trivy_skip_args(root))
            secret_args.append(str(root))
            secret_result = _run_command(secret_args, cwd=root, timeout=_command_timeout("trivy_secret"))
            secret_findings = normalize_trivy_json(_load_json_text(secret_result.get("stdout") or ""), run_id, secret_mode=True, root=root)
            findings.extend(secret_findings)
            trivy_partial = bool(vuln_result.get("timed_out") or secret_result.get("timed_out"))
            partial = partial or trivy_partial
            sbom_ref = _write_sbom(run_id, trivy, root)
            if sbom_ref:
                evidence_refs.append(sbom_ref)
            tool_results["trivy"] = {
                "status": "completed" if not trivy_partial else "partial",
                "available": True,
                "vuln_returncode": vuln_result.get("returncode"),
                "secret_returncode": secret_result.get("returncode"),
                "finding_count": len(vuln_findings) + len(secret_findings),
                "sbom_saved": bool(sbom_ref),
            }

    evidence_refs.append(evidence.write_evidence(run_id, "trivy-normalized.json", {"tool": "trivy", "profile": policy.SCAN_PROFILE_QUICK, "findings": [f for f in findings if f.get("source") == "trivy"]}))
    run["tool_results"] = tool_results
    run["execution_timeline"] = execution_timeline_for_phase(run, "posture_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    posture = runtime_config_posture(root)
    tool_results["config_posture"] = {
        "status": posture.get("status") or "completed",
        "available": True,
        "finding_count": 0,
    }
    run["tool_results"] = tool_results
    run["coverage_summary"] = build_coverage_summary(plan, tool_results, posture)
    coverage_ref = evidence.write_evidence(run_id, "coverage-summary.json", run["coverage_summary"])
    if coverage_ref not in evidence_refs:
        evidence_refs.append(coverage_ref)
    run["execution_timeline"] = execution_timeline_for_phase(run, "evidence_saving")
    _write_intermediate_running_state(run, findings, evidence_refs)

    counts = count_findings(findings)
    final_status = "degraded" if partial else "succeeded"
    run.update(
        {
            "status": final_status,
            "summary": "Safety check timed out before all checks completed." if partial else "Safety check completed.",
            "completed_at": deps.now_utc_iso(),
            "partial_results": partial,
            "tool_results": tool_results,
            "coverage_summary": build_coverage_summary(plan, tool_results, posture),
            "critical_count": counts.get("critical", 0),
            "high_count": counts.get("high", 0),
            "medium_count": counts.get("medium", 0),
            "low_count": counts.get("low", 0),
            "info_count": counts.get("info", 0),
            "evidence_refs": evidence_refs,
        }
    )
    run["execution_timeline"] = execution_timeline_for_phase(run, "degraded" if partial else "completed")
    state = build_state(
        run,
        findings,
        evidence_refs,
        status_override="degraded" if partial else None,
        summary_override="Safety check timed out before all checks completed." if partial else None,
    )
    summary_ref = evidence.write_evidence(
        run_id,
        "summary.json",
        {
            "run": run,
            "score": state.get("score"),
            "status": state.get("status"),
            "summary": state.get("summary"),
            "counts": counts,
            "findings": findings,
            "component_posture": state.get("component_posture"),
            "coverage_summary": state.get("coverage_summary"),
            "scan_profile": state.get("scan_profile"),
            "evidence_refs": evidence_refs,
        },
    )
    if summary_ref not in evidence_refs:
        evidence_refs.insert(0, summary_ref)
    run["evidence_refs"] = evidence_refs
    state["evidence_refs"] = evidence_refs
    _write_security_state(state)
    _write_run_projection(run)
    return {"run": run, "state": state, "findings": findings, "evidence_refs": evidence_refs}



def _full_target_status(target_id: str, target_label: str, tool: str, status: str, *, elapsed_seconds: int | None = None, finding_count: int = 0, evidence_ref: str | None = None, summary: str | None = None) -> dict[str, Any]:
    return policy.redact_value({
        "target_id": target_id,
        "target_label": target_label,
        "tool": tool,
        "status": status,
        "elapsed_seconds": elapsed_seconds,
        "finding_count": finding_count,
        "evidence_ref": evidence_ref,
        "summary": summary or f"{target_label} {status}.",
    })


def _full_target_current_status(run: dict[str, Any], target_id: str, default: str = "pending") -> str:
    for item in run.get("target_statuses") or []:
        if str((item or {}).get("target_id") or "") == target_id:
            status = str((item or {}).get("status") or default)
            if status in {"checked", "completed"}:
                return "completed"
            if status in {"partial", "missing", "timed_out", "review"}:
                return "review"
            if status in {"failed", "error"}:
                return "failed"
    return default


def _full_execution_timeline_for_phase(run: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    terminal_phases = {"completed", "degraded", "failed"}
    phase_order = [
        "queued",
        "lynis_running",
        "pocketlab_running",
        "runtime_running",
        "proot_running",
        "photoprism_running",
        "backup_running",
        "evidence_saving",
        "completed",
    ]
    try:
        current_index = phase_order.index("completed" if phase in terminal_phases else phase)
    except ValueError:
        current_index = 0

    def status_for(step_phase: str, target_id: str | None = None) -> str:
        if phase == step_phase:
            return "running"
        try:
            step_index = phase_order.index(step_phase)
        except ValueError:
            step_index = current_index + 1
        if phase in terminal_phases or current_index > step_index:
            return _full_target_current_status(run, target_id, "completed") if target_id else "completed"
        return "pending"

    evidence_status = "running" if phase == "evidence_saving" else "completed" if phase in terminal_phases else "pending"
    return [
        _timeline_step("request_accepted", "Request accepted", "FastAPI accepted the explicit Full Local Check request.", "completed" if current_index >= 0 else "pending"),
        _timeline_step("worker_picked_up", "Worker picked it up", "The backend worker started the deeper local check.", "completed" if current_index >= 1 or phase in terminal_phases else "pending"),
        _timeline_step("host_posture", "Host posture checked", "Lynis checked Android/Termux host posture, with Android limitations marked as review when needed.", status_for("lynis_running", "termux_host")),
        _timeline_step("pocketlab_files", "Pocket Lab files checked", "Pocket Lab source, runtime config, scripts, contracts, operations, and runbooks were checked with exclusions.", status_for("pocketlab_running", "pocketlab_source")),
        _timeline_step("runtime_config", "Runtime config checked", "PM2, Caddy, NATS, PhotoPrism route, evidence, and recovery metadata were checked without dumping raw config.", status_for("runtime_running", "runtime_config")),
        _timeline_step("proot_ubuntu", "PROot Ubuntu checked", "Selected PROot Ubuntu metadata/runtime areas were checked if present.", status_for("proot_running", "proot_ubuntu")),
        _timeline_step("photoprism", "PhotoPrism checked", "PhotoPrism app/config/runtime metadata was checked while media folders stayed skipped.", status_for("photoprism_running", "photoprism")),
        _timeline_step("backup_metadata", "Backup metadata checked", "Backup manifests, receipts, restore preview, and restore-run metadata summaries were checked without scanning payloads.", status_for("backup_running", "backup_metadata")),
        _timeline_step("evidence_saved", "Evidence saved", "Sanitized target-level evidence and coverage summary were saved.", evidence_status),
    ]



def _app_execution_timeline_for_phase(run: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    terminal_phases = {"completed", "degraded", "failed"}
    phase_order = [
        "queued",
        "route_running",
        "app_files_running",
        "settings_running",
        "backup_metadata_running",
        "action_state_running",
        "evidence_saving",
        "completed",
    ]
    try:
        current_index = phase_order.index("completed" if phase in terminal_phases else phase)
    except ValueError:
        current_index = 0

    def status_for(step_phase: str, target_id: str | None = None) -> str:
        if phase == step_phase:
            return "running"
        try:
            step_index = phase_order.index(step_phase)
        except ValueError:
            step_index = current_index + 1
        if phase in terminal_phases or current_index > step_index:
            return _full_target_current_status(run, target_id, "completed") if target_id else "completed"
        return "pending"

    evidence_status = "running" if phase == "evidence_saving" else "completed" if phase in terminal_phases else "pending"
    return [
        _timeline_step("request_accepted", "Request accepted", "FastAPI accepted the explicit App Check request.", "completed" if current_index >= 0 else "pending"),
        _timeline_step("worker_picked_up", "Worker picked it up", "The backend worker started the app check.", "completed" if current_index >= 1 or phase in terminal_phases else "pending"),
        _timeline_step("app_route", "App route checked", "PhotoPrism same-origin route health was checked without exposing route internals.", status_for("route_running", "photoprism_route")),
        _timeline_step("app_files", "App files checked", "Selected PhotoPrism app files were checked with media folders skipped.", status_for("app_files_running", "photoprism_app_files")),
        _timeline_step("app_settings", "App settings checked", "PhotoPrism settings were checked with runtime secrets protected.", status_for("settings_running", "photoprism_settings")),
        _timeline_step("app_backup_metadata", "App backup metadata checked", "PhotoPrism backup metadata was summarized without scanning payloads.", status_for("backup_metadata_running", "photoprism_backup_metadata")),
        _timeline_step("app_action_state", "App action state checked", "PhotoPrism safe action readiness was summarized without loading backend-only evidence.", status_for("action_state_running", "photoprism_action_state")),
        _timeline_step("evidence_saved", "Evidence saved", "Sanitized app target evidence and coverage summary were saved.", evidence_status),
    ]


def _app_route_posture(app_id: str) -> dict[str, Any]:
    try:
        target = policy.app_check_target(app_id)
    except ValueError:
        return {"status": "missing", "summary": "App Check target is not registered."}
    route = str(target.get("route") or "/apps/photoprism/")
    health_path = str(target.get("health_path") or "/apps/photoprism/api/v1/status")
    health = _photoprism_route_health() if app_id == "photoprism" else {"status": "missing", "route_ready": False}
    route_ready = bool(health.get("route_ready"))
    return policy.redact_value({
        "app_id": target.get("app_id"),
        "app_label": target.get("app_label"),
        "status": "checked" if route_ready else "partial",
        "route_label": route,
        "health_endpoint_label": health_path,
        "expected_health": target.get("expected_health"),
        "route_ready": route_ready,
        "execution_owner": "backend worker and app runtime",
        "summary": "PhotoPrism route is operational." if route_ready else "PhotoPrism route needs review or was not reachable quickly.",
    })


def _photoprism_action_state_summary() -> dict[str, Any]:
    actions = ["check_app", "repair_app", "backup_app", "preview_restore", "update_app"]
    return policy.redact_value({
        "status": "checked",
        "app_id": "photoprism",
        "app_label": "PhotoPrism",
        "checked_actions": actions,
        "summary": "PhotoPrism action readiness was summarized without loading raw evidence.",
        "what_did_not_happen": ["No app settings were changed.", "No photo files were scanned.", "No backend-only evidence was loaded into the UI."],
    })


def _photoprism_backup_metadata_summary(root: Path) -> dict[str, Any]:
    summary = _backup_metadata_summary(root)
    return policy.redact_value({
        **summary,
        "app_id": "photoprism",
        "app_label": "PhotoPrism",
        "skipped": ["backup payloads", "restic repository contents", "restore checkpoints", "PhotoPrism database files"],
    })


def _overall_budget_exhausted(started: float, profile: str) -> bool:
    key = "full_overall" if profile == policy.SCAN_PROFILE_FULL else "app_overall" if profile == policy.SCAN_PROFILE_APP else "overall"
    return time.monotonic() - started > policy.TIMEOUTS[key]


def _trivy_timeout_key(profile: str, scanners: str) -> str:
    if profile == policy.SCAN_PROFILE_FULL:
        if scanners == "secret":
            return "full_trivy_secret"
        return "full_trivy_vuln_misconfig"
    if profile == policy.SCAN_PROFILE_APP:
        if scanners == "secret":
            return "app_trivy_secret"
        return "app_trivy_vuln_misconfig"
    if scanners == "secret":
        return "trivy_secret"
    return "trivy_vuln_misconfig"


def _write_target_json(run_id: str, filename: str, payload: dict[str, Any]) -> str:
    return evidence.write_evidence(run_id, filename, policy.redact_value(payload))


def _run_trivy_target_job(
    *,
    trivy: str | None,
    run_id: str,
    root: Path,
    target_path: Path,
    target_id: str,
    target_label: str,
    scanners: str,
    profile: str,
    secret_mode: bool = False,
    evidence_name: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evidence_name = evidence_name or f"target-{target_id}-trivy-{scanners.replace(',', '-')}.json"
    if not target_path.exists():
        ref = _write_target_json(run_id, evidence_name, {
            "target_id": target_id,
            "target_label": target_label,
            "tool": "trivy",
            "scanners": scanners,
            "status": "missing",
            "summary": f"{target_label} was not present on this device.",
        })
        return [], _full_target_status(target_id, target_label, "trivy", "missing", evidence_ref=ref, summary=f"{target_label} was not present on this device.")
    if not trivy:
        ref = _write_target_json(run_id, evidence_name, {
            "target_id": target_id,
            "target_label": target_label,
            "tool": "trivy",
            "scanners": scanners,
            "status": "missing_tool",
            "summary": "Trivy is not available on this device.",
        })
        return [], _full_target_status(target_id, target_label, "trivy", "partial", evidence_ref=ref, summary="Trivy is not available on this device.")

    started = time.monotonic()
    args = [trivy, "fs", "--format", "json", "--scanners", scanners]
    args.extend(policy.trivy_skip_args_for_profile(target_path, profile))
    args.append(str(target_path))
    result = _run_command(args, cwd=root, timeout=_command_timeout(_trivy_timeout_key(profile, scanners)))
    payload = _load_json_text(result.get("stdout") or "")
    findings = normalize_trivy_json(payload, run_id, secret_mode=secret_mode, root=target_path if target_path.is_dir() else target_path.parent)
    elapsed = max(0, int(time.monotonic() - started))
    status = "timed_out" if result.get("timed_out") else "checked"
    if result.get("returncode") not in {0, None} and not findings and not result.get("timed_out"):
        status = "partial"
    ref = _write_target_json(run_id, evidence_name, {
        "target_id": target_id,
        "target_label": target_label,
        "tool": "trivy",
        "scanners": scanners,
        "status": status,
        "elapsed_seconds": elapsed,
        "finding_count": len(findings),
        "findings": findings,
        "returncode": result.get("returncode"),
        "timed_out": bool(result.get("timed_out")),
    })
    for finding in findings:
        finding["evidence_ref"] = ref
    summary = f"{target_label} checked with Trivy {scanners}." if status == "checked" else f"{target_label} {status} during Trivy {scanners}."
    return findings, _full_target_status(target_id, target_label, "trivy", status, elapsed_seconds=elapsed, finding_count=len(findings), evidence_ref=ref, summary=summary)


def _write_target_sbom(trivy: str | None, run_id: str, root: Path, target_path: Path, target_id: str, target_label: str, profile: str) -> dict[str, Any]:
    filename = f"target-{target_id}-sbom.cdx.json"
    if not target_path.exists():
        ref = _write_target_json(run_id, filename, {"target_id": target_id, "target_label": target_label, "tool": "trivy", "status": "missing"})
        return _full_target_status(target_id, target_label, "sbom", "missing", evidence_ref=ref, summary=f"{target_label} was not present for SBOM.")
    if not trivy:
        ref = _write_target_json(run_id, filename, {"target_id": target_id, "target_label": target_label, "tool": "trivy", "status": "missing_tool"})
        return _full_target_status(target_id, target_label, "sbom", "partial", evidence_ref=ref, summary="Trivy is not available for SBOM.")
    out = evidence.evidence_dir(run_id) / filename
    args = [trivy, "fs", "--format", "cyclonedx", "--output", str(out)]
    args.extend(policy.trivy_skip_args_for_profile(target_path, profile))
    args.append(str(target_path))
    started = time.monotonic()
    result = _run_command(args, cwd=root, timeout=_command_timeout("full_trivy_sbom" if profile == policy.SCAN_PROFILE_FULL else "app_trivy_sbom" if profile == policy.SCAN_PROFILE_APP else "trivy_sbom"))
    elapsed = max(0, int(time.monotonic() - started))
    if result.get("ok") and out.exists():
        existing = evidence.read_json(out, {})
        evidence.write_json(out, existing if existing else {"status": "created", "target_id": target_id, "target_label": target_label})
        return _full_target_status(target_id, target_label, "sbom", "checked", elapsed_seconds=elapsed, evidence_ref=f"security/evidence/{run_id}/{filename}", summary=f"{target_label} SBOM saved.")
    ref = _write_target_json(run_id, filename, {"target_id": target_id, "target_label": target_label, "tool": "trivy", "status": "timed_out" if result.get("timed_out") else "partial"})
    return _full_target_status(target_id, target_label, "sbom", "timed_out" if result.get("timed_out") else "partial", elapsed_seconds=elapsed, evidence_ref=ref, summary=f"{target_label} SBOM was not fully saved.")


def _first_existing(paths: list[Path]) -> Path | None:
    for candidate in paths:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def _photoprism_proot_targets(rootfs: Path | None) -> list[tuple[Path, str, bool, str, str]]:
    if not rootfs:
        return []
    app_path = rootfs / "opt/photoprism"
    binary_path = rootfs / "usr/local/bin/photoprism"
    targets = [(app_path, "vuln,misconfig", False, "target-photoprism-trivy.json", "PhotoPrism app files")]
    if binary_path.exists():
        targets.append((binary_path, "vuln,misconfig", False, "target-photoprism-binary-trivy.json", "PhotoPrism app binary"))
    elif app_path.exists():
        # Keep the binary as optional metadata instead of marking the whole app missing when
        # PhotoPrism is running from the app tree or through PROot launch metadata.
        targets.append((app_path, "vuln,misconfig", False, "target-photoprism-binary-trivy.json", "PhotoPrism app binary metadata"))
    return targets


def _backup_metadata_summary(root: Path) -> dict[str, Any]:
    candidates = policy.backup_metadata_candidates(root)
    present = []
    for candidate in candidates:
        try:
            if candidate.exists():
                present.append(candidate)
        except OSError:
            continue
    return policy.redact_value({
        "status": "checked" if present else "missing",
        "checked_candidates": len(candidates),
        "present_count": len(present),
        "summary": "Backup metadata summary is available." if present else "Backup metadata was not found on this device.",
        "present_labels": [str(item).replace(str(Path.home()), "~") for item in present[:6]],
        "skipped": ["backup payloads", "restic repository contents", "restore checkpoints", "large restore-run content"],
    })


def _run_full_security_scan(command: dict[str, Any]) -> dict[str, Any]:
    run = mark_running(command)
    run_id = str(run["run_id"])
    started = time.monotonic()
    root = policy.allowed_scan_root(command.get("scope") or command.get("scan_root"))
    plan = policy.build_full_scan_plan(root)
    findings: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}
    target_statuses: list[dict[str, Any]] = []
    evidence_refs: list[str] = []
    partial = False
    posture: dict[str, Any] | None = None
    run["scan_profile"] = policy.SCAN_PROFILE_FULL
    run["target_statuses"] = target_statuses
    run["coverage_summary"] = build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)

    lynis = shutil.which("lynis")
    if not lynis:
        missing = missing_tool_finding("lynis")
        missing["evidence_ref"] = f"security/evidence/{run_id}/lynis-normalized.json"
        findings.append(missing)
        tool_results["lynis"] = {"status": "missing_tool", "available": False, "label": "Termux host"}
        target_statuses.append(_full_target_status("termux_host", "Termux host", "lynis", "partial", finding_count=1, summary="Lynis is not available on this device."))
    else:
        lynis_started = time.monotonic()
        result = _run_command([lynis, "audit", "system", "--no-colors", "--quiet"], cwd=root, timeout=_command_timeout("full_lynis"))
        normalized = normalize_lynis_output(result, run_id)
        findings.extend(normalized)
        lynis_status = "timed_out" if result.get("timed_out") else "checked"
        partial = partial or bool(result.get("timed_out"))
        tool_results["lynis"] = {"status": "completed" if lynis_status == "checked" else "timed_out", "available": True, "returncode": result.get("returncode"), "finding_count": len(normalized), "label": "Termux host"}
        target_statuses.append(_full_target_status("termux_host", "Termux host", "lynis", lynis_status, elapsed_seconds=max(0, int(time.monotonic() - lynis_started)), finding_count=len(normalized), summary="Android/Termux host posture checked." if lynis_status == "checked" else "Android/Termux host posture partially checked."))
    evidence_refs.append(evidence.write_evidence(run_id, "lynis-normalized.json", {"tool": "lynis", "profile": policy.SCAN_PROFILE_FULL, "findings": [f for f in findings if f.get("source") == "lynis"]}))
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "pocketlab_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    trivy = shutil.which("trivy")
    if _overall_budget_exhausted(started, policy.SCAN_PROFILE_FULL):
        partial = True
        target_statuses.append(_full_target_status("pocketlab_source", "Pocket Lab Lite", "trivy", "timed_out", summary="Full Local Check reached its overall budget before source scanning."))
    else:
        for scanners, secret_mode, evidence_name in [
            ("vuln,misconfig", False, "target-pocketlab-source-trivy-vuln.json"),
            ("secret", True, "target-pocketlab-source-trivy-secret.json"),
        ]:
            new_findings, status = _run_trivy_target_job(trivy=trivy, run_id=run_id, root=root, target_path=root, target_id="pocketlab_source", target_label="Pocket Lab Lite", scanners=scanners, profile=policy.SCAN_PROFILE_FULL, secret_mode=secret_mode, evidence_name=evidence_name)
            findings.extend(new_findings)
            target_statuses.append(status)
            if status.get("evidence_ref"):
                evidence_refs.append(str(status["evidence_ref"]))
            partial = partial or str(status.get("status")) in {"partial", "timed_out"}
        sbom_status = _write_target_sbom(trivy, run_id, root, root, "pocketlab_source", "Pocket Lab Lite", policy.SCAN_PROFILE_FULL)
        target_statuses.append(sbom_status)
        if sbom_status.get("evidence_ref"):
            evidence_refs.append(str(sbom_status["evidence_ref"]))
        tool_results["trivy_source"] = {"status": "completed", "available": bool(trivy), "label": "Pocket Lab Lite", "finding_count": len([item for item in findings if item.get("source") == "trivy"])}
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "runtime_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    posture = runtime_config_posture(root)
    tool_results["runtime_config"] = {"status": posture.get("status") or "completed", "available": True, "label": "Runtime config", "finding_count": 0}
    target_statuses.append(_full_target_status("runtime_config", "Runtime config", "custom", "checked" if posture.get("status") == "completed" else str(posture.get("status") or "partial"), finding_count=0, evidence_ref=_write_target_json(run_id, "target-runtime-config.json", posture), summary="Runtime metadata checked without dumping raw config."))
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, posture, target_statuses, evidence_refs)})
    if target_statuses[-1].get("evidence_ref"):
        evidence_refs.append(str(target_statuses[-1]["evidence_ref"]))
    run["execution_timeline"] = execution_timeline_for_phase(run, "proot_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    rootfs = policy.discover_proot_ubuntu_rootfs(root)
    if rootfs:
        proot_candidates = [rootfs / "etc", rootfs / "usr/local", rootfs / "var/lib/dpkg"]
        existing = [candidate for candidate in proot_candidates if candidate.exists()]
        if existing:
            proot_findings_total = 0
            proot_partial = False
            for index, candidate in enumerate(existing[:3]):
                new_findings, status = _run_trivy_target_job(trivy=trivy, run_id=run_id, root=root, target_path=candidate, target_id="proot_ubuntu", target_label="PROot Ubuntu", scanners="vuln,misconfig", profile=policy.SCAN_PROFILE_FULL, evidence_name=f"target-proot-ubuntu-trivy-{index + 1}.json")
                findings.extend(new_findings)
                target_statuses.append(status)
                proot_findings_total += len(new_findings)
                if status.get("evidence_ref"):
                    evidence_refs.append(str(status["evidence_ref"]))
                proot_partial = proot_partial or str(status.get("status")) in {"partial", "timed_out"}
            tool_results["proot_ubuntu"] = {"status": "partial" if proot_partial else "completed", "available": bool(trivy), "label": "PROot Ubuntu", "finding_count": proot_findings_total}
            partial = partial or proot_partial
        else:
            target_statuses.append(_full_target_status("proot_ubuntu", "PROot Ubuntu", "custom", "missing", summary="Selected PROot Ubuntu metadata areas were not present."))
    else:
        target_statuses.append(_full_target_status("proot_ubuntu", "PROot Ubuntu", "custom", "missing", summary="PROot Ubuntu is optional and was not found."))
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, posture, target_statuses, evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "photoprism_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    photoprism_targets = _photoprism_proot_targets(rootfs)
    photoprism_config = policy.photoprism_config_dir()
    photoprism_targets.append((photoprism_config, "secret", True, "target-photoprism-config-secret.json", "PhotoPrism settings"))
    photoprism_seen = False
    photoprism_partial = False
    photoprism_finding_count = 0
    for target_path, scanners, secret_mode, evidence_name, photoprism_label in photoprism_targets:
        if target_path.exists():
            photoprism_seen = True
        new_findings, status = _run_trivy_target_job(trivy=trivy, run_id=run_id, root=root, target_path=target_path, target_id="photoprism", target_label=photoprism_label, scanners=scanners, profile=policy.SCAN_PROFILE_FULL, secret_mode=secret_mode, evidence_name=evidence_name)
        findings.extend(new_findings)
        target_statuses.append(status)
        photoprism_finding_count += len(new_findings)
        if status.get("evidence_ref"):
            evidence_refs.append(str(status["evidence_ref"]))
        photoprism_partial = photoprism_partial or str(status.get("status")) in {"partial", "timed_out"}
    if not photoprism_seen:
        target_statuses.append(_full_target_status("photoprism", "PhotoPrism", "custom", "missing", summary="PhotoPrism app/config targets were not present."))
    else:
        sbom_target = _first_existing([rootfs / "opt/photoprism"] if rootfs else [])
        if sbom_target:
            sbom_status = _write_target_sbom(trivy, run_id, root, sbom_target, "photoprism", "PhotoPrism", policy.SCAN_PROFILE_FULL)
            target_statuses.append(sbom_status)
            if sbom_status.get("evidence_ref"):
                evidence_refs.append(str(sbom_status["evidence_ref"]))
    tool_results["photoprism"] = {"status": "partial" if photoprism_partial else "completed" if photoprism_seen else "missing", "available": photoprism_seen, "label": "PhotoPrism", "finding_count": photoprism_finding_count}
    partial = partial or photoprism_partial
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, posture, target_statuses, evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "backup_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    backup_summary = _backup_metadata_summary(root)
    backup_ref = _write_target_json(run_id, "target-backup-metadata.json", backup_summary)
    backup_status = str(backup_summary.get("status") or "missing")
    target_statuses.append(_full_target_status("backup_metadata", "Backup metadata", "custom", "checked" if backup_status == "checked" else "missing", evidence_ref=backup_ref, summary=str(backup_summary.get("summary") or "Backup metadata checked.")))
    evidence_refs.append(backup_ref)
    tool_results["backup_metadata"] = {"status": "completed" if backup_status == "checked" else "missing", "available": backup_status == "checked", "label": "Backup metadata", "finding_count": 0}
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, posture, target_statuses, evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "evidence_saving")
    _write_intermediate_running_state(run, findings, evidence_refs)

    evidence_refs.append(evidence.write_evidence(run_id, "trivy-normalized.json", {"tool": "trivy", "profile": policy.SCAN_PROFILE_FULL, "findings": [f for f in findings if f.get("source") == "trivy"]}))
    run["coverage_summary"] = build_coverage_summary(plan, tool_results, posture, target_statuses, evidence_refs)
    coverage_ref = evidence.write_evidence(run_id, "coverage-summary.json", run["coverage_summary"])
    if coverage_ref not in evidence_refs:
        evidence_refs.append(coverage_ref)

    counts = count_findings(findings)
    target_review = any(str(item.get("status")) in {"partial", "timed_out", "failed", "review"} for item in target_statuses)
    partial = partial or target_review
    final_status = "degraded" if partial else "succeeded"
    copy = _profile_copy(policy.SCAN_PROFILE_FULL)
    run.update({
        "status": final_status,
        "summary": copy["partial"] if partial else copy["complete"],
        "completed_at": deps.now_utc_iso(),
        "partial_results": partial,
        "tool_results": tool_results,
        "target_statuses": target_statuses,
        "coverage_summary": build_coverage_summary(plan, tool_results, posture, target_statuses, evidence_refs),
        "critical_count": counts.get("critical", 0),
        "high_count": counts.get("high", 0),
        "medium_count": counts.get("medium", 0),
        "low_count": counts.get("low", 0),
        "info_count": counts.get("info", 0),
        "evidence_refs": evidence_refs,
    })
    run["execution_timeline"] = execution_timeline_for_phase(run, "degraded" if partial else "completed")
    state = build_state(run, findings, evidence_refs, status_override="degraded" if partial else None, summary_override=copy["partial"] if partial else None)
    summary_ref = evidence.write_evidence(run_id, "summary.json", {"run": run, "score": state.get("score"), "status": state.get("status"), "summary": state.get("summary"), "counts": counts, "findings": findings, "component_posture": state.get("component_posture"), "coverage_summary": state.get("coverage_summary"), "scan_profile": state.get("scan_profile"), "evidence_refs": evidence_refs})
    if summary_ref not in evidence_refs:
        evidence_refs.insert(0, summary_ref)
    run["evidence_refs"] = evidence_refs
    state["evidence_refs"] = evidence_refs
    _write_security_state(state)
    _write_run_projection(run)
    return {"run": run, "state": state, "findings": findings, "evidence_refs": evidence_refs}



def _run_app_security_scan(command: dict[str, Any]) -> dict[str, Any]:
    app_id = _scan_app_id(command) or "photoprism"
    app_label = _app_label(app_id) or "PhotoPrism"
    run = mark_running({**command, "profile": policy.SCAN_PROFILE_APP, "app_id": app_id})
    run_id = str(run["run_id"])
    started = time.monotonic()
    root = policy.allowed_scan_root(command.get("scope") or command.get("scan_root"))
    plan = policy.build_app_scan_plan(app_id, root)
    findings: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}
    target_statuses: list[dict[str, Any]] = []
    evidence_refs: list[str] = []
    partial = False
    posture: dict[str, Any] | None = None
    run.update({"scan_profile": policy.SCAN_PROFILE_APP, "app_id": app_id, "app_label": app_label, "tools": ["trivy", "app-posture"], "target_statuses": target_statuses})
    run["coverage_summary"] = build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)

    route_posture = _app_route_posture(app_id)
    route_ref = _write_target_json(run_id, "target-photoprism-route-posture.json", route_posture)
    route_status = str(route_posture.get("status") or "partial")
    target_statuses.append(_full_target_status("photoprism_route", "PhotoPrism route", "posture", "checked" if route_status == "checked" else "partial", evidence_ref=route_ref, summary=str(route_posture.get("summary") or "PhotoPrism route checked.")))
    evidence_refs.append(route_ref)
    tool_results["photoprism_route"] = {"status": "completed" if route_status == "checked" else "partial", "available": True, "label": "PhotoPrism route", "finding_count": 0}
    partial = partial or route_status != "checked"
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "app_files_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    trivy = shutil.which("trivy")
    rootfs = policy.discover_proot_ubuntu_rootfs(root)
    app_targets = _photoprism_proot_targets(rootfs)
    app_seen = False
    app_partial = False
    app_finding_count = 0
    for target_path, scanners, secret_mode, evidence_name, label in app_targets:
        if _overall_budget_exhausted(started, policy.SCAN_PROFILE_APP):
            status = _full_target_status("photoprism_app_files", label, "trivy", "timed_out", summary="App Check reached its overall budget before this app-file target completed.")
            target_statuses.append(status)
            app_partial = True
            continue
        if target_path.exists():
            app_seen = True
        new_findings, status = _run_trivy_target_job(trivy=trivy, run_id=run_id, root=root, target_path=target_path, target_id="photoprism_app_files", target_label=label, scanners=scanners, profile=policy.SCAN_PROFILE_APP, secret_mode=secret_mode, evidence_name=evidence_name)
        findings.extend(new_findings)
        target_statuses.append(status)
        app_finding_count += len(new_findings)
        if status.get("evidence_ref"):
            evidence_refs.append(str(status["evidence_ref"]))
        app_partial = app_partial or str(status.get("status")) in {"partial", "timed_out", "failed", "review"}
    if not app_targets:
        target_statuses.append(_full_target_status("photoprism_app_files", "PhotoPrism app files", "trivy", "missing", summary="Selected PhotoPrism app files were not present."))
    else:
        sbom_target = _first_existing([rootfs / "opt/photoprism"] if rootfs else [])
        if sbom_target:
            sbom_status = _write_target_sbom(trivy, run_id, root, sbom_target, "photoprism", "PhotoPrism", policy.SCAN_PROFILE_APP)
            target_statuses.append(sbom_status)
            if sbom_status.get("evidence_ref"):
                evidence_refs.append(str(sbom_status["evidence_ref"]))
            app_partial = app_partial or str(sbom_status.get("status")) in {"partial", "timed_out", "failed", "review"}
    tool_results["photoprism_app_files"] = {"status": "partial" if app_partial else "completed" if app_seen else "missing", "available": app_seen, "label": "PhotoPrism app files", "finding_count": app_finding_count}
    partial = partial or app_partial
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "settings_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    config_path = policy.photoprism_config_dir()
    config_findings, config_status = _run_trivy_target_job(trivy=trivy, run_id=run_id, root=root, target_path=config_path, target_id="photoprism_settings", target_label="PhotoPrism settings", scanners="secret", profile=policy.SCAN_PROFILE_APP, secret_mode=True, evidence_name="target-photoprism-config-secret.json")
    findings.extend(config_findings)
    target_statuses.append(config_status)
    if config_status.get("evidence_ref"):
        evidence_refs.append(str(config_status["evidence_ref"]))
    config_partial = str(config_status.get("status")) in {"partial", "timed_out", "failed", "review"}
    tool_results["photoprism_settings"] = {"status": "partial" if config_partial else "completed" if str(config_status.get("status")) == "checked" else str(config_status.get("status") or "missing"), "available": str(config_status.get("status")) != "missing", "label": "PhotoPrism settings", "finding_count": len(config_findings)}
    partial = partial or config_partial
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "backup_metadata_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    backup_summary = _photoprism_backup_metadata_summary(root)
    backup_ref = _write_target_json(run_id, "target-photoprism-backup-metadata.json", backup_summary)
    backup_status = str(backup_summary.get("status") or "missing")
    target_statuses.append(_full_target_status("photoprism_backup_metadata", "PhotoPrism backup metadata", "custom", "checked" if backup_status == "checked" else "missing", evidence_ref=backup_ref, summary=str(backup_summary.get("summary") or "PhotoPrism backup metadata checked.")))
    evidence_refs.append(backup_ref)
    tool_results["photoprism_backup_metadata"] = {"status": "completed" if backup_status == "checked" else "missing", "available": backup_status == "checked", "label": "PhotoPrism backup metadata", "finding_count": 0}
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "action_state_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    action_summary = _photoprism_action_state_summary()
    action_ref = _write_target_json(run_id, "target-photoprism-action-state.json", action_summary)
    target_statuses.append(_full_target_status("photoprism_action_state", "PhotoPrism action state", "custom", "checked", evidence_ref=action_ref, summary="PhotoPrism safe action state was summarized."))
    evidence_refs.append(action_ref)
    tool_results["photoprism_action_state"] = {"status": "completed", "available": True, "label": "PhotoPrism action state", "finding_count": 0}
    run.update({"tool_results": tool_results, "target_statuses": target_statuses, "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)})
    run["execution_timeline"] = execution_timeline_for_phase(run, "evidence_saving")
    _write_intermediate_running_state(run, findings, evidence_refs)

    evidence_refs.append(evidence.write_evidence(run_id, "trivy-normalized.json", {"tool": "trivy", "profile": policy.SCAN_PROFILE_APP, "app_id": app_id, "findings": [f for f in findings if f.get("source") == "trivy"]}))
    run["coverage_summary"] = build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs)
    coverage_ref = evidence.write_evidence(run_id, "coverage-summary.json", run["coverage_summary"])
    if coverage_ref not in evidence_refs:
        evidence_refs.append(coverage_ref)
    counts = count_findings(findings)
    target_review = any(str(item.get("status")) in {"partial", "timed_out", "failed", "review"} for item in target_statuses)
    partial = partial or target_review
    final_status = "degraded" if partial else "succeeded"
    copy = _profile_copy(policy.SCAN_PROFILE_APP)
    run.update({
        "status": final_status,
        "summary": copy["partial"] if partial else copy["complete"],
        "completed_at": deps.now_utc_iso(),
        "partial_results": partial,
        "tool_results": tool_results,
        "target_statuses": target_statuses,
        "coverage_summary": build_coverage_summary(plan, tool_results, target_statuses=target_statuses, evidence_refs=evidence_refs),
        "critical_count": counts.get("critical", 0),
        "high_count": counts.get("high", 0),
        "medium_count": counts.get("medium", 0),
        "low_count": counts.get("low", 0),
        "info_count": counts.get("info", 0),
        "evidence_refs": evidence_refs,
    })
    run["execution_timeline"] = execution_timeline_for_phase(run, "degraded" if partial else "completed")
    state = build_state(run, findings, evidence_refs, status_override="degraded" if partial else None, summary_override=copy["partial"] if partial else None)
    summary_ref = evidence.write_evidence(run_id, "summary.json", {"run": run, "score": state.get("score"), "status": state.get("status"), "summary": state.get("summary"), "counts": counts, "findings": findings, "component_posture": state.get("component_posture"), "coverage_summary": state.get("coverage_summary"), "scan_profile": state.get("scan_profile"), "app_id": app_id, "app_label": app_label, "evidence_refs": evidence_refs})
    if summary_ref not in evidence_refs:
        evidence_refs.insert(0, summary_ref)
    run["evidence_refs"] = evidence_refs
    state["evidence_refs"] = evidence_refs
    _write_security_state(state)
    _write_run_projection(run)
    return {"run": run, "state": state, "findings": findings, "evidence_refs": evidence_refs}


def run_security_scan(command: dict[str, Any]) -> dict[str, Any]:
    initialize_security_sqlite_runtime(reconcile=False)
    profile = _scan_profile(command)
    run_id = str(command.get("run_id") or command.get("command_id") or "")
    try:
        if profile == policy.SCAN_PROFILE_FULL:
            return _run_full_security_scan({**command, "profile": policy.SCAN_PROFILE_FULL})
        if profile == policy.SCAN_PROFILE_APP:
            return _run_app_security_scan({**command, "profile": policy.SCAN_PROFILE_APP})
        return _run_quick_security_scan({**command, "profile": policy.SCAN_PROFILE_QUICK})
    except Exception as exc:
        if run_id:
            fail_security_run(run_id, exc)
        raise
