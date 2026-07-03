from __future__ import annotations

from typing import Any
import re

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

ACTION_CATEGORY_LABELS = {
    "access": "Open",
    "media": "Photos",
    "safety": "Safety",
    "recovery": "Recovery",
    "setup": "App setup",
    "danger": "Remove",
}

ACTION_DEFINITIONS: dict[str, dict[str, Any]] = {
    "open": {
        "label": "Open",
        "category": "access",
        "summary": "Open PhotoPrism through Pocket Lab.",
        "risk": "low",
        "execution_owner": "browser_navigation",
    },
    "open_full_screen": {
        "label": "Open full screen",
        "category": "access",
        "summary": "Open PhotoPrism in a full browser tab.",
        "risk": "low",
        "execution_owner": "browser_navigation",
    },
    "install_to_phone": {
        "label": "Install to phone",
        "category": "access",
        "summary": "Install the PhotoPrism web app shortcut on this phone.",
        "risk": "low",
        "execution_owner": "browser_navigation",
    },
    "connect_photos": {
        "label": "Connect photos",
        "category": "media",
        "summary": "Choose where PhotoPrism should look for pictures.",
        "risk": "low",
        "execution_owner": "fastapi",
    },
    "import_photos": {
        "label": "Import photos",
        "category": "media",
        "summary": "Bring connected photos into PhotoPrism. PhotoPrism handles indexing and media details.",
        "risk": "low",
        "execution_owner": "backend_worker",
    },
    "check_app": {
        "label": "Check app",
        "category": "safety",
        "summary": "Check route, health, storage, and safety record.",
        "risk": "low",
        "execution_owner": "backend_worker",
    },
    "backup_app": {
        "label": "Back up app",
        "category": "recovery",
        "summary": "Save settings, mappings, route records, and safe app records. Media is excluded by default.",
        "risk": "low",
        "execution_owner": "backend_worker",
    },
    "preview_restore": {
        "label": "Preview restore",
        "category": "recovery",
        "summary": "Review what would be restored before making changes.",
        "risk": "review",
        "execution_owner": "backend_worker",
    },
    "backup_to_storage": {
        "label": "Back up to storage device",
        "category": "recovery",
        "summary": "Join a storage device to save app backups elsewhere.",
        "risk": "low",
        "execution_owner": "backend_worker",
    },
    "repair_app": {
        "label": "Repair",
        "category": "recovery",
        "summary": "Fix route, health, and storage setup safely.",
        "risk": "review",
        "execution_owner": "backend_worker",
    },
    "install_app": {
        "label": "Install",
        "category": "setup",
        "summary": "Set up PhotoPrism through the backend worker.",
        "risk": "review",
        "execution_owner": "backend_worker",
    },
    "update_app": {
        "label": "Update",
        "category": "setup",
        "summary": "Check whether this app is ready for a safe update. No update is applied.",
        "risk": "review",
        "execution_owner": "backend_worker",
    },
    "remove_app": {
        "label": "Remove app",
        "category": "danger",
        "summary": "Remove PhotoPrism only after explicit confirmation. Media, backups, and backend records are preserved by default.",
        "risk": "destructive",
        "execution_owner": "backend_worker",
    },
}


