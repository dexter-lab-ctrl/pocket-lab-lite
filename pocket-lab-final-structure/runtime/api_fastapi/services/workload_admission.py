from __future__ import annotations

"""Bounded FastAPI-owned workload classification, admission, and execution.

The control plane uses this module for short-to-medium local maintenance work.
Long-running scanners, package operations, remote probes, backup/restore execution,
and broad report construction remain worker/agent/supervisor owned.
"""

import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import os
import threading
import time
from typing import Any, Callable, Mapping

from .runtime_diagnostics import RUNTIME_DIAGNOSTICS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


class ExecutionOwner(str, Enum):
    EVENT_LOOP_SAFE = "event_loop_safe"
    BOUNDED_MAINTENANCE = "bounded_maintenance_executor"
    WORKER_OWNED = "worker_owned"


class CostClass(str, Enum):
    CONSTANT = "constant"
    SMALL = "small"
    MEDIUM = "medium"
    HEAVY = "heavy"
    UNBOUNDED = "unbounded"


class AdmissionClass(str, Enum):
    EVENT_LOOP_SAFE = "event_loop_safe"
    COMMAND_RESERVATION = "command_reservation"
    LIFECYCLE_WRITE = "lifecycle_write"
    MAINTENANCE_READ = "maintenance_read"
    COMPATIBILITY_WRITE = "compatibility_write"
    AUDIT_AGGREGATION = "audit_aggregation"
    SYSTEM_PROBE = "system_probe"
    CPU_NORMALIZATION = "cpu_normalization"
    WORKER_OWNED = "worker_owned"


@dataclass(frozen=True, slots=True)
class WorkloadDefinition:
    operation_id: str
    category: str
    execution_owner: ExecutionOwner
    cost_class: CostClass
    admission_class: AdmissionClass
    default_deadline_seconds: float
    cancellation_safe: bool
    retry_safe: bool
    coalescing_safe: bool
    authoritative_output: bool
    audit_evidence_required: bool

    def snapshot(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "category": self.category,
            "execution_owner": self.execution_owner.value,
            "cost_class": self.cost_class.value,
            "admission_class": self.admission_class.value,
            "default_deadline_seconds": self.default_deadline_seconds,
            "cancellation_safe": self.cancellation_safe,
            "retry_safe": self.retry_safe,
            "coalescing_safe": self.coalescing_safe,
            "output": "authoritative" if self.authoritative_output else "derived",
            "audit_evidence_required": self.audit_evidence_required,
        }


def _workload(
    operation_id: str,
    category: str,
    owner: ExecutionOwner,
    cost: CostClass,
    admission: AdmissionClass,
    deadline: float,
    *,
    cancellation_safe: bool,
    retry_safe: bool,
    coalescing_safe: bool,
    authoritative: bool,
    audit: bool,
) -> WorkloadDefinition:
    return WorkloadDefinition(
        operation_id=operation_id,
        category=category,
        execution_owner=owner,
        cost_class=cost,
        admission_class=admission,
        default_deadline_seconds=deadline,
        cancellation_safe=cancellation_safe,
        retry_safe=retry_safe,
        coalescing_safe=coalescing_safe,
        authoritative_output=authoritative,
        audit_evidence_required=audit,
    )


