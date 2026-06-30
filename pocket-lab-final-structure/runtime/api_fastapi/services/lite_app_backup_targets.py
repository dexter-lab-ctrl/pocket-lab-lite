from __future__ import annotations

import hashlib
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import fleet_registry, lite_device_capabilities

SUPPORTED_APP_IDS = {"photoprism"}
BACKUP_TO_STORAGE_SUBJECT = "pocketlab.commands.lite.app.backup.transfer"
_MIN_FREE_GB = 1.0
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
    "backup_key",
    "encryption_key",
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
                "summary": "PhotoPrism is the first app with Lite storage backup targets.",
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


def _safe_label(value: Any, fallback: str = "Storage device") -> str:
    text = _safe_text(value, fallback)
    if "/" in text and not text.startswith("/apps/"):
        return fallback
    return text[:80]


def _device_id(device: dict[str, Any]) -> str:
    return fleet_registry.normalize_node_id(str(device.get("id") or device.get("node_id") or device.get("name") or ""))


def _available_gb(device: dict[str, Any]) -> float | None:
    storage = device.get("storage") if isinstance(device.get("storage"), dict) else {}
    for value in (
        storage.get("available_gb"),
        device.get("available_gb"),
        device.get("free_storage_gb"),
        device.get("storage_available_gb"),
    ):
        if value in {None, ""}:
            continue
        try:
            amount = float(value)
        except (TypeError, ValueError):
            continue
        if amount >= 0:
            return round(amount, 1)
    return None


def _is_protected_server(device: dict[str, Any]) -> bool:
    role = str(device.get("role") or "").strip().lower().replace("-", "_")
    if role in {"server", "server_host", "control_plane", "control_plane_host"}:
        return True
    if bool(device.get("is_current") or device.get("isCurrent") or device.get("is_control_plane")):
        return True
    return _device_id(device) == "pocket-lab-lite-server"


def _device_ready(device: dict[str, Any]) -> bool:
    connection = str(device.get("connection") or "").strip().lower()
    status = str(device.get("status") or "").strip().lower()
    return connection == "online" or status in {"active", "healthy", "online", "ready"}


def _capabilities(device: dict[str, Any]) -> list[str]:
    caps = device.get("capabilities") if isinstance(device.get("capabilities"), list) else None
    if caps is None:
        caps = lite_device_capabilities.capability_ids_for_role(device.get("role"))
    normalized: list[str] = []
    for item in caps or []:
        value = str(item or "").strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _target_from_device(device: dict[str, Any]) -> dict[str, Any] | None:
    caps = _capabilities(device)
    if "backup_target" not in caps and "media_storage" not in caps:
        return None
    device_id = _device_id(device)
    protected = _is_protected_server(device)
    online = _device_ready(device)
    free_gb = _available_gb(device)
    enough_space = free_gb is None or free_gb >= _MIN_FREE_GB
    available = bool(not protected and online and enough_space and device_id and device_id != "unknown-node")
    if protected:
        reason = "The server phone is protected and is not used as a remote Storage Node."
    elif not online:
        reason = "Storage device is offline."
    elif not enough_space:
        reason = "Not enough space reported."
    else:
        reason = ""
    name = _safe_label(device.get("name") or device.get("hostname") or device_id, "Storage device")
    return {
        "device_id": device_id,
        "id": device_id,
        "name": name,
        "status": "ready" if available else "not_ready",
        "connection": "online" if online else "offline",
        "label": "Storage device",
        "capabilities": [cap for cap in caps if cap in {"backup_target", "media_storage"}],
        "capability_labels": lite_device_capabilities.labels_for_capabilities(caps),
        "available": available,
        "ready": available,
        "available_gb": free_gb,
        "reason": reason,
        "summary": f"{name} can save app backups." if available else reason or "Storage device is not ready.",
        "used_for": "app_backups" if available else "not_ready",
    }


