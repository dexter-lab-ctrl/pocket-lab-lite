from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .. import deps
from .idle_efficiency import IDLE_EFFICIENCY
from .nats_bus import BUS
from .workload_admission import WORKLOAD_ADMISSION

_LOGGER = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, minimum: float = 1.0, maximum: float = 86_400.0) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))




def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _stable_hash(payload: Any) -> str:
    try:
        blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        blob = str(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _stable_jitter(name: str, attempt: int, ratio: float = 0.10) -> float:
    digest = hashlib.sha256(f"{name}:{attempt}".encode("utf-8")).digest()
    return 1.0 + (int.from_bytes(digest[:2], "big") / 65535.0) * ratio


def _health_signature(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    services = snapshot.get("services") or {}
    service_sig: Dict[str, Any] = {}
    if isinstance(services, dict):
        for name, value in services.items():
            if isinstance(value, dict):
                service_sig[str(name)] = {
                    "status": value.get("status"),
                    "summary": value.get("summary"),
                    "url": value.get("url"),
                }
            else:
                service_sig[str(name)] = {"status": value}
    return {
        "status": snapshot.get("status"),
        "summary": snapshot.get("summary") or {},
        "services": service_sig,
        "source": snapshot.get("source"),
    }


def _fleet_signature(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    nodes = snapshot.get("nodes") or snapshot.get("items") or []
    if not isinstance(nodes, list):
        nodes = []
    return {
        "status": snapshot.get("status"),
        "summary": snapshot.get("summary") or {},
        "nodes": [
            {
                "id": node.get("id") or node.get("name"),
                "status": node.get("status") or node.get("health"),
                "role": node.get("role"),
            }
            for node in nodes
            if isinstance(node, dict)
        ],
    }


def _telemetry_changed(
    previous: Optional[Dict[str, Any]], current: Dict[str, Any], threshold: float
) -> bool:
    if not previous:
        return True
    numeric_keys = [
        "cpu_temp_c",
        "cpu_usage_percent",
        "memory_usage_mb",
        "memory_free_mb",
        "free_space_mb",
    ]
    for key in numeric_keys:
        try:
            before = float(previous.get(key, 0) or 0)
            after = float(current.get(key, 0) or 0)
        except Exception:
            continue
        if key in {"cpu_temp_c", "cpu_usage_percent"}:
            if abs(after - before) >= threshold:
                return True
        else:
            base = max(abs(before), 1.0)
            if abs(after - before) / base * 100.0 >= threshold:
                return True
    return False


@dataclass
class LiveStatusSampler:
    """Consolidated, event-wakeable and adaptive live-status sampler.

    One coordinator owns all periodic work. Stable domains back off toward long
    idle intervals, changes reset them to active cadence, and repeated failures
    open a bounded circuit while the last safe state remains available.
    """

    enabled: bool = field(
        default_factory=lambda: _env_bool("POCKETLAB_LIVE_STATUS_ENABLED", True)
    )
    telemetry_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_TELEMETRY_SAMPLE_SECONDS", 30.0)
    )
    health_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_HEALTH_SAMPLE_SECONDS", 60.0)
    )
    fleet_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_FLEET_SAMPLE_SECONDS", 60.0)
    )
    telemetry_idle_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_TELEMETRY_IDLE_SECONDS", 300.0)
    )
    health_idle_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_HEALTH_IDLE_SECONDS", 300.0)
    )
    fleet_idle_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_FLEET_IDLE_SECONDS", 300.0)
    )
    device_health_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_DEVICE_HEALTH_SWEEP_SECONDS", 60.0, 30.0, 900.0)
    )
    device_health_idle_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_DEVICE_HEALTH_IDLE_SECONDS", 300.0, 60.0, 3600.0)
    )
    max_idle_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_LIVE_STATUS_MAX_IDLE_SECONDS", 1800.0)
    )
    sample_deadline_seconds: float = field(
        default_factory=lambda: _env_float("POCKETLAB_LIVE_STATUS_DEADLINE_SECONDS", 12.0, 1.0, 120.0)
    )
    publish_keepalive_seconds: float = field(
        default_factory=lambda: _env_float("POCKETLAB_LIVE_STATUS_KEEPALIVE_SECONDS", 900.0)
    )
    circuit_failures: int = field(
        default_factory=lambda: _env_int("POCKETLAB_LIVE_STATUS_CIRCUIT_FAILURES", 3, 2, 8)
    )
    circuit_cooldown_seconds: float = field(
        default_factory=lambda: _env_float("POCKETLAB_LIVE_STATUS_CIRCUIT_SECONDS", 300.0, 30.0, 3600.0)
    )
    telemetry_threshold: float = field(
        default_factory=lambda: _env_float("POCKETLAB_TELEMETRY_CHANGE_THRESHOLD", 2.0, 0.1, 100.0)
    )
    _tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    _started_at: Optional[str] = None
    _last_telemetry: Optional[Dict[str, Any]] = None
    _last_health_hash: str = ""
    _last_fleet_hash: str = ""
    _last_health_services: Dict[str, str] = field(default_factory=dict)
    _device_health_sampler: Callable[[], Dict[str, Any]] | None = None
    _last_device_health_hash: str = ""
    _samples: Dict[str, int] = field(
        default_factory=lambda: {"telemetry": 0, "health": 0, "fleet": 0, "device_health": 0}
    )
    _unchanged: Dict[str, int] = field(
        default_factory=lambda: {"telemetry": 0, "health": 0, "fleet": 0, "device_health": 0}
    )
    _published: Dict[str, int] = field(
        default_factory=lambda: {"telemetry": 0, "health": 0, "fleet": 0, "device_health": 0}
    )
    _errors: Dict[str, str] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _state_lock: threading.Lock = field(default_factory=threading.Lock)
    _wake: asyncio.Event = field(default_factory=asyncio.Event)
    _loop_ref: asyncio.AbstractEventLoop | None = None
    _due_at: Dict[str, float] = field(default_factory=dict)
    _stable_count: Dict[str, int] = field(default_factory=dict)
    _failure_count: Dict[str, int] = field(default_factory=dict)
    _circuit_until: Dict[str, float] = field(default_factory=dict)
    _last_duration_ms: Dict[str, float] = field(default_factory=dict)
    _last_published_at: Dict[str, float] = field(default_factory=dict)
    _last_changed: Dict[str, bool] = field(default_factory=dict)
    _semantic_source_revision: Dict[str, int] = field(default_factory=dict)
    _semantic_full_probe_at: Dict[str, float] = field(default_factory=dict)
    _semantic_prebuild_skips: Dict[str, int] = field(default_factory=dict)
    _semantic_reconciliations: Dict[str, int] = field(default_factory=dict)
    _coalesced_wakeups: int = 0
    _event_wakeups: int = 0
    _pressure_deferrals: int = 0
    _last_event_reason: str = ""

    @property
    def _names(self) -> tuple[str, ...]:
        names = ("telemetry", "health", "fleet")
        return names + (("device_health",) if self._device_health_sampler is not None else ())

    def _active_interval(self, name: str) -> float:
        return {
            "telemetry": self.telemetry_interval,
            "health": self.health_interval,
            "fleet": self.fleet_interval,
            "device_health": self.device_health_interval,
        }[name]

    def _idle_interval(self, name: str) -> float:
        return min(
            self.max_idle_interval,
            {
                "telemetry": self.telemetry_idle_interval,
                "health": self.health_idle_interval,
                "fleet": self.fleet_idle_interval,
                "device_health": self.device_health_idle_interval,
            }[name],
        )

    def _adaptive_interval(self, name: str, changed: bool) -> float:
        if changed:
            self._stable_count[name] = 0
            return self._active_interval(name)
        stable = min(8, self._stable_count.get(name, 0) + 1)
        self._stable_count[name] = stable
        base = self._active_interval(name)
        return min(self._idle_interval(name), base * (2 ** min(stable, 6)))

    def register_device_health_sampler(
        self,
        callback: Callable[[], Dict[str, Any]],
    ) -> None:
        """Register the backend-owned proactive health projection callback."""
        if not callable(callback):
            raise TypeError("device health sampler must be callable")
        self._device_health_sampler = callback
        with self._state_lock:
            for mapping in (
                self._stable_count,
                self._failure_count,
                self._circuit_until,
                self._last_duration_ms,
                self._last_published_at,
                self._last_changed,
            ):
                mapping.setdefault("device_health", 0)
        self.request_sample("device_health", reason="device_health_registered")

    async def start(self) -> None:
        async with self._lock:
            if not self.enabled or self._tasks:
                return
            self._started_at = deps.now_utc_iso()
            self._loop_ref = asyncio.get_running_loop()
            now = self._loop_ref.time()
            with self._state_lock:
                # Stagger cold-start probes so Termux does not receive a three-job
                # allocation/GC burst immediately after Uvicorn becomes ready.
                self._due_at = {
                    name: now + index
                    for index, name in enumerate(self._names)
                }
                self._stable_count = {name: 0 for name in self._names}
                self._failure_count = {name: 0 for name in self._names}
                self._circuit_until = {name: 0.0 for name in self._names}
            task = asyncio.create_task(
                self._coordinator_loop(), name="pocketlab-live-status-coordinator"
            )
            self._tasks = [task]
            with contextlib.suppress(Exception):
                await BUS.publish_json(
                    "pocketlab.events.live_status.started",
                    "live_status.started",
                    self.status(),
                )

    async def stop(self) -> None:
        async with self._lock:
            tasks = list(self._tasks)
            self._tasks.clear()
            self._loop_ref = None
        self._wake.set()
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        with contextlib.suppress(Exception):
            await BUS.publish_json(
                "pocketlab.events.live_status.stopped", "live_status.stopped", self.status()
            )

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def request_sample(self, *names: str, reason: str = "event") -> None:
        """Coalesce a thread-safe event hint into the single coordinator."""
        selected = tuple(name for name in names if name in self._names) or self._names
        loop = self._loop_ref
        if loop is None or loop.is_closed():
            return

        def apply() -> None:
            now = loop.time()
            with self._state_lock:
                self._event_wakeups += 1
                self._last_event_reason = str(reason or "event")[:64]
                for name in selected:
                    if self._due_at.get(name, now) <= now:
                        self._coalesced_wakeups += 1
                    self._due_at[name] = now
            self._wake.set()

        try:
            loop.call_soon_threadsafe(apply)
        except RuntimeError:
            return

    async def _coordinator_loop(self) -> None:
        try:
            while True:
                loop = asyncio.get_running_loop()
                now = loop.time()
                with self._state_lock:
                    due = [name for name in self._names if self._due_at.get(name, now) <= now]
                    next_due = min(
                        (self._due_at.get(name, now + 60.0) for name in self._names),
                        default=now + 60.0,
                    )
                if due:
                    # Sequential execution prevents startup and periodic CPU bursts
                    # from stacking collectors onto the same low-power process.
                    for name in due:
                        await self._run_one(name)
                    continue
                timeout = max(0.05, min(300.0, next_due - now))
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    pass
                self._wake.clear()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.exception(
                "pocketlab.live_status.coordinator_failed error_type=%s",
                type(exc).__name__,
            )

    async def _run_one(self, name: str) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        with self._state_lock:
            circuit_until = self._circuit_until.get(name, 0.0)
        if now < circuit_until:
            with self._state_lock:
                self._due_at[name] = circuit_until
            return

        pressure = IDLE_EFFICIENCY.pressure_reason()
        if pressure:
            with self._state_lock:
                self._pressure_deferrals += 1
                self._due_at[name] = now + min(60.0, max(10.0, self._active_interval(name)))
            return

        sampler = {
            "telemetry": self.sample_telemetry,
            "health": self.sample_health,
            "fleet": self.sample_fleet,
            "device_health": self.sample_device_health,
        }[name]
        started = time.monotonic()
        try:
            await asyncio.wait_for(
                sampler(source="coordinator"), timeout=self.sample_deadline_seconds
            )
            changed = bool(self._last_changed.get(name))
            interval = self._adaptive_interval(name, changed)
            with self._state_lock:
                self._failure_count[name] = 0
                self._circuit_until[name] = 0.0
                self._last_duration_ms[name] = (time.monotonic() - started) * 1000.0
                self._due_at[name] = loop.time() + interval
            self._errors.pop(name, None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failure = min(8, self._failure_count.get(name, 0) + 1)
            delay = min(300.0, 5.0 * (2 ** min(failure, 6))) * _stable_jitter(name, failure)
            circuit_until = 0.0
            if failure >= self.circuit_failures:
                delay = max(delay, self.circuit_cooldown_seconds)
                circuit_until = loop.time() + delay
            with self._state_lock:
                self._failure_count[name] = failure
                self._circuit_until[name] = circuit_until
                self._last_duration_ms[name] = (time.monotonic() - started) * 1000.0
                self._due_at[name] = loop.time() + delay
            self._errors[name] = type(exc).__name__
            with contextlib.suppress(Exception):
                await BUS.publish_json(
                    f"pocketlab.events.live_status.{name}_error",
                    f"live_status.{name}_error",
                    {
                        "component": name,
                        "error_type": type(exc).__name__,
                        "retry_after_seconds": round(delay, 2),
                        "sanitized": True,
                    },
                )

    def _should_publish(self, name: str, changed: bool) -> bool:
        now = time.monotonic()
        last = self._last_published_at.get(name, 0.0)
        publish = changed or last <= 0.0 or now - last >= self.publish_keepalive_seconds
        if publish:
            self._last_published_at[name] = now
            self._published[name] += 1
        else:
            self._unchanged[name] += 1
        return publish

    def last_telemetry_snapshot(self) -> Dict[str, Any]:
        with self._state_lock:
            return dict(self._last_telemetry or {})

    def _semantic_probe_skipped(
        self, name: str, source_revision: int, *, source: str, max_probe_seconds: float
    ) -> bool:
        if source != "coordinator" or source_revision <= 0:
            return False
        now = time.monotonic()
        previous = int(self._semantic_source_revision.get(name) or 0)
        last_full = float(self._semantic_full_probe_at.get(name) or 0.0)
        if previous == source_revision and last_full > 0 and now - last_full < max_probe_seconds:
            self._semantic_prebuild_skips[name] = self._semantic_prebuild_skips.get(name, 0) + 1
            return True
        self._semantic_source_revision[name] = source_revision
        self._semantic_full_probe_at[name] = now
        self._semantic_reconciliations[name] = self._semantic_reconciliations.get(name, 0) + 1
        return False

    async def sample_telemetry(self, *, source: str = "manual") -> Dict[str, Any]:
        sample, _ = await WORKLOAD_ADMISSION.run(
            "system.telemetry_probe", deps.core.telemetry_snapshot
        )
        sample["sample_source"] = source
        sample["sampled_at"] = deps.now_utc_iso()
        changed = _telemetry_changed(self._last_telemetry, sample, self.telemetry_threshold)
        previous = self._last_telemetry
        self._last_telemetry = dict(sample)
        self._last_changed["telemetry"] = changed
        self._samples["telemetry"] += 1
        payload = {
            "sample": sample,
            "changed": changed,
            "source": source,
            "threshold": self.telemetry_threshold,
        }
        if self._should_publish("telemetry", changed):
            await BUS.publish_json(
                "pocketlab.events.telemetry.sampled", "telemetry.sampled", payload
            )
        if changed:
            await BUS.publish_json(
                "pocketlab.events.telemetry.changed",
                "telemetry.changed",
                {"sample": sample, "previous": previous or {}, "source": source},
            )
        return sample

    async def sample_health(self, *, source: str = "manual") -> Dict[str, Any]:
        from . import lite_phase3b_projections as phase3b

        source_revision = phase3b.system_health_source_revision()
        if self._semantic_probe_skipped(
            "health", source_revision, source=source, max_probe_seconds=300.0
        ):
            prepared = phase3b.snapshot("system.health") or {}
            self._last_changed["health"] = False
            self._samples["health"] += 1
            return prepared

        snapshot, _ = await WORKLOAD_ADMISSION.run(
            "system.health_probe", deps.core.build_health_engine_snapshot
        )
        snapshot["sample_source"] = source
        snapshot["sampled_at"] = deps.now_utc_iso()
        current_hash = _stable_hash(_health_signature(snapshot))
        changed = current_hash != self._last_health_hash
        previous_services = dict(self._last_health_services)
        services = snapshot.get("services") or {}
        current_services: Dict[str, str] = {}
        if isinstance(services, dict):
            for service_name, value in services.items():
                current_services[str(service_name)] = str(
                    value.get("status") if isinstance(value, dict) else value or "unknown"
                )
        self._last_health_hash = current_hash
        self._last_health_services = current_services
        self._last_changed["health"] = changed
        self._samples["health"] += 1
        phase3b.project("system.health", phase3b.collect_system_health_state(snapshot))
        phase3b.mark_dirty("system.status", reason="health_sample")
        payload = {
            "snapshot": snapshot,
            "status": snapshot.get("status"),
            "summary": snapshot.get("summary", {}),
            "source": snapshot.get("source"),
            "changed": changed,
        }
        if self._should_publish("health", changed):
            await BUS.publish_json(
                "pocketlab.events.health.checked", "health.checked", payload
            )
        if changed:
            await BUS.publish_json(
                "pocketlab.events.health.changed", "health.changed", payload
            )
        for service, status in current_services.items():
            if previous_services and previous_services.get(service) != status:
                await BUS.publish_json(
                    "pocketlab.events.health.service_changed",
                    "health.service_changed",
                    {
                        "service": service,
                        "previous": previous_services.get(service),
                        "current": status,
                        "snapshot": snapshot,
                    },
                )
        return snapshot

    async def sample_fleet(self, *, source: str = "manual") -> Dict[str, Any]:
        from . import lite_phase3b_projections as phase3b

        source_revision = phase3b.fleet_probe_source_revision()
        if self._semantic_probe_skipped(
            "fleet", source_revision, source=source, max_probe_seconds=300.0
        ):
            prepared = phase3b.snapshot("system.fleet_probe") or {}
            self._last_changed["fleet"] = False
            self._samples["fleet"] += 1
            return prepared

        snapshot = await asyncio.to_thread(phase3b.collect_fleet_probe_state)
        snapshot["sample_source"] = source
        current_hash = _stable_hash(_fleet_signature({
            "status": snapshot.get("status"),
            "summary": snapshot.get("summary") or {},
            "nodes": snapshot.get("items") or [],
        }))
        changed = current_hash != self._last_fleet_hash
        self._last_fleet_hash = current_hash
        self._last_changed["fleet"] = changed
        self._samples["fleet"] += 1
        phase3b.project("system.fleet_probe", snapshot)
        phase3b.mark_dirty(
            "system.agent", "system.supervisor", "system.health", "system.status",
            reason="fleet_sample",
        )
        payload = {"snapshot": snapshot, "changed": changed, "source": source}
        if self._should_publish("fleet", changed):
            await BUS.publish_json(
                "pocketlab.events.fleet.health_sampled", "fleet.health_sampled", payload
            )
        if changed:
            await BUS.publish_json(
                "pocketlab.events.fleet.health_changed", "fleet.health_changed", payload
            )
        return snapshot

    async def sample_device_health(self, *, source: str = "manual") -> Dict[str, Any]:
        callback = self._device_health_sampler
        if callback is None:
            raise RuntimeError("device health sampler is not registered")
        result = await asyncio.to_thread(callback)
        if not isinstance(result, dict):
            raise TypeError("device health sampler must return a mapping")
        signature = {
            "source_revision": result.get("source_revision"),
            "read_degraded": bool(result.get("read_degraded")),
            "refresh_pending": bool(result.get("refresh_pending")),
        }
        current_hash = _stable_hash(signature)
        changed = current_hash != self._last_device_health_hash
        self._last_device_health_hash = current_hash
        self._last_changed["device_health"] = changed
        self._samples["device_health"] += 1
        payload = {
            "result": signature,
            "changed": changed,
            "source": source,
            "sanitized": True,
        }
        if self._should_publish("device_health", changed):
            await BUS.publish_json(
                "pocketlab.events.fleet.device_health_sampled",
                "fleet.device_health_sampled",
                payload,
            )
        return dict(result)

    async def sample_all(self, *, source: str = "manual") -> Dict[str, Any]:
        # Keep manual diagnostics bounded and sequential on edge devices.
        telemetry = await self.sample_telemetry(source=source)
        health = await self.sample_health(source=source)
        fleet = await self.sample_fleet(source=source)
        result = {
            "telemetry": telemetry,
            "health": health,
            "fleet": fleet,
            "sampled_at": deps.now_utc_iso(),
        }
        if self._device_health_sampler is not None:
            result["device_health"] = await self.sample_device_health(source=source)
        return result

    def status(self) -> Dict[str, Any]:
        loop = self._loop_ref
        now = loop.time() if loop is not None and not loop.is_closed() else time.monotonic()
        with self._state_lock:
            next_due = {
                name: max(0.0, round(self._due_at.get(name, now) - now, 2))
                for name in self._names
            }
            failure_count = dict(self._failure_count)
            circuit_open = {
                name: self._circuit_until.get(name, 0.0) > now for name in self._names
            }
            stable_count = dict(self._stable_count)
            duration = {name: round(value, 2) for name, value in self._last_duration_ms.items()}
            coalesced = self._coalesced_wakeups
            event_wakeups = self._event_wakeups
            last_event_reason = self._last_event_reason
            pressure_deferrals = self._pressure_deferrals
        return {
            "enabled": self.enabled,
            "running": any(not task.done() for task in self._tasks),
            "started_at": self._started_at,
            "mode": "consolidated_adaptive",
            "intervals": {
                "active": {
                    "telemetry_seconds": self.telemetry_interval,
                    "health_seconds": self.health_interval,
                    "fleet_seconds": self.fleet_interval,
                    "device_health_seconds": self.device_health_interval,
                },
                "idle": {
                    "telemetry_seconds": self.telemetry_idle_interval,
                    "health_seconds": self.health_idle_interval,
                    "fleet_seconds": self.fleet_idle_interval,
                    "device_health_seconds": self.device_health_idle_interval,
                    "maximum_seconds": self.max_idle_interval,
                },
            },
            "next_due_seconds": next_due,
            "stable_count": stable_count,
            "failure_count": failure_count,
            "circuit_open": circuit_open,
            "last_duration_ms": duration,
            "coalesced_wakeups": coalesced,
            "event_wakeups": event_wakeups,
            "last_event_reason": last_event_reason,
            "pressure_deferrals": pressure_deferrals,
            "telemetry_change_threshold": self.telemetry_threshold,
            "samples": dict(self._samples),
            "unchanged_suppressed": dict(self._unchanged),
            "published": dict(self._published),
            "errors": dict(self._errors),
            "idle_efficiency": IDLE_EFFICIENCY.snapshot(),
            "bus": BUS.status(),
            "last_health_services": dict(self._last_health_services),
            "semantic_revision_gates": {
                "source_revisions": dict(self._semantic_source_revision),
                "prebuild_unchanged_skips": dict(self._semantic_prebuild_skips),
                "bounded_reconciliations": dict(self._semantic_reconciliations),
            },
            "sanitized": True,
        }


LIVE_STATUS = LiveStatusSampler()
