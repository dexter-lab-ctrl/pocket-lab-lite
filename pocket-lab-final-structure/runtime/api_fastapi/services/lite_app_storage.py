from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import HTTPException

from .. import deps

PHOTOPRISM_APP_ID = "photoprism"
SUPPORTED_SOURCE_TYPES = {"phone_media", "managed_media", "storage_device"}
SUPPORTED_TARGETS = {"import", "originals"}
SUPPORTED_MODES = {"read_only", "read_write"}

PHONE_STORAGE_ROOT = "~/storage"
MAX_STORAGE_PREVIEW_FOLDERS = 30

SOURCE_TYPE_LABELS = {
    "phone_media": "Phone photos",
    "managed_media": "Managed media",
    "storage_device": "Storage device",
}
TARGET_LABELS = {
    "import": "Import folder",
    "originals": "Originals",
}
MODE_LABELS = {
    "read_only": "Read-only",
    "read_write": "Can edit",
}

_ALLOWED_ROOTS = [
    (PHONE_STORAGE_ROOT, "Phone storage", {"phone_media"}),
    ("~/storage/shared/DCIM", "Camera folder", {"phone_media", "storage_device"}),
    ("~/storage/shared/Pictures", "Pictures", {"phone_media", "storage_device"}),
    ("~/storage/shared/Movies", "Movies", {"phone_media", "storage_device"}),
    ("~/storage/downloads", "Downloads", {"phone_media", "storage_device"}),
    ("~/.pocket_lab/lite/media", "Managed media", {"managed_media", "phone_media", "storage_device"}),
]

_SENSITIVE_PATH_PATTERNS = (
    "~/.ssh",
    "~/.pocket_lab/vault",
    "~/.pocket_lab/nats",
    "~/.pocket_lab/tailscale-certs",
    "~/.pocket_lab/lite/secrets",
    "/proc",
    "/sys",
    "/dev",
    "/data/data",
    "/etc",
    "/root",
)


def _state_path() -> Any:
    return deps.settings().state_dir / "lite_app_storage_mappings.json"


def _audit_path() -> Any:
    return deps.settings().state_dir / "lite_app_storage_audit.json"


def _read_json(path: Any, default: Any) -> Any:
    return deps.core.read_json_file(path, default)


def _write_json(path: Any, payload: Any) -> None:
    deps.core.write_json_file(path, payload)


def _now() -> str:
    return deps.now_utc_iso()


def _normalize_enum(value: Any, allowed: set[str], field: str, default: str | None = None) -> str:
    raw = str(value if value is not None else (default or "")).strip().lower().replace("-", "_").replace(" ", "_")
    if raw not in allowed:
        raise HTTPException(status_code=422, detail=f"Unsupported {field}. Choose one of: {', '.join(sorted(allowed))}.")
    return raw


def _normalize_posix_path(value: str) -> str:
    cleaned = value.strip().replace("\\", "/")
    if not cleaned:
        raise HTTPException(status_code=422, detail="Choose a media folder to connect.")
    if "\x00" in cleaned or any(token in cleaned for token in ("`", "$", "|", ";", "&&", "||", "<", ">")):
        raise HTTPException(status_code=422, detail="This folder path is not allowed.")
    if cleaned.startswith("//") or re.match(r"^[A-Za-z]:", cleaned):
        raise HTTPException(status_code=422, detail="Use a Pocket Lab approved media folder path.")
    if not cleaned.startswith("~/"):
        raise HTTPException(status_code=422, detail="Use a Pocket Lab approved media folder path.")
    parts = PurePosixPath(cleaned).parts
    if ".." in parts:
        raise HTTPException(status_code=422, detail="Parent folders are not allowed in media mappings.")
    return str(PurePosixPath(cleaned))


def _is_path_same_or_child(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root.rstrip('/')}/")


def _reject_sensitive_path(path: str) -> None:
    lowered = path.lower()
    for pattern in _SENSITIVE_PATH_PATTERNS:
        if lowered == pattern or lowered.startswith(f"{pattern.rstrip('/')}/"):
            raise HTTPException(status_code=422, detail="This folder is protected and cannot be connected to PhotoPrism.")


