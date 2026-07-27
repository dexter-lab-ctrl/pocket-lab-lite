from __future__ import annotations

"""Bounded CPU attribution for FastAPI-owned background work.

The profiler records aggregate wall/CPU timings only. It never captures payloads,
arguments, secrets, stack traces, or user data. Persistence is best effort and
change-only so diagnostics cannot become a new hot path.
"""

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import os
import threading
import time
from typing import Any, Iterator

from ..db.runtime import SQLITE_WRITER


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


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass(slots=True)
class _Metric:
    runs: int = 0
    failures: int = 0
    deadline_exceeded: int = 0
    changed_commits: int = 0
    unchanged_commits: int = 0
    skipped_unchanged: int = 0
    coalesced: int = 0
    wall_ms_total: float = 0.0
    cpu_ms_total: float = 0.0
    wall_ms_max: float = 0.0
    cpu_ms_max: float = 0.0
    last_wall_ms: float = 0.0
    last_cpu_ms: float = 0.0
    last_outcome: str = "never"
    last_error_type: str = ""
    last_started_at: str | None = None
    last_completed_at: str | None = None
    recent_cpu_ms: deque[float] = field(default_factory=lambda: deque(maxlen=64))
    recent_wall_ms: deque[float] = field(default_factory=lambda: deque(maxlen=64))
    persisted_checksum: str = ""


