from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_profiles, lite_app_storage, lite_catalog, lite_catalog_live, lite_photoprism_media

SUPPORTED_APP_IDS = {"photoprism"}
_SAFE_ROUTE = "/apps/photoprism/"
_SECRET_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "private_key",
    "credential",
    "vault",
    "nats",
    "restic",
    "admin_password",
)

_STATUS_ORDER = {
    "ready": 0,
    "checking": 1,
    "review": 2,
    "offline": 3,
    "needs_attention": 4,
    "unavailable": 5,
    "unknown": 6,
}


def _now() -> str:
    return deps.now_utc_iso()


def _validate_app_id(app_id: Any) -> str:
    normalized = str(app_id or "").strip().lower().replace("_", "-")
    if normalized not in SUPPORTED_APP_IDS:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_app",
                "summary": "PhotoPrism is the first app with a Lite lifecycle profile.",
            },
        )
    return normalized


def _safe_text(value: Any, fallback: str = "Available") -> str:
    text = str(value or fallback).strip() or fallback
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return fallback
    if (text.startswith("/") or text.startswith("~")) and "/apps/" not in text:
        return fallback
    return text[:220]


def _safe_label(value: Any, fallback: str = "Available") -> str:
    text = _safe_text(value, fallback)
    if "/" in text and not text.startswith("/apps/"):
        return fallback
    return text[:80]


def _catalog_payload() -> dict[str, Any]:
    payload = lite_catalog.catalog_payload()
    try:
        payload = lite_catalog_live.hydrate_catalog(payload)
    except Exception:
        pass
    return payload if isinstance(payload, dict) else {}


def _catalog_app(app_id: str) -> dict[str, Any]:
    payload = _catalog_payload()
    for app in payload.get("apps") or payload.get("items") or []:
        if isinstance(app, dict) and str(app.get("id") or "").lower() == app_id:
            return app
    return {}


def _storage_payload() -> dict[str, Any]:
    try:
        payload = lite_app_storage.list_mappings("photoprism")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {"mappings": [], "count": 0, "summary": "No media folders connected yet."}


def _security_payload() -> dict[str, Any]:
    try:
        payload = lite_app_profiles.app_security_profile("photoprism")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {"status": "unknown", "summary": "App safety status is not available yet.", "evidence": {"count": 0}}


def _backup_payload() -> dict[str, Any]:
    try:
        payload = lite_app_profiles.app_backup_profile("photoprism")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {"status": "unknown", "summary": "App backup status is not available yet.", "evidence": {"count": 0}}


def _media_payload() -> dict[str, Any]:
    try:
        payload = lite_photoprism_media.media_status("photoprism")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {
            "status": "unknown",
            "summary": "PhotoPrism media status is not available yet.",
            "mapping_count": 0,
        }


def _normalize_lifecycle_status(value: Any) -> str:
    raw = str(value or "unknown").strip().lower().replace("-", "_")
    if raw in {"ready", "healthy", "protected", "passed", "saved", "installed", "online"}:
        return "ready"
    if raw in {"queued", "running", "checking", "installing", "pending", "unknown", "not_checked"}:
        return "checking"
    if raw in {"review", "needs_review", "degraded", "partial", "not_connected"}:
        return "review"
    if raw in {"failed", "unhealthy", "error", "blocked", "needs_attention"}:
        return "needs_attention"
    if raw in {"offline", "stale", "disconnected"}:
        return "offline"
    if raw in {"unavailable", "not_installed", "unsupported"}:
        return "unavailable"
    return "unknown"


def _host_device(app: dict[str, Any], installed: bool) -> dict[str, Any]:
    name = _safe_label(app.get("host_device_name") or "Pocket Lab Lite Server", "Pocket Lab Lite Server")
    device_id = _safe_label(app.get("host_device_id") or "pocket-lab-lite-server", "pocket-lab-lite-server")
    status = "online" if installed else "unknown"
    return {
        "id": device_id,
        "name": name,
        "label": "Runs on Server Phone" if name == "Pocket Lab Lite Server" else f"Runs on {name}",
        "status": status,
    }


def _storage_profile(storage: dict[str, Any]) -> dict[str, Any]:
    mappings = [item for item in storage.get("mappings") or [] if isinstance(item, dict)]
    labels = [_safe_label(item.get("label") or item.get("source_label"), "Media folder") for item in mappings]
    labels = [label for label in labels if label]
    count = int(storage.get("count") or len(mappings) or 0)
    connected = count > 0
    return {
        "status": "connected" if connected else "not_connected",
        "summary": _safe_text(storage.get("summary"), "Media connected" if connected else "Media not connected"),
        "mapping_count": count,
        "labels": labels[:6],
    }


def _security_profile(security: dict[str, Any]) -> dict[str, Any]:
    evidence = security.get("evidence") if isinstance(security.get("evidence"), dict) else {}
    status = _normalize_lifecycle_status(security.get("status"))
    protected = status == "ready"
    return {
        "status": "protected" if protected else status,
        "summary": "Protected app" if protected else _safe_text(security.get("summary"), "Check app safety."),
        "evidence_status": _safe_label(evidence.get("status"), "pending"),
        "last_checked_at": security.get("last_checked_at"),
    }


