from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_storage

PHOTOPRISM_APP_ID = "photoprism"
MEDIA_ACTIONS = {"import_photos", "index_photos"}
MEDIA_COMMAND_SUBJECT = "pocketlab.commands.lite.app.media"
STALE_OPERATION_SECONDS = int(os.environ.get("POCKETLAB_LITE_MEDIA_STALE_SECONDS", "1800"))
MEDIA_COMMAND_TIMEOUT_SECONDS = int(os.environ.get("POCKETLAB_LITE_MEDIA_COMMAND_TIMEOUT_SECONDS", "1800"))
ORPHANED_RUNNING_GRACE_SECONDS = int(os.environ.get("POCKETLAB_LITE_MEDIA_ORPHANED_GRACE_SECONDS", "60"))
_MEDIA_CANCEL_PATTERN = r"photoprism (import|index)|exiftool .*pocketlab-mappings|perl .*/exiftool .*pocketlab-mappings"
_PHONE_STORAGE_MEDIA_ROOTS = (
    ("dcim", "Camera photos"),
    ("pictures", "Pictures"),
    ("movies", "Videos"),
    ("shared/DCIM", "Camera photos"),
    ("shared/Pictures", "Pictures"),
    ("shared/Movies", "Videos"),
)
_PHONE_STORAGE_EXCLUDED_ROOTS = (
    ("shared/Android", "Android app data"),
    ("shared/Download", "Downloads and documents"),
    ("shared/Downloads", "Downloads and documents"),
    ("shared/Documents", "Documents"),
    ("shared/WhatsApp/Media/WhatsApp Documents", "WhatsApp documents"),
    ("shared/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Documents", "WhatsApp documents"),
    ("downloads", "Downloads and documents"),
    ("documents", "Documents"),
)

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


def _now() -> str:
    return deps.now_utc_iso()

def _parse_ts(value: Any) -> datetime | None:
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


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _state_path() -> Path:
    return deps.settings().state_dir / "lite_photoprism_media_operations.json"


def _evidence_path() -> Path:
    return deps.settings().state_dir / "lite_photoprism_media_evidence.json"


def _app_root() -> Path:
    return Path.home() / ".pocket_lab" / "lite" / "apps" / "photoprism"


def _env_file() -> Path:
    return _app_root() / "config" / "photoprism.env"


def _mapping_root_for_target(target: str) -> Path:
    base = _app_root() / ("originals" if target == "originals" else "import")
    return base / "pocketlab-mappings"


def _read_json(path: Path, default: Any) -> Any:
    return deps.core.read_json_file(path, default)


def _write_json(path: Path, payload: Any) -> None:
    deps.core.write_json_file(path, payload)


def _validate_app_id(app_id: Any) -> str:
    normalized = str(app_id or "").strip().lower().replace("_", "-")
    if normalized != PHOTOPRISM_APP_ID:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_app",
                "summary": "PhotoPrism is the first app with media import and index actions.",
            },
        )
    return normalized


def validate_action_id(action_id: Any) -> str:
    normalized = str(action_id or "").strip().lower().replace("-", "_")
    if normalized not in MEDIA_ACTIONS:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_action",
                "summary": "Choose Import photos or Index photos for PhotoPrism media.",
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


def _operation_label(action_id: str) -> str:
    return "Import photos" if action_id == "import_photos" else "Index photos"


def _operation_summary(action_id: str, status: str) -> str:
    label = _operation_label(action_id)
    if status == "queued":
        return f"{label} queued. Pocket Lab will run it through the backend worker."
    if status == "running":
        return f"{label} is running."
    if status == "succeeded":
        return f"{label} completed."
    if status == "cancelled":
        return f"{label} was stopped safely."
    if status == "not_ready":
        return f"{label} is not ready yet."
    if status == "failed":
        return f"{label} could not complete."
    return f"{label} status is available."


