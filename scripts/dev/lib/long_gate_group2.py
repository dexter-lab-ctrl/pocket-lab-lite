#!/usr/bin/env python3
"""Phase 5 Group 2 non-disruptive endurance gate implementations.

The Group 1 framework remains responsible for run identity, locking, checkpoints,
baselines, sanitization, checksums, and final aggregation. This module owns only
bounded Group 2 sampling, read-only lifecycle inspection, trend analysis, and
per-gate result evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import signal
import sqlite3
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = 1
ACTIVE_STATUSES = {"queued", "accepted", "running", "working", "in_progress"}
TERMINAL_SUCCESS_STATUSES = {"succeeded", "degraded", "completed"}
TERMINAL_FAILURE_STATUSES = {"failed", "cancelled", "canceled"}
TERMINAL_STATUSES = TERMINAL_SUCCESS_STATUSES | TERMINAL_FAILURE_STATUSES
MIN_PROGRESS_SAMPLE_INTERVAL_MS = 200
DEFAULT_REPORT_LIMIT_BYTES = 128 * 1024 * 1024
PROCESS_NAMES = {
    "pocket-api",
    "pocket-worker",
    "pocket-nats",
    "pocket-node-agent",
    "pocketlab-core-supervisor",
    "caddy-proxy",
    "pocket-telemetry",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def epoch_ms() -> int:
    return int(time.time() * 1000)


def clamp_text(value: Any, limit: int = 1000) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)\b(https?|nats)://([^\s/:]+):([^\s/@]+)@", r"\1://[REDACTED]@", text)
    return text[:limit]


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Inconsistent JSON state in {path.name}: {exc.msg}") from None


def report_size_bytes(run_dir: Path) -> int:
    total = 0
    for path in run_dir.rglob("*"):
        if path.is_file() and ".lock" not in path.parts and "tmp" not in path.parts:
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def ensure_report_budget(run_dir: Path, maximum: int) -> None:
    current = report_size_bytes(run_dir)
    if current > maximum:
        raise GateFailure(
            f"Evidence package exceeded the configured safe limit ({current} > {maximum} bytes).",
            stage="evidence-budget",
            retryable=False,
        )


def percentile(values: Sequence[float], fraction: float) -> float | None:
    clean = sorted(float(item) for item in values if item is not None and math.isfinite(float(item)))
    if not clean:
        return None
    index = min(len(clean) - 1, max(0, math.ceil(len(clean) * fraction) - 1))
    return clean[index]


def latency_summary(values: Sequence[float]) -> dict[str, Any]:
    clean = [float(item) for item in values if item is not None and math.isfinite(float(item))]
    return {
        "count": len(clean),
        "p50": round(percentile(clean, 0.50), 4) if clean else None,
        "p95": round(percentile(clean, 0.95), 4) if clean else None,
        "max": round(max(clean), 4) if clean else None,
    }


def window_medians(values: Sequence[float], *, window_count: int = 4) -> list[float]:
    clean = [float(item) for item in values if item is not None and math.isfinite(float(item))]
    if not clean:
        return []
    window_count = max(1, min(window_count, len(clean)))
    width = max(1, len(clean) // window_count)
    windows: list[float] = []
    start = 0
    while start < len(clean):
        chunk = clean[start : start + width]
        if start + width >= len(clean) or len(windows) + 1 == window_count:
            chunk = clean[start:]
        if chunk:
            windows.append(float(statistics.median(chunk)))
        start += len(chunk)
    return windows


def evaluate_sustained_growth(
    values: Sequence[float | int | None],
    *,
    warmup_samples: int,
    budget: float,
    minimum_stable_samples: int = 4,
) -> dict[str, Any]:
    clean = [float(item) for item in values if item is not None and math.isfinite(float(item))]
    stable = clean[max(0, warmup_samples) :]
    if len(stable) < minimum_stable_samples:
        return {
            "status": "unavailable",
            "samples": len(stable),
            "reason": "Insufficient stable-window samples.",
            "budget": budget,
        }
    split = max(1, len(stable) // 3)
    early = stable[:split]
    late = stable[-split:]
    early_median = float(statistics.median(early))
    late_median = float(statistics.median(late))
    growth = late_median - early_median
    medians = window_medians(stable, window_count=min(5, len(stable)))
    monotonic_steps = sum(1 for first, second in zip(medians, medians[1:]) if second > first)
    sustained = len(medians) >= 3 and monotonic_steps >= len(medians) - 2 and growth > budget
    return {
        "status": "failed" if sustained else "passed",
        "samples": len(stable),
        "early_median": round(early_median, 3),
        "late_median": round(late_median, 3),
        "growth": round(growth, 3),
        "budget": budget,
        "window_medians": [round(item, 3) for item in medians],
        "sustained": sustained,
    }


def compare_latency_groups(values: Sequence[float], *, ratio_budget: float = 2.5, absolute_budget: float = 30.0) -> dict[str, Any]:
    clean = [float(item) for item in values if item is not None and math.isfinite(float(item))]
    if len(clean) < 4:
        return {"status": "unavailable", "samples": len(clean), "reason": "At least four runs are required."}
    width = max(1, len(clean) // 3)
    early = float(statistics.median(clean[:width]))
    late = float(statistics.median(clean[-width:]))
    ratio = late / max(early, 0.001)
    degraded = late - early > absolute_budget and ratio > ratio_budget
    return {
        "status": "failed" if degraded else "passed",
        "samples": len(clean),
        "early_median_seconds": round(early, 3),
        "late_median_seconds": round(late, 3),
        "ratio": round(ratio, 3),
        "ratio_budget": ratio_budget,
        "absolute_budget_seconds": absolute_budget,
    }


def progress_regressions(samples: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []
    prior: dict[str, dict[str, Any]] = {}
    for sample in samples:
        run_id = str(sample.get("run_id") or "")
        if not run_id:
            continue
        previous = prior.get(run_id)
        if previous:
            for key in ("percent", "revision", "run_revision", "sqlite_revision", "updated_at_epoch_ms"):
                current_value = sample.get(key)
                prior_value = previous.get(key)
                if current_value is None or prior_value is None:
                    continue
                try:
                    if float(current_value) < float(prior_value):
                        regressions.append(
                            {
                                "run_id": run_id,
                                "field": key,
                                "prior": prior_value,
                                "current": current_value,
                                "timestamp": sample.get("timestamp"),
                            }
                        )
                except (TypeError, ValueError):
                    continue
        prior[run_id] = sample
    return regressions


def direct_proxy_consistent(direct: dict[str, Any], proxy: dict[str, Any], *, target_run_id: str = "") -> tuple[bool, str]:
    direct_run = str(direct.get("run_id") or "")
    proxy_run = str(proxy.get("run_id") or "")
    if target_run_id and direct_run not in {"", target_run_id} and proxy_run not in {"", target_run_id}:
        return False, "Neither endpoint referred to the tracked run."
    if direct_run and proxy_run and direct_run != proxy_run:
        return False, "Direct and proxy responses referred to different runs."
    direct_status = str(direct.get("status") or "").lower()
    proxy_status = str(proxy.get("status") or "").lower()
    if direct_status in TERMINAL_STATUSES and proxy_status in ACTIVE_STATUSES:
        return True, "bounded_terminal_race"
    if proxy_status in TERMINAL_STATUSES and direct_status in ACTIVE_STATUSES:
        return True, "bounded_terminal_race"
    return True, "consistent"


def resume_scan_decision(state: dict[str, Any], lifecycle: dict[str, Any]) -> str:
    """Return monitor, finalize, submit, or ambiguous without mutating state."""
    tracked = str(state.get("tracked_run_id") or "")
    submission_started = bool(state.get("submission_started"))
    status = str(lifecycle.get("status") or "").lower()
    lifecycle_run = str(lifecycle.get("run_id") or "")
    if tracked:
        if lifecycle_run and lifecycle_run != tracked:
            return "ambiguous"
        if status in ACTIVE_STATUSES:
            return "monitor"
        if status in TERMINAL_STATUSES:
            return "finalize"
        return "ambiguous"
    if submission_started:
        return "ambiguous"
    return "submit"


class GateFailure(RuntimeError):
    def __init__(self, reason: str, *, stage: str = "execution", retryable: bool = True):
        super().__init__(reason)
        self.reason = clamp_text(reason)
        self.stage = stage
        self.retryable = retryable


@dataclass
class HttpResult:
    timestamp: str
    status_code: int | None
    ok: bool
    error_type: str
    latency_seconds: float
    time_starttransfer: float
    time_total: float
    etag: str
    body: dict[str, Any] | None
    response_bytes: int

    def safe_record(self, *, endpoint_type: str) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "endpoint_type": endpoint_type,
            "http_status": self.status_code,
            "ok": self.ok,
            "error_type": self.error_type,
            "time_starttransfer": round(self.time_starttransfer, 4),
            "time_total": round(self.time_total, 4),
            "etag": self.etag,
            "response_bytes": self.response_bytes,
        }


class HttpClient:
    def __init__(self, *, connect_timeout: float, total_timeout: float, token: str = ""):
        self.connect_timeout = max(0.1, float(connect_timeout))
        self.total_timeout = max(self.connect_timeout, float(total_timeout))
        self.token = token

    def request(
        self,
        method: str,
        base_url: str,
        endpoint: str,
        *,
        body: dict[str, Any] | None = None,
        etag: str = "",
        retry_read: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> HttpResult:
        attempts = 2 if retry_read and method.upper() == "GET" else 1
        last: HttpResult | None = None
        for attempt in range(attempts):
            last = self._once(method, base_url, endpoint, body=body, etag=etag, extra_headers=extra_headers)
            if last.ok or last.status_code == 304 or attempt + 1 >= attempts:
                return last
            time.sleep(0.1)
        assert last is not None
        return last

    def _once(
        self,
        method: str,
        base_url: str,
        endpoint: str,
        *,
        body: dict[str, Any] | None,
        etag: str,
        extra_headers: dict[str, str] | None,
    ) -> HttpResult:
        url = base_url.rstrip("/") + endpoint
        headers = {"Accept": "application/json"}
        if extra_headers:
            for key, value in extra_headers.items():
                clean_key = str(key).strip()
                if clean_key and "\n" not in clean_key and "\r" not in clean_key:
                    headers[clean_key] = str(value).replace("\n", "").replace("\r", "")[:512]
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if etag:
            headers["If-None-Match"] = etag
        request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        started = time.monotonic()
        status: int | None = None
        raw = b""
        response_etag = ""
        error_type = ""
        try:
            with urllib.request.urlopen(request, timeout=self.total_timeout) as response:
                first_byte = time.monotonic()
                raw = response.read(1024 * 1024)
                completed = time.monotonic()
                status = int(response.status)
                response_etag = str(response.headers.get("ETag") or "")[:256]
        except urllib.error.HTTPError as exc:
            first_byte = time.monotonic()
            completed = first_byte
            status = int(exc.code)
            response_etag = str(exc.headers.get("ETag") or "")[:256] if exc.headers else ""
            if status != 304:
                try:
                    raw = exc.read(64 * 1024)
                except OSError:
                    raw = b""
                error_type = "http_error"
        except TimeoutError:
            first_byte = completed = time.monotonic()
            error_type = "timeout"
        except urllib.error.URLError as exc:
            first_byte = completed = time.monotonic()
            error_type = "timeout" if isinstance(exc.reason, TimeoutError) else "connection_error"
        except OSError:
            first_byte = completed = time.monotonic()
            error_type = "request_error"
        payload: dict[str, Any] | None = None
        if raw:
            try:
                decoded = json.loads(raw.decode("utf-8", errors="replace"))
                if isinstance(decoded, dict):
                    payload = decoded
                else:
                    error_type = error_type or "invalid_json_shape"
            except json.JSONDecodeError:
                error_type = error_type or "invalid_json"
        ok = status is not None and (200 <= status < 300 or status == 304) and not error_type
        return HttpResult(
            timestamp=utc_now(),
            status_code=status,
            ok=ok,
            error_type=error_type,
            latency_seconds=max(0.0, completed - started),
            time_starttransfer=max(0.0, first_byte - started),
            time_total=max(0.0, completed - started),
            etag=response_etag,
            body=payload,
            response_bytes=len(raw),
        )


def normalized_progress(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    view = payload.get("view_model") if isinstance(payload.get("view_model"), dict) else {}
    merged = {**view, **payload}
    keys = (
        "run_id",
        "job_id",
        "command_id",
        "status",
        "stage",
        "current_stage",
        "percent",
        "current_percent",
        "revision",
        "run_revision",
        "sqlite_revision",
        "projection_age_ms",
        "storage_backend",
        "projection_source",
        "source",
        "read_degraded",
        "active_scan",
        "requested_at",
        "requested_at_epoch_ms",
        "command_published_at",
        "command_received_at",
        "execution_started_at",
        "last_progress_at",
        "completed_at",
        "updated_at_epoch_ms",
        "evidence_saved",
    )
    result = {key: merged.get(key) for key in keys if key in merged}
    result["stage"] = result.get("stage") or result.get("current_stage") or ""
    result["percent"] = result.get("percent") if result.get("percent") is not None else result.get("current_percent")
    result["projection_source"] = result.get("projection_source") or result.get("source") or ""
    result["status"] = str(result.get("status") or "").lower()
    return result


def run_command(command: list[str], *, cwd: Path | None = None, timeout: float = 5.0, env: dict[str, str] | None = None) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if not executable:
        return {"available": False, "ok": False, "exit_code": None, "error_type": "tool_unavailable", "stdout": ""}
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
        return {"available": True, "ok": False, "exit_code": None, "error_type": "timeout", "stdout": ""}
    except OSError as exc:
        if process is not None and process.poll() is None:
            process.kill()
        return {
            "available": True,
            "ok": False,
            "exit_code": None,
            "error_type": type(exc).__name__,
            "stdout": "",
        }
    return_code = int(process.returncode if process is not None else 1)
    return {
        "available": True,
        "ok": return_code == 0,
        "exit_code": return_code,
        "error_type": "" if return_code == 0 else "command_failed",
        "stdout": (stdout or "")[:1024 * 1024],
    }


def pm2_snapshot() -> dict[str, Any]:
    result = run_command(["pm2", "jlist"], timeout=4.0)
    if not result["ok"]:
        return {"available": result["available"], "error_type": result["error_type"], "processes": []}
    try:
        rows = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"available": True, "error_type": "invalid_json", "processes": []}
    processes: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")[:120]
        if name not in PROCESS_NAMES and not name.startswith("pocketlab-app-"):
            continue
        env = row.get("pm2_env") if isinstance(row.get("pm2_env"), dict) else {}
        monit = row.get("monit") if isinstance(row.get("monit"), dict) else {}
        pid = int(row.get("pid") or 0)
        processes.append(
            {
                "name": name,
                "pid": pid or None,
                "status": str(env.get("status") or "unknown")[:32],
                "restart_count": int(env.get("restart_time") or 0),
                "rss_bytes": int(monit.get("memory") or 0),
                "cpu_percent": float(monit.get("cpu") or 0.0),
                "fd_count": open_fd_count(pid) if pid else None,
            }
        )
    return {"available": True, "error_type": "", "processes": sorted(processes, key=lambda item: item["name"])}


def open_fd_count(pid: int) -> int | None:
    if pid <= 0:
        return None
    path = Path(f"/proc/{pid}/fd")
    try:
        return sum(1 for _ in path.iterdir())
    except OSError:
        return None


def scanner_inventory() -> list[dict[str, Any]]:
    result = run_command(["ps", "-A", "-o", "PID=,COMM="], timeout=3.0)
    if not result["ok"]:
        return []
    scanners: list[dict[str, Any]] = []
    for line in result["stdout"].splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid_raw, command = parts
        name = Path(command).name.lower()
        if name not in {"lynis", "trivy"} and not name.startswith("lynis") and not name.startswith("trivy"):
            continue
        try:
            pid = int(pid_raw)
        except ValueError:
            continue
        scanners.append({"pid": pid, "name": name[:64]})
    return scanners[:50]


def safe_tree_size(path: Path, *, max_entries: int = 20000) -> int | None:
    if not path.exists():
        return 0
    total = 0
    count = 0
    try:
        for item in path.rglob("*"):
            if count >= max_entries:
                break
            count += 1
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
    except OSError:
        return None
    return total


def resource_snapshot(*, db_path: Path, state_dir: Path, run_dir: Path, include_log_sizes: bool = True, include_scanners: bool = True) -> dict[str, Any]:
    pm2 = pm2_snapshot()
    processes = pm2.get("processes", [])
    selected = [item for item in processes if item.get("name") in {"pocket-api", "pocket-worker", "pocket-nats"}]
    stat = shutil.disk_usage(state_dir if state_dir.exists() else run_dir)
    logs_total = 0
    log_available = False
    if include_log_sizes:
        log_sources = [Path.home() / ".pm2" / "logs", state_dir / "logs"]
        for source in log_sources:
            size = safe_tree_size(source, max_entries=10000)
            if size is not None:
                logs_total += size
                log_available = True
    def fsize(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return 0
    return {
        "timestamp": utc_now(),
        "pm2_available": bool(pm2.get("available")),
        "processes": processes,
        "selected_rss_bytes": sum(int(item.get("rss_bytes") or 0) for item in selected),
        "selected_cpu_percent": round(sum(float(item.get("cpu_percent") or 0.0) for item in selected), 3),
        "selected_fd_count": sum(int(item.get("fd_count") or 0) for item in selected if item.get("fd_count") is not None) if selected else None,
        "scanner_processes": scanner_inventory() if include_scanners else [],
        "scanner_inventory_available": include_scanners,
        "db_bytes": fsize(db_path),
        "wal_bytes": fsize(Path(str(db_path) + "-wal")),
        "shm_bytes": fsize(Path(str(db_path) + "-shm")),
        "filesystem_free_bytes": stat.free,
        "filesystem_free_percent": round((stat.free / stat.total) * 100, 3) if stat.total else None,
        "log_bytes": logs_total if log_available else None,
        "evidence_bytes": report_size_bytes(run_dir),
        "sanitized": True,
    }


def compare_pm2(initial: dict[str, Any], current: dict[str, Any]) -> tuple[list[str], list[str]]:
    before = {item.get("name"): item for item in initial.get("processes", []) if item.get("name")}
    after = {item.get("name"): item for item in current.get("processes", []) if item.get("name")}
    restarts: list[str] = []
    exits: list[str] = []
    for name, prior in before.items():
        now = after.get(name)
        if not now:
            exits.append(str(name))
            continue
        if int(now.get("restart_count") or 0) > int(prior.get("restart_count") or 0):
            restarts.append(str(name))
        if prior.get("status") == "online" and now.get("status") != "online":
            exits.append(str(name))
    return sorted(set(restarts)), sorted(set(exits))


def sqlite_connect_readonly(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.is_file():
        return None
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3.0)
    connection.row_factory = sqlite3.Row
    return connection


def lifecycle_snapshot(db_path: Path, *, run_id: str = "") -> dict[str, Any]:
    connection = sqlite_connect_readonly(db_path)
    if connection is None:
        return {"available": False, "active_count": None, "runs": [], "run": None}
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(security_scan_runs)")}
        selected = [
            "run_id", "profile", "app_id", "status", "active_key", "summary", "score",
            "requested_at", "accepted_at", "started_at", "completed_at", "updated_at",
            "requested_at_epoch_ms", "accepted_at_epoch_ms", "started_at_epoch_ms", "completed_at_epoch_ms", "updated_at_epoch_ms",
            "current_stage", "current_percent", "command_id", "correlation_id", "revision", "evidence_saved",
            "critical_count", "high_count", "medium_count", "low_count", "info_count",
            "command_published_at", "command_published_at_epoch_ms", "command_received_at", "command_received_at_epoch_ms",
            "execution_started_at", "execution_started_at_epoch_ms", "last_progress_at", "last_progress_at_epoch_ms",
            "delivery_attempt", "failure_code", "failure_message",
        ]
        selected = [item for item in selected if item in columns]
        select_sql = ", ".join(selected)
        active_rows = connection.execute(
            f"SELECT {select_sql} FROM security_scan_runs WHERE active_key IS NOT NULL ORDER BY updated_at_epoch_ms DESC LIMIT 10"
        ).fetchall()
        latest_rows = connection.execute(
            f"SELECT {select_sql} FROM security_scan_runs ORDER BY updated_at_epoch_ms DESC LIMIT 10"
        ).fetchall()
        target = None
        if run_id:
            target_row = connection.execute(
                f"SELECT {select_sql} FROM security_scan_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            target = dict(target_row) if target_row else None
        return {
            "available": True,
            "active_count": len(active_rows),
            "active_runs": [dict(row) for row in active_rows],
            "runs": [dict(row) for row in latest_rows],
            "run": target,
            "sanitized": True,
        }
    finally:
        connection.close()


def latest_terminal_run(db_path: Path) -> dict[str, Any] | None:
    snapshot = lifecycle_snapshot(db_path)
    for row in snapshot.get("runs", []):
        if str(row.get("status") or "").lower() in TERMINAL_STATUSES:
            return row
    return None


def run_sqlite_tools(repo_root: Path, state_dir: Path, db_path: Path) -> dict[str, Any]:
    env = {
        "POCKETLAB_STATE_DIR": str(state_dir),
        "POCKETLAB_LITE_DB_PATH": str(db_path),
        "POCKETLAB_LITE_SECURITY_STORE_MODE": "sqlite",
    }
    health_result = run_command(
        [sys.executable, "scripts/lite/security-db-check.py"], cwd=repo_root, timeout=30.0, env=env
    )
    parity_result = run_command(
        [sys.executable, "scripts/lite/security-db-compare.py", "--no-record"], cwd=repo_root, timeout=45.0, env=env
    )
    def parse(result: dict[str, Any]) -> dict[str, Any]:
        if not result.get("stdout"):
            return {"available": result.get("available"), "ok": False, "error_type": result.get("error_type")}
        try:
            payload = json.loads(result.get("stdout") or "{}")
        except json.JSONDecodeError:
            return {"available": True, "ok": False, "error_type": "invalid_json"}
        return payload if isinstance(payload, dict) else {"available": True, "ok": False, "error_type": "invalid_json_shape"}
    health = parse(health_result)
    parity = parse(parity_result)
    return {
        "timestamp": utc_now(),
        "health": health,
        "parity": parity,
        "quick_check": health.get("quick_check"),
        "schema_current": health.get("schema_current"),
        "migration_checksums_valid": health.get("migration_checksums_valid"),
        "journal_mode": health.get("journal_mode"),
        "foreign_keys": health.get("foreign_keys"),
        "matched": parity.get("matched"),
        "mismatch_fields": parity.get("mismatch_fields", []),
        "sanitized": True,
    }


def durable_consumers_healthy(payload: dict[str, Any] | None) -> tuple[bool | None, list[str]]:
    if not isinstance(payload, dict):
        return None, []
    health = payload.get("durable_consumer_health")
    if not isinstance(health, dict) or not health:
        return None, []
    unhealthy = []
    for name, item in health.items():
        if isinstance(item, dict) and item.get("healthy") is False:
            unhealthy.append(str(name)[:120])
    return not unhealthy, unhealthy


def compact_runtime(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        "sanitized": payload.get("sanitized"),
        "event_loop": payload.get("event_loop") if isinstance(payload.get("event_loop"), dict) else {},
        "security_progress": payload.get("security_progress") if isinstance(payload.get("security_progress"), dict) else {},
        "progress_refresher": payload.get("progress_refresher") if isinstance(payload.get("progress_refresher"), dict) else {},
        "workload_admission": payload.get("workload_admission") if isinstance(payload.get("workload_admission"), dict) else {},
    }


def numeric_values(value: Any, *, key_pattern: re.Pattern[str]) -> list[float]:
    found: list[float] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key_pattern.search(str(key)) and isinstance(item, (int, float)):
                found.append(float(item))
            found.extend(numeric_values(item, key_pattern=key_pattern))
    elif isinstance(value, list):
        for item in value:
            found.extend(numeric_values(item, key_pattern=key_pattern))
    return found


def write_result(path: Path, payload: dict[str, Any]) -> None:
    status = str(payload.get("status") or "")
    reason = str(payload.get("failure_reason") or "")
    if status == "passed" and reason:
        raise RuntimeError("passed result cannot have a failure reason")
    if status == "failed" and not reason:
        raise RuntimeError("failed result requires a failure reason")
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("completed_at", utc_now())
    payload.setdefault("sanitized", True)
    payload.setdefault("phase5_gate", True)
    payload.setdefault("framework_validation", False)
    payload.setdefault("resume_safe", True)
    payload.setdefault("retryable", True)
    atomic_write_json(path, payload)


@dataclass
class Context:
    repo_root: Path
    run_dir: Path
    run_id: str
    gate_id: str
    state_dir: Path
    db_path: Path
    proxy_base_url: str
    direct_base_url: str
    connect_timeout: float
    http_timeout: float
    report_limit_bytes: int
    resume: bool

    @property
    def gate_dir(self) -> Path:
        return self.run_dir / "gates" / self.gate_id

    def client(self, *, timeout: float | None = None) -> HttpClient:
        return HttpClient(
            connect_timeout=self.connect_timeout,
            total_timeout=timeout if timeout is not None else self.http_timeout,
            token=os.getenv("POCKETLAB_API_TOKEN", ""),
        )


def common_context(args: argparse.Namespace) -> Context:
    return Context(
        repo_root=Path(args.repo_root).resolve(),
        run_dir=Path(args.run_dir).resolve(),
        run_id=args.run_id,
        gate_id=args.gate_id,
        state_dir=Path(args.state_dir).expanduser().resolve(),
        db_path=Path(args.db_path).expanduser().resolve(),
        proxy_base_url=args.proxy_base_url,
        direct_base_url=args.direct_base_url,
        connect_timeout=float(args.connect_timeout),
        http_timeout=float(args.http_timeout),
        report_limit_bytes=int(args.report_limit_bytes),
        resume=bool(args.resume),
    )


def endpoint_get(client: HttpClient, base_url: str, endpoint: str, *, endpoint_type: str, retry: bool = True) -> tuple[dict[str, Any], dict[str, Any] | None]:
    result = client.request("GET", base_url, endpoint, retry_read=retry)
    record = result.safe_record(endpoint_type=endpoint_type)
    return record, result.body


def gate_failure_result(ctx: Context, started_at: str, started_monotonic: float, failure: GateFailure, fields: dict[str, Any]) -> int:
    payload = {
        "run_id": ctx.run_id,
        "gate_id": ctx.gate_id,
        "gate": ctx.gate_id,
        "status": "failed",
        "started_at": started_at,
        "duration_seconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
        "failed_stage": failure.stage,
        "failure_reason": failure.reason,
        "retryable": failure.retryable,
        "resume_safe": True,
        **fields,
    }
    write_result(ctx.gate_dir / "result.json", payload)
    return 2


def idle_light_sample(ctx: Context, client: HttpClient) -> dict[str, Any]:
    endpoints = {
        "progress": "/api/lite/security/progress",
        "runtime": "/api/lite/diagnostics/runtime",
        "workflow": "/api/workflows/status",
        "nats": "/api/nats/status",
        "health": "/health",
    }
    http: dict[str, Any] = {}
    bodies: dict[str, Any] = {}
    for name, endpoint in endpoints.items():
        record, body = endpoint_get(client, ctx.proxy_base_url, endpoint, endpoint_type=name)
        http[name] = record
        bodies[name] = body
    progress = normalized_progress(bodies.get("progress"))
    lifecycle = lifecycle_snapshot(ctx.db_path, run_id=str(progress.get("run_id") or ""))
    resources = resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir, include_log_sizes=False, include_scanners=False)
    consumer_ok, unhealthy = durable_consumers_healthy(bodies.get("nats"))
    return {
        "timestamp": utc_now(),
        "http": http,
        "progress": progress,
        "runtime": compact_runtime(bodies.get("runtime")),
        "workflow": bodies.get("workflow") if isinstance(bodies.get("workflow"), dict) else {},
        "nats": {
            key: bodies.get("nats", {}).get(key)
            for key in ("connected", "watchdog_running", "reconnect_pending", "published", "received", "transient_invalid_state_errors")
            if isinstance(bodies.get("nats"), dict) and key in bodies.get("nats", {})
        },
        "durable_consumers_healthy": consumer_ok,
        "unhealthy_consumers": unhealthy,
        "health": bodies.get("health") if isinstance(bodies.get("health"), dict) else {},
        "lifecycle": {
            "available": lifecycle.get("available"),
            "active_count": lifecycle.get("active_count"),
            "active_runs": lifecycle.get("active_runs", []),
            "latest_terminal": latest_terminal_run(ctx.db_path),
        },
        "resources": resources,
        "sanitized": True,
    }


def run_idle(args: argparse.Namespace) -> int:
    ctx = common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started_monotonic = time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    samples_path = ctx.gate_dir / "samples.jsonl"
    resources_path = ctx.gate_dir / "resources.jsonl"
    sqlite_path = ctx.gate_dir / "sqlite-checks.jsonl"
    events_path = ctx.gate_dir / "events.jsonl"
    duration = int(args.duration_seconds)
    interval = int(args.sample_interval_seconds)
    heavy_interval = int(args.heavy_check_interval_seconds)
    warmup = int(args.warmup_seconds)
    expected = max(1, math.floor(duration / interval) + 1)
    state = read_json(state_path, {})
    if state and state.get("gate_id") != ctx.gate_id:
        return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Idle resume state belongs to another gate.", stage="resume", retryable=False), {})
    if not state:
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "elapsed_active_seconds": 0.0,
            "samples_completed": 0,
            "heavy_checks_completed": 0,
            "light_sample_failures": 0,
            "started_at": started_at,
            "initial_pm2": pm2_snapshot(),
            "initial_resources": resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir, include_log_sizes=True, include_scanners=True),
            "sanitized": True,
        }
        atomic_write_json(state_path, state)
    segment_started = time.monotonic()
    next_sample_at = segment_started
    next_heavy_elapsed = (int(state.get("heavy_checks_completed") or 0) + 1) * heavy_interval
    samples: list[dict[str, Any]] = []
    if samples_path.exists():
        for line in samples_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    samples.append(item)
            except json.JSONDecodeError:
                return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Idle sample stream is inconsistent.", stage="resume", retryable=False), {})
    client = ctx.client()
    try:
        while float(state.get("elapsed_active_seconds") or 0.0) < duration:
            now = time.monotonic()
            if now < next_sample_at:
                time.sleep(min(0.25, next_sample_at - now))
                continue
            elapsed = float(state.get("elapsed_active_seconds") or 0.0) + max(0.0, now - segment_started)
            segment_started = now
            try:
                sample = idle_light_sample(ctx, client)
            except Exception as exc:  # bounded and recorded; repeated failure is evaluated below
                state["light_sample_failures"] = int(state.get("light_sample_failures") or 0) + 1
                sample = {"timestamp": utc_now(), "error_type": type(exc).__name__, "sanitized": True}
            sample["sample_index"] = int(state.get("samples_completed") or 0) + 1
            sample["elapsed_active_seconds"] = round(elapsed, 3)
            append_jsonl(samples_path, sample)
            if isinstance(sample.get("resources"), dict):
                append_jsonl(resources_path, sample["resources"])
            samples.append(sample)
            state["samples_completed"] = sample["sample_index"]
            state["elapsed_active_seconds"] = elapsed
            state["updated_at"] = utc_now()
            atomic_write_json(state_path, state)
            ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
            if elapsed >= next_heavy_elapsed:
                sqlite_check = run_sqlite_tools(ctx.repo_root, ctx.state_dir, ctx.db_path)
                sqlite_check["elapsed_active_seconds"] = round(elapsed, 3)
                append_jsonl(sqlite_path, sqlite_check)
                heavy_resource = resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir, include_log_sizes=True, include_scanners=True)
                append_jsonl(resources_path, heavy_resource)
                append_jsonl(
                    events_path,
                    {
                        "timestamp": utc_now(),
                        "event": "idle.heavy_check",
                        "quick_check": sqlite_check.get("quick_check"),
                        "parity_matched": sqlite_check.get("matched"),
                        "scanner_count": len(heavy_resource.get("scanner_processes") or []),
                        "sanitized": True,
                    },
                )
                state["heavy_checks_completed"] = int(state.get("heavy_checks_completed") or 0) + 1
                atomic_write_json(state_path, state)
                next_heavy_elapsed = (int(state["heavy_checks_completed"]) + 1) * heavy_interval
            next_sample_at = time.monotonic() + interval
    except KeyboardInterrupt:
        raise
    except GateFailure as failure:
        return gate_failure_result(ctx, started_at, started_monotonic, failure, {})

    final_sqlite = run_sqlite_tools(ctx.repo_root, ctx.state_dir, ctx.db_path)
    append_jsonl(sqlite_path, final_sqlite)
    final_resource = resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir, include_log_sizes=True, include_scanners=True)
    append_jsonl(resources_path, final_resource)
    current_pm2 = pm2_snapshot()
    restarts, exits = compare_pm2(state.get("initial_pm2", {}), current_pm2)
    warmup_samples = math.ceil(warmup / max(interval, 1))
    resource_samples = [item.get("resources", {}) for item in samples if isinstance(item.get("resources"), dict)]
    rss = [item.get("selected_rss_bytes") for item in resource_samples]
    cpu = [item.get("selected_cpu_percent") for item in resource_samples]
    fds = [item.get("selected_fd_count") for item in resource_samples]
    wal = [item.get("wal_bytes") for item in resource_samples]
    logs = [state.get("initial_resources", {}).get("log_bytes"), final_resource.get("log_bytes")]
    rss_trend = evaluate_sustained_growth(rss, warmup_samples=warmup_samples, budget=float(args.rss_budget_mb) * 1024 * 1024)
    cpu_trend = evaluate_sustained_growth(cpu, warmup_samples=warmup_samples, budget=float(args.cpu_growth_budget))
    fd_trend = evaluate_sustained_growth(fds, warmup_samples=warmup_samples, budget=float(args.fd_growth_budget))
    wal_trend = evaluate_sustained_growth(wal, warmup_samples=warmup_samples, budget=float(args.wal_budget_mb) * 1024 * 1024)
    log_growth = None
    valid_logs = [float(item) for item in logs if item is not None]
    if len(valid_logs) >= 2:
        log_growth = max(0.0, valid_logs[-1] - valid_logs[0])
    http_latencies = [
        float(record.get("time_total") or 0.0)
        for sample in samples
        for record in (sample.get("http") or {}).values()
        if isinstance(record, dict) and record.get("ok")
    ]
    http_failures = sum(
        1
        for sample in samples
        for record in (sample.get("http") or {}).values()
        if isinstance(record, dict) and not record.get("ok")
    )
    stale_active = [
        item
        for sample in samples
        for item in (sample.get("lifecycle", {}).get("active_runs") or [])
        if int(item.get("updated_at_epoch_ms") or 0) and epoch_ms() - int(item.get("updated_at_epoch_ms") or 0) > int(args.stale_active_seconds) * 1000
    ]
    unhealthy_consumer_events = sum(1 for sample in samples if sample.get("durable_consumers_healthy") is False)
    late_cpu = [float(item) for item in cpu[warmup_samples:] if item is not None]
    persistent_cpu = bool(late_cpu) and float(statistics.median(late_cpu[-max(1, len(late_cpu)//3):])) > float(args.cpu_idle_threshold)
    required_failures: list[str] = []
    minimum_samples = max(1, min(expected, int(args.minimum_samples)))
    if int(state.get("samples_completed") or 0) < minimum_samples:
        required_failures.append("missing_required_samples")
    if http_failures:
        required_failures.append("bounded_http_failures")
    if restarts:
        required_failures.append("unexpected_restarts")
    if exits:
        required_failures.append("process_exits")
    if stale_active:
        required_failures.append("stale_active_runs")
    if unhealthy_consumer_events:
        required_failures.append("durable_consumer_loss")
    if persistent_cpu:
        required_failures.append("persistent_idle_cpu")
    for name, trend in (("rss", rss_trend), ("fd", fd_trend), ("wal", wal_trend)):
        if trend.get("status") == "failed":
            required_failures.append(f"sustained_{name}_growth")
    if log_growth is not None and log_growth > float(args.log_growth_budget_mb) * 1024 * 1024:
        required_failures.append("log_growth_budget")
    if final_sqlite.get("quick_check") != "ok":
        required_failures.append("sqlite_quick_check")
    if final_sqlite.get("matched") is not True:
        required_failures.append("parity_mismatch")
    failure_reason = "" if not required_failures else "Idle stability requirements failed: " + ", ".join(required_failures)
    result = {
        "run_id": ctx.run_id,
        "gate_id": ctx.gate_id,
        "gate": ctx.gate_id,
        "status": "passed" if not required_failures else "failed",
        "started_at": state.get("started_at") or started_at,
        "duration_seconds": round(float(state.get("elapsed_active_seconds") or 0.0), 3),
        "samples_expected": expected,
        "samples_completed": int(state.get("samples_completed") or 0),
        "light_sample_failures": int(state.get("light_sample_failures") or 0),
        "heavy_checks_completed": int(state.get("heavy_checks_completed") or 0),
        "unexpected_restarts": restarts,
        "process_exits": exits,
        "stale_active_runs": len(stale_active),
        "rss_trend": rss_trend,
        "cpu_trend": cpu_trend,
        "fd_trend": fd_trend,
        "wal_trend": wal_trend,
        "log_growth": {"bytes": log_growth, "budget_bytes": float(args.log_growth_budget_mb) * 1024 * 1024, "status": "failed" if "log_growth_budget" in required_failures else "passed" if log_growth is not None else "unavailable"},
        "http_latency_summary": latency_summary(http_latencies),
        "http_failures": http_failures,
        "sqlite_quick_check": final_sqlite.get("quick_check"),
        "parity_matched": final_sqlite.get("matched"),
        "failed_stage": "evaluation" if required_failures else "",
        "failure_reason": failure_reason,
        "retryable": not bool(restarts or exits),
        "resume_safe": True,
        "sanitized": True,
        "evidence_refs": ["gates/idle/samples.jsonl", "gates/idle/resources.jsonl", "gates/idle/sqlite-checks.jsonl", "gates/idle/events.jsonl"],
    }
    write_result(ctx.gate_dir / "result.json", result)
    return 0 if not required_failures else 2


def wait_for_scanner_cleanup(timeout_seconds: int = 20) -> list[dict[str, Any]]:
    deadline = time.monotonic() + max(0, timeout_seconds)
    residue = scanner_inventory()
    while residue and time.monotonic() < deadline:
        time.sleep(1)
        residue = scanner_inventory()
    return residue


def submit_quick_scan(ctx: Context, client: HttpClient, logical_id: str, submission_timeout: float) -> tuple[HttpResult, dict[str, Any]]:
    submission_client = ctx.client(timeout=submission_timeout)
    result = submission_client.request(
        "POST",
        ctx.proxy_base_url,
        "/api/lite/security/check",
        body={"profile": "quick", "reason": f"phase5 {ctx.gate_id} {logical_id}"},
        retry_read=False,
    )
    payload = result.body or {}
    return result, payload


def progress_sample(ctx: Context, client: HttpClient, *, base_url: str | None = None, endpoint_type: str = "proxy") -> tuple[dict[str, Any], HttpResult]:
    result = client.request("GET", base_url or ctx.proxy_base_url, "/api/lite/security/progress", retry_read=True)
    record = result.safe_record(endpoint_type=endpoint_type)
    progress = normalized_progress(result.body)
    record.update(progress)
    return record, result


def run_repeated_scans(args: argparse.Namespace) -> int:
    ctx = common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started_monotonic = time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    runs_path = ctx.gate_dir / "runs.jsonl"
    progress_path = ctx.gate_dir / "progress.jsonl"
    resources_path = ctx.gate_dir / "resources.jsonl"
    sqlite_path = ctx.gate_dir / "sqlite-checks.jsonl"
    events_path = ctx.gate_dir / "events.jsonl"
    count = int(args.count)
    state = read_json(state_path, {})
    if state and state.get("gate_id") != ctx.gate_id:
        return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Repeated-scan resume state belongs to another gate.", stage="resume", retryable=False), {})
    if not state:
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "next_index": 1,
            "completed_scan_count": 0,
            "tracked_run_id": "",
            "logical_submission_id": "",
            "submission_started": False,
            "submission_attempt": 0,
            "initial_resources": resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir),
            "initial_pm2": pm2_snapshot(),
            "started_at": started_at,
            "sanitized": True,
        }
        atomic_write_json(state_path, state)
    client = ctx.client()
    infrastructure_failures: list[str] = []
    duplicate_runs = 0
    stale_active_runs = 0
    active_key_leaks = 0
    scanner_residue_events = 0
    terminal_success_count = 0
    terminal_non_success_count = 0
    execution_durations: list[float] = []
    submission_latencies: list[float] = []
    all_progress: list[dict[str, Any]] = []
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    all_progress.append(item)
            except json.JSONDecodeError:
                return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Repeated-scan Progress evidence is inconsistent.", stage="resume", retryable=False), {})
    if runs_path.exists():
        for line in runs_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Repeated-scan run evidence is inconsistent.", stage="resume", retryable=False), {})
            if not isinstance(item, dict):
                continue
            if str(item.get("terminal_status") or "") in TERMINAL_SUCCESS_STATUSES:
                terminal_success_count += 1
            else:
                terminal_non_success_count += 1
            if item.get("execution_duration_seconds") is not None:
                execution_durations.append(float(item["execution_duration_seconds"]))
            if item.get("submission_latency_seconds") is not None:
                submission_latencies.append(float(item["submission_latency_seconds"]))
    try:
        while int(state.get("next_index") or 1) <= count:
            index = int(state.get("next_index") or 1)
            lifecycle = lifecycle_snapshot(ctx.db_path, run_id=str(state.get("tracked_run_id") or ""))
            decision = resume_scan_decision(state, lifecycle.get("run") or {})
            if decision == "ambiguous":
                raise GateFailure("Resume state is ambiguous; no replacement scan was submitted.", stage="resume", retryable=False)
            if decision == "submit":
                active_count = lifecycle.get("active_count")
                if active_count not in (0, None):
                    raise GateFailure("A Security run was already active before sequential submission.", stage="pre-submit", retryable=True)
                logical_id = f"scan-{index:03d}-{uuid.uuid4().hex[:8]}"
                state.update({
                    "logical_submission_id": logical_id,
                    "submission_started": True,
                    "submission_attempt": int(state.get("submission_attempt") or 0) + 1,
                    "tracked_run_id": "",
                    "updated_at": utc_now(),
                })
                atomic_write_json(state_path, state)
                submitted_at = utc_now()
                result, payload = submit_quick_scan(ctx, client, logical_id, float(args.submission_timeout_seconds))
                submission_latencies.append(result.time_total)
                if not result.ok or result.status_code != 202:
                    raise GateFailure("Quick scan submission did not receive an unambiguous HTTP 202 response.", stage="submission", retryable=False)
                run_id = str(payload.get("run_id") or "")
                if not run_id:
                    raise GateFailure("Accepted Quick scan submission did not return a run ID.", stage="submission", retryable=False)
                if payload.get("deduplicated") is True:
                    duplicate_runs += 1
                    raise GateFailure("Quick scan submission was deduplicated against an existing run.", stage="submission", retryable=False)
                state.update({"tracked_run_id": run_id, "submitted_at": submitted_at, "submission_payload_status": payload.get("status"), "updated_at": utc_now()})
                atomic_write_json(state_path, state)
                append_jsonl(events_path, {"timestamp": utc_now(), "event": "scan.submitted", "index": index, "logical_submission_id": logical_id, "run_id": run_id, "submission_latency_seconds": round(result.time_total, 4), "sanitized": True})
                decision = "monitor"
            tracked_run_id = str(state.get("tracked_run_id") or "")
            if decision == "finalize":
                decision = "monitor"
            if decision == "monitor":
                deadline = time.monotonic() + int(args.run_timeout_seconds)
                terminal_progress: dict[str, Any] | None = None
                while time.monotonic() <= deadline:
                    record, _ = progress_sample(ctx, client)
                    record["logical_submission_id"] = state.get("logical_submission_id")
                    record["scan_index"] = index
                    append_jsonl(progress_path, record)
                    all_progress.append(record)
                    if not record.get("ok"):
                        infrastructure_failures.append(f"progress_http_failure_scan_{index}")
                    run_id = str(record.get("run_id") or "")
                    if run_id and run_id != tracked_run_id:
                        # A brief old/new projection race is allowed only before the tracked run appears.
                        tracked_lifecycle = lifecycle_snapshot(ctx.db_path, run_id=tracked_run_id).get("run")
                        if tracked_lifecycle and str(tracked_lifecycle.get("status") or "").lower() in TERMINAL_STATUSES:
                            terminal_progress = {**record, **tracked_lifecycle, "run_id": tracked_run_id}
                            break
                    status = str(record.get("status") or "").lower()
                    if run_id == tracked_run_id and status in TERMINAL_STATUSES:
                        terminal_progress = record
                        break
                    tracked_lifecycle = lifecycle_snapshot(ctx.db_path, run_id=tracked_run_id).get("run")
                    if tracked_lifecycle and str(tracked_lifecycle.get("status") or "").lower() in TERMINAL_STATUSES:
                        terminal_progress = {**record, **tracked_lifecycle, "run_id": tracked_run_id}
                        break
                    state["updated_at"] = utc_now()
                    atomic_write_json(state_path, state)
                    ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
                    time.sleep(float(args.progress_sample_interval_seconds))
                if terminal_progress is None:
                    raise GateFailure(f"Quick scan {index} did not reach terminal state within the configured timeout.", stage="monitor", retryable=True)
                lifecycle = lifecycle_snapshot(ctx.db_path, run_id=tracked_run_id)
                run = lifecycle.get("run") or terminal_progress
                status = str(run.get("status") or terminal_progress.get("status") or "").lower()
                if status in TERMINAL_SUCCESS_STATUSES:
                    terminal_success_count += 1
                else:
                    terminal_non_success_count += 1
                    infrastructure_failures.append(f"terminal_status_{status or 'unknown'}_scan_{index}")
                if run.get("active_key") not in (None, ""):
                    active_key_leaks += 1
                    infrastructure_failures.append(f"active_key_leak_scan_{index}")
                active_count = lifecycle.get("active_count")
                if active_count not in (0, None):
                    stale_active_runs += int(active_count or 0)
                    infrastructure_failures.append(f"active_run_remained_scan_{index}")
                if status in TERMINAL_SUCCESS_STATUSES and run.get("evidence_saved") not in (1, True):
                    infrastructure_failures.append(f"execution_evidence_missing_scan_{index}")
                residue = wait_for_scanner_cleanup(int(args.scanner_cleanup_timeout_seconds))
                if residue:
                    scanner_residue_events += 1
                    infrastructure_failures.append(f"scanner_residue_scan_{index}")
                nats_result = client.request("GET", ctx.proxy_base_url, "/api/nats/status", retry_read=True)
                consumer_ok, unhealthy_consumers = durable_consumers_healthy(nats_result.body)
                append_jsonl(events_path, {"timestamp": utc_now(), "event": "scan.post_run_health", "scan_index": index, "run_id": tracked_run_id, "durable_consumers_healthy": consumer_ok, "unhealthy_consumers": unhealthy_consumers, "sanitized": True})
                if not nats_result.ok:
                    infrastructure_failures.append(f"nats_status_failure_scan_{index}")
                if consumer_ok is False:
                    infrastructure_failures.append(f"durable_consumer_unhealthy_scan_{index}")
                requested_ms = int(run.get("requested_at_epoch_ms") or 0)
                completed_ms = int(run.get("completed_at_epoch_ms") or 0)
                duration_seconds = (completed_ms - requested_ms) / 1000 if requested_ms and completed_ms >= requested_ms else None
                if duration_seconds is not None:
                    execution_durations.append(duration_seconds)
                run_record = {
                    "timestamp": utc_now(),
                    "scan_index": index,
                    "logical_submission_id": state.get("logical_submission_id"),
                    "submission_attempt": state.get("submission_attempt"),
                    "run_id": tracked_run_id,
                    "job_id": terminal_progress.get("job_id"),
                    "command_id": run.get("command_id") or terminal_progress.get("command_id"),
                    "submission_status": state.get("submission_payload_status"),
                    "deduplicated": False,
                    "submission_latency_seconds": round(submission_latencies[-1], 4) if submission_latencies else None,
                    "requested_at": run.get("requested_at"),
                    "command_published_at": run.get("command_published_at"),
                    "command_received_at": run.get("command_received_at"),
                    "execution_started_at": run.get("execution_started_at") or run.get("started_at"),
                    "last_progress_at": run.get("last_progress_at"),
                    "completed_at": run.get("completed_at"),
                    "delivery_attempt": run.get("delivery_attempt"),
                    "terminal_status": status,
                    "finding_counts": {key: run.get(key) for key in ("critical_count", "high_count", "medium_count", "low_count", "info_count")},
                    "evidence_saved": bool(run.get("evidence_saved")),
                    "active_key_cleared": run.get("active_key") in (None, ""),
                    "execution_duration_seconds": duration_seconds,
                    "scanner_residue": residue,
                    "sanitized": True,
                }
                append_jsonl(runs_path, run_record)
                state.update({
                    "completed_scan_count": int(state.get("completed_scan_count") or 0) + 1,
                    "next_index": index + 1,
                    "tracked_run_id": "",
                    "logical_submission_id": "",
                    "submission_started": False,
                    "submission_payload_status": "",
                    "updated_at": utc_now(),
                })
                atomic_write_json(state_path, state)
                if index % int(args.resource_sample_every) == 0:
                    append_jsonl(resources_path, resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir))
                if index % int(args.parity_every) == 0:
                    check = run_sqlite_tools(ctx.repo_root, ctx.state_dir, ctx.db_path)
                    check["scan_index"] = index
                    append_jsonl(sqlite_path, check)
                    if check.get("quick_check") != "ok" or check.get("matched") is not True:
                        infrastructure_failures.append(f"sqlite_or_parity_scan_{index}")
                ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
                if infrastructure_failures and bool(args.stop_on_first_failure):
                    break
                if int(state.get("next_index") or 1) <= count:
                    time.sleep(int(args.cooldown_seconds))
    except GateFailure as failure:
        fields = {
            "requested_scan_count": count,
            "completed_scan_count": int(state.get("completed_scan_count") or 0),
            "infrastructure_failures": sorted(set(infrastructure_failures + [failure.stage])),
            "duplicate_runs": duplicate_runs,
            "stale_active_runs": stale_active_runs,
            "active_key_leaks": active_key_leaks,
            "scanner_residue_events": scanner_residue_events,
            "sanitized": True,
        }
        return gate_failure_result(ctx, started_at, started_monotonic, failure, fields)

    final_sqlite = run_sqlite_tools(ctx.repo_root, ctx.state_dir, ctx.db_path)
    current_pm2 = pm2_snapshot()
    restarts, exits = compare_pm2(state.get("initial_pm2", {}), current_pm2)
    if restarts:
        infrastructure_failures.append("unexpected_restarts")
    if exits:
        infrastructure_failures.append("process_exits")
    regressions = progress_regressions(all_progress)
    if regressions:
        infrastructure_failures.append("progress_regressions")
    if final_sqlite.get("quick_check") != "ok":
        infrastructure_failures.append("sqlite_quick_check")
    if final_sqlite.get("matched") is not True:
        infrastructure_failures.append("parity_mismatch")
    completed = int(state.get("completed_scan_count") or 0)
    if completed != count:
        infrastructure_failures.append("incomplete_scan_count")
    final_resources = resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir)
    initial_resources = state.get("initial_resources", {})
    growth = {
        key: int(final_resources.get(key) or 0) - int(initial_resources.get(key) or 0)
        for key in ("db_bytes", "wal_bytes", "log_bytes", "evidence_bytes")
        if final_resources.get(key) is not None and initial_resources.get(key) is not None
    }
    growth_budgets = {
        "db_bytes": int(float(args.db_growth_budget_mb) * 1024 * 1024),
        "wal_bytes": int(float(args.wal_growth_budget_mb) * 1024 * 1024),
        "log_bytes": int(float(args.log_growth_budget_mb) * 1024 * 1024),
    }
    for key, budget in growth_budgets.items():
        if growth.get(key, 0) > budget:
            infrastructure_failures.append(f"{key}_growth_budget")
    failures = sorted(set(infrastructure_failures))
    failure_reason = "" if not failures else "Repeated Quick scan requirements failed: " + ", ".join(failures)
    result = {
        "run_id": ctx.run_id,
        "gate_id": ctx.gate_id,
        "gate": ctx.gate_id,
        "status": "passed" if not failures else "failed",
        "started_at": state.get("started_at") or started_at,
        "duration_seconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
        "requested_scan_count": count,
        "completed_scan_count": completed,
        "terminal_success_count": terminal_success_count if terminal_success_count else completed - terminal_non_success_count,
        "terminal_non_success_count": terminal_non_success_count,
        "infrastructure_failures": failures,
        "duplicate_runs": duplicate_runs,
        "stale_active_runs": stale_active_runs,
        "active_key_leaks": active_key_leaks,
        "scanner_residue_events": scanner_residue_events,
        "unexpected_restarts": restarts,
        "process_exits": exits,
        "progress_regressions": regressions,
        "submission_latency": latency_summary(submission_latencies),
        "latency_trend": compare_latency_groups(execution_durations),
        "db_growth": {"bytes": growth.get("db_bytes"), "budget_bytes": growth_budgets["db_bytes"]},
        "wal_growth": {"bytes": growth.get("wal_bytes"), "budget_bytes": growth_budgets["wal_bytes"]},
        "log_growth": {"bytes": growth.get("log_bytes"), "budget_bytes": growth_budgets["log_bytes"]},
        "parity_matched": final_sqlite.get("matched"),
        "sqlite_quick_check": final_sqlite.get("quick_check"),
        "failed_stage": "evaluation" if failures else "",
        "failure_reason": failure_reason,
        "retryable": not bool(restarts or exits or duplicate_runs),
        "resume_safe": True,
        "sanitized": True,
        "evidence_refs": ["gates/repeated-scans/runs.jsonl", "gates/repeated-scans/progress.jsonl", "gates/repeated-scans/resources.jsonl", "gates/repeated-scans/sqlite-checks.jsonl", "gates/repeated-scans/events.jsonl"],
    }
    write_result(ctx.gate_dir / "result.json", result)
    return 0 if not failures else 2


def etag_check(client: HttpClient, base_url: str, etag: str, prior: dict[str, Any], endpoint_type: str) -> dict[str, Any]:
    result = client.request("GET", base_url, "/api/lite/security/progress", etag=etag, retry_read=False)
    current = normalized_progress(result.body)
    valid = False
    behavior = ""
    if result.status_code == 304:
        valid = bool(etag)
        behavior = "not_modified"
    elif result.status_code == 200:
        changed = (
            str(result.etag or "") != str(etag or "")
            or current.get("revision") != prior.get("revision")
            or current.get("run_revision") != prior.get("run_revision")
            or current.get("percent") != prior.get("percent")
            or current.get("status") != prior.get("status")
        )
        valid = bool(changed)
        behavior = "changed" if changed else "etag_not_honored"
    else:
        behavior = result.error_type or "http_failure"
    return {
        "timestamp": utc_now(),
        "endpoint_type": endpoint_type,
        "request_etag_present": bool(etag),
        "response_etag": result.etag,
        "http_status": result.status_code,
        "behavior": behavior,
        "valid": valid,
        "prior_revision": prior.get("revision"),
        "current_revision": current.get("revision"),
        "sanitized": True,
    }


def run_progress_soak(args: argparse.Namespace) -> int:
    ctx = common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started_monotonic = time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    direct_path = ctx.gate_dir / "direct-samples.jsonl"
    proxy_path = ctx.gate_dir / "proxy-samples.jsonl"
    paired_path = ctx.gate_dir / "paired-samples.jsonl"
    etag_path = ctx.gate_dir / "etag-checks.jsonl"
    resources_path = ctx.gate_dir / "resources.jsonl"
    events_path = ctx.gate_dir / "events.jsonl"
    scan_count = int(args.scan_count)
    interval_ms = int(args.sample_interval_ms)
    if interval_ms < MIN_PROGRESS_SAMPLE_INTERVAL_MS:
        return gate_failure_result(ctx, started_at, started_monotonic, GateFailure(f"Progress sample interval must be at least {MIN_PROGRESS_SAMPLE_INTERVAL_MS} ms.", stage="configuration", retryable=False), {})
    state = read_json(state_path, {})
    if state and state.get("gate_id") != ctx.gate_id:
        return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Progress-soak resume state belongs to another gate.", stage="resume", retryable=False), {})
    if not state:
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "next_scan_index": 1,
            "completed_scan_count": 0,
            "tracked_run_id": "",
            "logical_submission_id": "",
            "submission_started": False,
            "sample_count": 0,
            "direct_etag": "",
            "proxy_etag": "",
            "started_at": started_at,
            "initial_pm2": pm2_snapshot(),
            "sanitized": True,
        }
        atomic_write_json(state_path, state)
    client = ctx.client(timeout=max(ctx.http_timeout, float(args.max_budget_seconds) + 1.0))
    direct_latencies: list[float] = []
    proxy_latencies: list[float] = []
    direct_failures = 0
    proxy_failures = 0
    over_five = 0
    projection_violations = 0
    regressions: list[dict[str, Any]] = []
    etag_checks = 0
    etag_failures = 0
    mismatches = 0
    read_degraded = 0
    critical_stalls = 0
    samples_by_endpoint: dict[str, list[dict[str, Any]]] = {"direct": [], "proxy": []}
    for endpoint_type, path in (("direct", direct_path), ("proxy", proxy_path)):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Progress-soak sample evidence is inconsistent.", stage="resume", retryable=False), {})
            if isinstance(item, dict):
                samples_by_endpoint[endpoint_type].append(item)
                if item.get("ok"):
                    (direct_latencies if endpoint_type == "direct" else proxy_latencies).append(float(item.get("time_total") or 0.0))
                else:
                    if endpoint_type == "direct": direct_failures += 1
                    else: proxy_failures += 1
                if float(item.get("time_total") or 0.0) > 5:
                    over_five += 1
                if item.get("read_degraded") is True:
                    read_degraded += 1
    if etag_path.exists():
        for line in etag_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                return gate_failure_result(ctx, started_at, started_monotonic, GateFailure("Progress-soak ETag evidence is inconsistent.", stage="resume", retryable=False), {})
            if isinstance(item, dict):
                etag_checks += 1
                if not item.get("valid"): etag_failures += 1
    try:
        while int(state.get("next_scan_index") or 1) <= scan_count:
            index = int(state.get("next_scan_index") or 1)
            lifecycle = lifecycle_snapshot(ctx.db_path, run_id=str(state.get("tracked_run_id") or ""))
            decision = resume_scan_decision(state, lifecycle.get("run") or {})
            if decision == "ambiguous":
                raise GateFailure("Progress soak resume state is ambiguous; no replacement scan was submitted.", stage="resume", retryable=False)
            if decision == "submit":
                if lifecycle.get("active_count") not in (0, None):
                    raise GateFailure("A Security run was active before Progress soak submission.", stage="pre-submit", retryable=True)
                logical_id = f"progress-{index:03d}-{uuid.uuid4().hex[:8]}"
                state.update({"logical_submission_id": logical_id, "submission_started": True, "tracked_run_id": "", "updated_at": utc_now()})
                atomic_write_json(state_path, state)
                submission, payload = submit_quick_scan(ctx, client, logical_id, float(args.submission_timeout_seconds))
                if not submission.ok or submission.status_code != 202 or payload.get("deduplicated") is True:
                    raise GateFailure("Progress soak scan submission was not an unambiguous new HTTP 202 run.", stage="submission", retryable=False)
                tracked = str(payload.get("run_id") or "")
                if not tracked:
                    raise GateFailure("Progress soak submission did not return a run ID.", stage="submission", retryable=False)
                state.update({"tracked_run_id": tracked, "updated_at": utc_now()})
                atomic_write_json(state_path, state)
                append_jsonl(events_path, {"timestamp": utc_now(), "event": "progress_soak.scan_submitted", "scan_index": index, "logical_submission_id": logical_id, "run_id": tracked, "sanitized": True})
            tracked = str(state.get("tracked_run_id") or "")
            deadline = time.monotonic() + int(args.run_timeout_seconds)
            mismatch_streak = 0
            while time.monotonic() <= deadline:
                cycle_started = time.monotonic()
                direct_record, direct_result = progress_sample(ctx, client, base_url=ctx.direct_base_url, endpoint_type="direct")
                proxy_record, proxy_result = progress_sample(ctx, client, base_url=ctx.proxy_base_url, endpoint_type="proxy")
                for record in (direct_record, proxy_record):
                    record["scan_index"] = index
                    record["tracked_run_id"] = tracked
                append_jsonl(direct_path, direct_record)
                append_jsonl(proxy_path, proxy_record)
                samples_by_endpoint["direct"].append(direct_record)
                samples_by_endpoint["proxy"].append(proxy_record)
                state["sample_count"] = int(state.get("sample_count") or 0) + 1
                if direct_result.ok:
                    direct_latencies.append(direct_result.time_total)
                else:
                    direct_failures += 1
                if proxy_result.ok:
                    proxy_latencies.append(proxy_result.time_total)
                else:
                    proxy_failures += 1
                if direct_result.time_total > 5 or proxy_result.time_total > 5:
                    over_five += int(direct_result.time_total > 5) + int(proxy_result.time_total > 5)
                for record in (direct_record, proxy_record):
                    age = record.get("projection_age_ms")
                    status = str(record.get("status") or "")
                    if status in ACTIVE_STATUSES:
                        if age is None:
                            projection_violations += 1
                        else:
                            try:
                                if float(age) > float(args.max_projection_age_ms):
                                    projection_violations += 1
                            except (TypeError, ValueError):
                                projection_violations += 1
                    if record.get("read_degraded") is True:
                        read_degraded += 1
                consistent, consistency_reason = direct_proxy_consistent(direct_record, proxy_record, target_run_id=tracked)
                if consistent:
                    mismatch_streak = 0
                else:
                    mismatch_streak += 1
                    if mismatch_streak > int(args.race_tolerance_samples):
                        mismatches += 1
                pair = {
                    "timestamp": utc_now(),
                    "scan_index": index,
                    "tracked_run_id": tracked,
                    "direct": {key: direct_record.get(key) for key in ("http_status", "time_starttransfer", "time_total", "etag", "run_id", "status", "stage", "percent", "revision", "run_revision", "projection_age_ms", "read_degraded", "storage_backend", "projection_source")},
                    "proxy": {key: proxy_record.get(key) for key in ("http_status", "time_starttransfer", "time_total", "etag", "run_id", "status", "stage", "percent", "revision", "run_revision", "projection_age_ms", "read_degraded", "storage_backend", "projection_source")},
                    "consistent": consistent,
                    "consistency_reason": consistency_reason,
                    "mismatch_streak": mismatch_streak,
                    "sanitized": True,
                }
                append_jsonl(paired_path, pair)
                if direct_result.etag:
                    state["direct_etag"] = direct_result.etag
                if proxy_result.etag:
                    state["proxy_etag"] = proxy_result.etag
                if int(state["sample_count"]) % int(args.etag_check_every) == 0:
                    for endpoint_type, base_url, etag_value, prior in (
                        ("direct", ctx.direct_base_url, state.get("direct_etag", ""), direct_record),
                        ("proxy", ctx.proxy_base_url, state.get("proxy_etag", ""), proxy_record),
                    ):
                        check = etag_check(client, base_url, str(etag_value or ""), prior, endpoint_type)
                        append_jsonl(etag_path, check)
                        etag_checks += 1
                        if not check.get("valid"):
                            etag_failures += 1
                if int(state["sample_count"]) % int(args.resource_sample_every) == 0:
                    resource = resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir, include_log_sizes=False, include_scanners=False)
                    runtime_result = client.request("GET", ctx.proxy_base_url, "/api/lite/diagnostics/runtime", retry_read=True)
                    runtime = compact_runtime(runtime_result.body)
                    lag_values = numeric_values(runtime.get("event_loop", {}), key_pattern=re.compile(r"(?i)(lag|delay).*(?:ms|millisecond)?"))
                    if lag_values and max(lag_values) > float(args.critical_event_loop_stall_ms):
                        critical_stalls += 1
                    resource["event_loop"] = runtime.get("event_loop", {})
                    append_jsonl(resources_path, resource)
                regressions = progress_regressions(samples_by_endpoint["direct"]) + progress_regressions(samples_by_endpoint["proxy"])
                if regressions:
                    raise GateFailure("Progress regressed for the tracked run.", stage="sampling", retryable=False)
                state["updated_at"] = utc_now()
                atomic_write_json(state_path, state)
                ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
                statuses = {str(direct_record.get("status") or ""), str(proxy_record.get("status") or "")}
                run_ids = {str(direct_record.get("run_id") or ""), str(proxy_record.get("run_id") or "")}
                lifecycle_run = lifecycle_snapshot(ctx.db_path, run_id=tracked).get("run") or {}
                lifecycle_status = str(lifecycle_run.get("status") or "").lower()
                if tracked in run_ids and any(item in TERMINAL_STATUSES for item in statuses):
                    break
                if lifecycle_status in TERMINAL_STATUSES:
                    break
                elapsed = time.monotonic() - cycle_started
                sleep_seconds = max(0.0, interval_ms / 1000 - elapsed)
                if sleep_seconds:
                    time.sleep(sleep_seconds)
            else:
                raise GateFailure("Progress soak scan did not reach terminal state within the configured timeout.", stage="sampling", retryable=True)
            lifecycle = lifecycle_snapshot(ctx.db_path, run_id=tracked)
            run = lifecycle.get("run") or {}
            if str(run.get("status") or "").lower() not in TERMINAL_SUCCESS_STATUSES:
                raise GateFailure("Progress soak tracked scan ended with an infrastructure failure status.", stage="terminal", retryable=True)
            if run.get("active_key") not in (None, "") or lifecycle.get("active_count") not in (0, None):
                raise GateFailure("Progress soak terminal run retained an active key.", stage="terminal", retryable=False)
            residue = wait_for_scanner_cleanup(20)
            if residue:
                raise GateFailure("Progress soak left scanner process residue after terminal state.", stage="terminal", retryable=True)
            state.update({
                "completed_scan_count": int(state.get("completed_scan_count") or 0) + 1,
                "next_scan_index": index + 1,
                "tracked_run_id": "",
                "logical_submission_id": "",
                "submission_started": False,
                "updated_at": utc_now(),
            })
            atomic_write_json(state_path, state)
    except GateFailure as failure:
        fields = {
            "scan_count": scan_count,
            "sample_interval_ms": interval_ms,
            "direct_request_count": len(samples_by_endpoint["direct"]),
            "proxy_request_count": len(samples_by_endpoint["proxy"]),
            "direct_failures": direct_failures,
            "proxy_failures": proxy_failures,
            "progress_regressions": regressions,
            "etag_checks": etag_checks,
            "etag_failures": etag_failures,
            "direct_proxy_mismatches": mismatches,
            "read_degraded_count": read_degraded,
            "sanitized": True,
        }
        return gate_failure_result(ctx, started_at, started_monotonic, failure, fields)

    final_sqlite = run_sqlite_tools(ctx.repo_root, ctx.state_dir, ctx.db_path)
    current_pm2 = pm2_snapshot()
    restarts, exits = compare_pm2(state.get("initial_pm2", {}), current_pm2)
    direct_summary = latency_summary(direct_latencies)
    proxy_summary = latency_summary(proxy_latencies)
    failures: list[str] = []
    if direct_failures:
        failures.append("direct_http_failures")
    if proxy_failures:
        failures.append("proxy_http_failures")
    if (direct_summary.get("p95") or 0) >= float(args.p95_budget_seconds):
        failures.append("direct_p95_budget")
    if (proxy_summary.get("p95") or 0) >= float(args.p95_budget_seconds):
        failures.append("proxy_p95_budget")
    if (direct_summary.get("max") or 0) >= float(args.max_budget_seconds):
        failures.append("direct_max_budget")
    if (proxy_summary.get("max") or 0) >= float(args.max_budget_seconds):
        failures.append("proxy_max_budget")
    if over_five:
        failures.append("requests_over_five_seconds")
    if projection_violations:
        failures.append("projection_age_violations")
    if regressions:
        failures.append("progress_regressions")
    if etag_failures:
        failures.append("etag_failures")
    if mismatches:
        failures.append("direct_proxy_mismatches")
    if read_degraded:
        failures.append("read_degraded")
    if critical_stalls:
        failures.append("critical_event_loop_stalls")
    if restarts:
        failures.append("unexpected_restarts")
    if exits:
        failures.append("process_exits")
    if int(state.get("completed_scan_count") or 0) != scan_count:
        failures.append("incomplete_scan_count")
    if final_sqlite.get("quick_check") != "ok":
        failures.append("sqlite_quick_check")
    if final_sqlite.get("matched") is not True:
        failures.append("parity_mismatch")
    failures = sorted(set(failures))
    failure_reason = "" if not failures else "Active Progress soak requirements failed: " + ", ".join(failures)
    result = {
        "run_id": ctx.run_id,
        "gate_id": ctx.gate_id,
        "gate": ctx.gate_id,
        "status": "passed" if not failures else "failed",
        "started_at": state.get("started_at") or started_at,
        "duration_seconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
        "scan_count": scan_count,
        "completed_scan_count": int(state.get("completed_scan_count") or 0),
        "sample_interval_ms": interval_ms,
        "direct_request_count": len(samples_by_endpoint["direct"]),
        "proxy_request_count": len(samples_by_endpoint["proxy"]),
        "direct_failures": direct_failures,
        "proxy_failures": proxy_failures,
        "direct_latency": direct_summary,
        "proxy_latency": proxy_summary,
        "requests_over_5_seconds": over_five,
        "projection_age_violations": projection_violations,
        "progress_regressions": regressions,
        "etag_checks": etag_checks,
        "etag_failures": etag_failures,
        "direct_proxy_mismatches": mismatches,
        "read_degraded_count": read_degraded,
        "critical_event_loop_stalls": critical_stalls,
        "unexpected_restarts": restarts,
        "process_exits": exits,
        "sqlite_quick_check": final_sqlite.get("quick_check"),
        "parity_matched": final_sqlite.get("matched"),
        "failed_stage": "evaluation" if failures else "",
        "failure_reason": failure_reason,
        "retryable": not bool(restarts or exits),
        "resume_safe": True,
        "sanitized": True,
        "evidence_refs": ["gates/progress-soak/direct-samples.jsonl", "gates/progress-soak/proxy-samples.jsonl", "gates/progress-soak/paired-samples.jsonl", "gates/progress-soak/etag-checks.jsonl", "gates/progress-soak/resources.jsonl", "gates/progress-soak/events.jsonl"],
    }
    write_result(ctx.gate_dir / "result.json", result)
    return 0 if not failures else 2


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--proxy-base-url", required=True)
    parser.add_argument("--direct-base-url", required=True)
    parser.add_argument("--connect-timeout", type=float, default=2.0)
    parser.add_argument("--http-timeout", type=float, default=5.0)
    parser.add_argument("--report-limit-bytes", type=int, default=DEFAULT_REPORT_LIMIT_BYTES)
    parser.add_argument("--resume", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    idle = sub.add_parser("idle")
    add_common(idle)
    idle.add_argument("--duration-seconds", type=int, required=True)
    idle.add_argument("--sample-interval-seconds", type=int, required=True)
    idle.add_argument("--heavy-check-interval-seconds", type=int, required=True)
    idle.add_argument("--warmup-seconds", type=int, required=True)
    idle.add_argument("--rss-budget-mb", type=float, required=True)
    idle.add_argument("--wal-budget-mb", type=float, required=True)
    idle.add_argument("--log-growth-budget-mb", type=float, required=True)
    idle.add_argument("--fd-growth-budget", type=float, required=True)
    idle.add_argument("--cpu-idle-threshold", type=float, required=True)
    idle.add_argument("--cpu-growth-budget", type=float, default=10.0)
    idle.add_argument("--stale-active-seconds", type=int, default=300)
    idle.add_argument("--minimum-samples", type=int, default=3)

    repeated = sub.add_parser("repeated-scans")
    add_common(repeated)
    repeated.add_argument("--count", type=int, required=True)
    repeated.add_argument("--cooldown-seconds", type=int, required=True)
    repeated.add_argument("--run-timeout-seconds", type=int, required=True)
    repeated.add_argument("--submission-timeout-seconds", type=float, required=True)
    repeated.add_argument("--parity-every", type=int, required=True)
    repeated.add_argument("--resource-sample-every", type=int, required=True)
    repeated.add_argument("--stop-on-first-failure", type=int, choices=(0, 1), required=True)
    repeated.add_argument("--progress-sample-interval-seconds", type=float, default=2.0)
    repeated.add_argument("--scanner-cleanup-timeout-seconds", type=int, default=20)
    repeated.add_argument("--db-growth-budget-mb", type=float, default=64.0)
    repeated.add_argument("--wal-growth-budget-mb", type=float, default=64.0)
    repeated.add_argument("--log-growth-budget-mb", type=float, default=128.0)

    progress = sub.add_parser("progress-soak")
    add_common(progress)
    progress.add_argument("--scan-count", type=int, required=True)
    progress.add_argument("--sample-interval-ms", type=int, required=True)
    progress.add_argument("--run-timeout-seconds", type=int, required=True)
    progress.add_argument("--submission-timeout-seconds", type=float, required=True)
    progress.add_argument("--etag-check-every", type=int, required=True)
    progress.add_argument("--max-projection-age-ms", type=float, required=True)
    progress.add_argument("--p95-budget-seconds", type=float, required=True)
    progress.add_argument("--max-budget-seconds", type=float, required=True)
    progress.add_argument("--race-tolerance-samples", type=int, default=2)
    progress.add_argument("--resource-sample-every", type=int, default=20)
    progress.add_argument("--critical-event-loop-stall-ms", type=float, default=1000.0)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.report_limit_bytes < 1024 * 1024:
        raise ValueError("report limit must be at least 1 MiB")
    if args.command == "idle":
        if args.duration_seconds < 1 or args.sample_interval_seconds < 1 or args.heavy_check_interval_seconds < 1:
            raise ValueError("idle durations and intervals must be positive")
        if args.heavy_check_interval_seconds < args.sample_interval_seconds:
            raise ValueError("heavy check interval cannot be shorter than the light sample interval")
        if args.warmup_seconds < 0 or args.warmup_seconds >= args.duration_seconds:
            raise ValueError("idle warm-up must be non-negative and shorter than the duration")
    elif args.command == "repeated-scans":
        if args.count < 1 or args.cooldown_seconds < 0 or args.run_timeout_seconds < 1:
            raise ValueError("scan count and timeout must be positive and cooldown non-negative")
        if args.parity_every < 1 or args.resource_sample_every < 1:
            raise ValueError("repeated-scan sampling intervals must be positive")
    elif args.command == "progress-soak":
        if args.scan_count < 1 or args.run_timeout_seconds < 1:
            raise ValueError("Progress soak scan count and timeout must be positive")
        if args.sample_interval_ms < MIN_PROGRESS_SAMPLE_INTERVAL_MS:
            raise ValueError(f"sample interval must be at least {MIN_PROGRESS_SAMPLE_INTERVAL_MS} ms")
        if args.etag_check_every < 1 or args.resource_sample_every < 1:
            raise ValueError("Progress soak sample cadences must be positive")
        if args.p95_budget_seconds <= 0 or args.max_budget_seconds <= 0:
            raise ValueError("latency budgets must be positive")
        if args.max_budget_seconds < args.p95_budget_seconds:
            raise ValueError("max latency budget cannot be lower than p95 budget")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        if args.command == "idle":
            return run_idle(args)
        if args.command == "repeated-scans":
            return run_repeated_scans(args)
        if args.command == "progress-soak":
            return run_progress_soak(args)
    except KeyboardInterrupt:
        return 75
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {clamp_text(exc)}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