def backup_targets() -> dict[str, Any]:
    try:
        fleet = __import__("api_fastapi.services.lite_status", fromlist=["lite_fleet"]).lite_fleet()
        devices = fleet.get("devices") if isinstance(fleet, dict) else []
    except Exception:
        devices = []
    targets = [target for item in devices if isinstance(item, dict) for target in [_target_from_device(item)] if target]
    ready_count = sum(1 for target in targets if target.get("ready"))
    return {
        "status": "healthy",
        "summary": "Backup targets are available." if ready_count else "No backup target yet. Join a storage device to save app backups elsewhere.",
        "targets": targets,
        "items": targets,
        "count": len(targets),
        "ready_count": ready_count,
        "updated_at": _now(),
    }


def app_backup_targets(app_id: str) -> dict[str, Any]:
    _validate_app_id(app_id)
    payload = backup_targets()
    return {
        **payload,
        "app_id": "photoprism",
        "name": "PhotoPrism",
        "summary": "PhotoPrism backup targets are available." if payload.get("ready_count") else "No backup target yet. Join a storage device to save app backups elsewhere.",
    }


def backup_target_summary(app_id: str = "photoprism") -> dict[str, Any]:
    targets = app_backup_targets(app_id)
    ready = [item for item in targets.get("targets") or [] if isinstance(item, dict) and item.get("ready")]
    count = int(targets.get("count") or 0)
    ready_count = len(ready)
    first = ready[0] if ready else None
    return {
        "status": "ready" if ready_count else "needs_attention",
        "available": ready_count > 0,
        "ready": ready_count > 0,
        "count": count,
        "ready_count": ready_count,
        "label": "Backup target available" if ready_count else "No backup target yet",
        "summary": f"Backups can be saved to {first.get('name')}." if first else "Join a storage device to save app backups elsewhere.",
        "target_label": first.get("name") if first else None,
        "targets": targets.get("targets") or [],
    }


def validate_backup_target(target_device_id: Any, *, app_id: str = "photoprism") -> dict[str, Any]:
    _validate_app_id(app_id)
    wanted = fleet_registry.normalize_node_id(str(target_device_id or ""))
    if not wanted or wanted == "unknown-node":
        raise HTTPException(status_code=422, detail={"status": "target_required", "summary": "Choose a storage device."})
    targets = app_backup_targets(app_id).get("targets") or []
    for target in targets:
        if not isinstance(target, dict):
            continue
        if fleet_registry.normalize_node_id(str(target.get("device_id") or target.get("id") or "")) != wanted:
            continue
        if not target.get("ready"):
            raise HTTPException(status_code=409, detail={"status": "target_not_ready", "summary": target.get("reason") or "Storage device is not ready.", "target": target})
        return target
    raise HTTPException(status_code=404, detail={"status": "unknown_target", "summary": "Choose a joined storage device."})


def _transfer_id(app_id: str, target_device_id: str) -> str:
    digest = hashlib.sha256(f"{app_id}|{target_device_id}|{_now()}".encode("utf-8")).hexdigest()[:12]
    return f"app-backup-target-{digest}"


def backup_to_storage_not_implemented(app_id: str, target_device_id: Any, *, reason: str | None = None) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    target = validate_backup_target(target_device_id, app_id=app)
    return {
        "status": "not_implemented",
        "accepted": False,
        "app_id": app,
        "action_id": "backup_to_storage",
        "transfer_id": _transfer_id(app, target["device_id"]),
        "target_device_id": target["device_id"],
        "target_label": target["name"],
        "summary": "Backup target transfer is prepared, but the storage-device transfer worker is not enabled yet.",
        "reason": _safe_text(reason, "manual app backup to storage device"),
        "evidence": {"status": "pending", "summary": "Transfer evidence pending"},
        "bundle": {"encrypted": True, "checksum_recorded": False, "media_included": False},
        "sensitive_values_hidden": True,
    }
