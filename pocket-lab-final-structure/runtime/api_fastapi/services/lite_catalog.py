from __future__ import annotations

import json
import os
import secrets
import subprocess
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from .. import deps
from .fleet_registry import normalize_node_id

COMMAND_SUBJECT = "pocketlab.commands.lite.catalog.install"
PHOTOPRISM_APP_ID = "photoprism"
PHOTOPRISM_ROUTE = "/apps/photoprism/"
PHOTOPRISM_UPSTREAM = "127.0.0.1:2342"
PHOTOPRISM_PROCESS = "pocketlab-app-photoprism"
INSTALL_STEPS_TOTAL = 7
RUNNING_OPERATION_STATUSES = {"queued", "running", "installing", "preparing"}


def _now() -> str:
    return deps.now_utc_iso()


def _state_dir() -> Path:
    deps.settings().ensure_dirs()
    return deps.settings().state_dir


def _state_path() -> Path:
    return _state_dir() / "lite_catalog_state.json"


def route_registry_path() -> Path:
    override = os.environ.get("POCKETLAB_LITE_APP_ROUTES")
    if override:
        return Path(override).expanduser()
    return _state_dir() / "app_routes.json"


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
    return state


def _write_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    _write_json(_state_path(), state)


def _server_node_id() -> str:
    return normalize_node_id(os.environ.get("POCKETLAB_NODE_ID") or "pocket-lab-lite-server")


def _server_name() -> str:
    return os.environ.get("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")


def _default_app_state() -> dict[str, Any]:
    return {
        "id": PHOTOPRISM_APP_ID,
        "install_state": "not_installed",
        "status": "not_installed",
        "runtime": {"route": PHOTOPRISM_ROUTE, "url": None, "health": "not_installed", "version": None, "process": PHOTOPRISM_PROCESS},
        "route": {"path": PHOTOPRISM_ROUTE, "upstream": PHOTOPRISM_UPSTREAM, "enabled": False, "health": "not_installed"},
        "access": {"route_ready": False, "open_url": None, "message": "Install PhotoPrism to enable secure app access."},
        "evidence_refs": [],
        "last_operation": None,
        "progress": None,
        "updated_at": _now(),
    }


def _get_app_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or _read_state()
    apps = state.setdefault("apps", {})
    app = apps.get(PHOTOPRISM_APP_ID)
    if not isinstance(app, dict):
        app = _default_app_state()
        apps[PHOTOPRISM_APP_ID] = app
    return app


def _safe_message(value: Any, fallback: str = "PhotoPrism install status is available.") -> str:
    text = str(value or fallback)
    forbidden = ("token", "password", "secret", "api_key", "private key", "hash")
    if any(term in text.lower() for term in forbidden):
        return fallback
    return text[:240]


def _detect_secure_origin_from_request(request: Request | None = None) -> str | None:
    configured = (os.environ.get("POCKETLAB_LITE_SECURE_ORIGIN") or os.environ.get("POCKETLAB_SECURE_ORIGIN") or "").strip().rstrip("/")
    if configured.startswith("https://") and ".ts.net" in configured:
        return configured
    if request is not None:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
        if proto == "https" and host and host.split(":", 1)[0].endswith(".ts.net"):
            return f"https://{host}".rstrip("/")
    return _detect_secure_origin_from_caddyfile()


def _detect_secure_origin_from_caddyfile() -> str | None:
    candidates = [os.environ.get("POCKET_LAB_CADDYFILE"), os.environ.get("CADDYFILE"), str(Path.home() / "pocket-lab-lite" / "caddy" / "Caddyfile")]
    for candidate in [c for c in candidates if c]:
        path = Path(candidate).expanduser()
        if not path.exists():
            continue
        try:
            for raw in path.read_text(errors="ignore").splitlines():
                line = raw.strip()
                if line.endswith("{"):
                    label = line[:-1].strip()
                    if label.endswith(".ts.net"):
                        return f"https://{label}"
        except Exception:
            continue
    return None


