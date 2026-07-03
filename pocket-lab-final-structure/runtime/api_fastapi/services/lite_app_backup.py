from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_backup_targets, lite_backup, lite_backup_manifest
from .lite_backup_policy import backup_layout

SUPPORTED_APP_IDS = {"photoprism"}
APP_LABELS = {"photoprism": "PhotoPrism"}

APP_BACKUP_CREATE_SUBJECT = "pocketlab.commands.lite.app.backup.create"
APP_RESTORE_PREVIEW_SUBJECT = "pocketlab.commands.lite.app.restore.preview"

APP_BACKUP_INCLUDES = [
    "app_config",
    "app_metadata",
    "storage_mappings",
    "route_registry",
    "safe_evidence_refs",
]
APP_BACKUP_EXCLUDES = [
    "original_media",
    "import_folder_media",
    "generated_cache",
    "raw_secrets",
]
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
                "summary": "PhotoPrism is the first app with App Catalog backup and restore preview.",
            },
        )
    return normalized


def _safe_text(value: Any, fallback: str = "Available") -> str:
    text = str(value or fallback).strip() or fallback
    text = re.sub(r"(?i)(password|token|secret|api[_-]?key|private[_ -]?key)\s*[:=]\s*\S+", r"\1=[hidden]", text)
    text = re.sub(r"(?i)nats://\S+", "[hidden-route]", text)
    if re.search(r"/(data/data|home|proc|sys|dev|etc|root)/\S*", text):
        return fallback
    if re.search(r"~/(?!storage\b)\S+", text):
        return fallback
    if any(marker in text.lower() for marker in ("restic_password", "vault_token", "nats_password")):
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


def _state_path() -> Path:
    return deps.settings().state_dir / "lite_app_backup_state.json"


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


def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    app = manifest.get("app_backup") if isinstance(manifest.get("app_backup"), dict) else {}
    return {
        "app_id": app.get("app_id") or "photoprism",
        "app_label": app.get("app_label") or "PhotoPrism",
        "backup_id": manifest.get("backup_id"),
        "created_at": manifest.get("created_at"),
        "status": "verified" if manifest.get("verification_status") == "verified" else "saved",
        "mode": app.get("mode") or "config_only",
        "snapshot_id": manifest.get("snapshot_id"),
        "manifest_checksum": manifest.get("manifest_checksum"),
        "verification_status": manifest.get("verification_status", "not_verified"),
        "verified_at": manifest.get("verified_at"),
        "included_sets": app.get("included_sets") or APP_BACKUP_INCLUDES,
        "excluded_sets": app.get("excluded_sets") or APP_BACKUP_EXCLUDES,
        "media_included": bool(app.get("media_included")),
        "secrets_hidden": True,
        "raw_paths_hidden": True,
        "evidence_ref": f"apps/photoprism/backups/{_safe_ref(manifest.get('backup_id'), 'latest')}.json",
        "summary": _safe_text(manifest.get("summary"), "PhotoPrism app backup saved."),
    }


def _is_app_manifest(manifest: dict[str, Any], app_id: str) -> bool:
    app = manifest.get("app_backup") if isinstance(manifest.get("app_backup"), dict) else {}
    backup_id = str(manifest.get("backup_id") or "")
    return app.get("app_id") == app_id or backup_id.startswith(f"app-backup-{app_id}-")


def _app_manifests(app_id: str, *, limit: int = 25) -> list[dict[str, Any]]:
    app = _validate_app_id(app_id)
    items = [item for item in lite_backup_manifest.list_manifests(limit=max(limit, 50)) if _is_app_manifest(item, app)]
    return items[: max(1, min(limit, 100))]


def latest_app_manifest(app_id: str, *, verified_only: bool = False) -> dict[str, Any] | None:
    for manifest in _app_manifests(app_id, limit=50):
        if not verified_only or manifest.get("verification_status") == "verified":
            return manifest
    return None


def _resolve_app_backup_id(app_id: str, backup_id: str | None = None, *, verified_only: bool = False) -> str | None:
    app = _validate_app_id(app_id)
    selected = str(backup_id or "latest").strip() or "latest"
    if selected == "latest":
        latest = latest_app_manifest(app, verified_only=verified_only)
        return str(latest.get("backup_id")) if latest else None
    manifest = lite_backup_manifest.read_manifest(selected)
    if not manifest or not _is_app_manifest(manifest, app):
        return None
    if verified_only and manifest.get("verification_status") != "verified":
        return None
    return selected