def _read_state() -> dict[str, Any]:
    payload = _read_json(_state_path(), {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("version", 1)
    payload.setdefault("apps", {})
    app = payload["apps"].setdefault(PHOTOPRISM_APP_ID, {})
    app.setdefault("operations", {})
    app.setdefault("updated_at", None)
    return payload


def _write_state(payload: dict[str, Any]) -> None:
    payload["updated_at"] = _now()
    _write_json(_state_path(), payload)


def _mappings() -> dict[str, Any]:
    try:
        payload = lite_app_storage.list_mappings(PHOTOPRISM_APP_ID)
        return payload if isinstance(payload, dict) else {"mappings": [], "count": 0}
    except Exception:
        return {"mappings": [], "count": 0, "summary": "No media folders connected yet."}


def mapping_count() -> int:
    payload = _mappings()
    return int(payload.get("count") or len(payload.get("mappings") or []) or 0)


def mapping_labels() -> list[str]:
    labels: list[str] = []
    for item in _mappings().get("mappings") or []:
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label") or item.get("source_label"), "Media folder")
        if label:
            labels.append(label[:80])
    return labels[:6]


def _public_operation(operation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(operation, dict):
        return None
    action_id = str(operation.get("action_id") or "").strip()
    if action_id not in MEDIA_ACTIONS:
        return None
    status = str(operation.get("status") or "unknown").strip().lower()
    progress = operation.get("progress") if isinstance(operation.get("progress"), dict) else {}
    payload: dict[str, Any] = {
        "action_id": action_id,
        "label": _operation_label(action_id),
        "status": status,
        "summary": _safe_text(operation.get("summary"), _operation_summary(action_id, status)),
        "started_at": operation.get("started_at"),
        "completed_at": operation.get("completed_at"),
        "mapping_count": int(operation.get("mapping_count") or 0),
        "evidence_status": _safe_text(operation.get("evidence_status"), "pending"),
        "phase": _safe_text(operation.get("phase"), progress.get("phase") or status),
        "progress": {
            "phase": _safe_text(progress.get("phase") or operation.get("phase"), status),
            "step": _safe_text(progress.get("step"), _operation_summary(action_id, status)),
            "current": int(progress.get("current") or 1),
            "total": int(progress.get("total") or 5),
            "percent": max(0, min(100, int(progress.get("percent") or 0))),
            "bounded": True,
            "timeout_seconds": MEDIA_COMMAND_TIMEOUT_SECONDS,
        },
    }
    if operation.get("evidence_ref") and payload.get("evidence_status") not in {"failed", "not_ready"}:
        payload["evidence_status"] = "saved"
    return payload


def _operation_is_stale(operation: dict[str, Any], *, now: datetime | None = None) -> bool:
    status = str(operation.get("status") or "").lower()
    if status not in {"queued", "running"}:
        return False
    started = _parse_ts(operation.get("started_at") or operation.get("updated_at"))
    if started is None:
        return False
    now = now or _utc_now_dt()
    return (now - started).total_seconds() >= STALE_OPERATION_SECONDS


def _running_operation_age_seconds(operation: dict[str, Any], *, now: datetime | None = None) -> float:
    started = _parse_ts(operation.get("started_at") or operation.get("updated_at"))
    if started is None:
        return 0.0
    now = now or _utc_now_dt()
    return max(0.0, (now - started).total_seconds())


def _cancel_operation_in_state(
    operation: dict[str, Any],
    *,
    action: str,
    now: str,
    summary: str,
) -> dict[str, Any]:
    operation["status"] = "cancelled"
    operation["summary"] = _safe_text(summary, _operation_summary(action, "cancelled"))
    operation["completed_at"] = now
    operation["updated_at"] = now
    operation["evidence_status"] = "saved"
    operation["evidence_ref"] = f"apps/photoprism/media/{operation.get('operation_id') or _operation_id(action)}.json"
    operation["phase"] = "cancelled"
    operation["progress"] = _progress_payload("cancelled", "Photo action stopped safely.", 5)
    return operation


def reconcile_orphaned_running_operations(app_id: str = PHOTOPRISM_APP_ID) -> int:
    """Close running media state when no PhotoPrism media process exists.

    This protects the Lite UI from staying in a false running state after a
    cancel, worker restart, or child process exit. A short grace window avoids
    racing the worker while it is applying mappings before the CLI starts.
    """
    _validate_app_id(app_id)
    if _matching_media_process_count() > 0:
        return 0

    state = _read_state()
    app_state = state.get("apps", {}).get(PHOTOPRISM_APP_ID, {})
    operations = app_state.get("operations") if isinstance(app_state.get("operations"), dict) else {}
    if not operations:
        return 0

    now_dt = _utc_now_dt()
    now = now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    changed = 0
    summary = "PhotoPrism media action was stopped because no running media process was found."
    for action, operation in list(operations.items()):
        if action not in MEDIA_ACTIONS or not isinstance(operation, dict):
            continue
        if str(operation.get("status") or "").lower() != "running":
            continue
        if _running_operation_age_seconds(operation, now=now_dt) < ORPHANED_RUNNING_GRACE_SECONDS:
            continue
        _cancel_operation_in_state(operation, action=action, now=now, summary=summary)
        _append_evidence(operation)
        changed += 1

    if changed:
        app_state["updated_at"] = now
        state["updated_at"] = now
        _write_state(state)
    return changed


def reconcile_stale_operations(app_id: str = PHOTOPRISM_APP_ID) -> int:
    """Close stale queued/running media operations without deleting evidence.

    This only updates Pocket Lab's local state/evidence. It does not execute shell
    commands, touch PhotoPrism runtime files, or mutate user media.
    """
    _validate_app_id(app_id)
    state = _read_state()
    app_state = state.get("apps", {}).get(PHOTOPRISM_APP_ID, {})
    operations = app_state.get("operations") if isinstance(app_state.get("operations"), dict) else {}
    if not operations:
        return 0
    now_dt = _utc_now_dt()
    now = now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    changed = 0
    for action, operation in list(operations.items()):
        if not isinstance(operation, dict) or not _operation_is_stale(operation, now=now_dt):
            continue
        operation["status"] = "failed"
        operation["summary"] = f"{_operation_label(str(operation.get('action_id') or action))} timed out before worker completion. Please retry after checking worker command handling."
        operation["completed_at"] = now
        operation["updated_at"] = now
        operation["evidence_status"] = "failed"
        operation["evidence_ref"] = f"apps/photoprism/media/{operation.get('operation_id') or _operation_id(str(operation.get('action_id') or action))}.json"
        _append_evidence(operation)
        changed += 1
    if changed:
        app_state["updated_at"] = now
        state["updated_at"] = now
        _write_state(state)
    return changed


def record_operation_failure(command: dict[str, Any], error: Any) -> dict[str, Any]:
    action = validate_action_id(command.get("action_id") or command.get("operation"))
    summary = _sanitize_output(str(error)) or f"{_operation_label(action)} failed safely."
    return record_operation(command, status="failed", summary=summary)


def media_status(app_id: str = PHOTOPRISM_APP_ID) -> dict[str, Any]:
    _validate_app_id(app_id)
    reconcile_stale_operations(app_id)
    reconcile_orphaned_running_operations(app_id)
    state = _read_state()
    app_state = state.get("apps", {}).get(PHOTOPRISM_APP_ID, {})
    operations = app_state.get("operations") if isinstance(app_state.get("operations"), dict) else {}
    mappings = _mappings()
    count = int(mappings.get("count") or 0)
    last_import = _public_operation(operations.get("import_photos"))
    last_index = _public_operation(operations.get("index_photos"))
    running = any(
        isinstance(item, dict) and str(item.get("status") or "").lower() in {"queued", "running"}
        for item in operations.values()
    )
    failed = any(
        isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "not_ready"}
        for item in operations.values()
    )
    if running:
        status = "running"
        summary = "PhotoPrism media action is running."
    elif count < 1:
        status = "not_connected"
        summary = "Connect a photo folder first."
    elif failed:
        status = "review"
        summary = "PhotoPrism media needs attention."
    else:
        status = "ready"
        summary = "Import ready."
    return {
        "status": status,
        "summary": summary,
        "mapping_count": count,
        "labels": mapping_labels(),
        "last_import": last_import,
        "last_index": last_index,
        "last_indexed_at": (last_index or {}).get("completed_at") if last_index else None,
        "last_imported_at": (last_import or {}).get("completed_at") if last_import else None,
        "operation_running": running,
        "evidence": media_evidence_summary(),
        "updated_at": app_state.get("updated_at") or state.get("updated_at"),
    }


def media_evidence_summary() -> dict[str, Any]:
    payload = _read_json(_evidence_path(), {})
    if not isinstance(payload, dict):
        payload = {}
    events = [item for item in payload.get("events") or [] if isinstance(item, dict)]
    return {
        "status": "saved" if events else "pending",
        "count": len(events),
        "summary": f"{len(events)} media record(s)" if events else "Media evidence pending",
    }


def _operation_id(action_id: str) -> str:
    digest = hashlib.sha256(f"{action_id}|{_now()}".encode("utf-8")).hexdigest()[:12]
    return f"photoprism-media-{digest}"


def media_command(action_id: str, *, reason: str | None = None, command_id: str | None = None) -> dict[str, Any]:
    action = validate_action_id(action_id)
    count = mapping_count()
    if count < 1:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "not_ready",
                "app_id": PHOTOPRISM_APP_ID,
                "action_id": action,
                "summary": "Connect a photo folder first.",
            },
        )
    command_ref = command_id or _operation_id(action)
    return {
        "command_id": command_ref,
        "app_id": PHOTOPRISM_APP_ID,
        "action_id": action,
        "operation": action,
        "reason": _safe_text(reason, "manual media action"),
        "requested_by": "lite-api",
        "mapping_count": count,
        "mapping_labels": mapping_labels(),
    }