def access_status(request: Request | None = None) -> dict[str, Any]:
    origin = _detect_secure_origin_from_request(request)
    https_ready = bool(origin)
    return {
        "https_ready": https_ready,
        "secure_origin": origin,
        "route_mode": "tailscale_caddy" if https_ready else "local_recovery",
        "pwa_ready": https_ready,
        "message": "Secure access is ready." if https_ready else "Remote access not ready.",
    }


def _target_model() -> dict[str, Any]:
    return {
        "default_node_id": _server_node_id(),
        "supported_roles": ["server"],
        "eligible_devices": [{"node_id": _server_node_id(), "name": _server_name(), "status": "online", "eligible": True, "reason": "Ready to install"}],
    }


def _device_capability_summary() -> dict[str, Any]:
    # Import lazily to avoid a module-cycle during Lite status construction.
    try:
        from . import lite_status

        fleet = lite_status.lite_fleet()
        summary = fleet.get("capability_summary") if isinstance(fleet, dict) else {}
        return summary if isinstance(summary, dict) else {}
    except Exception:
        return {}


def _storage_summary() -> dict[str, Any]:
    try:
        from . import lite_app_storage

        return lite_app_storage.catalog_storage_summary()
    except Exception:
        return {
            "status": "not_connected",
            "summary": "No media folders connected",
            "mappings": [],
            "count": 0,
        }


def _runtime_health_from_state(app: dict[str, Any]) -> str:
    runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
    route = app.get("route") if isinstance(app.get("route"), dict) else {}
    for value in (runtime.get("health"), route.get("health"), app.get("status")):
        text = str(value or "").lower()
        if text in {"healthy", "ready"}:
            return "healthy"
        if text in {"unhealthy", "failed", "needs_attention"}:
            return "unhealthy"
        if text in {"installing", "running", "queued"}:
            return "installing"
    return "not_installed"