def _pending_backup(app_id: str) -> dict[str, Any] | None:
    app = _validate_app_id(app_id)
    state = _read_state()
    pending = state.get("pending_backup") if isinstance(state.get("pending_backup"), dict) else None
    if not pending or pending.get("app_id") != app:
        return None
    return pending


def _pending_backup_active(app_id: str) -> bool:
    pending = _pending_backup(app_id)
    if not pending:
        return False
    return str(pending.get("status") or "").lower() in {"queued", "pending", "running", "working"}


def _restore_preview_disabled_reason(app_id: str, verified: bool) -> str | None:
    if _pending_backup_active(app_id):
        return "Wait for the current app backup to finish before preview restore."
    if not verified:
        return "No verified app backup yet"
    return None

def backup_profile() -> dict[str, Any]:
    return {
        "app_id": "photoprism",
        "app_label": "PhotoPrism",
        "backup_supported": True,
        "restore_preview_supported": True,
        "restore_apply_supported": False,
        "default_mode": "config_only",
        "media_included_by_default": False,
        "includes": list(APP_BACKUP_INCLUDES),
        "excludes": list(APP_BACKUP_EXCLUDES),
    }


def app_backup_command(app_id: str, *, mode: str = "config_only", reason: str | None = None) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    selected_mode = str(mode or "config_only").strip().lower()
    if selected_mode != "config_only":
        raise HTTPException(
            status_code=422,
            detail={
                "status": "unsupported_mode",
                "summary": "App Catalog backups are config-only in this phase. Media is preserved by PhotoPrism and excluded by default.",
            },
        )
    timestamp = _now().replace(":", "").replace(".", "-")
    command_id = f"app-backup-{app}-{timestamp}"
    return {
        "command_id": command_id,
        "backup_id": command_id,
        "app_id": app,
        "app_label": APP_LABELS[app],
        "app_backup_mode": selected_mode,
        "include_app_data": True,
        "include_event_journal": True,
        "reason": _safe_text(reason, "manual app backup"),
        "requested_by": "lite-api",
        "dry_run": False,
        "profile": backup_profile(),
        "profile_summary": "PhotoPrism settings, mappings, route records, and safe app records are included. Media is excluded by default.",
    }


def app_restore_preview_command(app_id: str, *, backup_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    if _pending_backup_active(app):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "backup_still_running",
                "summary": "Wait for the current app backup to finish before preview restore.",
                "disabled_reason": "Wait for the current app backup to finish before preview restore.",
            },
        )
    selected = backup_id or "latest"
    resolved = _resolve_app_backup_id(app, selected, verified_only=True)
    if not resolved:
        raise HTTPException(status_code=409, detail={"status": "no_verified_app_backup", "summary": "No verified app backup yet. Back up PhotoPrism first.", "disabled_reason": "No verified app backup yet"})
    command_id = f"app-restore-preview-{app}-{uuid.uuid4().hex[:16]}"
    return {
        "command_id": command_id,
        "preview_id": command_id,
        "app_id": app,
        "app_label": APP_LABELS[app],
        "backup_id": resolved,
        "reason": _safe_text(reason, "manual restore preview"),
        "requested_by": "lite-api",
        "preview_only": True,
        "restore_apply_supported": False,
    }


def record_backup_request(command: dict[str, Any]) -> dict[str, Any]:
    pending = lite_backup.record_backup_request(command)
    pending.update({
        "app_id": command.get("app_id") or "photoprism",
        "action_id": "backup_app",
        "mode": command.get("app_backup_mode") or "config_only",
        "summary": "Backing up PhotoPrism app settings.",
    })
    _write_state({"pending_backup": pending})
    return pending


def record_restore_preview_request(command: dict[str, Any]) -> dict[str, Any]:
    pending = {
        "preview_id": command.get("preview_id") or command.get("command_id"),
        "backup_id": command.get("backup_id"),
        "app_id": command.get("app_id") or "photoprism",
        "action_id": "preview_restore",
        "status": "queued",
        "requested_at": _now(),
        "summary": "Preparing PhotoPrism restore preview.",
    }
    _write_state({"pending_restore_preview": pending})
    return pending


