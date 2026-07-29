from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppRuntimeSpec:
    app_id: str
    process_name: str
    route_path: str
    local_url: str
    config_paths: tuple[str, ...] = ()


_APP_SPECS: dict[str, AppRuntimeSpec] = {
    "photoprism": AppRuntimeSpec(
        app_id="photoprism",
        process_name="pocketlab-app-photoprism",
        route_path="/apps/photoprism/",
        local_url="http://127.0.0.1:2342/",
        config_paths=("~/.pocket_lab/lite/apps/photoprism/config/photoprism.env",),
    ),
}
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 10.0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def app_runtime_spec(app_id: str) -> AppRuntimeSpec | None:
    return _APP_SPECS.get(str(app_id or "").strip().lower())


def _pm2_process(process_name: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["pm2", "jlist"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.5,
            env={**os.environ, "NO_COLOR": "1"},
        )
        if completed.returncode != 0:
            return {}
        rows = json.loads(completed.stdout or "[]")
        if not isinstance(rows, list):
            return {}
        for row in rows:
            if not isinstance(row, dict) or row.get("name") != process_name:
                continue
            env = row.get("pm2_env") if isinstance(row.get("pm2_env"), dict) else {}
            status = str(env.get("status") or "unknown").lower()
            return {
                "registered": True,
                "running": status == "online" and int(row.get("pid") or 0) > 0,
                "status": status,
                "pid_present": int(row.get("pid") or 0) > 0,
                "restart_count": int(env.get("restart_time") or 0),
            }
    except Exception:
        return {}
    return {}


def _http_reachable(url: str) -> tuple[bool, int | None]:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "PocketLab-Lite-Runtime-Probe/1"})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=0.8) as response:
            return True, int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        # Any HTTP response proves that the application accepted the connection.
        return True, int(exc.code)
    except Exception:
        return False, None


def probe_app_runtime(app_id: str, *, force: bool = False) -> dict[str, Any]:
    spec = app_runtime_spec(app_id)
    if spec is None:
        return {
            "app_id": str(app_id or "").strip().lower(),
            "supported": False,
            "installed": False,
            "running": False,
            "reachable": False,
            "installation_state": "unknown",
            "sanitized": True,
        }

    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(spec.app_id)
        if not force and cached and now - cached[0] <= _CACHE_TTL_SECONDS:
            return dict(cached[1])

    pm2 = _pm2_process(spec.process_name)
    config_present = any(Path(path).expanduser().is_file() for path in spec.config_paths)
    reachable, http_status = _http_reachable(spec.local_url)
    process_registered = bool(pm2.get("registered"))
    process_running = bool(pm2.get("running"))
    installed = bool(process_registered or process_running or config_present or reachable)

    if process_running and reachable:
        installation_state = "installed_running"
    elif installed and process_running:
        installation_state = "installed_degraded"
    elif installed:
        installation_state = "installed_stopped"
    else:
        installation_state = "not_installed"

    payload = {
        "app_id": spec.app_id,
        "supported": True,
        "installed": installed,
        "running": process_running,
        "reachable": reachable,
        "installation_state": installation_state,
        "process": {
            "name": spec.process_name,
            "registered": process_registered,
            "running": process_running,
            "status": str(pm2.get("status") or "missing"),
            "pid_present": bool(pm2.get("pid_present")),
            "restart_count": int(pm2.get("restart_count") or 0),
        },
        "route_path": spec.route_path,
        "http_status": http_status,
        "config_present": config_present,
        "evidence": {
            "pm2_registered": process_registered,
            "process_running": process_running,
            "http_responding": reachable,
            "config_present": config_present,
        },
        "sanitized": True,
    }
    with _CACHE_LOCK:
        _CACHE[spec.app_id] = (now, dict(payload))
    return payload


def reconcile_install_state(app_id: str, saved: dict[str, Any] | None = None, *, force: bool = False) -> dict[str, Any]:
    saved = saved if isinstance(saved, dict) else {}
    runtime = probe_app_runtime(app_id, force=force)
    saved_installed = bool(
        saved.get("installed") is True
        or str(saved.get("install_state") or "").lower() in {"installed", "installed_running", "installed_stopped"}
        or str(saved.get("status") or "").lower() in {"ready", "installed", "running"}
    )
    runtime_installed = bool(runtime.get("installed"))
    conflict = saved_installed != runtime_installed and bool(saved)
    result = dict(runtime)
    result.update({
        "saved_installed": saved_installed,
        "state_conflict": conflict,
        "authoritative_source": "runtime_evidence" if runtime_installed else "saved_state",
    })
    return result


def install_guard(app_id: str) -> dict[str, Any]:
    evidence = reconcile_install_state(app_id, force=True)
    if evidence.get("installed"):
        return {
            "allowed": False,
            "status": "already_installed",
            "summary": "The app is already installed on this device.",
            "runtime": evidence,
        }
    return {"allowed": True, "status": "ready", "summary": "The app can be installed.", "runtime": evidence}


def normalize_action_availability(
    action_id: str,
    action: dict[str, Any] | None,
    *,
    installed: bool,
    operation_running: bool = False,
    app_name: str = "This app",
) -> dict[str, Any]:
    normalized = dict(action or {})
    action_id = str(action_id or "").strip().lower()
    enabled = bool(normalized.get("enabled"))
    reason = normalized.get("disabled_reason") or normalized.get("reason")

    if operation_running:
        enabled = False
        reason = "Another app operation is already running."
    elif not installed and action_id != "install_app":
        enabled = False
        reason = f"Install {app_name} first."
    elif installed and action_id == "install_app":
        enabled = False
        reason = f"{app_name} is already installed."

    normalized["enabled"] = enabled
    normalized["status"] = "ready" if enabled else "disabled"
    if reason:
        normalized["disabled_reason"] = str(reason)[:220]
        normalized["reason"] = str(reason)[:220]
    return normalized