def record_operation(command: dict[str, Any], *, status: str, summary: str | None = None) -> dict[str, Any]:
    action = validate_action_id(command.get("action_id") or command.get("operation"))
    now = _now()
    state = _read_state()
    app_state = state["apps"].setdefault(PHOTOPRISM_APP_ID, {"operations": {}})
    operations = app_state.setdefault("operations", {})
    previous = operations.get(action) if isinstance(operations.get(action), dict) else {}
    command_ref = str(command.get("command_id") or previous.get("operation_id") or _operation_id(action))
    same_operation = str(previous.get("operation_id") or "") == command_ref
    previous_for_operation = previous if same_operation else {}
    if (
        same_operation
        and str(previous.get("status") or "").lower() == "cancelled"
        and status in {"running", "failed", "succeeded"}
    ):
        # A late worker result from a cancelled command must not flip the UI
        # back to running/failed/succeeded after the user stopped it. New
        # commands have a new operation_id and are unaffected.
        return _public_operation(previous) or {}

    operation = {
        **previous_for_operation,
        "operation_id": command_ref,
        "app_id": PHOTOPRISM_APP_ID,
        "action_id": action,
        "status": status,
        "summary": _safe_text(summary, _operation_summary(action, status)),
        "mapping_count": int(command.get("mapping_count") or mapping_count() or 0),
        "runtime_mappings_used": int(command.get("runtime_mappings_used") or previous_for_operation.get("runtime_mappings_used") or 0),
        "skipped_overlapping_mappings": int(command.get("skipped_overlapping_mappings") or previous_for_operation.get("skipped_overlapping_mappings") or 0),
        "runtime_roots_used": int(command.get("runtime_roots_used") or previous_for_operation.get("runtime_roots_used") or command.get("runtime_mappings_used") or 0),
        "excluded_noisy_roots": int(command.get("excluded_noisy_roots") or previous_for_operation.get("excluded_noisy_roots") or 0),
        "evidence_status": "pending" if status in {"queued", "running"} else "saved",
        "updated_at": now,
    }

    if status in {"queued", "running"}:
        operation["started_at"] = previous_for_operation.get("started_at") or now
        operation.pop("completed_at", None)
        operation.pop("evidence_ref", None)

    progress = command.get("progress") if isinstance(command.get("progress"), dict) else None
    if progress:
        operation["progress"] = {
            "phase": _safe_text(progress.get("phase"), status),
            "step": _safe_text(progress.get("step"), _operation_summary(action, status)),
            "current": int(progress.get("current") or 1),
            "total": int(progress.get("total") or 5),
            "percent": max(0, min(100, int(progress.get("percent") or 0))),
            "bounded": True,
            "timeout_seconds": MEDIA_COMMAND_TIMEOUT_SECONDS,
        }
        operation["phase"] = operation["progress"]["phase"]

    if status in {"succeeded", "failed", "not_ready", "cancelled"}:
        operation["started_at"] = previous_for_operation.get("started_at") or now
        operation["completed_at"] = now
        operation["evidence_ref"] = f"apps/photoprism/media/{operation['operation_id']}.json"

    operations[action] = operation
    app_state["updated_at"] = now
    _write_state(state)
    if status in {"succeeded", "failed", "not_ready", "cancelled"}:
        _append_evidence(operation)
    return _public_operation(operation) or {}


