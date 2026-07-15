from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .. import deps
from .nats_bus import BUS
from .workload_admission import WORKLOAD_ADMISSION


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except Exception:
        return default


def _stable_hash(payload: Any) -> str:
    try:
        blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        blob = str(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


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
    """Enterprise live health/NOC sampler for Phase 9.

    FastAPI owns this lightweight sampler on the control-plane node. It turns
    snapshots that were previously only returned by HTTP endpoints into
    continuously published Pocket Lab events. NATS/JetStream carries them when
    available and the in-memory bus keeps local demo/test mode functional.
    """

    enabled: bool = field(
        default_factory=lambda: _env_bool("POCKETLAB_LIVE_STATUS_ENABLED", True)
    )
    telemetry_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_TELEMETRY_SAMPLE_SECONDS", 5.0)
    )
    health_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_HEALTH_SAMPLE_SECONDS", 15.0)
    )
    fleet_interval: float = field(
        default_factory=lambda: _env_float("POCKETLAB_FLEET_SAMPLE_SECONDS", 15.0)
    )
    telemetry_threshold: float = field(
        default_factory=lambda: _env_float("POCKETLAB_TELEMETRY_CHANGE_THRESHOLD", 2.0)
    )
    _tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    _started_at: Optional[str] = None
    _last_telemetry: Optional[Dict[str, Any]] = None
    _last_health_hash: str = ""
    _last_fleet_hash: str = ""
    _last_health_services: Dict[str, str] = field(default_factory=dict)
    _samples: Dict[str, int] = field(
        default_factory=lambda: {"telemetry": 0, "health": 0, "fleet": 0}
    )
    _errors: Dict[str, str] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def start(self) -> None:
        async with self._lock:
            if not self.enabled or self._tasks:
                return
            self._started_at = deps.now_utc_iso()
            self._tasks = [
                asyncio.create_task(
                    self._loop(
                        "telemetry", self.telemetry_interval, self.sample_telemetry
                    ),
                    name="pocketlab-telemetry-sampler",
                ),
                asyncio.create_task(
                    self._loop("health", self.health_interval, self.sample_health),
                    name="pocketlab-health-sampler",
                ),
                asyncio.create_task(
                    self._loop("fleet", self.fleet_interval, self.sample_fleet),
                    name="pocketlab-fleet-sampler",
                ),
            ]
            await BUS.publish_json(
                "pocketlab.events.live_status.started",
                "live_status.started",
                self.status(),
            )

    async def stop(self) -> None:
        async with self._lock:
            tasks = list(self._tasks)
            self._tasks.clear()
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await BUS.publish_json(
            "pocketlab.events.live_status.stopped", "live_status.stopped", self.status()
        )

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def _loop(self, name: str, interval: float, sampler: Any) -> None:
        # Publish one sample immediately so the UI becomes live as soon as the API starts.
        while True:
            try:
                await sampler(source="sampler")
                self._errors.pop(name, None)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._errors[name] = str(exc)
                await BUS.publish_json(
                    f"pocketlab.events.live_status.{name}_error",
                    f"live_status.{name}_error",
                    {"component": name, "error": str(exc)},
                )
            await asyncio.sleep(max(1.0, interval))

    async def sample_telemetry(self, *, source: str = "manual") -> Dict[str, Any]:
        sample, _ = await WORKLOAD_ADMISSION.run(
            "system.telemetry_probe", deps.core.telemetry_snapshot
        )
        sample["sample_source"] = source
        sample["sampled_at"] = deps.now_utc_iso()
        changed = _telemetry_changed(
            self._last_telemetry, sample, self.telemetry_threshold
        )
        previous = self._last_telemetry
        self._last_telemetry = dict(sample)
        self._samples["telemetry"] += 1
        payload = {
            "sample": sample,
            "changed": changed,
            "source": source,
            "threshold": self.telemetry_threshold,
        }
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
        snapshot, _ = await WORKLOAD_ADMISSION.run(
            "system.health_probe", deps.core.build_health_engine_snapshot
        )
        snapshot["sample_source"] = source
        snapshot["sampled_at"] = deps.now_utc_iso()
        signature = _health_signature(snapshot)
        current_hash = _stable_hash(signature)
        changed = current_hash != self._last_health_hash
        previous_services = dict(self._last_health_services)
        services = snapshot.get("services") or {}
        current_services: Dict[str, str] = {}
        if isinstance(services, dict):
            for name, value in services.items():
                if isinstance(value, dict):
                    current_services[str(name)] = str(value.get("status") or "unknown")
                else:
                    current_services[str(name)] = str(value or "unknown")
        self._last_health_hash = current_hash
        self._last_health_services = current_services
        self._samples["health"] += 1
        payload = {
            "snapshot": snapshot,
            "status": snapshot.get("status"),
            "summary": snapshot.get("summary", {}),
            "source": snapshot.get("source"),
            "changed": changed,
        }
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
        from .fleet_registry import fleet_health_snapshot

        snapshot, _ = await WORKLOAD_ADMISSION.run(
            "system.fleet_probe", fleet_health_snapshot
        )
        snapshot["sample_source"] = source
        snapshot["sampled_at"] = deps.now_utc_iso()
        signature = _fleet_signature(snapshot)
        current_hash = _stable_hash(signature)
        changed = current_hash != self._last_fleet_hash
        self._last_fleet_hash = current_hash
        self._samples["fleet"] += 1
        payload = {"snapshot": snapshot, "changed": changed, "source": source}
        await BUS.publish_json(
            "pocketlab.events.fleet.health_sampled", "fleet.health_sampled", payload
        )
        if changed:
            await BUS.publish_json(
                "pocketlab.events.fleet.health_changed", "fleet.health_changed", payload
            )
        return snapshot

    async def sample_all(self, *, source: str = "manual") -> Dict[str, Any]:
        telemetry, health, fleet = await asyncio.gather(
            self.sample_telemetry(source=source),
            self.sample_health(source=source),
            self.sample_fleet(source=source),
        )
        return {
            "telemetry": telemetry,
            "health": health,
            "fleet": fleet,
            "sampled_at": deps.now_utc_iso(),
        }

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": any(not task.done() for task in self._tasks),
            "started_at": self._started_at,
            "intervals": {
                "telemetry_seconds": self.telemetry_interval,
                "health_seconds": self.health_interval,
                "fleet_seconds": self.fleet_interval,
            },
            "telemetry_change_threshold": self.telemetry_threshold,
            "samples": dict(self._samples),
            "errors": dict(self._errors),
            "bus": BUS.status(),
            "last_telemetry": self._last_telemetry,
            "last_health_services": dict(self._last_health_services),
        }


LIVE_STATUS = LiveStatusSampler()
