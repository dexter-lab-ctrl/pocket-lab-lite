from __future__ import annotations

import json
import os
import selectors
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SIGNAL_PRESENT = "present"
SIGNAL_ABSENT = "absent"
SIGNAL_UNKNOWN = "unknown"
INSTALL_STATES = frozenset(
    {
        "installed_running",
        "installed_degraded",
        "installed_stopped",
        "not_installed",
        "unknown",
        "state_conflict",
    }
)
_MAX_PM2_OUTPUT_BYTES = 256 * 1024
_PM2_TIMEOUT_SECONDS = 2.0
_RUNTIME_CACHE_TTL_SECONDS = 10.0
_LAST_VALID_TTL_SECONDS = 120.0


@dataclass(frozen=True)
class AppRuntimeSpec:
    app_id: str
    process_name: str
    route_path: str
    local_url: str
    config_paths: tuple[str, ...] = ()
    executable_paths: tuple[str, ...] = ()

    @property
    def local_probe_url(self) -> str:
        return self.local_url


_APP_SPECS: dict[str, AppRuntimeSpec] = {
    "photoprism": AppRuntimeSpec(
        app_id="photoprism",
        process_name="pocketlab-app-photoprism",
        route_path="/apps/photoprism/",
        local_url="http://127.0.0.1:2342/apps/photoprism/api/v1/status",
        config_paths=("~/.pocket_lab/lite/apps/photoprism/config/photoprism.env",),
        executable_paths=(
            "~/.pocket_lab/lite/apps/photoprism/bin/photoprism",
            "~/.pocket_lab/proot-distro/installed-rootfs/ubuntu/usr/local/bin/photoprism",
        ),
    ),
}
_CACHE_LOCK = threading.RLock()
_CACHE_CONDITION = threading.Condition(_CACHE_LOCK)
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LAST_VALID: dict[str, tuple[float, dict[str, Any]]] = {}
_PM2_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_PM2_LAST_VALID: dict[str, tuple[float, dict[str, Any]]] = {}
_PM2_INFLIGHT: set[str] = set()
_CACHE_TTL_SECONDS = _RUNTIME_CACHE_TTL_SECONDS  # compatibility for existing tests


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def app_runtime_spec(app_id: str) -> AppRuntimeSpec | None:
    return _APP_SPECS.get(str(app_id or "").strip().lower())


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _bounded_text(value: Any, limit: int = _MAX_PM2_OUTPUT_BYTES) -> str:
    if isinstance(value, bytes):
        value = value[:limit].decode("utf-8", errors="replace")
    return str(value or "")[:limit]


def _pm2_environment() -> dict[str, str]:
    env = {str(key): str(value) for key, value in os.environ.items()}
    home = Path(env.get("HOME") or os.path.expanduser("~")).expanduser().resolve()
    pm2_home = Path(env.get("PM2_HOME") or home / ".pm2").expanduser().resolve()
    env["HOME"] = str(home)
    env["PM2_HOME"] = str(pm2_home)
    env["NO_COLOR"] = "1"
    return env


