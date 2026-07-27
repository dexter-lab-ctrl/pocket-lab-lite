from __future__ import annotations

"""Adaptive runtime budgets for Pocket Lab Lite.

The controller is deliberately process-local and diagnostics-only. It keeps
bounded timing/size samples, makes conservative admission decisions, and
returns sanitized reasons. It never retains projection payloads, command
arguments, environment values, raw logs, or evidence contents.
"""

from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
import sys
import threading
import time
from time import monotonic as _monotonic
from typing import Any, Iterable


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _safe(value: Any, default: str = "unknown", maximum: int = 96) -> str:
    text = "".join(
        character if character.isalnum() or character in "._:-" else "_"
        for character in str(value or default).strip().lower()
    )
    return (text or default)[:maximum]




# Explicit semantic cadence policies for every prepared Phase 3 domain.
# Values are (active transition, stable reconciliation, maximum backoff) seconds.
# Environment overrides still control CPU/payload/allocation limits.
DOMAIN_CADENCE_SECONDS: dict[str, tuple[float, float, float]] = {
    "fleet.summary": (4.0, 300.0, 1_200.0),
    "apps.catalog": (5.0, 600.0, 3_600.0),
    "apps.lifecycle": (5.0, 600.0, 3_600.0),
    "apps.actions:photoprism": (5.0, 300.0, 1_800.0),
    "apps.update:photoprism": (8.0, 900.0, 3_600.0),
    "apps.backup:photoprism": (8.0, 900.0, 3_600.0),
    "recovery.summary": (8.0, 900.0, 3_600.0),
    "recovery.details": (15.0, 1_200.0, 3_600.0),
    "security.progress": (2.0, 120.0, 600.0),
    "security.summary": (5.0, 300.0, 1_800.0),
    "system.status": (5.0, 300.0, 1_800.0),
    "system.health": (5.0, 300.0, 1_800.0),
    "system.processes": (10.0, 600.0, 1_800.0),
    "system.agent": (5.0, 300.0, 1_200.0),
    "system.supervisor": (5.0, 300.0, 1_200.0),
    "system.remote_access": (10.0, 600.0, 1_800.0),
    "system.nats_remote": (3.0, 180.0, 900.0),
    "system.fleet_probe": (5.0, 300.0, 1_200.0),
    "system.telemetry_thresholds": (10.0, 600.0, 1_800.0),
    "system.storage_pressure": (15.0, 600.0, 1_800.0),
    "system.sqlite_health": (15.0, 900.0, 3_600.0),
    "system.activity_current": (2.0, 120.0, 600.0),
    "system.activity_history": (15.0, 900.0, 3_600.0),
    "system.activity_summary": (2.0, 120.0, 600.0),
}

def _termux_runtime() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "") or sys.platform == "android"