ACTION_DETAIL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "open": {
        "summary": "Pocket Lab opens PhotoPrism through the secure same-origin route.",
        "what_happened": ["Pocket Lab uses the current browser origin to open PhotoPrism."],
        "what_changed": ["Nothing changed in the backend."],
        "what_did_not_happen": ["No worker command was queued.", "No app files were changed.", "No photos were changed."],
        "saved": False,
    },
    "open_full_screen": {
        "summary": "Pocket Lab opens PhotoPrism in a full browser tab through the secure same-origin route.",
        "what_happened": ["Pocket Lab uses the current browser origin to open PhotoPrism full screen."],
        "what_changed": ["Nothing changed in the backend."],
        "what_did_not_happen": ["No worker command was queued.", "No app files were changed.", "No photos were changed."],
        "saved": False,
    },
    "install_to_phone": {
        "summary": "Pocket Lab opens PhotoPrism so the browser can install it on this phone.",
        "what_happened": ["Pocket Lab opens PhotoPrism through the secure same-origin route."],
        "what_changed": ["Nothing changed in the backend."],
        "what_did_not_happen": ["No worker command was queued.", "No app files were changed.", "No photos were changed."],
        "saved": False,
    },
    "connect_photos": {
        "summary": "Pocket Lab prepares a safe photo-source connection.",
        "what_happened": ["Pocket Lab checks the selected photo source before connecting it."],
        "what_changed": ["A safe media mapping may be recorded after confirmation."],
        "what_did_not_happen": ["No photos were moved.", "No photos were deleted.", "Raw paths were not shown in the app."],
    },
    "import_photos": {
        "summary": "PhotoPrism imported connected photos.",
        "what_happened": ["PhotoPrism imported connected photos through the backend worker path."],
        "what_changed": ["PhotoPrism was asked to bring connected photos into its library."],
        "what_did_not_happen": ["Pocket Lab did not expose file names or raw app logs.", "Pocket Lab did not change source photos."],
        "technical_details": ["PhotoPrism owns indexing, thumbnails, metadata, and media warnings."],
    },
    "check_app": {
        "summary": "Pocket Lab checked PhotoPrism safety and readiness.",
        "what_happened": ["Pocket Lab checked PhotoPrism route, health, storage, and protection state."],
        "what_changed": ["Nothing changed unless a backend action completed and recorded a new status."],
        "what_did_not_happen": ["No photos were scanned.", "No database was changed.", "No app password was changed."],
    },
    "backup_app": {
        "summary": "Pocket Lab saved PhotoPrism app settings and safe records.",
        "what_happened": ["Pocket Lab queued or ran an app backup through the backend worker path."],
        "what_changed": ["PhotoPrism settings, mappings, route records, and safe app records may be saved."],
        "what_did_not_happen": ["Photo files were not backed up by this app-record backup.", "Raw secrets were not exposed.", "Raw backup internals were not shown."],
    },
    "preview_restore": {
        "summary": "Pocket Lab prepared a restore preview.",
        "what_happened": ["Pocket Lab prepared a preview of what restore would do."],
        "what_changed": ["Nothing changed."],
        "what_did_not_happen": ["No restore was applied.", "No app data was changed.", "No photos were changed."],
    },
    "backup_to_storage": {
        "summary": "This action is paused until a storage device is ready.",
        "what_happened": ["Pocket Lab checked whether a storage device can receive app backups."],
        "what_changed": ["Nothing changed."],
        "what_did_not_happen": ["No backup was started.", "No worker command was queued when no storage device was ready."],
    },
    "repair_app": {
        "summary": "Pocket Lab checked PhotoPrism setup and repair readiness.",
        "what_happened": ["Pocket Lab checked route, health, and storage setup."],
        "what_changed": ["Nothing changed unless a safe repair step was needed and completed."],
        "what_did_not_happen": ["No photos were changed.", "No database was changed.", "No app password was changed.", "No reinstall was started."],
    },
    "install_app": {
        "summary": "Pocket Lab prepares PhotoPrism installation through the backend worker path.",
        "what_happened": ["Pocket Lab checks whether PhotoPrism can be installed safely."],
        "what_changed": ["Nothing changed unless the backend worker accepted and ran the install."],
        "what_did_not_happen": ["The browser did not run install commands.", "No raw app credentials were shown."],
    },
    "update_app": {
        "summary": "Pocket Lab checked whether PhotoPrism is ready for an update.",
        "what_happened": ["Pocket Lab checked whether PhotoPrism is ready for a safe update."],
        "what_changed": ["Nothing changed."],
        "what_did_not_happen": ["No update was installed.", "No files were replaced.", "No database was changed.", "No services were restarted."],
    },
    "remove_app": {
        "summary": "Pocket Lab is waiting for confirmation before making changes.",
        "what_happened": ["Pocket Lab is waiting for confirmation before making changes."],
        "what_changed": ["Nothing changed."],
        "what_would_happen_after_confirmation": ["PhotoPrism runtime and route would be removed when remove support is enabled."],
        "what_will_not_happen_by_default": ["Your photo files will not be deleted.", "Backups and backend records will be preserved."],
        "what_did_not_happen": ["No remove action was started from this details view."],
        "technical_details": ["This is a destructive action and requires confirmation."],
        "saved": False,
    },
}

ACTION_ORDER = [
    "open",
    "open_full_screen",
    "install_to_phone",
    "connect_photos",
    "import_photos",
    "check_app",
    "backup_app",
    "preview_restore",
    "backup_to_storage",
    "repair_app",
    "install_app",
    "update_app",
    "remove_app",
]

TERMINAL_STATUS_VALUES = {"succeeded", "success", "done", "completed", "review", "degraded", "warning", "needs_attention", "failed", "error"}


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


