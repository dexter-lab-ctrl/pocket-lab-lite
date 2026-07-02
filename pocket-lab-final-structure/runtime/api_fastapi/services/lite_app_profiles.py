from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_storage, lite_backup, lite_catalog, lite_catalog_live, lite_security, lite_app_backup_targets, lite_app_backup

SUPPORTED_APP_IDS = {"photoprism"}
APP_NAMES = {"photoprism": "PhotoPrism"}

APP_SECURITY_CHECK_SUBJECT = "pocketlab.commands.lite.security.app_scan"
APP_BACKUP_SUBJECT = lite_app_backup.APP_BACKUP_CREATE_SUBJECT

_SECRET_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "private_key",
    "credential",
    "nats",
    "vault",
    "restic_password",
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
                "summary": "PhotoPrism is the first app with Lite app profiles.",
            },
        )
    return normalized


def _public_text(value: Any, fallback: str = "Available") -> str:
    text = str(value or fallback).strip() or fallback
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return fallback
    if "/" in text and (text.startswith("/") or text.startswith("~")):
        return fallback
    return text[:220]


def _catalog_app(app_id: str) -> dict[str, Any]:
    payload = lite_catalog.catalog_payload()
    try:
        payload = lite_catalog_live.hydrate_catalog(payload)
    except Exception:
        pass
    for app in payload.get("apps") or payload.get("items") or []:
        if isinstance(app, dict) and str(app.get("id") or "").lower() == app_id:
            return app
    return {}


def _evidence_summary(kind: str) -> dict[str, Any]:
    if kind == "security":
        state = lite_security.current_state()
        refs = state.get("evidence_refs") if isinstance(state.get("evidence_refs"), list) else []
        history = state.get("history") if isinstance(state.get("history"), list) else []
        count = len(refs) or int((history[0] or {}).get("evidence_count") or 0) if history else len(refs)
        return {
            "status": "saved" if count else "pending",
            "count": int(count or 0),
            "summary": f"{int(count)} safety record(s)" if count else "Evidence pending",
        }

    backups = lite_backup.list_backups()
    count = int(backups.get("count") or 0)
    return {
        "status": "saved" if count else "pending",
        "count": count,
        "summary": f"{count} recovery record(s)" if count else "No app backup evidence yet",
    }


def _mapping_summary() -> dict[str, Any]:
    try:
        return lite_app_storage.list_mappings("photoprism")
    except Exception:
        return {"mappings": [], "count": 0, "summary": "No media folders connected yet."}


def _backup_target_summary(app: dict[str, Any]) -> dict[str, Any]:
    try:
        return lite_app_backup_targets.backup_target_summary("photoprism")
    except Exception:
        ready = app.get("ready_device_capabilities") if isinstance(app.get("ready_device_capabilities"), dict) else {}
        available = app.get("available_device_capabilities") if isinstance(app.get("available_device_capabilities"), dict) else {}
        ready_count = int(ready.get("backup_target") or 0)
        available_count = int(available.get("backup_target") or 0)
        count = ready_count or available_count
        return {
            "available": count > 0,
            "ready": ready_count > 0,
            "count": count,
            "ready_count": ready_count,
            "label": "Backup target available" if count else "No backup target yet",
            "summary": "Storage device ready for backups" if ready_count else ("Backup target known but not ready" if count else "Join a storage device to save app backups elsewhere."),
        }


def _check(check_id: str, label: str, status: str, summary: str) -> dict[str, str]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "summary": _public_text(summary, "Check recorded."),
    }


def _security_status_from_checks(checks: list[dict[str, str]], installed: bool) -> str:
    if not installed:
        return "unavailable"
    statuses = {item.get("status") for item in checks}
    if "failed" in statuses or "needs_attention" in statuses:
        return "needs_attention"
    if "review" in statuses:
        return "review"
    if "pending" in statuses or "unknown" in statuses:
        return "checking"
    return "ready"


