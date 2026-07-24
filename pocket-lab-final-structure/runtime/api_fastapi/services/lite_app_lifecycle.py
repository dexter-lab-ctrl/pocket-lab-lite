from __future__ import annotations

from typing import Any, Callable

import concurrent.futures
import logging
import os
import sys
import threading
import time

from fastapi import HTTPException

from .. import deps
from . import lite_app_backup_targets, lite_app_operations, lite_app_profiles, lite_app_storage, lite_app_update, lite_catalog, lite_catalog_live, lite_photoprism_lifecycle, lite_photoprism_media, lite_recovery_subprojections
from .lite_control_plane_store import CONTROL_PLANE

_LOGGER = logging.getLogger(__name__)
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



def _timed_stage(
    timings: dict[str, float] | None,
    name: str,
    callback: Callable[[], Any],
) -> Any:
    started = time.monotonic()
    try:
        return callback()
    finally:
        if timings is not None:
            timings[name] = round(max(0.0, (time.monotonic() - started) * 1000.0), 3)



_SUBPROJECTION_LOCK = threading.RLock()

def _app_subprojection_workers() -> int:
    configured = os.environ.get("POCKETLAB_LITE_APP_SUBPROJECTION_WORKERS", "").strip()
    if configured:
        try:
            return max(1, min(4, int(configured)))
        except ValueError:
            pass
    prefix = os.environ.get("PREFIX", "").lower()
    return 3 if "com.termux" in prefix or sys.platform == "android" else 4


_SUBPROJECTION_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=_app_subprojection_workers(), thread_name_prefix="pocketlab-app-subprojection"
)

def _app_stage_workers() -> int:
    configured = os.environ.get("POCKETLAB_LITE_APP_STAGE_WORKERS", "").strip()
    if configured:
        try:
            return max(1, min(3, int(configured)))
        except ValueError:
            pass
    prefix = os.environ.get("PREFIX", "").lower()
    return 2 if "com.termux" in prefix or sys.platform == "android" else 3


_STAGE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=_app_stage_workers(), thread_name_prefix="pocketlab-app-stage"
)
_STAGE_INFLIGHT_LOCK = threading.Lock()
_STAGE_INFLIGHT: set[concurrent.futures.Future[Any]] = set()


def _track_stage_future(future: concurrent.futures.Future[Any]) -> None:
    with _STAGE_INFLIGHT_LOCK:
        _STAGE_INFLIGHT.add(future)

    def completed(done: concurrent.futures.Future[Any]) -> None:
        with _STAGE_INFLIGHT_LOCK:
            _STAGE_INFLIGHT.discard(done)

    future.add_done_callback(completed)


def _stage_work_busy() -> bool:
    with _STAGE_INFLIGHT_LOCK:
        return any(not future.done() for future in _STAGE_INFLIGHT)


def _app_stage_deadline_seconds() -> float:
    configured = os.environ.get("POCKETLAB_LITE_APP_STAGE_DEADLINE_SECONDS", "1.5").strip()
    try:
        return max(0.25, min(4.0, float(configured)))
    except (TypeError, ValueError):
        return 1.5


def _stage_timeout_payload(fallback: Any, *, refresh_pending: bool) -> dict[str, Any]:
    value = dict(fallback) if isinstance(fallback, dict) else {}
    value["read_degraded"] = True
    value["refresh_pending"] = bool(refresh_pending)
    return value
_RECONCILE_LOCK = threading.RLock()
_RECONCILE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="pocketlab-app-reconcile"
)
_RECONCILE_FUTURE: concurrent.futures.Future[Any] | None = None
_RECONCILE_NEXT_ALLOWED = 0.0
_RECONCILE_FAILURES = 0
_SUBPROJECTION_VALUES: dict[str, tuple[dict[str, Any], float]] = {}
_SUBPROJECTION_FUTURES: dict[str, concurrent.futures.Future[Any]] = {}
_SUBPROJECTION_FAILURES: dict[str, int] = {}
_SUBPROJECTION_NEXT_ALLOWED: dict[str, float] = {}


def _subprojection_done(name: str, future: concurrent.futures.Future[Any]) -> None:
    try:
        value = future.result()
        if not isinstance(value, dict):
            raise TypeError("Subprojection must return a mapping")
    except Exception as exc:
        with _SUBPROJECTION_LOCK:
            failures = min(8, _SUBPROJECTION_FAILURES.get(name, 0) + 1)
            _SUBPROJECTION_FAILURES[name] = failures
            _SUBPROJECTION_NEXT_ALLOWED[name] = time.monotonic() + min(300.0, 2.0 ** failures)
            _SUBPROJECTION_FUTURES.pop(name, None)
        _LOGGER.warning(
            "pocketlab.app_subprojection.refresh_degraded key=%s error_type=%s",
            name, type(exc).__name__,
        )
        return
    with _SUBPROJECTION_LOCK:
        _SUBPROJECTION_VALUES[name] = (value, time.monotonic())
        _SUBPROJECTION_FAILURES[name] = 0
        _SUBPROJECTION_NEXT_ALLOWED[name] = time.monotonic() + 30.0
        _SUBPROJECTION_FUTURES.pop(name, None)


