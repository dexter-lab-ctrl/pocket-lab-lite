from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_backup, lite_catalog, lite_catalog_live, lite_security

SUPPORTED_APP_IDS = {"photoprism"}
APP_LABELS = {"photoprism": "PhotoPrism"}
APP_UPDATE_CHECK_SUBJECT = "pocketlab.commands.lite.app.update.check"
STALE_SECONDS = 20 * 60
SECRET_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "private_key",
    "credential",
    "vault",
    "nats",
    "restic",
    "database_url",
    "connection_string",
    "github_token",
    "cert_key",
)


def _now() -> str:
    return deps.now_utc_iso()


def _validate_app_id(app_id: Any) -> str:
    normalized = str(app_id or "").strip().lower().replace("_", "-")
    if normalized not in SUPPORTED_APP_IDS:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_app",
                "summary": "PhotoPrism is the first app with App Catalog update readiness.",
            },
        )
    return normalized


def _state_path() -> Path:
    return deps.settings().state_dir / "lite_app_update_state.json"


def _read_state() -> dict[str, Any]:
    try:
        payload = deps.core.read_json_file(_state_path(), {})
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(update: dict[str, Any]) -> dict[str, Any]:
    state = _read_state()
    state.update(update)
    state["updated_at"] = _now()
    deps.core.write_json_file(_state_path(), state)
    return state


def _safe_text(value: Any, fallback: str = "Available") -> str:
    text = str(value or fallback).strip() or fallback
    text = re.sub(r"(?i)(password|token|secret|api[_-]?key|private[_ -]?key)\s*[:=]\s*\S+", r"\1=[hidden]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "bearer [hidden]", text)
    text = re.sub(r"(?i)nats://\S+", "[hidden-route]", text)
    if re.search(r"/(data/data|home|proc|sys|dev|etc|root)/\S*", text):
        return fallback
    if re.search(r"~/(?!storage\b)\S+", text):
        return fallback
    if any(marker in text.lower() for marker in SECRET_MARKERS):
        if any(safe in text.lower() for safe in ("secrets hidden", "secret values are hidden", "raw secrets")):
            return text[:240]
        return fallback
    return text[:240]


def _safe_ref(value: Any, fallback: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    if any(marker in raw.lower() for marker in SECRET_MARKERS):
        return fallback
    if raw.startswith("/") or raw.startswith("~"):
        return fallback
    safe = re.sub(r"[^A-Za-z0-9._:/=-]+", "-", raw).strip("-._/")
    return safe[:180] or fallback


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _age_seconds(value: Any) -> int | None:
    parsed = _parse_time(value)
    if not parsed:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))


def update_profile(app_id: str = "photoprism") -> dict[str, Any]:
    app = _validate_app_id(app_id)
    return {
        "app_id": app,
        "app_label": APP_LABELS[app],
        "update_check_supported": True,
        "update_apply_supported": False,
        "rollback_supported": False,
        "version_detection": {"supported": True, "safe": True},
        "update_source": {"known": False, "summary": "Update source not configured yet."},
        "requires_verified_backup": True,
        "requires_restore_preview": True,
        "requires_healthy_route": True,
        "readiness_only": True,
    }


def _catalog_app(app_id: str) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    try:
        payload = lite_catalog_live.hydrate_catalog(lite_catalog.catalog_payload(None))
        apps = payload.get("apps") if isinstance(payload.get("apps"), list) else []
        for item in apps:
            if isinstance(item, dict) and item.get("id") == app:
                return item
    except Exception:
        pass
    return {}


def _is_installed(app: dict[str, Any]) -> bool:
    return bool(
        app.get("installed") is True
        or app.get("install_state") == "installed"
        or app.get("status") == "ready"
    )


def _route_healthy(app: dict[str, Any]) -> bool:
    access = app.get("access") if isinstance(app.get("access"), dict) else {}
    runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
    actions = app.get("actions") if isinstance(app.get("actions"), dict) else {}
    return bool(
        access.get("route_ready") is True
        or runtime.get("health") == "healthy"
        or actions.get("open") is True
    )


