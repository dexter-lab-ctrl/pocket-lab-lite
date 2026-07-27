from __future__ import annotations

"""Bounded cross-domain prepared-projection scheduling for Lite control-plane reads.

Request handlers only mark a domain dirty. Collectors run here under conservative
Termux-safe limits, and projector callbacks commit through the existing single
SQLite writer. Payload contents are never retained in diagnostics.
"""

import concurrent.futures
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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
from .adaptive_runtime import ADAPTIVE_RUNTIME

_LOGGER = logging.getLogger(__name__)
WorkClass = Literal["critical", "io", "cpu"]
_PROJECTION_CONTEXT: ContextVar[dict[str, Any]] = ContextVar(
    "pocketlab_projection_context", default={}
)
_PROCESS_START_GENERATION = hashlib.sha256(
    f"{time.time_ns()}:{os.getpid()}".encode("utf-8")
).hexdigest()[:16]


def _loaded_build_version() -> str:
    configured = str(
        os.environ.get("POCKETLAB_BUILD_VERSION")
        or os.environ.get("POCKETLAB_RELEASE_VERSION")
        or ""
    ).strip()
    if configured:
        safe = re.sub(r"[^A-Za-z0-9_.:+-]+", "-", configured)[:64]
        if safe:
            return safe
    digest = hashlib.sha256()
    source_dir = Path(__file__).resolve().parent
    loaded = 0
    for filename in (
        "projection_scheduler.py",
        "lite_phase3b_projections.py",
        "lite_phase3c_projections.py",
    ):
        try:
            content = (source_dir / filename).read_bytes()
        except OSError:
            continue
        digest.update(filename.encode("utf-8"))
        digest.update(content)
        loaded += 1
    return f"sha256:{digest.hexdigest()[:16]}" if loaded else "unavailable"


_LOADED_BUILD_VERSION = _loaded_build_version()


class ProjectionCommitRejected(RuntimeError):
    """A prepared projection commit failed a database/generation fence."""


def _process_role() -> str:
    value = re.sub(
        r"[^a-z0-9_.:-]+",
        "-",
        str(os.environ.get("POCKETLAB_PROCESS_ROLE") or "unknown").strip().lower(),
    )
    return (value or "unknown")[:48]


def _configured_execution_owner() -> str:
    value = re.sub(
        r"[^a-z0-9_.:-]+",
        "-",
        str(os.environ.get("POCKETLAB_PROJECTION_EXECUTION_OWNER") or "worker")
        .strip()
        .lower(),
    )
    return (value or "worker")[:48]


def _is_execution_owner() -> bool:
    role = _process_role()
    # Direct unit-test and one-shot harnesses do not set a process role. Keep
    # those process-local while production API/worker roles stay explicit.
    return role in {"unknown", "test", "direct", "oneshot"} or role == _configured_execution_owner()


def _safe_reason(value: Any) -> str:
    text = re.sub(r"[^a-z0-9_.:-]+", "_", str(value or "event").strip().lower())
    return (text or "event")[:96]


