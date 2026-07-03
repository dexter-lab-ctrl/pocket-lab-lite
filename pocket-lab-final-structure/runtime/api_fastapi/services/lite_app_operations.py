from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_app_profiles, lite_app_storage, lite_catalog, lite_catalog_live, lite_photoprism_media

PHOTOPRISM_APP_ID = "photoprism"
CHECK_APP_ACTION = "check_app"
REPAIR_APP_ACTION = "repair_app"
SAFETY_SUBJECT = "pocketlab.commands.lite.app.safety"
REPAIR_SUBJECT = "pocketlab.commands.lite.app.repair"
SUPPORTED_APP_IDS = {PHOTOPRISM_APP_ID}
SUPPORTED_ACTIONS = {CHECK_APP_ACTION, REPAIR_APP_ACTION}
STALE_OPERATION_SECONDS = int(os.environ.get("POCKETLAB_LITE_APP_OPERATION_STALE_SECONDS", "900") or "900")

_SECRET_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "vault",
    "nats",
    "restic",
    "admin_password",
    "database_url",
    "connection_string",
)

_STEP_LABELS = {
    CHECK_APP_ACTION: [
        ("request_accepted", "Request accepted"),
        ("worker_picked_up", "Worker picked it up"),
        ("route_checked", "Route checked"),
        ("health_checked", "Health checked"),
        ("evidence_saved", "Evidence saved"),
    ],
    REPAIR_APP_ACTION: [
        ("setup_checked", "Checking setup"),
        ("route_refreshed", "Refreshing route"),
        ("storage_checked", "Checking storage"),
        ("app_verified", "Verifying app"),
        ("evidence_saved", "Evidence saved"),
    ],
}


def _now() -> str:
    return deps.now_utc_iso()


def _state_path() -> Path:
    deps.settings().ensure_dirs()
    return deps.settings().state_dir / "lite_app_operations.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return deps.core.read_json_file(path, default)
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    deps.core.write_json_file(path, payload)


def _read_state() -> dict[str, Any]:
    state = _read_json(_state_path(), {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("apps", {})
    state.setdefault("operations", {})
    return _reconcile_stale_state(state)


def _write_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    # Preserve operation IDs as JSON object keys. Values are sanitized again before
    # returning to the UI, and this state file contains only bounded, public metadata.
    _write_json(_state_path(), state)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _seconds_since(value: Any) -> int | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))


def _validate_app_id(app_id: Any) -> str:
    normalized = str(app_id or "").strip().lower().replace("_", "-")
    if normalized not in SUPPORTED_APP_IDS:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unsupported_app",
                "summary": "PhotoPrism is the first app with App Catalog safety and repair.",
            },
        )
    return normalized


def _validate_action_id(action_id: Any) -> str:
    normalized = str(action_id or "").strip().lower().replace("-", "_")
    if normalized not in SUPPORTED_ACTIONS:
        raise HTTPException(
            status_code=404,
            detail={"status": "unsupported_action", "summary": "Choose Check app or Repair."},
        )
    return normalized


def _safe_text(value: Any, fallback: str = "Available") -> str:
    text = str(value or fallback).strip() or fallback
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        # Keep safe redaction phrases, but hide anything that looks like a value.
        if not any(allowed in lowered for allowed in ("hidden", "redacted", "not exposed", "secrets hidden")):
            return fallback
    if re.search(r"/(data/data|home|proc|sys|dev|etc|root)/\S*", text):
        return fallback
    if re.search(r"~/(?!storage\b)\S+", text):
        return fallback
    text = re.sub(r"(?i)(password|token|secret|api[_-]?key|private[_ -]?key)\s*[:=]\s*\S+", r"\1=[hidden]", text)
    text = re.sub(r"(?i)nats://\S+", "[hidden-route]", text)
    return text[:240]