def _current_version(app: dict[str, Any]) -> dict[str, Any]:
    runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
    raw = runtime.get("version") or app.get("version")
    if not raw or str(raw).lower() in {"detected-or-unknown", "unknown", "none", "null"}:
        return {
            "status": "unknown",
            "summary": "Current version could not be safely verified.",
            "raw_value_hidden": True,
        }
    return {
        "status": "detected",
        "label": _safe_text(raw, "PhotoPrism version detected."),
        "summary": "Current version detected safely.",
        "raw_value_hidden": True,
    }


def _latest_verified_backup(app_id: str) -> dict[str, Any] | None:
    try:
        manifest = lite_app_backup.latest_app_manifest(app_id, verified_only=True)
    except Exception:
        return None
    if not manifest:
        return None
    try:
        public = lite_app_backup.app_backup_status(app_id).get("latest_backup")
    except Exception:
        public = None
    if isinstance(public, dict) and public.get("verification_status") == "verified":
        return public
    return {
        "backup_id": manifest.get("backup_id"),
        "verification_status": manifest.get("verification_status"),
        "verified_at": manifest.get("verified_at"),
        "created_at": manifest.get("created_at"),
        "summary": "Verified app backup is available.",
    }


def _restore_preview_ready(app_id: str) -> tuple[bool, dict[str, Any] | None]:
    try:
        status = lite_app_backup.app_backup_status(app_id)
    except Exception:
        return False, None
    preview = status.get("latest_restore_preview") if isinstance(status.get("latest_restore_preview"), dict) else None
    if not preview:
        return False, None
    return str(preview.get("status") or "").lower() == "ready", preview


def _safety_recent() -> tuple[bool, dict[str, Any] | None]:
    try:
        state = lite_security.current_state()
    except Exception:
        return False, None
    run = state.get("last_run") if isinstance(state.get("last_run"), dict) else None
    if not run:
        return False, None
    status = str(run.get("status") or "").lower()
    checked_at = run.get("completed_at") or run.get("updated_at") or run.get("started_at")
    age = _age_seconds(checked_at)
    return status in {"succeeded", "success", "completed"} and (age is None or age <= 24 * 60 * 60), run


def _proof(proof_id: str, label: str, status: str, summary: str) -> dict[str, Any]:
    return {
        "id": proof_id,
        "label": _safe_text(label, proof_id.replace("_", " ")),
        "status": status if status in {"passed", "review", "failed", "not_checked", "not_applicable"} else "not_checked",
        "plain_language": _safe_text(summary, "Proof available."),
    }


def _proof_counts(proofs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"passed": 0, "review": 0, "failed": 0, "not_checked": 0, "not_applicable": 0}
    for item in proofs:
        status = str(item.get("status") or "not_checked")
        counts[status if status in counts else "not_checked"] += 1
    return counts


def _readiness_summary(
    *,
    installed: bool,
    route_healthy: bool,
    backup_fresh: bool,
    restore_preview_ready: bool,
    update_source_known: bool,
    rollback_ready: bool,
    apply_supported: bool,
    version_status: str,
) -> tuple[str, str, list[str]]:
    attention: list[str] = []
    if not installed:
        return "blocked", "Install PhotoPrism before checking update readiness.", ["App is not installed."]
    if not route_healthy:
        return "blocked", "PhotoPrism route needs review before update readiness can pass.", ["App route is not healthy."]
    if not backup_fresh:
        attention.append("Create a verified app backup before updating.")
    if not restore_preview_ready:
        attention.append("Prepare a restore preview before updating.")
    if not update_source_known:
        attention.append("Update source is not configured yet.")
    if not rollback_ready:
        attention.append("Rollback is not ready yet.")
    if not apply_supported:
        attention.append("Update apply is not enabled yet.")
    if version_status != "detected":
        attention.append("Current version is unknown.")
    if attention:
        if not update_source_known:
            return "review", "Update source not ready. No update was applied.", attention
        if not backup_fresh:
            return "review", "Backup recommended before update. No update was applied.", attention
        return "review", "Update readiness checked. No update was applied.", attention
    return "ready", "Already current or ready for review. No update was applied.", attention