def _backup_profile(backup: dict[str, Any]) -> dict[str, Any]:
    target = backup.get("backup_target") if isinstance(backup.get("backup_target"), dict) else {}
    media = backup.get("media") if isinstance(backup.get("media"), dict) else {}
    status = _normalize_lifecycle_status(backup.get("status"))
    return {
        "status": status,
        "summary": "Backup ready" if status == "ready" else _safe_text(backup.get("summary"), "Backup profile needs review."),
        "default_mode": _safe_label(backup.get("default_mode"), "config_only"),
        "media": _safe_label(media.get("default"), "excluded"),
        "target_available": bool(target.get("ready") or target.get("available")),
        "target_ready": bool(target.get("ready")),
        "target_summary": _safe_text(target.get("summary") or target.get("label"), "Backup target not ready"),
    }


def _recovery_profile(backup: dict[str, Any]) -> dict[str, Any]:
    restore = backup.get("restore") if isinstance(backup.get("restore"), dict) else {}
    preview = bool(restore.get("preview_available"))
    return {
        "status": "ready" if preview else "review",
        "summary": _safe_text(restore.get("summary"), "Restore preview not ready" if not preview else "Restore preview available"),
        "preview_available": preview,
        "restore_available": bool(restore.get("restore_available")),
    }


def _action(enabled: bool, label: str, *, url: str | None = None, reason: str | None = None, summary: str | None = None, status: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"enabled": bool(enabled), "label": label}
    if url and url.startswith("/apps/"):
        payload["url"] = url
    if reason:
        payload["reason"] = _safe_text(reason, "Action not ready")
    if summary:
        payload["summary"] = _safe_text(summary, "Action status is available.")
    if status:
        payload["status"] = _safe_label(status, "available")
    return payload


def _media_action_ready(installed: bool, route_enabled: bool, media: dict[str, Any]) -> tuple[bool, str | None, str]:
    if not installed:
        return False, "Install PhotoPrism first.", "unavailable"
    if not route_enabled:
        return False, "PhotoPrism is not ready yet.", "unavailable"
    if media.get("operation_running"):
        return False, "PhotoPrism media action is already running.", "running"
    if int(media.get("mapping_count") or 0) < 1:
        return False, "Connect a photo folder first.", "not_ready"
    return True, None, "ready"


def _actions(app: dict[str, Any], installed: bool, backup: dict[str, Any], recovery: dict[str, Any], media: dict[str, Any]) -> dict[str, Any]:
    access = app.get("access") if isinstance(app.get("access"), dict) else {}
    actions = app.get("actions") if isinstance(app.get("actions"), dict) else {}
    open_url = access.get("open_url") or (app.get("runtime") or {}).get("url")
    route_enabled = bool(actions.get("open") and open_url == _SAFE_ROUTE)
    backup_enabled = bool(installed)
    media_ready, media_reason, media_status = _media_action_ready(installed, route_enabled, media)
    return {
        "open": _action(route_enabled, "Open", url=_SAFE_ROUTE if route_enabled else None, reason=None if route_enabled else "Open is not ready yet."),
        "open_full_screen": _action(route_enabled, "Open full screen", url=_SAFE_ROUTE if route_enabled else None, reason=None if route_enabled else "Open full screen is not ready yet."),
        "install_to_phone": _action(route_enabled, "Install to phone", url=_SAFE_ROUTE if route_enabled else None, reason=None if route_enabled else "Install to phone is available after Open is ready."),
        "connect_photos": _action(installed, "Connect photos", reason=None if installed else "Install PhotoPrism first."),
        "check_app": _action(False, "Check app", reason="Use Run Safety Check for the current device-wide scan."),
        "backup_app": _action(backup_enabled, "Back up app", reason=None if backup_enabled else "Install PhotoPrism first."),
        "preview_restore": _action(bool(recovery.get("preview_available")), "Preview restore", reason=None if recovery.get("preview_available") else "No verified app backup yet"),
        "import_photos": _action(
            media_ready,
            "Import photos",
            reason=media_reason,
            summary="Import connected photos into PhotoPrism.",
            status=media_status,
        ),
        "index_photos": _action(
            media_ready,
            "Index photos",
            reason=media_reason,
            summary="Update PhotoPrism with connected media.",
            status=media_status,
        ),
    }