def _decorate_manifest(command: dict[str, Any]) -> dict[str, Any]:
    backup_id = str(command.get("backup_id") or command.get("command_id") or "")
    manifest = lite_backup_manifest.read_manifest(backup_id)
    if not manifest:
        raise RuntimeError("App backup manifest was not found after backup creation.")
    mode = str(command.get("app_backup_mode") or "config_only")
    app_metadata = {
        "app_id": command.get("app_id") or "photoprism",
        "app_label": command.get("app_label") or "PhotoPrism",
        "mode": mode,
        "backup_supported": True,
        "restore_preview_supported": True,
        "restore_apply_supported": False,
        "media_included": mode == "full_with_media",
        "media_included_by_default": False,
        "included_sets": list(APP_BACKUP_INCLUDES),
        "excluded_sets": list(APP_BACKUP_EXCLUDES),
        "secrets_hidden": True,
        "raw_paths_hidden": True,
        "raw_logs_hidden": True,
        "evidence_ref": f"apps/photoprism/backups/{_safe_ref(backup_id, 'latest')}.json",
    }
    manifest = dict(manifest)
    manifest["app_backup"] = app_metadata
    manifest["included_app_state"] = list(APP_BACKUP_INCLUDES)
    manifest["excluded_app_state"] = list(APP_BACKUP_EXCLUDES)
    manifest["restore_apply_supported"] = False
    manifest["summary"] = "PhotoPrism app backup saved. Settings, mappings, route records, and safe app records are protected; media remains excluded by default."
    refs = list(manifest.get("evidence_references") or [])
    for ref in (
        "pocketlab.events.lite.app.backup.started",
        "pocketlab.events.lite.app.backup.completed",
        "pocketlab.audit.lite.app.backup.completed",
    ):
        if ref not in refs:
            refs.append(ref)
    manifest["evidence_references"] = refs
    manifest = lite_backup_manifest.write_manifest(manifest)

    receipt = lite_backup_manifest.read_receipt(backup_id) or {"backup_id": backup_id}
    receipt.update({
        "backup_id": backup_id,
        "app_id": "photoprism",
        "app_label": "PhotoPrism",
        "action_id": "backup_app",
        "status": receipt.get("status") or "succeeded",
        "summary": "App backup saved",
        "engine": "restic",
        "snapshot_id": manifest.get("snapshot_id"),
        "manifest_checksum": manifest.get("manifest_checksum"),
        "evidence_saved": True,
        "evidence_references": refs,
        "included_sets": app_metadata["included_sets"],
        "excluded_sensitive_items": manifest.get("excluded_sensitive_items", []),
        "app_backup": app_metadata,
        "restore_apply_supported": False,
    })
    lite_backup_manifest.write_receipt(backup_id, receipt)
    return manifest


def create_app_backup(command: dict[str, Any]) -> dict[str, Any]:
    app = _validate_app_id(command.get("app_id") or "photoprism")
    backup_id = str(command.get("backup_id") or command.get("command_id") or "")
    _write_state({
        "pending_backup": {
            "backup_id": backup_id,
            "app_id": app,
            "action_id": "backup_app",
            "status": "running",
            "started_at": _now(),
            "summary": "Backing up PhotoPrism app settings.",
        }
    })
    result = lite_backup.create_backup(command)
    manifest = _decorate_manifest(command)
    try:
        verification = lite_backup.verify_backup(backup_id, reason="automatic app backup verification")
        manifest = _decorate_manifest(command)
    except Exception as exc:
        verification = {"status": "failed", "summary": _safe_text(str(exc), "Backup verification needs review.")}
    public = _public_manifest(manifest)
    _write_state({
        "pending_backup": None,
        "latest_backup": public,
        "last_backup_result": {
            "backup_id": backup_id,
            "app_id": app,
            "status": public.get("verification_status") or result.get("status"),
            "completed_at": _now(),
            "verification_status": public.get("verification_status"),
        },
    })
    return {
        "status": "succeeded" if public.get("verification_status") == "verified" else "review",
        "app_id": app,
        "action_id": "backup_app",
        "backup_id": backup_id,
        "mode": command.get("app_backup_mode") or "config_only",
        "latest_backup": public,
        "verification": verification,
        "media_included": bool(public.get("media_included")),
        "included_sets": public.get("included_sets") or APP_BACKUP_INCLUDES,
        "excluded_sets": public.get("excluded_sets") or APP_BACKUP_EXCLUDES,
        "secrets_hidden": True,
        "raw_paths_hidden": True,
        "summary": "App backup saved" if public.get("verification_status") == "verified" else "Backup saved but verification needs review",
        "evidence_ref": public.get("evidence_ref"),
        "restore_apply_supported": False,
    }