# Central source of truth for FastAPI/worker ownership. Keep this bounded and
# explicit so new heavy work cannot silently land on the request event loop.
WORKLOADS: Mapping[str, WorkloadDefinition] = {
    item.operation_id: item
    for item in (
        _workload("security.progress.read", "prepared_security_read", ExecutionOwner.EVENT_LOOP_SAFE, CostClass.CONSTANT, AdmissionClass.EVENT_LOOP_SAFE, 0.25, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.summary.read", "prepared_security_read", ExecutionOwner.EVENT_LOOP_SAFE, CostClass.SMALL, AdmissionClass.EVENT_LOOP_SAFE, 0.50, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.runtime.initialize", "sqlite_runtime_initialization", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 15.0, cancellation_safe=False, retry_safe=True, coalescing_safe=True, authoritative=True, audit=False),
        _workload("security.projection.stop", "projection_runtime_shutdown", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.SMALL, AdmissionClass.MAINTENANCE_READ, 5.0, cancellation_safe=False, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.scan.reservation", "command_reservation", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.COMMAND_RESERVATION, 12.0, cancellation_safe=False, retry_safe=True, coalescing_safe=False, authoritative=True, audit=True),
        _workload("security.scan.submission_failure_commit", "lifecycle_write", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.SMALL, AdmissionClass.LIFECYCLE_WRITE, 12.0, cancellation_safe=False, retry_safe=True, coalescing_safe=False, authoritative=True, audit=True),
        _workload("security.scan.lifecycle_commit", "lifecycle_write", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.LIFECYCLE_WRITE, 12.0, cancellation_safe=False, retry_safe=True, coalescing_safe=False, authoritative=True, audit=True),
        _workload("security.profile.reconstruction", "security_profile_reconstruction", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.history.reconstruction", "security_history_reconstruction", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.details.reconstruction", "security_details_reconstruction", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.current_state.read", "security_current_state_read", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 10.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.evidence.summary", "security_evidence_summary", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.full_reconstruction", "security_full_reconstruction", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 3600.0, cancellation_safe=False, retry_safe=True, coalescing_safe=False, authoritative=False, audit=True),
        _workload("security.compatibility.write", "compatibility_json_write", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.COMPATIBILITY_WRITE, 10.0, cancellation_safe=False, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("security.compact.write", "compact_projection_write", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.COMPATIBILITY_WRITE, 10.0, cancellation_safe=False, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("security.maintenance.parity_read", "sqlite_json_parity_read", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 20.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.progress.retention", "security_progress_retention", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 30.0, cancellation_safe=False, retry_safe=True, coalescing_safe=True, authoritative=True, audit=True),
        _workload("sqlite.integrity_check", "sqlite_integrity_check", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 30.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("audit.summary", "audit_aggregation", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.AUDIT_AGGREGATION, 15.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("audit.history.reconstruction", "audit_history_reconstruction", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.AUDIT_AGGREGATION, 20.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("audit.large_report", "audit_report_construction", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 900.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("workflow.summary", "workflow_aggregation", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.AUDIT_AGGREGATION, 15.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("workflow.history.reconstruction", "workflow_history_reconstruction", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.AUDIT_AGGREGATION, 20.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("backup.metadata.read", "backup_inventory_metadata_read", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 15.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("recovery.metadata.read", "recovery_inventory_metadata_read", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.MAINTENANCE_READ, 15.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.local_probe", "bounded_system_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.SYSTEM_PROBE, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.telemetry_probe", "local_telemetry_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.SMALL, AdmissionClass.SYSTEM_PROBE, 5.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.health_probe", "local_health_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.SYSTEM_PROBE, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.fleet_probe", "local_fleet_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.SYSTEM_PROBE, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.observability_probe", "local_observability_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.SYSTEM_PROBE, 10.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.pm2_probe", "local_pm2_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.SYSTEM_PROBE, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.nats_status.read", "prepared_nats_status_read", ExecutionOwner.EVENT_LOOP_SAFE, CostClass.CONSTANT, AdmissionClass.EVENT_LOOP_SAFE, 0.25, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.nats_probe", "local_nats_connectivity_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.SMALL, AdmissionClass.SYSTEM_PROBE, 5.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.filesystem_metadata_probe", "bounded_filesystem_metadata_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.SYSTEM_PROBE, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.caddy_runtime_probe", "local_caddy_runtime_probe", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.SYSTEM_PROBE, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("system.tailscale_probe", "tailscale_and_tailnet_probe", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 120.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("system.remote_probe", "remote_system_probe", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 120.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("control.command_envelope.prepare", "command_and_evidence_envelope_normalization", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.CPU_NORMALIZATION, 8.0, cancellation_safe=True, retry_safe=True, coalescing_safe=False, authoritative=False, audit=False),
        _workload("normalization.bounded", "bounded_sanitization_sorting_grouping_checksum", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.CPU_NORMALIZATION, 15.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("normalization.large", "large_nested_sanitization_and_normalization", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 300.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("report.evidence.large", "large_report_and_evidence_construction", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 900.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=True),
        _workload("response.large.construct", "large_response_construction", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 300.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.cpu_normalization", "finding_and_payload_normalization", ExecutionOwner.BOUNDED_MAINTENANCE, CostClass.MEDIUM, AdmissionClass.CPU_NORMALIZATION, 15.0, cancellation_safe=True, retry_safe=True, coalescing_safe=True, authoritative=False, audit=False),
        _workload("security.scanner.execute", "security_scanner_execution", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 3600.0, cancellation_safe=False, retry_safe=True, coalescing_safe=False, authoritative=True, audit=True),
        _workload("backup.execute", "backup_restore_execution", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 3600.0, cancellation_safe=False, retry_safe=True, coalescing_safe=False, authoritative=True, audit=True),
        _workload("recovery.execute", "backup_restore_execution", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 3600.0, cancellation_safe=False, retry_safe=False, coalescing_safe=False, authoritative=True, audit=True),
        _workload("package.repair", "package_runtime_repair", ExecutionOwner.WORKER_OWNED, CostClass.HEAVY, AdmissionClass.WORKER_OWNED, 1800.0, cancellation_safe=False, retry_safe=True, coalescing_safe=False, authoritative=True, audit=True),
    )
}


class WorkloadAdmissionError(RuntimeError):
    reason = "executor_unavailable"
    retryable = True

    def __init__(self, operation_id: str, admission_class: AdmissionClass, message: str) -> None:
        super().__init__(message)
        self.operation_id = operation_id
        self.admission_class = admission_class
        self.safe_message = message


class AdmissionQueueFull(WorkloadAdmissionError):
    reason = "control_plane_busy"


class AdmissionTimeout(WorkloadAdmissionError):
    reason = "control_plane_admission_timeout"


class OperationDeadlineExceeded(WorkloadAdmissionError):
    reason = "control_plane_operation_timeout"


class ExecutorUnavailable(WorkloadAdmissionError):
    reason = "control_plane_unavailable"


class AdmissionShutdown(WorkloadAdmissionError):
    reason = "control_plane_shutdown"
    retryable = False


@dataclass(frozen=True, slots=True)
class AdmissionClassConfig:
    capacity: int
    queue_capacity: int


class _BoundedAdmissionLane:
    def __init__(self, name: AdmissionClass, config: AdmissionClassConfig) -> None:
        self.name = name
        self.capacity = config.capacity
        self.queue_capacity = config.queue_capacity
        self._executor = ThreadPoolExecutor(
            max_workers=self.capacity,
            thread_name_prefix=f"pocketlab-{name.value.replace('_', '-')}",
        )
        self._lock = threading.RLock()
        self._accepting = True
        self._shutdown_state = "running"
        self._active = 0
        self._queued = 0
        self._admitted = 0
        self._tracked: set[asyncio.Task[Any]] = set()
        self._wait_samples: deque[float] = deque(maxlen=32)
        self._execution_samples: deque[float] = deque(maxlen=32)
        self._stats: dict[str, Any] = {
            "accepted": 0,
            "rejected": 0,
            "completed": 0,
            "failed": 0,
            "timed_out": 0,
            "cancelled": 0,
            "admission_wait_count": 0,
            "last_rejection_at": None,
            "last_timeout_at": None,
            "last_error_type": "",
        }

    def _try_admit(self) -> str | None:
        with self._lock:
            if not self._accepting:
                raise AdmissionShutdown("unknown", self.name, "Pocket Lab is shutting down.")
            if self._admitted >= self.capacity + self.queue_capacity:
                return None
            self._admitted += 1
            if self._active < self.capacity:
                self._active += 1
                return "active"
            self._queued += 1
            return "queued"

    async def _admit(self, operation_id: str, timeout_seconds: float) -> float:
        started = time.monotonic()
        waited = False
        admitted = False
        owns_active = False
        try:
            while True:
                try:
                    admission_state = self._try_admit()
                except AdmissionShutdown as exc:
                    exc.operation_id = operation_id
                    raise
                admitted = admission_state is not None
                if admitted:
                    owns_active = admission_state == "active"
                    waited = admission_state == "queued"
                    break
                if timeout_seconds <= 0:
                    self._record_rejection("AdmissionQueueFull")
                    raise AdmissionQueueFull(
                        operation_id,
                        self.name,
                        "Pocket Lab is busy with another safe operation. Try again shortly.",
                    )
                waited = True
                elapsed = time.monotonic() - started
                if elapsed >= timeout_seconds:
                    self._record_timeout("AdmissionTimeout")
                    self._record_rejection("AdmissionTimeout")
                    raise AdmissionTimeout(
                        operation_id,
                        self.name,
                        "Pocket Lab is busy. Try again shortly.",
                    )
                await asyncio.sleep(min(0.01, max(0.001, timeout_seconds - elapsed)))
            if waited:
                with self._lock:
                    self._stats["admission_wait_count"] += 1
            # A total admission slot is reserved. Wait until this admission owns
            # one active worker before submitting, so ThreadPoolExecutor's
            # internal queue never becomes the actual admission queue.
            if not owns_active:
                while True:
                    with self._lock:
                        if not self._accepting:
                            self._queued = max(0, self._queued - 1)
                            self._admitted = max(0, self._admitted - 1)
                            admitted = False
                            raise AdmissionShutdown(
                                operation_id, self.name, "Pocket Lab is shutting down."
                            )
                        if self._queued > 0 and self._active < self.capacity:
                            self._queued -= 1
                            self._active += 1
                            owns_active = True
                            break
                    elapsed = time.monotonic() - started
                    if elapsed >= timeout_seconds:
                        with self._lock:
                            self._queued = max(0, self._queued - 1)
                            self._admitted = max(0, self._admitted - 1)
                        admitted = False
                        self._record_timeout("AdmissionTimeout")
                        self._record_rejection("AdmissionTimeout")
                        raise AdmissionTimeout(
                            operation_id,
                            self.name,
                            "Pocket Lab is busy. Try again shortly.",
                        )
                    await asyncio.sleep(
                        min(0.01, max(0.001, timeout_seconds - elapsed))
                    )
            wait_ms = max(0.0, (time.monotonic() - started) * 1000.0)
            with self._lock:
                self._wait_samples.append(wait_ms)
                self._stats["accepted"] += 1
            return wait_ms
        except asyncio.CancelledError:
            if admitted:
                with self._lock:
                    if owns_active:
                        self._active = max(0, self._active - 1)
                    else:
                        self._queued = max(0, self._queued - 1)
                    self._admitted = max(0, self._admitted - 1)
                    self._stats["cancelled"] += 1
            raise

    def _record_rejection(self, error_type: str) -> None:
        with self._lock:
            self._stats["rejected"] += 1
            self._stats["last_rejection_at"] = _utc_now()
            self._stats["last_error_type"] = error_type[:64]

    def _record_timeout(self, error_type: str) -> None:
        with self._lock:
            self._stats["timed_out"] += 1
            self._stats["last_timeout_at"] = _utc_now()
            self._stats["last_error_type"] = error_type[:64]

    def _release_active(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)
            self._admitted = max(0, self._admitted - 1)

    async def run(
        self,
        operation: WorkloadDefinition,
        function: Callable[..., Any],
        /,
        *args: Any,
        admission_timeout_seconds: float,
        deadline_seconds: float,
        diagnostic_name: str | None = None,
        **kwargs: Any,
    ) -> tuple[Any, dict[str, Any]]:
        wait_ms = await self._admit(operation.operation_id, admission_timeout_seconds)
        submitted = time.monotonic()
        loop = asyncio.get_running_loop()

        def invoke() -> tuple[Any, float, float, float, float]:
            started = time.monotonic()
            process_cpu = time.process_time()
            thread_cpu = time.thread_time()
            token = RUNTIME_DIAGNOSTICS.begin_operation(
                str(diagnostic_name or operation.operation_id)[:80]
            )
            result_name = "ok"
            try:
                value = function(*args, **kwargs)
                return (
                    value,
                    started,
                    time.monotonic(),
                    process_cpu,
                    time.process_time(),
                    thread_cpu,
                    time.thread_time(),
                )
            except Exception:
                result_name = "failed"
                raise
            finally:
                RUNTIME_DIAGNOSTICS.end_operation(token, result=result_name)

        executor_future = loop.run_in_executor(self._executor, invoke)

        async def complete() -> tuple[Any, dict[str, Any]]:
            result_name = "ok"
            try:
                (
                    value, started, completed, process_cpu, completed_process_cpu,
                    thread_cpu, completed_thread_cpu,
                ) = await executor_future
                execution_ms = max(0.0, (completed - started) * 1000.0)
                with self._lock:
                    self._stats["completed"] += 1
                    self._execution_samples.append(execution_ms)
                return value, {
                    "admission_class": self.name.value,
                    "admission_wait_ms": wait_ms,
                    "queue_wait_ms": wait_ms,
                    "execution_ms": execution_ms,
                    "total_ms": max(0.0, (completed - submitted) * 1000.0),
                    "process_cpu_ms": max(0.0, (completed_process_cpu - process_cpu) * 1000.0),
                    "thread_cpu_ms": max(0.0, (completed_thread_cpu - thread_cpu) * 1000.0),
                    "thread_kind": "maintenance_executor",
                    "result": result_name,
                }
            except Exception as exc:
                result_name = "failed"
                with self._lock:
                    self._stats["failed"] += 1
                    self._stats["last_error_type"] = type(exc).__name__[:64]
                raise
            finally:
                self._release_active()

        completion_task = asyncio.create_task(
            complete(), name=f"pocketlab-admission-{operation.operation_id[:48]}"
        )
        with self._lock:
            self._tracked.add(completion_task)

        def consume_and_forget(task: asyncio.Task[Any]) -> None:
            with self._lock:
                self._tracked.discard(task)
            try:
                task.exception()
            except (asyncio.CancelledError, Exception):
                pass

        completion_task.add_done_callback(consume_and_forget)
        try:
            return await asyncio.wait_for(
                asyncio.shield(completion_task), timeout=max(0.01, deadline_seconds)
            )
        except asyncio.TimeoutError as exc:
            self._record_timeout("OperationDeadlineExceeded")
            raise OperationDeadlineExceeded(
                operation.operation_id,
                self.name,
                "Pocket Lab is still finishing a safe operation. Check status shortly.",
            ) from exc
        except asyncio.CancelledError:
            with self._lock:
                self._stats["cancelled"] += 1
            # Shielded authoritative/local work continues and releases admission
            # only when the worker thread actually exits.
            raise

    async def shutdown(self, drain_timeout_seconds: float) -> None:
        with self._lock:
            self._accepting = False
            self._shutdown_state = "draining"
            tracked = list(self._tracked)
        if tracked:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*(asyncio.shield(task) for task in tracked), return_exceptions=True),
                    timeout=max(0.1, drain_timeout_seconds),
                )
            except asyncio.TimeoutError:
                pass
        self._executor.shutdown(wait=False, cancel_futures=True)
        with self._lock:
            self._shutdown_state = "stopped"

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            wait_values = list(self._wait_samples)
            execution_values = list(self._execution_samples)
            return {
                "name": self.name.value,
                "capacity": self.capacity,
                "queue_capacity": self.queue_capacity,
                "active": self._active,
                "queued": self._queued,
                "accepted": int(self._stats["accepted"]),
                "rejected": int(self._stats["rejected"]),
                "completed": int(self._stats["completed"]),
                "failed": int(self._stats["failed"]),
                "timed_out": int(self._stats["timed_out"]),
                "cancelled": int(self._stats["cancelled"]),
                "admission_wait_count": int(self._stats["admission_wait_count"]),
                "recent_admission_wait_ms": round(wait_values[-1] if wait_values else 0.0, 2),
                "recent_max_admission_wait_ms": round(max(wait_values, default=0.0), 2),
                "recent_execution_ms": round(execution_values[-1] if execution_values else 0.0, 2),
                "recent_max_execution_ms": round(max(execution_values, default=0.0), 2),
                "last_rejection_at": self._stats["last_rejection_at"],
                "last_timeout_at": self._stats["last_timeout_at"],
                "last_error_type": self._stats["last_error_type"],
                "running": self._shutdown_state == "running",
                "shutdown_state": self._shutdown_state,
            }


class WorkloadAdmissionManager:
    def __init__(self, configs: Mapping[AdmissionClass, AdmissionClassConfig] | None = None) -> None:
        self.default_admission_timeout_seconds = _bounded_float(
            "POCKETLAB_ADMISSION_TIMEOUT_SECONDS", 0.35, 0.0, 30.0
        )
        self.default_operation_deadline_seconds = _bounded_float(
            "POCKETLAB_OPERATION_DEADLINE_SECONDS", 15.0, 0.1, 3600.0
        )
        self.shutdown_drain_timeout_seconds = _bounded_float(
            "POCKETLAB_ADMISSION_SHUTDOWN_DRAIN_SECONDS", 5.0, 0.1, 60.0
        )
        self._configs = dict(configs or self._settings_from_environment())
        self._lock = threading.RLock()
        self._lanes: dict[AdmissionClass, _BoundedAdmissionLane] = {}
        self._started = False
        self._shutdown_state = "not_started"

    @staticmethod
    def _settings_from_environment() -> dict[AdmissionClass, AdmissionClassConfig]:
        def config(prefix: str, capacity: int, queue_capacity: int, max_capacity: int = 8) -> AdmissionClassConfig:
            return AdmissionClassConfig(
                capacity=_bounded_int(f"POCKETLAB_ADMISSION_{prefix}_CONCURRENCY", capacity, 1, max_capacity),
                queue_capacity=_bounded_int(f"POCKETLAB_ADMISSION_{prefix}_QUEUED", queue_capacity, 0, 64),
            )

        return {
            AdmissionClass.COMMAND_RESERVATION: config("RESERVATION", 1, 2, 4),
            AdmissionClass.LIFECYCLE_WRITE: config("LIFECYCLE", 1, 4, 4),
            AdmissionClass.MAINTENANCE_READ: config("MAINTENANCE", 2, 4, 8),
            AdmissionClass.COMPATIBILITY_WRITE: config("COMPATIBILITY", 1, 4, 4),
            AdmissionClass.AUDIT_AGGREGATION: config("AUDIT", 1, 2, 4),
            AdmissionClass.SYSTEM_PROBE: config("SYSTEM_PROBE", 2, 2, 8),
            AdmissionClass.CPU_NORMALIZATION: config("NORMALIZATION", 1, 2, 4),
        }

    async def start(self) -> bool:
        with self._lock:
            if self._started:
                return False
            self._lanes = {
                name: _BoundedAdmissionLane(name, config)
                for name, config in self._configs.items()
            }
            self._started = True
            self._shutdown_state = "running"
        return True

    async def _ensure_started(self) -> None:
        with self._lock:
            started = self._started
            state = self._shutdown_state
        if state in {"draining", "stopped"}:
            raise AdmissionShutdown(
                "unknown", AdmissionClass.MAINTENANCE_READ, "Pocket Lab is shutting down."
            )
        if not started:
            await self.start()

    def definition(self, operation_id: str) -> WorkloadDefinition:
        try:
            return WORKLOADS[operation_id]
        except KeyError as exc:
            raise ExecutorUnavailable(
                operation_id,
                AdmissionClass.MAINTENANCE_READ,
                "This control-plane operation is not classified.",
            ) from exc

    async def run(
        self,
        operation_id: str,
        function: Callable[..., Any],
        /,
        *args: Any,
        admission_timeout_seconds: float | None = None,
        deadline_seconds: float | None = None,
        diagnostic_name: str | None = None,
        **kwargs: Any,
    ) -> tuple[Any, dict[str, Any]]:
        await self._ensure_started()
        operation = self.definition(operation_id)
        if operation.execution_owner is not ExecutionOwner.BOUNDED_MAINTENANCE:
            raise ExecutorUnavailable(
                operation_id,
                operation.admission_class,
                "This operation is not owned by the FastAPI maintenance executor.",
            )
        lane = self._lanes.get(operation.admission_class)
        if lane is None:
            raise ExecutorUnavailable(
                operation_id,
                operation.admission_class,
                "The bounded maintenance executor is unavailable.",
            )
        return await lane.run(
            operation,
            function,
            *args,
            admission_timeout_seconds=(
                self.default_admission_timeout_seconds
                if admission_timeout_seconds is None
                else max(0.0, min(float(admission_timeout_seconds), 30.0))
            ),
            deadline_seconds=(
                min(
                    operation.default_deadline_seconds,
                    self.default_operation_deadline_seconds,
                )
                if deadline_seconds is None
                else max(0.01, min(float(deadline_seconds), 3600.0))
            ),
            diagnostic_name=diagnostic_name or operation_id,
            **kwargs,
        )

    async def shutdown(self) -> None:
        with self._lock:
            if not self._started or self._shutdown_state in {"draining", "stopped"}:
                return
            self._shutdown_state = "draining"
            lanes = list(self._lanes.values())
        await asyncio.gather(
            *(lane.shutdown(self.shutdown_drain_timeout_seconds) for lane in lanes),
            return_exceptions=True,
        )
        with self._lock:
            self._shutdown_state = "stopped"
            self._started = False

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            lanes = dict(self._lanes)
            state = self._shutdown_state
        configs = {
            name.value: {
                "capacity": config.capacity,
                "queue_capacity": config.queue_capacity,
            }
            for name, config in self._configs.items()
        }
        metrics = {
            name.value: lane.snapshot()
            for name, lane in sorted(lanes.items(), key=lambda item: item[0].value)
        }
        # Before startup, expose effective sanitized configuration and zero metrics.
        for name, config in self._configs.items():
            metrics.setdefault(
                name.value,
                {
                    "name": name.value,
                    "capacity": config.capacity,
                    "queue_capacity": config.queue_capacity,
                    "active": 0,
                    "queued": 0,
                    "accepted": 0,
                    "rejected": 0,
                    "completed": 0,
                    "failed": 0,
                    "timed_out": 0,
                    "cancelled": 0,
                    "admission_wait_count": 0,
                    "recent_admission_wait_ms": 0.0,
                    "recent_max_admission_wait_ms": 0.0,
                    "recent_execution_ms": 0.0,
                    "recent_max_execution_ms": 0.0,
                    "last_rejection_at": None,
                    "last_timeout_at": None,
                    "last_error_type": "",
                    "running": False,
                    "shutdown_state": state,
                },
            )
        return {
            "status": "running" if state == "running" else state,
            "default_admission_timeout_seconds": self.default_admission_timeout_seconds,
            "default_operation_deadline_seconds": self.default_operation_deadline_seconds,
            "shutdown_drain_timeout_seconds": self.shutdown_drain_timeout_seconds,
            "effective_configuration": configs,
            "classes": metrics,
            "sanitized": True,
        }


def workload_classification_snapshot() -> list[dict[str, Any]]:
    return [WORKLOADS[key].snapshot() for key in sorted(WORKLOADS)]


WORKLOAD_ADMISSION = WorkloadAdmissionManager()