def _append_evidence(operation: dict[str, Any]) -> dict[str, Any]:
    payload = _read_json(_evidence_path(), {})
    if not isinstance(payload, dict):
        payload = {}
    events = payload.setdefault("events", [])
    action = str(operation.get("action_id") or "index_photos")
    event = {
        "event_id": operation.get("operation_id"),
        "operation": action,
        "app_id": PHOTOPRISM_APP_ID,
        "status": operation.get("status"),
        "started_at": operation.get("started_at"),
        "completed_at": operation.get("completed_at"),
        "media_mappings": int(operation.get("mapping_count") or 0),
        "summary": _safe_text(operation.get("summary"), _operation_summary(action, str(operation.get("status") or "unknown"))),
        "phase": _safe_text(operation.get("phase"), str(operation.get("status") or "unknown")),
        "runtime_mappings_used": int(operation.get("runtime_mappings_used") or 0),
        "skipped_overlapping_mappings": int(operation.get("skipped_overlapping_mappings") or 0),
        "runtime_roots_used": int(operation.get("runtime_roots_used") or operation.get("runtime_mappings_used") or 0),
        "excluded_noisy_roots": int(operation.get("excluded_noisy_roots") or 0),
        "bounded": True,
        "timeout_seconds": MEDIA_COMMAND_TIMEOUT_SECONDS,
        "sensitive_values_hidden": True,
    }
    events.insert(0, event)
    payload["events"] = events[:100]
    payload["updated_at"] = _now()
    _write_json(_evidence_path(), payload)
    return event