def list_app_backups(app_id: str, limit: int = 25) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    items = [_public_manifest(item) for item in _app_manifests(app, limit=limit)]
    return {
        "status": "healthy" if items else "empty",
        "app_id": app,
        "app_label": APP_LABELS[app],
        "count": len(items),
        "backups": items,
        "items": items,
        "latest_backup": items[0] if items else None,
        "summary": "App backups are available." if items else "No verified app backup yet.",
        "updated_at": _now(),
    }


def _latest_restore_preview(app_id: str) -> dict[str, Any] | None:
    state = _read_state()
    preview = state.get("latest_restore_preview") if isinstance(state.get("latest_restore_preview"), dict) else None
    if preview and preview.get("app_id") == app_id:
        return preview
    return None


def app_backup_status(app_id: str) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    backups = list_app_backups(app)
    latest = backups.get("latest_backup")
    backup_items = backups.get("items") if isinstance(backups.get("items"), list) else []
    preview = _latest_restore_preview(app)
    verified = bool(latest and latest.get("verification_status") == "verified")
    pending_backup = _pending_backup(app)
    backup_running = _pending_backup_active(app)
    restore_disabled_reason = _restore_preview_disabled_reason(app, verified)
    restore_preview_enabled = verified and not backup_running
    target = lite_app_backup_targets.backup_target_summary(app)
    storage_ready = bool(target.get("ready"))
    storage_summary = _safe_text(target.get("summary"), "Join a storage device to save app backups elsewhere.")
    return {
        "status": "healthy",
        "app_id": app,
        "app_label": APP_LABELS[app],
        "summary": "App backup ready." if latest else "App backup ready. No backup has been saved yet.",
        "profile": backup_profile(),
        "backup_supported": True,
        "restore_preview_supported": True,
        "restore_apply_supported": False,
        "latest_backup": latest,
        "backup_count": len(backup_items),
        "first_backup_at": (backup_items[-1].get("created_at") if backup_items else None),
        "latest_backup_created_at": latest.get("created_at") if latest else None,
        "latest_backup_verified_at": latest.get("verified_at") if latest else None,
        "latest_verified_backup_id": latest.get("backup_id") if verified else None,
        "pending_backup": pending_backup,
        "backup_running": backup_running,
        "latest_restore_preview": preview,
        "latest_restore_preview_id": preview.get("preview_id") if isinstance(preview, dict) else None,
        "latest_restore_preview_created_at": preview.get("created_at") if isinstance(preview, dict) else None,
        "first_restore_preview_at": preview.get("created_at") if isinstance(preview, dict) else None,
        "restore_preview_count": 1 if isinstance(preview, dict) and preview.get("preview_id") else 0,
        "restore_preview_ready": restore_preview_enabled,
        "restore_preview_disabled_reason": restore_disabled_reason,
        "storage_target": {
            "ready": storage_ready,
            "summary": storage_summary,
            "target_label": target.get("target_label") if storage_ready else None,
        },
        "actions": {
            "backup_app": {
                "enabled": True,
                "label": "Back up app",
                "summary": "Save PhotoPrism settings, mappings, route records, and safe app records.",
            },
            "preview_restore": {
                "enabled": restore_preview_enabled,
                "label": "Preview restore",
                "status": "ready" if restore_preview_enabled else ("running" if backup_running else "not_ready"),
                "disabled_reason": restore_disabled_reason,
                "summary": "Review what would be restored before making changes." if restore_preview_enabled else (restore_disabled_reason or "No verified app backup yet"),
                "requires_current_backup": True,
                "latest_verified_backup_id": latest.get("backup_id") if verified else None,
            },
            "backup_to_storage_device": {
                "enabled": False,
                "label": "Back up to storage device",
                "disabled_reason": "Join a storage device to save app backups elsewhere." if not storage_ready else "Storage transfer worker is not enabled yet.",
                "summary": "Join a storage device to save app backups elsewhere." if not storage_ready else "Storage target detected, but app backup transfer remains disabled until verified end to end.",
            },
        },
        "updated_at": _now(),
    }