def update_command(app_id: str, *, reason: str | None = None) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    command_id = f"app-update-check-{app}-{uuid.uuid4().hex[:16]}"
    return {
        "command_id": command_id,
        "operation_id": command_id,
        "app_id": app,
        "app_label": APP_LABELS[app],
        "action_id": "update_app",
        "reason": _safe_text(reason, "manual update readiness check"),
        "requested_by": "lite-api",
        "requested_at": _now(),
        "readiness_only": True,
        "update_apply_supported": False,
        "profile": update_profile(app),
    }


def record_update_request(command: dict[str, Any]) -> dict[str, Any]:
    app = _validate_app_id(command.get("app_id") or "photoprism")
    now = _now()
    pending = {
        "operation_id": command.get("operation_id") or command.get("command_id"),
        "command_id": command.get("command_id"),
        "app_id": app,
        "app_label": APP_LABELS[app],
        "action_id": "update_app",
        "status": "queued",
        "readiness": "unknown",
        "summary": "Checking PhotoPrism update readiness.",
        "requested_at": command.get("requested_at") or now,
        "queued_at": now,
        "progress": {
            "phase": "queued",
            "step": "Update check queued.",
            "bounded": True,
            "steps": [
                {"id": "version", "label": "Version", "status": "waiting"},
                {"id": "backup", "label": "Backup", "status": "waiting"},
                {"id": "restore_preview", "label": "Restore Preview", "status": "waiting"},
                {"id": "route", "label": "Route", "status": "waiting"},
                {"id": "rollback", "label": "Rollback", "status": "waiting"},
                {"id": "evidence", "label": "Evidence", "status": "waiting"},
            ],
        },
        "evidence_ref": f"apps/{app}/update/{_safe_ref(command.get('command_id'), 'latest')}.json",
    }
    _write_state({"pending_update_check": pending})
    return pending


def _reconcile_stale_pending(state: dict[str, Any]) -> dict[str, Any]:
    pending = state.get("pending_update_check") if isinstance(state.get("pending_update_check"), dict) else None
    if not pending:
        return state
    status = str(pending.get("status") or "").lower()
    if status not in {"queued", "running"}:
        return state
    started = pending.get("started_at") or pending.get("queued_at") or pending.get("requested_at")
    age = _age_seconds(started)
    if age is None or age <= STALE_SECONDS:
        return state
    now = _now()
    operation_id = str(pending.get("operation_id") or pending.get("command_id") or f"app-update-check-photoprism-{uuid.uuid4().hex[:8]}")
    result = {
        **pending,
        "operation_id": operation_id,
        "status": "review",
        "readiness": "review",
        "summary": "Update readiness check needs review. The worker did not finish in the expected time.",
        "completed_at": now,
        "updated_at": now,
        "apply_supported": False,
        "rollback_ready": False,
        "evidence_ref": f"apps/photoprism/update/{_safe_ref(operation_id, 'latest')}.json",
        "proofs": [
            _proof("backend_worker_executed", "Backend worker executed", "review", "Pocket Lab queued the update readiness check, but completion was not confirmed."),
            _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser did not run update commands."),
            _proof("no_update_applied", "No update was applied", "passed", "No files were replaced and no services were restarted."),
            _proof("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden."),
        ],
        "what_changed": ["Pocket Lab marked the stale update readiness check for review."],
        "what_did_not_happen": ["No update was installed.", "No files were replaced.", "No services were restarted.", "No photos were changed."],
    }
    result["proof_counts"] = _proof_counts(result["proofs"])
    state["pending_update_check"] = None
    state["latest_update_check"] = result
    state["updated_at"] = now
    try:
        deps.core.write_json_file(_state_path(), state)
    except Exception:
        pass
    return state


def latest_update_check(app_id: str = "photoprism") -> dict[str, Any] | None:
    app = _validate_app_id(app_id)
    state = _reconcile_stale_pending(_read_state())
    latest = state.get("latest_update_check") if isinstance(state.get("latest_update_check"), dict) else None
    if latest and latest.get("app_id") == app:
        return latest
    return None


