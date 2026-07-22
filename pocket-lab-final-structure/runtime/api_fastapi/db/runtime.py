from __future__ import annotations

import os
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from .connection import database_path, open_connection


T = TypeVar("T")


class SQLiteWriteRejected(RuntimeError):
    """A bounded process-local SQLite write could not be admitted."""


class SQLiteWriteDeadlineExceeded(SQLiteWriteRejected):
    """A queued write exceeded its caller-visible deadline."""


@dataclass
class _WriteRequest(Generic[T]):
    operation: str
    callback: Callable[[sqlite3.Connection], T]
    enqueued_at: float
    deadline_at: float
    completed: threading.Event
    result: T | None = None
    error: BaseException | None = None


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))




def _database_identity() -> str:
    path = database_path()
    try:
        stat = path.stat()
        return f"{path}:{stat.st_dev}:{stat.st_ino}"
    except OSError:
        return f"{path}:missing"


class SQLiteWriteService:
    """One bounded process-local writer for short SQLite transactions.

    Callbacks must only perform bounded SQLite work. Network, shell, filesystem
    traversal and subprocess work are intentionally outside this service.
    """

    def __init__(self, *, max_queue: int | None = None) -> None:
        self.max_queue = max_queue or _bounded_int(
            "POCKETLAB_LITE_DB_WRITE_QUEUE", 64, 4, 1024
        )
        self._queue: queue.Queue[_WriteRequest[Any] | None] = queue.Queue(
            maxsize=self.max_queue
        )
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._shutdown = False
        self._metrics: dict[str, float | int] = {
            "write_count": 0,
            "rejected_writes": 0,
            "busy_retries": 0,
            "deadline_expiry": 0,
            "rollback_count": 0,
            "queue_wait_ms_total": 0.0,
            "transaction_ms_total": 0.0,
            "queue_wait_ms_max": 0.0,
            "transaction_ms_max": 0.0,
        }

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            if self._shutdown:
                raise SQLiteWriteRejected("SQLite writer is shut down")
            self._thread = threading.Thread(
                target=self._run,
                name="pocketlab-sqlite-single-writer",
                daemon=True,
            )
            self._thread.start()

    def submit(
        self,
        operation: str,
        callback: Callable[[sqlite3.Connection], T],
        *,
        deadline_seconds: float = 2.0,
    ) -> T:
        self.start()
        now = time.monotonic()
        bounded_deadline = max(0.05, min(float(deadline_seconds), 30.0))
        request: _WriteRequest[T] = _WriteRequest(
            operation=str(operation or "sqlite.write")[:80],
            callback=callback,
            enqueued_at=now,
            deadline_at=now + bounded_deadline,
            completed=threading.Event(),
        )
        try:
            self._queue.put_nowait(request)
        except queue.Full as exc:
            self._increment("rejected_writes")
            raise SQLiteWriteRejected("SQLite write queue is full") from exc
        remaining = request.deadline_at - time.monotonic()
        if remaining <= 0 or not request.completed.wait(remaining):
            self._increment("deadline_expiry")
            raise SQLiteWriteDeadlineExceeded("SQLite write deadline expired")
        if request.error is not None:
            raise request.error
        return request.result  # type: ignore[return-value]

    def _run(self) -> None:
        conn: sqlite3.Connection | None = None
        connection_identity = ""
        try:
            while True:
                request = self._queue.get()
                if request is None:
                    return
                if time.monotonic() >= request.deadline_at:
                    self._increment("deadline_expiry")
                    request.error = SQLiteWriteDeadlineExceeded(
                        "SQLite write expired before execution"
                    )
                    request.completed.set()
                    continue
                current_identity = _database_identity()
                if conn is None or connection_identity != current_identity:
                    if conn is not None:
                        conn.close()
                    conn = open_connection(read_only=False)
                    connection_identity = current_identity
                queue_wait_ms = max(
                    0.0, (time.monotonic() - request.enqueued_at) * 1000.0
                )
                started = time.monotonic()
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    request.result = request.callback(conn)
                    if time.monotonic() >= request.deadline_at:
                        raise SQLiteWriteDeadlineExceeded(
                            "SQLite write deadline expired during transaction"
                        )
                    conn.execute("COMMIT")
                    self._increment("write_count")
                except sqlite3.OperationalError as exc:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    self._increment("rollback_count")
                    if "busy" in str(exc).lower() or "locked" in str(exc).lower():
                        self._increment("busy_retries")
                    request.error = exc
                except BaseException as exc:  # keep writer alive after callback failures
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    self._increment("rollback_count")
                    request.error = exc
                finally:
                    transaction_ms = max(
                        0.0, (time.monotonic() - started) * 1000.0
                    )
                    self._observe(queue_wait_ms, transaction_ms)
                    request.completed.set()
        finally:
            if conn is not None:
                conn.close()

    def _increment(self, key: str) -> None:
        with self._metrics_lock:
            self._metrics[key] = int(self._metrics.get(key, 0)) + 1

    def _observe(self, queue_wait_ms: float, transaction_ms: float) -> None:
        with self._metrics_lock:
            self._metrics["queue_wait_ms_total"] = float(
                self._metrics["queue_wait_ms_total"]
            ) + queue_wait_ms
            self._metrics["transaction_ms_total"] = float(
                self._metrics["transaction_ms_total"]
            ) + transaction_ms
            self._metrics["queue_wait_ms_max"] = max(
                float(self._metrics["queue_wait_ms_max"]), queue_wait_ms
            )
            self._metrics["transaction_ms_max"] = max(
                float(self._metrics["transaction_ms_max"]), transaction_ms
            )

    def snapshot(self) -> dict[str, Any]:
        with self._metrics_lock:
            metrics = dict(self._metrics)
        writes = max(1, int(metrics.get("write_count") or 0))
        metrics.update(
            {
                "queue_depth": self._queue.qsize(),
                "queue_capacity": self.max_queue,
                "queue_wait_ms_avg": round(
                    float(metrics["queue_wait_ms_total"]) / writes, 3
                ),
                "transaction_ms_avg": round(
                    float(metrics["transaction_ms_total"]) / writes, 3
                ),
                "running": bool(self._thread and self._thread.is_alive()),
                "sanitized": True,
            }
        )
        return metrics

    def shutdown(self, *, timeout_seconds: float = 5.0) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            thread = self._thread
        if thread is not None and thread.is_alive():
            try:
                self._queue.put(None, timeout=max(0.1, timeout_seconds))
            except queue.Full:
                pass
            thread.join(timeout=max(0.1, timeout_seconds))


