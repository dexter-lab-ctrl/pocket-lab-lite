#!/usr/bin/env python3
"""Pocket Lab Lite Phase 5 long-duration gate evidence helpers.

This module intentionally owns structured JSON operations so the Bash framework can
remain portable on Android/Termux without requiring jq or GNU-only utilities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
ORCHESTRATOR_VERSION = "phase5-group4-v1"
REPORT_FORMAT_VERSION = "1"
TERMINAL_CHECKPOINT_STATES = {"passed", "failed", "skipped", "unavailable"}
CHECKPOINT_STATES = {
    "not_started",
    "running",
    "interrupted",
    "passed",
    "failed",
    "skipped",
    "unavailable",
}
REAL_PHASE5_GATES = {
    "idle",
    "repeated-scans",
    "progress-soak",
    "submission-recovery",
    "nats-restart",
    "worker-restart",
    "wal-pressure",
    "low-storage",
    "android-resume",
}
IMPLEMENTED_PHASE5_GATES = set(REAL_PHASE5_GATES)
UNAVAILABLE_FUTURE_GATES = REAL_PHASE5_GATES - IMPLEMENTED_PHASE5_GATES

SENSITIVE_KEY_RE = re.compile(
    r"(?i)(authorization|cookie|password|passwd|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|invite[_-]?token|nats[_-]?(?:credential|password|token)|"
    r"private[_-]?key|client[_-]?secret|secret[_-]?key)"
)
SECRET_PATTERNS = (
    ("authorization_header", re.compile(r"(?i)authorization\s*:\s*(?:bearer|basic)\s+\S+")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("credential_url", re.compile(r"(?i)\b(?:https?|nats)://[^\s/:]+:[^\s/@]+@")),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(?:POCKETLAB_API_TOKEN|NATS_(?:PASSWORD|TOKEN|CREDS)|"
            r"PASSWORD|API_KEY|ACCESS_TOKEN|INVITE_TOKEN|PRIVATE_KEY)\s*[=:]\s*"
            r"(?!\[REDACTED\]|null\b|None\b|false\b|true\b)[^\s,}\]]+"
        ),
    ),
    (
        "json_secret_value",
        re.compile(
            r'(?i)"(?:authorization|cookie|password|passwd|api[_-]?key|access[_-]?token|'
            r'refresh[_-]?token|invite[_-]?token|nats[_-]?(?:credential|password|token)|'
            r'private[_-]?key|client[_-]?secret|secret[_-]?key)"\s*:\s*"'
            r'(?!\[REDACTED\]")[^"\n]{4,}"'
        ),
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def epoch_seconds() -> int:
    return int(time.time())


def read_json(path: Path, *, required: bool = True) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        if required:
            raise ValueError(f"required JSON file is missing: {path.name}") from None
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.name}: {exc.msg}") from None


def fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_tmp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        fsync_directory(path.parent)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass


def stable_path_identifier(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"basename": None, "identifier": None}
    raw = str(path.expanduser())
    return {
        "basename": path.name or ".",
        "identifier": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12],
    }


def sanitize_scalar(value: Any, *, key: str = "") -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if SENSITIVE_KEY_RE.search(key):
        return "[REDACTED]"
    text = re.sub(
        r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)\b(https?|nats)://([^\s/:]+):([^\s/@]+)@",
        r"\1://[REDACTED]@",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:POCKETLAB_API_TOKEN|NATS_(?:PASSWORD|TOKEN|CREDS)|PASSWORD|"
        r"API_KEY|ACCESS_TOKEN|INVITE_TOKEN|PRIVATE_KEY)=\S+",
        "[REDACTED]",
        text,
    )
    return text[:4096]


def sanitize_data(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= 200:
                sanitized["_truncated"] = True
                break
            item_key = str(raw_key)[:160]
            sanitized[item_key] = sanitize_data(raw_value, key=item_key, depth=depth + 1)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [sanitize_data(item, key=key, depth=depth + 1) for item in list(value)[:200]]
    return sanitize_scalar(value, key=key)


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 3.0,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if not executable:
        return {
            "available": False,
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "error_type": "tool_unavailable",
        }
    safe_env = os.environ.copy()
    if env:
        safe_env.update(env)
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [executable, *command[1:]],
            cwd=str(cwd) if cwd else None,
            env=safe_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, _stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                process.kill()
            try:
                process.communicate(timeout=1.0)
            except (subprocess.TimeoutExpired, OSError):
                pass
        return {
            "available": True,
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "error_type": "timeout",
        }
    except OSError as exc:
        if process is not None and process.poll() is None:
            process.kill()
        return {
            "available": True,
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "error_type": type(exc).__name__,
        }
    return_code = int(process.returncode if process is not None else 1)
    return {
        "available": True,
        "ok": return_code == 0,
        "exit_code": return_code,
        "stdout": sanitize_scalar((stdout or "").strip())[:8192],
        "error_type": None if return_code == 0 else "command_failed",
    }


def command_version(command: list[str], *, timeout: float = 2.0) -> str | None:
    result = run_command(command, timeout=timeout)
    if not result["available"] or not result["stdout"]:
        return None
    return str(result["stdout"]).splitlines()[0][:240]


def parse_json_output(result: dict[str, Any]) -> dict[str, Any] | list[Any] | None:
    if not result.get("stdout"):
        return None
    try:
        value = json.loads(str(result["stdout"]))
    except json.JSONDecodeError:
        return None
    return sanitize_data(value)


def endpoint_summary(endpoint: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"valid_json_object": False}
    if endpoint == "/health":
        services = payload.get("services")
        safe_services: dict[str, Any] = {}
        if isinstance(services, dict):
            for name, state in list(services.items())[:50]:
                if isinstance(state, dict):
                    safe_services[str(name)] = {
                        key: sanitize_data(state.get(key), key=key)
                        for key in ("status", "healthy", "ready", "reachable")
                        if key in state
                    }
                else:
                    safe_services[str(name)] = sanitize_scalar(state)
        return {
            "status": sanitize_scalar(payload.get("status")),
            "healthy": payload.get("healthy"),
            "ready": payload.get("ready"),
            "services": safe_services,
        }
    if endpoint.endswith("/security/progress"):
        keys = (
            "run_id",
            "status",
            "stage",
            "percent",
            "active_scan",
            "storage_backend",
            "source",
            "read_degraded",
            "projection_age_ms",
            "sqlite_revision",
            "updated_at_epoch_ms",
            "execution_started_at",
            "completed_at",
        )
        return {key: sanitize_data(payload.get(key), key=key) for key in keys if key in payload}
    if endpoint.endswith("/diagnostics/runtime"):
        keys = (
            "sanitized",
            "event_loop",
            "admission",
            "request_limits",
            "security_progress_refresher",
            "progress_refresher",
            "recent_operations",
        )
        return {key: sanitize_data(payload.get(key), key=key) for key in keys if key in payload}
    if endpoint.endswith("/nats/status"):
        keys = (
            "mode",
            "connected",
            "servers",
            "jetstream_enabled",
            "nats_required",
            "watchdog_running",
            "reconnect_pending",
            "transient_invalid_state_errors",
            "published",
            "received",
            "durable_consumer_health",
            "streams",
        )
        return {key: sanitize_data(payload.get(key), key=key) for key in keys if key in payload}
    if endpoint.endswith("/workflows/status"):
        keys = ("status", "healthy", "active", "queued", "running", "failed")
        return {key: sanitize_data(payload.get(key), key=key) for key in keys if key in payload}
    return sanitize_data(payload)


def fetch_json(base_url: str, endpoint: str, *, timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + endpoint
    headers = {"Accept": "application/json"}
    token = os.getenv("POCKETLAB_API_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1024 * 1024)
            status_code = int(response.status)
    except urllib.error.HTTPError as exc:
        return {
            "available": True,
            "ok": False,
            "status_code": int(exc.code),
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "error_type": "http_error",
            "sanitized": True,
        }
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        error_type = "timeout" if isinstance(reason, TimeoutError) else "unreachable"
        return {
            "available": False,
            "ok": False,
            "status_code": None,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "error_type": error_type,
            "sanitized": True,
        }
    except (TimeoutError, OSError):
        return {
            "available": False,
            "ok": False,
            "status_code": None,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "error_type": "timeout",
            "sanitized": True,
        }
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "available": True,
            "ok": False,
            "status_code": status_code,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "error_type": "invalid_json",
            "sanitized": True,
        }
    return {
        "available": True,
        "ok": status_code == 200,
        "status_code": status_code,
        "latency_ms": round((time.monotonic() - started) * 1000, 2),
        "payload": endpoint_summary(endpoint, payload),
        "sanitized": True,
    }


def pm2_processes() -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    result = run_command(["pm2", "jlist"], timeout=5.0)
    if not result["available"]:
        return [], ["pm2 unavailable"]
    if not result["ok"]:
        return [], ["pm2 process inventory failed"]
    try:
        rows = json.loads(str(result["stdout"]))
    except json.JSONDecodeError:
        return [], ["pm2 returned invalid JSON"]
    processes: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        env = row.get("pm2_env") if isinstance(row.get("pm2_env"), dict) else {}
        monit = row.get("monit") if isinstance(row.get("monit"), dict) else {}
        started_ms = env.get("pm_uptime")
        uptime_seconds = None
        if isinstance(started_ms, (int, float)) and started_ms > 0:
            uptime_seconds = max(0, int(time.time() - (float(started_ms) / 1000.0)))
        name = str(row.get("name") or "")[:160]
        processes.append(
            {
                "name": name,
                "status": sanitize_scalar(env.get("status")),
                "pid": int(row.get("pid") or 0) or None,
                "restart_count": int(env.get("restart_time") or 0),
                "uptime_seconds": uptime_seconds,
                "rss_bytes": int(monit.get("memory") or 0),
                "cpu_percent": float(monit.get("cpu") or 0.0),
                "open_file_descriptors": open_fd_count(int(row.get("pid") or 0)),
            }
        )
    processes.sort(key=lambda item: item["name"])
    return processes, warnings


def open_fd_count(pid: int) -> int | None:
    if pid <= 0:
        return None
    fd_dir = Path("/proc") / str(pid) / "fd"
    try:
        return sum(1 for _ in fd_dir.iterdir())
    except OSError:
        return None


def scanner_inventory() -> list[dict[str, Any]]:
    result = run_command(["ps", "-eo", "pid=,ppid=,comm="], timeout=3.0)
    if not result.get("ok"):
        return []
    rows: list[dict[str, Any]] = []
    for line in str(result["stdout"]).splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        pid_raw, ppid_raw, command = parts
        command_name = Path(command).name.lower()
        if "lynis" not in command_name and "trivy" not in command_name:
            continue
        try:
            pid = int(pid_raw)
            ppid = int(ppid_raw)
        except ValueError:
            continue
        rows.append({"pid": pid, "ppid": ppid, "command": command_name[:120]})
    return rows[:100]


def bounded_dir_size(path: Path, *, max_entries: int = 5000) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "bytes": None, "entries": 0, "truncated": False}
    total = 0
    entries = 0
    truncated = False
    try:
        for root, directories, files in os.walk(path):
            directories[:] = [
                name
                for name in directories
                if name not in {"originals", "import", "storage", "shared", "DCIM"}
            ]
            for name in files:
                entries += 1
                if entries > max_entries:
                    truncated = True
                    break
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    continue
            if truncated:
                break
    except OSError:
        return {"available": False, "bytes": None, "entries": entries, "truncated": truncated}
    return {"available": True, "bytes": total, "entries": entries, "truncated": truncated}


def file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def filesystem_state(path: Path) -> dict[str, Any]:
    target = path if path.exists() else path.parent
    try:
        usage = shutil.disk_usage(target)
    except OSError:
        return {"available": False, "free_bytes": None, "free_percent": None}
    free_percent = round((usage.free / usage.total) * 100, 2) if usage.total else None
    return {
        "available": True,
        "free_bytes": usage.free,
        "free_percent": free_percent,
        "total_bytes": usage.total,
    }


def repository_identity(repo_root: Path) -> dict[str, Any]:
    commit = run_command(["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=2.0)
    branch = run_command(["git", "branch", "--show-current"], cwd=repo_root, timeout=2.0)
    dirty = run_command(["git", "status", "--porcelain"], cwd=repo_root, timeout=3.0)
    describe = run_command(
        ["git", "describe", "--tags", "--always", "--dirty"], cwd=repo_root, timeout=2.0
    )
    return {
        "commit": commit["stdout"] if commit["ok"] else None,
        "branch": branch["stdout"] if branch["ok"] else None,
        "dirty": bool(dirty["stdout"]) if dirty["ok"] else None,
        "release": describe["stdout"] if describe["ok"] else None,
    }


def runtime_identity() -> dict[str, Any]:
    prefix = os.getenv("PREFIX", "")
    runtime_type = "termux" if os.getenv("TERMUX_VERSION") or "com.termux" in prefix else "ubuntu_or_linux"
    return {
        "runtime_type": runtime_type,
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "python": command_version([sys.executable, "--version"]),
        "node": command_version(["node", "--version"]),
        "pm2": command_version(["pm2", "--version"]),
        "sqlite": command_version(["sqlite3", "--version"]),
    }


def database_and_parity(repo_root: Path, db_path: Path | None, state_dir: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    failed_required: list[str] = []
    store_mode = os.getenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "unknown")
    db_exists = bool(db_path and db_path.exists())
    required = store_mode.lower() == "sqlite" or db_exists
    if not required:
        return (
            {
                "security_store_mode": store_mode,
                "state_directory": stable_path_identifier(state_dir),
                "database": stable_path_identifier(db_path),
                "database_health": {
                    "reachable": False,
                    "schema_current": False,
                    "quick_check": "unavailable",
                    "migration_checksums_valid": None,
                    "error_type": "database_not_configured",
                },
                "json_sqlite_parity": {
                    "ok": False,
                    "matched": None,
                    "mismatch_fields": [],
                    "error_type": "database_not_configured",
                },
            },
            ["SQLite health and parity were not evaluated because no live SQLite store was configured."],
            [],
        )
    env = {
        "POCKETLAB_STATE_DIR": str(state_dir),
        "POCKETLAB_LITE_SECURITY_STORE_MODE": store_mode,
    }
    if db_path:
        env["POCKETLAB_LITE_DB_PATH"] = str(db_path)
    health_result = run_command(
        [sys.executable, "scripts/lite/security-db-check.py"],
        cwd=repo_root,
        timeout=float(os.getenv("POCKETLAB_LONG_GATE_DB_TIMEOUT", "12")),
        env=env,
    )
    health = parse_json_output(health_result)
    if isinstance(health, dict):
        health.pop("path", None)
    else:
        health = {
            "reachable": False,
            "schema_current": False,
            "quick_check": "unavailable",
            "error_type": health_result.get("error_type") or "invalid_output",
        }
    if required and not health_result.get("ok"):
        failed_required.append("sqlite_health")
    elif not health_result.get("ok"):
        warnings.append("SQLite health unavailable in this environment")

    parity_result = run_command(
        [sys.executable, "scripts/lite/security-db-compare.py", "--no-record"],
        cwd=repo_root,
        timeout=float(os.getenv("POCKETLAB_LONG_GATE_DB_TIMEOUT", "12")),
        env=env,
    )
    parity_payload = parse_json_output(parity_result)
    if isinstance(parity_payload, dict):
        parity = {
            "ok": parity_payload.get("ok"),
            "matched": parity_payload.get("matched"),
            "mismatch_fields": sanitize_data(parity_payload.get("mismatch_fields") or []),
            "compared_at": sanitize_scalar(parity_payload.get("compared_at")),
        }
    else:
        parity = {
            "ok": False,
            "matched": None,
            "mismatch_fields": [],
            "error_type": parity_result.get("error_type") or "invalid_output",
        }
    if required and not parity_result.get("ok"):
        failed_required.append("json_sqlite_parity")
    elif not parity_result.get("ok"):
        warnings.append("JSON/SQLite parity unavailable in this environment")

    config = {
        "security_store_mode": store_mode,
        "state_directory": stable_path_identifier(state_dir),
        "database": stable_path_identifier(db_path),
        "database_health": health,
        "json_sqlite_parity": parity,
    }
    return config, warnings, failed_required


def capture_baseline(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    state_dir = Path(args.state_dir).expanduser().resolve()
    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else None
    warnings: list[str] = []
    missing_optional: list[str] = []
    failed_required: list[str] = []

    config, config_warnings, config_failures = database_and_parity(repo_root, db_path, state_dir)
    warnings.extend(config_warnings)
    failed_required.extend(config_failures)

    processes, process_warnings = pm2_processes()
    warnings.extend(process_warnings)
    if not processes:
        missing_optional.append("pm2_process_inventory")

    endpoints = (
        "/health",
        "/api/lite/security/progress",
        "/api/lite/diagnostics/runtime",
        "/api/nats/status",
        "/api/workflows/status",
    )
    api_state: dict[str, Any] = {}
    http_timeout = float(os.getenv("POCKETLAB_LONG_GATE_HTTP_TIMEOUT", "3"))
    for endpoint in endpoints:
        result = fetch_json(args.base_url, endpoint, timeout=http_timeout)
        api_state[endpoint] = result
        if not result.get("ok"):
            missing_optional.append(f"endpoint:{endpoint}")
            if args.require_live:
                failed_required.append(f"endpoint:{endpoint}")

    evidence_dir = state_dir / "security" / "evidence"
    logs_dir = state_dir / "logs"
    storage = {
        "database_bytes": file_size(db_path) if db_path else None,
        "wal_bytes": file_size(Path(str(db_path) + "-wal")) if db_path else None,
        "shm_bytes": file_size(Path(str(db_path) + "-shm")) if db_path else None,
        "evidence_directory": bounded_dir_size(evidence_dir),
        "report_directory": bounded_dir_size(run_dir),
        "logs_directory": bounded_dir_size(logs_dir, max_entries=1000),
        "filesystem": filesystem_state(run_dir),
    }
    process_by_name = {item["name"]: item for item in processes}
    named_pids = {
        role: process_by_name.get(name, {}).get("pid")
        for role, name in {
            "api": "pocket-api",
            "worker": "pocket-worker",
            "nats": "pocket-nats",
            "node_agent": "pocket-node-agent",
            "supervisor": "pocketlab-core-supervisor",
            "caddy": "caddy-proxy",
            "telemetry": "pocket-telemetry",
        }.items()
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "baseline_phase": args.phase,
        "run_id": args.run_id,
        "captured_at": utc_now(),
        "status": "failed" if failed_required else "captured",
        "sanitized": True,
        "warnings": sorted(set(warnings)),
        "missing_optional_tools": sorted(set(missing_optional)),
        "failed_required_checks": sorted(set(failed_required)),
        "repository": repository_identity(repo_root),
        "runtime": runtime_identity(),
        "pocket_lab": config,
        "process_state": {
            "processes": processes,
            "named_pids": named_pids,
            "scanner_children": scanner_inventory(),
        },
        "storage": storage,
        "api_runtime": api_state,
    }
    atomic_write_json(Path(args.output), payload)
    return 2 if failed_required else 0


def validate_manifest(manifest: dict[str, Any], run_id: str) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("manifest schema version is unsupported")
    if manifest.get("run_id") != run_id:
        raise ValueError("manifest run ID does not match requested run")
    if manifest.get("sanitized") is not True:
        raise ValueError("manifest is not marked sanitized")


def init_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    manifest_path = run_dir / "manifest.json"
    state_path = run_dir / "state.json"
    selected_gates = [item for item in args.gates.split(",") if item]
    run_dir.mkdir(parents=True, exist_ok=True)
    for relative in (
        "checkpoints",
        "baseline",
        "gates",
        "samples",
        "logs",
        "tmp",
    ):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)
    now = utc_now()
    repo = repository_identity(Path(args.repo_root).resolve())
    if args.resume:
        manifest = read_json(manifest_path)
        validate_manifest(manifest, args.run_id)
        requested_gates = [item for item in args.gates.split(",") if item]
        if requested_gates and manifest.get("selected_gates") != requested_gates:
            raise ValueError("resume gate selection does not match the run manifest")
        state = read_json(state_path)
        if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("run state is missing or has an unsupported schema")
        state["resume_count"] = int(state.get("resume_count") or 0) + 1
        state["status"] = "running"
        state["updated_at"] = now
        state["failure_reason"] = ""
        manifest["resume_count"] = state["resume_count"]
        manifest["updated_at"] = now
        atomic_write_json(state_path, state)
        atomic_write_json(manifest_path, manifest)
        return 0
    if manifest_path.exists() or state_path.exists():
        raise ValueError("run directory already contains a manifest or state file")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "report_format_version": REPORT_FORMAT_VERSION,
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "run_id": args.run_id,
        "created_at": now,
        "updated_at": now,
        "repository_commit": repo.get("commit"),
        "selected_gates": selected_gates,
        "state": "running",
        "resume_count": 0,
        "sanitized": True,
    }
    state = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "status": "running",
        "mode": args.mode,
        "started_at": now,
        "updated_at": now,
        "completed_at": None,
        "resume_count": 0,
        "current_gate": None,
        "current_stage": None,
        "failure_reason": "",
        "sanitized": True,
    }
    atomic_write_json(manifest_path, manifest)
    atomic_write_json(state_path, state)
    return 0


def update_run_state(args: argparse.Namespace) -> int:
    path = Path(args.run_dir) / "state.json"
    state = read_json(path)
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("run state is invalid")
    if args.status:
        state["status"] = args.status
    if args.current_gate is not None:
        state["current_gate"] = args.current_gate or None
    if args.current_stage is not None:
        state["current_stage"] = args.current_stage or None
    if args.failure_reason is not None:
        state["failure_reason"] = sanitize_scalar(args.failure_reason)
    state["updated_at"] = utc_now()
    if args.status in {"passed", "failed", "interrupted", "framework_validated", "baseline_captured", "not_ready"}:
        state["completed_at"] = state["updated_at"]
    atomic_write_json(path, state)
    return 0


def checkpoint_path(run_dir: Path, gate_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,80}", gate_id):
        raise ValueError("gate ID contains unsupported characters")
    return run_dir / "checkpoints" / f"{gate_id}.json"


def validate_checkpoint(payload: dict[str, Any], *, run_id: str, gate_id: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError("checkpoint must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("checkpoint schema version is unsupported")
    if payload.get("run_id") != run_id or payload.get("gate_id") != gate_id:
        raise ValueError("checkpoint identity is inconsistent")
    if payload.get("status") not in CHECKPOINT_STATES:
        raise ValueError("checkpoint status is invalid")
    if not isinstance(payload.get("history"), list):
        raise ValueError("checkpoint history is invalid")


def checkpoint_transition(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    path = checkpoint_path(run_dir, args.gate_id)
    now = utc_now()
    if path.exists():
        payload = read_json(path)
        validate_checkpoint(payload, run_id=args.run_id, gate_id=args.gate_id)
    else:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": args.run_id,
            "gate_id": args.gate_id,
            "stage_id": args.stage_id,
            "status": "not_started",
            "started_at": None,
            "updated_at": now,
            "completed_at": None,
            "attempt": 0,
            "failure_reason": "",
            "evidence_refs": [],
            "last_successful_stage": None,
            "resume_safe": True,
            "retryable": True,
            "sanitized": True,
            "history": [],
        }
    prior_status = payload.get("status")
    if args.status == "running":
        if prior_status == "running":
            payload["history"].append(
                {
                    "stage_id": payload.get("stage_id"),
                    "status": "interrupted",
                    "started_at": payload.get("started_at"),
                    "completed_at": now,
                    "attempt": payload.get("attempt"),
                    "failure_reason": "Previous process ended before the stage checkpoint completed.",
                    "resume_safe": bool(payload.get("resume_safe", True)),
                }
            )
        payload["attempt"] = int(payload.get("attempt") or 0) + 1
        payload["started_at"] = now
        payload["completed_at"] = None
        payload["failure_reason"] = ""
    elif args.status in TERMINAL_CHECKPOINT_STATES | {"interrupted"}:
        if prior_status == "running" and payload.get("stage_id") != args.stage_id:
            raise ValueError("cannot complete a different stage than the active checkpoint stage")
        payload["completed_at"] = now
    payload["stage_id"] = args.stage_id
    payload["status"] = args.status
    payload["updated_at"] = now
    payload["resume_safe"] = bool(args.resume_safe)
    payload["retryable"] = bool(args.retryable)
    payload["failure_reason"] = sanitize_scalar(args.failure_reason or "")
    refs = [item for item in (args.evidence_refs or "").split(",") if item]
    payload["evidence_refs"] = refs
    if args.status == "passed":
        payload["last_successful_stage"] = args.stage_id
    if args.status == "failed" and not payload["failure_reason"]:
        raise ValueError("failed checkpoint requires a non-empty failure reason")
    payload["history"].append(
        {
            "stage_id": args.stage_id,
            "status": args.status,
            "started_at": payload.get("started_at"),
            "completed_at": payload.get("completed_at"),
            "attempt": payload.get("attempt"),
            "failure_reason": payload["failure_reason"],
            "resume_safe": payload["resume_safe"],
            "evidence_refs": refs,
        }
    )
    payload["history"] = payload["history"][-200:]
    atomic_write_json(path, payload)
    return 0


def checkpoint_status(args: argparse.Namespace) -> int:
    path = checkpoint_path(Path(args.run_dir), args.gate_id)
    if not path.exists():
        print("not_started")
        return 0
    payload = read_json(path)
    validate_checkpoint(payload, run_id=args.run_id, gate_id=args.gate_id)
    if args.stage_id and payload.get("stage_id") != args.stage_id:
        for entry in reversed(payload.get("history", [])):
            if entry.get("stage_id") == args.stage_id:
                print(entry.get("status") or "not_started")
                return 0
        print("not_started")
        return 0
    print(payload.get("status") or "not_started")
    return 0


def mark_interrupted(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    checkpoint_dir = run_dir / "checkpoints"
    for path in sorted(checkpoint_dir.glob("*.json")):
        payload = read_json(path)
        gate_id = path.stem
        validate_checkpoint(payload, run_id=args.run_id, gate_id=gate_id)
        if payload.get("status") != "running":
            continue
        now = utc_now()
        reason = "Previous process ended before the stage checkpoint completed."
        payload["status"] = "interrupted"
        payload["updated_at"] = now
        payload["completed_at"] = now
        payload["failure_reason"] = reason
        payload["history"].append(
            {
                "stage_id": payload.get("stage_id"),
                "status": "interrupted",
                "started_at": payload.get("started_at"),
                "completed_at": now,
                "attempt": payload.get("attempt"),
                "failure_reason": reason,
                "resume_safe": bool(payload.get("resume_safe", True)),
                "evidence_refs": payload.get("evidence_refs") or [],
            }
        )
        payload["history"] = payload["history"][-200:]
        atomic_write_json(path, payload)
    return 0


def gate_result(args: argparse.Namespace) -> int:
    if args.status == "failed" and not args.failure_reason:
        raise ValueError("failed gate result requires a non-empty failure reason")
    result_dir = Path(args.run_dir) / "gates" / args.gate_id
    result_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "gate_id": args.gate_id,
        "status": args.status,
        "phase5_gate": bool(args.phase5_gate),
        "framework_validation": bool(args.framework_validation),
        "started_at": args.started_at or None,
        "completed_at": utc_now(),
        "duration_seconds": max(0.0, float(args.duration_seconds or 0.0)),
        "failure_reason": sanitize_scalar(args.failure_reason or ""),
        "failed_stage": sanitize_scalar(args.failed_stage or ""),
        "retryable": bool(args.retryable),
        "resume_safe": bool(args.resume_safe),
        "evidence_refs": [item for item in (args.evidence_refs or "").split(",") if item],
        "sanitized": True,
    }
    atomic_write_json(result_dir / "result.json", payload)
    return 0


def _stage_passed(checkpoint: dict[str, Any] | None, stage_id: str) -> bool:
    if not checkpoint:
        return False
    if checkpoint.get("stage_id") == stage_id and checkpoint.get("status") == "passed":
        return True
    return any(
        isinstance(entry, dict)
        and entry.get("stage_id") == stage_id
        and entry.get("status") == "passed"
        for entry in checkpoint.get("history", [])
    )


def framework_self_test(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    gate_id = args.gate_id
    gate_dir = run_dir / "gates" / gate_id
    gate_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_path(run_dir, gate_id)

    def transition(stage_id: str, status: str, reason: str = "") -> None:
        namespace = argparse.Namespace(
            run_dir=str(run_dir),
            run_id=args.run_id,
            gate_id=gate_id,
            stage_id=stage_id,
            status=status,
            failure_reason=reason,
            evidence_refs="",
            resume_safe=1,
            retryable=1,
        )
        checkpoint_transition(namespace)

    def current_checkpoint() -> dict[str, Any] | None:
        if not path.exists():
            return None
        payload = read_json(path)
        validate_checkpoint(payload, run_id=args.run_id, gate_id=gate_id)
        return payload

    stages = ("layout", "atomic-evidence", "sample-stream", "resume-boundary")
    for stage_id in stages:
        checkpoint = current_checkpoint()
        if _stage_passed(checkpoint, stage_id):
            continue
        transition(stage_id, "running")
        if os.getenv("POCKETLAB_LONG_GATE_SELF_TEST_INTERRUPT_AT_STAGE") == stage_id:
            return 75
        if stage_id == "layout":
            missing = [
                name
                for name in ("checkpoints", "baseline", "gates", "samples", "logs", "tmp")
                if not (run_dir / name).is_dir()
            ]
            if missing:
                transition(stage_id, "failed", "Required run directories are missing: " + ", ".join(missing))
                return 2
            atomic_write_json(
                gate_dir / "layout.json",
                {
                    "status": "passed",
                    "sanitized": True,
                    "production_commands_published": 0,
                    "production_services_restarted": 0,
                },
            )
        elif stage_id == "atomic-evidence":
            output = gate_dir / "atomic-write.json"
            atomic_write_json(output, {"status": "passed", "atomic": True, "sanitized": True})
            leftovers = list(gate_dir.glob(".*.tmp"))
            if leftovers:
                transition(stage_id, "failed", "Atomic JSON write left a temporary file behind.")
                return 2
        elif stage_id == "sample-stream":
            sample = gate_dir / "samples.jsonl"
            append_jsonl(sample, {"sample": 1, "status": "ok", "sanitized": True})
            append_jsonl(sample, {"sample": 2, "status": "ok", "sanitized": True})
        elif stage_id == "resume-boundary":
            pause = float(os.getenv("POCKETLAB_LONG_GATE_SELF_TEST_PAUSE_SECONDS", "0"))
            if pause > 0:
                time.sleep(pause)
            atomic_write_json(
                gate_dir / "resume-boundary.json",
                {"status": "passed", "resume_safe": True, "sanitized": True},
            )
        transition(stage_id, "passed")
    return 0


def compare_processes(before: dict[str, Any], after: dict[str, Any]) -> tuple[list[str], list[str]]:
    before_rows = before.get("process_state", {}).get("processes", [])
    after_rows = after.get("process_state", {}).get("processes", [])
    before_by_name = {row.get("name"): row for row in before_rows if isinstance(row, dict)}
    after_by_name = {row.get("name"): row for row in after_rows if isinstance(row, dict)}
    restarts: list[str] = []
    exits: list[str] = []
    for name, prior in before_by_name.items():
        current = after_by_name.get(name)
        if not current:
            exits.append(str(name))
            continue
        if int(current.get("restart_count") or 0) > int(prior.get("restart_count") or 0):
            restarts.append(str(name))
        if prior.get("status") == "online" and current.get("status") != "online":
            exits.append(str(name))
    return sorted(set(restarts)), sorted(set(exits))


def invariant_record(status: str, evidence: Any = None, reason: str = "") -> dict[str, Any]:
    return {
        "status": status,
        "reason": sanitize_scalar(reason),
        "evidence": sanitize_data(evidence),
    }


def evaluate_invariants(args: argparse.Namespace) -> int:
    before = read_json(Path(args.before), required=False) or {}
    after = read_json(Path(args.after), required=False) or {}
    pocket = after.get("pocket_lab", {}) if isinstance(after, dict) else {}
    health = pocket.get("database_health", {}) if isinstance(pocket, dict) else {}
    parity = pocket.get("json_sqlite_parity", {}) if isinstance(pocket, dict) else {}
    store_mode = pocket.get("security_store_mode")
    restarts, exits = compare_processes(before, after) if before and after else ([], [])
    checks: dict[str, Any] = {
        "sqlite_authoritative": invariant_record(
            "passed" if store_mode == "sqlite" else "not_evaluated",
            store_mode,
            "Security store mode was not reported as sqlite." if store_mode != "sqlite" else "",
        ),
        "sqlite_quick_check": invariant_record(
            "passed" if health.get("quick_check") == "ok" else "failed" if health.get("reachable") else "not_evaluated",
            health.get("quick_check"),
            "SQLite quick_check did not return ok." if health.get("reachable") and health.get("quick_check") != "ok" else "",
        ),
        "schema_current": invariant_record(
            "passed" if health.get("schema_current") is True else "failed" if health.get("reachable") else "not_evaluated",
            {
                "schema_version": health.get("schema_version"),
                "expected_schema_version": health.get("expected_schema_version"),
            },
            "SQLite schema is not current." if health.get("reachable") and health.get("schema_current") is not True else "",
        ),
        "migration_checksums": invariant_record(
            "passed" if health.get("migration_checksums_valid") is True else "failed" if health.get("reachable") else "not_evaluated",
            health.get("migration_checksums_valid"),
            "Migration checksums are invalid." if health.get("reachable") and health.get("migration_checksums_valid") is not True else "",
        ),
        "json_sqlite_parity": invariant_record(
            "passed" if parity.get("matched") is True else "failed" if parity.get("matched") is False else "not_evaluated",
            {"matched": parity.get("matched"), "mismatch_fields": parity.get("mismatch_fields")},
            "JSON/SQLite parity did not match." if parity.get("matched") is False else "",
        ),
        "unexpected_process_restarts": invariant_record(
            "failed" if restarts else "passed" if before and after else "not_evaluated",
            restarts,
            "Unexpected PM2 restart count increased." if restarts else "",
        ),
        "unexpected_process_exits": invariant_record(
            "failed" if exits else "passed" if before and after else "not_evaluated",
            exits,
            "A previously online PM2 process was missing or not online." if exits else "",
        ),
        "single_active_security_run": invariant_record("not_evaluated", None, "Requires a gate-specific lifecycle sample set."),
        "terminal_active_key_cleared": invariant_record("not_evaluated", None, "Requires a gate-specific SQLite lifecycle query."),
        "lifecycle_timestamps_monotonic": invariant_record("not_evaluated", None, "Requires a gate-specific lifecycle sample set."),
        "progress_monotonic": invariant_record("not_evaluated", None, "Requires a gate-specific Progress sample set."),
        "execution_evidence_present": invariant_record("not_evaluated", None, "Requires a completed real scan gate."),
        "admission_counters_valid": invariant_record("not_evaluated", None, "Requires gate-specific admission samples."),
        "reports_sanitized": invariant_record("not_evaluated", None, "Evaluated after final report scan."),
    }
    required_failures = [name for name, item in checks.items() if item["status"] == "failed"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "evaluated_at": utc_now(),
        "checks": checks,
        "required_failures": required_failures,
        "sanitized": True,
    }
    atomic_write_json(Path(args.output), payload)
    return 2 if required_failures else 0


def iter_report_files(run_dir: Path, *, include_checksums: bool = False) -> Iterable[Path]:
    ignored_parts = {"tmp", ".lock"}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(run_dir)
        if any(part in ignored_parts for part in relative.parts):
            continue
        if not include_checksums and relative.name == "checksums.json":
            continue
        yield path


def sanitization_scan(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    output = Path(args.output)
    findings: list[dict[str, Any]] = []
    for path in iter_report_files(run_dir):
        if path.resolve() == output.resolve():
            continue
        try:
            if path.stat().st_size > 5 * 1024 * 1024:
                findings.append({"file": str(path.relative_to(run_dir)), "type": "oversized_unscanned_file"})
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            findings.append({"file": str(path.relative_to(run_dir)), "type": "unscannable_file"})
            continue
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append({"file": str(path.relative_to(run_dir)), "type": kind})
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "scanned_at": utc_now(),
        "sanitized": not findings,
        "findings": findings,
    }
    atomic_write_json(output, payload)
    return 0 if not findings else 2


def checksum_manifest(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    output = Path(args.output)
    files: list[dict[str, Any]] = []
    for path in iter_report_files(run_dir):
        if path.resolve() == output.resolve():
            continue
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            relative = str(path.relative_to(run_dir))
            files.append({"path": relative, "sha256": digest.hexdigest(), "bytes": path.stat().st_size})
        except OSError as exc:
            raise ValueError(f"unable to checksum {path.name}: {type(exc).__name__}") from None
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "generated_at": utc_now(),
        "algorithm": "sha256",
        "files": files,
        "sanitized": True,
    }
    atomic_write_json(output, payload)
    return 0


def aggregate(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    manifest = read_json(run_dir / "manifest.json")
    validate_manifest(manifest, args.run_id)
    state = read_json(run_dir / "state.json")
    results: list[dict[str, Any]] = []
    for path in sorted((run_dir / "gates").glob("*/result.json")):
        item = read_json(path)
        if isinstance(item, dict):
            results.append(item)
    counts = {name: 0 for name in ("passed", "failed", "skipped", "unavailable")}
    for item in results:
        status = str(item.get("status") or "")
        if status in counts:
            counts[status] += 1
    real_results = [item for item in results if item.get("phase5_gate") is True]
    real_passed = [item for item in real_results if item.get("status") == "passed"]
    failures = [item for item in results if item.get("status") == "failed"]
    unavailable = [item for item in results if item.get("status") == "unavailable"]
    invariants = read_json(run_dir / "invariants.json", required=False) or {}
    invariant_failures = list(invariants.get("required_failures") or []) if isinstance(invariants, dict) else []
    sanitization = read_json(run_dir / "sanitization.json", required=False) or {}
    sanitized = sanitization.get("sanitized") is True
    before = read_json(run_dir / "baseline" / "before.json", required=False) or {}
    after = read_json(run_dir / "baseline" / "after.json", required=False) or {}
    baseline_ok = before.get("status") == "captured" and after.get("status") == "captured"
    started_at = state.get("started_at")
    try:
        started_epoch = datetime.fromisoformat(str(started_at).replace("Z", "+00:00")).timestamp()
        duration = max(0.0, time.time() - started_epoch)
    except (TypeError, ValueError):
        duration = 0.0

    mode = str(state.get("mode") or "gates")
    failure_reason = ""
    if failures:
        failure_reason = str(failures[0].get("failure_reason") or "A selected gate failed.")
    elif unavailable:
        failure_reason = "One or more selected Phase 5 gates are not implemented."
    elif invariant_failures:
        failure_reason = "Required final invariants failed: " + ", ".join(invariant_failures)
    elif not baseline_ok:
        failure_reason = "Before and after baseline capture did not both succeed."
    elif not sanitized:
        failure_reason = "Sanitization validation did not pass."
    elif not real_results:
        failure_reason = "No real Phase 5 gates were executed."

    ready = bool(
        real_results
        and len(real_passed) == len(real_results)
        and not failures
        and not unavailable
        and not invariant_failures
        and baseline_ok
        and sanitized
    )
    if ready:
        status = "ready"
    elif mode == "framework_self_test" and not failures and baseline_ok and sanitized:
        status = "framework_validated"
    elif mode == "baseline_only" and baseline_ok and sanitized:
        status = "baseline_captured"
    else:
        status = "not_ready"
    after_health = after.get("pocket_lab", {}).get("database_health", {}) if isinstance(after, dict) else {}
    after_parity = after.get("pocket_lab", {}).get("json_sqlite_parity", {}) if isinstance(after, dict) else {}
    checks = invariants.get("checks", {}) if isinstance(invariants, dict) else {}
    restarts = checks.get("unexpected_process_restarts", {}).get("evidence") if isinstance(checks, dict) else None
    selected_real = {str(item) for item in (manifest.get("selected_gates") or []) if str(item) in REAL_PHASE5_GATES}
    full_phase5_ready = bool(
        selected_real == REAL_PHASE5_GATES
        and {str(item.get("gate_id") or "") for item in real_passed} == REAL_PHASE5_GATES
        and ready
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "run_id": args.run_id,
        "mode": mode,
        "duration_seconds": round(duration, 3),
        "gates_total": len(results),
        "gates_passed": counts["passed"],
        "gates_failed": counts["failed"],
        "gates_skipped": counts["skipped"],
        "gates_unavailable": counts["unavailable"],
        "real_phase5_gates_executed": len(real_results),
        "implemented_gates": sorted(IMPLEMENTED_PHASE5_GATES),
        "selected_gates": list(manifest.get("selected_gates") or []),
        "passed_gates": sorted(str(item.get("gate_id") or "") for item in results if item.get("status") == "passed"),
        "failed_gates": sorted(str(item.get("gate_id") or "") for item in results if item.get("status") == "failed"),
        "selected_unavailable_gates": sorted(str(item.get("gate_id") or "") for item in unavailable),
        "unavailable_future_gates": sorted(UNAVAILABLE_FUTURE_GATES),
        "phase5_scope_complete": full_phase5_ready,
        "full_phase5_ready": full_phase5_ready,
        "unexpected_process_restarts": restarts,
        "duplicate_runs": None,
        "stale_active_runs": None,
        "sqlite_quick_check": after_health.get("quick_check"),
        "parity_matched": after_parity.get("matched"),
        "sanitized": sanitized,
        "failure_reason": sanitize_scalar(failure_reason),
        "required_invariant_failures": invariant_failures,
        "baseline_before_status": before.get("status"),
        "baseline_after_status": after.get("status"),
        "completed_at": utc_now(),
    }
    if status == "not_ready" and not payload["failure_reason"]:
        payload["failure_reason"] = "Phase 5 readiness requirements were not satisfied."
    atomic_write_json(Path(args.output), payload)
    state["status"] = status
    state["updated_at"] = payload["completed_at"]
    state["completed_at"] = payload["completed_at"]
    state["current_gate"] = None
    state["current_stage"] = None
    state["failure_reason"] = payload["failure_reason"]
    atomic_write_json(run_dir / "state.json", state)
    return 0 if status in {"ready", "framework_validated", "baseline_captured"} else 2


def write_json_command(args: argparse.Namespace) -> int:
    if args.json:
        try:
            payload = json.loads(args.json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid --json payload: {exc.msg}") from None
    else:
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from stdin: {exc.msg}") from None
    atomic_write_json(Path(args.output), sanitize_data(payload))
    return 0


def append_jsonl_command(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid --json payload: {exc.msg}") from None
    append_jsonl(Path(args.output), sanitize_data(payload))
    return 0


def lock_metadata(args: argparse.Namespace) -> int:
    host = socket.gethostname().split(".")[0][:80]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "pid": int(args.pid),
        "started_at": utc_now(),
        "started_epoch": epoch_seconds(),
        "device_label": sanitize_scalar(host),
        "owner_state": "active",
        "sanitized": True,
    }
    atomic_write_json(Path(args.output), payload)
    return 0


def inspect_lock(args: argparse.Namespace) -> int:
    path = Path(args.path)
    payload = read_json(path)
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("lock metadata is invalid")
    if payload.get("run_id") != args.run_id:
        raise ValueError("lock metadata belongs to a different run")
    pid = int(payload.get("pid") or 0)
    active = False
    if pid > 0:
        try:
            os.kill(pid, 0)
            active = True
        except ProcessLookupError:
            active = False
        except PermissionError:
            active = True
    raw_started_epoch = payload.get("started_epoch")
    try:
        started_epoch = int(raw_started_epoch)
    except (TypeError, ValueError):
        started_epoch = epoch_seconds()
    age = max(0, epoch_seconds() - started_epoch)
    result = {"active": active, "age_seconds": age, "pid": pid, "valid": True}
    print(json.dumps(result, sort_keys=True))
    if active:
        return 3
    if age < int(args.minimum_age):
        return 4
    return 0


def find_resumable(args: argparse.Namespace) -> int:
    root = Path(args.report_root)
    candidates: list[tuple[float, str]] = []
    if root.exists():
        for state_path in root.glob("*/state.json"):
            try:
                state = read_json(state_path)
            except ValueError:
                continue
            if not isinstance(state, dict):
                continue
            if state.get("status") not in {"running", "interrupted", "not_ready"}:
                continue
            try:
                modified = state_path.stat().st_mtime
            except OSError:
                modified = 0.0
            candidates.append((modified, state_path.parent.name))
    if not candidates:
        return 2
    candidates.sort(reverse=True)
    print(candidates[0][1])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_id = subparsers.add_parser("generate-run-id")
    run_id.add_argument("--timestamp", default="")

    init = subparsers.add_parser("init-run")
    init.add_argument("--run-dir", required=True)
    init.add_argument("--run-id", required=True)
    init.add_argument("--repo-root", required=True)
    init.add_argument("--gates", default="")
    init.add_argument("--mode", default="gates")
    init.add_argument("--resume", action="store_true")

    update = subparsers.add_parser("update-state")
    update.add_argument("--run-dir", required=True)
    update.add_argument("--status", default="")
    update.add_argument("--current-gate", default=None)
    update.add_argument("--current-stage", default=None)
    update.add_argument("--failure-reason", default=None)

    checkpoint = subparsers.add_parser("checkpoint")
    checkpoint.add_argument("--run-dir", required=True)
    checkpoint.add_argument("--run-id", required=True)
    checkpoint.add_argument("--gate-id", required=True)
    checkpoint.add_argument("--stage-id", required=True)
    checkpoint.add_argument("--status", choices=sorted(CHECKPOINT_STATES), required=True)
    checkpoint.add_argument("--failure-reason", default="")
    checkpoint.add_argument("--evidence-refs", default="")
    checkpoint.add_argument("--resume-safe", type=int, choices=(0, 1), default=1)
    checkpoint.add_argument("--retryable", type=int, choices=(0, 1), default=1)

    status = subparsers.add_parser("checkpoint-status")
    status.add_argument("--run-dir", required=True)
    status.add_argument("--run-id", required=True)
    status.add_argument("--gate-id", required=True)
    status.add_argument("--stage-id", default="")

    interrupted = subparsers.add_parser("mark-interrupted")
    interrupted.add_argument("--run-dir", required=True)
    interrupted.add_argument("--run-id", required=True)

    baseline = subparsers.add_parser("baseline")
    baseline.add_argument("--repo-root", required=True)
    baseline.add_argument("--run-dir", required=True)
    baseline.add_argument("--run-id", required=True)
    baseline.add_argument("--phase", choices=("before", "after"), required=True)
    baseline.add_argument("--output", required=True)
    baseline.add_argument("--base-url", required=True)
    baseline.add_argument("--state-dir", required=True)
    baseline.add_argument("--db-path", default="")
    baseline.add_argument("--require-live", action="store_true")

    self_test = subparsers.add_parser("framework-self-test")
    self_test.add_argument("--run-dir", required=True)
    self_test.add_argument("--run-id", required=True)
    self_test.add_argument("--gate-id", default="framework-self-test")

    gate = subparsers.add_parser("gate-result")
    gate.add_argument("--run-dir", required=True)
    gate.add_argument("--run-id", required=True)
    gate.add_argument("--gate-id", required=True)
    gate.add_argument("--status", choices=("passed", "failed", "skipped", "unavailable"), required=True)
    gate.add_argument("--phase5-gate", type=int, choices=(0, 1), default=0)
    gate.add_argument("--framework-validation", type=int, choices=(0, 1), default=0)
    gate.add_argument("--started-at", default="")
    gate.add_argument("--duration-seconds", default="0")
    gate.add_argument("--failure-reason", default="")
    gate.add_argument("--failed-stage", default="")
    gate.add_argument("--retryable", type=int, choices=(0, 1), default=1)
    gate.add_argument("--resume-safe", type=int, choices=(0, 1), default=1)
    gate.add_argument("--evidence-refs", default="")

    invariants = subparsers.add_parser("evaluate-invariants")
    invariants.add_argument("--run-id", required=True)
    invariants.add_argument("--before", required=True)
    invariants.add_argument("--after", required=True)
    invariants.add_argument("--output", required=True)

    sanitize = subparsers.add_parser("sanitize-scan")
    sanitize.add_argument("--run-dir", required=True)
    sanitize.add_argument("--run-id", required=True)
    sanitize.add_argument("--output", required=True)

    checksums = subparsers.add_parser("checksums")
    checksums.add_argument("--run-dir", required=True)
    checksums.add_argument("--run-id", required=True)
    checksums.add_argument("--output", required=True)

    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--run-dir", required=True)
    aggregate_parser.add_argument("--run-id", required=True)
    aggregate_parser.add_argument("--output", required=True)

    writer = subparsers.add_parser("write-json")
    writer.add_argument("--output", required=True)
    writer.add_argument("--json", default="")

    jsonl = subparsers.add_parser("append-jsonl")
    jsonl.add_argument("--output", required=True)
    jsonl.add_argument("--json", required=True)

    lock = subparsers.add_parser("lock-metadata")
    lock.add_argument("--output", required=True)
    lock.add_argument("--run-id", required=True)
    lock.add_argument("--pid", required=True)

    inspect = subparsers.add_parser("inspect-lock")
    inspect.add_argument("--path", required=True)
    inspect.add_argument("--run-id", required=True)
    inspect.add_argument("--minimum-age", default="60")

    resumable = subparsers.add_parser("find-resumable")
    resumable.add_argument("--report-root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate-run-id":
        stamp = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        entropy = hashlib.sha256(f"{time.time_ns()}:{os.getpid()}".encode()).hexdigest()[:8]
        print(f"pocketlab-long-gates-{stamp}-{entropy}")
        return 0
    commands = {
        "init-run": init_run,
        "update-state": update_run_state,
        "checkpoint": checkpoint_transition,
        "checkpoint-status": checkpoint_status,
        "mark-interrupted": mark_interrupted,
        "baseline": capture_baseline,
        "framework-self-test": framework_self_test,
        "gate-result": gate_result,
        "evaluate-invariants": evaluate_invariants,
        "sanitize-scan": sanitization_scan,
        "checksums": checksum_manifest,
        "aggregate": aggregate,
        "write-json": write_json_command,
        "append-jsonl": append_jsonl_command,
        "lock-metadata": lock_metadata,
        "inspect-lock": inspect_lock,
        "find-resumable": find_resumable,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"ERROR: {sanitize_scalar(exc)}", file=sys.stderr)
        raise SystemExit(2) from None