def _sanitize_output(text: str) -> str:
    cleaned = re.sub(r"(?i)(password|token|secret|api[_-]?key|private[_ -]?key)\s*[:=]\s*\S+", r"\1=[hidden]", text or "")
    cleaned = re.sub(r"/data/data/\S+", "[protected-path]", cleaned)
    cleaned = re.sub(r"/home/\S+", "[local-path]", cleaned)
    cleaned = re.sub(r"~/.\S+", "[local-path]", cleaned)
    return cleaned[-500:]



def _mapping_slug(mapping_id: Any) -> str:
    raw = str(mapping_id or "mapping").strip().lower()
    safe = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    if not safe.startswith("map-"):
        safe = f"map-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:14]}"
    return safe[:80]


def _path_depth(value: str) -> int:
    return len([part for part in str(value or "").split("/") if part and part != "~"])


def _is_same_or_descendant_path(child: str, parent: str) -> bool:
    child_value = str(child or "").rstrip("/")
    parent_value = str(parent or "").rstrip("/")
    return child_value == parent_value or child_value.startswith(parent_value + "/")


def _optimized_runtime_mappings(mappings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Drop nested duplicate runtime mappings for the worker apply plan.

    Public mapping records are preserved for audit and user visibility, but the
    PhotoPrism runtime only receives the broadest approved source per target.
    This avoids scanning the same Android storage tree through several paths.
    """

    prepared: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for mapping in mappings:
        source_path = str(mapping.get("source_path") or "")
        target = str(mapping.get("target") or "import")
        prepared.append({**mapping, "_depth": _path_depth(source_path), "_target": target})

    selected: list[dict[str, Any]] = []
    for mapping in sorted(prepared, key=lambda item: (str(item.get("_target") or "import"), int(item.get("_depth") or 99), str(item.get("mapping_id") or ""))):
        source_path = str(mapping.get("source_path") or "")
        target = str(mapping.get("_target") or "import")
        parent = next(
            (item for item in selected if str(item.get("target") or "import") == target and _is_same_or_descendant_path(source_path, str(item.get("source_path") or ""))),
            None,
        )
        if parent:
            skipped.append({
                "mapping_id": str(mapping.get("mapping_id") or ""),
                "label": _safe_text(mapping.get("label") or mapping.get("source_label"), "Media folder"),
                "reason": "covered by a broader mapping",
                "covered_by": str(parent.get("mapping_id") or ""),
            })
            continue
        selected.append({k: v for k, v in mapping.items() if not k.startswith("_")})

    return selected, skipped


def _progress_payload(phase: str, step: str, current: int, total: int = 5) -> dict[str, Any]:
    current = max(1, min(total, int(current)))
    total = max(1, int(total))
    return {
        "phase": phase,
        "step": step,
        "current": current,
        "total": total,
        "percent": int((current / total) * 100),
        "bounded": True,
        "timeout_seconds": MEDIA_COMMAND_TIMEOUT_SECONDS,
    }


def _command_with_progress(command: dict[str, Any], phase: str, step: str, current: int, total: int = 5) -> dict[str, Any]:
    return {**command, "progress": _progress_payload(phase, step, current, total)}


def _media_root_slug(name: str) -> str:
    safe = re.sub(r"[^a-z0-9._-]+", "-", str(name or "media").strip().lower()).strip("-._")
    return safe[:48] or "media"


def _readable_directory(path: Path) -> bool:
    try:
        return path.exists() and path.is_dir() and os.access(path, os.R_OK)
    except OSError:
        return False


def _focused_phone_storage_sources(source_path: str, source: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return media-focused runtime roots for the user-visible ~/storage mapping.

    The Lite UI still exposes a single friendly "Phone storage" mapping, but
    the worker should not hand all of Android shared storage to PhotoPrism. On
    phones this can drag in app data, downloads, documents, PDFs, and chat
    exports. Instead, use photo/video-heavy roots and record sanitized excluded
    categories for evidence.
    """
    if str(source_path or "").strip() != lite_app_storage.PHONE_STORAGE_ROOT:
        return ([{"path": source, "suffix": "", "label": "Media folder"}], [])

    roots: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen_realpaths: set[str] = set()

    for relative, label in _PHONE_STORAGE_MEDIA_ROOTS:
        candidate = source / relative
        if not _readable_directory(candidate):
            continue
        try:
            real = str(candidate.resolve())
        except OSError:
            real = str(candidate)
        if real in seen_realpaths:
            continue
        seen_realpaths.add(real)
        roots.append({
            "path": candidate,
            "suffix": _media_root_slug(relative),
            "label": label,
        })

    for relative, label in _PHONE_STORAGE_EXCLUDED_ROOTS:
        candidate = source / relative
        if _readable_directory(candidate):
            excluded.append({"label": label, "reason": "excluded from PhotoPrism import runtime plan"})

    # If Android exposes a non-standard layout and none of the focused roots
    # exist, fall back to the root rather than making a valid mapping unusable.
    # This fallback is explicit in evidence through excluded_noisy_roots=0.
    if not roots:
        roots.append({"path": source, "suffix": "phone-storage", "label": "Phone storage"})

    return roots, excluded[:8]


def _clear_stale_mapping_links(active_targets: set[Path]) -> None:
    for root in {_mapping_root_for_target("import"), _mapping_root_for_target("originals")}:
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if child in active_targets:
                continue
            # Only remove links/files created inside Pocket Lab's mapping area.
            # Do not recursively delete directories because user media must never
            # be removed by mapping apply.
            try:
                if child.is_symlink() or child.is_file():
                    child.unlink()
            except OSError:
                continue


def _apply_storage_mappings_for_media(action: str) -> dict[str, Any]:
    """Apply backend-approved PhotoPrism mappings before Import/Index.

    The apply step creates sanitized symlink entries under PhotoPrism's managed
    import/originals mapping directory. For the user-visible ~/storage mapping,
    the worker expands to media-focused roots so PhotoPrism does not crawl noisy
    Android/document folders such as WhatsApp Documents or Downloads.
    """

    connected_mappings = lite_app_storage.runtime_mappings(PHOTOPRISM_APP_ID)
    mappings, optimized_skipped = _optimized_runtime_mappings(connected_mappings)
    applied_ids: list[str] = []
    covered_ids = [item["mapping_id"] for item in optimized_skipped if item.get("mapping_id")]
    skipped: list[dict[str, str]] = [*optimized_skipped]
    excluded_noisy_roots: list[dict[str, str]] = []
    active_targets: set[Path] = set()
    runtime_roots_used = 0

    for mapping in mappings:
        mapping_id = str(mapping.get("mapping_id") or "")
        source_path = str(mapping.get("source_path") or "")
        target = str(mapping.get("target") or "import")
        mode = str(mapping.get("mode") or "read_only")
        label = _safe_text(mapping.get("label") or mapping.get("source_label"), "Media folder")

        if mode != "read_only" and target == "import":
            skipped.append({"mapping_id": mapping_id, "label": label, "reason": "read-only import mappings are required"})
            continue

        try:
            source = lite_app_storage.resolve_mapping_source_path(source_path)
        except Exception:
            skipped.append({"mapping_id": mapping_id, "label": label, "reason": "source path was not approved"})
            continue

        if not _readable_directory(source):
            skipped.append({"mapping_id": mapping_id, "label": label, "reason": "source folder is not ready"})
            continue

        runtime_sources, excluded = _focused_phone_storage_sources(source_path, source)
        excluded_noisy_roots.extend(excluded)
        mapping_applied = False

        for index, runtime_source in enumerate(runtime_sources):
            runtime_path = runtime_source["path"]
            if not _readable_directory(runtime_path):
                continue

            suffix = str(runtime_source.get("suffix") or "")
            slug = _mapping_slug(mapping_id)
            if suffix:
                slug = f"{slug}-{suffix}"[:96]

            mapping_root = _mapping_root_for_target(target)
            mapping_root.mkdir(parents=True, exist_ok=True)
            link_path = mapping_root / slug
            active_targets.add(link_path)

            try:
                if link_path.is_symlink() or link_path.is_file():
                    current = link_path.readlink() if link_path.is_symlink() else None
                    if current is not None and str(current) == str(runtime_path):
                        mapping_applied = True
                        runtime_roots_used += 1
                        continue
                    link_path.unlink()
                elif link_path.exists():
                    skipped.append({"mapping_id": mapping_id, "label": label, "reason": "managed mapping path is occupied"})
                    continue
                os.symlink(runtime_path, link_path, target_is_directory=True)
                mapping_applied = True
                runtime_roots_used += 1
            except OSError:
                skipped.append({"mapping_id": mapping_id, "label": label, "reason": "mapping could not be applied"})

        if mapping_applied:
            applied_ids.append(mapping_id)
        elif runtime_sources:
            skipped.append({"mapping_id": mapping_id, "label": label, "reason": "no readable media-focused runtime roots were available"})

    _clear_stale_mapping_links(active_targets)

    ready_ids = [*applied_ids, *covered_ids]
    if ready_ids:
        lite_app_storage.mark_mappings_applied(
            PHOTOPRISM_APP_ID,
            ready_ids,
            reason=f"{_operation_label(action)} worker apply",
        )

    return {
        "status": "applied" if applied_ids else "not_ready",
        "applied_count": len(applied_ids),
        "ready_count": len(ready_ids),
        "runtime_mapping_count": len(mappings),
        "runtime_roots_used": runtime_roots_used,
        "skipped_count": len(skipped),
        "overlap_skipped_count": len(optimized_skipped),
        "excluded_noisy_roots": len(excluded_noisy_roots),
        "mapping_count": len(connected_mappings),
        "skipped": skipped[:6],
        "excluded": excluded_noisy_roots[:6],
    }

def _photoprism_cli_command(action: str) -> str:
    if action == "import_photos":
        return "photoprism import"
    if action == "index_photos":
        return "photoprism index"
    raise HTTPException(status_code=404, detail="Unsupported PhotoPrism media action.")


def _runtime_ready() -> tuple[bool, str]:
    if shutil.which("proot-distro") is None:
        return False, "PhotoPrism media execution requires the server runtime."
    if not _env_file().exists():
        return False, "PhotoPrism app config is not ready yet."
    return True, "PhotoPrism runtime is ready."



def _matching_media_process_lines() -> list[str]:
    try:
        found = subprocess.run(
            ["pgrep", "-af", _MEDIA_CANCEL_PATTERN],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []
    if found.returncode not in {0, 1}:
        return []
    lines = []
    for line in (found.stdout or "").splitlines():
        text = line.strip()
        if not text:
            continue
        if "pgrep -af" in text or "pkill" in text:
            continue
        lines.append(text)
    return lines


def _matching_media_process_count() -> int:
    return len(_matching_media_process_lines())


def _stop_media_processes() -> dict[str, Any]:
    before = _matching_media_process_count()
    if before < 1:
        return {"status": "idle", "matched": 0, "terminated": 0, "killed": 0}

    terminated = 0
    killed = 0
    try:
        term = subprocess.run(["pkill", "-TERM", "-f", _MEDIA_CANCEL_PATTERN], check=False, capture_output=True, text=True, timeout=5)
        terminated = before if term.returncode in {0, 1} else 0
    except Exception:
        terminated = 0

    try:
        import time
        for _ in range(5):
            time.sleep(1)
            if _matching_media_process_count() < 1:
                break
    except Exception:
        pass

    remaining = _matching_media_process_count()
    if remaining > 0:
        try:
            kill = subprocess.run(["pkill", "-KILL", "-f", _MEDIA_CANCEL_PATTERN], check=False, capture_output=True, text=True, timeout=5)
            killed = remaining if kill.returncode in {0, 1} else 0
        except Exception:
            killed = 0
        try:
            import time
            for _ in range(5):
                time.sleep(1)
                if _matching_media_process_count() < 1:
                    break
        except Exception:
            pass

    after = _matching_media_process_count()
    return {
        "status": "stopped" if after < 1 and (terminated or killed or before) else "unknown",
        "matched": before,
        "terminated": terminated,
        "killed": killed,
        "remaining": after,
    }


def cancel_media_action(app_id: str = PHOTOPRISM_APP_ID, *, reason: str | None = None) -> dict[str, Any]:
    """Backend-owned cancel for long-running PhotoPrism media work.

    This stops only PhotoPrism import/index child commands, never the web server,
    and records sanitized local evidence. It intentionally performs no frontend
    filesystem access and does not delete user media.
    """

    _validate_app_id(app_id)
    stop_result = _stop_media_processes()
    state = _read_state()
    app_state = state["apps"].setdefault(PHOTOPRISM_APP_ID, {"operations": {}})
    operations = app_state.setdefault("operations", {})
    changed: list[dict[str, Any]] = []
    summary = _safe_text(reason, "PhotoPrism media action was stopped safely.")
    now = _now()
    for action, operation in list(operations.items()):
        if action not in MEDIA_ACTIONS or not isinstance(operation, dict):
            continue
        if str(operation.get("status") or "").lower() not in {"queued", "running"}:
            continue
        _cancel_operation_in_state(operation, action=action, now=now, summary=summary)
        _append_evidence(operation)
        changed.append(_public_operation(operation) or {})

    if changed:
        app_state["updated_at"] = now
        state["updated_at"] = now
        _write_state(state)

    return {
        "status": "cancelled" if changed or int(stop_result.get("matched") or 0) > 0 else "idle",
        "accepted": True,
        "app_id": PHOTOPRISM_APP_ID,
        "action_id": "cancel_media",
        "cancelled_operations": len(changed),
        "processes": {
            "matched": int(stop_result.get("matched") or 0),
            "terminated": int(stop_result.get("terminated") or 0),
            "killed": int(stop_result.get("killed") or 0),
            "remaining": int(stop_result.get("remaining") or 0),
        },
        "summary": "PhotoPrism media action stopped safely." if changed or int(stop_result.get("matched") or 0) > 0 else "No PhotoPrism media action was running.",
        "evidence": {"status": "saved", "summary": "Cancel evidence saved." if changed else "No running media action found."},
    }


def execute_media_operation(command: dict[str, Any]) -> dict[str, Any]:
    """Worker-owned PhotoPrism media execution.

    This function is intentionally not called by the browser or FastAPI read paths.
    It runs only from the domain worker handler after FastAPI publishes the command.
    Raw PhotoPrism output is redacted and not returned in the default API surface.
    """
    _validate_app_id(command.get("app_id"))
    action = validate_action_id(command.get("action_id") or command.get("operation"))
    count = mapping_count()
    if count < 1:
        operation = record_operation(command, status="not_ready", summary="Connect a photo folder first.")
        return {"status": "not_ready", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation}

    record_operation(_command_with_progress(command, "starting", "Starting bounded PhotoPrism media job.", 1), status="running", summary="Starting PhotoPrism media job.")
    ready, reason = _runtime_ready()
    if not ready:
        operation = record_operation(command, status="failed", summary=reason)
        return {"status": "failed", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation}

    record_operation(_command_with_progress(command, "applying_storage", "Applying connected storage mappings safely.", 2), status="running", summary="Applying connected storage mappings safely.")
    apply_result = _apply_storage_mappings_for_media(action)
    if int(apply_result.get("applied_count") or 0) < 1:
        skipped = apply_result.get("skipped") if isinstance(apply_result.get("skipped"), list) else []
        reason = "Connected photo storage is not ready yet."
        if skipped and isinstance(skipped[0], dict):
            reason = str(skipped[0].get("reason") or reason)
        operation = record_operation(_command_with_progress(command, "failed", "Connected storage was not ready.", 5), status="failed", summary=f"{_operation_label(action)} could not apply connected storage: {reason}")
        return {
            "status": "failed",
            "app_id": PHOTOPRISM_APP_ID,
            "action_id": action,
            "operation": operation,
            "mapping_apply": {
                "status": "not_ready",
                "applied_count": 0,
                "skipped_count": int(apply_result.get("skipped_count") or 0),
            },
        }

    record_operation(_command_with_progress(command, "executing", f"Running {_operation_label(action)} in PhotoPrism.", 3), status="running", summary=f"{_operation_label(action)} is running in PhotoPrism.")

    env_file = shlex.quote(str(_env_file()))
    cli = _photoprism_cli_command(action)
    script = f"set -Eeuo pipefail; set -a; source {env_file}; set +a; {cli}"
    try:
        completed = subprocess.run(
            ["proot-distro", "login", "ubuntu", "--", "bash", "-lc", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=MEDIA_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        operation = record_operation(_command_with_progress(command, "timed_out", "PhotoPrism media job reached its bounded timeout.", 5), status="failed", summary=f"{_operation_label(action)} timed out safely.")
        return {"status": "failed", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation, "mapping_apply": {"status": str(apply_result.get("status") or "unknown"), "applied_count": int(apply_result.get("applied_count") or 0), "skipped_count": int(apply_result.get("skipped_count") or 0)}}

    if completed.returncode == 0:
        success_command = _command_with_progress(command, "done", "PhotoPrism media job completed and evidence was saved.", 5)
        success_command["runtime_mappings_used"] = int(apply_result.get("runtime_mapping_count") or 0)
        success_command["runtime_roots_used"] = int(apply_result.get("runtime_roots_used") or 0)
        success_command["skipped_overlapping_mappings"] = int(apply_result.get("overlap_skipped_count") or 0)
        success_command["excluded_noisy_roots"] = int(apply_result.get("excluded_noisy_roots") or 0)
        operation = record_operation(success_command, status="succeeded", summary=_operation_summary(action, "succeeded"))
        return {"status": "succeeded", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation, "mapping_apply": {"status": "applied", "applied_count": int(apply_result.get("applied_count") or 0), "ready_count": int(apply_result.get("ready_count") or 0), "runtime_mapping_count": int(apply_result.get("runtime_mapping_count") or 0), "runtime_roots_used": int(apply_result.get("runtime_roots_used") or 0), "skipped_count": int(apply_result.get("skipped_count") or 0), "overlap_skipped_count": int(apply_result.get("overlap_skipped_count") or 0), "excluded_noisy_roots": int(apply_result.get("excluded_noisy_roots") or 0)}}

    summary = _sanitize_output(completed.stderr or completed.stdout) or f"{_operation_label(action)} failed safely."
    operation = record_operation(_command_with_progress(command, "failed", "PhotoPrism media job failed safely.", 5), status="failed", summary=summary)
    return {"status": "failed", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation, "mapping_apply": {"status": str(apply_result.get("status") or "unknown"), "applied_count": int(apply_result.get("applied_count") or 0), "skipped_count": int(apply_result.get("skipped_count") or 0)}}
