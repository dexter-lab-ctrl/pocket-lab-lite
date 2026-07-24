from __future__ import annotations

"""Bounded cross-domain prepared-projection scheduling for Lite control-plane reads.

Request handlers only mark a domain dirty. Collectors run here under conservative
Termux-safe limits, and projector callbacks commit through the existing single
SQLite writer. Payload contents are never retained in diagnostics.
"""

import concurrent.futures
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import heapq
import json
import logging
import os
import re
import shutil
import threading
import time
from typing import Any, Callable, Literal

from ..db.connection import database_path
from ..db.runtime import SQLITE_WRITER, SQLiteWriteDeadlineExceeded, SQLiteWriteRejected
from .runtime_diagnostics import RUNTIME_DIAGNOSTICS
from .idle_efficiency import IDLE_EFFICIENCY
from .hot_path_profiler import HOT_PATH_PROFILER

_LOGGER = logging.getLogger(__name__)
WorkClass = Literal["critical", "io", "cpu"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_ms() -> int:
    return int(time.time() * 1000)


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _safe_domain(value: str) -> str:
    return re.sub(r"[^a-z0-9_.:-]+", "-", str(value or "").strip().lower())[:96]


@dataclass(frozen=True, slots=True)
class ProjectionJob:
    domain: str
    builder: Callable[[], dict[str, Any]]
    projector: Callable[[dict[str, Any]], int]
    priority: int
    work_class: WorkClass
    deadline_seconds: float
    optional: bool = True
    source_revision: Callable[[], int] | None = None
    on_unchanged: Callable[[], None] | None = None
    max_probe_seconds: float = 900.0


@dataclass(slots=True)
class _DomainState:
    generation: int = 0
    committed_generation: int = 0
    dirty: bool = False
    queued: bool = False
    active: bool = False
    priority: int = 50
    work_class: WorkClass = "io"
    failure_count: int = 0
    next_retry_at: float = 0.0
    coalesced_count: int = 0
    late_result_count: int = 0
    stale_generation_count: int = 0
    enqueued_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    last_started_iso: str = ""
    last_completed_iso: str = ""
    next_retry_epoch_ms: int = 0
    last_duration_ms: float = 0.0
    last_error_type: str = ""
    last_pressure_reason: str = ""
    database_instance: str = ""
    last_payload_checksum: str = ""
    last_source_revision: int = -1
    last_full_probe_at: float = 0.0
    unchanged_count: int = 0
    execution_count: int = 0
    committed_count: int = 0
    circuit_open_count: int = 0
    last_persisted_checksum: str = ""


class ProjectionScheduler:
    """One process-local scheduler with one coalesced item per domain."""

    def __init__(self) -> None:
        termux = "com.termux" in os.environ.get("PREFIX", "")
        self.io_workers = _bounded_int(
            "POCKETLAB_LITE_PROJECTION_IO_WORKERS", 2 if not termux else 2, 1, 4
        )
        self.cpu_workers = _bounded_int(
            "POCKETLAB_LITE_PROJECTION_CPU_WORKERS", 1, 1, 2
        )
        self.max_domains = _bounded_int(
            "POCKETLAB_LITE_PROJECTION_MAX_DOMAINS", 16, 8, 64
        )
        self.critical_lag_ms = float(
            _bounded_int("POCKETLAB_LITE_PROJECTION_CRITICAL_LAG_MS", 250, 50, 5000)
        )
        self.circuit_failure_threshold = _bounded_int(
            "POCKETLAB_LITE_PROJECTION_CIRCUIT_FAILURES", 3, 2, 8
        )
        self.circuit_cooldown_seconds = float(_bounded_int(
            "POCKETLAB_LITE_PROJECTION_CIRCUIT_COOLDOWN_SECONDS", 300, 30, 3600
        ))
        self.idle_wait_seconds = float(_bounded_int(
            "POCKETLAB_LITE_PROJECTION_IDLE_WAIT_SECONDS", 60, 1, 300
        ))
        self._condition = threading.Condition(threading.RLock())
        self._states: dict[str, _DomainState] = {}
        self._jobs: dict[str, ProjectionJob] = {}
        self._heap: list[tuple[int, int, str, int]] = []
        self._sequence = 0
        self._dispatcher: threading.Thread | None = None
        self._io_executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._cpu_executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._active_futures: dict[concurrent.futures.Future[Any], tuple[str, int]] = {}
        self._accepting = False
        self._shutdown = False
        self._startup_complete = False
        self._event_signal_count = 0

    @staticmethod
    def _database_instance() -> str:
        path = database_path()
        try:
            stat = path.stat()
            return f"{path}:{stat.st_dev}:{stat.st_ino}"
        except OSError:
            return f"{path}:missing"

    @staticmethod
    def _retry_delay(domain: str, failure_count: int) -> float:
        base = (60.0, 120.0, 300.0)[min(max(failure_count, 1) - 1, 2)]
        digest = hashlib.sha256(f"{domain}:{failure_count}".encode("utf-8")).digest()
        jitter = int.from_bytes(digest[:2], "big") / 65535.0 * 0.08
        return min(324.0, base * (1.0 + jitter))

    def start(self) -> bool:
        with self._condition:
            if self._dispatcher is not None and self._dispatcher.is_alive():
                self._accepting = True
                self._startup_complete = True
                return False
            self._shutdown = False
            self._accepting = True
            self._startup_complete = True
            self._io_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.io_workers,
                thread_name_prefix="pocketlab-projection-io",
            )
            self._cpu_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.cpu_workers,
                thread_name_prefix="pocketlab-projection-cpu",
            )
            self._dispatcher = threading.Thread(
                target=self._dispatch_loop,
                name="pocketlab-projection-scheduler",
                daemon=True,
            )
            self._dispatcher.start()
            return True

    def register(self, job: ProjectionJob) -> None:
        domain = _safe_domain(job.domain)
        if not domain:
            raise ValueError("projection domain is required")
        if not 0 <= int(job.priority) <= 100:
            raise ValueError("projection priority must be between 0 and 100")
        if job.work_class not in {"critical", "io", "cpu"}:
            raise ValueError("invalid projection work class")
        with self._condition:
            if domain not in self._states and len(self._states) >= self.max_domains:
                raise RuntimeError("projection scheduler domain capacity reached")
            self._jobs[domain] = ProjectionJob(
                domain=domain,
                builder=job.builder,
                projector=job.projector,
                priority=int(job.priority),
                work_class=job.work_class,
                deadline_seconds=max(0.1, min(float(job.deadline_seconds), 300.0)),
                optional=bool(job.optional),
                source_revision=job.source_revision,
                on_unchanged=job.on_unchanged,
                max_probe_seconds=max(5.0, min(float(job.max_probe_seconds), 86_400.0)),
            )
            self._states.setdefault(domain, _DomainState())

    def mark_dirty(
        self,
        domain: str,
        *,
        job: ProjectionJob | None = None,
        priority: int | None = None,
        force_followup: bool = True,
    ) -> dict[str, Any]:
        if job is not None:
            self.register(job)
        safe_domain = _safe_domain(domain)
        with self._condition:
            if self._shutdown:
                return {
                    "accepted": False,
                    "refresh_pending": False,
                    "retry_after_seconds": 0,
                    "reason": "shutdown",
                }
        self.start()
        with self._condition:
            if not self._accepting or self._shutdown:
                return {
                    "accepted": False,
                    "refresh_pending": False,
                    "retry_after_seconds": 0,
                    "reason": "shutdown",
                }
            registered = self._jobs.get(safe_domain)
            state = self._states.get(safe_domain)
            if registered is None or state is None:
                return {
                    "accepted": False,
                    "refresh_pending": False,
                    "retry_after_seconds": 0,
                    "reason": "unregistered_domain",
                }
            was_pending = bool(state.queued or state.active)
            requested_priority = registered.priority if priority is None else max(0, min(int(priority), 100))
            prior_priority = state.priority
            state.priority = min(state.priority, requested_priority) if was_pending else requested_priority
            state.work_class = registered.work_class

            if was_pending and not force_followup:
                # Prepared-read polling is only a refresh hint. Do not invalidate an
                # in-flight generation: doing so creates an endless build/discard
                # loop when clients poll faster than a collector can complete.
                state.coalesced_count += 1
                if state.queued and state.priority < prior_priority:
                    self._heap = [item for item in self._heap if item[2] != safe_domain]
                    heapq.heapify(self._heap)
                    state.queued = False
                    self._enqueue_locked(safe_domain, state)
            else:
                state.generation += 1
                state.dirty = True
                if was_pending:
                    state.coalesced_count += 1
                    if state.queued and state.priority < prior_priority:
                        self._heap = [item for item in self._heap if item[2] != safe_domain]
                        heapq.heapify(self._heap)
                        state.queued = False
                        self._enqueue_locked(safe_domain, state)
                else:
                    self._enqueue_locked(safe_domain, state)
            retry_after = max(0, int(state.next_retry_at - time.monotonic() + 0.999))
            # Dirty signalling is request-path safe: do not synchronously write
            # scheduler diagnostics here. The background dispatcher persists the
            # coalesced state after admission.
            self._condition.notify_all()
            return {
                "accepted": True,
                "refresh_pending": True,
                "generation": state.generation,
                "retry_after_seconds": retry_after,
                "coalesced": was_pending,
            }

    def mark_registered_prefix_dirty(
        self,
        domain_prefix: str,
        *,
        priority: int | None = None,
    ) -> int:
        """Fan one trusted state-change signal into registered projection jobs.

        The method is intentionally prefix-scoped and only touches jobs already
        registered by backend-owned prepared reads. It does not execute work on
        the caller thread and does not create arbitrary domains.
        """
        prefix = _safe_domain(domain_prefix).rstrip(".")
        if not prefix:
            return 0
        with self._condition:
            domains = [
                domain for domain in self._jobs
                if domain == prefix or domain.startswith(f"{prefix}.")
            ]
            self._event_signal_count += len(domains)
        accepted = 0
        for domain in domains:
            result = self.mark_dirty(
                domain,
                priority=priority,
                force_followup=True,
            )
            if result.get("accepted"):
                accepted += 1
        return accepted

    def _enqueue_locked(self, domain: str, state: _DomainState) -> None:
        if state.queued or state.active:
            return
        state.queued = True
        state.enqueued_at = time.monotonic()
        self._sequence += 1
        heapq.heappush(
            self._heap,
            (int(state.priority), self._sequence, domain, int(state.generation)),
        )

    def _pressure_reason(self, job: ProjectionJob) -> str:
        if job.work_class == "critical":
            return ""
        if not self._startup_complete:
            return "startup_incomplete"
        try:
            if RUNTIME_DIAGNOSTICS.latest_event_loop_lag_ms() >= self.critical_lag_ms:
                return "event_loop_pressure"
        except Exception:
            pass
        try:
            governor_reason = IDLE_EFFICIENCY.pressure_reason()
            if governor_reason:
                return governor_reason
        except Exception:
            pass
        try:
            from . import lite_security_maintenance

            if lite_security_maintenance.maintenance_state().get("active"):
                return "sqlite_maintenance"
            if job.priority >= 60 and lite_security_maintenance.active_security_scan():
                return "active_security_operation"
        except Exception:
            pass
        try:
            usage = shutil.disk_usage(database_path().parent)
            minimum_free = max(64 * 1024 * 1024, int(usage.total * 0.02))
            if usage.free < minimum_free:
                return "low_storage"
        except OSError:
            pass
        return ""

    def _executor_for(self, work_class: WorkClass) -> concurrent.futures.ThreadPoolExecutor | None:
        return self._cpu_executor if work_class == "cpu" else self._io_executor

    def _active_count_locked(self, work_class: WorkClass) -> int:
        count = 0
        for future, (domain, _generation) in self._active_futures.items():
            if future.done():
                continue
            job = self._jobs.get(domain)
            if job and ((work_class == "cpu" and job.work_class == "cpu") or (work_class != "cpu" and job.work_class != "cpu")):
                count += 1
        return count

    def _dispatch_loop(self) -> None:
        while True:
            with self._condition:
                self._reap_done_locked()
                if self._shutdown:
                    return
                if not self._heap:
                    # Interruptible monotonic sleep: no fixed 250 ms wake-up while idle.
                    self._condition.wait(timeout=self.idle_wait_seconds)
                    continue
                priority, sequence, domain, queued_generation = heapq.heappop(self._heap)
                state = self._states.get(domain)
                job = self._jobs.get(domain)
                if state is None or job is None:
                    continue
                state.queued = False
                if state.active or not state.dirty or queued_generation > state.generation:
                    continue
                now = time.monotonic()
                if now < state.next_retry_at:
                    self._enqueue_locked(domain, state)
                    self._condition.wait(
                        timeout=min(self.idle_wait_seconds, state.next_retry_at - now)
                    )
                    continue
                pressure = self._pressure_reason(job)
                if pressure and job.optional:
                    state.last_pressure_reason = pressure
                    state.next_retry_at = max(state.next_retry_at, now + 5.0)
                    state.next_retry_epoch_ms = _epoch_ms() + max(
                        0, int((state.next_retry_at - now) * 1000)
                    )
                    self._enqueue_locked(domain, state)
                    self._persist_state_best_effort(domain, state)
                    continue
                capacity = self.cpu_workers if job.work_class == "cpu" else self.io_workers
                if self._active_count_locked(job.work_class) >= capacity:
                    self._enqueue_locked(domain, state)
                    # Future completion wakes the dispatcher. Keep only a bounded
                    # safety timeout instead of spinning at 20 Hz.
                    self._condition.wait(timeout=1.0)
                    continue
                executor = self._executor_for(job.work_class)
                if executor is None:
                    state.last_error_type = "ExecutorUnavailable"
                    state.failure_count += 1
                    state.next_retry_at = now + self._retry_delay(domain, state.failure_count)
                    state.next_retry_epoch_ms = _epoch_ms() + max(
                        0, int((state.next_retry_at - now) * 1000)
                    )
                    self._enqueue_locked(domain, state)
                    continue
                generation = state.generation
                state.active = True
                state.started_at = now
                state.last_started_iso = _utc_now()
                state.database_instance = self._database_instance()
                state.last_pressure_reason = ""
                try:
                    future = executor.submit(self._execute_profiled, job, generation, state.database_instance)
                except RuntimeError:
                    state.active = False
                    state.last_error_type = "ExecutorRejected"
                    state.failure_count += 1
                    state.next_retry_at = now + self._retry_delay(domain, state.failure_count)
                    state.next_retry_epoch_ms = _epoch_ms() + max(
                        0, int((state.next_retry_at - now) * 1000)
                    )
                    self._enqueue_locked(domain, state)
                    continue
                self._active_futures[future] = (domain, generation)
                future.add_done_callback(lambda _future: self._wake_dispatcher())
                self._persist_state_best_effort(domain, state)

    def _wake_dispatcher(self) -> None:
        with self._condition:
            self._condition.notify_all()

    @staticmethod
    def _payload_checksum(payload: dict[str, Any]) -> str:
        try:
            material = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), default=str
            )
        except (TypeError, ValueError):
            material = repr(payload)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _execute_profiled(self, job: ProjectionJob, generation: int, database_instance: str) -> dict[str, Any]:
        with HOT_PATH_PROFILER.measure(f"projection.{job.domain}") as hot_path:
            result = self._execute(job, generation, database_instance)
            outcome = str(result.get("outcome") or "completed")
            hot_path["outcome"] = outcome
            hot_path["changed"] = True if outcome == "committed" else False if outcome in {"unchanged", "source_unchanged"} else None
            if outcome == "source_unchanged":
                HOT_PATH_PROFILER.increment(f"projection.{job.domain}", "skipped_unchanged")
            return result

    def _execute(self, job: ProjectionJob, generation: int, database_instance: str) -> dict[str, Any]:
        started = time.monotonic()
        source_revision: int | None = None
        with self._condition:
            state = self._states.get(job.domain)
            prior_source_revision = state.last_source_revision if state is not None else -1
            last_full_probe_at = state.last_full_probe_at if state is not None else 0.0
        if job.source_revision is not None:
            source_revision = int(job.source_revision())
            within_probe_window = (
                last_full_probe_at > 0.0
                and time.monotonic() - last_full_probe_at < job.max_probe_seconds
            )
            if prior_source_revision >= 0 and source_revision == prior_source_revision and within_probe_window:
                if job.on_unchanged is not None:
                    job.on_unchanged()
                return {
                    "outcome": "source_unchanged",
                    "duration_ms": (time.monotonic() - started) * 1000.0,
                    "generation": generation,
                    "database_instance": database_instance,
                    "source_revision": source_revision,
                }

        payload = job.builder()
        build_duration = time.monotonic() - started
        if not isinstance(payload, dict):
            raise TypeError("projection builder must return a mapping")
        if build_duration > job.deadline_seconds:
            return {
                "outcome": "late",
                "duration_ms": build_duration * 1000.0,
                "generation": generation,
                "database_instance": database_instance,
                "source_revision": source_revision,
            }
        if self._database_instance() != database_instance:
            return {
                "outcome": "database_changed",
                "duration_ms": build_duration * 1000.0,
                "generation": generation,
                "database_instance": database_instance,
                "source_revision": source_revision,
            }
        checksum = self._payload_checksum(payload)
        with self._condition:
            state = self._states.get(job.domain)
            if state is None or state.generation != generation or self._shutdown:
                return {
                    "outcome": "stale_generation",
                    "duration_ms": build_duration * 1000.0,
                    "generation": generation,
                    "database_instance": database_instance,
                    "source_revision": source_revision,
                }
            unchanged = bool(
                state.last_payload_checksum and state.last_payload_checksum == checksum
            )
        if unchanged:
            if job.on_unchanged is not None:
                job.on_unchanged()
            return {
                "outcome": "unchanged",
                "duration_ms": (time.monotonic() - started) * 1000.0,
                "generation": generation,
                "database_instance": database_instance,
                "payload_checksum": checksum,
                "source_revision": source_revision,
            }
        revision = int(job.projector(payload))
        if job.source_revision is not None:
            try:
                source_revision = int(job.source_revision())
            except Exception:
                pass
        return {
            "outcome": "committed",
            "revision": revision,
            "duration_ms": (time.monotonic() - started) * 1000.0,
            "generation": generation,
            "database_instance": database_instance,
            "payload_checksum": checksum,
            "source_revision": source_revision,
        }

    def _reap_done_locked(self) -> None:
        for future, (domain, generation) in list(self._active_futures.items()):
            if not future.done():
                continue
            self._active_futures.pop(future, None)
            state = self._states.get(domain)
            if state is None:
                continue
            state.active = False
            state.completed_at = time.monotonic()
            state.last_completed_iso = _utc_now()
            state.execution_count += 1
            try:
                result = future.result()
                outcome = str(result.get("outcome") or "unknown")
                state.last_duration_ms = float(result.get("duration_ms") or 0.0)
                if outcome == "committed":
                    state.committed_generation = max(state.committed_generation, generation)
                    state.failure_count = 0
                    state.next_retry_at = 0.0
                    state.next_retry_epoch_ms = 0
                    state.last_error_type = ""
                    state.dirty = state.generation > generation
                    state.committed_count += 1
                    state.last_payload_checksum = str(result.get("payload_checksum") or state.last_payload_checksum)
                    if result.get("source_revision") is not None:
                        state.last_source_revision = int(result["source_revision"])
                    state.last_full_probe_at = state.completed_at
                elif outcome in {"unchanged", "source_unchanged"}:
                    state.committed_generation = max(state.committed_generation, generation)
                    state.failure_count = 0
                    state.next_retry_at = 0.0
                    state.next_retry_epoch_ms = 0
                    state.last_error_type = ""
                    state.dirty = state.generation > generation
                    state.unchanged_count += 1
                    if result.get("payload_checksum"):
                        state.last_payload_checksum = str(result["payload_checksum"])
                    if result.get("source_revision") is not None:
                        state.last_source_revision = int(result["source_revision"])
                    if outcome == "unchanged":
                        state.last_full_probe_at = state.completed_at
                elif outcome == "stale_generation":
                    state.stale_generation_count += 1
                    state.dirty = True
                elif outcome in {"late", "database_changed"}:
                    if outcome == "late":
                        state.late_result_count += 1
                    else:
                        state.stale_generation_count += 1
                    state.failure_count = min(8, state.failure_count + 1)
                    delay = self._retry_delay(domain, state.failure_count)
                    if state.failure_count >= self.circuit_failure_threshold:
                        delay = max(delay, self.circuit_cooldown_seconds)
                        state.circuit_open_count += 1
                    retry_now = time.monotonic()
                    state.next_retry_at = retry_now + delay
                    state.next_retry_epoch_ms = _epoch_ms() + int(delay * 1000)
                    state.last_error_type = "DeadlineExceeded" if outcome == "late" else "DatabaseGenerationMismatch"
                    state.dirty = True
                    _LOGGER.warning(
                        "pocketlab.projection.deferred domain=%s generation=%d reason=%s retry_seconds=%.0f",
                        domain,
                        generation,
                        state.last_error_type,
                        max(0.0, state.next_retry_at - time.monotonic()),
                    )
                else:
                    state.dirty = True
            except Exception as exc:
                state.failure_count = min(8, state.failure_count + 1)
                delay = self._retry_delay(domain, state.failure_count)
                if state.failure_count >= self.circuit_failure_threshold:
                    delay = max(delay, self.circuit_cooldown_seconds)
                    state.circuit_open_count += 1
                state.next_retry_at = time.monotonic() + delay
                state.next_retry_epoch_ms = _epoch_ms() + int(delay * 1000)
                state.last_error_type = type(exc).__name__
                state.dirty = True
                _LOGGER.exception(
                    "pocketlab.projection.failed domain=%s generation=%d error_type=%s",
                    domain,
                    generation,
                    type(exc).__name__,
                )
            job = self._jobs.get(domain)
            if job is not None and job.optional and state.last_duration_ms > 0:
                cooldown = IDLE_EFFICIENCY.optional_cooldown_seconds(state.last_duration_ms)
                if cooldown > 0:
                    cooldown_until = time.monotonic() + cooldown
                    if cooldown_until > state.next_retry_at:
                        state.next_retry_at = cooldown_until
                        state.next_retry_epoch_ms = _epoch_ms() + int(cooldown * 1000)
            if state.dirty and not self._shutdown:
                self._enqueue_locked(domain, state)
            self._persist_state_best_effort(domain, state)

    def _persist_state_best_effort(self, domain: str, state: _DomainState) -> None:
        snapshot = {
            "domain": domain,
            "generation": state.generation,
            "committed_generation": state.committed_generation,
            "dirty": int(state.dirty),
            "active": int(state.active),
            "priority": state.priority,
            "work_class": state.work_class,
            "failure_count": state.failure_count,
            "next_retry_epoch_ms": max(0, int(state.next_retry_epoch_ms)),
            "coalesced_count": state.coalesced_count,
            "late_result_count": state.late_result_count,
            "stale_generation_count": state.stale_generation_count,
            "last_started_at": state.last_started_iso or None,
            "last_completed_at": state.last_completed_iso or None,
            "last_error_type": state.last_error_type[:80],
            "last_pressure_reason": state.last_pressure_reason[:80],
            "database_instance": state.database_instance[:240],
            "updated_at": _utc_now(),
        }
        persistence_material = json.dumps(
            {key: value for key, value in snapshot.items() if key != "updated_at"},
            sort_keys=True,
            separators=(",", ":"),
        )
        persistence_checksum = hashlib.sha256(
            persistence_material.encode("utf-8")
        ).hexdigest()
        if state.last_persisted_checksum == persistence_checksum:
            return
        def write(conn):
            conn.execute(
                """
                INSERT INTO projection_refresh_state(
                    domain,generation,committed_generation,dirty,active,priority,work_class,
                    failure_count,next_retry_epoch_ms,coalesced_count,late_result_count,
                    stale_generation_count,last_started_at,last_completed_at,last_error_type,
                    last_pressure_reason,database_instance,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(domain) DO UPDATE SET
                    generation=excluded.generation,
                    committed_generation=excluded.committed_generation,
                    dirty=excluded.dirty,
                    active=excluded.active,
                    priority=excluded.priority,
                    work_class=excluded.work_class,
                    failure_count=excluded.failure_count,
                    next_retry_epoch_ms=excluded.next_retry_epoch_ms,
                    coalesced_count=excluded.coalesced_count,
                    late_result_count=excluded.late_result_count,
                    stale_generation_count=excluded.stale_generation_count,
                    last_started_at=excluded.last_started_at,
                    last_completed_at=excluded.last_completed_at,
                    last_error_type=excluded.last_error_type,
                    last_pressure_reason=excluded.last_pressure_reason,
                    database_instance=excluded.database_instance,
                    updated_at=excluded.updated_at
                """,
                tuple(snapshot[key] for key in (
                    "domain","generation","committed_generation","dirty","active","priority","work_class",
                    "failure_count","next_retry_epoch_ms","coalesced_count","late_result_count",
                    "stale_generation_count","last_started_at","last_completed_at","last_error_type",
                    "last_pressure_reason","database_instance","updated_at",
                )),
            )

        try:
            SQLITE_WRITER.submit("projection.scheduler.state", write, deadline_seconds=0.4)
            state.last_persisted_checksum = persistence_checksum
        except Exception:
            # Diagnostics persistence is deliberately best effort and never blocks
            # lifecycle/current-state commits or request handling.
            return

    def status(self, domain: str) -> dict[str, Any]:
        safe_domain = _safe_domain(domain)
        with self._condition:
            state = self._states.get(safe_domain)
            if state is None:
                return {
                    "registered": False,
                    "refresh_pending": False,
                    "retry_after_seconds": 0,
                }
            return {
                "registered": safe_domain in self._jobs,
                "generation": state.generation,
                "committed_generation": state.committed_generation,
                "refresh_pending": bool(state.dirty or state.queued or state.active),
                "active": state.active,
                "queued": state.queued,
                "priority": state.priority,
                "work_class": state.work_class,
                "queue_age_ms": round(max(0.0, (time.monotonic() - state.enqueued_at) * 1000.0), 2) if state.queued else 0.0,
                "retry_after_seconds": max(0, int(state.next_retry_at - time.monotonic() + 0.999)),
                "failure_count": state.failure_count,
                "coalesced_count": state.coalesced_count,
                "late_result_count": state.late_result_count,
                "stale_generation_count": state.stale_generation_count,
                "last_error_type": state.last_error_type,
                "pressure_reason": state.last_pressure_reason,
                "last_duration_ms": round(state.last_duration_ms, 2),
                "execution_count": state.execution_count,
                "committed_count": state.committed_count,
                "unchanged_count": state.unchanged_count,
                "circuit_open_count": state.circuit_open_count,
                "circuit_open": bool(
                    state.failure_count >= self.circuit_failure_threshold
                    and state.next_retry_at > time.monotonic()
                ),
                "source_revision": max(-1, state.last_source_revision),
                "sanitized": True,
            }

    def diagnostics(self) -> dict[str, Any]:
        with self._condition:
            return {
                "status": "stopping" if self._shutdown else "running" if self._accepting else "stopped",
                "io_workers": self.io_workers,
                "cpu_workers": self.cpu_workers,
                "queued_domains": sum(1 for state in self._states.values() if state.queued),
                "active_domains": sum(1 for state in self._states.values() if state.active),
                "active_io": self._active_count_locked("io"),
                "active_cpu": self._active_count_locked("cpu"),
                "circuit_failure_threshold": self.circuit_failure_threshold,
                "circuit_cooldown_seconds": self.circuit_cooldown_seconds,
                "idle_wait_seconds": self.idle_wait_seconds,
                "event_signal_count": self._event_signal_count,
                "idle_efficiency": IDLE_EFFICIENCY.snapshot(),
                "domains": {domain: self.status(domain) for domain in sorted(self._states)},
                "sanitized": True,
            }

    def shutdown(self, *, drain_seconds: float = 5.0) -> None:
        with self._condition:
            if self._shutdown:
                return
            self._accepting = False
            self._shutdown = True
            self._condition.notify_all()
            dispatcher = self._dispatcher
        if dispatcher is not None:
            dispatcher.join(timeout=max(0.1, min(float(drain_seconds), 30.0)))
        for executor in (self._io_executor, self._cpu_executor):
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)


PROJECTION_SCHEDULER = ProjectionScheduler()