def _cached_subprojection(
    name: str,
    callback: Callable[[], dict[str, Any]],
    fallback: dict[str, Any],
    *,
    wait_seconds: float,
    ttl_seconds: float = 300.0,
) -> dict[str, Any]:
    now = time.monotonic()
    with _SUBPROJECTION_LOCK:
        cached = _SUBPROJECTION_VALUES.get(name)
        future = _SUBPROJECTION_FUTURES.get(name)
        allowed = now >= _SUBPROJECTION_NEXT_ALLOWED.get(name, 0.0)
        if cached is not None and now - cached[1] <= ttl_seconds:
            return dict(cached[0])
        if future is None and allowed:
            future = _SUBPROJECTION_EXECUTOR.submit(callback)
            _SUBPROJECTION_FUTURES[name] = future
            future.add_done_callback(lambda completed, key=name: _subprojection_done(key, completed))
    if future is not None:
        try:
            value = future.result(timeout=max(0.01, wait_seconds))
            return dict(value) if isinstance(value, dict) else dict(fallback)
        except concurrent.futures.TimeoutError:
            pass
        except Exception:
            pass
    if cached is not None:
        stale = dict(cached[0])
        stale["read_degraded"] = True
        stale["refresh_pending"] = future is not None
        return stale
    degraded = dict(fallback)
    degraded["read_degraded"] = True
    degraded["refresh_pending"] = future is not None
    return degraded


def app_security_subprojection() -> dict[str, Any]:
    return _cached_subprojection(
        "photoprism:security", _security_payload,
        {"status": "unknown", "summary": "App safety status is refreshing.", "evidence": {"count": 0}},
        wait_seconds=1.5, ttl_seconds=300.0,
    )


def app_backup_subprojection() -> dict[str, Any]:
    return _cached_subprojection(
        "photoprism:backup", _backup_payload,
        {"status": "unknown", "summary": "App backup status is refreshing.", "evidence": {"count": 0}},
        wait_seconds=1.5, ttl_seconds=300.0,
    )


def app_runtime_subprojection() -> dict[str, Any]:
    return _cached_subprojection(
        "photoprism:runtime", lite_photoprism_lifecycle.lifecycle_state,
        {"status": "unknown", "summary": "App runtime status is refreshing."},
        wait_seconds=1.0, ttl_seconds=120.0,
    )


def invalidate_app_subprojections(*areas: str) -> None:
    """Drop bounded app read projections after backend-owned state changes."""
    aliases = {
        "backup": "photoprism:backup",
        "security": "photoprism:security",
        "runtime": "photoprism:runtime",
    }
    names = {
        aliases.get(
            str(area or "").strip().lower(),
            str(area or "").strip(),
        )
        for area in areas
    }
    names.discard("")

    with _SUBPROJECTION_LOCK:
        for name in names:
            _SUBPROJECTION_VALUES.pop(name, None)
            _SUBPROJECTION_NEXT_ALLOWED[name] = 0.0


def _prime_app_subprojections() -> None:
    starters = (
        ("photoprism:security", _security_payload, {"status": "unknown"}),
        ("photoprism:backup", _backup_payload, {"status": "unknown"}),
        ("photoprism:runtime", lite_photoprism_lifecycle.lifecycle_state, {"status": "unknown"}),
    )
    for name, callback, fallback in starters:
        _cached_subprojection(name, callback, fallback, wait_seconds=0.01, ttl_seconds=120.0)