def _pm2_binary(env: dict[str, str]) -> str | None:
    configured = str(env.get("POCKETLAB_PM2_BIN") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which("pm2", path=env.get("PATH"))


def _run_pm2_jlist(executable: str, env: dict[str, str]) -> tuple[int, bytes]:
    """Run pm2 jlist with bounded time and combined output."""
    process = subprocess.Popen(
        [executable, "jlist"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        close_fds=True,
    )
    selector = selectors.DefaultSelector()
    buffers: list[bytes] = []
    captured = 0
    deadline = time.monotonic() + _PM2_TIMEOUT_SECONDS
    try:
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                selector.register(stream, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired([executable, "jlist"], _PM2_TIMEOUT_SECONDS)
            events = selector.select(timeout=min(0.05, remaining))
            if not events and process.poll() is not None:
                events = [(key, selectors.EVENT_READ) for key in list(selector.get_map().values())]
            for key, _mask in events:
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                captured += len(chunk)
                if captured > _MAX_PM2_OUTPUT_BYTES:
                    raise BufferError("pm2_output_too_large")
                # Only stdout is parsed; stderr is deliberately discarded.
                if key.fileobj is process.stdout:
                    buffers.append(chunk)
        remaining = max(0.05, deadline - time.monotonic())
        return process.wait(timeout=remaining), b"".join(buffers)
    except Exception:
        process.kill()
        try:
            process.wait(timeout=0.2)
        except Exception:
            pass
        raise
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass


def _unknown_pm2(error_type: str, *, last_valid_used: bool = False) -> dict[str, Any]:
    return {
        "signal": SIGNAL_UNKNOWN,
        "registered": None,
        "running": None,
        "status": "unknown",
        "pid_present": None,
        "pid_valid": None,
        "restart_count": 0,
        "error_type": str(error_type or "pm2_unknown")[:80],
        "last_valid_used": bool(last_valid_used),
        "sanitized": True,
    }


def _collect_pm2_process(process_name: str) -> dict[str, Any]:
    env = _pm2_environment()
    executable = _pm2_binary(env)
    if not executable:
        return _unknown_pm2("pm2_binary_missing")
    try:
        returncode, raw_stdout = _run_pm2_jlist(executable, env)
    except subprocess.TimeoutExpired:
        return _unknown_pm2("pm2_timeout")
    except BufferError:
        return _unknown_pm2("pm2_output_too_large")
    except OSError:
        return _unknown_pm2("pm2_unavailable")
    except Exception:
        return _unknown_pm2("pm2_probe_failed")

    if returncode != 0:
        return _unknown_pm2("pm2_daemon_error")
    stdout = _bounded_text(raw_stdout)
    try:
        rows = json.loads(stdout or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return _unknown_pm2("pm2_invalid_json")
    if not isinstance(rows, list):
        return _unknown_pm2("pm2_unexpected_schema")

    matches = [row for row in rows if isinstance(row, dict) and row.get("name") == process_name]
    if not matches:
        return {
            "signal": SIGNAL_ABSENT,
            "registered": False,
            "running": False,
            "status": "missing",
            "pid_present": False,
            "pid_valid": False,
            "restart_count": 0,
            "error_type": "",
            "last_valid_used": False,
            "sanitized": True,
        }
    if len(matches) != 1:
        return _unknown_pm2("pm2_duplicate_process_name")

    row = matches[0]
    pm2_env = row.get("pm2_env") if isinstance(row.get("pm2_env"), dict) else None
    if pm2_env is None:
        return _unknown_pm2("pm2_unexpected_schema")
    status = str(pm2_env.get("status") or "unknown").strip().lower()
    pid = _safe_int(row.get("pid"), 0)
    pid_valid = pid > 0
    running = status == "online" and pid_valid
    if status not in {"online", "stopped", "errored", "launching", "stopping", "one-launch-status"}:
        status = "unknown"
    return {
        "signal": SIGNAL_PRESENT,
        "registered": True,
        "running": running,
        "status": status,
        "pid_present": pid_valid,
        "pid_valid": pid_valid,
        "restart_count": max(0, _safe_int(pm2_env.get("restart_time"), 0)),
        "error_type": "" if status != "unknown" else "pm2_unknown_status",
        "last_valid_used": False,
        "sanitized": True,
    }


def _pm2_process(process_name: str, *, force: bool = False) -> dict[str, Any]:
    """Return deterministic PM2 evidence with bounded single-flight collection."""
    key = str(process_name or "").strip()
    now = time.monotonic()
    with _CACHE_CONDITION:
        cached = _PM2_CACHE.get(key)
        if not force and cached and now - cached[0] <= _RUNTIME_CACHE_TTL_SECONDS:
            return dict(cached[1])
        if key in _PM2_INFLIGHT:
            deadline = now + _PM2_TIMEOUT_SECONDS + 0.5
            while key in _PM2_INFLIGHT and time.monotonic() < deadline:
                _CACHE_CONDITION.wait(timeout=0.05)
            cached = _PM2_CACHE.get(key)
            if cached:
                return dict(cached[1])
        _PM2_INFLIGHT.add(key)

    try:
        result = _collect_pm2_process(key)
        if result.get("signal") == SIGNAL_UNKNOWN:
            with _CACHE_LOCK:
                last_valid = _PM2_LAST_VALID.get(key)
            if last_valid and now - last_valid[0] <= _LAST_VALID_TTL_SECONDS:
                retained = dict(last_valid[1])
                retained.update(
                    {
                        "last_valid_used": True,
                        "current_probe_signal": SIGNAL_UNKNOWN,
                        "current_probe_error_type": result.get("error_type"),
                    }
                )
                result = retained
        else:
            with _CACHE_LOCK:
                _PM2_LAST_VALID[key] = (now, dict(result))
        with _CACHE_LOCK:
            _PM2_CACHE[key] = (now, dict(result))
        return dict(result)
    finally:
        with _CACHE_CONDITION:
            _PM2_INFLIGHT.discard(key)
            _CACHE_CONDITION.notify_all()


def _http_signal(url: str) -> dict[str, Any]:
    if not str(url or "").strip():
        return {"signal": SIGNAL_UNKNOWN, "responding": None, "status": None, "error_type": "http_probe_unconfigured"}
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "PocketLab-Lite-Runtime-Probe/2"})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=0.9) as response:
            return {
                "signal": SIGNAL_PRESENT,
                "responding": True,
                "status": _safe_int(getattr(response, "status", 200), 200),
                "error_type": "",
            }
    except urllib.error.HTTPError as exc:
        # A non-2xx response still proves the process accepted the connection.
        return {"signal": SIGNAL_PRESENT, "responding": True, "status": _safe_int(exc.code), "error_type": ""}
    except TimeoutError:
        return {"signal": SIGNAL_UNKNOWN, "responding": None, "status": None, "error_type": "http_timeout"}
    except urllib.error.URLError:
        return {"signal": SIGNAL_UNKNOWN, "responding": None, "status": None, "error_type": "http_unreachable"}
    except Exception:
        return {"signal": SIGNAL_UNKNOWN, "responding": None, "status": None, "error_type": "http_probe_failed"}


def _http_reachable(url: str) -> tuple[bool, int | None]:
    """Compatibility wrapper retained for existing tests and callers."""
    signal = _http_signal(url)
    return bool(signal.get("responding")), signal.get("status")


def _path_signal(paths: tuple[str, ...]) -> dict[str, Any]:
    if not paths:
        return {"signal": SIGNAL_UNKNOWN, "present": None, "count": 0}
    present = 0
    checked = 0
    for value in paths[:8]:
        try:
            path = Path(value).expanduser()
            checked += 1
            if path.is_file():
                present += 1
        except (OSError, RuntimeError):
            continue
    return {
        "signal": SIGNAL_PRESENT if present else SIGNAL_ABSENT if checked else SIGNAL_UNKNOWN,
        "present": bool(present) if checked else None,
        "count": present,
    }


def _canonical_installation_state(
    *, pm2: dict[str, Any], http: dict[str, Any], config: dict[str, Any], executable: dict[str, Any]
) -> tuple[str, bool]:
    pm2_signal = pm2.get("signal")
    pm2_status = str(pm2.get("status") or "unknown")
    pm2_running = pm2.get("running") is True and pm2.get("pid_valid") is True
    http_present = http.get("signal") == SIGNAL_PRESENT
    config_present = config.get("signal") == SIGNAL_PRESENT
    executable_present = executable.get("signal") == SIGNAL_PRESENT
    positive_install_evidence = bool(pm2_signal == SIGNAL_PRESENT or http_present or config_present or executable_present)

    if pm2_running and http_present:
        return "installed_running", False
    if http_present and (config_present or executable_present) and (pm2_signal == SIGNAL_UNKNOWN or not pm2_running):
        return "installed_degraded", bool(pm2_signal == SIGNAL_PRESENT and pm2_status == "online")
    if pm2_signal == SIGNAL_PRESENT and pm2_status in {"stopped", "errored"}:
        return "installed_stopped", False
    if positive_install_evidence:
        return "installed_degraded", bool(pm2_signal == SIGNAL_PRESENT and pm2_status == "online" and not pm2_running)

    explicit_absence = (
        pm2_signal == SIGNAL_ABSENT
        and config.get("signal") == SIGNAL_ABSENT
        and executable.get("signal") in {SIGNAL_ABSENT, SIGNAL_UNKNOWN}
        and http.get("signal") != SIGNAL_PRESENT
    )
    return ("not_installed", False) if explicit_absence else ("unknown", False)


def probe_app_runtime(app_id: str, *, force: bool = False) -> dict[str, Any]:
    spec = app_runtime_spec(app_id)
    normalized_app_id = str(app_id or "").strip().lower()
    if spec is None:
        return {
            "app_id": normalized_app_id,
            "supported": False,
            "installed": False,
            "running": False,
            "reachable": False,
            "installation_state": "unknown",
            "evidence_quality": "unknown",
            "sanitized": True,
        }

    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(spec.app_id)
        if not force and cached and now - cached[0] <= _RUNTIME_CACHE_TTL_SECONDS:
            return dict(cached[1])

    try:
        pm2 = _pm2_process(spec.process_name, force=force)
    except TypeError:
        # Compatibility for narrow test doubles and older callers.
        pm2 = _pm2_process(spec.process_name)
    pm2 = dict(pm2 or {})
    if pm2.get("signal") not in {SIGNAL_PRESENT, SIGNAL_ABSENT, SIGNAL_UNKNOWN}:
        pm2["signal"] = SIGNAL_PRESENT if pm2.get("registered") is True else SIGNAL_ABSENT if pm2.get("registered") is False else SIGNAL_UNKNOWN
    if pm2.get("pid_valid") is None:
        pm2["pid_valid"] = pm2.get("pid_present")
    config = _path_signal(spec.config_paths)
    executable = _path_signal(spec.executable_paths)
    reachable, http_status = _http_reachable(spec.local_probe_url)
    http = (
        {"signal": SIGNAL_PRESENT, "responding": True, "status": http_status, "error_type": ""}
        if reachable
        else {"signal": SIGNAL_UNKNOWN, "responding": None, "status": http_status, "error_type": "http_unreachable"}
    )
    installation_state, state_conflict = _canonical_installation_state(
        pm2=pm2, http=http, config=config, executable=executable
    )
    installed = installation_state in {
        "installed_running",
        "installed_degraded",
        "installed_stopped",
        "state_conflict",
    }
    running = installation_state == "installed_running"
    reachable = http.get("signal") == SIGNAL_PRESENT
    authoritative_signal_count = sum(
        value.get("signal") in {SIGNAL_PRESENT, SIGNAL_ABSENT}
        for value in (pm2, http, config, executable)
    )
    evidence_quality = (
        "authoritative" if authoritative_signal_count >= 3 and pm2.get("last_valid_used") is not True
        else "retained" if pm2.get("last_valid_used") is True
        else "partial" if authoritative_signal_count
        else "unknown"
    )
    payload = {
        "app_id": spec.app_id,
        "supported": True,
        "installed": installed,
        "running": running,
        "reachable": reachable,
        "installation_state": "state_conflict" if state_conflict else installation_state,
        "process": {
            "name": spec.process_name,
            "signal": pm2.get("signal", SIGNAL_UNKNOWN),
            "registered": pm2.get("registered"),
            "running": pm2.get("running"),
            "status": str(pm2.get("status") or "unknown"),
            "pid_present": pm2.get("pid_present"),
            "pid_valid": pm2.get("pid_valid"),
            "restart_count": max(0, _safe_int(pm2.get("restart_count"), 0)),
            "last_valid_used": bool(pm2.get("last_valid_used")),
            "error_type": str(pm2.get("current_probe_error_type") or pm2.get("error_type") or "")[:80],
        },
        "route_path": spec.route_path,
        "http_status": http.get("status"),
        "config_present": config.get("present") is True,
        "executable_present": executable.get("present") is True,
        "state_conflict": state_conflict,
        "evidence_quality": evidence_quality,
        "evidence": {
            "pm2": {"signal": pm2.get("signal", SIGNAL_UNKNOWN), "status": pm2.get("status", "unknown"), "last_valid_used": bool(pm2.get("last_valid_used"))},
            "http": {"signal": http.get("signal", SIGNAL_UNKNOWN), "responding": http.get("responding"), "status": http.get("status")},
            "config": {"signal": config.get("signal", SIGNAL_UNKNOWN), "present": config.get("present")},
            "executable": {"signal": executable.get("signal", SIGNAL_UNKNOWN), "present": executable.get("present")},
        },
        "sanitized": True,
    }

    with _CACHE_LOCK:
        if installation_state not in {"unknown"}:
            _LAST_VALID[spec.app_id] = (now, dict(payload))
        elif spec.app_id in _LAST_VALID and now - _LAST_VALID[spec.app_id][0] <= _LAST_VALID_TTL_SECONDS:
            retained = dict(_LAST_VALID[spec.app_id][1])
            retained["evidence_quality"] = "retained"
            retained["probe_degraded"] = True
            retained["current_probe_state"] = "unknown"
            payload = retained
        _CACHE[spec.app_id] = (now, dict(payload))
    return payload



def _explicit_signal(value: Any, *, present: set[str] | None = None, absent: set[str] | None = None) -> str:
    if isinstance(value, bool):
        return SIGNAL_PRESENT if value else SIGNAL_ABSENT
    text = str(value or "").strip().lower()
    if present and text in present:
        return SIGNAL_PRESENT
    if absent and text in absent:
        return SIGNAL_ABSENT
    return SIGNAL_UNKNOWN


def _saved_context_evidence(saved: dict[str, Any]) -> dict[str, Any]:
    runtime = saved.get("runtime") if isinstance(saved.get("runtime"), dict) else {}
    access = saved.get("access") if isinstance(saved.get("access"), dict) else {}
    route = saved.get("route") if isinstance(saved.get("route"), dict) else {}
    storage = saved.get("storage") if isinstance(saved.get("storage"), dict) else {}
    mappings = storage.get("mappings") if isinstance(storage.get("mappings"), list) else []
    mapping_count = max(0, _safe_int(storage.get("mapping_count", storage.get("count", len(mappings))), len(mappings)))
    storage_status = str(storage.get("status") or "").strip().lower()
    route_value = access.get("route_ready") if "route_ready" in access else route.get("enabled") if "enabled" in route else None
    route_signal = _explicit_signal(route_value)
    if route_signal == SIGNAL_UNKNOWN and access.get("open_url"):
        route_signal = SIGNAL_PRESENT
    storage_signal = (
        SIGNAL_PRESENT if mapping_count > 0 or storage_status in {"ready", "connected", "active", "applied"}
        else SIGNAL_ABSENT if storage_status in {"not_connected", "missing", "none"} and mapping_count == 0
        else SIGNAL_UNKNOWN
    )
    last_operation = saved.get("last_operation") if isinstance(saved.get("last_operation"), dict) else {}
    action_id = str(last_operation.get("action_id") or "").strip().lower()
    operation_status = str(last_operation.get("status") or "").strip().lower()
    install_history = SIGNAL_PRESENT if action_id in {"install", "install_app"} and operation_status in {"succeeded", "completed"} else SIGNAL_UNKNOWN
    removal_history = SIGNAL_PRESENT if action_id in {"remove", "remove_app"} and operation_status in {"succeeded", "completed"} else SIGNAL_UNKNOWN
    version = str(runtime.get("version") or "").strip()
    return {
        "route": {"signal": route_signal, "ready": route_value if isinstance(route_value, bool) else bool(access.get("open_url")) if access.get("open_url") else None},
        "storage": {"signal": storage_signal, "mapping_count": mapping_count},
        "version": {"signal": SIGNAL_PRESENT if version else SIGNAL_UNKNOWN, "present": bool(version)},
        "install_history": {"signal": install_history},
        "removal_history": {"signal": removal_history},
    }

def _saved_positive_install_evidence(saved: dict[str, Any]) -> bool:
    state = str(saved.get("install_state") or saved.get("installation_state") or "").strip().lower()
    status = str(saved.get("status") or "").strip().lower()
    return bool(
        saved.get("installed") is True
        or state in {"installed", "installed_running", "installed_stopped", "installed_degraded", "state_conflict"}
        or status in {"ready", "installed", "running", "needs_attention"}
    )


def reconcile_install_state(app_id: str, saved: dict[str, Any] | None = None, *, force: bool = False) -> dict[str, Any]:
    saved = saved if isinstance(saved, dict) else {}
    runtime = probe_app_runtime(app_id, force=force)
    saved_installed = _saved_positive_install_evidence(saved)
    runtime_state = str(runtime.get("installation_state") or "unknown")
    runtime_installed = bool(runtime.get("installed"))
    explicit_runtime_absence = runtime_state == "not_installed"
    saved_state = str(saved.get("install_state") or saved.get("installation_state") or saved.get("status") or "").strip().lower()
    saved_explicit_absence = saved.get("installed") is False and saved_state in {"not_installed", "unavailable", "missing"}
    runtime_internal_conflict = bool(runtime.get("state_conflict"))
    persisted_conflict = bool((saved_installed and explicit_runtime_absence) or (runtime_installed and saved_explicit_absence))
    conflict = runtime_internal_conflict or persisted_conflict

    result = dict(runtime)
    context_evidence = _saved_context_evidence(saved)
    evidence = dict(result.get("evidence") or {})
    evidence.update(context_evidence)
    result["evidence"] = evidence
    if runtime_internal_conflict or (saved_installed and explicit_runtime_absence):
        result["installation_state"] = "state_conflict"
        result["installed"] = True
        result["running"] = bool(runtime.get("running"))
    elif runtime_state == "unknown" and saved_installed:
        result["installed"] = True
        result["installation_state"] = str(saved.get("install_state") or "installed_degraded")
        if result["installation_state"] not in INSTALL_STATES or result["installation_state"] == "not_installed":
            result["installation_state"] = "installed_degraded"
        result["evidence_quality"] = "saved_last_valid"
    result.update(
        {
            "saved_installed": saved_installed,
            "state_conflict": conflict,
            "authoritative_source": "runtime_evidence" if runtime_state not in {"unknown"} else "saved_last_valid",
        }
    )
    return result


def install_guard(app_id: str) -> dict[str, Any]:
    evidence = reconcile_install_state(app_id, force=True)
    if evidence.get("installed") or evidence.get("installation_state") in {"unknown", "state_conflict"}:
        summary = (
            "The app is already installed on this device."
            if evidence.get("installed")
            else "Pocket Lab could not safely confirm that the app is absent. Check again before installing."
        )
        return {"allowed": False, "status": "already_installed" if evidence.get("installed") else "checking", "summary": summary, "runtime": evidence}
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