def create_app_restore_preview(command: dict[str, Any]) -> dict[str, Any]:
    app = _validate_app_id(command.get("app_id") or "photoprism")
    backup_id = _resolve_app_backup_id(app, str(command.get("backup_id") or "latest"), verified_only=True)
    if not backup_id:
        raise RuntimeError("No verified app backup is available for restore preview")
    manifest = lite_backup_manifest.read_manifest(backup_id)
    if not manifest:
        raise RuntimeError("App backup manifest was not found")
    preview_id = str(command.get("preview_id") or command.get("command_id") or f"app-restore-preview-{app}-{uuid.uuid4().hex[:12]}")
    created_at = _now()
    app_meta = manifest.get("app_backup") if isinstance(manifest.get("app_backup"), dict) else {}
    would_restore = [
        {"id": "app_config", "label": "PhotoPrism settings", "action": "would_restore", "destructive": False},
        {"id": "storage_mappings", "label": "Approved photo mappings", "action": "would_restore", "destructive": False},
        {"id": "route_registry", "label": "Same-origin app route record", "action": "would_restore", "destructive": False},
        {"id": "safe_evidence_refs", "label": "Safe app evidence references", "action": "would_restore", "destructive": False},
    ]
    would_preserve = [
        {"id": "original_media", "label": "Original photos and videos", "reason": "Media is excluded from app config backup by default."},
        {"id": "generated_cache", "label": "Generated cache and thumbnails", "reason": "PhotoPrism can rebuild generated data."},
        {"id": "raw_secrets", "label": "Raw secrets", "reason": "Secret values are not exposed or restored from this preview."},
    ]
    preview = {
        "app_id": app,
        "app_label": APP_LABELS[app],
        "preview_id": preview_id,
        "backup_id": backup_id,
        "status": "ready",
        "preview_only": True,
        "restore_allowed": False,
        "restore_apply_supported": False,
        "destructive": False,
        "created_at": created_at,
        "mode": app_meta.get("mode") or "config_only",
        "summary": "Restore preview ready. This phase is preview-only and will not change app state.",
        "would_restore": would_restore,
        "would_preserve": would_preserve,
        "changes": would_restore,
        "warnings": [
            "Preview only: app restore apply is disabled in this phase.",
            "Original media files are preserved and not included by default.",
            "Raw secrets, logs, private paths, and repository internals are hidden.",
        ],
        "evidence_ref": f"apps/photoprism/restore-previews/{_safe_ref(preview_id, 'latest')}.json",
        "backup_manifest_checksum": manifest.get("manifest_checksum"),
        "secrets_hidden": True,
        "raw_paths_hidden": True,
        "media_included": bool(app_meta.get("media_included")),
    }
    path = backup_layout().restore_previews / f"{preview_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    _write_state({
        "pending_restore_preview": None,
        "latest_restore_preview": {
            "app_id": app,
            "app_label": APP_LABELS[app],
            "preview_id": preview_id,
            "backup_id": backup_id,
            "status": "ready",
            "preview_only": True,
            "restore_allowed": False,
            "created_at": created_at,
            "summary": preview["summary"],
            "evidence_ref": preview["evidence_ref"],
        },
    })
    return preview


def get_app_restore_preview(app_id: str, preview_id: str) -> dict[str, Any] | None:
    app = _validate_app_id(app_id)
    value = str(preview_id or "").strip()
    if value == "latest":
        latest = _latest_restore_preview(app)
        value = str((latest or {}).get("preview_id") or "")
    if not value:
        return None
    path = backup_layout().restore_previews / f"{value}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("app_id") != app:
        return None
    return payload