def _validate_source_path(source_type: str, source_path: Any, target: str = "import", mode: str = "read_only") -> tuple[str, str]:
    normalized = _normalize_posix_path(str(source_path or ""))
    _reject_sensitive_path(normalized)

    if normalized == PHONE_STORAGE_ROOT:
        if source_type == "phone_media" and target == "import" and mode == "read_only":
            return normalized, "Phone storage"
        raise HTTPException(status_code=422, detail="Phone storage can only be connected as a read-only PhotoPrism import source.")

    for root, label, source_types in _ALLOWED_ROOTS:
        if root == PHONE_STORAGE_ROOT:
            continue
        if source_type in source_types and _is_path_same_or_child(normalized, root):
            if normalized == root:
                return normalized, label
            # Keep the label friendly and avoid echoing the full private path.
            suffix = normalized[len(root):].strip("/")
            short_suffix = suffix.split("/", 1)[0] if suffix else ""
            return normalized, f"{label} / {short_suffix}" if short_suffix else label
    raise HTTPException(status_code=422, detail="Choose phone storage, phone photos, pictures, downloads, or managed media.")


def _state() -> dict[str, Any]:
    payload = _read_json(_state_path(), {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("version", 1)
    payload.setdefault("apps", {})
    payload.setdefault("updated_at", None)
    app = payload["apps"].setdefault(PHOTOPRISM_APP_ID, {})
    app.setdefault("mappings", [])
    return payload


def _write_state(payload: dict[str, Any]) -> None:
    payload["updated_at"] = _now()
    _write_json(_state_path(), payload)


def _mapping_id(source_type: str, source_path: str, target: str) -> str:
    digest = hashlib.sha256(f"{source_type}|{source_path}|{target}".encode("utf-8")).hexdigest()[:14]
    return f"map-{digest}"


def _label_for_mapping(label: Any, source_type: str, path_label: str) -> str:
    raw = str(label or "").strip()
    if raw:
        safe = re.sub(r"[^A-Za-z0-9 ._()/-]+", "", raw).strip()
        if safe:
            return safe[:48]
    return path_label or SOURCE_TYPE_LABELS.get(source_type, "Media folder")


def _public_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        "mapping_id": mapping.get("mapping_id"),
        "app_id": PHOTOPRISM_APP_ID,
        "source_type": mapping.get("source_type"),
        "source_type_label": SOURCE_TYPE_LABELS.get(str(mapping.get("source_type")), "Media folder"),
        "label": mapping.get("label"),
        "source_label": mapping.get("source_label") or mapping.get("label"),
        "source_path_summary": mapping.get("source_path_summary"),
        "device_id": mapping.get("device_id"),
        "device_name": mapping.get("device_name"),
        "target": mapping.get("target"),
        "target_label": TARGET_LABELS.get(str(mapping.get("target")), "Import folder"),
        "mode": mapping.get("mode"),
        "mode_label": MODE_LABELS.get(str(mapping.get("mode")), "Read-only"),
        "status": mapping.get("status") or "pending_apply",
        "status_label": "Needs apply" if mapping.get("pending_apply", True) else "Ready",
        "pending_apply": bool(mapping.get("pending_apply", True)),
        "requires_restart": bool(mapping.get("requires_restart", True)),
        "apply_strategy": "Agent will apply this safely" if mapping.get("pending_apply", True) else "Applied",
        "created_at": mapping.get("created_at"),
        "updated_at": mapping.get("updated_at"),
        "evidence_ref": mapping.get("evidence_ref"),
    }


def _append_audit(event_type: str, mapping: dict[str, Any]) -> dict[str, Any]:
    audit = _read_json(_audit_path(), {})
    if not isinstance(audit, dict):
        audit = {}
    events = audit.setdefault("events", [])
    event = {
        "event_id": f"storage-{hashlib.sha256((event_type + str(mapping.get('mapping_id')) + _now()).encode('utf-8')).hexdigest()[:12]}",
        "event_type": event_type,
        "app_id": PHOTOPRISM_APP_ID,
        "mapping_id": mapping.get("mapping_id"),
        "source_type": mapping.get("source_type"),
        "source_label": mapping.get("source_label") or mapping.get("label"),
        "target": mapping.get("target"),
        "mode": mapping.get("mode"),
        "status": mapping.get("status") or "pending_apply",
        "recorded_at": _now(),
        "summary": "PhotoPrism media folder mapping recorded." if event_type.endswith("created") else "PhotoPrism media folder mapping removed.",
    }
    events.insert(0, event)
    audit["events"] = events[:100]
    audit["updated_at"] = event["recorded_at"]
    _write_json(_audit_path(), audit)
    return event

_STORAGE_PREVIEW_KIND_LABELS = {
    "shared": "Android shared storage",
    "dcim": "Camera photos",
    "pictures": "Pictures",
    "movies": "Videos",
    "downloads": "Downloads",
    "music": "Music",
    "external-1": "External storage",
}

_STORAGE_PREVIEW_PHOTO_LIKELY = {"shared", "dcim", "pictures", "movies", "downloads"}
_STORAGE_PREVIEW_ORDER = ["shared", "dcim", "pictures", "movies", "downloads", "music", "external-1"]
_STORAGE_PREVIEW_BLOCKED_NAMES = {
    ".ssh",
    ".pocket_lab",
    ".pocketlab",
    "pocket-lab-lite",
    "proc",
    "sys",
    "dev",
    "data",
    "root",
    "etc",
}


def _phone_storage_root() -> Path:
    return Path.home() / "storage"


def _preview_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    name = str(item.get("name") or "").lower()
    try:
        return (_STORAGE_PREVIEW_ORDER.index(name), name)
    except ValueError:
        return (len(_STORAGE_PREVIEW_ORDER), name)


def _safe_preview_child_name(name: str) -> str | None:
    cleaned = str(name or "").strip()
    if not cleaned or cleaned.startswith("."):
        return None
    lowered = cleaned.lower()
    if lowered in _STORAGE_PREVIEW_BLOCKED_NAMES:
        return None
    if ".." in PurePosixPath(cleaned).parts:
        return None
    if any(token in cleaned for token in ("`", "$", "|", ";", "&&", "||", "<", ">", "\x00", "/", "\\")):
        return None
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "", cleaned).strip()
    return safe[:80] or None