def _percentile(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(max(0.0, float(value)) for value in values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * max(0.0, min(1.0, percentile))
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


@dataclass(frozen=True, slots=True)
class AdaptivePolicy:
    active_interval_seconds: float
    stable_interval_seconds: float
    max_interval_seconds: float
    transition_hold_seconds: float
    short_cpu_budget_ms: float
    medium_cpu_budget_ms: float
    long_cpu_budget_ms: float
    payload_budget_bytes: int
    allocation_budget_bytes: int
    serialization_budget_ms: float
    critical: bool = False


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    accepted: bool
    reason: str
    retry_after_ms: int
    load_state: str
    cadence_state: str
    cpu_budget_remaining_ms: float


@dataclass(frozen=True, slots=True)
class PayloadAssessment:
    checksum: str
    payload_bytes: int
    serialization_ms: float
    allocation_estimate_bytes: int
    item_count: int
    within_budget: bool
    reason: str


@dataclass(slots=True)
class _Sample:
    at: float
    cpu_ms: float
    wall_ms: float
    queue_wait_ms: float
    payload_bytes: int
    serialization_ms: float
    allocation_bytes: int
    outcome: str


@dataclass(slots=True)
class _DomainRuntime:
    samples: deque[_Sample] = field(default_factory=lambda: deque(maxlen=256))
    cadence_state: str = "stable"
    load_state: str = "normal"
    next_due_at: float = 0.0
    active_until: float = 0.0
    last_change_at: float = 0.0
    last_result_at: float = 0.0
    consecutive_unchanged: int = 0
    admitted: int = 0
    deferred: int = 0
    rejected: int = 0
    budget_exhausted: int = 0
    pressure_deferred: int = 0
    queue_deferred: int = 0
    payload_deferred: int = 0
    last_reason: str = ""
    last_retry_after_ms: int = 0
    last_payload_bytes: int = 0
    last_serialization_ms: float = 0.0
    last_allocation_bytes: int = 0
    last_queue_wait_ms: float = 0.0
    last_cpu_ms: float = 0.0
    last_wall_ms: float = 0.0
    last_outcome: str = "never"


class AdaptiveRuntimeController:
    """Per-domain adaptive cadence, admission, and bounded metrics."""

    WINDOWS = (60.0, 300.0, 900.0)

    def __init__(self) -> None:
        termux = _termux_runtime()
        self.profile = "termux_arm64" if termux else "development"
        self.queue_depth_warning = _bounded_int(
            "POCKETLAB_ADAPTIVE_QUEUE_DEPTH_WARNING", 6 if termux else 10, 2, 128
        )
        self.queue_depth_critical = _bounded_int(
            "POCKETLAB_ADAPTIVE_QUEUE_DEPTH_CRITICAL", 12 if termux else 20, 4, 256
        )
        self.queue_lag_warning_ms = _bounded_float(
            "POCKETLAB_ADAPTIVE_QUEUE_LAG_WARNING_MS", 4_000.0, 100.0, 300_000.0
        )
        self.queue_lag_critical_ms = _bounded_float(
            "POCKETLAB_ADAPTIVE_QUEUE_LAG_CRITICAL_MS", 15_000.0, 500.0, 900_000.0
        )
        self.event_loop_warning_ms = _bounded_float(
            "POCKETLAB_ADAPTIVE_EVENT_LOOP_WARNING_MS", 120.0, 10.0, 10_000.0
        )
        self.event_loop_critical_ms = _bounded_float(
            "POCKETLAB_ADAPTIVE_EVENT_LOOP_CRITICAL_MS", 350.0, 25.0, 30_000.0
        )
        self.sample_limit = _bounded_int(
            "POCKETLAB_ADAPTIVE_SAMPLE_LIMIT", 256, 32, 2_048
        )
        self._lock = threading.RLock()
        self._domains: dict[str, _DomainRuntime] = {}
        self._policies: dict[str, AdaptivePolicy] = {}
        self._event_sizes: deque[tuple[float, int, str]] = deque(maxlen=256)
        self._event_oversize_rejections = 0
        self._global_admitted = 0
        self._global_deferred = 0
        self._global_rejected = 0

    @staticmethod
    def _base_policy(*, critical: bool = False, active: float = 5.0, stable: float = 300.0, maximum: float = 1_800.0) -> AdaptivePolicy:
        termux = _termux_runtime()
        factor = 1.0 if termux else 1.6
        cpu_short = 800.0 if critical else 320.0
        cpu_medium = 3_000.0 if critical else 1_150.0
        cpu_long = 7_500.0 if critical else 3_000.0
        return AdaptivePolicy(
            active_interval_seconds=max(1.0, active),
            stable_interval_seconds=max(active, stable),
            max_interval_seconds=max(stable, maximum),
            transition_hold_seconds=120.0 if critical else 90.0,
            short_cpu_budget_ms=cpu_short * factor,
            medium_cpu_budget_ms=cpu_medium * factor,
            long_cpu_budget_ms=cpu_long * factor,
            payload_budget_bytes=_bounded_int(
                "POCKETLAB_PROJECTION_PAYLOAD_BUDGET_BYTES", 512 * 1024, 32 * 1024, 8 * 1024 * 1024
            ),
            allocation_budget_bytes=_bounded_int(
                "POCKETLAB_PROJECTION_ALLOCATION_BUDGET_BYTES", 2 * 1024 * 1024, 128 * 1024, 32 * 1024 * 1024
            ),
            serialization_budget_ms=_bounded_float(
                "POCKETLAB_PROJECTION_SERIALIZATION_BUDGET_MS", 120.0 if termux else 180.0, 5.0, 5_000.0
            ),
            critical=critical,
        )

    def policy_for(self, domain: str, *, priority: int = 50, work_class: str = "io", optional: bool = True) -> AdaptivePolicy:
        safe_domain = _safe(domain)
        with self._lock:
            existing = self._policies.get(safe_domain)
            if existing is not None:
                return existing
        critical = not optional or work_class == "critical" or priority <= 20
        explicit = DOMAIN_CADENCE_SECONDS.get(safe_domain)
        if explicit is not None:
            active, stable, maximum = explicit
            policy = self._base_policy(
                critical=critical or safe_domain in {
                    "security.progress", "system.activity_current",
                    "system.activity_summary", "system.nats_remote",
                },
                active=active, stable=stable, maximum=maximum,
            )
        elif safe_domain.startswith("system.") or safe_domain.startswith("security."):
            policy = self._base_policy(critical=critical, active=5.0, stable=300.0, maximum=1_800.0)
        elif safe_domain.startswith("fleet"):
            policy = self._base_policy(critical=critical, active=4.0, stable=300.0, maximum=1_200.0)
        elif safe_domain.startswith("apps."):
            policy = self._base_policy(critical=critical, active=5.0, stable=600.0, maximum=3_600.0)
        elif safe_domain.startswith("recovery."):
            policy = self._base_policy(critical=critical, active=8.0, stable=900.0, maximum=3_600.0)
        else:
            policy = self._base_policy(critical=critical)
        with self._lock:
            self._policies[safe_domain] = policy
            runtime = self._domains.setdefault(safe_domain, _DomainRuntime())
            if runtime.samples.maxlen != self.sample_limit:
                runtime.samples = deque(runtime.samples, maxlen=self.sample_limit)
        return policy

    def mark_dirty(self, domain: str, *, active_hint: bool = True) -> None:
        safe_domain = _safe(domain)
        now = _monotonic()
        policy = self.policy_for(safe_domain)
        with self._lock:
            runtime = self._domains.setdefault(safe_domain, _DomainRuntime())
            if active_hint:
                runtime.active_until = max(runtime.active_until, now + policy.transition_hold_seconds)
                runtime.cadence_state = "active_transition"
            runtime.next_due_at = 0.0

    def _window_cpu(self, runtime: _DomainRuntime, window_seconds: float, now: float) -> float:
        return sum(sample.cpu_ms for sample in runtime.samples if now - sample.at <= window_seconds)

    def _budget_remaining(self, runtime: _DomainRuntime, policy: AdaptivePolicy, now: float) -> float:
        remaining = (
            policy.short_cpu_budget_ms - self._window_cpu(runtime, 60.0, now),
            policy.medium_cpu_budget_ms - self._window_cpu(runtime, 300.0, now),
            policy.long_cpu_budget_ms - self._window_cpu(runtime, 900.0, now),
        )
        return min(remaining)

    def decide(
        self,
        domain: str,
        *,
        priority: int,
        work_class: str,
        optional: bool,
        queue_depth: int,
        queue_age_ms: float,
        active_count: int,
        capacity: int,
        event_loop_lag_ms: float = 0.0,
        external_pressure_reason: str = "",
    ) -> AdmissionDecision:
        safe_domain = _safe(domain)
        policy = self.policy_for(
            safe_domain, priority=priority, work_class=work_class, optional=optional
        )
        now = _monotonic()
        with self._lock:
            runtime = self._domains.setdefault(safe_domain, _DomainRuntime())
            remaining = self._budget_remaining(runtime, policy, now)
            load_state = "normal"
            reason = ""
            retry_ms = 0
            if queue_depth >= self.queue_depth_critical or queue_age_ms >= self.queue_lag_critical_ms or event_loop_lag_ms >= self.event_loop_critical_ms:
                load_state = "critical"
            elif queue_depth >= self.queue_depth_warning or queue_age_ms >= self.queue_lag_warning_ms or event_loop_lag_ms >= self.event_loop_warning_ms:
                load_state = "elevated"
            if external_pressure_reason:
                load_state = "critical" if external_pressure_reason in {"low_storage", "sqlite_maintenance"} else "elevated"
            runtime.load_state = load_state

            # Preserve the most actionable current pressure reason. CPU budget
            # state remains visible in diagnostics, but an active event-loop,
            # storage, memory, or maintenance pressure signal should not be
            # hidden behind a historical rolling-window exhaustion reason.
            if optional and external_pressure_reason:
                reason = _safe(external_pressure_reason)
                retry_ms = 10_000 if load_state == "critical" else 5_000
                runtime.pressure_deferred += 1
            elif optional and remaining <= 0.0:
                reason = "cpu_budget_exhausted"
                retry_ms = 15_000 if load_state == "normal" else 30_000
                runtime.budget_exhausted += 1
            elif optional and load_state == "critical":
                reason = "system_pressure"
                retry_ms = 10_000
                runtime.pressure_deferred += 1
            elif optional and active_count >= max(1, capacity):
                reason = "worker_capacity"
                retry_ms = 1_000
                runtime.queue_deferred += 1
            elif optional and queue_depth >= self.queue_depth_warning and priority >= 50:
                reason = "queue_pressure"
                retry_ms = 5_000
                runtime.queue_deferred += 1

            accepted = not reason
            if accepted:
                runtime.admitted += 1
                self._global_admitted += 1
            else:
                runtime.deferred += 1
                self._global_deferred += 1
                runtime.last_reason = reason
                runtime.last_retry_after_ms = retry_ms
            cadence_state = runtime.cadence_state
            return AdmissionDecision(
                accepted=accepted,
                reason=reason,
                retry_after_ms=retry_ms,
                load_state=load_state,
                cadence_state=cadence_state,
                cpu_budget_remaining_ms=round(remaining, 2),
            )

    def _interval(self, domain: str, runtime: _DomainRuntime, policy: AdaptivePolicy, now: float) -> float:
        if runtime.load_state == "critical":
            runtime.cadence_state = "degraded"
            return min(policy.max_interval_seconds, max(policy.stable_interval_seconds, 300.0))
        if runtime.active_until > now:
            runtime.cadence_state = "active_transition"
            return policy.active_interval_seconds
        if runtime.consecutive_unchanged >= 4:
            multiplier = min(4.0, 1.0 + (runtime.consecutive_unchanged - 3) * 0.5)
            runtime.cadence_state = "stable"
            return min(policy.max_interval_seconds, policy.stable_interval_seconds * multiplier)
        if runtime.last_change_at and now - runtime.last_change_at < policy.transition_hold_seconds:
            runtime.cadence_state = "recently_changed"
            return min(policy.stable_interval_seconds, max(policy.active_interval_seconds * 3.0, 15.0))
        runtime.cadence_state = "stable"
        return policy.stable_interval_seconds

    @staticmethod
    def _jitter(domain: str, interval: float) -> float:
        digest = hashlib.sha256(domain.encode("utf-8")).digest()
        fraction = int.from_bytes(digest[:2], "big") / 65535.0
        return interval * (0.96 + fraction * 0.08)

    def record_result(
        self,
        domain: str,
        *,
        cpu_ms: float,
        wall_ms: float,
        queue_wait_ms: float,
        payload_bytes: int = 0,
        serialization_ms: float = 0.0,
        allocation_bytes: int = 0,
        outcome: str,
        changed: bool | None,
        active_transition: bool = False,
    ) -> None:
        safe_domain = _safe(domain)
        now = _monotonic()
        policy = self.policy_for(safe_domain)
        with self._lock:
            runtime = self._domains.setdefault(safe_domain, _DomainRuntime())
            runtime.samples.append(
                _Sample(
                    at=now,
                    cpu_ms=max(0.0, float(cpu_ms)),
                    wall_ms=max(0.0, float(wall_ms)),
                    queue_wait_ms=max(0.0, float(queue_wait_ms)),
                    payload_bytes=max(0, int(payload_bytes)),
                    serialization_ms=max(0.0, float(serialization_ms)),
                    allocation_bytes=max(0, int(allocation_bytes)),
                    outcome=_safe(outcome, maximum=40),
                )
            )
            runtime.last_result_at = now
            runtime.last_cpu_ms = max(0.0, float(cpu_ms))
            runtime.last_wall_ms = max(0.0, float(wall_ms))
            runtime.last_queue_wait_ms = max(0.0, float(queue_wait_ms))
            runtime.last_payload_bytes = max(0, int(payload_bytes))
            runtime.last_serialization_ms = max(0.0, float(serialization_ms))
            runtime.last_allocation_bytes = max(0, int(allocation_bytes))
            runtime.last_outcome = _safe(outcome, maximum=40)
            if changed is True:
                runtime.last_change_at = now
                runtime.consecutive_unchanged = 0
                runtime.active_until = max(runtime.active_until, now + policy.transition_hold_seconds)
            elif changed is False:
                runtime.consecutive_unchanged += 1
            if active_transition:
                runtime.active_until = max(runtime.active_until, now + policy.transition_hold_seconds)
            interval = self._interval(safe_domain, runtime, policy, now)
            runtime.next_due_at = now + self._jitter(safe_domain, interval)

    def defer_payload(self, domain: str, reason: str, retry_after_ms: int = 30_000) -> None:
        safe_domain = _safe(domain)
        with self._lock:
            runtime = self._domains.setdefault(safe_domain, _DomainRuntime())
            runtime.payload_deferred += 1
            runtime.deferred += 1
            runtime.last_reason = _safe(reason)
            runtime.last_retry_after_ms = max(1_000, int(retry_after_ms))
            runtime.load_state = "elevated"
            runtime.next_due_at = _monotonic() + runtime.last_retry_after_ms / 1000.0
            self._global_deferred += 1

    def next_due_seconds(self, registered_domains: Iterable[str]) -> float | None:
        now = _monotonic()
        with self._lock:
            deadlines = [
                runtime.next_due_at
                for raw in registered_domains
                if (runtime := self._domains.get(_safe(raw))) is not None
                and runtime.next_due_at > 0.0
            ]
        if not deadlines:
            return None
        return max(0.0, min(deadlines) - now)

    def due_domains(self, registered_domains: Iterable[str]) -> list[str]:
        now = _monotonic()
        due: list[str] = []
        with self._lock:
            for raw in registered_domains:
                domain = _safe(raw)
                runtime = self._domains.get(domain)
                if runtime is None or runtime.next_due_at <= 0.0:
                    continue
                if runtime.next_due_at <= now:
                    due.append(domain)
                    runtime.next_due_at = 0.0
        return due

    @staticmethod
    def _estimate_size(value: Any, *, node_limit: int = 20_000) -> tuple[int, int]:
        total = 0
        count = 0
        stack = [value]
        seen: set[int] = set()
        while stack and count < node_limit:
            item = stack.pop()
            identity = id(item)
            if identity in seen:
                continue
            seen.add(identity)
            count += 1
            try:
                total += sys.getsizeof(item)
            except TypeError:
                pass
            if isinstance(item, dict):
                stack.extend(item.keys())
                stack.extend(item.values())
            elif isinstance(item, (list, tuple, set, frozenset, deque)):
                stack.extend(item)
        return max(0, total), count

    def assess_payload(self, domain: str, payload: dict[str, Any]) -> PayloadAssessment:
        policy = self.policy_for(domain)
        started = _monotonic()
        material = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
        serialization_ms = max(0.0, (_monotonic() - started) * 1000.0)
        allocation_bytes, item_count = self._estimate_size(payload)
        payload_bytes = len(material)
        reason = ""
        if payload_bytes > policy.payload_budget_bytes:
            reason = "payload_budget_exceeded"
        elif allocation_bytes > policy.allocation_budget_bytes:
            reason = "allocation_budget_exceeded"
        elif serialization_ms > policy.serialization_budget_ms:
            reason = "serialization_budget_exceeded"
        return PayloadAssessment(
            checksum=hashlib.sha256(material).hexdigest(),
            payload_bytes=payload_bytes,
            serialization_ms=round(serialization_ms, 3),
            allocation_estimate_bytes=allocation_bytes,
            item_count=item_count,
            within_budget=not reason,
            reason=reason,
        )

    def record_event_size(self, *, subject: str, payload_bytes: int, accepted: bool) -> None:
        safe_subject = _safe(subject, maximum=120)
        with self._lock:
            self._event_sizes.append((_monotonic(), max(0, int(payload_bytes)), safe_subject))
            if not accepted:
                self._event_oversize_rejections += 1

    def domain_status(self, domain: str) -> dict[str, Any]:
        safe_domain = _safe(domain)
        now = _monotonic()
        policy = self.policy_for(safe_domain)
        with self._lock:
            runtime = self._domains.setdefault(safe_domain, _DomainRuntime())
            samples = list(runtime.samples)
            remaining = self._budget_remaining(runtime, policy, now)
            cpu = [sample.cpu_ms for sample in samples]
            wall = [sample.wall_ms for sample in samples]
            queue = [sample.queue_wait_ms for sample in samples]
            payload = [float(sample.payload_bytes) for sample in samples]
            serialization = [sample.serialization_ms for sample in samples]
            allocation = [float(sample.allocation_bytes) for sample in samples]
            return {
                "cadence_state": runtime.cadence_state,
                "load_state": runtime.load_state,
                "next_reconciliation_seconds": max(0, int(runtime.next_due_at - now + 0.999)) if runtime.next_due_at else 0,
                "active_transition_seconds": max(0, int(runtime.active_until - now + 0.999)),
                "consecutive_unchanged": runtime.consecutive_unchanged,
                "cpu_budget_remaining_ms": round(remaining, 2),
                "cpu_budget_exhausted": remaining <= 0.0,
                "short_cpu_used_ms": round(self._window_cpu(runtime, 60.0, now), 2),
                "medium_cpu_used_ms": round(self._window_cpu(runtime, 300.0, now), 2),
                "long_cpu_used_ms": round(self._window_cpu(runtime, 900.0, now), 2),
                "budgets_ms": {
                    "short_60s": round(policy.short_cpu_budget_ms, 2),
                    "medium_300s": round(policy.medium_cpu_budget_ms, 2),
                    "long_900s": round(policy.long_cpu_budget_ms, 2),
                },
                "cadence_intervals_seconds": {
                    "active": policy.active_interval_seconds,
                    "stable": policy.stable_interval_seconds,
                    "maximum": policy.max_interval_seconds,
                    "transition_hold": policy.transition_hold_seconds,
                },
                "critical_reserve": policy.critical,
                "payload_budget_bytes": policy.payload_budget_bytes,
                "allocation_budget_bytes": policy.allocation_budget_bytes,
                "serialization_budget_ms": policy.serialization_budget_ms,
                "admitted": runtime.admitted,
                "deferred": runtime.deferred,
                "rejected": runtime.rejected,
                "budget_exhausted_count": runtime.budget_exhausted,
                "pressure_deferred_count": runtime.pressure_deferred,
                "queue_deferred_count": runtime.queue_deferred,
                "payload_deferred_count": runtime.payload_deferred,
                "last_reason": runtime.last_reason,
                "last_retry_after_ms": runtime.last_retry_after_ms,
                "sample_count": len(samples),
                "cpu_ms": self._distribution(cpu),
                "wall_ms": self._distribution(wall),
                "queue_wait_ms": self._distribution(queue),
                "payload_bytes": self._distribution(payload),
                "serialization_ms": self._distribution(serialization),
                "allocation_bytes": self._distribution(allocation),
                "last": {
                    "outcome": runtime.last_outcome,
                    "cpu_ms": round(runtime.last_cpu_ms, 2),
                    "wall_ms": round(runtime.last_wall_ms, 2),
                    "queue_wait_ms": round(runtime.last_queue_wait_ms, 2),
                    "payload_bytes": runtime.last_payload_bytes,
                    "serialization_ms": round(runtime.last_serialization_ms, 2),
                    "allocation_bytes": runtime.last_allocation_bytes,
                },
                "sanitized": True,
            }

    @staticmethod
    def _distribution(values: list[float]) -> dict[str, float | int]:
        return {
            "count": len(values),
            "p50": round(_percentile(values, 0.50), 2),
            "p95": round(_percentile(values, 0.95), 2),
            "p99": round(_percentile(values, 0.99), 2),
            "max": round(max(values) if values else 0.0, 2),
        }

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            domains = sorted(set(self._domains) | set(self._policies))
            event_sizes = [float(item[1]) for item in self._event_sizes]
            event_subjects = len({item[2] for item in self._event_sizes})
            oversize = self._event_oversize_rejections
            admitted = self._global_admitted
            deferred = self._global_deferred
            rejected = self._global_rejected
        return {
            "profile": self.profile,
            "windows_seconds": [60, 300, 900],
            "queue_thresholds": {
                "warning_depth": self.queue_depth_warning,
                "critical_depth": self.queue_depth_critical,
                "warning_lag_ms": self.queue_lag_warning_ms,
                "critical_lag_ms": self.queue_lag_critical_ms,
            },
            "event_loop_thresholds_ms": {
                "warning": self.event_loop_warning_ms,
                "critical": self.event_loop_critical_ms,
            },
            "admitted": admitted,
            "deferred": deferred,
            "rejected": rejected,
            "event_payloads": {
                **self._distribution(event_sizes),
                "subjects": event_subjects,
                "oversize_rejections": oversize,
            },
            "domains": {domain: self.domain_status(domain) for domain in domains},
            "sanitized": True,
        }


ADAPTIVE_RUNTIME = AdaptiveRuntimeController()