def pending_update_check(app_id: str = "photoprism") -> dict[str, Any] | None:
    app = _validate_app_id(app_id)
    state = _reconcile_stale_pending(_read_state())
    pending = state.get("pending_update_check") if isinstance(state.get("pending_update_check"), dict) else None
    if pending and pending.get("app_id") == app:
        return pending
    return None


def update_status(app_id: str = "photoprism") -> dict[str, Any]:
    app = _validate_app_id(app_id)
    latest = latest_update_check(app)
    pending = pending_update_check(app)
    running = bool(pending and str(pending.get("status") or "").lower() in {"queued", "running"})
    catalog_app = _catalog_app(app)
    installed = _is_installed(catalog_app)
    route_ok = _route_healthy(catalog_app)
    readiness = latest.get("readiness") if latest else "unknown"
    summary = latest.get("summary") if latest else "No update check has run yet."
    action_enabled = installed and not running
    disabled_reason = "Update readiness check is already running." if running else (None if installed else "Install PhotoPrism first.")
    return {
        "status": "healthy",
        "app_id": app,
        "app_label": APP_LABELS[app],
        "summary": "Update readiness can be checked.",
        "profile": update_profile(app),
        "update_check_supported": True,
        "update_apply_supported": False,
        "apply_supported": False,
        "latest_check": latest,
        "pending_check": pending,
        "operation_running": running,
        "readiness": {"status": readiness or "unknown", "summary": _safe_text(summary, "No update check has run yet.")},
        "installed": installed,
        "route_healthy": route_ok,
        "actions": {
            "update_app": {
                "enabled": action_enabled,
                "label": "Update",
                "summary": "Check whether this app is ready for a safe update.",
                "disabled_reason": disabled_reason,
            },
            "apply_update": {
                "enabled": False,
                "label": "Apply update",
                "disabled_reason": "Update apply is not enabled yet.",
            },
        },
        "updated_at": (latest or pending or {}).get("updated_at") or _now(),
    }