def _backup_status(profile: dict[str, Any]) -> str:
    if not profile.get("installed"):
        return "unavailable"
    return "ready"


def photoprism_backup_profile() -> dict[str, Any]:
    app = _catalog_app("photoprism")
    mappings = _mapping_summary()
    target = _backup_target_summary(app)
    app_backup_status = lite_app_backup.app_backup_status("photoprism")
    latest_app_backup = app_backup_status.get("latest_backup") if isinstance(app_backup_status.get("latest_backup"), dict) else None
    latest_restore_preview = app_backup_status.get("latest_restore_preview") if isinstance(app_backup_status.get("latest_restore_preview"), dict) else None
    restore_preview_ready = bool((app_backup_status.get("actions") or {}).get("preview_restore", {}).get("enabled"))
    installed = bool(app.get("installed") or app.get("install_state") == "installed" or app.get("status") == "ready")
    profile: dict[str, Any] = {
        "app_id": "photoprism",
        "name": "PhotoPrism",
        "installed": installed,
        "status": "ready" if installed else "unavailable",
        "summary": "PhotoPrism config and app metadata are ready for backup." if installed else "Install PhotoPrism to protect it here.",
        "default_mode": "config_only",
        "available_modes": [
            {
                "id": "config_only",
                "label": "Config only",
                "description": "Backs up PhotoPrism settings and Pocket Lab app metadata.",
            },
            {
                "id": "config_and_index",
                "label": "Config + index",
                "description": "Includes PhotoPrism metadata when available.",
            },
            {
                "id": "full_with_media",
                "label": "Include media",
                "description": "Includes connected media folders. This can be large.",
                "requires_capability": "backup_target",
                "available": bool(target.get("ready")),
            },
        ],
        "included": [
            "App config",
            "App metadata",
            "Storage mappings",
            "Caddy route metadata",
            "Sanitized evidence references",
        ],
        "excluded": [
            "Original media",
            "Import folder media",
            "Generated cache",
            "Raw secrets",
        ],
        "media": {
            "default": "excluded",
            "summary": "Media excluded. Your photo files can be large. Add media backup when a storage device is ready.",
            "connected_folder_count": int(mappings.get("count") or 0),
        },
        "backup_target": target,
        "backup_target_summary": target,
        "backup_targets": target.get("targets", []) if isinstance(target, dict) else [],
        "evidence": _evidence_summary("recovery"),
        "latest_backup": latest_app_backup,
        "latest_restore_preview": latest_restore_preview,
        "storage_mappings": {
            "count": int(mappings.get("count") or 0),
            "summary": _public_text(mappings.get("summary"), "No media folders connected."),
        },
        "restore": {
            "preview_available": restore_preview_ready,
            "restore_available": False,
            "preview_only": True,
            "restore_apply_supported": False,
            "summary": "Restore preview ready." if restore_preview_ready else "No verified app backup yet.",
        },
        "updated_at": _now(),
    }
    profile["status"] = _backup_status(profile)
    return profile


def app_backup_profiles() -> dict[str, Any]:
    profiles = [photoprism_backup_profile()]
    return {
        "status": "healthy",
        "summary": "App backup profiles are available.",
        "apps": profiles,
        "items": profiles,
        "count": len(profiles),
        "updated_at": _now(),
    }