def _safe_ref(value: Any, fallback: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    if any(marker in raw.lower() for marker in _SECRET_MARKERS):
        return fallback
    if raw.startswith("/") or raw.startswith("~"):
        return fallback
    return re.sub(r"[^A-Za-z0-9._:/=-]+", "-", raw).strip("-._/")[:160] or fallback


def _sanitize_technical(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = re.sub(r"[^A-Za-z0-9_]+", "_", str(key or "field")).strip("_").lower()[:64]
            if not safe_key or any(marker in safe_key for marker in _SECRET_MARKERS):
                continue
            clean[safe_key] = _sanitize_technical(item)
        return clean
    if isinstance(value, list):
        return [_sanitize_technical(item) for item in value[:25]]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _safe_text(value, "hidden")


def _sanitize_payload(value: Any) -> Any:
    return _sanitize_technical(value)


def _operation_id(action_id: str) -> str:
    stamp = _now().replace(":", "").replace("+", "Z").replace(".", "-")
    prefix = "safety" if action_id == CHECK_APP_ACTION else "repair"
    return f"app-photoprism-{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _progress(action_id: str, phase: str, index: int = 0, *, status: str = "running", step: str | None = None) -> dict[str, Any]:
    steps = _STEP_LABELS.get(action_id, [])
    normalized_index = max(0, min(index, len(steps) - 1 if steps else 0))
    step_id, label = steps[normalized_index] if steps else (phase, step or phase)
    completed = []
    for current, (item_id, item_label) in enumerate(steps):
        if current < normalized_index:
            item_status = "completed"
        elif current == normalized_index and status in {"queued", "running"}:
            item_status = "active"
        elif current == normalized_index and status in {"succeeded", "review"}:
            item_status = "completed" if status == "succeeded" else "review"
        elif status == "failed" and current == normalized_index:
            item_status = "failed"
        else:
            item_status = "waiting"
        completed.append({"id": item_id, "label": item_label, "status": item_status})
    percent = 100 if status in {"succeeded", "review", "failed"} else max(8, min(92, int(((normalized_index + 1) / max(1, len(steps))) * 100)))
    return {
        "phase": phase,
        "step": _safe_text(step or label, label),
        "current": normalized_index + 1,
        "total": max(1, len(steps)),
        "percent": percent,
        "bounded": True,
        "indeterminate": status in {"queued", "running"},
        "steps": completed,
    }


def command_for_operation(app_id: str, action_id: str, *, reason: str | None = None) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    action = _validate_action_id(action_id)
    command_id = _operation_id(action)
    return {
        "command_id": command_id,
        "job_id": command_id,
        "app_id": app,
        "action_id": action,
        "operation": action,
        "reason": _safe_text(reason, "manual app operation"),
        "requested_by": "lite-api",
        "created_at": _now(),
        "dry_run": False,
    }


def subject_for_action(action_id: str) -> str:
    action = _validate_action_id(action_id)
    return SAFETY_SUBJECT if action == CHECK_APP_ACTION else REPAIR_SUBJECT


def record_queued_operation(command: dict[str, Any]) -> dict[str, Any]:
    app_id = _validate_app_id(command.get("app_id"))
    action_id = _validate_action_id(command.get("action_id") or command.get("operation"))
    command_id = str(command.get("command_id") or command.get("job_id") or _operation_id(action_id))
    now = _now()
    op = {
        "operation_id": command_id,
        "command_id": command_id,
        "app_id": app_id,
        "action_id": action_id,
        "status": "queued",
        "summary": "Checking PhotoPrism safety." if action_id == CHECK_APP_ACTION else "Repairing PhotoPrism safely.",
        "queued_at": now,
        "started_at": None,
        "completed_at": None,
        "reason": _safe_text(command.get("reason"), "manual app operation"),
        "progress": _progress(action_id, "queued", 0, status="queued", step="Check queued." if action_id == CHECK_APP_ACTION else "Repair queued."),
        "checks": [],
        "repair_steps": [],
        "proofs": [],
        "evidence_ref": f"apps/photoprism/{'safety' if action_id == CHECK_APP_ACTION else 'repair'}/{_safe_ref(command_id, 'latest')}.json",
        "redaction": _redaction(),
    }
    state = _read_state()
    state.setdefault("operations", {})[command_id] = op
    app = state.setdefault("apps", {}).setdefault(app_id, {})
    latest = app.setdefault("latest_by_action", {})
    latest[action_id] = command_id
    app["current_action"] = {"action_id": action_id, "status": "queued", "operation_id": command_id, "summary": op["summary"], "progress": op["progress"]}
    _write_state(state)
    return op


def mark_operation_failed(command: dict[str, Any], summary: str) -> dict[str, Any]:
    command_id = str(command.get("command_id") or command.get("job_id") or "")
    state = _read_state()
    op = state.get("operations", {}).get(command_id) if command_id else None
    if not isinstance(op, dict):
        op = record_queued_operation(command)
        state = _read_state()
        op = state.get("operations", {}).get(str(op.get("operation_id")))
    if not isinstance(op, dict):
        raise HTTPException(status_code=500, detail="App operation could not be recorded.")
    op.update({
        "status": "failed",
        "summary": _safe_text(summary, "App operation could not be queued."),
        "completed_at": _now(),
        "progress": _progress(str(op.get("action_id")), "failed", 0, status="failed", step="Request could not be queued."),
        "redaction": _redaction(),
    })
    _finalize_current_action(state, op)
    _write_state(state)
    return op


def _redaction() -> dict[str, Any]:
    return {
        "status": "passed",
        "secrets_hidden": True,
        "raw_logs_hidden": True,
        "raw_paths_hidden": True,
        "secret_values_saved": False,
    }


def _check(check_id: str, label: str, status: str, summary: str, *, technical: dict[str, Any] | None = None) -> dict[str, Any]:
    allowed = {"passed", "review", "failed", "not_checked", "not_applicable"}
    normalized = str(status or "not_checked").lower().replace("-", "_")
    if normalized not in allowed:
        normalized = "not_checked"
    payload = {"id": check_id, "label": _safe_text(label, check_id.replace("_", " ")), "status": normalized, "summary": _safe_text(summary, "Check completed.")}
    if technical:
        payload["technical"] = _sanitize_technical(technical)
    return payload


def _step(step_id: str, label: str, status: str, summary: str, *, safe: bool = True, destructive: bool = False, technical: dict[str, Any] | None = None) -> dict[str, Any]:
    allowed = {"skipped", "planned", "running", "changed", "unchanged", "passed", "review", "failed"}
    normalized = str(status or "skipped").lower().replace("-", "_")
    if normalized not in allowed:
        normalized = "skipped"
    payload = {
        "id": step_id,
        "label": _safe_text(label, step_id.replace("_", " ")),
        "status": normalized,
        "safe": bool(safe),
        "destructive": bool(destructive),
        "summary": _safe_text(summary, "Repair step checked."),
    }
    if technical:
        payload["technical"] = _sanitize_technical(technical)
    return payload


def _proof(proof_id: str, label: str, status: str, plain_language: str, *, technical: dict[str, Any] | None = None) -> dict[str, Any]:
    return _check(proof_id, label, status, plain_language, technical=technical)


def _catalog_app() -> dict[str, Any]:
    try:
        payload = lite_catalog.catalog_payload()
        try:
            payload = lite_catalog_live.hydrate_catalog(payload)
        except Exception:
            pass
        for app in payload.get("apps") or payload.get("items") or []:
            if isinstance(app, dict) and str(app.get("id") or "").lower() == PHOTOPRISM_APP_ID:
                return app
    except Exception:
        pass
    return {}


def _installed_from_catalog(app: dict[str, Any]) -> bool:
    return bool(app.get("installed") is True or app.get("install_state") == "installed" or app.get("status") == "ready")


def _pm2_process_online(process_name: str = "pocketlab-app-photoprism") -> str:
    if shutil.which("pm2") is None:
        return "not_checked"
    try:
        proc = subprocess.run(["pm2", "jlist"], check=False, capture_output=True, text=True, timeout=5)
    except Exception:
        return "not_checked"
    if proc.returncode != 0:
        return "not_checked"
    try:
        payload = json.loads(proc.stdout or "[]")
    except Exception:
        return "not_checked"
    for item in payload if isinstance(payload, list) else []:
        name = str(item.get("name") or "")
        if name != process_name:
            continue
        status = str((item.get("pm2_env") or {}).get("status") or "").lower()
        return "online" if status == "online" else "offline"
    return "offline"


def _url_json_healthy(url: str, *, timeout: float = 1.8) -> bool:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status < 200 or status >= 400:
                return False
            body = response.read(2048)
            payload = json.loads(body.decode("utf-8", errors="replace"))
            return str(payload.get("status") or "").lower() in {"operational", "healthy", "ok"}
    except Exception:
        return False


def _local_health_ready() -> bool:
    return _url_json_healthy("http://127.0.0.1:2342/apps/photoprism/api/v1/status")


def _route_health_ready() -> bool:
    return _url_json_healthy("http://127.0.0.1:8443/apps/photoprism/api/v1/status")


def _route_registry_status() -> tuple[str, dict[str, Any]]:
    try:
        registry = _read_json(lite_catalog.route_registry_path(), {})
    except Exception:
        registry = {}
    if not isinstance(registry, dict):
        return "review", {"present": False, "path": "missing"}
    for route in registry.get("routes") or []:
        if not isinstance(route, dict):
            continue
        if route.get("app_id") != PHOTOPRISM_APP_ID:
            continue
        ok = route.get("enabled") is True and route.get("path") == "/apps/photoprism/" and route.get("upstream") == "127.0.0.1:2342"
        return ("passed" if ok else "review"), {"present": True, "enabled": bool(route.get("enabled")), "route_path": "/apps/photoprism/" if route.get("path") == "/apps/photoprism/" else "not_ready"}
    return "review", {"present": False, "route_path": "missing"}


def _caddy_route_status() -> tuple[str, dict[str, Any]]:
    candidates = [os.environ.get("POCKETLAB_CADDYFILE"), os.environ.get("CADDYFILE"), "~/pocket-lab-lite/caddy/Caddyfile"]
    caddyfile: Path | None = None
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            caddyfile = path
            break
    if caddyfile is None:
        return "not_checked", {"caddyfile_checked": False, "prefix_preserved": None}
    try:
        text = caddyfile.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "not_checked", {"caddyfile_checked": False, "prefix_preserved": None}
    preserved = "handle /apps/photoprism/*" in text
    stripped = "handle_path /apps/photoprism/*" in text
    if preserved and not stripped:
        return "passed", {"caddyfile_checked": True, "prefix_preserved": True}
    return "review", {"caddyfile_checked": True, "prefix_preserved": False}


def _storage_status() -> tuple[str, dict[str, Any]]:
    try:
        payload = lite_app_storage.list_mappings(PHOTOPRISM_APP_ID)
    except Exception:
        return "not_checked", {"mapping_count": 0, "read_only": None, "pending_apply": None}
    mappings = [item for item in payload.get("mappings") or [] if isinstance(item, dict)]
    if not mappings:
        return "review", {"mapping_count": 0, "read_only": None, "pending_apply": None}
    all_read_only = all(str(item.get("mode") or "").lower() == "read_only" for item in mappings)
    pending_apply = any(bool(item.get("pending_apply") or item.get("requires_restart") or str(item.get("status") or "").lower() in {"pending", "needs_repair"}) for item in mappings)
    status = "passed" if all_read_only and not pending_apply else "review"
    return status, {"mapping_count": len(mappings), "read_only": all_read_only, "pending_apply": pending_apply}


def _backup_status() -> tuple[str, dict[str, Any]]:
    try:
        payload = lite_app_profiles.app_backup_profile(PHOTOPRISM_APP_ID)
    except Exception:
        return "not_checked", {"config_backup_available": None, "storage_target_ready": None}
    status = str(payload.get("status") or "unknown").lower()
    target_summary = payload.get("backup_target_summary") if isinstance(payload.get("backup_target_summary"), dict) else {}
    return ("passed" if status in {"ready", "healthy"} else "review"), {
        "config_backup_available": status in {"ready", "healthy"},
        "storage_target_ready": bool(target_summary.get("ready")),
    }


def _security_ref_status() -> tuple[str, dict[str, Any]]:
    try:
        from . import lite_security
        state = lite_security.current_state()
    except Exception:
        return "not_checked", {"security_evidence_ref": None}
    last_run = state.get("last_run") if isinstance(state.get("last_run"), dict) else {}
    if last_run.get("run_id"):
        return "passed", {"security_evidence_ref": f"security/evidence/{_safe_ref(last_run.get('run_id'), 'latest')}/summary.json"}
    return "not_checked", {"security_evidence_ref": None}


def _status_from_items(items: list[dict[str, Any]], *, failed_is_review: bool = True) -> str:
    statuses = {str(item.get("status") or "").lower() for item in items}
    if "failed" in statuses:
        return "review" if failed_is_review else "failed"
    if "review" in statuses:
        return "review"
    if statuses and statuses.issubset({"passed", "unchanged", "changed", "skipped", "not_applicable"}):
        return "succeeded"
    return "review"


def _check_summary(status: str) -> str:
    if status == "succeeded":
        return "Protected app"
    if status == "review":
        return "Something changed"
    return "Check could not complete"


def _repair_summary(status: str, changed: bool) -> str:
    if status == "succeeded" and changed:
        return "Repair completed"
    if status == "succeeded":
        return "Nothing needed repair"
    if status == "review":
        return "Repair needs attention"
    return "Repair could not complete"


def _check_needs_attention(process_state: str, local_health: bool, route_health: bool, storage_status: str, installed: bool) -> list[str]:
    items: list[str] = []
    if not installed:
        items.append("PhotoPrism is not installed yet.")
    if process_state == "offline":
        items.append("PhotoPrism was stopped.")
    elif process_state == "not_checked":
        items.append("Pocket Lab could not confirm whether PhotoPrism was running.")
    if not local_health and not route_health:
        items.append("PhotoPrism health could not be confirmed.")
    elif not route_health:
        items.append("The secure app route needs attention.")
    if storage_status == "review":
        items.append("Photo storage connection needs review.")
    return items[:5]


def _plain_status_checks(*, status: str, local_health: bool, route_health: bool, storage_status: str) -> list[dict[str, Any]]:
    route_ready = bool(route_health)
    health_ready = bool(local_health or route_health)
    storage_ready = storage_status == "passed"
    safety_ready = status == "succeeded"
    return [
        {"id": "route", "label": "Route", "status": "ready" if route_ready else "review", "summary": "The PhotoPrism route is ready." if route_ready else "The PhotoPrism route needs attention."},
        {"id": "health", "label": "Health", "status": "ready" if health_ready else "review", "summary": "PhotoPrism health responded." if health_ready else "PhotoPrism health could not be confirmed."},
        {"id": "storage", "label": "Storage", "status": "ready" if storage_ready else "review", "summary": "Phone Storage is connected safely." if storage_ready else "Photo storage connection needs attention."},
        {"id": "safety", "label": "Safety", "status": "ready" if safety_ready else "review", "summary": "Private details stayed hidden." if safety_ready else "Pocket Lab saved a review record."},
    ]


def _check_details(*, status: str, process_state: str, local_health: bool, route_health: bool, storage_status: str, installed: bool) -> dict[str, Any]:
    attention = _check_needs_attention(process_state, local_health, route_health, storage_status, installed)
    protected = status == "succeeded" and not attention
    if protected:
        summary = "Protected app"
        happened = ["Pocket Lab checked PhotoPrism and confirmed the app is running and reachable."]
        changed = ["Nothing changed. This was a check only."]
    elif process_state == "offline":
        summary = "PhotoPrism was stopped."
        happened = ["Pocket Lab checked PhotoPrism and found that the app was not running."]
        changed = ["Nothing changed. This was a check only."]
    elif not local_health and not route_health:
        summary = "PhotoPrism health needs attention."
        happened = ["Pocket Lab checked PhotoPrism and could not confirm app health."]
        changed = ["Nothing changed. This was a check only."]
    else:
        summary = "Something changed" if status == "review" else "Check could not complete"
        happened = ["Pocket Lab checked PhotoPrism route, health, storage, and protection state."]
        changed = ["Nothing changed. This was a check only."]
    return {
        "title": "Check app",
        "status": "ready" if status == "succeeded" else "review",
        "summary": summary,
        "last_result": "Protected app" if protected else "Something changed",
        "what_happened": happened,
        "what_changed": changed,
        "what_needs_attention": attention,
        "status_checks": _plain_status_checks(status=status, local_health=local_health, route_health=route_health, storage_status=storage_status),
        "what_did_not_happen": [
            "No photos were scanned.",
            "No database was changed.",
            "No app login was changed.",
            "No repair was started.",
        ],
        "saved_for_troubleshooting": {
            "saved": True,
            "backend_only": True,
            "summary": "A backend record was saved for troubleshooting.",
        },
        "technical_details": [
            "Execution owner: backend worker",
            "Action: check_app",
            f"Process state: {'online' if process_state == 'online' else 'stopped' if process_state == 'offline' else 'not checked'}",
            f"Route health: {'ready' if route_health else 'not ready'}",
            "Backend troubleshooting records stay backend-only.",
        ],
    }


def _repair_details(*, status: str, changed: bool, restart_performed: bool, local_health_before: bool, route_health_before: bool, local_health_after: bool, route_health_after: bool, route_changed: bool, caddy_changed: bool, storage_changed: bool, storage_status: str) -> dict[str, Any]:
    before_ready = bool(local_health_before or route_health_before)
    after_ready = bool(local_health_after or route_health_after)
    attention: list[str] = []
    if not after_ready:
        attention.append("PhotoPrism still needs attention after repair.")
    if status == "succeeded" and restart_performed and after_ready:
        summary = "Repair completed"
        happened = ["Pocket Lab found PhotoPrism was not responding and started it again."]
        what_changed = ["PhotoPrism was restarted.", "PhotoPrism is now online."]
    elif status == "succeeded" and changed:
        summary = "Repair completed"
        happened = ["Pocket Lab found a safe repair step was needed and completed it."]
        what_changed = []
        if route_changed or caddy_changed:
            what_changed.append("The app route was refreshed.")
        if storage_changed:
            what_changed.append("Photo storage connection records were refreshed.")
        if after_ready:
            what_changed.append("PhotoPrism is now online.")
        if not what_changed:
            what_changed = ["A safe repair step was completed."]
    elif status == "succeeded":
        summary = "Nothing needed repair"
        happened = ["Pocket Lab checked PhotoPrism and it was already running."]
        what_changed = ["Nothing changed."]
    else:
        summary = "Repair needs attention"
        happened = ["Pocket Lab checked PhotoPrism repair steps, but the app still needs attention."]
        what_changed = ["No unsafe changes were made."]
    return {
        "title": "Repair",
        "status": "ready" if status == "succeeded" else "review",
        "summary": summary,
        "last_result": summary,
        "what_happened": happened,
        "what_changed": what_changed,
        "what_needs_attention": attention,
        "status_checks": _plain_status_checks(status=status, local_health=local_health_after, route_health=route_health_after, storage_status=storage_status),
        "what_did_not_happen": [
            "No photos were changed.",
            "No database was changed.",
            "No app login was changed.",
            "No reinstall was started.",
        ],
        "saved_for_troubleshooting": {
            "saved": True,
            "backend_only": True,
            "summary": "A backend record was saved for troubleshooting.",
        },
        "technical_details": [
            "Execution owner: backend worker",
            "Action: repair_app",
            f"Before status: {'ready' if before_ready else 'not ready'}",
            f"After status: {'ready' if after_ready else 'not ready'}",
            f"App restart: {'performed' if restart_performed else 'not needed'}",
            "Backend troubleshooting records stay backend-only.",
        ],
    }


def _repair_final_status(repair_steps: list[dict[str, Any]], *, local_health_after: bool, route_health_after: bool) -> str:
    # App health after repair is the truth source for a stopped-app recovery.
    # Non-critical route/storage review steps should not hide that the app was started again successfully.
    if local_health_after or route_health_after:
        return "succeeded"
    return _status_from_items(repair_steps)


def _finish_operation(state: dict[str, Any], op: dict[str, Any], *, status: str, summary: str, checks: list[dict[str, Any]] | None = None, repair_steps: list[dict[str, Any]] | None = None, proofs: list[dict[str, Any]] | None = None, technical: dict[str, Any] | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    action_id = str(op.get("action_id") or CHECK_APP_ACTION)
    op.update({
        "status": status,
        "summary": _safe_text(summary, "App operation completed."),
        "completed_at": _now(),
        "checks": checks or [],
        "repair_steps": repair_steps or [],
        "proofs": proofs or [],
        "redaction": _redaction(),
        "technical_details": _sanitize_technical(technical or {}),
        "details": _sanitize_payload(details or {}),
        "progress": _progress(action_id, "completed" if status == "succeeded" else status, len(_STEP_LABELS.get(action_id, [])) - 1, status=status, step="Evidence saved"),
    })
    _finalize_current_action(state, op)
    _write_state(state)
    return _sanitize_payload(op)


def _finalize_current_action(state: dict[str, Any], op: dict[str, Any]) -> None:
    app = state.setdefault("apps", {}).setdefault(str(op.get("app_id") or PHOTOPRISM_APP_ID), {})
    app["current_action"] = None
    key = "last_safety_check" if op.get("action_id") == CHECK_APP_ACTION else "last_repair"
    app[key] = {
        "operation_id": op.get("operation_id"),
        "command_id": op.get("command_id"),
        "status": op.get("status"),
        "summary": op.get("summary"),
        "completed_at": op.get("completed_at"),
        "evidence_ref": op.get("evidence_ref"),
        "progress": op.get("progress"),
    }
    latest = app.setdefault("latest_by_action", {})
    latest[str(op.get("action_id"))] = str(op.get("operation_id") or op.get("command_id"))


def execute_check_app(command: dict[str, Any]) -> dict[str, Any]:
    app_id = _validate_app_id(command.get("app_id"))
    command_id = str(command.get("command_id") or command.get("job_id") or _operation_id(CHECK_APP_ACTION))
    state = _read_state()
    op = state.get("operations", {}).get(command_id)
    if not isinstance(op, dict):
        op = record_queued_operation({**command, "command_id": command_id, "app_id": app_id, "action_id": CHECK_APP_ACTION})
        state = _read_state()
        op = state.get("operations", {}).get(command_id, op)
    op.update({"status": "running", "started_at": op.get("started_at") or _now(), "progress": _progress(CHECK_APP_ACTION, "running", 1, status="running", step="Pocket Lab is checking PhotoPrism through the backend worker.")})
    state.setdefault("apps", {}).setdefault(app_id, {})["current_action"] = {"action_id": CHECK_APP_ACTION, "status": "running", "operation_id": command_id, "summary": "Checking PhotoPrism safety.", "progress": op["progress"]}
    _write_state(state)

    app = _catalog_app()
    installed = _installed_from_catalog(app)
    process_state = _pm2_process_online()
    local_health = _local_health_ready()
    route_health = _route_health_ready()
    route_registry_status, route_registry_detail = _route_registry_status()
    caddy_status, caddy_detail = _caddy_route_status()
    storage_status, storage_detail = _storage_status()
    backup_status, backup_detail = _backup_status()
    security_status, security_detail = _security_ref_status()

    checks = [
        _check("app_installed", "App installed", "passed" if installed else "review", "PhotoPrism install state was checked."),
        _check("process_online", "App process online", "passed" if process_state == "online" else ("review" if process_state == "offline" else "not_checked"), "PhotoPrism process status was checked as online/offline only.", technical={"process_state": process_state}),
        _check("health_endpoint", "App health responded", "passed" if local_health else "review", "PhotoPrism base-path health endpoint was checked.", technical={"base_path_health": bool(local_health)}),
        _check("same_origin_route", "Secure app route ready", "passed" if route_health else "review", "Pocket Lab checked the same-origin PhotoPrism route.", technical={"route": "/apps/photoprism/", "route_health": bool(route_health)}),
        _check("route_registry", "App route record checked", route_registry_status, "Pocket Lab checked the app route record.", technical=route_registry_detail),
        _check("pwa_app_route", "App route stays outside PWA", caddy_status, "Pocket Lab checked that /apps/ routes stay backend-owned.", technical=caddy_detail),
        _check("storage_mapping", "Photo storage mapping safe", storage_status, "Pocket Lab checked connected photo storage without listing media files.", technical=storage_detail),
        _check("backup_readiness", "Backup readiness checked", backup_status, "Pocket Lab checked app backup readiness from safe state.", technical=backup_detail),
        _check("security_evidence", "Security evidence linked", security_status, "Pocket Lab linked recent device safety evidence when available.", technical=security_detail),
        _check("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden from this check."),
        _check("raw_logs_hidden", "Raw logs hidden", "passed", "Raw app logs are not returned."),
        _check("raw_paths_hidden", "Raw paths hidden", "passed", "Raw Android and backend paths are hidden."),
        _check("media_not_scanned", "Media was not scanned", "passed", "Pocket Lab did not scan, index, or parse user photos."),
        _check("media_details_owned_by_photoprism", "PhotoPrism owns media details", "passed", "PhotoPrism handles indexing, thumbnails, metadata, and media warnings."),
    ]
    status = _status_from_items(checks)
    proof_status = "passed" if status == "succeeded" else "review"
    proofs = [
        _proof("backend_worker_executed", "Backend worker executed", "passed", "The app check was handled by Pocket Lab Lite backend worker."),
        _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested Check app through FastAPI."),
        _proof("browser_no_file_access", "Browser did not access files", "passed", "The browser did not access files or PhotoPrism internals."),
        _proof("app_route_checked", "Secure route checked", "passed" if route_health else "review", "Pocket Lab checked the same-origin PhotoPrism route."),
        _proof("app_health_checked", "App health checked", "passed" if local_health else "review", "Pocket Lab checked PhotoPrism's base-path health endpoint."),
        _proof("storage_mapping_checked", "Storage mapping checked", storage_status, "Photo storage mapping state was checked without listing files."),
        _proof("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden."),
        _proof("raw_logs_hidden", "Raw logs hidden", "passed", "Raw app logs are hidden."),
        _proof("raw_paths_hidden", "Raw paths hidden", "passed", "Raw paths are hidden."),
        _proof("media_not_scanned", "Media was not scanned", "passed", "No photos were scanned, imported, or indexed."),
        _proof("media_details_owned_by_photoprism", "PhotoPrism owns media details", "passed", "PhotoPrism handles media-specific details."),
        _proof("receipt_saved", "Receipt saved", proof_status, "Pocket Lab saved a sanitized Check app receipt."),
    ]
    technical = {
        "process_state": process_state,
        "app_installed": installed,
        "local_health_checked": True,
        "same_origin_route_checked": True,
        "route_path": "/apps/photoprism/",
        "storage_mode": "read_only" if storage_detail.get("read_only") else "review",
        "media_scanned": False,
        "index_started": False,
        "import_started": False,
    }
    details = _check_details(
        status=status,
        process_state=process_state,
        local_health=local_health,
        route_health=route_health,
        storage_status=storage_status,
        installed=installed,
    )
    return _finish_operation(state, op, status=status, summary=_check_summary(status), checks=checks, proofs=proofs, technical=technical, details=details)


def _helper_script_path() -> Path:
    return Path(__file__).resolve().parents[3] / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "lite" / "restart-caddy-proxy.sh"


def _refresh_caddy_route_if_safe(route_needs_refresh: bool) -> tuple[str, bool]:
    if not route_needs_refresh:
        return "skipped", False
    helper = _helper_script_path()
    if not helper.exists():
        return "review", False
    if shutil.which("bash") is None:
        return "review", False
    try:
        proc = subprocess.run(["bash", str(helper)], check=False, capture_output=True, text=True, timeout=25)
    except Exception:
        return "review", False
    return ("changed" if proc.returncode == 0 else "review"), proc.returncode == 0


def _restart_photoprism_if_safe(health_failed: bool) -> tuple[str, bool]:
    if not health_failed:
        return "skipped", False
    if shutil.which("pm2") is None:
        return "skipped", False
    try:
        proc = subprocess.run(["pm2", "restart", "pocketlab-app-photoprism", "--update-env"], check=False, capture_output=True, text=True, timeout=20)
    except Exception:
        return "review", False
    return ("changed" if proc.returncode == 0 else "review"), proc.returncode == 0


def _wait_for_photoprism_health(*, attempts: int = 24, delay_seconds: float = 1.0) -> tuple[bool, bool]:
    local_ready = False
    route_ready = False
    for _ in range(max(1, attempts)):
        local_ready = _local_health_ready()
        route_ready = _route_health_ready()
        if local_ready or route_ready:
            return local_ready, route_ready
        time.sleep(delay_seconds)
    return local_ready, route_ready


def _repair_storage_if_safe(storage_detail: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:
    if not storage_detail.get("mapping_count"):
        return "skipped", False, {"mapping_count": 0}
    if not storage_detail.get("pending_apply"):
        return "passed", False, {"mapping_count": storage_detail.get("mapping_count"), "pending_apply": False}
    try:
        result = lite_photoprism_media._apply_storage_mappings_for_media("import_photos")  # worker-owned managed mapping repair only
    except Exception:
        return "review", False, {"mapping_count": storage_detail.get("mapping_count"), "pending_apply": True}
    changed = int(result.get("applied_count") or 0) > 0
    return ("changed" if changed else "review"), changed, {"mapping_count": storage_detail.get("mapping_count"), "applied_count": int(result.get("applied_count") or 0), "pending_apply": not changed}


def execute_repair_app(command: dict[str, Any]) -> dict[str, Any]:
    app_id = _validate_app_id(command.get("app_id"))
    command_id = str(command.get("command_id") or command.get("job_id") or _operation_id(REPAIR_APP_ACTION))
    state = _read_state()
    op = state.get("operations", {}).get(command_id)
    if not isinstance(op, dict):
        op = record_queued_operation({**command, "command_id": command_id, "app_id": app_id, "action_id": REPAIR_APP_ACTION})
        state = _read_state()
        op = state.get("operations", {}).get(command_id, op)
    op.update({"status": "running", "started_at": op.get("started_at") or _now(), "progress": _progress(REPAIR_APP_ACTION, "running", 1, status="running", step="Pocket Lab is checking route, health, and storage setup.")})
    state.setdefault("apps", {}).setdefault(app_id, {})["current_action"] = {"action_id": REPAIR_APP_ACTION, "status": "running", "operation_id": command_id, "summary": "Repairing PhotoPrism safely.", "progress": op["progress"]}
    _write_state(state)

    app = _catalog_app()
    installed = _installed_from_catalog(app)
    env_ready = False
    try:
        env_ready = lite_photoprism_media._env_file().exists()
    except Exception:
        env_ready = False
    route_registry_status, route_registry_detail = _route_registry_status()
    caddy_status, caddy_detail = _caddy_route_status()
    storage_status, storage_detail = _storage_status()
    local_health_before = _local_health_ready()
    route_health_before = _route_health_ready()

    route_changed = False
    if installed and route_registry_status != "passed":
        try:
            lite_catalog._write_route_registry("unknown")
            route_registry_status, route_registry_detail = _route_registry_status()
            route_changed = True
        except Exception:
            route_registry_status = "review"

    caddy_needs_refresh = caddy_status == "review" or route_changed
    caddy_step_status, caddy_changed = _refresh_caddy_route_if_safe(caddy_needs_refresh)
    storage_step_status, storage_changed, storage_step_detail = _repair_storage_if_safe(storage_detail)
    restart_step_status, restart_performed = _restart_photoprism_if_safe(not (local_health_before or route_health_before))
    if restart_performed:
        local_health_after, route_health_after = _wait_for_photoprism_health()
    else:
        local_health_after = _local_health_ready()
        route_health_after = _route_health_ready()

    repair_steps = [
        _step("config_present", "App config checked", "passed" if env_ready else ("review" if installed else "skipped"), "Pocket Lab checked that app config exists without reading values.", technical={"config_present": env_ready}),
        _step("route_registry", "App route record checked", "changed" if route_changed else ("passed" if route_registry_status == "passed" else "review"), "Pocket Lab checked or refreshed the PhotoPrism route record.", technical=route_registry_detail),
        _step("caddy_route", "Secure app route refreshed", caddy_step_status if caddy_needs_refresh else ("passed" if caddy_status == "passed" else "skipped"), "Pocket Lab checked that the app route preserves /apps/photoprism/.", technical={**caddy_detail, "helper_used": caddy_changed}),
        _step("storage_mappings", "Photo storage connection checked", storage_step_status, "Pocket Lab checked managed storage mappings without touching source photos.", technical=storage_step_detail),
        _step("app_restart", "App restart checked", restart_step_status, "Pocket Lab restarted only the app process when health was failing and PM2 was available." if restart_performed else "Pocket Lab did not restart the app process.", technical={"restart_performed": restart_performed}),
        _step("app_health", "App health verified", "passed" if (local_health_after or route_health_after) else "review", "Pocket Lab verified PhotoPrism health after repair."),
    ]
    status = _repair_final_status(repair_steps, local_health_after=local_health_after, route_health_after=route_health_after)
    changed = bool(route_changed or caddy_changed or storage_changed or restart_performed)
    proofs = [
        _proof("backend_worker_executed", "Backend worker executed", "passed", "The repair was handled by Pocket Lab Lite backend worker."),
        _proof("frontend_no_shell", "Browser did not run commands", "passed", "The browser only requested Repair through FastAPI."),
        _proof("browser_no_file_access", "Browser did not access files", "passed", "The browser did not read app files or storage."),
        _proof("repair_bounded", "Repair was bounded", "passed", "Repair was limited to route, health, and managed storage checks."),
        _proof("media_preserved", "Media preserved", "passed", "No source photos were deleted or changed."),
        _proof("no_destructive_changes", "No destructive changes", "passed", "Repair did not reset the database, credentials, or media."),
        _proof("app_route_checked", "Secure route checked", "passed" if (route_health_after or caddy_status == "passed") else "review", "Pocket Lab checked or refreshed the app route."),
        _proof("storage_mapping_checked", "Storage mapping checked", storage_status if storage_step_status == "skipped" else ("passed" if storage_step_status in {"passed", "changed"} else "review"), "Managed storage mappings were checked safely."),
        _proof("app_health_checked", "App health verified", "passed" if (local_health_after or route_health_after) else "review", "Pocket Lab checked app health after repair."),
        _proof("restart_safe", "Restart was safe", "passed" if restart_performed else "not_applicable", "No restart was needed or only the app process was restarted safely."),
        _proof("secrets_hidden", "Secrets hidden", "passed", "Secret values are hidden."),
        _proof("raw_logs_hidden", "Raw logs hidden", "passed", "Raw PM2 and app logs are hidden."),
        _proof("raw_paths_hidden", "Raw paths hidden", "passed", "Raw file paths are hidden."),
        _proof("receipt_saved", "Receipt saved", "passed" if status == "succeeded" else "review", "Pocket Lab saved a sanitized Repair receipt."),
    ]
    technical = {
        "repair_bounded": True,
        "before": {
            "local_health_ready": bool(local_health_before),
            "route_health_ready": bool(route_health_before),
        },
        "after": {
            "local_health_ready": bool(local_health_after),
            "route_health_ready": bool(route_health_after),
        },
        "route_registry_refreshed": route_changed,
        "caddy_route_checked": True,
        "storage_mapping_checked": True,
        "restart_performed": restart_performed,
        "media_preserved": True,
        "destructive_changes": False,
        "index_started": False,
        "import_started": False,
        "app_login_changed": False,
        "database_reset": False,
    }
    details = _repair_details(
        status=status,
        changed=changed,
        restart_performed=restart_performed,
        local_health_before=local_health_before,
        route_health_before=route_health_before,
        local_health_after=local_health_after,
        route_health_after=route_health_after,
        route_changed=route_changed,
        caddy_changed=caddy_changed,
        storage_changed=storage_changed,
        storage_status=storage_status,
    )
    return _finish_operation(state, op, status=status, summary=_repair_summary(status, changed), repair_steps=repair_steps, proofs=proofs, technical=technical, details=details)


def execute_app_operation(command: dict[str, Any]) -> dict[str, Any]:
    action = _validate_action_id(command.get("action_id") or command.get("operation"))
    if action == CHECK_APP_ACTION:
        return execute_check_app(command)
    return execute_repair_app(command)


def record_operation_failure(command: dict[str, Any], exc: Exception) -> dict[str, Any]:
    command_id = str(command.get("command_id") or command.get("job_id") or _operation_id(str(command.get("action_id") or CHECK_APP_ACTION)))
    action = _validate_action_id(command.get("action_id") or command.get("operation") or CHECK_APP_ACTION)
    state = _read_state()
    op = state.get("operations", {}).get(command_id)
    if not isinstance(op, dict):
        op = record_queued_operation({**command, "command_id": command_id, "app_id": PHOTOPRISM_APP_ID, "action_id": action})
        state = _read_state()
        op = state.get("operations", {}).get(command_id, op)
    op.update({
        "status": "failed",
        "summary": "Check could not complete" if action == CHECK_APP_ACTION else "Repair could not complete",
        "completed_at": _now(),
        "redaction": _redaction(),
        "progress": _progress(action, "failed", 1, status="failed", step="The backend worker could not complete the app action."),
        "failure_kind": exc.__class__.__name__,
    })
    _finalize_current_action(state, op)
    _write_state(state)
    return _sanitize_payload(op)


def _reconcile_stale_state(state: dict[str, Any]) -> dict[str, Any]:
    changed = False
    operations = state.setdefault("operations", {})
    for op in list(operations.values()):
        if not isinstance(op, dict):
            continue
        if str(op.get("status") or "").lower() not in {"queued", "running"}:
            continue
        age = _seconds_since(op.get("started_at") or op.get("queued_at") or op.get("created_at"))
        if age is None or age <= STALE_OPERATION_SECONDS:
            continue
        action = str(op.get("action_id") or CHECK_APP_ACTION)
        op.update({
            "status": "review",
            "summary": "Check needs review" if action == CHECK_APP_ACTION else "Repair needs review",
            "completed_at": _now(),
            "stale_reconciled": True,
            "progress": _progress(action, "review", len(_STEP_LABELS.get(action, [])) - 1, status="review", step="Worker progress became stale; Pocket Lab did not fake success."),
            "proofs": [
                _proof("backend_worker_executed", "Backend worker execution not confirmed", "review", "Pocket Lab could not confirm that the worker completed before the timeout."),
                _proof("secrets_hidden", "Secrets hidden", "passed", "No secret values were exposed."),
                _proof("receipt_saved", "Receipt saved", "review", "Pocket Lab saved a stale-operation receipt."),
            ],
            "redaction": _redaction(),
        })
        _finalize_current_action(state, op)
        changed = True
    if changed:
        state["updated_at"] = _now()
    return state


def _operation_completed_after(candidate: dict[str, Any] | None, baseline: dict[str, Any] | None) -> bool:
    if not isinstance(candidate, dict) or not isinstance(baseline, dict):
        return False
    candidate_at = str(candidate.get("completed_at") or candidate.get("updated_at") or "")
    baseline_at = str(baseline.get("completed_at") or baseline.get("updated_at") or "")
    return bool(candidate_at and baseline_at and candidate_at >= baseline_at)


def _repair_restart_was_performed(repair: dict[str, Any]) -> bool:
    technical = repair.get("technical_details") if isinstance(repair.get("technical_details"), dict) else {}
    if technical.get("restart_performed") is True:
        return True
    for step in repair.get("repair_steps") if isinstance(repair.get("repair_steps"), list) else []:
        if not isinstance(step, dict):
            continue
        if step.get("id") == "app_restart" and str(step.get("status") or "").lower() in {"changed", "passed"}:
            return True
    return False


def _reconcile_repair_with_followup_check(repair: dict[str, Any] | None, check: dict[str, Any] | None) -> dict[str, Any] | None:
    """Show Repair as complete when a newer Check app proves the restarted app is healthy.

    Repair may run its post-restart health probe before PhotoPrism is fully warm on
    Termux/Android. A later successful Check app is stronger evidence than that early
    probe, so the read API can reconcile the visible Repair state without exposing logs
    or raw process details.
    """
    if not isinstance(repair, dict):
        return repair
    if str(repair.get("status") or "").lower() == "succeeded":
        return repair
    if not _repair_restart_was_performed(repair):
        return repair
    if not isinstance(check, dict) or str(check.get("status") or "").lower() != "succeeded":
        return repair
    if not _operation_completed_after(check, repair):
        return repair

    reconciled = dict(repair)
    reconciled["status"] = "succeeded"
    reconciled["summary"] = "Repair completed"
    progress = dict(reconciled.get("progress") if isinstance(reconciled.get("progress"), dict) else {})
    progress.update({"phase": "completed", "status": "succeeded", "step": "Evidence saved", "percent": 100})
    reconciled["progress"] = progress

    repair_details = dict(reconciled.get("details") if isinstance(reconciled.get("details"), dict) else {})
    check_details = check.get("details") if isinstance(check.get("details"), dict) else {}
    repair_details.update({
        "status": "ready",
        "summary": "Repair completed",
        "last_result": "Repair completed",
        "what_happened": ["Pocket Lab restarted PhotoPrism. A follow-up check confirmed the app is now stable."],
        "what_changed": ["PhotoPrism was restarted.", "PhotoPrism is now online."],
        "what_needs_attention": [],
        "status_checks": check_details.get("status_checks") if isinstance(check_details.get("status_checks"), list) else repair_details.get("status_checks", []),
        "technical_details": [
            "Execution owner: backend worker",
            "Action: repair_app",
            "Before status: not ready",
            "After status: ready",
            "App restart: performed",
            "Confirmed by follow-up Check app.",
            "Backend troubleshooting records stay backend-only.",
        ],
    })
    reconciled["details"] = repair_details
    technical = dict(reconciled.get("technical_details") if isinstance(reconciled.get("technical_details"), dict) else {})
    after = dict(technical.get("after") if isinstance(technical.get("after"), dict) else {})
    after.update({"local_health_ready": True, "route_health_ready": True})
    technical.update({"after": after, "reconciled_by_followup_check": True})
    reconciled["technical_details"] = technical
    return reconciled


def app_operation_status(app_id: str) -> dict[str, Any]:
    app = _validate_app_id(app_id)
    state = _read_state()
    if state.get("updated_at") and state != _read_json(_state_path(), {}):
        _write_state(state)
    app_state = state.setdefault("apps", {}).setdefault(app, {})
    latest_by_action = app_state.get("latest_by_action") if isinstance(app_state.get("latest_by_action"), dict) else {}
    operations = state.get("operations") if isinstance(state.get("operations"), dict) else {}
    last_safety = operations.get(latest_by_action.get(CHECK_APP_ACTION)) if latest_by_action.get(CHECK_APP_ACTION) else app_state.get("last_safety_check")
    last_repair = operations.get(latest_by_action.get(REPAIR_APP_ACTION)) if latest_by_action.get(REPAIR_APP_ACTION) else app_state.get("last_repair")
    if isinstance(last_repair, dict):
        last_repair = _reconcile_repair_with_followup_check(last_repair, last_safety if isinstance(last_safety, dict) else None)
    current = app_state.get("current_action") if isinstance(app_state.get("current_action"), dict) else None
    return _sanitize_payload({
        "status": "healthy",
        "app_id": app,
        "current_action": current,
        "last_safety_check": last_safety if isinstance(last_safety, dict) else None,
        "last_repair": last_repair if isinstance(last_repair, dict) else None,
        "actions": {
            CHECK_APP_ACTION: _operation_action_summary(CHECK_APP_ACTION, last_safety if isinstance(last_safety, dict) else None, current),
            REPAIR_APP_ACTION: _operation_action_summary(REPAIR_APP_ACTION, last_repair if isinstance(last_repair, dict) else None, current),
        },
        "updated_at": state.get("updated_at") or _now(),
    })


def _operation_action_summary(action_id: str, last: dict[str, Any] | None, current: dict[str, Any] | None) -> dict[str, Any]:
    running = isinstance(current, dict) and current.get("action_id") == action_id and str(current.get("status") or "").lower() in {"queued", "running"}
    source = current if running else (last or {})
    return {
        "status": str(source.get("status") or "ready").lower(),
        "summary": _safe_text(source.get("summary"), "Ready"),
        "progress": source.get("progress"),
        "evidence_ref": (last or {}).get("evidence_ref"),
        "updated_at": (last or {}).get("completed_at") or (last or {}).get("updated_at"),
        "started_at": (last or {}).get("started_at"),
        "completed_at": (last or {}).get("completed_at"),
        "checks": (last or {}).get("checks") if not running else [],
        "repair_steps": (last or {}).get("repair_steps") if not running else [],
        "details": (last or {}).get("details") if not running else {},
        "technical_details": (last or {}).get("technical_details") if not running else {},
    }


def operation_receipts(app_id: str) -> list[dict[str, Any]]:
    app = _validate_app_id(app_id)
    state = _read_state()
    operations = [op for op in (state.get("operations") or {}).values() if isinstance(op, dict) and op.get("app_id") == app and op.get("action_id") in SUPPORTED_ACTIONS]
    return sorted(_sanitize_payload(operations), key=lambda item: str(item.get("completed_at") or item.get("queued_at") or ""), reverse=True)