def create_update_readiness(command: dict[str, Any]) -> dict[str, Any]:
    app = _validate_app_id(command.get("app_id") or "photoprism")
    operation_id = str(command.get("operation_id") or command.get("command_id") or f"app-update-check-{app}-{uuid.uuid4().hex[:12]}")
    now = _now()
    _write_state({
        "pending_update_check": {
            **record_update_request({**command, "operation_id": operation_id, "command_id": operation_id}),
            "status": "running",
            "started_at": now,
            "summary": "Checking version, backup, route, rollback, and safety proof.",
            "progress": {
                "phase": "running",
                "step": "Checking version, backup, route, rollback, and safety proof.",
                "bounded": True,
                "percent": 48,
                "indeterminate": True,
                "steps": [
                    {"id": "version", "label": "Version", "status": "active"},
                    {"id": "backup", "label": "Backup", "status": "waiting"},
                    {"id": "restore_preview", "label": "Restore Preview", "status": "waiting"},
                    {"id": "route", "label": "Route", "status": "waiting"},
                    {"id": "rollback", "label": "Rollback", "status": "waiting"},
                    {"id": "evidence", "label": "Evidence", "status": "waiting"},
                ],
            },
        }
    })

    catalog_app = _catalog_app(app)
    installed = _is_installed(catalog_app)
    route_ok = _route_healthy(catalog_app)
    current = _current_version(catalog_app)
    latest = {"status": "unknown", "summary": "Update source not configured yet."}
    backup = _latest_verified_backup(app)
    backup_fresh = bool(backup and backup.get("verification_status") == "verified")
    preview_ok, preview = _restore_preview_ready(app)
    safety_ok, safety = _safety_recent()
    update_source_known = False
    update_available = "unknown"
    apply_supported = False
    rollback_ready = False
    disk_ready = "unknown"

    readiness, summary, attention = _readiness_summary(
        installed=installed,
        route_healthy=route_ok,
        backup_fresh=backup_fresh,
        restore_preview_ready=preview_ok,
        update_source_known=update_source_known,
        rollback_ready=rollback_ready,
        apply_supported=apply_supported,
        version_status=str(current.get("status") or "unknown"),
    )
    status = "succeeded" if readiness in {"ready", "review"} else ("failed" if readiness == "failed" else "blocked")
    proof_status = "passed" if status == "succeeded" else ("failed" if status == "failed" else "review")
    proofs = [
        _proof("backend_worker_executed", "Backend worker executed", proof_status, "The update readiness check ran through Pocket Lab Lite backend worker."),
        _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested Update through FastAPI."),
        _proof("no_update_applied", "No update was applied", "passed", "No files were replaced, no services were restarted, and no database was changed."),
        _proof("version_checked", "Version checked", "passed" if current.get("status") == "detected" else "review", current.get("summary") or "Current version was checked."),
        _proof("update_source_checked", "Update source checked", "passed" if update_source_known else "review", "Update source is configured." if update_source_known else "Update source is not configured yet."),
        _proof("app_health_checked", "App health checked", "passed" if route_ok else "failed", "Pocket Lab checked the same-origin PhotoPrism route."),
        _proof("backup_freshness_checked", "Backup freshness checked", "passed" if backup_fresh else "review", "A verified app backup is available." if backup_fresh else "Create a verified app backup before updating."),
        _proof("restore_preview_checked", "Restore preview checked", "passed" if preview_ok else "review", "A restore preview is ready." if preview_ok else "Prepare a restore preview before updating."),
        _proof("rollback_readiness_checked", "Rollback readiness checked", "passed" if rollback_ready else "review", "Rollback is ready." if rollback_ready else "Rollback is not enabled for app updates yet."),
        _proof("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden."),
        _proof("raw_logs_hidden", "Raw logs hidden", "passed", "Raw app logs are hidden."),
        _proof("raw_paths_hidden", "Raw paths hidden", "passed", "Raw Android and app paths are hidden."),
        _proof("media_preserved", "Media preserved", "passed", "No photos were changed."),
        _proof("photoprism_owns_media_details", "PhotoPrism owns media details", "passed", "PhotoPrism handles indexing, thumbnails, metadata, and media warnings."),
        _proof("receipt_saved", "Receipt saved", proof_status, "Pocket Lab saved a sanitized update-readiness receipt."),
    ]
    completed = _now()
    evidence_ref = f"apps/{app}/update/{_safe_ref(operation_id, 'latest')}.json"
    result = {
        "app_id": app,
        "app_label": APP_LABELS[app],
        "action_id": "update_app",
        "action_label": "Update",
        "operation_id": operation_id,
        "command_id": operation_id,
        "status": status,
        "readiness": readiness,
        "summary": summary,
        "started_at": now,
        "completed_at": completed,
        "updated_at": completed,
        "current_version": current,
        "latest_version": latest,
        "update_source": {"known": update_source_known, "summary": "Update source not configured yet."},
        "update_available": update_available,
        "apply_supported": apply_supported,
        "update_apply_supported": apply_supported,
        "rollback_ready": rollback_ready,
        "backup_fresh": backup_fresh,
        "latest_backup": backup,
        "restore_preview_ready": preview_ok,
        "latest_restore_preview": preview,
        "route_healthy": route_ok,
        "safety_recent": safety_ok,
        "latest_safety_check": safety,
        "disk_ready": disk_ready,
        "attention_items": attention,
        "proofs": proofs,
        "proof_counts": _proof_counts(proofs),
        "evidence_ref": evidence_ref,
        "redaction": {
            "status": "passed",
            "secrets_hidden": True,
            "raw_logs_hidden": True,
            "raw_paths_hidden": True,
            "media_file_names_hidden": True,
            "secret_values_saved": False,
        },
        "technical_details": {
            "action_id": "update_app",
            "execution_owner": "backend worker",
            "current_version_status": current.get("status"),
            "latest_version_status": latest.get("status"),
            "update_available": update_available,
            "apply_supported": False,
            "rollback_ready": rollback_ready,
            "backup_fresh": backup_fresh,
            "restore_preview_ready": preview_ok,
            "route_healthy": route_ok,
            "safety_recent": safety_ok,
            "raw_logs": "hidden",
            "raw_paths": "hidden",
            "secret_values": "hidden",
        },
        "what_changed": ["Pocket Lab Lite checked whether PhotoPrism is ready for a safe update."],
        "what_did_not_happen": [
            "No update was installed.",
            "No files were replaced.",
            "No database was changed.",
            "No photos were changed.",
            "No services were restarted.",
            "No secret values were exposed.",
        ],
        "details_owner": {"name": "PhotoPrism", "reason": "PhotoPrism handles indexing, thumbnails, metadata, and media-specific warnings."},
        "progress": {
            "phase": "completed" if status == "succeeded" else status,
            "step": "Update readiness checked. No update was applied.",
            "bounded": True,
            "percent": 100,
            "steps": [
                {"id": "version", "label": "Version", "status": "completed" if current.get("status") == "detected" else "review"},
                {"id": "backup", "label": "Backup", "status": "completed" if backup_fresh else "review"},
                {"id": "restore_preview", "label": "Restore Preview", "status": "completed" if preview_ok else "review"},
                {"id": "route", "label": "Route", "status": "completed" if route_ok else "failed"},
                {"id": "rollback", "label": "Rollback", "status": "completed" if rollback_ready else "review"},
                {"id": "evidence", "label": "Evidence", "status": "completed"},
            ],
        },
    }
    _write_state({"pending_update_check": None, "latest_update_check": result})
    return result