def app_backup_profile(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    return photoprism_backup_profile()


def photoprism_security_profile() -> dict[str, Any]:
    app = _catalog_app("photoprism")
    mappings = _mapping_summary()
    backup = photoprism_backup_profile()
    evidence_summary = _evidence_summary("security")
    installed = bool(app.get("installed") or app.get("install_state") == "installed" or app.get("status") == "ready")
    route_ready = bool((app.get("access") or {}).get("route_ready") or (app.get("actions") or {}).get("open"))
    mapping_items = [item for item in mappings.get("mappings") or [] if isinstance(item, dict)]
    read_write = [item for item in mapping_items if str(item.get("mode") or "").lower() == "read_write"]
    profile_checks = [
        _check(
            "route_safety",
            "Secure app route",
            "passed" if route_ready else "review",
            "PhotoPrism opens through Pocket Lab." if route_ready else "Pocket Lab could not verify the app route yet.",
        ),
        _check(
            "config_redaction",
            "Config protected",
            "passed" if installed else "unknown",
            "Sensitive values are hidden." if installed else "Install PhotoPrism before checking app config.",
        ),
        _check(
            "media_permissions",
            "Media folder access",
            "review" if read_write else "passed" if mapping_items else "unknown",
            f"{len(read_write)} folder(s) can edit media." if read_write else ("Connected folders are read-only." if mapping_items else "No media folders connected yet."),
        ),
        _check(
            "backup_readiness",
            "Backup readiness",
            "passed" if backup.get("status") in {"ready", "review"} else "unknown",
            "App config can be backed up." if installed else "Install PhotoPrism before app backups are available.",
        ),
        _check(
            "pwa_route_readiness",
            "PWA route readiness",
            "passed" if route_ready else "review",
            "Open stays inside Pocket Lab routing." if route_ready else "Open is not ready yet.",
        ),
        _check(
            "evidence_saved",
            "Evidence saved",
            "passed" if evidence_summary.get("count") else "unknown",
            evidence_summary.get("summary") or "Evidence pending.",
        ),
    ]
    status = _security_status_from_checks(profile_checks, installed)
    current = lite_security.current_state()
    last_run = current.get("last_run") if isinstance(current.get("last_run"), dict) else {}
    return {
        "app_id": "photoprism",
        "name": "PhotoPrism",
        "installed": installed,
        "status": status,
        "summary": "PhotoPrism is protected." if status == "ready" else "PhotoPrism protection needs review." if installed else "Install PhotoPrism to include it in app safety checks.",
        "last_checked_at": last_run.get("completed_at") or last_run.get("started_at") or last_run.get("requested_at"),
        "checks": profile_checks,
        "evidence": evidence_summary,
        "backup": {
            "status": backup.get("status"),
            "summary": backup.get("summary"),
            "media": (backup.get("media") or {}).get("summary"),
        },
        "updated_at": _now(),
    }


def app_security_profiles() -> dict[str, Any]:
    profiles = [photoprism_security_profile()]
    return {
        "status": "healthy",
        "summary": "Protected app profiles are available.",
        "apps": profiles,
        "items": profiles,
        "count": len(profiles),
        "updated_at": _now(),
    }


def app_security_profile(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    return photoprism_security_profile()


def app_security_check_not_implemented(app_id: str, reason: str | None = None) -> dict[str, Any]:
    _validate_app_id(app_id)
    return {
        "status": "not_implemented",
        "accepted": False,
        "app_id": "photoprism",
        "summary": "App-specific safety checks are prepared, but execution is not enabled yet. Use Run Safety Check for the current device-wide scan.",
        "reason": _public_text(reason, "manual app safety check"),
        "next_step": "Extend the worker with a bounded app security command before enabling app-specific execution.",
    }


def app_backup_command(app_id: str, *, mode: str = "config_only", reason: str | None = None) -> dict[str, Any]:
    _validate_app_id(app_id)
    return lite_app_backup.app_backup_command(app_id, mode=mode, reason=reason)


def app_restore_preview_not_implemented(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    return {
        "status": "not_implemented",
        "accepted": False,
        "app_id": "photoprism",
        "summary": "Restore preview coming soon for app-specific recovery.",
    }


def app_restore_not_implemented(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    return {
        "status": "not_implemented",
        "accepted": False,
        "app_id": "photoprism",
        "summary": "App restore is disabled until preview, confirmation, checkpoint, whitelist, and health validation are implemented.",
    }