def _normalized_status(value: Any, *, enabled: bool) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"queued", "pending"}:
        return "queued"
    if raw in {"running", "working", "executing"}:
        return "running"
    if raw in {"succeeded", "success", "done", "completed", "verified", "ready"}:
        return "ready" if not raw.startswith("succeed") else "succeeded"
    if raw in {"review", "degraded", "warning", "needs_attention"}:
        return "review"
    if raw in {"failed", "failure", "error"}:
        return "failed"
    if raw in {"blocked", "disabled", "paused"}:
        return "blocked"
    if raw in {"not_supported", "unsupported"}:
        return "not_supported"
    if raw in {"not_ready", "unavailable"}:
        return "not_ready"
    if raw in {"connected", "imported"}:
        return raw
    if enabled:
        return "ready"
    return "not_ready"


def _progress_payload(action_id: str, action: dict[str, Any], status: str) -> dict[str, Any]:
    raw = action.get("progress") if isinstance(action.get("progress"), dict) else {}
    phase = raw.get("phase") or status or "ready"
    step = raw.get("step") or raw.get("summary")
    if not step:
        if status == "queued":
            step = "Request accepted."
        elif status == "running":
            step = "Worker picked it up."
        elif status in {"ready", "not_ready"}:
            step = "Ready." if status == "ready" else "Not ready."
        else:
            step = "Action status is available."
    steps = raw.get("steps") if isinstance(raw.get("steps"), list) else []
    return {
        "phase": _safe_text(phase, "ready"),
        "step": _safe_text(step, "Action status is available."),
        "percent": raw.get("percent") if isinstance(raw.get("percent"), (int, float)) else None,
        "indeterminate": bool(raw.get("indeterminate", status in {"queued", "running"})),
        "bounded": bool(raw.get("bounded", True)),
        "steps": steps,
    }


def _result_payload(action_id: str, action: dict[str, Any], status: str) -> dict[str, Any]:
    latest_check = action.get("latest_check") if isinstance(action.get("latest_check"), dict) else {}
    raw_status = latest_check.get("status") or action.get("result_status") or status
    raw_summary = action.get("last_result") or latest_check.get("summary") or action.get("result_summary")
    receipt_id = action.get("receipt_id") or latest_check.get("receipt_id")
    if status not in TERMINAL_STATUS_VALUES and not raw_summary and not receipt_id:
        return {
            "status": None,
            "summary": None,
            "receipt_id": None,
            "backend_only": True,
        }
    return {
        "status": _normalized_status(raw_status, enabled=True),
        "summary": _safe_text(raw_summary, "Action result is available."),
        "receipt_id": _safe_text(receipt_id, "") if receipt_id else None,
        "backend_only": True,
    }