def _app_payload(app: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    operation = app.get("last_operation") if isinstance(app.get("last_operation"), dict) else None
    op_status = str((operation or {}).get("status") or "").lower()
    install_state = str(app.get("install_state") or "not_installed")
    runtime_health = _runtime_health_from_state(app)
    route = app.get("route") if isinstance(app.get("route"), dict) else {}
    route_ready = bool(route.get("enabled") and route.get("health") in {"healthy", "ready"} and access.get("https_ready"))

    if op_status in RUNNING_OPERATION_STATUSES:
        status = "installing"
    elif install_state == "installed" and runtime_health == "healthy":
        status = "ready"
    elif install_state in {"failed", "needs_attention"} or runtime_health == "unhealthy":
        status = "needs_attention"
    elif install_state == "unavailable":
        status = "unavailable"
    else:
        status = "not_installed"

    open_url = PHOTOPRISM_ROUTE if route_ready else None
    actions = {"install": status in {"not_installed", "needs_attention", "unavailable"}, "open": bool(open_url), "details": True, "retry": status in {"needs_attention", "unavailable"}, "remove": False}
    access_message = "PhotoPrism is ready over secure access." if open_url else ("Install PhotoPrism to enable secure app access." if status == "not_installed" else "Open is not ready yet.")
    if not access.get("https_ready"):
        access_message = "Remote access not ready. PhotoPrism can be prepared, but Open stays disabled until HTTPS is ready."

    device_summary = _device_capability_summary()
    storage = _storage_summary()
    storage_devices = device_summary.get("storage_devices") if isinstance(device_summary.get("storage_devices"), list) else []
    available_capabilities = device_summary.get("available_device_capabilities") if isinstance(device_summary.get("available_device_capabilities"), dict) else {}
    ready_capabilities = device_summary.get("ready_device_capabilities") if isinstance(device_summary.get("ready_device_capabilities"), dict) else {}
    host_device_id = device_summary.get("host_device_id") or _server_node_id()
    host_device_name = device_summary.get("host_device_name") or _server_name()
    media_from = storage.get("summary") or "No media folders connected"

    return {
        "id": PHOTOPRISM_APP_ID,
        "name": "PhotoPrism",
        "category": "Photos",
        "summary": "Private photo library for your self-hosted workspace.",
        "status": status,
        "install_state": "installed" if status == "ready" else install_state,
        "installed": status == "ready",
        "target": _target_model(),
        "actions": actions,
        "runtime": {"route": PHOTOPRISM_ROUTE, "url": open_url, "health": runtime_health, "version": (app.get("runtime") or {}).get("version") if isinstance(app.get("runtime"), dict) else None, "process": PHOTOPRISM_PROCESS},
        "access": {"https_ready": bool(access.get("https_ready")), "route_ready": bool(route_ready), "open_url": open_url, "message": access_message},
        "progress": app.get("progress") if isinstance(app.get("progress"), dict) else None,
        "last_operation": operation,
        "evidence_refs": app.get("evidence_refs") if isinstance(app.get("evidence_refs"), list) else [],
        "host_device_id": host_device_id,
        "host_device_name": host_device_name,
        "connected_devices": [
            {"id": item.get("device_id"), "name": item.get("device_name") or item.get("label"), "source_type": item.get("source_type")}
            for item in storage.get("mappings", [])
            if isinstance(item, dict) and item.get("source_type") == "storage_device"
        ],
        "available_device_capabilities": available_capabilities,
        "ready_device_capabilities": ready_capabilities,
        "device_relationships": {
            "runs_on": host_device_name,
            "media_from": media_from,
            "storage_devices_available": int(available_capabilities.get("media_storage") or 0),
            "storage_devices_ready": int(ready_capabilities.get("media_storage") or 0),
        },
        "storage_devices": storage_devices,
        "storage": storage,
    }


def catalog_payload(request: Request | None = None) -> dict[str, Any]:
    state = _read_state()
    app = _get_app_state(state)
    access = access_status(request)
    payload = _app_payload(app, access)
    return {"status": "healthy", "access": access, "apps": [payload], "items": [payload], "count": 1, "updated_at": state.get("updated_at") or _now()}


def catalog_apps_count() -> int:
    return 1


def _operation_id() -> str:
    return f"app-photoprism-{secrets.token_hex(6)}"


def validate_install_request(app_id: str, target_node_id: str | None = None) -> dict[str, Any]:
    normalized_app = str(app_id or "").strip().lower()
    if normalized_app != PHOTOPRISM_APP_ID:
        raise HTTPException(status_code=400, detail="PhotoPrism is the first supported Lite app.")
    target = normalize_node_id(target_node_id or _server_node_id())
    server_id = _server_node_id()
    if target != server_id:
        raise HTTPException(status_code=409, detail="PhotoPrism can only be installed on the Server Host in this release.")
    state = _read_state()
    app = _get_app_state(state)
    op = app.get("last_operation") if isinstance(app.get("last_operation"), dict) else {}
    if str(op.get("status") or "").lower() in RUNNING_OPERATION_STATUSES:
        raise HTTPException(status_code=409, detail={"status": "install_in_progress", "message": "PhotoPrism install is already running.", "operation_id": op.get("operation_id") or op.get("command_id")})
    if str(app.get("install_state") or "") == "installed" and _runtime_health_from_state(app) == "healthy":
        return {"already_installed": True, "operation_id": (op or {}).get("operation_id") or _operation_id(), "target_node_id": server_id}
    return {"already_installed": False, "operation_id": _operation_id(), "target_node_id": server_id}


def install_command(app_id: str, target_node_id: str | None, *, requested_by: str | None = None, dry_run: bool = False, params: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = validate_install_request(app_id, target_node_id)
    operation_id = str(validation["operation_id"])
    return {"command_id": operation_id, "operation_id": operation_id, "app_id": PHOTOPRISM_APP_ID, "target_node_id": str(validation["target_node_id"]), "requested_by": requested_by or "lite-user", "requested_at": _now(), "dry_run": bool(dry_run), "params": dict(params or {}), "already_installed": bool(validation.get("already_installed"))}


def already_installed_response(command: dict[str, Any]) -> dict[str, Any]:
    return {"accepted": True, "status": "already_installed", "operation_id": command["operation_id"], "app_id": PHOTOPRISM_APP_ID, "target_node_id": command["target_node_id"], "message": "PhotoPrism is already ready."}


def record_install_queued(command: dict[str, Any]) -> None:
    state = _read_state()
    app = _get_app_state(state)
    op = {"operation_id": command["operation_id"], "command_id": command["command_id"], "status": "queued", "updated_at": _now(), "message": "PhotoPrism install started."}
    app.update({"install_state": "installing", "status": "installing", "last_operation": op, "progress": {"step": "Install request accepted", "current": 1, "total": INSTALL_STEPS_TOTAL, "message": "Preparing PhotoPrism install on the Server Host."}, "updated_at": _now()})
    state["operations"][command["operation_id"]] = op
    _write_state(state)


def discard_operation(operation_id: str) -> None:
    state = _read_state()
    state.get("operations", {}).pop(operation_id, None)
    app = _get_app_state(state)
    op = app.get("last_operation") if isinstance(app.get("last_operation"), dict) else {}
    if op.get("operation_id") == operation_id:
        state.setdefault("apps", {})[PHOTOPRISM_APP_ID] = _default_app_state()
    _write_state(state)


def _progress(operation_id: str, current: int, step: str, message: str, *, status: str = "running") -> None:
    state = _read_state()
    app = _get_app_state(state)
    operation = app.get("last_operation") if isinstance(app.get("last_operation"), dict) else {}
    operation.update({"operation_id": operation_id, "command_id": operation_id, "status": status, "updated_at": _now(), "message": message})
    app["last_operation"] = operation
    app["install_state"] = "installing"
    app["status"] = "installing"
    app["progress"] = {"step": step, "current": current, "total": INSTALL_STEPS_TOTAL, "message": message}
    state.setdefault("operations", {})[operation_id] = operation
    _write_state(state)


def _runtime_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def installer_script_path() -> Path:
    override = os.environ.get("POCKETLAB_PHOTOPRISM_INSTALLER")
    if override:
        return Path(override).expanduser()
    return _runtime_dir().parent / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "lite" / "install-photoprism-proot.sh"


def _env_for_installer(command: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env.update({"POCKETLAB_LITE_APP_ID": PHOTOPRISM_APP_ID, "POCKETLAB_LITE_APP_OPERATION_ID": str(command["operation_id"]), "POCKETLAB_LITE_APP_ROUTE": PHOTOPRISM_ROUTE, "POCKETLAB_LITE_APP_UPSTREAM": PHOTOPRISM_UPSTREAM, "POCKETLAB_LITE_APP_ROUTES": str(route_registry_path()), "POCKETLAB_STATE_DIR": str(_state_dir()), "POCKETLAB_PHOTOPRISM_PROCESS": PHOTOPRISM_PROCESS})
    origin = _detect_secure_origin_from_request(None)
    if origin:
        env["POCKETLAB_LITE_SECURE_ORIGIN"] = origin
    return env


def _write_route_registry(health: str = "healthy") -> dict[str, Any]:
    path = route_registry_path()
    registry = _read_json(path, {})
    if not isinstance(registry, dict):
        registry = {}
    routes = [r for r in registry.get("routes", []) if isinstance(r, dict) and r.get("app_id") != PHOTOPRISM_APP_ID]
    route = {"app_id": PHOTOPRISM_APP_ID, "path": PHOTOPRISM_ROUTE, "upstream": PHOTOPRISM_UPSTREAM, "enabled": True, "health": health, "updated_at": _now()}
    routes.append(route)
    registry.update({"routes": routes, "updated_at": _now()})
    _write_json(path, registry)
    return route


def _success(command: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    operation_id = str(command["operation_id"])
    version = result.get("version") or result.get("photoprism_version") or "detected-or-unknown"
    route = _write_route_registry(str(result.get("route_health") or "healthy"))
    evidence_refs = result.get("evidence_refs") if isinstance(result.get("evidence_refs"), list) else [f"catalog/evidence/{operation_id}/summary.json"]
    state = _read_state()
    app = _get_app_state(state)
    last_operation = {"operation_id": operation_id, "command_id": operation_id, "status": "succeeded", "updated_at": _now(), "message": "PhotoPrism is ready."}
    app.update({"install_state": "installed", "status": "ready", "runtime": {"route": PHOTOPRISM_ROUTE, "url": PHOTOPRISM_ROUTE, "health": "healthy", "version": version, "process": PHOTOPRISM_PROCESS}, "route": route, "access": {"route_ready": True, "open_url": PHOTOPRISM_ROUTE, "message": "PhotoPrism is ready over secure access."}, "last_operation": last_operation, "progress": {"step": "PhotoPrism ready", "current": INSTALL_STEPS_TOTAL, "total": INSTALL_STEPS_TOTAL, "message": "PhotoPrism passed local health checks."}, "evidence_refs": evidence_refs, "updated_at": _now()})
    state.setdefault("operations", {})[operation_id] = last_operation
    _write_state(state)
    return {"status": "succeeded", "operation_id": operation_id, "app_id": PHOTOPRISM_APP_ID, "summary": "PhotoPrism is ready.", "evidence_refs": evidence_refs}


def _failure(command: dict[str, Any], message: str, *, install_state: str = "needs_attention") -> dict[str, Any]:
    operation_id = str(command.get("operation_id") or command.get("command_id") or _operation_id())
    safe_message = _safe_message(message, "PhotoPrism install needs attention.")
    state = _read_state()
    app = _get_app_state(state)
    last_operation = {"operation_id": operation_id, "command_id": operation_id, "status": "failed", "updated_at": _now(), "message": safe_message}
    app.update({"install_state": install_state, "status": "needs_attention", "runtime": {"route": PHOTOPRISM_ROUTE, "url": None, "health": "unhealthy", "version": None, "process": PHOTOPRISM_PROCESS}, "route": {"path": PHOTOPRISM_ROUTE, "upstream": PHOTOPRISM_UPSTREAM, "enabled": False, "health": "unhealthy"}, "last_operation": last_operation, "progress": {"step": "Install needs attention", "current": INSTALL_STEPS_TOTAL, "total": INSTALL_STEPS_TOTAL, "message": safe_message}, "updated_at": _now()})
    state.setdefault("operations", {})[operation_id] = last_operation
    _write_state(state)
    return {"status": "failed", "operation_id": operation_id, "app_id": PHOTOPRISM_APP_ID, "summary": safe_message}


def run_install(command: dict[str, Any]) -> dict[str, Any]:
    operation_id = str(command.get("operation_id") or command.get("command_id") or _operation_id())
    command = {**command, "operation_id": operation_id, "command_id": operation_id}
    if command.get("dry_run") is True:
        _progress(operation_id, 2, "Dry run checked", "PhotoPrism install request was validated without making changes.", status="succeeded")
        return {"status": "succeeded", "operation_id": operation_id, "dry_run": True, "summary": "PhotoPrism install request is valid."}

    script = installer_script_path()
    if not script.exists():
        return _failure(command, f"PhotoPrism installer script is missing: {script}", install_state="unavailable")

    _progress(operation_id, 2, "Preparing PhotoPrism runtime", "Setting up the app environment.")
    try:
        completed = subprocess.run(["bash", str(script)], cwd=str(script.parent), env=_env_for_installer(command), text=True, capture_output=True, timeout=int(os.environ.get("POCKETLAB_PHOTOPRISM_INSTALL_TIMEOUT_SECONDS", "2700")), check=False)
    except subprocess.TimeoutExpired:
        return _failure(command, "PhotoPrism install timed out. Retry while the device is charging and connected.")

    summary_path = _state_dir() / "catalog" / "evidence" / operation_id / "summary.json"
    result = _read_json(summary_path, {}) if summary_path.exists() else {}
    if completed.returncode != 0:
        message = result.get("summary") or (completed.stderr.splitlines()[-1] if completed.stderr else "PhotoPrism installer failed.")
        return _failure(command, message)
    if not isinstance(result, dict):
        result = {}
    if result.get("status") not in {"succeeded", "ready", "healthy"}:
        return _failure(command, result.get("summary") or "PhotoPrism installer did not produce a healthy result.")
    return _success(command, result)