def update_receipt(app_id: str = "photoprism", operation_id: str | None = None) -> dict[str, Any] | None:
    app = _validate_app_id(app_id)
    latest = latest_update_check(app)
    if not latest:
        return None
    selected = str(operation_id or "latest")
    if selected not in {"", "latest"} and selected not in {str(latest.get("operation_id")), str(latest.get("command_id"))}:
        return None
    return {
        "receipt_version": 1,
        "receipt_id": _safe_ref(latest.get("operation_id") or latest.get("command_id"), "app-update-check"),
        "app_id": app,
        "app_label": APP_LABELS[app],
        "action_id": "update_app",
        "action_label": "Update",
        "status": latest.get("status") or "review",
        "readiness": latest.get("readiness") or "review",
        "summary": _safe_text(latest.get("summary"), "Update readiness checked. No update was applied."),
        "started_at": latest.get("started_at"),
        "completed_at": latest.get("completed_at") or latest.get("updated_at"),
        "proofs": latest.get("proofs") or [],
        "proof_counts": latest.get("proof_counts") or _proof_counts(latest.get("proofs") or []),
        "proof_status": "passed" if latest.get("status") == "succeeded" and latest.get("readiness") == "ready" else "review",
        "safety_badges": ["Backend worker executed", "No update applied", "Secrets hidden", "Media preserved"],
        "what_changed": latest.get("what_changed") or ["Pocket Lab Lite checked update readiness."],
        "what_did_not_happen": latest.get("what_did_not_happen") or ["No update was installed.", "No files were replaced.", "No photos were changed."],
        "details_owner": latest.get("details_owner") or {"name": "PhotoPrism", "reason": "PhotoPrism handles media-specific details."},
        "redaction": latest.get("redaction") or {"status": "passed", "secrets_hidden": True, "raw_logs_hidden": True, "raw_paths_hidden": True},
        "technical_details": latest.get("technical_details") or {},
        "evidence_ref": latest.get("evidence_ref"),
        "updated_at": latest.get("updated_at") or _now(),
    }


def apply_update_disabled(app_id: str = "photoprism") -> dict[str, Any]:
    app = _validate_app_id(app_id)
    return {
        "status": "disabled",
        "accepted": False,
        "app_id": app,
        "action_id": "apply_update",
        "summary": "Update apply is not enabled yet. Run backup and review readiness first.",
        "update_apply_supported": False,
    }