def photoprism_storage_preview() -> dict[str, Any]:
    """Return a shallow, sanitized preview of Termux ~/storage for PhotoPrism.

    This endpoint is intentionally read-only and bounded. It lists only direct
    visible child directories under ~/storage and never returns resolved Android
    paths, file names, recursive counts, or secret/private directories.
    """

    root = _phone_storage_root()
    base = {
        "root": PHONE_STORAGE_ROOT,
        "root_label": "Phone storage",
    }

    try:
        ready = root.exists() and root.is_dir() and os.access(root, os.R_OK)
    except OSError:
        ready = False

    if not ready:
        return {
            **base,
            "status": "not_ready",
            "summary": "Phone storage is not ready yet.",
            "reason": "Run termux-setup-storage in Termux and allow storage access.",
            "subfolders": [],
            "connect_payload": None,
        }

    subfolders: list[dict[str, Any]] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return {
            **base,
            "status": "not_ready",
            "summary": "Phone storage is not ready yet.",
            "reason": "Pocket Lab could not read ~/storage. Run termux-setup-storage and allow storage access.",
            "subfolders": [],
            "connect_payload": None,
        }

    for child in children:
        if len(subfolders) >= MAX_STORAGE_PREVIEW_FOLDERS:
            break
        safe_name = _safe_preview_child_name(child.name)
        if not safe_name:
            continue
        try:
            if not child.is_dir():
                continue
        except OSError:
            continue
        lowered = safe_name.lower()
        subfolders.append({
            "name": safe_name,
            "path_summary": f"{PHONE_STORAGE_ROOT}/{safe_name}",
            "kind": _STORAGE_PREVIEW_KIND_LABELS.get(lowered, "Folder"),
            "included": True,
            "photo_likely": lowered in _STORAGE_PREVIEW_PHOTO_LIKELY,
        })

    subfolders.sort(key=_preview_sort_key)
    return {
        **base,
        "status": "ready",
        "summary": "PhotoPrism can look for pictures in this phone’s storage.",
        "subfolders": subfolders[:MAX_STORAGE_PREVIEW_FOLDERS],
        "connect_payload": {
            "source_type": "phone_media",
            "label": "Phone storage",
            "source_path": PHONE_STORAGE_ROOT,
            "target": "import",
            "mode": "read_only",
        },
    }


def list_mappings(app_id: str = PHOTOPRISM_APP_ID) -> dict[str, Any]:
    if str(app_id).strip().lower() != PHOTOPRISM_APP_ID:
        raise HTTPException(status_code=404, detail="PhotoPrism storage mappings are the first supported app mapping.")
    payload = _state()
    mappings = payload.get("apps", {}).get(PHOTOPRISM_APP_ID, {}).get("mappings", [])
    public = [_public_mapping(item) for item in mappings if isinstance(item, dict)]
    return {
        "status": "healthy",
        "app_id": PHOTOPRISM_APP_ID,
        "mappings": public,
        "count": len(public),
        "summary": "No media folders connected yet." if not public else f"{len(public)} media folder(s) connected.",
        "updated_at": payload.get("updated_at"),
    }


