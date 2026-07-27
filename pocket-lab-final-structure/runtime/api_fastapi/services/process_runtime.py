from __future__ import annotations

"""Bounded subprocess execution for heavy Lite collectors.

The runtime owns concurrency, output limits, process-group cleanup, portable
resource limits, and sanitized aggregate diagnostics. It never stores command
arguments, environment values, stdout/stderr contents, secrets, or paths.
"""

from collections import deque
from dataclasses import dataclass, field
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable

try:  # Unix/Termux capability; optional on Windows.
    import resource  # type: ignore
except Exception:  # pragma: no cover - platform dependent
    resource = None  # type: ignore


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _safe(value: Any, maximum: int = 80) -> str:
    text = "".join(
        character if character.isalnum() or character in "._:-" else "_"
        for character in str(value or "unknown").strip().lower()
    )
    return (text or "unknown")[:maximum]


@dataclass(slots=True)
class _WorkloadMetric:
    runs: int = 0
    completed: int = 0
    failed: int = 0
    timed_out: int = 0
    capacity_deferred: int = 0
    cleanup_degraded: int = 0
    output_truncated: int = 0
    resource_limit_attempts: int = 0
    resource_limit_failures: int = 0
    active: int = 0
    duration_ms: deque[float] = field(default_factory=lambda: deque(maxlen=64))
    output_bytes: deque[int] = field(default_factory=lambda: deque(maxlen=64))
    last_status: str = "never"
    last_error_type: str = ""
    last_completed_at_epoch_ms: int = 0