def current_projection_context() -> dict[str, Any]:
    return dict(_PROJECTION_CONTEXT.get())


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
    projector: Callable[[dict[str, Any]], Any]
    priority: int
    work_class: WorkClass
    deadline_seconds: float
    optional: bool = True
    source_revision: Callable[[], int] | None = None
    on_unchanged: Callable[[], None] | None = None
    max_probe_seconds: float = 900.0
    quiet_window_seconds: float = 0.0


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
    not_before_at: float = 0.0
    dirty_mark_count: int = 0
    followup_requested: bool = False
    trigger_reason: str = "event"
    last_trigger_reason: str = ""
    execution_owner: str = "unknown"
    last_queue_wait_ms: float = 0.0
    last_payload_bytes: int = 0
    last_serialization_ms: float = 0.0
    last_allocation_bytes: int = 0
    last_cpu_ms: float = 0.0
    adaptive_deferred_count: int = 0


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
            "POCKETLAB_LITE_PROJECTION_MAX_DOMAINS", 32, 24, 64
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
        self._signal_schema_ready = False
        self._signal_schema_lock = threading.Lock()

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
        if not _is_execution_owner():
            with self._condition:
                self._startup_complete = True
                self._accepting = False
            return False
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
            existing = self._jobs.get(domain)
            source_revision = job.source_revision
            on_unchanged = job.on_unchanged
            max_probe_seconds = job.max_probe_seconds
            quiet_window_seconds = job.quiet_window_seconds
            priority = int(job.priority)
            work_class = job.work_class
            deadline_seconds = job.deadline_seconds
            optional = bool(job.optional)

            if existing is not None:
                # Request-scoped registrations must not downgrade previously
                # installed semantic callbacks or their richer admission guards.
                incomplete_registration = (
                    job.source_revision is None
                    and existing.source_revision is not None
                )
                source_revision = source_revision or existing.source_revision
                on_unchanged = on_unchanged or existing.on_unchanged
                if incomplete_registration:
                    max_probe_seconds = existing.max_probe_seconds
                    quiet_window_seconds = existing.quiet_window_seconds
                    priority = min(priority, existing.priority)
                    work_class = existing.work_class
                    deadline_seconds = existing.deadline_seconds
                    optional = existing.optional
                elif quiet_window_seconds <= 0 and existing.quiet_window_seconds > 0:
                    quiet_window_seconds = existing.quiet_window_seconds

            self._jobs[domain] = ProjectionJob(
                domain=domain,
                builder=job.builder,
                projector=job.projector,
                priority=priority,
                work_class=work_class,
                deadline_seconds=max(0.1, min(float(deadline_seconds), 300.0)),
                optional=optional,
                source_revision=source_revision,
                on_unchanged=on_unchanged,
                max_probe_seconds=max(5.0, min(float(max_probe_seconds), 86_400.0)),
                quiet_window_seconds=max(0.0, min(float(quiet_window_seconds), 30.0)),
            )
            self._states.setdefault(domain, _DomainState())
            ADAPTIVE_RUNTIME.policy_for(
                domain,
                priority=priority,
                work_class=work_class,
                optional=optional,
            )

    def _ensure_signal_schema(self) -> None:
        if self._signal_schema_ready:
            return
        with self._signal_schema_lock:
            if self._signal_schema_ready:
                return
            from ..db.migrations import apply_migrations

            apply_migrations()
            self._signal_schema_ready = True

    def _persist_dirty_signal(self, domain: str, reason: str) -> dict[str, Any]:
        self._ensure_signal_schema()
        requested_by = _process_role()
        safe_reason = _safe_reason(reason)
        now_iso = _utc_now()
        now_ms = _epoch_ms()

        def _write(conn):
            conn.execute(
                """
                INSERT INTO projection_dirty_signals(
                    domain, signal_generation, claimed_generation, trigger_reason,
                    requested_by, updated_at, updated_at_epoch_ms
                ) VALUES (?, 1, 0, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    signal_generation = projection_dirty_signals.signal_generation + 1,
                    trigger_reason = CASE
                        WHEN projection_dirty_signals.claimed_generation < projection_dirty_signals.signal_generation
                             AND projection_dirty_signals.trigger_reason <> excluded.trigger_reason
                        THEN 'coalesced_multiple'
                        ELSE excluded.trigger_reason
                    END,
                    requested_by = excluded.requested_by,
                    updated_at = excluded.updated_at,
                    updated_at_epoch_ms = excluded.updated_at_epoch_ms
                """,
                (domain, safe_reason, requested_by, now_iso, now_ms),
            )
            row = conn.execute(
                "SELECT signal_generation,claimed_generation,trigger_reason "
                "FROM projection_dirty_signals WHERE domain=?",
                (domain,),
            ).fetchone()
            return dict(row) if row is not None else {}

        return SQLITE_WRITER.submit(
            "projection.dirty_signal", _write, deadline_seconds=1.5
        )

    def _claim_dirty_signal(self, domain: str, generation: int) -> None:
        self._ensure_signal_schema()

        def _write(conn):
            conn.execute(
                "UPDATE projection_dirty_signals SET claimed_generation=MAX(claimed_generation, ?) "
                "WHERE domain=? AND signal_generation>=?",
                (int(generation), domain, int(generation)),
            )

        SQLITE_WRITER.submit(
            "projection.claim_signal", _write, deadline_seconds=1.5
        )

    def consume_dirty_signals(self, *, limit: int = 32) -> dict[str, Any]:
        if not _is_execution_owner():
            return {"claimed": 0, "pending": 0, "execution_owner": _configured_execution_owner()}
        self._ensure_signal_schema()
        from ..db.connection import read_connection

        bounded_limit = max(1, min(int(limit), self.max_domains))
        with read_connection() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT domain,signal_generation,claimed_generation,trigger_reason
                    FROM projection_dirty_signals
                    WHERE signal_generation > claimed_generation
                    ORDER BY updated_at_epoch_ms,domain
                    LIMIT ?
                    """,
                    (bounded_limit,),
                )
            ]
        claimed = 0
        unregistered = 0
        for row in rows:
            domain = _safe_domain(row.get("domain") or "")
            generation = int(row.get("signal_generation") or 0)
            with self._condition:
                registered = domain in self._jobs
            if not registered:
                unregistered += 1
                continue
            result = self.mark_dirty(
                domain,
                reason=str(row.get("trigger_reason") or "mailbox"),
                _persist_signal=False,
            )
            if result.get("accepted"):
                self._claim_dirty_signal(domain, generation)
                claimed += 1
        return {
            "claimed": claimed,
            "pending": max(0, len(rows) - claimed),
            "unregistered": unregistered,
            "execution_owner": _configured_execution_owner(),
            "process_role": _process_role(),
        }

    def mark_dirty(
        self,
        domain: str,
        *,
        job: ProjectionJob | None = None,
        priority: int | None = None,
        force_followup: bool = False,
        reason: str = "event",
        _persist_signal: bool = True,
    ) -> dict[str, Any]:
        if job is not None:
            self.register(job)
        safe_domain = _safe_domain(domain)
        if not safe_domain:
            return {
                "accepted": False,
                "refresh_pending": False,
                "retry_after_seconds": 0,
                "reason": "invalid_domain",
            }
        ADAPTIVE_RUNTIME.mark_dirty(
            safe_domain,
            active_hint=_safe_reason(reason) not in {"adaptive_reconcile", "startup_warmup"},
        )
        if not _is_execution_owner():
            try:
                signal = self._persist_dirty_signal(safe_domain, reason)
            except (SQLiteWriteRejected, SQLiteWriteDeadlineExceeded, OSError) as exc:
                return {
                    "accepted": False,
                    "refresh_pending": False,
                    "retry_after_seconds": 1,
                    "reason": type(exc).__name__,
                    "execution_owner": _configured_execution_owner(),
                }
            self._event_signal_count += 1
            return {
                "accepted": True,
                "refresh_pending": True,
                "generation": int(signal.get("signal_generation") or 0),
                "retry_after_seconds": 1,
                "coalesced": int(signal.get("signal_generation") or 0) > int(signal.get("claimed_generation") or 0),
                "execution_owner": _configured_execution_owner(),
                "local_execution": False,
            }
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
            requested_reason = _safe_reason(reason)
            if was_pending and state.trigger_reason != requested_reason:
                state.trigger_reason = "coalesced_multiple"
            else:
                state.trigger_reason = requested_reason

            if was_pending and not force_followup:
                # Prepared-read polling is only a refresh hint. Do not invalidate an
                # in-flight generation: doing so creates an endless build/discard
                # loop when clients poll faster than a collector can complete.
                state.coalesced_count += 1
                if state.active:
                    state.followup_requested = True
                if state.queued and state.priority < prior_priority:
                    self._heap = [item for item in self._heap if item[2] != safe_domain]
                    heapq.heapify(self._heap)
                    state.queued = False
                    self._enqueue_locked(safe_domain, state)
            else:
                state.generation += 1
                state.dirty = True
                state.dirty_mark_count += 1
                if not was_pending and registered.quiet_window_seconds > 0:
                    state.not_before_at = (
                        time.monotonic()
                        + registered.quiet_window_seconds
                    )
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
                force_followup=False,
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

    def _enqueue_due_reconciliations_locked(self) -> int:
        due = ADAPTIVE_RUNTIME.due_domains(self._jobs.keys())
        scheduled = 0
        for domain in due:
            state = self._states.get(domain)
            job = self._jobs.get(domain)
            if state is None or job is None or state.active or state.queued or state.dirty:
                continue
            state.generation += 1
            state.dirty = True
            state.dirty_mark_count += 1
            state.priority = job.priority
            state.work_class = job.work_class
            state.trigger_reason = "adaptive_reconcile"
            self._enqueue_locked(domain, state)
            scheduled += 1
        return scheduled

    @staticmethod
    def _payload_has_active_transition(payload: dict[str, Any]) -> bool:
        active_values = {
            "accepted", "queued", "running", "working", "repairing",
            "joining", "waiting", "pending", "in_progress", "starting",
            "restarting", "verifying", "restoring", "scanning",
        }
        stack: list[Any] = [payload]
        visited = 0
        while stack and visited < 2048:
            item = stack.pop()
            visited += 1
            if isinstance(item, dict):
                for key, value in item.items():
                    if str(key).lower() in {"status", "state", "phase", "connection_state", "operation_state"}:
                        if str(value or "").strip().lower().replace("-", "_") in active_values:
                            return True
                    if isinstance(value, (dict, list, tuple)):
                        stack.append(value)
            elif isinstance(item, (list, tuple)):
                stack.extend(item[:256])
        return False

    def _dispatch_loop(self) -> None:
        while True:
            with self._condition:
                self._reap_done_locked()
                self._enqueue_due_reconciliations_locked()
                if self._shutdown:
                    return
                if not self._heap:
                    # One interruptible scheduler loop owns both event-driven and
                    # adaptive reconciliation. No second timer thread is created.
                    next_due = ADAPTIVE_RUNTIME.next_due_seconds(self._jobs.keys())
                    timeout = self.idle_wait_seconds if next_due is None else min(
                        self.idle_wait_seconds, max(0.05, next_due)
                    )
                    self._condition.wait(timeout=timeout)
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
                if now < state.not_before_at:
                    self._enqueue_locked(domain, state)
                    self._condition.wait(timeout=min(self.idle_wait_seconds, state.not_before_at - now))
                    continue
                if now < state.next_retry_at:
                    self._enqueue_locked(domain, state)
                    self._condition.wait(
                        timeout=min(self.idle_wait_seconds, state.next_retry_at - now)
                    )
                    continue
                pressure = self._pressure_reason(job)
                capacity = self.cpu_workers if job.work_class == "cpu" else self.io_workers
                active_count = self._active_count_locked(job.work_class)
                try:
                    event_loop_lag_ms = float(RUNTIME_DIAGNOSTICS.latest_event_loop_lag_ms())
                except Exception:
                    event_loop_lag_ms = 0.0
                queue_age_ms = max(0.0, (now - state.enqueued_at) * 1000.0)
                admission = ADAPTIVE_RUNTIME.decide(
                    domain,
                    priority=job.priority,
                    work_class=job.work_class,
                    optional=job.optional,
                    queue_depth=len(self._heap) + len(self._active_futures) + 1,
                    queue_age_ms=queue_age_ms,
                    active_count=active_count,
                    capacity=capacity,
                    event_loop_lag_ms=event_loop_lag_ms,
                    external_pressure_reason=pressure,
                )
                if not admission.accepted and job.optional:
                    state.last_pressure_reason = admission.reason or pressure
                    state.adaptive_deferred_count += 1
                    retry_seconds = max(1.0, admission.retry_after_ms / 1000.0)
                    state.next_retry_at = max(state.next_retry_at, now + retry_seconds)
                    state.next_retry_epoch_ms = _epoch_ms() + max(
                        0, int((state.next_retry_at - now) * 1000)
                    )
                    self._enqueue_locked(domain, state)
                    self._persist_state_best_effort(domain, state)
                    continue
                if active_count >= capacity:
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
                trigger_reason = _safe_reason(state.trigger_reason)
                state.active = True
                state.started_at = now
                state.last_trigger_reason = trigger_reason
                state.execution_owner = _process_role()
                state.last_started_iso = _utc_now()
                state.database_instance = self._database_instance()
                state.last_pressure_reason = ""
                try:
                    state.last_queue_wait_ms = queue_age_ms
                    future = executor.submit(
                        self._execute_profiled, job, generation, state.database_instance,
                        trigger_reason, queue_age_ms
                    )
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

    def _execute_profiled(
        self,
        job: ProjectionJob,
        generation: int,
        database_instance: str,
        trigger_reason: str,
        queue_wait_ms: float = 0.0,
    ) -> dict[str, Any]:
        wall_started = time.monotonic()
        cpu_started = time.thread_time() if hasattr(time, "thread_time") else time.process_time()
        result: dict[str, Any] = {}
        try:
            with HOT_PATH_PROFILER.measure(f"projection.{job.domain}") as hot_path:
                result = self._execute(
                    job, generation, database_instance, trigger_reason
                )
                outcome = str(result.get("outcome") or "completed")
                hot_path["outcome"] = outcome
                hot_path["changed"] = True if outcome == "committed" else False if outcome in {"unchanged", "source_unchanged"} else None
                if outcome == "source_unchanged":
                    HOT_PATH_PROFILER.increment(f"projection.{job.domain}", "skipped_unchanged")
                return result
        except Exception:
            result = {"outcome": "failed"}
            raise
        finally:
            cpu_now = time.thread_time() if hasattr(time, "thread_time") else time.process_time()
            cpu_ms = max(0.0, (cpu_now - cpu_started) * 1000.0)
            wall_ms = max(0.0, (time.monotonic() - wall_started) * 1000.0)
            outcome = str(result.get("outcome") or "failed")
            result["cpu_ms"] = cpu_ms
            result["wall_ms"] = wall_ms
            result["queue_wait_ms"] = max(0.0, float(queue_wait_ms))
            ADAPTIVE_RUNTIME.record_result(
                job.domain,
                cpu_ms=cpu_ms,
                wall_ms=wall_ms,
                queue_wait_ms=queue_wait_ms,
                payload_bytes=int(result.get("payload_bytes") or 0),
                serialization_ms=float(result.get("serialization_ms") or 0.0),
                allocation_bytes=int(result.get("allocation_estimate_bytes") or 0),
                outcome=outcome,
                changed=True if outcome == "committed" else False if outcome in {"unchanged", "source_unchanged"} else None,
                active_transition=bool(result.get("active_transition")),
            )

    def _execute(
        self,
        job: ProjectionJob,
        generation: int,
        database_instance: str,
        trigger_reason: str = "event",
    ) -> dict[str, Any]:
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
        assessment = ADAPTIVE_RUNTIME.assess_payload(job.domain, payload)
        checksum = assessment.checksum
        if not assessment.within_budget and job.optional:
            ADAPTIVE_RUNTIME.defer_payload(job.domain, assessment.reason)
            return {
                "outcome": "budget_deferred",
                "duration_ms": (time.monotonic() - started) * 1000.0,
                "generation": generation,
                "database_instance": database_instance,
                "payload_checksum": checksum,
                "payload_bytes": assessment.payload_bytes,
                "serialization_ms": assessment.serialization_ms,
                "allocation_estimate_bytes": assessment.allocation_estimate_bytes,
                "budget_reason": assessment.reason,
                "retry_after_ms": 30_000,
                "source_revision": source_revision,
                "active_transition": self._payload_has_active_transition(payload),
            }
        active_transition = self._payload_has_active_transition(payload)
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
                "payload_bytes": assessment.payload_bytes,
                "serialization_ms": assessment.serialization_ms,
                "allocation_estimate_bytes": assessment.allocation_estimate_bytes,
                "active_transition": active_transition,
            }
        database_instance_hash = hashlib.sha256(
            database_instance.encode("utf-8")
        ).hexdigest()[:24]
        token = _PROJECTION_CONTEXT.set(
            {
                "domain": job.domain,
                "scheduler_generation": generation,
                "database_instance": database_instance,
                "database_instance_hash": database_instance_hash,
                "trigger_reason": _safe_reason(trigger_reason),
                "execution_owner": _process_role(),
                "source_revision_before": source_revision,
            }
        )
        try:
            projected = job.projector(payload)
        except ProjectionCommitRejected as exc:
            reason = str(exc)
            return {
                "outcome": (
                    "database_changed"
                    if reason == "database_instance_changed"
                    else "stale_generation"
                ),
                "duration_ms": (time.monotonic() - started) * 1000.0,
                "generation": generation,
                "database_instance": database_instance,
                "payload_checksum": checksum,
                "source_revision": source_revision,
            }
        finally:
            _PROJECTION_CONTEXT.reset(token)
        revision = int(projected)
        changed = getattr(projected, "changed", True) is not False
        if job.source_revision is not None:
            try:
                source_revision = int(job.source_revision())
            except Exception:
                pass
        return {
            "outcome": "committed" if changed else "unchanged",
            "revision": revision,
            "duration_ms": (time.monotonic() - started) * 1000.0,
            "generation": generation,
            "database_instance": database_instance,
            "payload_checksum": checksum,
            "source_revision": source_revision,
            "trigger_reason": _safe_reason(trigger_reason),
            "payload_bytes": assessment.payload_bytes,
            "serialization_ms": assessment.serialization_ms,
            "allocation_estimate_bytes": assessment.allocation_estimate_bytes,
            "active_transition": active_transition,
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
                state.last_cpu_ms = float(result.get("cpu_ms") or 0.0)
                state.last_queue_wait_ms = float(result.get("queue_wait_ms") or state.last_queue_wait_ms)
                state.last_payload_bytes = int(result.get("payload_bytes") or 0)
                state.last_serialization_ms = float(result.get("serialization_ms") or 0.0)
                state.last_allocation_bytes = int(result.get("allocation_estimate_bytes") or 0)
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
                elif outcome == "budget_deferred":
                    state.dirty = True
                    state.adaptive_deferred_count += 1
                    retry_ms = max(1_000, int(result.get("retry_after_ms") or 30_000))
                    state.next_retry_at = time.monotonic() + retry_ms / 1000.0
                    state.next_retry_epoch_ms = _epoch_ms() + retry_ms
                    state.last_error_type = str(result.get("budget_reason") or "RuntimeBudgetDeferred")[:80]
                    state.last_pressure_reason = state.last_error_type
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
            if state.followup_requested and not self._shutdown:
                # Commit active work before scheduling one bounded follow-up.
                # The source-revision fence skips it when semantic state did
                # not change while the collector was running.
                state.followup_requested = False
                if state.generation <= generation:
                    state.generation = generation + 1
                    state.dirty = True
                    state.dirty_mark_count += 1
                    registered = self._jobs.get(domain)
                    if (
                        registered is not None
                        and registered.quiet_window_seconds > 0
                    ):
                        state.not_before_at = (
                            time.monotonic()
                            + registered.quiet_window_seconds
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
            "source_revision": state.last_source_revision,
            "last_duration_ms": round(state.last_duration_ms, 3),
            "execution_count": state.execution_count,
            "committed_count": state.committed_count,
            "unchanged_count": state.unchanged_count,
            "dirty_mark_count": state.dirty_mark_count,
            "followup_requested": int(state.followup_requested),
            "trigger_reason": _safe_reason(state.trigger_reason),
            "last_trigger_reason": _safe_reason(state.last_trigger_reason),
            "execution_owner": _safe_reason(state.execution_owner),
            "executor_build_version": _LOADED_BUILD_VERSION,
            "executor_process_generation": _PROCESS_START_GENERATION,
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
                    last_pressure_reason,database_instance,source_revision,last_duration_ms,
                    execution_count,committed_count,unchanged_count,dirty_mark_count,
                    followup_requested,trigger_reason,
                    last_trigger_reason,execution_owner,executor_build_version,
                    executor_process_generation,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    source_revision=excluded.source_revision,
                    last_duration_ms=excluded.last_duration_ms,
                    execution_count=excluded.execution_count,
                    committed_count=excluded.committed_count,
                    unchanged_count=excluded.unchanged_count,
                    dirty_mark_count=excluded.dirty_mark_count,
                    followup_requested=excluded.followup_requested,
                    trigger_reason=excluded.trigger_reason,
                    last_trigger_reason=excluded.last_trigger_reason,
                    execution_owner=excluded.execution_owner,
                    executor_build_version=excluded.executor_build_version,
                    executor_process_generation=excluded.executor_process_generation,
                    updated_at=excluded.updated_at
                """,
                tuple(snapshot[key] for key in (
                    "domain","generation","committed_generation","dirty","active","priority","work_class",
                    "failure_count","next_retry_epoch_ms","coalesced_count","late_result_count",
                    "stale_generation_count","last_started_at","last_completed_at","last_error_type",
                    "last_pressure_reason","database_instance","source_revision","last_duration_ms",
                    "execution_count","committed_count","unchanged_count","dirty_mark_count",
                    "followup_requested","trigger_reason",
                    "last_trigger_reason","execution_owner","executor_build_version",
                    "executor_process_generation","updated_at",
                )),
            )

        try:
            SQLITE_WRITER.submit("projection.scheduler.state", write, deadline_seconds=0.4)
            state.last_persisted_checksum = persistence_checksum
        except Exception:
            # Diagnostics persistence is deliberately best effort and never blocks
            # lifecycle/current-state commits or request handling.
            return

    def _shared_status(self, domain: str) -> dict[str, Any]:
        try:
            self._ensure_signal_schema()
            from ..db.connection import read_connection

            with read_connection() as conn:
                row = conn.execute(
                    """
                    SELECT generation,committed_generation,dirty,active,priority,work_class,
                           failure_count,next_retry_epoch_ms,coalesced_count,late_result_count,
                           stale_generation_count,last_error_type,last_pressure_reason,
                           source_revision,last_duration_ms,execution_count,committed_count,
                           unchanged_count,dirty_mark_count,
                           followup_requested,trigger_reason,last_trigger_reason,execution_owner,
                           executor_build_version,executor_process_generation
                    FROM projection_refresh_state WHERE domain=?
                    """,
                    (domain,),
                ).fetchone()
            if row is None:
                return {}
            data = dict(row)
            now_ms = _epoch_ms()
            return {
                "generation": int(data.get("generation") or 0),
                "committed_generation": int(data.get("committed_generation") or 0),
                "refresh_pending": bool(data.get("dirty") or data.get("active")),
                "active": bool(data.get("active")),
                "queued": bool(data.get("dirty") and not data.get("active")),
                "priority": int(data.get("priority") or 50),
                "work_class": str(data.get("work_class") or "io"),
                "retry_after_seconds": max(
                    0, int((int(data.get("next_retry_epoch_ms") or 0) - now_ms + 999) / 1000)
                ),
                "failure_count": int(data.get("failure_count") or 0),
                "coalesced_count": int(data.get("coalesced_count") or 0),
                "late_result_count": int(data.get("late_result_count") or 0),
                "stale_generation_count": int(data.get("stale_generation_count") or 0),
                "last_error_type": str(data.get("last_error_type") or "")[:80],
                "pressure_reason": str(data.get("last_pressure_reason") or "")[:80],
                "source_revision": int(data.get("source_revision") or -1),
                "last_duration_ms": round(float(data.get("last_duration_ms") or 0.0), 2),
                "execution_count": int(data.get("execution_count") or 0),
                "committed_count": int(data.get("committed_count") or 0),
                "unchanged_count": int(data.get("unchanged_count") or 0),
                "dirty_mark_count": int(data.get("dirty_mark_count") or 0),
                "followup_requested": bool(data.get("followup_requested")),
                "trigger_reason": _safe_reason(data.get("trigger_reason")),
                "last_trigger_reason": _safe_reason(data.get("last_trigger_reason")),
                "execution_owner": _safe_reason(data.get("execution_owner")),
                "executor_build_version": str(
                    data.get("executor_build_version") or "unavailable"
                )[:64],
                "executor_process_generation": str(
                    data.get("executor_process_generation") or "unknown"
                )[:32],
            }
        except Exception:
            return {}

    def status(self, domain: str) -> dict[str, Any]:
        safe_domain = _safe_domain(domain)
        shared = self._shared_status(safe_domain) if not _is_execution_owner() else {}
        with self._condition:
            state = self._states.get(safe_domain)
            job = self._jobs.get(safe_domain)
            if state is None:
                return {
                    "registered": False,
                    "refresh_pending": bool(shared.get("refresh_pending")),
                    "retry_after_seconds": int(shared.get("retry_after_seconds") or 0),
                    **shared,
                    "process_role": _process_role(),
                    "configured_execution_owner": _configured_execution_owner(),
                    "loaded_build_version": _LOADED_BUILD_VERSION,
                    "process_start_generation": _PROCESS_START_GENERATION,
                    "sanitized": True,
                }
            local = {
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
                "last_cpu_ms": round(state.last_cpu_ms, 2),
                "last_queue_wait_ms": round(state.last_queue_wait_ms, 2),
                "last_payload_bytes": state.last_payload_bytes,
                "last_serialization_ms": round(state.last_serialization_ms, 2),
                "last_allocation_bytes": state.last_allocation_bytes,
                "adaptive_deferred_count": state.adaptive_deferred_count,
                "adaptive": ADAPTIVE_RUNTIME.domain_status(safe_domain),
                "execution_count": state.execution_count,
                "committed_count": state.committed_count,
                "unchanged_count": state.unchanged_count,
                "circuit_open_count": state.circuit_open_count,
                "circuit_open": bool(
                    state.failure_count >= self.circuit_failure_threshold
                    and state.next_retry_at > time.monotonic()
                ),
                "source_revision": max(-1, state.last_source_revision),
                "source_revision_enabled": bool(
                    job and job.source_revision is not None
                ),
                "dirty_mark_count": state.dirty_mark_count,
                "followup_requested": state.followup_requested,
                "trigger_reason": _safe_reason(state.trigger_reason),
                "last_trigger_reason": _safe_reason(state.last_trigger_reason),
                "execution_owner": _safe_reason(state.execution_owner),
                "process_role": _process_role(),
                "configured_execution_owner": _configured_execution_owner(),
                "loaded_build_version": _LOADED_BUILD_VERSION,
                "process_start_generation": _PROCESS_START_GENERATION,
                "executor_build_version": _LOADED_BUILD_VERSION
                if _is_execution_owner()
                else str(shared.get("executor_build_version") or "unavailable"),
                "executor_process_generation": _PROCESS_START_GENERATION
                if _is_execution_owner()
                else str(shared.get("executor_process_generation") or "unknown"),
                "sanitized": True,
            }
            if shared:
                for key, value in shared.items():
                    if key in {
                        "generation", "committed_generation", "refresh_pending",
                        "active", "queued", "priority", "work_class",
                        "retry_after_seconds", "failure_count", "coalesced_count",
                        "late_result_count", "stale_generation_count",
                        "last_error_type", "pressure_reason", "source_revision",
                        "last_duration_ms", "execution_count",
                        "committed_count", "unchanged_count", "dirty_mark_count",
                        "followup_requested", "trigger_reason",
                        "last_trigger_reason", "execution_owner",
                        "executor_build_version", "executor_process_generation",
                    }:
                        local[key] = value
            return local


    def execution_fence_valid(
        self,
        domain: str,
        generation: int,
        database_instance_hash: str,
    ) -> bool:
        safe_domain = _safe_domain(domain)
        with self._condition:
            state = self._states.get(safe_domain)
            if state is None or self._shutdown:
                return False
            current_hash = hashlib.sha256(
                self._database_instance().encode("utf-8")
            ).hexdigest()[:24]
            return bool(
                state.active
                and state.generation == int(generation)
                and current_hash == str(database_instance_hash or "")
            )

    def quiesce_for_database_switch(self, *, timeout_seconds: float = 5.0) -> bool:
        """Cancel queued refreshes and wait for active jobs before changing databases.

        Registrations are preserved so the process can continue serving after a
        restore, test database switch, or other explicit database handoff.
        Active collectors are generation-fenced and allowed to finish; no new
        queued work is admitted during the bounded drain.
        """
        deadline = time.monotonic() + max(0.1, min(float(timeout_seconds), 30.0))
        with self._condition:
            self._heap.clear()
            for state in self._states.values():
                state.generation += 1
                state.dirty = False
                state.queued = False
                state.followup_requested = False
                state.not_before_at = 0.0
            self._condition.notify_all()

        while True:
            with self._condition:
                self._reap_done_locked()
                active = [
                    future
                    for future in self._active_futures
                    if not future.done()
                ]
                if not active:
                    for state in self._states.values():
                        state.active = False
                        state.dirty = False
                        state.queued = False
                        state.followup_requested = False
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
            concurrent.futures.wait(
                active,
                timeout=min(0.1, remaining),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )

    def _reconcile_queue_state_locked(self) -> dict[str, int]:
        """Make queue diagnostics reflect runnable executor work, not stale flags.

        Heap entries are generation-fenced.  Stale/duplicate entries are removed,
        orphaned ``queued`` flags are cleared, and dirty inactive domains that lost
        their heap entry are re-enqueued.  No durable mailbox rows are deleted.
        """
        valid_heap: list[tuple[int, int, str, int]] = []
        queued_domains: set[str] = set()
        stale_entries = 0
        duplicate_entries = 0
        for item in self._heap:
            priority, sequence, domain, generation = item
            state = self._states.get(domain)
            job = self._jobs.get(domain)
            if (
                state is None
                or job is None
                or state.active
                or not state.dirty
                or int(generation) != int(state.generation)
            ):
                stale_entries += 1
                continue
            if domain in queued_domains:
                duplicate_entries += 1
                continue
            queued_domains.add(domain)
            valid_heap.append((priority, sequence, domain, generation))

        if stale_entries or duplicate_entries or len(valid_heap) != len(self._heap):
            self._heap = valid_heap
            heapq.heapify(self._heap)

        cleared_flags = 0
        repaired_domains = 0
        for domain, state in self._states.items():
            should_be_queued = domain in queued_domains
            if state.queued and not should_be_queued:
                state.queued = False
                cleared_flags += 1
            elif should_be_queued and not state.queued:
                state.queued = True

            if (
                state.dirty
                and not state.active
                and not state.queued
                and domain in self._jobs
                and not self._shutdown
            ):
                self._enqueue_locked(domain, state)
                queued_domains.add(domain)
                repaired_domains += 1

        return {
            "executor_depth": len(queued_domains),
            "followup_domains": sum(
                1 for state in self._states.values() if state.followup_requested
            ),
            "active_domains": sum(1 for state in self._states.values() if state.active),
            "stale_entries_removed": stale_entries,
            "duplicate_entries_removed": duplicate_entries,
            "stale_flags_cleared": cleared_flags,
            "orphaned_dirty_requeued": repaired_domains,
        }

    def queue_health(self) -> dict[str, int]:
        with self._condition:
            self._reap_done_locked()
            return dict(self._reconcile_queue_state_locked())

    def diagnostics(self) -> dict[str, Any]:
        with self._condition:
            self._reap_done_locked()
            queue = self._reconcile_queue_state_locked()
            return {
                "status": "stopping" if self._shutdown else "running" if self._accepting else "stopped",
                "io_workers": self.io_workers,
                "cpu_workers": self.cpu_workers,
                "max_domains": self.max_domains,
                "registered_domains": len(self._states),
                "remaining_domain_capacity": max(0, self.max_domains - len(self._states)),
                # Backward-compatible alias used by the Phase 5 gate.  This is
                # now the authoritative executor heap depth, not a count of
                # historical per-domain flags.
                "queued_domains": int(queue["executor_depth"]),
                "active_domains": int(queue["active_domains"]),
                "queue": queue,
                "active_io": self._active_count_locked("io"),
                "active_cpu": self._active_count_locked("cpu"),
                "circuit_failure_threshold": self.circuit_failure_threshold,
                "circuit_cooldown_seconds": self.circuit_cooldown_seconds,
                "idle_wait_seconds": self.idle_wait_seconds,
                "event_signal_count": self._event_signal_count,
                "process_role": _process_role(),
                "loaded_build_version": _LOADED_BUILD_VERSION,
                "process_start_generation": _PROCESS_START_GENERATION,
                "projection_execution_owner": _configured_execution_owner(),
                "is_execution_owner": _is_execution_owner(),
                "idle_efficiency": IDLE_EFFICIENCY.snapshot(),
                "adaptive_runtime": ADAPTIVE_RUNTIME.diagnostics(),
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


def projection_execution_fence_valid(
    domain: str, generation: int, database_instance_hash: str
) -> bool:
    return PROJECTION_SCHEDULER.execution_fence_valid(
        domain, generation, database_instance_hash
    )
