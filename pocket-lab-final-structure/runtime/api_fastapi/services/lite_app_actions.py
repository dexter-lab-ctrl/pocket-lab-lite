from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from . import lite_app_backup, lite_app_backup_targets, lite_app_lifecycle, lite_app_operations, lite_app_profiles, lite_app_update, lite_photoprism_lifecycle, lite_photoprism_media

SUPPORTED_APP_IDS = {"photoprism"}
SUPPORTED_ACTIONS = {
    "open",
    "open_full_screen",
    "install_to_phone",
    "connect_photos",
    "check_app",
    "backup_app",
    "preview_restore",
    "import_photos",
    "backup_to_storage",
    "install_app",
    "update_app",
    "repair_app",
    "remove_app",
}


def _validate_app_id(app_id: Any) -> str:
    normalized = str(app_id or "").strip().lower().replace("_", "-")
    if normalized not in SUPPORTED_APP_IDS:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_app",
                "summary": "PhotoPrism is the first app with a Lite Action Center.",
            },
        )
    return normalized


def validate_action_id(action_id: Any) -> str:
    normalized = str(action_id or "").strip().lower().replace("-", "_")
    if normalized not in SUPPORTED_ACTIONS:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_action",
                "summary": "Choose a supported PhotoPrism action.",
            },
        )
    return normalized


def _safe_text(value: Any, fallback: str = "Action status is available.") -> str:
    text = str(value or fallback).strip() or fallback
    lowered = text.lower()
    if any(marker in lowered for marker in ("password", "token", "secret", "api_key", "private_key", "vault", "nats", "restic")):
        return fallback
    if (text.startswith("/") or text.startswith("~")) and "/apps/" not in text:
        return fallback
    return text[:220]


def app_actions(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    profile = lite_app_lifecycle.app_lifecycle_profile("photoprism")
    actions = profile.get("actions") if isinstance(profile.get("actions"), dict) else {}
    return {
        "status": "healthy",
        "app_id": "photoprism",
        "name": "PhotoPrism",
        "summary": "PhotoPrism Action Center is available.",
        "actions": actions,
        "items": actions,
        "media": profile.get("media") or lite_photoprism_media.media_status("photoprism"),
        "updated_at": profile.get("updated_at"),
    }


def prepare_action(app_id: str, action_id: str, *, payload: dict[str, Any] | None = None, reason: str | None = None) -> dict[str, Any]:
    _validate_app_id(app_id)
    action = validate_action_id(action_id)
    payload = payload or {}
    reason = payload.get("reason") if reason is None else reason
    profile = lite_app_lifecycle.app_lifecycle_profile("photoprism")
    action_profile = (profile.get("actions") or {}).get(action)
    if not isinstance(action_profile, dict):
        raise HTTPException(status_code=404, detail={"status": "unsupported_action", "summary": "Choose a supported PhotoPrism action."})

    # Destructive and target-specific actions validate their own preconditions so
    # callers get precise, safe reasons such as confirmation_required or target_not_ready.
    if action == "remove_app":
        response = lite_photoprism_lifecycle.remove_not_implemented(payload)
        return {"kind": "remove_not_implemented", "response": response, "summary": response.get("summary")}

    if action == "backup_to_storage":
        response = lite_app_backup.backup_to_storage_readiness(
            "photoprism",
            payload.get("target_device_id"),
            reason=reason,
        )
        return {"kind": "backup_to_storage_readiness", "response": response, "summary": response.get("summary")}

    if not action_profile.get("enabled"):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "disabled",
                "app_id": "photoprism",
                "action_id": action,
                "summary": _safe_text(action_profile.get("reason"), "This action is not ready yet."),
            },
        )

    if action in {"open", "open_full_screen", "install_to_phone"}:
        return {
            "kind": "url",
            "status": "ready",
            "accepted": False,
            "app_id": "photoprism",
            "action_id": action,
            "label": action_profile.get("label"),
            "url": action_profile.get("url") or "/apps/photoprism/",
            "summary": "Open PhotoPrism through Pocket Lab.",
        }

    if action == "connect_photos":
        return {
            "kind": "guidance",
            "status": "ready",
            "accepted": False,
            "app_id": "photoprism",
            "action_id": action,
            "label": action_profile.get("label"),
            "summary": "Use the media folder buttons to connect phone photos safely.",
        }

    if action == "backup_app":
        command = lite_app_backup.app_backup_command("photoprism", mode="config_only", reason=reason)
        return {"kind": "backup", "command": command, "summary": "PhotoPrism app backup queued."}

    if action == "preview_restore":
        command = lite_app_backup.app_restore_preview_command("photoprism", backup_id=payload.get("backup_id") or "latest", reason=reason)
        return {"kind": "restore_preview", "command": command, "summary": "PhotoPrism restore preview queued."}

    if action in {"check_app", "repair_app"}:
        command = lite_app_operations.command_for_operation("photoprism", action, reason=reason)
        summary = "Checking PhotoPrism safety." if action == "check_app" else "Repairing PhotoPrism safely."
        return {
            "kind": "app_operation",
            "command": command,
            "subject": lite_app_operations.subject_for_action(action),
            "summary": summary,
        }

    if action == "import_photos":
        command = lite_photoprism_media.media_command(action, reason=reason)
        return {"kind": "media", "command": command, "summary": action_profile.get("summary") or f"{action_profile.get('label')} queued."}

    if action == "install_app":
        command = lite_photoprism_lifecycle.install_command(reason=reason)
        return {"kind": "install_app", "command": command, "summary": "PhotoPrism install started."}

    if action == "update_app":
        command = lite_app_update.update_command("photoprism", reason=reason)
        return {"kind": "update_check", "command": command, "subject": lite_app_update.APP_UPDATE_CHECK_SUBJECT, "summary": "Checking PhotoPrism update readiness."}

    raise HTTPException(
        status_code=501,
        detail={
            "status": "not_implemented",
            "app_id": "photoprism",
            "action_id": action,
            "summary": "This app action is not implemented yet.",
        },
    )
