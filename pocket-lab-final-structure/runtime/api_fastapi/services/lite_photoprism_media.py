from __future__ import annotations

import hashlib
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_storage

PHOTOPRISM_APP_ID = "photoprism"
MEDIA_ACTIONS = {"import_photos", "index_photos"}
MEDIA_COMMAND_SUBJECT = "pocketlab.commands.lite.app.media"

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


def _state_path() -> Path:
    return deps.settings().state_dir / "lite_photoprism_media_operations.json"


def _evidence_path() -> Path:
    return deps.settings().state_dir / "lite_photoprism_media_evidence.json"


def _app_root() -> Path:
    return Path.home() / ".pocket_lab" / "lite" / "apps" / "photoprism"


def _env_file() -> Path:
    return _app_root() / "config" / "photoprism.env"


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
    payload: dict[str, Any] = {
        "action_id": action_id,
        "label": _operation_label(action_id),
        "status": status,
        "summary": _safe_text(operation.get("summary"), _operation_summary(action_id, status)),
        "started_at": operation.get("started_at"),
        "completed_at": operation.get("completed_at"),
        "mapping_count": int(operation.get("mapping_count") or 0),
        "evidence_status": _safe_text(operation.get("evidence_status"), "pending"),
    }
    if operation.get("evidence_ref"):
        payload["evidence_status"] = "saved"
    return payload


def media_status(app_id: str = PHOTOPRISM_APP_ID) -> dict[str, Any]:
    _validate_app_id(app_id)
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
    operation = {
        **previous,
        "operation_id": command.get("command_id") or previous.get("operation_id") or _operation_id(action),
        "app_id": PHOTOPRISM_APP_ID,
        "action_id": action,
        "status": status,
        "summary": _safe_text(summary, _operation_summary(action, status)),
        "mapping_count": int(command.get("mapping_count") or mapping_count() or 0),
        "evidence_status": "pending" if status in {"queued", "running"} else "saved",
        "updated_at": now,
    }
    if status in {"queued", "running"}:
        operation.setdefault("started_at", now)
    if status in {"succeeded", "failed", "not_ready"}:
        operation.setdefault("started_at", previous.get("started_at") or now)
        operation["completed_at"] = now
        operation["evidence_ref"] = f"apps/photoprism/media/{operation['operation_id']}.json"
    operations[action] = operation
    app_state["updated_at"] = now
    _write_state(state)
    if status in {"succeeded", "failed", "not_ready"}:
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

    record_operation(command, status="running", summary=_operation_summary(action, "running"))
    ready, reason = _runtime_ready()
    if not ready:
        operation = record_operation(command, status="failed", summary=reason)
        return {"status": "failed", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation}

    env_file = shlex.quote(str(_env_file()))
    cli = _photoprism_cli_command(action)
    script = f"set -Eeuo pipefail; set -a; source {env_file}; set +a; {cli}"
    try:
        completed = subprocess.run(
            ["proot-distro", "login", "ubuntu", "--", "bash", "-lc", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        operation = record_operation(command, status="failed", summary=f"{_operation_label(action)} timed out safely.")
        return {"status": "failed", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation}

    if completed.returncode == 0:
        operation = record_operation(command, status="succeeded", summary=_operation_summary(action, "succeeded"))
        return {"status": "succeeded", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation}

    summary = _sanitize_output(completed.stderr or completed.stdout) or f"{_operation_label(action)} failed safely."
    operation = record_operation(command, status="failed", summary=summary)
    return {"status": "failed", "app_id": PHOTOPRISM_APP_ID, "action_id": action, "operation": operation}