@dataclass
class _ReadEntry:
    connection: sqlite3.Connection
    generation: int
    database_identity: str
    opened_at: float
    last_used_at: float


class SQLiteReadConnectionManager:
    """Small bounded read-only connection pool with explicit generation fencing."""

    def __init__(self, *, max_connections: int | None = None) -> None:
        self.max_connections = max_connections or _bounded_int(
            "POCKETLAB_LITE_DB_READ_CONNECTIONS", 3, 1, 8
        )
        self.idle_seconds = _bounded_int(
            "POCKETLAB_LITE_DB_READ_IDLE_SECONDS", 60, 5, 600
        )
        self._available: queue.LifoQueue[_ReadEntry] = queue.LifoQueue(
            maxsize=self.max_connections
        )
        self._semaphore = threading.BoundedSemaphore(self.max_connections)
        self._generation = 1
        self._lock = threading.Lock()
        self._metrics = {
            "acquired": 0,
            "created": 0,
            "reused": 0,
            "invalidated": 0,
            "health_failures": 0,
            "acquire_timeout": 0,
        }

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def acquire(self, *, timeout_seconds: float = 1.0) -> tuple[_ReadEntry, float]:
        started = time.monotonic()
        if not self._semaphore.acquire(timeout=max(0.01, min(timeout_seconds, 5.0))):
            with self._lock:
                self._metrics["acquire_timeout"] += 1
            raise TimeoutError("SQLite read connection acquisition timed out")
        generation = self.generation
        current_identity = _database_identity()
        entry: _ReadEntry | None = None
        while entry is None:
            try:
                candidate = self._available.get_nowait()
            except queue.Empty:
                break
            expired = time.monotonic() - candidate.last_used_at > self.idle_seconds
            if (
                candidate.generation != generation
                or candidate.database_identity != current_identity
                or expired
                or not self._healthy(candidate)
            ):
                candidate.connection.close()
                continue
            entry = candidate
            with self._lock:
                self._metrics["reused"] += 1
        if entry is None:
            conn = open_connection(read_only=True)
            now = time.monotonic()
            entry = _ReadEntry(conn, generation, current_identity, now, now)
            with self._lock:
                self._metrics["created"] += 1
        with self._lock:
            self._metrics["acquired"] += 1
        return entry, max(0.0, (time.monotonic() - started) * 1000.0)

    def release(self, entry: _ReadEntry, *, discard: bool = False) -> None:
        try:
            entry.last_used_at = time.monotonic()
            if discard or entry.generation != self.generation:
                entry.connection.close()
            else:
                try:
                    self._available.put_nowait(entry)
                except queue.Full:
                    entry.connection.close()
        finally:
            self._semaphore.release()

    def _healthy(self, entry: _ReadEntry) -> bool:
        try:
            row = entry.connection.execute("SELECT 1").fetchone()
            return bool(row and int(row[0]) == 1)
        except sqlite3.Error:
            with self._lock:
                self._metrics["health_failures"] += 1
            return False

    def invalidate(self) -> int:
        with self._lock:
            self._generation += 1
            self._metrics["invalidated"] += 1
            generation = self._generation
        while True:
            try:
                entry = self._available.get_nowait()
            except queue.Empty:
                break
            entry.connection.close()
        return generation

    def close(self) -> None:
        self.invalidate()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            metrics = dict(self._metrics)
            metrics["generation"] = self._generation
        metrics.update(
            {
                "available": self._available.qsize(),
                "capacity": self.max_connections,
                "sanitized": True,
            }
        )
        return metrics


SQLITE_WRITER = SQLiteWriteService()
SQLITE_READS = SQLiteReadConnectionManager()


def new_database_instance_id() -> str:
    return uuid.uuid4().hex