def create_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    app_id = str(payload.get("app_id") or PHOTOPRISM_APP_ID).strip().lower()
    if app_id != PHOTOPRISM_APP_ID:
        raise HTTPException(status_code=404, detail="PhotoPrism storage mappings are the first supported app mapping.")
    source_type = _normalize_enum(payload.get("source_type"), SUPPORTED_SOURCE_TYPES, "source type")
    target = _normalize_enum(payload.get("target"), SUPPORTED_TARGETS, "target", default="import")
    mode = _normalize_enum(payload.get("mode"), SUPPORTED_MODES, "mode", default="read_only")
    source_path, path_label = _validate_source_path(source_type, payload.get("source_path"), target=target, mode=mode)
    mapping_id = _mapping_id(source_type, source_path, target)

    state = _state()
    mappings = state["apps"][PHOTOPRISM_APP_ID].setdefault("mappings", [])
    for item in mappings:
        if isinstance(item, dict) and item.get("mapping_id") == mapping_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "duplicate_mapping",
                    "summary": "This media folder is already connected to PhotoPrism.",
                    "mapping": _public_mapping(item),
                },
            )

    now = _now()
    label = _label_for_mapping(payload.get("label"), source_type, path_label)
    mapping = {
        "mapping_id": mapping_id,
        "app_id": PHOTOPRISM_APP_ID,
        "source_type": source_type,
        "source_path": source_path,
        "source_path_hash": hashlib.sha256(source_path.encode("utf-8")).hexdigest(),
        "source_path_summary": path_label,
        "source_label": path_label,
        "label": label,
        "device_id": str(payload.get("device_id") or "").strip() or None,
        "device_name": str(payload.get("device_name") or "").strip() or None,
        "target": target,
        "mode": mode,
        "status": "pending_apply",
        "pending_apply": True,
        "requires_restart": True,
        "created_at": now,
        "updated_at": now,
        "evidence_ref": f"apps/photoprism/storage-mappings/{mapping_id}.json",
    }
    mappings.append(mapping)
    _write_state(state)
    event = _append_audit("pocketlab.audit.apps.storage_mapping.created", mapping)
    return {
        "status": "created",
        "accepted": True,
        "app_id": PHOTOPRISM_APP_ID,
        "mapping": _public_mapping(mapping),
        "pending_apply": True,
        "requires_restart": True,
        "event": event,
        "summary": "Media folder connected. Pocket Lab will apply it safely through the app agent path.",
    }


def runtime_mappings(app_id: str = PHOTOPRISM_APP_ID) -> list[dict[str, Any]]:
    """Return raw-but-validated mapping records for backend/worker apply only.

    This helper is intentionally not used by public API responses because it
    includes internal source_path values. Callers must keep output out of the
    browser/API surface and evidence should use only friendly summaries.
    """

    if str(app_id).strip().lower() != PHOTOPRISM_APP_ID:
        raise HTTPException(status_code=404, detail="PhotoPrism storage mappings are the first supported app mapping.")
    payload = _state()
    mappings = payload.get("apps", {}).get(PHOTOPRISM_APP_ID, {}).get("mappings", [])
    safe: list[dict[str, Any]] = []
    for item in mappings:
        if not isinstance(item, dict):
            continue
        source_type = _normalize_enum(item.get("source_type"), SUPPORTED_SOURCE_TYPES, "source type")
        target = _normalize_enum(item.get("target"), SUPPORTED_TARGETS, "target", default="import")
        mode = _normalize_enum(item.get("mode"), SUPPORTED_MODES, "mode", default="read_only")
        source_path, path_label = _validate_source_path(source_type, item.get("source_path"), target=target, mode=mode)
        safe.append({
            **item,
            "source_type": source_type,
            "source_path": source_path,
            "source_path_summary": item.get("source_path_summary") or path_label,
            "source_label": item.get("source_label") or item.get("label") or path_label,
            "target": target,
            "mode": mode,
        })
    return safe