class BoundedProcessRuntime:
    def __init__(self) -> None:
        termux = "com.termux" in os.environ.get("PREFIX", "")
        self.max_global = _bounded_int(
            "POCKETLAB_HEAVY_PROCESS_MAX_CONCURRENT", 1 if termux else 2, 1, 8
        )
        self.max_security = _bounded_int(
            "POCKETLAB_SECURITY_PROCESS_MAX_CONCURRENT", 1, 1, 4
        )
        self.output_limit_bytes = _bounded_int(
            "POCKETLAB_PROCESS_OUTPUT_LIMIT_BYTES", 2 * 1024 * 1024, 64 * 1024, 16 * 1024 * 1024
        )
        self.acquire_timeout_seconds = float(
            _bounded_int("POCKETLAB_PROCESS_ACQUIRE_TIMEOUT_SECONDS", 2, 0, 60)
        )
        self.memory_limit_mb = _bounded_int(
            "POCKETLAB_HEAVY_PROCESS_MEMORY_LIMIT_MB", 768 if termux else 1536, 128, 8192
        )
        self.file_limit = _bounded_int(
            "POCKETLAB_HEAVY_PROCESS_FILE_LIMIT", 512, 64, 8192
        )
        self.nice_increment = _bounded_int(
            "POCKETLAB_HEAVY_PROCESS_NICE", 5 if termux else 3, 0, 19
        )
        self._global = threading.BoundedSemaphore(self.max_global)
        self._security = threading.BoundedSemaphore(self.max_security)
        self._lock = threading.RLock()
        self._metrics: dict[str, _WorkloadMetric] = {}

    def _metric(self, workload: str) -> _WorkloadMetric:
        safe = _safe(workload)
        with self._lock:
            return self._metrics.setdefault(safe, _WorkloadMetric())

    @staticmethod
    def _signal_process_group(process: subprocess.Popen[Any], sig: int) -> None:
        if os.name != "nt" and hasattr(os, "killpg"):
            try:
                os.killpg(os.getpgid(process.pid), sig)
                return
            except (ProcessLookupError, PermissionError, OSError):
                pass
        try:
            if sig == signal.SIGTERM:
                process.terminate()
            else:
                process.kill()
        except (ProcessLookupError, OSError):
            pass

    def _terminate(self, process: subprocess.Popen[Any], *, grace_seconds: float = 2.0) -> bool:
        if process.poll() is not None:
            return True
        self._signal_process_group(process, signal.SIGTERM)
        try:
            process.wait(timeout=max(0.1, grace_seconds))
        except subprocess.TimeoutExpired:
            self._signal_process_group(process, signal.SIGKILL)
            try:
                process.wait(timeout=max(0.1, grace_seconds))
            except subprocess.TimeoutExpired:
                return False
        return process.poll() is not None

    def _apply_limits(self, process: subprocess.Popen[Any], *, timeout: int, metric: _WorkloadMetric) -> None:
        if os.name == "nt":
            return
        metric.resource_limit_attempts += 1
        failed = False
        try:
            if hasattr(os, "setpriority") and self.nice_increment:
                os.setpriority(os.PRIO_PROCESS, process.pid, self.nice_increment)
        except (AttributeError, PermissionError, ProcessLookupError, OSError):
            failed = True
        if resource is not None and hasattr(resource, "prlimit"):
            try:
                memory_bytes = self.memory_limit_mb * 1024 * 1024
                resource.prlimit(process.pid, resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            except (AttributeError, PermissionError, ProcessLookupError, OSError, ValueError):
                failed = True
            try:
                cpu_limit = max(2, int(timeout) + 5)
                resource.prlimit(process.pid, resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 5))
            except (AttributeError, PermissionError, ProcessLookupError, OSError, ValueError):
                failed = True
            try:
                resource.prlimit(process.pid, resource.RLIMIT_NOFILE, (self.file_limit, self.file_limit))
            except (AttributeError, PermissionError, ProcessLookupError, OSError, ValueError):
                failed = True
        if failed:
            metric.resource_limit_failures += 1

    @staticmethod
    def _read_bounded(handle: Any, limit: int) -> tuple[str, int, bool]:
        if handle is None:
            return "", 0, False
        try:
            handle.flush()
            handle.seek(0)
            raw = handle.read(limit + 1)
        except (AttributeError, OSError, ValueError):
            return "", 0, False
        if isinstance(raw, str):
            encoded = raw.encode("utf-8", errors="replace")
        else:
            encoded = bytes(raw or b"")
        truncated = len(encoded) > limit
        bounded = encoded[:limit]
        return bounded.decode("utf-8", errors="replace"), len(encoded), truncated

    @staticmethod
    def _bounded_text(value: str, limit: int) -> tuple[str, int, bool]:
        encoded = str(value or "").encode("utf-8", errors="replace")
        return (
            encoded[:limit].decode("utf-8", errors="replace"),
            len(encoded),
            len(encoded) > limit,
        )

    def run(
        self,
        args: list[str],
        *,
        cwd: Path,
        timeout: int,
        workload: str,
        redact: Callable[[str], str],
        popen_factory: Callable[..., subprocess.Popen[Any]] = subprocess.Popen,
    ) -> dict[str, Any]:
        safe_workload = _safe(workload)
        metric = self._metric(safe_workload)
        started = time.monotonic()
        acquired_global = self._global.acquire(timeout=self.acquire_timeout_seconds)
        if not acquired_global:
            with self._lock:
                metric.capacity_deferred += 1
                metric.last_status = "capacity_deferred"
            return {
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": "Worker capacity is busy. Try again shortly.",
                "timed_out": False,
                "capacity_deferred": True,
                "retry_after_ms": 2_000,
                "process_cleanup": "not_started",
                "workload": safe_workload,
            }
        security_lane = safe_workload.startswith("security")
        acquired_workload = self._security.acquire(timeout=self.acquire_timeout_seconds) if security_lane else True
        if not acquired_workload:
            self._global.release()
            with self._lock:
                metric.capacity_deferred += 1
                metric.last_status = "capacity_deferred"
            return {
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": "Security worker capacity is busy. Try again shortly.",
                "timed_out": False,
                "capacity_deferred": True,
                "retry_after_ms": 2_000,
                "process_cleanup": "not_started",
                "workload": safe_workload,
            }

        process: subprocess.Popen[Any] | None = None
        stdout_handle = None
        stderr_handle = None
        use_bounded_files = popen_factory is subprocess.Popen
        with self._lock:
            metric.runs += 1
            metric.active += 1
        try:
            popen_kwargs: dict[str, Any] = {
                "cwd": str(cwd),
                "env": {**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
            }
            if use_bounded_files:
                stdout_handle = tempfile.TemporaryFile(mode="w+b")
                stderr_handle = tempfile.TemporaryFile(mode="w+b")
                popen_kwargs.update({"stdout": stdout_handle, "stderr": stderr_handle, "text": False})
            else:
                popen_kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True})
            if os.name == "nt":
                create_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                if create_group:
                    popen_kwargs["creationflags"] = create_group
            else:
                popen_kwargs["start_new_session"] = True

            process = popen_factory(args, **popen_kwargs)
            self._apply_limits(process, timeout=timeout, metric=metric)
            timed_out = False
            cleanup_confirmed = True
            stdout_raw: Any = ""
            stderr_raw: Any = ""
            try:
                stdout_raw, stderr_raw = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                cleanup_confirmed = self._terminate(process)
                try:
                    stdout_raw, stderr_raw = process.communicate(timeout=2.0)
                except subprocess.TimeoutExpired:
                    cleanup_confirmed = False
            if use_bounded_files:
                stdout, stdout_bytes, stdout_truncated = self._read_bounded(stdout_handle, self.output_limit_bytes)
                stderr, stderr_bytes, stderr_truncated = self._read_bounded(stderr_handle, self.output_limit_bytes)
            else:
                stdout, stdout_bytes, stdout_truncated = self._bounded_text(stdout_raw or "", self.output_limit_bytes)
                stderr, stderr_bytes, stderr_truncated = self._bounded_text(stderr_raw or "", self.output_limit_bytes)
            output_bytes = stdout_bytes + stderr_bytes
            truncated = stdout_truncated or stderr_truncated
            duration_ms = max(0.0, (time.monotonic() - started) * 1000.0)
            with self._lock:
                metric.duration_ms.append(duration_ms)
                metric.output_bytes.append(output_bytes)
                metric.last_completed_at_epoch_ms = int(time.time() * 1000)
                if timed_out:
                    metric.timed_out += 1
                    metric.last_status = "timed_out"
                elif process.returncode == 0:
                    metric.completed += 1
                    metric.last_status = "completed"
                else:
                    metric.failed += 1
                    metric.last_status = "failed"
                if not cleanup_confirmed:
                    metric.cleanup_degraded += 1
                if truncated:
                    metric.output_truncated += 1
            return {
                "ok": bool(not timed_out and process.returncode == 0),
                "returncode": process.returncode,
                "stdout": redact(stdout),
                "stderr": redact(stderr),
                "timed_out": timed_out,
                "timeout_seconds": timeout if timed_out else None,
                "capacity_deferred": False,
                "retry_after_ms": 0,
                "process_cleanup": "complete" if cleanup_confirmed else "degraded",
                "output_truncated": truncated,
                "output_bytes": output_bytes,
                "output_limit_bytes": self.output_limit_bytes,
                "duration_ms": round(duration_ms, 2),
                "workload": safe_workload,
            }
        except BaseException as exc:
            if process is not None and process.poll() is None:
                cleanup_confirmed = self._terminate(process)
            else:
                cleanup_confirmed = True
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            with self._lock:
                metric.failed += 1
                metric.last_status = "failed"
                metric.last_error_type = type(exc).__name__
                if not cleanup_confirmed:
                    metric.cleanup_degraded += 1
            return {
                "ok": False,
                "returncode": process.returncode if process is not None else None,
                "stdout": "",
                "stderr": redact(type(exc).__name__),
                "timed_out": False,
                "capacity_deferred": False,
                "retry_after_ms": 0,
                "process_cleanup": "complete" if cleanup_confirmed else "degraded",
                "workload": safe_workload,
            }
        finally:
            for handle in (stdout_handle, stderr_handle):
                if handle is not None:
                    try:
                        handle.close()
                    except OSError:
                        pass
            with self._lock:
                metric.active = max(0, metric.active - 1)
            if security_lane and acquired_workload:
                self._security.release()
            self._global.release()


    @staticmethod
    def _memory_usage() -> tuple[int | None, int | None, str]:
        current: int | None = None
        peak: int | None = None
        source = "unsupported"
        if os.name != "nt":
            try:
                statm = Path("/proc/self/statm").read_text(encoding="utf-8").split()
                page_size = int(os.sysconf("SC_PAGE_SIZE"))
                current = int(statm[1]) * page_size
                source = "proc_statm"
            except (OSError, ValueError, IndexError, AttributeError):
                pass
        if resource is not None:
            try:
                raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                # Linux/Android report KiB; macOS reports bytes.
                peak = raw if sys.platform == "darwin" else raw * 1024
                if source == "unsupported":
                    source = "getrusage_peak_only"
            except (AttributeError, OSError, ValueError):
                pass
        return current, peak, source

    @staticmethod
    def _distribution(values: list[float]) -> dict[str, float | int]:
        ordered = sorted(max(0.0, float(value)) for value in values)
        def percentile(ratio: float) -> float:
            if not ordered:
                return 0.0
            index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
            return ordered[index]
        return {
            "count": len(ordered),
            "p50": round(percentile(0.50), 2),
            "p95": round(percentile(0.95), 2),
            "p99": round(percentile(0.99), 2),
            "max": round(max(ordered) if ordered else 0.0, 2),
        }

    def snapshot(self) -> dict[str, Any]:
        memory_rss_bytes, memory_peak_rss_bytes, memory_source = self._memory_usage()
        with self._lock:
            rows = {}
            for name, metric in sorted(self._metrics.items()):
                rows[name] = {
                    "runs": metric.runs,
                    "completed": metric.completed,
                    "failed": metric.failed,
                    "timed_out": metric.timed_out,
                    "capacity_deferred": metric.capacity_deferred,
                    "cleanup_degraded": metric.cleanup_degraded,
                    "output_truncated": metric.output_truncated,
                    "resource_limit_attempts": metric.resource_limit_attempts,
                    "resource_limit_failures": metric.resource_limit_failures,
                    "active": metric.active,
                    "duration_ms": self._distribution(list(metric.duration_ms)),
                    "output_bytes": self._distribution([float(value) for value in metric.output_bytes]),
                    "last_status": metric.last_status,
                    "last_error_type": metric.last_error_type,
                    "last_completed_at_epoch_ms": metric.last_completed_at_epoch_ms,
                }
        active_children = sum(int(row.get("active") or 0) for row in rows.values())
        recycled_children = sum(
            int(row.get("completed") or 0) + int(row.get("failed") or 0)
            + int(row.get("timed_out") or 0)
            for row in rows.values()
        )
        return {
            "process_isolated": True,
            "recycle_strategy": "isolated_child_per_task",
            "recycle_count": recycled_children,
            "subprocess_count": active_children,
            "subprocess_limit": self.max_global,
            "max_concurrent": self.max_global,
            "security_max_concurrent": self.max_security,
            "memory_rss_bytes": memory_rss_bytes,
            "memory_peak_rss_bytes": memory_peak_rss_bytes,
            "memory_metric_source": memory_source,
            "output_limit_bytes": self.output_limit_bytes,
            "memory_limit_mb": self.memory_limit_mb,
            "file_limit": self.file_limit,
            "nice_increment": self.nice_increment,
            "workloads": rows,
            "sanitized": True,
        }


PROCESS_RUNTIME = BoundedProcessRuntime()