class HotPathProfiler:
    def __init__(self) -> None:
        self.enabled = os.environ.get("POCKETLAB_HOT_PATH_PROFILER_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
        self.max_jobs = _bounded_int("POCKETLAB_HOT_PATH_MAX_JOBS", 96, 16, 512)
        self.persist_every_runs = _bounded_int("POCKETLAB_HOT_PATH_PERSIST_EVERY_RUNS", 8, 1, 128)
        self.cpu_warning_ms = _bounded_float("POCKETLAB_HOT_PATH_CPU_WARNING_MS", 250.0, 1.0, 120_000.0)
        self.wall_warning_ms = _bounded_float("POCKETLAB_HOT_PATH_WALL_WARNING_MS", 500.0, 1.0, 300_000.0)
        self._lock = threading.RLock()
        self._metrics: dict[str, _Metric] = {}
        self._evictions = 0
        self._persist_failures = 0
        self._schema_ready = False

    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(ch for ch in str(value or "unknown") if ch.isalnum() or ch in "._:-")[:120] or "unknown"

    def _metric(self, name: str) -> _Metric:
        safe = self._safe_name(name)
        metric = self._metrics.get(safe)
        if metric is not None:
            return metric
        if len(self._metrics) >= self.max_jobs:
            victim = min(self._metrics, key=lambda key: self._metrics[key].last_completed_at or "")
            self._metrics.pop(victim, None)
            self._evictions += 1
        metric = _Metric()
        self._metrics[safe] = metric
        return metric

    @contextmanager
    def measure(self, name: str) -> Iterator[dict[str, Any]]:
        if not self.enabled:
            result: dict[str, Any] = {}
            yield result
            return
        safe = self._safe_name(name)
        wall_started = time.monotonic()
        cpu_started = time.thread_time() if hasattr(time, "thread_time") else time.process_time()
        started_at = _utc_now()
        outcome: dict[str, Any] = {"outcome": "completed", "changed": None, "error_type": ""}
        try:
            yield outcome
        except Exception as exc:
            outcome["outcome"] = "failed"
            outcome["error_type"] = type(exc).__name__
            raise
        finally:
            cpu_now = time.thread_time() if hasattr(time, "thread_time") else time.process_time()
            wall_ms = max(0.0, (time.monotonic() - wall_started) * 1000.0)
            cpu_ms = max(0.0, (cpu_now - cpu_started) * 1000.0)
            self.record(
                safe,
                wall_ms=wall_ms,
                cpu_ms=cpu_ms,
                outcome=str(outcome.get("outcome") or "completed"),
                changed=outcome.get("changed"),
                error_type=str(outcome.get("error_type") or ""),
                started_at=started_at,
            )

    def record(
        self,
        name: str,
        *,
        wall_ms: float,
        cpu_ms: float,
        outcome: str = "completed",
        changed: bool | None = None,
        error_type: str = "",
        started_at: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        safe = self._safe_name(name)
        with self._lock:
            metric = self._metric(safe)
            metric.runs += 1
            metric.wall_ms_total += max(0.0, wall_ms)
            metric.cpu_ms_total += max(0.0, cpu_ms)
            metric.wall_ms_max = max(metric.wall_ms_max, wall_ms)
            metric.cpu_ms_max = max(metric.cpu_ms_max, cpu_ms)
            metric.last_wall_ms = max(0.0, wall_ms)
            metric.last_cpu_ms = max(0.0, cpu_ms)
            metric.last_outcome = str(outcome or "completed")[:40]
            metric.last_error_type = str(error_type or "")[:80]
            metric.last_started_at = started_at or _utc_now()
            metric.last_completed_at = _utc_now()
            metric.recent_cpu_ms.append(metric.last_cpu_ms)
            metric.recent_wall_ms.append(metric.last_wall_ms)
            if metric.last_outcome == "failed":
                metric.failures += 1
            if metric.last_outcome in {"deadline", "deadline_exceeded"}:
                metric.deadline_exceeded += 1
            if changed is True:
                metric.changed_commits += 1
            elif changed is False:
                metric.unchanged_commits += 1
            should_persist = metric.runs == 1 or metric.runs % self.persist_every_runs == 0 or metric.last_outcome != "completed"
        if should_persist:
            self._persist_best_effort(safe)

    def increment(self, name: str, field: str, amount: int = 1) -> None:
        if not self.enabled or field not in {"skipped_unchanged", "coalesced"}:
            return
        with self._lock:
            metric = self._metric(name)
            setattr(metric, field, max(0, int(getattr(metric, field)) + max(0, int(amount))))

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        ordered = sorted(max(0.0, float(value)) for value in values)
        if not ordered:
            return 0.0
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * max(0.0, min(1.0, percentile))
        lower = int(position)
        upper = min(len(ordered) - 1, lower + 1)
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    def _snapshot_metric(self, name: str, metric: _Metric) -> dict[str, Any]:
        runs = max(1, metric.runs)
        recent_cpu = list(metric.recent_cpu_ms)
        recent_wall = list(metric.recent_wall_ms)
        return {
            "job": name,
            "runs": metric.runs,
            "failures": metric.failures,
            "deadline_exceeded": metric.deadline_exceeded,
            "changed_commits": metric.changed_commits,
            "unchanged_commits": metric.unchanged_commits,
            "skipped_unchanged": metric.skipped_unchanged,
            "coalesced": metric.coalesced,
            "cpu_ms_total": round(metric.cpu_ms_total, 2),
            "cpu_ms_average": round(metric.cpu_ms_total / runs, 2),
            "cpu_ms_last": round(metric.last_cpu_ms, 2),
            "cpu_ms_max": round(metric.cpu_ms_max, 2),
            "recent_cpu_ms_average": round(sum(recent_cpu) / max(1, len(recent_cpu)), 2),
            "recent_sample_count": len(recent_cpu),
            "cpu_ms_p50": round(self._percentile(recent_cpu, 0.50), 2),
            "cpu_ms_p95": round(self._percentile(recent_cpu, 0.95), 2),
            "cpu_ms_p99": round(self._percentile(recent_cpu, 0.99), 2),
            "wall_ms_total": round(metric.wall_ms_total, 2),
            "wall_ms_average": round(metric.wall_ms_total / runs, 2),
            "wall_ms_last": round(metric.last_wall_ms, 2),
            "wall_ms_max": round(metric.wall_ms_max, 2),
            "recent_wall_ms_average": round(sum(recent_wall) / max(1, len(recent_wall)), 2),
            "wall_ms_p50": round(self._percentile(recent_wall, 0.50), 2),
            "wall_ms_p95": round(self._percentile(recent_wall, 0.95), 2),
            "wall_ms_p99": round(self._percentile(recent_wall, 0.99), 2),
            "last_outcome": metric.last_outcome,
            "last_error_type": metric.last_error_type,
            "last_started_at": metric.last_started_at,
            "last_completed_at": metric.last_completed_at,
            "cpu_budget_warning": metric.last_cpu_ms >= self.cpu_warning_ms or metric.cpu_ms_max >= self.cpu_warning_ms,
            "wall_budget_warning": metric.last_wall_ms >= self.wall_warning_ms or metric.wall_ms_max >= self.wall_warning_ms,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [self._snapshot_metric(name, metric) for name, metric in self._metrics.items()]
            evictions = self._evictions
            persist_failures = self._persist_failures
        rows.sort(key=lambda row: (row["cpu_ms_total"], row["wall_ms_total"]), reverse=True)
        return {
            "enabled": self.enabled,
            "cpu_warning_ms": self.cpu_warning_ms,
            "wall_warning_ms": self.wall_warning_ms,
            "job_count": len(rows),
            "evictions": evictions,
            "persistence_failures": persist_failures,
            "top_cpu_jobs": rows[:20],
            "top_wall_jobs": sorted(rows, key=lambda row: row["wall_ms_total"], reverse=True)[:20],
            "jobs": rows,
            "sanitized": True,
        }

    def _persist_best_effort(self, name: str) -> None:
        with self._lock:
            metric = self._metrics.get(name)
            if metric is None:
                return
            row = self._snapshot_metric(name, metric)
            material = json.dumps(row, sort_keys=True, separators=(",", ":"))
            checksum = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if checksum == metric.persisted_checksum:
                return

        def write(conn):
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_hot_path_metrics(
                    job TEXT PRIMARY KEY,
                    runs INTEGER NOT NULL,
                    failures INTEGER NOT NULL,
                    deadline_exceeded INTEGER NOT NULL,
                    changed_commits INTEGER NOT NULL,
                    unchanged_commits INTEGER NOT NULL,
                    skipped_unchanged INTEGER NOT NULL,
                    coalesced INTEGER NOT NULL,
                    cpu_ms_total REAL NOT NULL,
                    cpu_ms_max REAL NOT NULL,
                    wall_ms_total REAL NOT NULL,
                    wall_ms_max REAL NOT NULL,
                    last_outcome TEXT NOT NULL,
                    last_error_type TEXT NOT NULL,
                    last_completed_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO runtime_hot_path_metrics(
                    job,runs,failures,deadline_exceeded,changed_commits,unchanged_commits,
                    skipped_unchanged,coalesced,cpu_ms_total,cpu_ms_max,wall_ms_total,
                    wall_ms_max,last_outcome,last_error_type,last_completed_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job) DO UPDATE SET
                    runs=excluded.runs, failures=excluded.failures,
                    deadline_exceeded=excluded.deadline_exceeded,
                    changed_commits=excluded.changed_commits,
                    unchanged_commits=excluded.unchanged_commits,
                    skipped_unchanged=excluded.skipped_unchanged,
                    coalesced=excluded.coalesced,
                    cpu_ms_total=excluded.cpu_ms_total, cpu_ms_max=excluded.cpu_ms_max,
                    wall_ms_total=excluded.wall_ms_total, wall_ms_max=excluded.wall_ms_max,
                    last_outcome=excluded.last_outcome,
                    last_error_type=excluded.last_error_type,
                    last_completed_at=excluded.last_completed_at,
                    updated_at=excluded.updated_at
                """,
                (
                    row["job"], row["runs"], row["failures"], row["deadline_exceeded"],
                    row["changed_commits"], row["unchanged_commits"], row["skipped_unchanged"],
                    row["coalesced"], row["cpu_ms_total"], row["cpu_ms_max"],
                    row["wall_ms_total"], row["wall_ms_max"], row["last_outcome"],
                    row["last_error_type"], row["last_completed_at"], _utc_now(),
                ),
            )

        try:
            SQLITE_WRITER.submit("runtime.hot_path.metrics", write, deadline_seconds=0.5)
            with self._lock:
                current = self._metrics.get(name)
                if current is not None:
                    current.persisted_checksum = checksum
                self._schema_ready = True
        except Exception:
            with self._lock:
                self._persist_failures += 1


HOT_PATH_PROFILER = HotPathProfiler()