def cached_app_backup_profiles() -> dict[str, Any]:
    backup = app_backup_subprojection()
    return {
        "status": "healthy" if not backup.get("read_degraded") else "degraded",
        "summary": "Saved app backup profiles are available.",
        "apps": [{"app_id": "photoprism", "name": "PhotoPrism", **backup}],
        "count": 1,
        "updated_at": _now(),
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
    target_summary = backup.get("backup_target_summary") if isinstance(backup.get("backup_target_summary"), dict) else target
    latest_backup = backup.get("latest_backup") if isinstance(backup.get("latest_backup"), dict) else None
    latest_restore_preview = backup.get("latest_restore_preview") if isinstance(backup.get("latest_restore_preview"), dict) else None
    pending_backup = backup.get("pending_backup") if isinstance(backup.get("pending_backup"), dict) else None
    restore = backup.get("restore") if isinstance(backup.get("restore"), dict) else {}
    return {
        "status": status,
        "summary": "Backup ready" if status == "ready" else _safe_text(backup.get("summary"), "Backup profile needs review."),
        "default_mode": _safe_label(backup.get("default_mode"), "config_only"),
        "media": _safe_label(media.get("default"), "excluded"),
        "target_available": bool(target_summary.get("ready") or target_summary.get("available")),
        "target_ready": bool(target_summary.get("ready")),
        "target_summary": _safe_text(target_summary.get("summary") or target_summary.get("label"), "Backup target not ready"),
        "target_label": _safe_label(target_summary.get("target_label"), "Storage device") if target_summary.get("target_label") else None,
        "latest_backup_id": _safe_label(latest_backup.get("backup_id"), "") if latest_backup else None,
        "latest_verified_backup_id": _safe_label(backup.get("latest_verified_backup_id"), "") if backup.get("latest_verified_backup_id") else None,
        "latest_backup_status": _safe_label(latest_backup.get("verification_status") or latest_backup.get("status"), "not_verified") if latest_backup else "not_created",
        "pending_backup_id": _safe_label(pending_backup.get("backup_id") or pending_backup.get("command_id"), "") if pending_backup else None,
        "backup_running": bool(backup.get("backup_running") or restore.get("backup_running")),
        "restore_preview_available": bool(restore.get("preview_available")),
        "restore_preview_disabled_reason": _safe_text(restore.get("disabled_reason") or backup.get("restore_preview_disabled_reason"), "No verified app backup yet"),
        "latest_restore_preview_id": _safe_label(latest_restore_preview.get("preview_id"), "") if latest_restore_preview else None,
    }


def _recovery_profile(backup: dict[str, Any]) -> dict[str, Any]:
    restore = backup.get("restore") if isinstance(backup.get("restore"), dict) else {}
    preview = bool(restore.get("preview_available"))
    disabled_reason = restore.get("disabled_reason") or backup.get("restore_preview_disabled_reason") or "No verified app backup yet"
    return {
        "status": "ready" if preview else ("checking" if backup.get("backup_running") else "review"),
        "summary": _safe_text(restore.get("summary") or disabled_reason, "Restore preview not ready" if not preview else "Restore preview available"),
        "disabled_reason": None if preview else _safe_text(disabled_reason, "No verified app backup yet"),
        "preview_available": preview,
        "backup_running": bool(backup.get("backup_running")),
        "restore_available": bool(restore.get("restore_available")),
        "preview_only": bool(restore.get("preview_only", True)),
        "restore_apply_supported": bool(restore.get("restore_apply_supported", False)),
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


def _backup_to_storage_action(backup: dict[str, Any]) -> dict[str, Any]:
    try:
        summary = lite_recovery_subprojections.app_backup_targets("photoprism")
    except Exception:
        summary = {"ready": False, "summary": "Join a storage device to save app backups elsewhere.", "target_label": None}
    ready = bool(summary.get("ready"))
    label = "Back up to storage device"
    reason = None if ready else _safe_text(summary.get("summary"), "Join a storage device to save app backups elsewhere.")
    action = _action(
        ready,
        label,
        reason=reason,
        summary=f"Save PhotoPrism backup to {summary.get('target_label')}." if ready and summary.get("target_label") else "Save PhotoPrism backup to a joined storage device.",
        status="ready" if ready else "not_ready",
    )
    action["requires_target"] = True
    if summary.get("target_label"):
        action["target_label"] = summary.get("target_label")
    if ready:
        action["warning"] = "Transfer worker must be enabled before Pocket Lab can save to the storage device."
    return action


def _photoprism_lifecycle_actions() -> dict[str, Any]:
    try:
        return lite_photoprism_lifecycle.action_readiness()
    except Exception:
        return {
            "install_app": _action(False, "Install", reason="Install action status is not available."),
            "update_app": _action(False, "Update", reason="Update check not ready yet."),
            "repair_app": _action(False, "Repair", reason="Repair app is not ready yet."),
            "remove_app": _action(False, "Remove app", reason="Remove app is not ready yet."),
        }


def _operation_action(action_id: str, installed: bool, operations: dict[str, Any]) -> dict[str, Any]:
    op = (operations.get("actions") or {}).get(action_id) if isinstance(operations, dict) else {}
    running = str(op.get("status") or "").lower() in {"queued", "running"}
    if action_id == "check_app":
        return _action(
            installed and not running,
            "Check app",
            reason=None if installed else "Install PhotoPrism first.",
            summary="Check route, health, storage, and safety proof.",
            status="running" if running else "ready",
        ) | {
            "category": "safety",
            "progress": op.get("progress"),
            "last_result": op.get("summary"),
            "first_ran_at": op.get("started_at") or op.get("queued_at") or op.get("completed_at"),
            "last_ran_at": op.get("completed_at") or op.get("updated_at") or op.get("started_at") or op.get("queued_at"),
            "run_count": 1 if op.get("summary") or op.get("evidence_ref") else 0,
            "evidence_ref": op.get("evidence_ref"),
            "checks": op.get("checks") if isinstance(op.get("checks"), list) else [],
            "details": op.get("details") if isinstance(op.get("details"), dict) else {},
            "technical_details": op.get("technical_details") if isinstance(op.get("technical_details"), dict) else {},
        }
    return _action(
        installed and not running,
        "Repair",
        reason=None if installed else "Install PhotoPrism first.",
        summary="Fix route, health, and storage setup safely.",
        status="running" if running else "ready",
    ) | {
        "category": "recovery",
        "progress": op.get("progress"),
        "last_result": op.get("summary"),
        "first_ran_at": op.get("started_at") or op.get("queued_at") or op.get("completed_at"),
        "last_ran_at": op.get("completed_at") or op.get("updated_at") or op.get("started_at") or op.get("queued_at"),
        "run_count": 1 if op.get("summary") or op.get("evidence_ref") else 0,
        "evidence_ref": op.get("evidence_ref"),
        "repair_steps": op.get("repair_steps") if isinstance(op.get("repair_steps"), list) else [],
        "details": op.get("details") if isinstance(op.get("details"), dict) else {},
        "technical_details": op.get("technical_details") if isinstance(op.get("technical_details"), dict) else {},
    }


def _actions(app: dict[str, Any], installed: bool, backup: dict[str, Any], recovery: dict[str, Any], media: dict[str, Any], operations: dict[str, Any] | None = None, update: dict[str, Any] | None = None) -> dict[str, Any]:
    access = app.get("access") if isinstance(app.get("access"), dict) else {}
    actions = app.get("actions") if isinstance(app.get("actions"), dict) else {}
    open_url = access.get("open_url") or (app.get("runtime") or {}).get("url")
    route_enabled = bool(actions.get("open") and open_url == _SAFE_ROUTE)
    backup_enabled = bool(installed)
    media_ready, media_reason, media_status = _media_action_ready(installed, route_enabled, media)
    action_payload = {
        "open": _action(route_enabled, "Open", url=_SAFE_ROUTE if route_enabled else None, reason=None if route_enabled else "Open is not ready yet."),
        "open_full_screen": _action(route_enabled, "Open full screen", url=_SAFE_ROUTE if route_enabled else None, reason=None if route_enabled else "Open full screen is not ready yet."),
        "install_to_phone": _action(route_enabled, "Install to phone", url=_SAFE_ROUTE if route_enabled else None, reason=None if route_enabled else "Install to phone is available after Open is ready."),
        "connect_photos": _action(installed, "Connect photos", reason=None if installed else "Install PhotoPrism first."),
        "check_app": _action(False, "Check app", reason="Use Run Safety Check for the current device-wide scan."),
        "backup_app": _action(
            backup_enabled,
            "Back up app",
            reason=None if backup_enabled else "Install PhotoPrism first.",
            summary="Save PhotoPrism settings, mappings, route records, and safe app records.",
            status="ready" if backup_enabled else "not_ready",
        ) | {
            "category": "recovery",
            "last_result": "App backup saved." if backup.get("latest_backup_id") else None,
            "latest_backup_id": backup.get("latest_backup_id"),
            "receipt_id": backup.get("latest_backup_id"),
            "first_ran_at": backup.get("first_backup_at") or backup.get("latest_backup_created_at"),
            "last_ran_at": backup.get("latest_backup_created_at") or backup.get("latest_backup_verified_at"),
            "run_count": backup.get("backup_count") or (1 if backup.get("latest_backup_id") else 0),
            "evidence_ref": f"apps/photoprism/backups/{backup.get('latest_backup_id')}.json" if backup.get("latest_backup_id") else None,
        },
        "backup_to_storage": _backup_to_storage_action(backup),
        "preview_restore": _action(
            bool(recovery.get("preview_available")),
            "Preview restore",
            reason=None if recovery.get("preview_available") else (recovery.get("disabled_reason") or backup.get("restore_preview_disabled_reason") or "No verified app backup yet"),
            summary="Review what would be restored before making changes." if recovery.get("preview_available") else (recovery.get("summary") or "No verified app backup yet"),
            status="ready" if recovery.get("preview_available") else ("running" if backup.get("backup_running") else "not_ready"),
        ) | {
            "category": "recovery",
            "last_result": "Restore preview ready. No changes were applied." if backup.get("latest_restore_preview_id") else None,
            "latest_restore_preview_id": backup.get("latest_restore_preview_id"),
            "receipt_id": backup.get("latest_restore_preview_id"),
            "first_ran_at": backup.get("first_restore_preview_at") or backup.get("latest_restore_preview_created_at"),
            "last_ran_at": backup.get("latest_restore_preview_created_at"),
            "run_count": backup.get("restore_preview_count") or (1 if backup.get("latest_restore_preview_id") else 0),
            "evidence_ref": f"apps/photoprism/restore-previews/{backup.get('latest_restore_preview_id')}.json" if backup.get("latest_restore_preview_id") else None,
        },
        "import_photos": _action(
            media_ready,
            "Import photos",
            reason=media_reason,
            summary="Import connected photos into PhotoPrism. PhotoPrism handles library indexing.",
            status=media_status,
        ),
    }
    action_payload.update(_photoprism_lifecycle_actions())
    update = update or {}
    update_actions = update.get("actions") if isinstance(update.get("actions"), dict) else {}
    update_action = update_actions.get("update_app") if isinstance(update_actions.get("update_app"), dict) else {}
    update_pending = update.get("pending_check") if isinstance(update.get("pending_check"), dict) else None
    update_latest = update.get("latest_check") if isinstance(update.get("latest_check"), dict) else None
    update_running = bool(update.get("operation_running"))
    update_readiness = update.get("readiness") if isinstance(update.get("readiness"), dict) else {}
    action_payload["update_app"] = _action(
        installed and bool(update_action.get("enabled", True)),
        "Update",
        reason=None if installed and bool(update_action.get("enabled", True)) else (update_action.get("disabled_reason") or "Install PhotoPrism first."),
        summary="Check whether this app is ready for a safe update.",
        status="running" if update_running else (update_readiness.get("status") or "ready"),
    ) | {
        "category": "app_setup",
        "readiness_only": True,
        "apply_supported": False,
        "apply_update_enabled": False,
        "apply_disabled_reason": "Update apply is not enabled yet.",
        "progress": (update_pending or {}).get("progress"),
        "last_result": (update_latest or {}).get("summary"),
        "latest_check": update_latest,
        "first_ran_at": (update_latest or {}).get("started_at") or (update_latest or {}).get("completed_at"),
        "last_ran_at": (update_latest or {}).get("completed_at") or (update_latest or {}).get("updated_at") or (update_pending or {}).get("started_at"),
        "run_count": 1 if update_latest else 0,
        "evidence_ref": (update_latest or update_pending or {}).get("evidence_ref"),
        "receipt_id": (update_latest or update_pending or {}).get("operation_id") or (update_latest or update_pending or {}).get("command_id"),
    }
    operations = operations or {}
    action_payload["check_app"] = _operation_action("check_app", installed, operations)
    action_payload["repair_app"] = _operation_action("repair_app", installed, operations)
    return action_payload


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
            "title": "Importing photos",
            "summary": "Pocket Lab is importing connected photos. PhotoPrism handles library indexing.",
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


def _saved_projection_max_age_seconds() -> float:
    configured = os.environ.get("POCKETLAB_LITE_APP_CURRENT_STATE_MAX_AGE_SECONDS", "900").strip()
    try:
        return max(30.0, min(3600.0, float(configured)))
    except ValueError:
        return 900.0


def _reconcile_delay_seconds() -> float:
    configured = os.environ.get("POCKETLAB_LITE_APP_RECONCILE_DELAY_SECONDS", "8.0").strip()
    try:
        return max(1.0, min(30.0, float(configured)))
    except ValueError:
        return 8.0


def _reconcile_deadline_seconds() -> float:
    configured = os.environ.get("POCKETLAB_LITE_APP_RECONCILE_DEADLINE_SECONDS", "4.0").strip()
    try:
        return max(1.0, min(15.0, float(configured)))
    except (TypeError, ValueError):
        return 4.0




def _reconcile_backoff_seconds(failures: int) -> float:
    base = (60.0, 120.0, 300.0)[min(max(int(failures), 1) - 1, 2)]
    # Stable jitter avoids a restart herd without making tests or logs random.
    jitter = ((failures * 37) % 11) / 100.0
    return min(330.0, base * (1.0 + jitter))

def _run_saved_stage_reconciliation(
    callbacks: dict[str, tuple[Callable[[], Any], Any, float]],
) -> None:
    global _RECONCILE_FUTURE, _RECONCILE_NEXT_ALLOWED, _RECONCILE_FAILURES
    lease: tuple[str, int] | None = None
    succeeded = False
    timed_out = False
    deferred = False
    try:
        threading.Event().wait(_reconcile_delay_seconds())
        acquire_workload = getattr(CONTROL_PLANE, "try_acquire_workload", None)
        lease = (
            acquire_workload("apps", "app-saved-reconciliation")
            if callable(acquire_workload)
            else ("legacy-app-saved-reconciliation", 0)
        )
        if lease is None:
            with _RECONCILE_LOCK:
                _RECONCILE_NEXT_ALLOWED = max(
                    _RECONCILE_NEXT_ALLOWED, time.monotonic() + 30.0
                )
            _LOGGER.info(
                "pocketlab.app_projection.reconcile_deferred reason=domain_busy retry_seconds=30"
            )
            return
        if _stage_work_busy():
            deferred = True
            with _RECONCILE_LOCK:
                _RECONCILE_NEXT_ALLOWED = max(
                    _RECONCILE_NEXT_ALLOWED, time.monotonic() + 30.0
                )
            _LOGGER.info(
                "pocketlab.app_projection.reconcile_deferred reason=stage_busy retry_seconds=30"
            )
            return

        futures: dict[str, concurrent.futures.Future[Any]] = {}
        for name, (callback, _fallback, _legacy_timeout) in callbacks.items():
            try:
                futures[name] = _STAGE_EXECUTOR.submit(callback)
                _track_stage_future(futures[name])
            except RuntimeError as exc:
                _LOGGER.warning(
                    "pocketlab.app_projection.reconcile_submit_degraded key=%s error_type=%s",
                    name, type(exc).__name__,
                )

        deadline_seconds = _reconcile_deadline_seconds()
        done, pending = concurrent.futures.wait(
            set(futures.values()),
            timeout=deadline_seconds,
            return_when=concurrent.futures.ALL_COMPLETED,
        ) if futures else (set(), set())
        projections: dict[str, dict[str, Any]] = {}
        pending_names: list[str] = []
        for name, future in futures.items():
            if future not in done:
                pending_names.append(name)
                future.cancel()
                continue
            try:
                value = future.result()
            except Exception as exc:
                _LOGGER.warning(
                    "pocketlab.app_projection.reconcile_degraded key=%s error_type=%s",
                    name, type(exc).__name__,
                )
                continue
            if not isinstance(value, dict):
                _LOGGER.warning(
                    "pocketlab.app_projection.reconcile_degraded key=%s error_type=InvalidPayload",
                    name,
                )
                continue
            if name in {"backup", "security"}:
                projections[name] = {"kind": "raw", "payload": value}
            else:
                projections[name] = value
        if pending_names:
            timed_out = True
            _LOGGER.warning(
                "pocketlab.app_projection.reconcile_timeout deadline_ms=%.0f pending=%s",
                deadline_seconds * 1000.0,
                ",".join(sorted(pending_names)),
            )
        if projections:
            CONTROL_PLANE.update_app_subprojections("photoprism", projections)
        succeeded = bool(projections) and not timed_out
    except Exception as exc:
        _LOGGER.exception(
            "pocketlab.app_projection.reconcile_degraded key=all error_type=%s",
            type(exc).__name__,
        )
    finally:
        release_workload = getattr(CONTROL_PLANE, "release_workload", None)
        if lease is not None and callable(release_workload):
            release_workload("apps", lease)
        with _RECONCILE_LOCK:
            _RECONCILE_FUTURE = None
            if succeeded:
                _RECONCILE_FAILURES = 0
                _RECONCILE_NEXT_ALLOWED = time.monotonic() + 30.0
            elif deferred:
                _RECONCILE_NEXT_ALLOWED = max(
                    _RECONCILE_NEXT_ALLOWED, time.monotonic() + 30.0
                )
            elif lease is not None:
                _RECONCILE_FAILURES = min(8, _RECONCILE_FAILURES + 1)
                delay = _reconcile_backoff_seconds(_RECONCILE_FAILURES)
                _RECONCILE_NEXT_ALLOWED = time.monotonic() + delay
                if timed_out:
                    _LOGGER.warning(
                        "pocketlab.app_projection.reconcile_backoff retry_seconds=%.0f failures=%d",
                        delay, _RECONCILE_FAILURES,
                    )


def _schedule_saved_stage_reconciliation(
    callbacks: dict[str, tuple[Callable[[], Any], Any, float]],
) -> None:
    global _RECONCILE_FUTURE
    now = time.monotonic()
    with _RECONCILE_LOCK:
        if _RECONCILE_FUTURE is not None and not _RECONCILE_FUTURE.done():
            return
        if now < _RECONCILE_NEXT_ALLOWED:
            return
        _RECONCILE_FUTURE = _RECONCILE_EXECUTOR.submit(
            _run_saved_stage_reconciliation, dict(callbacks)
        )

def _saved_stage_value(saved: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    if not isinstance(saved, dict):
        return None
    value = saved.get(name)
    if not isinstance(value, dict) or not value:
        return None
    if name == "backup":
        if value.get("kind") == "raw" and isinstance(value.get("payload"), dict):
            return dict(value["payload"])
        if value.get("kind") == "profile" and isinstance(value.get("backup"), dict):
            return {"__saved_profile__": True, **dict(value)}
    if name == "security":
        if value.get("kind") == "raw" and isinstance(value.get("payload"), dict):
            return dict(value["payload"])
        if value.get("kind") == "profile" and isinstance(value.get("security"), dict):
            return {"__saved_profile__": True, **dict(value)}
    return dict(value)


def _collect_app_stages(stage_timings: dict[str, float] | None = None) -> dict[str, Any]:
    callbacks: dict[str, tuple[Callable[[], Any], Any, float]] = {
        "catalog": (lambda: _catalog_app("photoprism"), {}, 2.5),
        "media": (_media_payload, {"status": "unknown", "summary": "Media status is refreshing."}, 2.5),
        "operations": (lambda: lite_app_operations.app_operation_status("photoprism"), {"status": "unknown", "actions": {}}, 2.0),
        "update": (lambda: lite_app_update.update_status("photoprism"), {"status": "unknown", "actions": {}, "readiness": {"status": "unknown", "summary": "Update readiness is refreshing."}}, 2.5),
        "backup": (app_backup_subprojection, {"status": "unknown", "summary": "App backup status is refreshing."}, 1.5),
        "security": (app_security_subprojection, {"status": "unknown", "summary": "App safety status is refreshing."}, 1.5),
        "backup_targets": (lambda: lite_recovery_subprojections.app_backup_targets("photoprism"), {"status": "degraded", "summary": "Backup targets are refreshing.", "ready": False}, 1.5),
    }
    try:
        saved = CONTROL_PLANE.app_current_subprojections(
            "photoprism", max_age_seconds=_saved_projection_max_age_seconds()
        )
    except Exception as exc:
        saved = None
        _LOGGER.warning(
            "pocketlab.app_projection.saved_read_degraded error_type=%s",
            type(exc).__name__,
        )

    started_at = time.monotonic()
    deadline_seconds = _app_stage_deadline_seconds()
    deadline_at = started_at + deadline_seconds
    submitted_at: dict[str, float] = {}
    futures: dict[str, concurrent.futures.Future[Any]] = {}
    results: dict[str, Any] = {}
    used_saved = False
    prior_stage_busy = _stage_work_busy()

    for name, (callback, fallback, _legacy_timeout) in callbacks.items():
        submitted_at[name] = time.monotonic()
        saved_value = _saved_stage_value(saved, name)
        if saved_value is not None:
            saved_value["projection_only"] = True
            saved_value["projection_age_ms"] = int((saved or {}).get("projection_age_ms") or 0)
            results[name] = saved_value
            used_saved = True
            if stage_timings is not None:
                stage_timings[name] = round(max(0.0, (time.monotonic() - submitted_at[name]) * 1000.0), 3)
            continue
        if prior_stage_busy:
            results[name] = _stage_timeout_payload(fallback, refresh_pending=True)
            if stage_timings is not None:
                stage_timings[name] = 0.0
            continue
        try:
            futures[name] = _STAGE_EXECUTOR.submit(callback)
            _track_stage_future(futures[name])
        except RuntimeError as exc:
            results[name] = _stage_timeout_payload(fallback, refresh_pending=False)
            _LOGGER.warning(
                "pocketlab.app_stage.submit_degraded key=%s error_type=%s",
                name, type(exc).__name__,
            )

    pending = set(futures.values())
    if pending:
        remaining = max(0.0, deadline_at - time.monotonic())
        done, pending = concurrent.futures.wait(
            pending,
            timeout=remaining,
            return_when=concurrent.futures.ALL_COMPLETED,
        )
    else:
        done = set()

    timed_out_names: list[str] = []
    for name, (_callback, fallback, _legacy_timeout) in callbacks.items():
        if name in results:
            continue
        future = futures.get(name)
        if future is None:
            results[name] = _stage_timeout_payload(fallback, refresh_pending=False)
        elif future in done:
            try:
                value = future.result()
                results[name] = value if isinstance(value, dict) else _stage_timeout_payload(
                    fallback, refresh_pending=False
                )
                if not isinstance(value, dict):
                    _LOGGER.warning(
                        "pocketlab.app_stage.degraded key=%s error_type=InvalidPayload",
                        name,
                    )
            except Exception as exc:
                results[name] = _stage_timeout_payload(fallback, refresh_pending=False)
                _LOGGER.warning(
                    "pocketlab.app_stage.degraded key=%s error_type=%s",
                    name, type(exc).__name__,
                )
        else:
            timed_out_names.append(name)
            results[name] = _stage_timeout_payload(fallback, refresh_pending=True)
            future.cancel()
        if stage_timings is not None:
            stage_timings[name] = round(
                max(0.0, (time.monotonic() - submitted_at.get(name, started_at)) * 1000.0),
                3,
            )

    if timed_out_names:
        _LOGGER.warning(
            "pocketlab.app_stage.deadline_exhausted deadline_ms=%.0f elapsed_ms=%.3f pending=%s",
            deadline_seconds * 1000.0,
            max(0.0, (time.monotonic() - started_at) * 1000.0),
            ",".join(sorted(timed_out_names)),
        )

    if used_saved or timed_out_names or prior_stage_busy:
        _schedule_saved_stage_reconciliation(callbacks)
    return results

def photoprism_lifecycle_profile(stage_timings: dict[str, float] | None = None) -> dict[str, Any]:
    _prime_app_subprojections()
    parallel = _collect_app_stages(stage_timings)
    app = parallel["catalog"]
    storage_raw = _timed_stage(stage_timings, "storage", _storage_payload)
    security_raw = parallel["security"]
    backup_raw = parallel["backup"]
    if stage_timings is not None and "backup" not in stage_timings:
        stage_timings["backup"] = 0.0
    media = parallel["media"]
    installed = bool(app.get("installed") or app.get("install_state") == "installed" or app.get("status") == "ready")

    storage = _storage_profile(storage_raw)
    if security_raw.get("__saved_profile__"):
        security = dict(security_raw.get("security") or {})
    else:
        security = _security_profile(security_raw)
    if backup_raw.get("__saved_profile__"):
        backup = dict(backup_raw.get("backup") or {})
        recovery = dict(backup_raw.get("recovery") or {})
    else:
        backup = _backup_profile(backup_raw)
        recovery = _recovery_profile(backup_raw)
    operations = parallel["operations"]
    update = parallel["update"]
    if not isinstance(update.get("actions"), dict):
        update["actions"] = {"update_app": {"enabled": installed, "label": "Update"}}
    attention = _attention(installed, storage, security, backup, recovery, media)
    current_action = operations.get("current_action") if isinstance(operations, dict) else None
    if isinstance(current_action, dict) and current_action.get("action_id") in {"check_app", "repair_app"}:
        attention.append({
            "id": f"{current_action.get('action_id')}_running",
            "area": "apps",
            "severity": "info",
            "title": "Checking app" if current_action.get("action_id") == "check_app" else "Repairing app",
            "summary": _safe_text(current_action.get("summary"), "Pocket Lab is working on this app."),
        })
    update_pending = update.get("pending_check") if isinstance(update, dict) and isinstance(update.get("pending_check"), dict) else None
    if update_pending:
        attention.append({
            "id": "update_check_running",
            "area": "apps",
            "severity": "info",
            "title": "Checking update",
            "summary": _safe_text(update_pending.get("summary"), "Pocket Lab is checking update readiness."),
        })
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
        "backup_targets": parallel["backup_targets"],
        "app_lifecycle": _timed_stage(stage_timings, "runtime_lifecycle", app_runtime_subprojection),
        "recovery": recovery,
        "media": media,
        "operations": operations,
        "update": update,
        "current_action": update.get("pending_check") if isinstance(update.get("pending_check"), dict) else operations.get("current_action") if isinstance(operations, dict) else None,
        "last_safety_check": operations.get("last_safety_check") if isinstance(operations, dict) else None,
        "last_repair": operations.get("last_repair") if isinstance(operations, dict) else None,
        "attention": attention,
        "actions": _actions(app, installed, backup, recovery, media, operations, update),
        "evidence": _evidence(security_raw, backup_raw, media),
        "updated_at": _now(),
    }


def app_lifecycle_profile(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    return photoprism_lifecycle_profile()


def app_lifecycle_profiles() -> dict[str, Any]:
    stage_timings: dict[str, float] = {}
    profiles = [photoprism_lifecycle_profile(stage_timings)]
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
        "__projection_stage_timing_ms": stage_timings,
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
                    "update": (profile.get("update") or {}).get("readiness", {}).get("summary") if isinstance((profile.get("update") or {}).get("readiness"), dict) else None,
                    "last_indexed_at": profile.get("media", {}).get("last_indexed_at"),
                    "attention_count": len(profile.get("attention") or []),
                }
    return payload
