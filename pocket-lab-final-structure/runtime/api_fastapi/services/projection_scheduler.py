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
    last_duration_ms: float = 0.0
    last_error_type: str = ""
    last_pressure_reason: str = ""
    database_instance: str = ""


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
                    self._condition.wait(timeout=0.25)
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
                    self._condition.wait(timeout=min(0.5, state.next_retry_at - now))
                    continue
                pressure = self._pressure_reason(job)
                if pressure and job.optional:
                    state.last_pressure_reason = pressure
                    state.next_retry_at = max(state.next_retry_at, now + 5.0)
                    self._enqueue_locked(domain, state)
                    self._persist_state_best_effort(domain, state)
                    continue
                capacity = self.cpu_workers if job.work_class == "cpu" else self.io_workers
                if self._active_count_locked(job.work_class) >= capacity:
                    self._enqueue_locked(domain, state)
                    self._condition.wait(timeout=0.05)
                    continue
                executor = self._executor_for(job.work_class)
                if executor is None:
                    state.last_error_type = "ExecutorUnavailable"
                    state.failure_count += 1
                    state.next_retry_at = now + self._retry_delay(domain, state.failure_count)
                    self._enqueue_locked(domain, state)
                    continue
                generation = state.generation
                state.active = True
                state.started_at = now
                state.database_instance = self._database_instance()
                state.last_pressure_reason = ""
                try:
                    future = executor.submit(self._execute, job, generation, state.database_instance)
                except RuntimeError:
                    state.active = False
                    state.last_error_type = "ExecutorRejected"
                    state.failure_count += 1
                    state.next_retry_at = now + self._retry_delay(domain, state.failure_count)
                    self._enqueue_locked(domain, state)
                    continue
                self._active_futures[future] = (domain, generation)
                future.add_done_callback(lambda _future: self._wake_dispatcher())
                self._persist_state_best_effort(domain, state)

    def _wake_dispatcher(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def _execute(self, job: ProjectionJob, generation: int, database_instance: str) -> dict[str, Any]:
        started = time.monotonic()
        payload = job.builder()
        duration = time.monotonic() - started
        if not isinstance(payload, dict):
            raise TypeError("projection builder must return a mapping")
        if duration > job.deadline_seconds:
            return {
                "outcome": "late",
                "duration_ms": duration * 1000.0,
                "generation": generation,
                "database_instance": database_instance,
            }
        if self._database_instance() != database_instance:
            return {
                "outcome": "database_changed",
                "duration_ms": duration * 1000.0,
                "generation": generation,
                "database_instance": database_instance,
            }
        with self._condition:
            state = self._states.get(job.domain)
            if state is None or state.generation != generation or self._shutdown:
                return {
                    "outcome": "stale_generation",
                    "duration_ms": duration * 1000.0,
                    "generation": generation,
                    "database_instance": database_instance,
                }
        revision = int(job.projector(payload))
        return {
            "outcome": "committed",
            "revision": revision,
            "duration_ms": (time.monotonic() - started) * 1000.0,
            "generation": generation,
            "database_instance": database_instance,
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
            try:
                result = future.result()
                outcome = str(result.get("outcome") or "unknown")
                state.last_duration_ms = float(result.get("duration_ms") or 0.0)
                if outcome == "committed":
                    state.committed_generation = max(state.committed_generation, generation)
                    state.failure_count = 0
                    state.next_retry_at = 0.0
                    state.last_error_type = ""
                    state.dirty = state.generation > generation
                elif outcome == "stale_generation":
                    state.stale_generation_count += 1
                    state.dirty = True
                elif outcome in {"late", "database_changed"}:
                    if outcome == "late":
                        state.late_result_count += 1
                    else:
                        state.stale_generation_count += 1
                    state.failure_count = min(8, state.failure_count + 1)
                    state.next_retry_at = time.monotonic() + self._retry_delay(domain, state.failure_count)
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
                state.next_retry_at = time.monotonic() + self._retry_delay(domain, state.failure_count)
                state.last_error_type = type(exc).__name__
                state.dirty = True
                _LOGGER.exception(
                    "pocketlab.projection.failed domain=%s generation=%d error_type=%s",
                    domain,
                    generation,
                    type(exc).__name__,
                )
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
            "next_retry_epoch_ms": _epoch_ms() + max(0, int((state.next_retry_at - time.monotonic()) * 1000)),
            "coalesced_count": state.coalesced_count,
            "late_result_count": state.late_result_count,
            "stale_generation_count": state.stale_generation_count,
            "last_started_at": _utc_now() if state.started_at else None,
            "last_completed_at": _utc_now() if state.completed_at else None,
            "last_error_type": state.last_error_type[:80],
            "last_pressure_reason": state.last_pressure_reason[:80],
            "database_instance": state.database_instance[:240],
            "updated_at": _utc_now(),
        }

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