def resolve_mapping_source_path(source_path: str) -> Path:
    """Resolve an already-validated Pocket Lab mapping path for worker use.

    The returned path is local to the server host. It must not be returned to
    the frontend or included in public evidence.
    """

    normalized = _normalize_posix_path(str(source_path or ""))
    _reject_sensitive_path(normalized)
    # Reuse the precise allowlist. Source type/target/mode only matter for the
    # whole-phone-storage special case; use the strict read-only import shape.
    if normalized == PHONE_STORAGE_ROOT:
        _validate_source_path("phone_media", normalized, target="import", mode="read_only")
    elif not any(_is_path_same_or_child(normalized, root) for root, _label, _source_types in _ALLOWED_ROOTS):
        raise HTTPException(status_code=422, detail="Use a Pocket Lab approved media folder path.")
    rel = normalized[2:] if normalized.startswith("~/") else normalized
    return Path.home() / rel


def mark_mappings_applied(app_id: str, mapping_ids: list[str], *, reason: str = "media action apply") -> dict[str, Any]:
    if str(app_id).strip().lower() != PHOTOPRISM_APP_ID:
        raise HTTPException(status_code=404, detail="PhotoPrism storage mappings are the first supported app mapping.")
    wanted = {str(item) for item in mapping_ids if item}
    if not wanted:
        return {"status": "unchanged", "app_id": PHOTOPRISM_APP_ID, "applied_count": 0}
    state = _state()
    mappings = state["apps"][PHOTOPRISM_APP_ID].setdefault("mappings", [])
    now = _now()
    applied: list[dict[str, Any]] = []
    for item in mappings:
        if not isinstance(item, dict) or item.get("mapping_id") not in wanted:
            continue
        item["status"] = "applied"
        item["pending_apply"] = False
        item["requires_restart"] = False
        item["applied_at"] = now
        item["updated_at"] = now
        item["apply_reason"] = reason[:120]
        applied.append(item)
    if applied:
        _write_state(state)
        for item in applied:
            _append_audit("pocketlab.audit.apps.storage_mapping.applied", item)
    return {
        "status": "applied" if applied else "unchanged",
        "app_id": PHOTOPRISM_APP_ID,
        "applied_count": len(applied),
        "mapping_ids": [item.get("mapping_id") for item in applied],
    }


def delete_mapping(app_id: str, mapping_id: str) -> dict[str, Any]:
    if str(app_id).strip().lower() != PHOTOPRISM_APP_ID:
        raise HTTPException(status_code=404, detail="PhotoPrism storage mappings are the first supported app mapping.")
    if not re.fullmatch(r"map-[a-f0-9]{14}", str(mapping_id or "")):
        raise HTTPException(status_code=404, detail="Storage mapping was not found.")
    state = _state()
    mappings = state["apps"][PHOTOPRISM_APP_ID].setdefault("mappings", [])
    kept = []
    removed: dict[str, Any] | None = None
    for item in mappings:
        if isinstance(item, dict) and item.get("mapping_id") == mapping_id:
            removed = item
        else:
            kept.append(item)
    if not removed:
        raise HTTPException(status_code=404, detail="Storage mapping was not found.")
    state["apps"][PHOTOPRISM_APP_ID]["mappings"] = kept
    _write_state(state)
    event = _append_audit("pocketlab.audit.apps.storage_mapping.deleted", removed)
    return {
        "status": "deleted",
        "accepted": True,
        "app_id": PHOTOPRISM_APP_ID,
        "mapping_id": mapping_id,
        "event": event,
        "summary": "Media folder disconnected. Pocket Lab recorded the change for safe app apply.",
    }


def catalog_storage_summary() -> dict[str, Any]:
    payload = list_mappings(PHOTOPRISM_APP_ID)
    mappings = payload.get("mappings") or []
    connected_labels = [str(item.get("label") or item.get("source_label") or "Media folder") for item in mappings if isinstance(item, dict)]
    return {
        "status": "not_connected" if not mappings else "pending_apply" if any(item.get("pending_apply") for item in mappings if isinstance(item, dict)) else "ready",
        "summary": "No media folders connected" if not mappings else ", ".join(connected_labels[:3]),
        "mappings": mappings,
        "count": len(mappings),
        "default_target": "import",
        "safe_modes": ["read_only", "read_write"],
        "allowed_sources": [
            {"source_type": "phone_media", "label": "Phone photos", "path_summary": "Camera folder"},
            {"source_type": "phone_media", "label": "Pictures", "path_summary": "Pictures"},
            {"source_type": "managed_media", "label": "Managed media", "path_summary": "Managed media"},
            {"source_type": "storage_device", "label": "Storage device", "path_summary": "Managed media"},
        ],
    }