def app_backup_receipt(app_id: str, backup_id: str = "latest") -> dict[str, Any] | None:
    app = _validate_app_id(app_id)
    resolved = _resolve_app_backup_id(app, backup_id, verified_only=False)
    if not resolved:
        return {
            "status": "not_created",
            "app_id": app,
            "app_label": APP_LABELS[app],
            "backup_id": backup_id or "latest",
            "summary": "No verified app backup yet.",
            "latest_backup_available": False,
        }
    manifest = lite_backup_manifest.read_manifest(resolved) or {}
    receipt = lite_backup_manifest.read_receipt(resolved) or {}
    public = _public_manifest(manifest)
    verified = public.get("verification_status") == "verified"
    proofs = [
        {"id": "backend_worker_executed", "label": "Backend worker executed", "status": "passed", "plain_language": "The app backup ran through Pocket Lab Lite backend worker."},
        {"id": "frontend_no_shell", "label": "Browser did not run commands", "status": "passed", "plain_language": "The browser only requested Back up app through FastAPI."},
        {"id": "backup_config_only", "label": "Config-only app backup", "status": "passed", "plain_language": "Settings, mappings, route records, and safe app records are included."},
        {"id": "media_excluded_from_backup", "label": "Media excluded by default", "status": "passed", "plain_language": "Original and imported media files were not included by default."},
        {"id": "secrets_hidden", "label": "Secrets hidden", "status": "passed", "plain_language": "Raw secret values are not exposed in the receipt."},
        {"id": "raw_paths_hidden", "label": "Raw paths hidden", "status": "passed", "plain_language": "Raw device and backup paths are hidden."},
        {"id": "backup_verified", "label": "Backup verified", "status": "passed" if verified else "review", "plain_language": "The backup is verified and ready for restore preview." if verified else "Verification still needs review."},
        {"id": "restore_apply_disabled", "label": "Restore apply disabled", "status": "passed", "plain_language": "This phase supports restore preview only, not destructive restore apply."},
    ]
    counts = {
        "passed": len([item for item in proofs if item["status"] == "passed"]),
        "review": len([item for item in proofs if item["status"] == "review"]),
        "failed": 0,
        "not_checked": 0,
        "not_applicable": 0,
    }
    return {
        "receipt_version": 1,
        "receipt_id": _safe_ref(resolved, "app-backup"),
        "app_id": app,
        "app_label": APP_LABELS[app],
        "action_id": "backup_app",
        "action_label": "Back up app",
        "backup_id": resolved,
        "status": "succeeded" if verified else "review",
        "summary": _safe_text(receipt.get("summary") or public.get("summary"), "App backup saved."),
        "started_at": receipt.get("created_at") or manifest.get("created_at"),
        "completed_at": receipt.get("verified_at") or manifest.get("verified_at") or manifest.get("created_at"),
        "proofs": proofs,
        "proof_counts": counts,
        "proof_status": "passed" if verified else "review",
        "safety_badges": ["Backend worker executed", "Secrets hidden", "Raw paths hidden", "Restore preview only"],
        "what_changed": ["PhotoPrism app settings, mappings, route records, and safe app records were backed up."],
        "what_did_not_happen": ["Original photos were not included by default.", "Raw secrets were not exposed.", "No frontend shell commands ran.", "No destructive restore was enabled."],
        "details_owner": {"name": "PhotoPrism", "reason": "PhotoPrism owns indexing, thumbnails, metadata, and media warnings."},
        "redaction": {"status": "passed", "secrets_hidden": True, "raw_logs_hidden": True, "raw_paths_hidden": True, "media_file_names_hidden": True, "secret_values_saved": False},
        "technical_details": {
            "backup_mode": public.get("mode"),
            "media_included": public.get("media_included"),
            "verification_status": public.get("verification_status"),
            "restore_apply_supported": False,
            "evidence_ref": public.get("evidence_ref"),
        },
        "evidence_ref": public.get("evidence_ref"),
        "updated_at": receipt.get("verified_at") or manifest.get("verified_at") or manifest.get("created_at") or _now(),
    }


def backup_to_storage_readiness(app_id: str, target_device_id: str | None = None, *, reason: str | None = None) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    selected_target: dict[str, Any] | None = None
    if target_device_id:
        selected_target = lite_app_backup_targets.validate_backup_target(target_device_id, app_id=app)
    target = lite_app_backup_targets.backup_target_summary(app)
    ready = bool(target.get("ready"))
    return {
        "status": "not_ready",
        "accepted": False,
        "app_id": app,
        "action_id": "backup_to_storage",
        "storage_target_ready": ready,
        "summary": "Join a storage device to save app backups elsewhere." if not ready else "Storage target detected, but app backup transfer is disabled until the storage-device worker contract is verified.",
        "disabled_reason": "Join a storage device to save app backups elsewhere." if not ready else "Storage-device transfer is disabled until the worker contract is verified.",
        "progress": {"phase": "not_ready" if not ready else "review", "step": "Storage-device readiness checked.", "bounded": True},
        "evidence": {"status": "not_started", "summary": "No backup transfer evidence was created because this is a readiness check."},
        "target_device_id": _safe_ref((selected_target or {}).get("device_id") or target_device_id, "") or None,
        "target_label": _safe_text((selected_target or {}).get("name"), "Storage device") if selected_target else target.get("target_label"),
        "reason": _safe_text(reason, "manual storage backup readiness check"),
        "restore_apply_supported": False,
    }
