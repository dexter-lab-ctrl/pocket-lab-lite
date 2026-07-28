from __future__ import annotations

"""Low-power runtime governor for the Pocket Lab Lite API process.

The governor is observational by default and only applies conservative, bounded
controls to optional background work. It never throttles request handling,
command delivery, security writes, or recovery execution.
"""

import asyncio
from collections import deque
import concurrent.futures
import gc
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any

from .runtime_diagnostics import RUNTIME_DIAGNOSTICS

_LOGGER = logging.getLogger(__name__)


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _memory_available_percent() -> float | None:
    path = Path("/proc/meminfo")
    try:
        values: dict[str, int] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            token = value.strip().split()[0]
            values[key] = int(token)
        total = int(values.get("MemTotal") or 0)
        available = int(values.get("MemAvailable") or values.get("MemFree") or 0)
        if total <= 0:
            return None
        return max(0.0, min(100.0, available / total * 100.0))
    except (OSError, ValueError, IndexError):
        return None


class IdleEfficiencyGovernor:
    """Samples process pressure and exposes bounded admission guidance."""

    def __init__(self) -> None:
        termux = "com.termux" in os.environ.get("PREFIX", "")
        self.enabled = _env_bool("POCKETLAB_LITE_IDLE_GOVERNOR_ENABLED", True)
        self.sample_seconds = _bounded_float(
            "POCKETLAB_LITE_IDLE_SAMPLE_SECONDS", 5.0, 1.0, 60.0
        )
        self.cpu_warning_percent = _bounded_float(
            "POCKETLAB_LITE_IDLE_CPU_WARNING_PERCENT", 18.0 if termux else 25.0, 1.0, 400.0
        )
        self.cpu_critical_percent = _bounded_float(
            "POCKETLAB_LITE_IDLE_CPU_CRITICAL_PERCENT", 35.0 if termux else 50.0,
            self.cpu_warning_percent,
            800.0,
        )
        self.memory_warning_available_percent = _bounded_float(
            "POCKETLAB_LITE_MEMORY_WARNING_AVAILABLE_PERCENT", 8.0, 1.0, 50.0
        )
        self.load_warning_ratio = _bounded_float(
            "POCKETLAB_LITE_LOAD_WARNING_RATIO", 0.90, 0.10, 8.0
        )
        self.optional_duty_cycle_percent = _bounded_float(
            "POCKETLAB_LITE_OPTIONAL_DUTY_CYCLE_PERCENT", 12.0 if termux else 20.0,
            1.0,
            100.0,
        )
        self.max_optional_cooldown_seconds = _bounded_float(
            "POCKETLAB_LITE_OPTIONAL_COOLDOWN_MAX_SECONDS", 30.0, 0.0, 300.0
        )
        self._lock = threading.Lock()
        self._task: asyncio.Task[None] | None = None
        self._wake: asyncio.Event | None = None
        self._sample_executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._started_at: str | None = None
        self._last_wall = time.monotonic()
        self._last_cpu = time.process_time()
        self._latest_cpu_percent = 0.0
        self._recent_cpu: deque[float] = deque(maxlen=24)
        self._latest_load_ratio = 0.0
        self._latest_memory_available_percent: float | None = None
        self._status = "healthy"
        self._pressure_reason = ""
        self._consecutive_warning = 0
        self._consecutive_critical = 0
        self._samples = 0
        self._warning_budget_breaches = 0
        self._critical_budget_breaches = 0
        self._healthy_samples = 0
        self._gc_configured = False
        self._gc_thresholds = tuple(gc.get_threshold())
        self._nice_applied: int | None = None

    def configure_process(self) -> dict[str, Any]:
        """Apply opt-out, low-risk process guards before background work starts."""
        if not self.enabled:
            return self.snapshot()
        termux = "com.termux" in os.environ.get("PREFIX", "")
        if _env_bool("POCKETLAB_LITE_GC_TUNING_ENABLED", True):
            defaults = (1400, 20, 20) if termux else (1000, 15, 15)
            thresholds = (
                _bounded_int("POCKETLAB_LITE_GC_GEN0_THRESHOLD", defaults[0], 200, 100_000),
                _bounded_int("POCKETLAB_LITE_GC_GEN1_THRESHOLD", defaults[1], 5, 1_000),
                _bounded_int("POCKETLAB_LITE_GC_GEN2_THRESHOLD", defaults[2], 5, 1_000),
            )
            gc.set_threshold(*thresholds)
            with self._lock:
                self._gc_configured = True
                self._gc_thresholds = thresholds

        # Never raise priority automatically. An explicitly configured non-negative
        # nice value may only lower this API process's scheduling priority.
        configured_nice = os.environ.get("POCKETLAB_LITE_API_NICE")
        if configured_nice is not None and hasattr(os, "getpriority") and hasattr(os, "setpriority"):
            try:
                requested = max(0, min(19, int(configured_nice)))
                current = int(os.getpriority(os.PRIO_PROCESS, 0))
                target = max(current, requested)
                if target != current:
                    os.setpriority(os.PRIO_PROCESS, 0, target)
                with self._lock:
                    self._nice_applied = target
            except (OSError, TypeError, ValueError):
                _LOGGER.warning("pocketlab.idle_governor.nice_degraded")
        return self.snapshot()

    async def start(self) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            if self._task is not None and not self._task.done():
                return False
            self._started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._last_wall = time.monotonic()
            self._last_cpu = time.process_time()
            self._wake = asyncio.Event()
            self._sample_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="pocketlab-idle-sampler",
            )
            self._task = asyncio.create_task(
                self._loop(), name="pocketlab-idle-efficiency-governor"
            )
        return True

    async def stop(self) -> None:
        with self._lock:
            task = self._task
            self._task = None
        wake = self._wake
        self._wake = None
        with self._lock:
            executor = self._sample_executor
            self._sample_executor = None
        if wake is not None:
            wake.set()
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def wake(self) -> None:
        wake = self._wake
        if wake is None:
            return
        try:
            wake.set()
        except RuntimeError:
            pass

    async def _loop(self) -> None:
        try:
            while True:
                wake = self._wake
                if wake is None:
                    return
                try:
                    await asyncio.wait_for(wake.wait(), timeout=self.sample_seconds)
                except asyncio.TimeoutError:
                    pass
                wake.clear()
                with self._lock:
                    executor = self._sample_executor
                if executor is None:
                    return
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(executor, self.sample_now)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.warning(
                "pocketlab.idle_governor.degraded error_type=%s", type(exc).__name__
            )

    def sample_now(self) -> dict[str, Any]:
        with RUNTIME_DIAGNOSTICS.operation("background.idle_efficiency.sample"):
            return self._sample_now_impl()

    def _sample_now_impl(self) -> dict[str, Any]:
        wall = time.monotonic()
        cpu = time.process_time()
        with self._lock:
            wall_delta = max(0.001, wall - self._last_wall)
            cpu_delta = max(0.0, cpu - self._last_cpu)
            self._last_wall = wall
            self._last_cpu = cpu
        cpu_percent = max(0.0, min(800.0, cpu_delta / wall_delta * 100.0))
        cpu_count = max(1, int(os.cpu_count() or 1))
        try:
            load_ratio = max(0.0, float(os.getloadavg()[0]) / cpu_count)
        except (AttributeError, OSError):
            load_ratio = 0.0
        memory_available = _memory_available_percent()
        lag_ms = RUNTIME_DIAGNOSTICS.latest_event_loop_lag_ms()

        reason = ""
        status = "healthy"
        if lag_ms >= RUNTIME_DIAGNOSTICS.loop_critical_ms:
            status, reason = "critical", "event_loop_pressure"
        elif cpu_percent >= self.cpu_critical_percent:
            status, reason = "critical", "process_cpu_budget"
        elif memory_available is not None and memory_available <= self.memory_warning_available_percent:
            status, reason = "warning", "memory_pressure"
        elif load_ratio >= self.load_warning_ratio:
            status, reason = "warning", "system_load_pressure"
        elif lag_ms >= RUNTIME_DIAGNOSTICS.loop_warning_ms:
            status, reason = "warning", "event_loop_pressure"
        elif cpu_percent >= self.cpu_warning_percent:
            status, reason = "warning", "process_cpu_budget"

        with self._lock:
            self._samples += 1
            self._latest_cpu_percent = cpu_percent
            self._recent_cpu.append(cpu_percent)
            self._latest_load_ratio = load_ratio
            self._latest_memory_available_percent = memory_available
            self._status = status
            self._pressure_reason = reason
            if status == "critical":
                self._critical_budget_breaches += 1
                self._warning_budget_breaches += 1
                self._consecutive_critical += 1
                self._consecutive_warning += 1
            elif status == "warning":
                self._warning_budget_breaches += 1
                self._consecutive_warning += 1
                self._consecutive_critical = 0
            else:
                self._healthy_samples += 1
                self._consecutive_warning = 0
                self._consecutive_critical = 0
        return self.snapshot()

    def pressure_reason(self) -> str:
        """Return a reason only after pressure persists for multiple samples."""
        with self._lock:
            if self._consecutive_critical >= 2:
                return self._pressure_reason or "runtime_pressure"
            if self._consecutive_warning >= 3 and self._pressure_reason in {
                "memory_pressure",
                "system_load_pressure",
            }:
                return self._pressure_reason
            return ""

    def optional_cooldown_seconds(self, duration_ms: float) -> float:
        duration_seconds = max(0.0, float(duration_ms) / 1000.0)
        if duration_seconds <= 0.0 or self.optional_duty_cycle_percent >= 100.0:
            return 0.0
        multiplier = (100.0 / self.optional_duty_cycle_percent) - 1.0
        return min(self.max_optional_cooldown_seconds, duration_seconds * multiplier)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            recent = list(self._recent_cpu)
            task_running = self._task is not None and not self._task.done()
            return {
                "enabled": self.enabled,
                "running": task_running,
                "started_at": self._started_at,
                "status": self._status,
                "pressure_reason": self._pressure_reason,
                "process_cpu_percent": round(self._latest_cpu_percent, 2),
                "recent_cpu_max_percent": round(max(recent, default=0.0), 2),
                "recent_cpu_average_percent": round(
                    sum(recent) / len(recent) if recent else 0.0, 2
                ),
                "system_load_ratio": round(self._latest_load_ratio, 3),
                "memory_available_percent": (
                    round(self._latest_memory_available_percent, 2)
                    if self._latest_memory_available_percent is not None
                    else None
                ),
                "samples": self._samples,
                "idle_budget": {
                    "within_budget": self._status == "healthy",
                    "healthy_samples": self._healthy_samples,
                    "warning_breach_samples": self._warning_budget_breaches,
                    "critical_breach_samples": self._critical_budget_breaches,
                },
                "consecutive_warning_samples": self._consecutive_warning,
                "consecutive_critical_samples": self._consecutive_critical,
                "budgets": {
                    "cpu_warning_percent": self.cpu_warning_percent,
                    "cpu_critical_percent": self.cpu_critical_percent,
                    "optional_duty_cycle_percent": self.optional_duty_cycle_percent,
                    "memory_warning_available_percent": self.memory_warning_available_percent,
                    "load_warning_ratio": self.load_warning_ratio,
                },
                "gc": {
                    "configured": self._gc_configured,
                    "thresholds": list(self._gc_thresholds),
                },
                "process": {
                    "nice": self._nice_applied,
                    "cpu_count": max(1, int(os.cpu_count() or 1)),
                },
                "sanitized": True,
            }


IDLE_EFFICIENCY = IdleEfficiencyGovernor()