def _troubleshooting_payload(action: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    latest_check = action.get("latest_check") if isinstance(action.get("latest_check"), dict) else {}
    receipt_id = action.get("receipt_id") or result.get("receipt_id") or latest_check.get("receipt_id")
    evidence_ref = action.get("evidence_ref") or latest_check.get("evidence_ref")
    available = bool(receipt_id or evidence_ref or result.get("summary"))
    return {
        "available": available,
        "backend_only": True,
        "debug_only": True,
        "receipt_id": _safe_text(receipt_id, "") if receipt_id else None,
        "summary": "A backend record is kept for troubleshooting and is not loaded by the normal App Catalog UI." if available else "No backend troubleshooting record is available yet.",
    }




def _timestamp_from_text(*values: Any) -> str | None:
    """Extract a safe ISO-like UTC timestamp from known action IDs/evidence refs."""
    for value in values:
        text = _safe_text(value, "")
        if not text:
            continue
        # Existing backend values may already be ISO timestamps.
        iso_match = re.search(r"(20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", text)
        if iso_match:
            return iso_match.group(1)
        compact_match = re.search(r"(20\d{2}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})Z", text)
        if compact_match:
            date, hour, minute, second = compact_match.groups()
            return f"{date}T{hour}:{minute}:{second}Z"
    return None


def _has_backend_record(action: dict[str, Any], result: dict[str, Any]) -> bool:
    troubleshooting = action.get("troubleshooting") if isinstance(action.get("troubleshooting"), dict) else {}
    latest_check = action.get("latest_check") if isinstance(action.get("latest_check"), dict) else {}
    return bool(
        action.get("last_result")
        or action.get("evidence_ref")
        or action.get("receipt_id")
        or action.get("latest_backup_id")
        or action.get("latest_restore_preview_id")
        or result.get("summary")
        or result.get("receipt_id")
        or troubleshooting.get("available")
        or latest_check.get("summary")
        or latest_check.get("evidence_ref")
    )

def _safe_list(values: Any, fallback: list[str] | None = None, *, max_items: int = 6) -> list[str]:
    raw_items = values if isinstance(values, list) else (fallback or [])
    items: list[str] = []
    for item in raw_items:
        text = _safe_text(item, "")
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


def _last_ran_at(action: dict[str, Any]) -> str | None:
    latest_check = action.get("latest_check") if isinstance(action.get("latest_check"), dict) else {}
    for key in ("last_ran_at", "completed_at", "updated_at", "verified_at", "created_at", "started_at", "queued_at"):
        value = action.get(key) or latest_check.get(key)
        if value:
            return _safe_text(value, "")
    return _timestamp_from_text(
        action.get("evidence_ref"),
        action.get("receipt_id"),
        action.get("latest_backup_id"),
        action.get("latest_restore_preview_id"),
        latest_check.get("evidence_ref"),
        latest_check.get("operation_id"),
        latest_check.get("command_id"),
    )


def _first_ran_at(action: dict[str, Any], result: dict[str, Any]) -> str | None:
    latest_check = action.get("latest_check") if isinstance(action.get("latest_check"), dict) else {}
    for key in ("first_ran_at", "created_at", "started_at", "queued_at", "completed_at", "updated_at"):
        value = action.get(key) or latest_check.get(key)
        if value:
            return _safe_text(value, "")
    return _last_ran_at(action) if _has_backend_record(action, result) else None


def _run_count(action: dict[str, Any], result: dict[str, Any]) -> int:
    for key in ("run_count", "backup_count", "operation_count"):
        try:
            count = int(action.get(key) or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            return count
    return 1 if _has_backend_record(action, result) else 0


def _phone_storage_connected(media: Any) -> bool:
    if not isinstance(media, dict):
        return False
    try:
        mapping_count = int(media.get("mapping_count") or 0)
    except (TypeError, ValueError):
        mapping_count = 0
    labels = media.get("labels") if isinstance(media.get("labels"), list) else []
    label_text = " ".join(str(label or "").lower() for label in labels)
    if "phone storage" in label_text or "phone" in label_text:
        return True
    return mapping_count > 0 and not labels


def _apply_connect_photos_truth(actions: dict[str, Any], media: Any) -> None:
    action = actions.get("connect_photos")
    if not isinstance(action, dict):
        return
    if _phone_storage_connected(media):
        action.update({
            "enabled": False,
            "status": "connected",
            "summary": "Phone storage is connected.",
            "disabled_reason": "Phone storage is already connected.",
            "reason": "Phone storage is already connected.",
            "last_result": None,
            "first_ran_at": None,
            "last_ran_at": None,
            "run_count": 0,
        })
        action["progress"] = {"phase": "idle", "step": "Connected.", "percent": None, "indeterminate": False, "bounded": True, "steps": []}
        action["result"] = {"status": None, "summary": None, "receipt_id": None, "backend_only": True}
        action["troubleshooting"] = {
            "available": False,
            "backend_only": True,
            "debug_only": True,
            "receipt_id": None,
            "summary": "No backend troubleshooting record is needed for an already connected phone storage shortcut.",
        }


def _media_import_completed(media: Any) -> bool:
    if not isinstance(media, dict):
        return False
    last_import = media.get("last_import") if isinstance(media.get("last_import"), dict) else {}
    status = str(last_import.get("status") or media.get("last_import_status") or "").lower()
    evidence_status = str(last_import.get("evidence_status") or (media.get("evidence") or {}).get("status") or "").lower() if isinstance(media.get("evidence"), dict) else str(last_import.get("evidence_status") or "").lower()
    return bool(
        media.get("last_imported_at")
        or last_import.get("completed_at")
        or status in {"succeeded", "success", "completed", "done"}
        or evidence_status == "saved"
    )


def _apply_import_photos_truth(actions: dict[str, Any], media: Any) -> None:
    action = actions.get("import_photos")
    if not isinstance(action, dict):
        return
    if _media_import_completed(media):
        last_import = media.get("last_import") if isinstance(media, dict) and isinstance(media.get("last_import"), dict) else {}
        completed_at = last_import.get("completed_at") or (media.get("last_imported_at") if isinstance(media, dict) else None)
        action.update({
            "enabled": False,
            "status": "imported",
            "summary": "Photos are imported. PhotoPrism will handle new photos.",
            "disabled_reason": "Photos are already imported. PhotoPrism will handle new photos.",
            "reason": "Photos are already imported. PhotoPrism will handle new photos.",
            "last_result": "Photos imported",
            "first_ran_at": completed_at or action.get("first_ran_at"),
            "last_ran_at": completed_at or action.get("last_ran_at"),
            "run_count": 1,
        })
        action["progress"] = {"phase": "idle", "step": "Imported.", "percent": None, "indeterminate": False, "bounded": True, "steps": []}
        action["result"] = {"status": "imported", "summary": "Photos are imported. PhotoPrism will handle new photos.", "receipt_id": None, "backend_only": True}
        action["troubleshooting"] = {
            "available": False,
            "backend_only": True,
            "debug_only": True,
            "receipt_id": None,
            "summary": "No normal App Catalog troubleshooting view is needed after photos are imported.",
        }


def _details_payload(
    action_id: str,
    action: dict[str, Any],
    *,
    label: str,
    status: str,
    enabled: bool,
    summary: str,
    result: dict[str, Any],
    disabled_reason: Any,
) -> dict[str, Any]:
    definition = ACTION_DEFINITIONS.get(action_id, {})
    operation_details = action.get("details") if isinstance(action.get("details"), dict) else {}
    detail_definition = operation_details or ACTION_DETAIL_DEFINITIONS.get(action_id, {})
    execution_owner = action.get("execution_owner") or definition.get("execution_owner") or "backend_worker"
    result_summary = result.get("summary") if isinstance(result, dict) else None
    disabled_summary = _safe_text(disabled_reason, "") if disabled_reason and not enabled else ""
    base_summary = _safe_text(disabled_summary or result_summary or detail_definition.get("summary") or summary, "Action details are available.")
    what_happened = _safe_list(detail_definition.get("what_happened"), [base_summary])
    what_changed = _safe_list(detail_definition.get("what_changed"), ["Nothing changed."])
    what_did_not_happen = _safe_list(detail_definition.get("what_did_not_happen"), ["No unsafe action was started."])
    if not enabled and disabled_reason:
        paused_summary = _safe_text(disabled_reason, "This action is not ready yet.")
        what_happened = [f"This action is paused because {paused_summary[:1].lower()}{paused_summary[1:]}"]
        what_changed = ["Nothing changed."]
        if action_id != "remove_app":
            what_did_not_happen = ["No worker command was queued."] + [item for item in what_did_not_happen if item != "No worker command was queued."]
            what_did_not_happen = what_did_not_happen[:6]
    technical_details = _safe_list(detail_definition.get("technical_details"), [], max_items=8)
    technical_details.extend([
        f"Execution owner: {str(execution_owner).replace('_', ' ')}",
        f"Action: {action_id}",
        f"Status: {status}",
        "Backend troubleshooting records stay backend-only.",
    ])
    saved_default = bool(result.get("summary") or result.get("receipt_id") or status in TERMINAL_STATUS_VALUES)
    saved = bool(detail_definition.get("saved", saved_default)) and enabled
    details: dict[str, Any] = {
        "title": label,
        "status": status,
        "summary": base_summary,
        "what_happened": what_happened,
        "what_changed": what_changed,
        "what_did_not_happen": what_did_not_happen,
        "saved_for_troubleshooting": {
            "saved": saved,
            "backend_only": True,
            "summary": "A backend record was saved for troubleshooting." if saved else "No backend record was saved because this action did not run.",
        },
        "technical_details": technical_details[:12],
    }
    for optional_key in ("what_needs_attention", "what_would_happen_after_confirmation", "what_will_not_happen_by_default"):
        if optional_key in detail_definition:
            details[optional_key] = _safe_list(detail_definition.get(optional_key), [], max_items=6)
    return details


def _normalize_action(action_id: str, raw_action: Any) -> dict[str, Any]:
    action = raw_action if isinstance(raw_action, dict) else {}
    definition = ACTION_DEFINITIONS.get(action_id, {})
    label = _safe_text(action.get("label") or definition.get("label") or action_id.replace("_", " ").title(), "App action")
    enabled = bool(action.get("enabled", False))
    status = _normalized_status(action.get("status"), enabled=enabled)
    disabled_reason = action.get("disabled_reason") or action.get("reason")
    if not enabled and not disabled_reason:
        disabled_reason = "Action is not ready yet."
    summary = _safe_text(action.get("summary") or definition.get("summary"), "Action status is available.")
    if action_id == "update_app" and "no update" not in summary.lower():
        summary = _safe_text(f"{summary} No update is applied.", "Check whether this app is ready for a safe update. No update is applied.")
    result = _result_payload(action_id, action, status)
    troubleshooting = _troubleshooting_payload(action, result)
    category = str(action.get("category") or definition.get("category") or "setup").replace("app_setup", "setup")
    normalized = dict(action)
    first_ran_at = _first_ran_at(action, result)
    last_ran_at = _last_ran_at(action) or first_ran_at
    run_count = _run_count(action, result)
    normalized.update({
        "id": action_id,
        "app_id": "photoprism",
        "label": label,
        "category": category,
        "category_label": ACTION_CATEGORY_LABELS.get(category, "App setup"),
        "summary": summary,
        "enabled": enabled,
        "status": status,
        "disabled_reason": _safe_text(disabled_reason, "Action is not ready yet.") if disabled_reason else None,
        "reason": _safe_text(disabled_reason, "Action is not ready yet.") if disabled_reason else action.get("reason"),
        "risk": action.get("risk") or definition.get("risk") or "review",
        "confirmation_required": bool(action.get("confirmation_required") or action.get("requires_confirmation")),
        "destructive": bool(action.get("destructive") or action.get("risk") == "destructive" or definition.get("risk") == "destructive"),
        "execution_owner": action.get("execution_owner") or definition.get("execution_owner") or "backend_worker",
        "progress": _progress_payload(action_id, action, status),
        "result": result,
        "last_result": result.get("summary"),
        "first_ran_at": first_ran_at,
        "last_ran_at": last_ran_at,
        "run_count": run_count,
        "details": _details_payload(action_id, action, label=label, status=status, enabled=enabled, summary=summary, result=result, disabled_reason=disabled_reason),
        "troubleshooting": troubleshooting,
    })
    return normalized


def _action_groups(actions: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = {}
    for action_id in ACTION_ORDER:
        action = actions.get(action_id)
        if not isinstance(action, dict):
            continue
        category = str(action.get("category") or "setup")
        groups.setdefault(category, []).append(action_id)
    return [
        {
            "id": category,
            "label": ACTION_CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
            "actions": action_ids,
        }
        for category, action_ids in groups.items()
    ]


def app_actions(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    profile = lite_app_lifecycle.app_lifecycle_profile("photoprism")
    raw_actions = profile.get("actions") if isinstance(profile.get("actions"), dict) else {}
    actions: dict[str, Any] = {}
    for action_id in ACTION_ORDER:
        if action_id in raw_actions:
            actions[action_id] = _normalize_action(action_id, raw_actions[action_id])
    for action_id, action in raw_actions.items():
        if action_id not in actions:
            actions[action_id] = _normalize_action(action_id, action)
    media = profile.get("media") or lite_photoprism_media.media_status("photoprism")
    _apply_connect_photos_truth(actions, media)
    _apply_import_photos_truth(actions, media)
    return {
        "status": "healthy",
        "app_id": "photoprism",
        "name": "PhotoPrism",
        "summary": "PhotoPrism Action Center is available.",
        "actions": actions,
        "items": actions,
        "action_list": list(actions.values()),
        "action_order": list(actions.keys()),
        "action_groups": _action_groups(actions),
        "current_operation": profile.get("current_action"),
        "latest_results": {key: value.get("result") for key, value in actions.items() if isinstance(value, dict) and isinstance(value.get("result"), dict) and value["result"].get("summary")},
        "latest_troubleshooting_records": {key: value.get("troubleshooting") for key, value in actions.items() if isinstance(value, dict) and isinstance(value.get("troubleshooting"), dict) and value["troubleshooting"].get("available")},
        "media": media,
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
        disabled_reason = _safe_text(action_profile.get("disabled_reason") or action_profile.get("reason"), "This action is not ready yet.")
        raise HTTPException(
            status_code=409,
            detail={
                "status": "disabled",
                "accepted": False,
                "app_id": "photoprism",
                "action_id": action,
                "summary": disabled_reason,
                "disabled_reason": disabled_reason,
                "progress": {"phase": "blocked", "step": disabled_reason, "bounded": True},
                "troubleshooting": {"status": "not_started", "backend_only": True, "summary": "No backend record was created because the action was not started."},
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