def _attention(installed: bool, storage: dict[str, Any], security: dict[str, Any], backup: dict[str, Any], recovery: dict[str, Any], media: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not installed:
        items.append({
            "id": "app_not_installed",
            "area": "apps",
            "severity": "review",
            "title": "App not installed",
            "summary": "Install PhotoPrism before checking app protection and recovery.",
        })
        return items
    if int(storage.get("mapping_count") or 0) < 1:
        items.append({
            "id": "media_not_connected",
            "area": "storage",
            "severity": "info",
            "title": "Media not connected",
            "summary": "Connect a photo folder to start using PhotoPrism.",
        })
    if _normalize_lifecycle_status(security.get("status")) not in {"ready"} and security.get("status") != "protected":
        items.append({
            "id": "security_not_ready",
            "area": "security",
            "severity": "review",
            "title": "App safety needs review",
            "summary": "Run a safety check to refresh app evidence.",
        })
    if not backup.get("target_available"):
        items.append({
            "id": "backup_target_missing",
            "area": "backup",
            "severity": "review",
            "title": "Backup target not ready",
            "summary": "Join a storage device to save app backups elsewhere.",
        })
    if str(media.get("status") or "") in {"running"}:
        items.append({
            "id": "media_action_running",
            "area": "media",
            "severity": "info",
            "title": "Indexing",
            "summary": "PhotoPrism media action is running through Pocket Lab.",
        })
    if str(media.get("status") or "") in {"review"}:
        items.append({
            "id": "media_action_review",
            "area": "media",
            "severity": "review",
            "title": "Photo action needs review",
            "summary": "Check the latest media action before running it again.",
        })
    if not recovery.get("preview_available"):
        items.append({
            "id": "restore_preview_not_ready",
            "area": "recovery",
            "severity": "info",
            "title": "Restore preview not ready",
            "summary": "App-specific restore preview will appear after verified app backup support is enabled.",
        })
    return items


def _overall_status(installed: bool, attention: list[dict[str, str]]) -> str:
    if not installed:
        return "unavailable"
    if any(item.get("severity") == "needs_attention" for item in attention):
        return "needs_attention"
    if any(item.get("severity") == "review" for item in attention):
        return "review"
    return "ready"


def _evidence(security: dict[str, Any], backup: dict[str, Any], media: dict[str, Any] | None = None) -> dict[str, Any]:
    sec = security.get("evidence") if isinstance(security.get("evidence"), dict) else {}
    rec = backup.get("evidence") if isinstance(backup.get("evidence"), dict) else {}
    security_count = int(sec.get("count") or 0)
    backup_count = int(rec.get("count") or 0)
    media_evidence = media.get("evidence") if isinstance(media, dict) and isinstance(media.get("evidence"), dict) else {}
    media_count = int(media_evidence.get("count") or 0)
    total = security_count + backup_count + media_count
    return {
        "status": "saved" if total else "pending",
        "summary": "Safety, recovery, and media records saved" if total else "Evidence pending",
        "security_count": security_count,
        "backup_count": backup_count,
        "media_count": media_count,
    }


def photoprism_lifecycle_profile() -> dict[str, Any]:
    app = _catalog_app("photoprism")
    storage_raw = _storage_payload()
    security_raw = _security_payload()
    backup_raw = _backup_payload()
    media = _media_payload()
    installed = bool(app.get("installed") or app.get("install_state") == "installed" or app.get("status") == "ready")

    storage = _storage_profile(storage_raw)
    security = _security_profile(security_raw)
    backup = _backup_profile(backup_raw)
    recovery = _recovery_profile(backup_raw)
    attention = _attention(installed, storage, security, backup, recovery, media)
    status = _overall_status(installed, attention)
    summary = (
        "PhotoPrism is ready, protected, and recoverable."
        if status == "ready"
        else "PhotoPrism needs attention."
        if installed
        else "Install PhotoPrism to start app lifecycle tracking."
    )
    return {
        "app_id": "photoprism",
        "name": "PhotoPrism",
        "installed": installed,
        "status": status,
        "summary": summary,
        "host_device": _host_device(app, installed),
        "storage": storage,
        "security": security,
        "backup": backup,
        "recovery": recovery,
        "media": media,
        "attention": attention,
        "actions": _actions(app, installed, backup, recovery, media),
        "evidence": _evidence(security_raw, backup_raw, media),
        "updated_at": _now(),
    }


def app_lifecycle_profile(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    return photoprism_lifecycle_profile()


def app_lifecycle_profiles() -> dict[str, Any]:
    profiles = [photoprism_lifecycle_profile()]
    ready = sum(1 for item in profiles if item.get("status") == "ready")
    attention = sum(1 for item in profiles if item.get("attention"))
    return {
        "status": "healthy",
        "summary": "Unified App Lifecycle profiles are available.",
        "apps": profiles,
        "items": profiles,
        "count": len(profiles),
        "ready_count": ready,
        "attention_count": attention,
        "updated_at": _now(),
    }


def hydrate_catalog_lifecycle(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    profile = photoprism_lifecycle_profile()
    for key in ("apps", "items"):
        apps = payload.get(key)
        if not isinstance(apps, list):
            continue
        for app in apps:
            if isinstance(app, dict) and str(app.get("id") or "").lower() == "photoprism":
                app["lifecycle"] = profile
                app["lifecycle_summary"] = {
                    "status": profile["status"],
                    "summary": profile["summary"],
                    "host": profile["host_device"].get("label"),
                    "storage": profile["storage"].get("summary"),
                    "security": profile["security"].get("summary"),
                    "backup": profile["backup"].get("summary"),
                    "media": profile.get("media", {}).get("summary"),
                    "last_indexed_at": profile.get("media", {}).get("last_indexed_at"),
                    "attention_count": len(profile.get("attention") or []),
                }
    return payload
