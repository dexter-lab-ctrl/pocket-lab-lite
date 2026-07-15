from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import gc
import logging
import os
import threading
import time
from typing import Any, Awaitable, Callable


_LOGGER = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


class RuntimeDiagnostics:
    """Bounded, process-local attribution for the Lite FastAPI runtime."""

    def __init__(
        self,
        *,
        loop_interval_seconds: float | None = None,
        loop_warning_ms: float | None = None,
        loop_critical_ms: float | None = None,
        gc_slow_ms: float | None = None,
    ) -> None:
        self.loop_interval_seconds = loop_interval_seconds or _bounded_float(
            "POCKETLAB_EVENT_LOOP_LAG_INTERVAL_SECONDS", 0.75, 0.10, 5.0
        )
        self.loop_warning_ms = loop_warning_ms or _bounded_float(
            "POCKETLAB_EVENT_LOOP_LAG_WARNING_MS", 250.0, 25.0, 10_000.0
        )
        self.loop_critical_ms = loop_critical_ms or _bounded_float(
            "POCKETLAB_EVENT_LOOP_LAG_CRITICAL_MS", 1000.0, self.loop_warning_ms, 30_000.0
        )
        self.gc_slow_ms = gc_slow_ms or _bounded_float(
            "POCKETLAB_GC_SLOW_MS", 50.0, 1.0, 10_000.0
        )
        self.request_slow_ms = _bounded_float(
            "POCKETLAB_PROGRESS_REQUEST_SLOW_MS", 1000.0, 50.0, 30_000.0
        )
        self.request_phase_slow_ms = _bounded_float(
            "POCKETLAB_PROGRESS_REQUEST_PHASE_SLOW_MS", 250.0, 10.0, 10_000.0
        )
        self._lock = threading.Lock()
        self._loop_task: asyncio.Task[None] | None = None
        self._loop_samples = 0
        self._loop_warning_count = 0
        self._loop_critical_count = 0
        self._loop_latest_ms = 0.0
        self._loop_recent: deque[float] = deque(maxlen=120)
        self._loop_last_warning_at: str | None = None
        self._loop_last_severity = "healthy"
        self._loop_last_summary_monotonic = 0.0
        self._gc_installed = False
        self._gc_started: dict[int, float] = {}
        self._gc_metrics: dict[int, dict[str, Any]] = {
            generation: {
                "collections": 0,
                "latest_duration_ms": 0.0,
                "recent": deque(maxlen=32),
                "collected": 0,
                "uncollectable": 0,
            }
            for generation in range(3)
        }
        self._slow_requests: deque[dict[str, Any]] = deque(maxlen=12)
        self._request_count = 0
        self._slow_request_count = 0
        self._failed_request_count = 0

    async def start(self) -> bool:
        """Start one lag monitor and install one GC callback."""
        with self._lock:
            if self._loop_task is not None and not self._loop_task.done():
                return False
            try:
                loop = asyncio.get_running_loop()
                self._loop_task = loop.create_task(
                    self._event_loop_lag_loop(),
                    name="pocketlab-event-loop-lag-monitor",
                )
            except RuntimeError:
                self._loop_task = None
                return False
        self._install_gc_callback()
        return True

    async def stop(self) -> None:
        """Cancel and await the monitor, then remove the GC callback."""
        with self._lock:
            task = self._loop_task
            self._loop_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._remove_gc_callback()

    async def _event_loop_lag_loop(self) -> None:
        loop = asyncio.get_running_loop()
        expected = loop.time() + self.loop_interval_seconds
        try:
            while True:
                await asyncio.sleep(max(0.0, expected - loop.time()))
                actual = loop.time()
                lag_ms = max(0.0, (actual - expected) * 1000.0)
                self.record_event_loop_lag(lag_ms)
                expected = actual + self.loop_interval_seconds
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # fail-safe instrumentation only
            _LOGGER.warning(
                "pocketlab.runtime.event_loop_monitor_degraded error_type=%s",
                type(exc).__name__,
            )

    def record_event_loop_lag(self, lag_ms: float) -> None:
        severity = (
            "critical"
            if lag_ms >= self.loop_critical_ms
            else "warning"
            if lag_ms >= self.loop_warning_ms
            else "healthy"
        )
        now_monotonic = time.monotonic()
        should_log = False
        with self._lock:
            self._loop_samples += 1
            self._loop_latest_ms = max(0.0, float(lag_ms))
            self._loop_recent.append(self._loop_latest_ms)
            if severity == "critical":
                self._loop_critical_count += 1
            elif severity == "warning":
                self._loop_warning_count += 1
            if severity != "healthy":
                self._loop_last_warning_at = _utc_now()
                should_log = severity != self._loop_last_severity
                if not should_log and now_monotonic - self._loop_last_summary_monotonic >= 60.0:
                    should_log = True
                if should_log:
                    self._loop_last_summary_monotonic = now_monotonic
            self._loop_last_severity = severity
            recent_max = max(self._loop_recent, default=0.0)
        if should_log:
            log = _LOGGER.error if severity == "critical" else _LOGGER.warning
            log(
                "pocketlab.runtime.event_loop_lag status=%s latest_lag_ms=%.2f recent_max_lag_ms=%.2f",
                severity,
                lag_ms,
                recent_max,
            )

    def latest_event_loop_lag_ms(self) -> float:
        with self._lock:
            return round(self._loop_latest_ms, 2)

    def _install_gc_callback(self) -> None:
        with self._lock:
            if self._gc_installed:
                return
            self._gc_installed = True
        try:
            if self._gc_callback not in gc.callbacks:
                gc.callbacks.append(self._gc_callback)
        except Exception as exc:
            with self._lock:
                self._gc_installed = False
            _LOGGER.warning(
                "pocketlab.runtime.gc_monitor_degraded error_type=%s",
                type(exc).__name__,
            )

    def _remove_gc_callback(self) -> None:
        with self._lock:
            installed = self._gc_installed
            self._gc_installed = False
            self._gc_started.clear()
        if not installed:
            return
        try:
            while self._gc_callback in gc.callbacks:
                gc.callbacks.remove(self._gc_callback)
        except (ValueError, RuntimeError):
            pass

    def _gc_callback(self, phase: str, info: dict[str, Any]) -> None:
        try:
            generation = max(0, min(2, int(info.get("generation", 0))))
            if phase == "start":
                with self._lock:
                    self._gc_started[generation] = time.perf_counter()
                return
            if phase != "stop":
                return
            completed = time.perf_counter()
            with self._lock:
                started = self._gc_started.pop(generation, completed)
                duration_ms = max(0.0, (completed - started) * 1000.0)
                metric = self._gc_metrics[generation]
                metric["collections"] += 1
                metric["latest_duration_ms"] = duration_ms
                metric["recent"].append(duration_ms)
                metric["collected"] += max(0, int(info.get("collected", 0) or 0))
                metric["uncollectable"] += max(0, int(info.get("uncollectable", 0) or 0))
            if duration_ms >= self.gc_slow_ms:
                _LOGGER.warning(
                    "pocketlab.runtime.gc_pause generation=%d duration_ms=%.2f collected=%d uncollectable=%d",
                    generation,
                    duration_ms,
                    max(0, int(info.get("collected", 0) or 0)),
                    max(0, int(info.get("uncollectable", 0) or 0)),
                )
        except Exception:
            # GC callbacks must never affect collection or API availability.
            return

    def record_progress_request(
        self,
        *,
        status_code: int,
        phases: dict[str, float],
        event_loop_lag_ms: float,
    ) -> None:
        safe_phases = {
            key: round(max(0.0, float(value)), 2)
            for key, value in phases.items()
            if key
            in {
                "middleware_to_route_ms",
                "auth_ms",
                "snapshot_read_ms",
                "response_build_ms",
                "route_handler_ms",
                "response_send_ms",
                "request_total_ms",
            }
        }
        total_ms = safe_phases.get("request_total_ms", 0.0)
        phase_slow = max(safe_phases.values(), default=0.0) >= self.request_phase_slow_ms
        failed = int(status_code) >= 400
        slow = total_ms >= self.request_slow_ms or phase_slow or event_loop_lag_ms >= self.loop_warning_ms
        with self._lock:
            self._request_count += 1
            if failed:
                self._failed_request_count += 1
            if slow or failed:
                self._slow_request_count += 1
                self._slow_requests.append(
                    {
                        "captured_at": _utc_now(),
                        "status_class": f"{max(1, int(status_code) // 100)}xx",
                        "event_loop_lag_ms": round(max(0.0, event_loop_lag_ms), 2),
                        **safe_phases,
                    }
                )
        if slow or failed:
            log = _LOGGER.warning if failed or total_ms >= self.request_slow_ms else _LOGGER.info
            log(
                "pocketlab.runtime.progress_request_slow status_class=%s request_total_ms=%.2f "
                "middleware_to_route_ms=%.2f auth_ms=%.2f snapshot_read_ms=%.2f "
                "response_build_ms=%.2f route_handler_ms=%.2f response_send_ms=%.2f "
                "event_loop_lag_ms=%.2f",
                f"{max(1, int(status_code) // 100)}xx",
                total_ms,
                safe_phases.get("middleware_to_route_ms", 0.0),
                safe_phases.get("auth_ms", 0.0),
                safe_phases.get("snapshot_read_ms", 0.0),
                safe_phases.get("response_build_ms", 0.0),
                safe_phases.get("route_handler_ms", 0.0),
                safe_phases.get("response_send_ms", 0.0),
                max(0.0, event_loop_lag_ms),
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            loop_recent_max = max(self._loop_recent, default=0.0)
            loop_status = (
                "critical"
                if self._loop_latest_ms >= self.loop_critical_ms
                else "warning"
                if self._loop_latest_ms >= self.loop_warning_ms
                else "healthy"
            )
            gc_payload = {}
            gc_recent_max = 0.0
            for generation, metric in self._gc_metrics.items():
                recent_max = max(metric["recent"], default=0.0)
                gc_recent_max = max(gc_recent_max, recent_max)
                gc_payload[f"generation_{generation}"] = {
                    "collections": int(metric["collections"]),
                    "latest_duration_ms": round(float(metric["latest_duration_ms"]), 2),
                    "recent_max_duration_ms": round(recent_max, 2),
                    "collected": int(metric["collected"]),
                    "uncollectable": int(metric["uncollectable"]),
                }
            requests = list(self._slow_requests)
            task_running = self._loop_task is not None and not self._loop_task.done()
            return {
                "event_loop": {
                    "status": loop_status,
                    "monitor_running": task_running,
                    "samples": self._loop_samples,
                    "warning_count": self._loop_warning_count,
                    "critical_count": self._loop_critical_count,
                    "latest_lag_ms": round(self._loop_latest_ms, 2),
                    "recent_max_lag_ms": round(loop_recent_max, 2),
                    "last_warning_at": self._loop_last_warning_at,
                },
                "gc": {
                    "recent_max_pause_ms": round(gc_recent_max, 2),
                    "generations": gc_payload,
                },
                "progress_requests": {
                    "request_count": self._request_count,
                    "slow_request_count": self._slow_request_count,
                    "failed_request_count": self._failed_request_count,
                    "recent_slow_requests": requests,
                },
                "sanitized": True,
            }


class RuntimeTimingMiddleware:
    """Attribute the Progress ASGI path without inspecting request content."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        if scope.get("type") != "http" or scope.get("path") != "/api/lite/security/progress":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        state = scope.setdefault("state", {})
        state["pocketlab_middleware_entry"] = started
        state["pocketlab_event_loop_lag_ms"] = RUNTIME_DIAGNOSTICS.latest_event_loop_lag_ms()
        status_code = 500
        response_started: float | None = None
        completed = False

        async def timed_send(message: dict[str, Any]) -> None:
            nonlocal status_code, response_started, completed
            message_type = message.get("type")
            if message_type == "http.response.start":
                status_code = int(message.get("status") or 500)
                response_started = time.perf_counter()
            await send(message)
            if message_type == "http.response.body" and not message.get("more_body", False):
                completed_at = time.perf_counter()
                completed = True
                phases = dict(state.get("pocketlab_progress_timing") or {})
                phases["response_send_ms"] = max(
                    0.0, (completed_at - (response_started or completed_at)) * 1000.0
                )
                phases["request_total_ms"] = max(0.0, (completed_at - started) * 1000.0)
                RUNTIME_DIAGNOSTICS.record_progress_request(
                    status_code=status_code,
                    phases=phases,
                    event_loop_lag_ms=float(state.get("pocketlab_event_loop_lag_ms") or 0.0),
                )

        try:
            await self.app(scope, receive, timed_send)
        except Exception:
            if not completed:
                failed_at = time.perf_counter()
                phases = dict(state.get("pocketlab_progress_timing") or {})
                phases["request_total_ms"] = max(0.0, (failed_at - started) * 1000.0)
                RUNTIME_DIAGNOSTICS.record_progress_request(
                    status_code=500,
                    phases=phases,
                    event_loop_lag_ms=float(state.get("pocketlab_event_loop_lag_ms") or 0.0),
                )
            raise


RUNTIME_DIAGNOSTICS = RuntimeDiagnostics()
