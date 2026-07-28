# ruff: noqa: E402
from __future__ import annotations

"""Enterprise event-sourced workflow engine for Pocket Lab.

This service turns the Phase 11 reliability layer from a dead-letter list into
an event-sourced workflow projection engine.  It persists every Pocket Lab event
as an append-only log, maintains compact workflow projections, reconstructs a
workflow from events on demand, and can recover/replay interrupted or dead-lettered
commands without relying only on local JSON operation state.

The implementation is intentionally file-backed and dependency-light so it runs
on Android/Termux, but its model mirrors enterprise workflow engines:

* append-only event journal
* deterministic projections rebuilt from events
* terminal/non-terminal workflow state
* dead-letter correlation
* replay-as-new-workflow
* recovery plan + recovery execution
"""

import hashlib
import json
import os
import queue
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import deps
from ..db.connection import begin_immediate, connection, fast_read_connection
from ..db.migrations import apply_migrations

TERMINAL_TYPES = {
    "operation.succeeded",
    "operation.failed",
    "command.succeeded",
    "command.failed",
    "command.dead_lettered",
    "release.workflow.completed",
    "release.workflow.failed",
    "workflow.cancelled",
    "workflow.replayed",
}
SUCCESS_TYPES = {
    "operation.succeeded",
    "command.succeeded",
    "release.workflow.completed",
}
FAILURE_TYPES = {"operation.failed", "command.failed", "release.workflow.failed"}
DLQ_TYPES = {"command.dead_lettered"}
ACTIVE_TYPES = {
    "operation.created",
    "operation.execute.requested",
    "operation.worker_claimed",
    "command.queued",
    "command.worker_claimed",
    "release.workflow.started",
    "release.stage.started",
}

SENSITIVE_KEYS = {"api_key", "token", "password", "secret", "value", "authorization"}



def _safe(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: ("***" if str(k).lower() in SENSITIVE_KEYS else _safe(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_safe(v) for v in data]
    return data


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    """Atomically persist compact JSON with optional durability sync."""
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        if os.environ.get("POCKETLAB_WORKFLOW_FSYNC", "0").strip().lower() in {"1", "true", "yes", "on"}:
            os.fsync(handle.fileno())
    os.replace(tmp, path)


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        )


def workflow_id_for_event(event: Dict[str, Any]) -> str:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    for key in ("workflow_id", "trace_id", "job_id", "command_id", "run_id"):
        value = (
            data.get(key)
            if key != "trace_id"
            else (event.get("trace_id") or data.get("trace_id"))
        )
        if value:
            return str(value)
    subject = str(event.get("subject") or "workflow")
    return f"event-{subject.replace('.', '-')[:64]}"


def _event_sort_key(event: Dict[str, Any]) -> tuple[str, str]:
    return (str(event.get("time") or ""), str(event.get("id") or ""))


def _epoch_ms(value: Any = None) -> int:
    if value is None or value == "":
        return int(time.time() * 1000)
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number if number > 10_000_000_000 else number * 1000)
    try:
        from datetime import datetime

        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except (TypeError, ValueError):
        return int(time.time() * 1000)


def _safe_error_type(exc: BaseException | Any) -> str:
    text = type(exc).__name__ if isinstance(exc, BaseException) else str(exc or "UnknownError")
    return "".join(character for character in text if character.isalnum() or character in "._-")[:80] or "UnknownError"


_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(token|password|secret|api[_-]?key|authorization|private[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_NATS_URL_RE = re.compile(r"(?i)\bnats(?:s)?://[^\s,;]+")
_PRIVATE_PATH_RE = re.compile(
    r"(?i)(?:/data/data/[^\s,;]+|/storage/(?:emulated/)?[^\s,;]+|/sdcard/[^\s,;]+|/mnt/sdcard/[^\s,;]+|[a-z]:\\(?:users|windows)\\[^\s,;]+)"
)


def _bounded_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\x00", " ").strip()
    text = _SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _BEARER_RE.sub("Bearer [redacted]", text)
    text = _NATS_URL_RE.sub("[redacted-url]", text)
    text = _PRIVATE_PATH_RE.sub("[redacted-path]", text)
    return text[:limit]


_COMPACT_DATA_KEYS = frozenset({
    "workflow_id", "trace_id", "job_id", "command_id", "run_id", "operation",
    "command_subject", "subject", "attempt", "error", "terminal", "replay_of",
    "replayed_from_dead_letter", "replayed_from", "replayed_as", "app_id", "node_id",
    "device_id", "reason", "status", "stage", "profile", "action_id", "sequence",
})


def _compact_workflow_event(event: Dict[str, Any] | Any) -> Dict[str, Any] | None:
    """Return the bounded semantic event admitted to the projection process."""
    if not isinstance(event, dict):
        return None
    event_type = _bounded_text(event.get("type") or event.get("event"), 120)
    subject = _bounded_text(event.get("subject"), 180)
    if not event_type and not subject:
        return None
    event_id = _bounded_text(event.get("id"), 160) or uuid.uuid4().hex
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    compact_data: Dict[str, Any] = {}
    for key in _COMPACT_DATA_KEYS:
        if key not in data:
            continue
        value = data.get(key)
        if isinstance(value, bool):
            compact_data[key] = value
        elif isinstance(value, (int, float)):
            compact_data[key] = value
        elif value is not None:
            compact_data[key] = _bounded_text(value, 320 if key == "error" else 180)
    compact: Dict[str, Any] = {
        "id": event_id,
        "type": event_type,
        "subject": subject,
        "time": _bounded_text(event.get("time"), 64) or deps.now_utc_iso(),
        "trace_id": _bounded_text(event.get("trace_id"), 160),
        "data": compact_data,
    }
    compact["workflow_id"] = _bounded_text(event.get("workflow_id"), 160) or workflow_id_for_event(compact)
    return compact


def _canonical_projection_material(projection: Dict[str, Any]) -> tuple[Any, ...]:
    """Stable operational truth tuple; excludes timestamp/display-only churn."""
    return tuple(
        projection.get(key)
        for key in (
            "workflow_id", "status", "terminal", "success", "failed", "dead_lettered",
            "attempts", "command_subject", "operation", "job_id", "command_id",
            "last_error", "replay_of", "replayed_as",
        )
    )


def _apply_projection_event(current: Dict[str, Any] | None, event: Dict[str, Any]) -> Dict[str, Any]:
    projection = WorkflowProjection(
        **{
            key: value
            for key, value in (current or {}).items()
            if key in WorkflowProjection.__annotations__
        }
    ).asdict()
    was_terminal = bool(projection.get("terminal"))
    workflow_id = str(event.get("workflow_id") or workflow_id_for_event(event))
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    etype = str(event.get("type") or "")
    subject = str(event.get("subject") or "")
    now = str(event.get("time") or deps.now_utc_iso())
    projection["workflow_id"] = workflow_id
    projection["created_at"] = projection.get("created_at") or now
    projection["updated_at"] = now
    projection["event_count"] = int(projection.get("event_count") or 0) + 1
    projection["last_event_type"] = etype
    projection["last_subject"] = subject
    projection["job_id"] = str(data.get("job_id") or projection.get("job_id") or "")
    projection["command_id"] = str(data.get("command_id") or projection.get("command_id") or "")
    projection["operation"] = str(data.get("operation") or projection.get("operation") or "")
    projection["command_subject"] = str(
        data.get("command_subject")
        or data.get("subject")
        or (subject if subject.startswith("pocketlab.commands.") else projection.get("command_subject") or "")
    )
    try:
        attempt = int(data.get("attempt") or 0)
    except (TypeError, ValueError):
        attempt = 0
    projection["attempts"] = max(int(projection.get("attempts") or 0), attempt)
    if data.get("error"):
        projection["last_error"] = _bounded_text(data.get("error"), 320)
    if data.get("replayed_from_dead_letter") or data.get("replay_of"):
        projection["replay_of"] = str(data.get("replayed_from_dead_letter") or data.get("replay_of"))
    if data.get("replayed_as"):
        projection["replayed_as"] = str(data.get("replayed_as"))

    if was_terminal:
        # Terminal workflow truth is immutable. Late/redelivered non-terminal events
        # remain in the bounded event index but cannot regress last-known-good state.
        return projection
    if etype in SUCCESS_TYPES:
        projection.update({"status": "succeeded", "terminal": True, "success": True, "failed": False})
    elif etype in FAILURE_TYPES:
        projection.update({"status": "failed", "terminal": True, "success": False, "failed": True})
    elif etype in DLQ_TYPES or subject.startswith("pocketlab.dlq."):
        projection.update({"status": "dead_lettered", "terminal": True, "dead_lettered": True, "success": False, "failed": True})
    elif "retry" in etype:
        projection.update({"status": "retrying", "terminal": False})
    elif etype in ACTIVE_TYPES or subject.startswith("pocketlab.commands."):
        projection.update({"status": "running" if "claimed" in etype else "queued", "terminal": False})
    elif not projection.get("terminal"):
        projection["status"] = projection.get("status") if projection.get("status") not in {"unknown", ""} else "observed"

    if not projection.get("title") or projection.get("title") == "Pocket Lab workflow":
        op = projection.get("operation") or projection.get("command_subject") or subject or workflow_id
        projection["title"] = str(op).replace("pocketlab.commands.", "").replace(".", " ").strip().title()
    return projection


@dataclass
class WorkflowProjection:
    workflow_id: str
    status: str = "unknown"
    title: str = "Pocket Lab workflow"
    created_at: str = ""
    updated_at: str = ""
    terminal: bool = False
    success: bool = False
    failed: bool = False
    dead_lettered: bool = False
    event_count: int = 0
    attempts: int = 0
    command_subject: str = ""
    operation: str = ""
    job_id: str = ""
    command_id: str = ""
    last_error: str = ""
    last_event_type: str = ""
    last_subject: str = ""
    replay_of: str = ""
    replayed_as: str = ""

    def asdict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class EventSourcedWorkflowEngine:
    def __init__(self) -> None:
        self.history_limit = max(100, min(int(os.environ.get("POCKETLAB_WORKFLOW_HISTORY_LIMIT", "5000")), 100_000))
        self._status_cache: Dict[str, Any] | None = None
        self._status_cache_at = 0.0
        self._status_cache_ttl = max(1.0, float(os.environ.get("POCKETLAB_WORKFLOW_STATUS_CACHE_SECONDS", "15")))
        self._status_cache_lock = threading.RLock()
        self._path_lock = threading.RLock()
        self._root: Path | None = None
        self._event_log: Path | None = None
        self._projection_file: Path | None = None
        self._command_file: Path | None = None
        self._projection_lock = threading.RLock()
        self._projection_cache: Dict[str, Any] | None = None
        self._process_role = str(os.environ.get("POCKETLAB_PROCESS_ROLE") or "unknown").strip().lower()
        self._execution_owner = str(os.environ.get("POCKETLAB_WORKFLOW_PROCESS_OWNER") or "worker").strip().lower()
        self._owns_process = self._process_role == self._execution_owner
        self._writer_queue: queue.Queue[Dict[str, Any] | None] = queue.Queue(
            maxsize=max(8, min(int(os.environ.get("POCKETLAB_WORKFLOW_WRITER_QUEUE_SIZE", "256")), 4096))
        )
        self._writer_batch_size = max(1, min(int(os.environ.get("POCKETLAB_WORKFLOW_WRITER_BATCH_SIZE", "32")), 256))
        self._mailbox_capacity = max(16, min(int(os.environ.get("POCKETLAB_WORKFLOW_MAILBOX_CAPACITY", "1024")), 16_384))
        self._writer_thread: threading.Thread | None = None
        self._dispatcher_generation = 0
        self._writer_stop = threading.Event()
        self._writer_lock = threading.RLock()
        self._pending_ids: set[str] = set()
        self._recent_rejections: deque[Dict[str, Any]] = deque(maxlen=16)
        self._process_health_known = False
        self._process_available = False
        self._supervisor_thread: threading.Thread | None = None
        self._projection_process: subprocess.Popen[Any] | None = None
        self._process_generation = 0
        self._restart_times: list[float] = []
        self._restart_backoff_seconds = 0.25
        self._restart_max = max(1, min(int(os.environ.get("POCKETLAB_WORKFLOW_RESTART_MAX", "5")), 50))
        self._restart_window_seconds = max(10, min(int(os.environ.get("POCKETLAB_WORKFLOW_RESTART_WINDOW_SECONDS", "300")), 3600))
        self._writer_stats: Dict[str, Any] = {
            "queued": 0,
            "written": 0,
            "accepted_events": 0,
            "coalesced_events": 0,
            "rejected_events": 0,
            "dropped_events": 0,
            "failed": 0,
            "process_restart_count": 0,
            "dispatcher_restart_count": 0,
            "recycle_count": 0,
            "last_restart_reason": "",
            "recent_max_write_ms": 0.0,
            "last_error_type": "",
            "last_write_at": "",
        }

    def _ensure_paths(self) -> None:
        if self._root is not None:
            return
        with self._path_lock:
            if self._root is not None:
                return
            state_override = str(os.environ.get("POCKETLAB_STATE_DIR") or "").strip()
            state_dir = Path(state_override).expanduser() if state_override else deps.settings().state_dir
            root = state_dir / "workflows"
            events = root / "events"
            projections = root / "projections"
            commands = root / "commands"
            for path in (root, events, projections, commands):
                path.mkdir(parents=True, exist_ok=True)
            self._root = root
            self._event_log = events / "workflow_events.jsonl"
            self._projection_file = projections / "workflow_projections.json"
            self._command_file = commands / "command_journal.json"

    @property
    def root(self) -> Path:
        self._ensure_paths()
        assert self._root is not None
        return self._root

    @property
    def event_log(self) -> Path:
        self._ensure_paths()
        assert self._event_log is not None
        return self._event_log

    @property
    def projection_file(self) -> Path:
        self._ensure_paths()
        assert self._projection_file is not None
        return self._projection_file

    @property
    def command_file(self) -> Path:
        self._ensure_paths()
        assert self._command_file is not None
        return self._command_file

    @property
    def mailbox_root(self) -> Path:
        root = self.root / "mailbox"
        for child in (root, root / "inbox", root / "processing", root / "failed"):
            child.mkdir(parents=True, exist_ok=True)
        return root

    @property
    def process_status_file(self) -> Path:
        path = self.root / "runtime" / "process_status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def process_generation_file(self) -> Path:
        path = self.root / "runtime" / "process_generation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _next_process_generation(self) -> int:
        payload = _read_json(self.process_generation_file, {})
        status = _read_json(self.process_status_file, {})
        previous = max(
            int(payload.get("generation") or 0) if isinstance(payload, dict) else 0,
            int(status.get("process_generation") or 0) if isinstance(status, dict) else 0,
            self._process_generation,
        )
        try:
            with fast_read_connection(timeout_ms=250) as conn:
                row = conn.execute(
                    "SELECT COALESCE(MAX(process_generation), 0) AS generation FROM workflow_current_state"
                ).fetchone()
            previous = max(previous, int(row["generation"] if row else 0))
        except (FileNotFoundError, sqlite3.Error, TypeError, ValueError):
            pass
        generation = previous + 1
        _write_json(self.process_generation_file, {
            "generation": generation,
            "updated_at": deps.now_utc_iso(),
            "sanitized": True,
        })
        return generation

    def start_writer(self) -> None:
        with self._writer_lock:
            if self._writer_thread is None or not self._writer_thread.is_alive():
                self._writer_stop.clear()
                if self._dispatcher_generation > 0:
                    self._writer_stats["dispatcher_restart_count"] += 1
                self._dispatcher_generation += 1
                self._writer_thread = threading.Thread(
                    target=self._dispatcher_loop,
                    name="pocketlab-wf-ipc",
                    daemon=True,
                )
                self._writer_thread.start()
            if self._owns_process and (
                self._supervisor_thread is None or not self._supervisor_thread.is_alive()
            ):
                self._supervisor_thread = threading.Thread(
                    target=self._supervisor_loop,
                    name="pocketlab-wf-supervisor",
                    daemon=True,
                )
                self._supervisor_thread.start()

    def stop_writer(self, *, drain_timeout_seconds: float = 3.0) -> None:
        self._writer_stop.set()
        try:
            self._writer_queue.put_nowait(None)
        except queue.Full:
            pass
        thread = self._writer_thread
        if thread is not None:
            thread.join(timeout=max(0.1, min(float(drain_timeout_seconds), 10.0)))
        self._writer_thread = None
        supervisor = self._supervisor_thread
        if supervisor is not None:
            supervisor.join(timeout=max(0.1, min(float(drain_timeout_seconds), 10.0)))
        self._supervisor_thread = None
        self._terminate_projection_process()

    def _sanitize_child_environment(self, generation: int) -> Dict[str, str]:
        allowed_exact = {
            "HOME", "PATH", "PYTHONPATH", "PREFIX", "LANG", "LC_ALL", "TMPDIR",
            "POCKETLAB_STATE_DIR", "POCKETLAB_LITE_DB_PATH", "POCKETLAB_LITE_DB_BUSY_TIMEOUT_MS",
            "POCKETLAB_LITE_DB_SYNCHRONOUS", "POCKETLAB_LITE_DB_WAL_AUTOCHECKPOINT",
            "POCKETLAB_WORKFLOW_BATCH_CPU_MS", "POCKETLAB_WORKFLOW_BATCH_MAX_EVENTS",
            "POCKETLAB_WORKFLOW_BATCH_WALL_MS", "POCKETLAB_WORKFLOW_COMPAT_SNAPSHOT_BATCHES",
            "POCKETLAB_WORKFLOW_EVENT_INDEX_LIMIT", "POCKETLAB_WORKFLOW_FSYNC",
            "POCKETLAB_WORKFLOW_HISTORY_LIMIT", "POCKETLAB_WORKFLOW_JOURNAL_MAX_BYTES",
            "POCKETLAB_WORKFLOW_MEMORY_MIN_AVAILABLE_PERCENT", "POCKETLAB_WORKFLOW_MEMORY_PROBE_SECONDS",
            "POCKETLAB_WORKFLOW_POLL_SECONDS", "POCKETLAB_WORKFLOW_PROJECTION_ITEM_MAX",
            "POCKETLAB_WORKFLOW_RECONCILE_MAX_ROWS", "POCKETLAB_WORKFLOW_RECONCILE_WORKFLOW_MAX",
            "POCKETLAB_WORKFLOW_SQLITE_DEADLINE_SECONDS", "POCKETLAB_WORKFLOW_RECYCLE_BATCH_COUNT",
            "POCKETLAB_WORKFLOW_RECYCLE_EVENT_COUNT", "POCKETLAB_WORKFLOW_RECYCLE_RSS_BYTES",
            "POCKETLAB_WORKFLOW_SERIALIZED_BYTES_MAX", "POCKETLAB_WORKFLOW_STAGGER_MAX_MS",
            "POCKETLAB_WORKFLOW_UPDATES_PER_WORKFLOW_BATCH",
        }
        env = {key: value for key, value in os.environ.items() if key in allowed_exact}
        env["POCKETLAB_PROCESS_ROLE"] = "workflow_projection"
        env["POCKETLAB_WORKFLOW_PROCESS_GENERATION"] = str(generation)
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"
        return env

    def _spawn_projection_process(self, generation: int) -> subprocess.Popen[Any]:
        runtime_dir = Path(__file__).resolve().parents[2]
        kwargs: Dict[str, Any] = {
            "cwd": str(runtime_dir),
            "env": self._sanitize_child_environment(generation),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            if creationflags:
                kwargs["creationflags"] = creationflags
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(
            [sys.executable, "-m", "api_fastapi.services.workflow_projection_process"],
            **kwargs,
        )

    def _terminate_projection_process(self) -> None:
        process = self._projection_process
        self._projection_process = None
        if process is None or process.poll() is not None:
            return
        try:
            if os.name != "nt" and hasattr(os, "killpg"):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=2.0)
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            try:
                if os.name != "nt" and hasattr(os, "killpg"):
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                process.wait(timeout=2.0)
            except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
                pass

    def _supervisor_loop(self) -> None:
        while not self._writer_stop.is_set():
            process = self._projection_process
            if process is not None and process.poll() is None:
                time.sleep(0.2)
                continue
            exit_code = process.poll() if process is not None else None
            now = time.monotonic()
            self._restart_times = [item for item in self._restart_times if now - item <= self._restart_window_seconds]
            if len(self._restart_times) >= self._restart_max:
                with self._writer_lock:
                    self._process_health_known = True
                    self._process_available = False
                    self._writer_stats["last_error_type"] = "WorkflowProjectionCircuitOpen"
                    self._writer_stats["last_restart_reason"] = "restart_limit"
                time.sleep(min(5.0, self._restart_backoff_seconds))
                continue
            try:
                self._process_generation = self._next_process_generation()
                self._projection_process = self._spawn_projection_process(self._process_generation)
            except Exception as exc:
                with self._writer_lock:
                    self._process_health_known = True
                    self._process_available = False
                    self._writer_stats["last_error_type"] = _safe_error_type(exc)
                time.sleep(self._restart_backoff_seconds)
                self._restart_backoff_seconds = min(30.0, self._restart_backoff_seconds * 2.0)
                continue
            self._restart_times.append(now)
            with self._writer_lock:
                self._process_health_known = True
                self._process_available = True
                if self._process_generation > 1:
                    self._writer_stats["process_restart_count"] += 1
                if exit_code == 75:
                    self._writer_stats["recycle_count"] += 1
                    self._writer_stats["last_restart_reason"] = "bounded_recycle"
                elif exit_code is not None:
                    self._writer_stats["last_restart_reason"] = "process_exit"
            self._restart_backoff_seconds = 0.25
            time.sleep(0.1)

    def _record_rejection(self, reason: str, event_id: str = "") -> None:
        with self._writer_lock:
            self._recent_rejections.append({
                "reason": _bounded_text(reason, 80),
                "event_id": _bounded_text(event_id, 160),
                "observed_at": deps.now_utc_iso(),
                "sanitized": True,
            })

    def admit_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if self._writer_stop.is_set():
            self._record_rejection("shutting_down")
            return {"status": "shutting_down", "accepted": False, "retry_after_ms": 1000}
        compact = _compact_workflow_event(event)
        if compact is None:
            with self._writer_lock:
                self._writer_stats["rejected_events"] += 1
            self._record_rejection("invalid")
            return {"status": "invalid", "accepted": False, "retry_after_ms": 0}
        event_id = str(compact["id"])
        with self._writer_lock:
            if event_id in self._pending_ids:
                self._writer_stats["coalesced_events"] += 1
                return {"status": "coalesced", "accepted": True, "event_id": event_id}
            self._pending_ids.add(event_id)
        self.start_writer()
        try:
            self._writer_queue.put_nowait({"kind": "event", "event": compact, "event_id": event_id})
        except queue.Full:
            with self._writer_lock:
                self._pending_ids.discard(event_id)
                self._writer_stats["rejected_events"] += 1
            self._record_rejection("queue_full", event_id)
            return {"status": "queue_full", "accepted": False, "retry_after_ms": 2000}
        with self._writer_lock:
            self._writer_stats["queued"] += 1
            self._writer_stats["accepted_events"] += 1
            process_known = self._process_health_known
            process_available = self._process_available
        if process_known and not process_available:
            return {
                "status": "process_unavailable",
                "accepted": True,
                "event_id": event_id,
                "refresh_pending": True,
                "retry_after_ms": 5000,
            }
        return {"status": "accepted", "accepted": True, "event_id": event_id}

    def enqueue_event(self, event: Dict[str, Any]) -> bool:
        return bool(self.admit_event(event).get("accepted"))

    def _enqueue_control(self, action: str) -> Dict[str, Any]:
        if self._writer_stop.is_set():
            return {"status": "shutting_down", "accepted": False}
        self.start_writer()
        control_id = uuid.uuid4().hex
        try:
            self._writer_queue.put_nowait({"kind": "control", "action": action, "event_id": control_id})
        except queue.Full:
            with self._writer_lock:
                self._writer_stats["rejected_events"] += 1
            return {"status": "queue_full", "accepted": False, "retry_after_ms": 2000}
        return {"status": "accepted", "accepted": True, "request_id": control_id}

    def _dispatcher_loop(self) -> None:
        inbox = self.mailbox_root / "inbox"
        while not self._writer_stop.is_set() or not self._writer_queue.empty():
            try:
                item = self._writer_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if item is None:
                self._writer_queue.task_done()
                continue
            started = time.monotonic()
            event_id = str(item.get("event_id") or uuid.uuid4().hex)
            try:
                while len(list(inbox.glob("*.json"))) >= self._mailbox_capacity:
                    with self._writer_lock:
                        self._writer_stats["last_error_type"] = "MailboxBackpressure"
                    if self._writer_stop.wait(0.1):
                        failed = self.mailbox_root / "failed" / f"undelivered-{event_id}.json"
                        _write_json(failed, {
                            "status": "retained_unprocessed",
                            "reason": "shutdown_during_mailbox_backpressure",
                            "event_id": event_id,
                            "payload": item.get("event") if str(item.get("kind") or "event") == "event" else {"kind": "control", "action": item.get("action")},
                            "observed_at": deps.now_utc_iso(),
                            "sanitized": True,
                        })
                        with self._writer_lock:
                            self._writer_stats["failed"] += 1
                            self._writer_stats["dropped_events"] += 1
                        self._record_rejection("shutdown_during_mailbox_backpressure", event_id)
                        raise RuntimeError("workflow_mailbox_shutdown")
                kind = str(item.get("kind") or "event")
                if kind == "control":
                    name = f"control-{str(item.get('action') or 'unknown')}-{event_id}.json"
                    payload = {"kind": "control", "action": item.get("action"), "request_id": event_id}
                else:
                    payload = item.get("event")
                    sort_epoch_ms = _epoch_ms(payload.get("time")) if isinstance(payload, dict) else _epoch_ms()
                    name = f"event-{sort_epoch_ms:016d}-{event_id}.json"
                target = inbox / name
                if target.exists():
                    with self._writer_lock:
                        self._writer_stats["coalesced_events"] += 1
                else:
                    tmp = target.with_suffix(f".json.{os.getpid()}.{uuid.uuid4().hex}.tmp")
                    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    with tmp.open("xb") as handle:
                        handle.write(encoded)
                        handle.flush()
                    os.replace(tmp, target)
                    with self._writer_lock:
                        self._writer_stats["written"] += 1
                        self._writer_stats["last_write_at"] = deps.now_utc_iso()
                        self._writer_stats["recent_max_write_ms"] = max(
                            float(self._writer_stats["recent_max_write_ms"]),
                            max(0.0, (time.monotonic() - started) * 1000.0),
                        )
            except Exception as exc:
                with self._writer_lock:
                    self._writer_stats["failed"] += 1
                    self._writer_stats["last_error_type"] = _safe_error_type(exc)
            finally:
                with self._writer_lock:
                    self._pending_ids.discard(event_id)
                self._writer_queue.task_done()

    def _child_status(self) -> Dict[str, Any]:
        payload = _read_json(self.process_status_file, {})
        if not isinstance(payload, dict):
            return {}
        started = str(payload.get("started_at") or "")
        stale = True
        try:
            from datetime import datetime, timezone

            reference = str(payload.get("heartbeat_at") or payload.get("last_batch_completed_at") or payload.get("last_success_at") or started)
            parsed = datetime.fromisoformat(reference.replace("Z", "+00:00"))
            stale = (datetime.now(timezone.utc) - parsed).total_seconds() > 30
        except Exception:
            stale = not bool(payload.get("process_alive"))
        normalized = {**payload, "health_stale": stale}
        for key in (
            "process_pid", "process_generation", "oldest_queue_age_ms", "processed_events",
            "batch_count", "last_batch_size", "serialized_bytes", "allocation_bytes",
            "canonical_noop_count", "canonical_change_count", "hash_input_bytes",
            "memory_pressure_deferred_count", "cpu_budget_deferred_count",
            "last_known_good_revision", "next_batch_due_ms", "stagger_ms", "rss_bytes",
        ):
            normalized[key] = int(normalized.get(key) or 0)
        for key in (
            "last_batch_wall_ms", "last_batch_cpu_ms", "serialization_ms", "hash_cpu_ms",
        ):
            normalized[key] = float(normalized.get(key) or 0.0)
        return normalized

    def writer_status(self) -> Dict[str, Any]:
        with self._writer_lock:
            stats = dict(self._writer_stats)
        thread = self._writer_thread
        process = self._projection_process
        child = self._child_status()
        process_alive = bool(process is not None and process.poll() is None) if self._owns_process else bool(child.get("process_alive") and not child.get("health_stale"))
        with self._writer_lock:
            self._process_health_known = bool(self._owns_process or child)
            self._process_available = process_alive
            recent_rejections = list(self._recent_rejections)
        return {
            "running": bool(thread is not None and thread.is_alive()),
            "dispatcher_alive": bool(thread is not None and thread.is_alive()),
            "dispatcher_restart_count": int(stats.get("dispatcher_restart_count") or 0),
            "dispatch_count": int(stats.get("written") or 0),
            "last_dispatch_at": stats.get("last_write_at") or "",
            "last_dispatch_error_type": stats.get("last_error_type") or "",
            "queue_depth": self._writer_queue.qsize(),
            "queue_capacity": self._writer_queue.maxsize,
            "mailbox_capacity": self._mailbox_capacity,
            "batch_size": self._writer_batch_size,
            "process_alive": process_alive,
            "process_pid": int(process.pid) if process_alive and process is not None else child.get("process_pid"),
            "process_generation": self._process_generation if self._owns_process else child.get("process_generation", 0),
            "started_at": child.get("started_at") or "",
            "restart_count": int(stats.get("process_restart_count") or 0),
            "execution_owner": "pocket-worker/workflow-subprocess",
            "degraded": not process_alive,
            "degraded_reason": "" if process_alive else "workflow_projection_unavailable",
            "data_source": "prepared_sqlite",
            "refresh_pending": self._writer_queue.qsize() > 0 or int(child.get("queue_depth") or 0) > 0,
            "retry_after_ms": 5000 if not process_alive else 0,
            "recent_rejection_evidence": recent_rejections,
            **stats,
            "last_error_type": child.get("last_error_type") or stats.get("last_error_type") or "",
            "child_last_error_type": child.get("last_error_type") or "",
            "coalesced": int(stats.get("coalesced_events") or 0),
            "dropped": int(stats.get("dropped_events") or 0),
            **{key: child.get(key) for key in (
                "oldest_queue_age_ms", "processed_events", "batch_count", "last_batch_size",
                "last_batch_started_at", "last_batch_completed_at", "last_batch_wall_ms",
                "last_batch_cpu_ms", "last_batch_serialized_bytes", "last_batch_allocation_bytes",
                "serialization_ms", "serialized_bytes", "allocation_bytes",
                "canonical_noop_count", "canonical_change_count", "hash_cpu_ms", "hash_input_bytes",
                "memory_pressure_deferred_count", "cpu_budget_deferred_count", "pressure_deferred_count", "last_error_at",
                "last_success_at", "last_known_good_revision", "next_batch_due_ms", "stagger_ms",
                "rss_bytes",
            )},
        }

    def ingest_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        admission = self.admit_event(event)
        workflow_id = workflow_id_for_event(event) if isinstance(event, dict) else ""
        return {"workflow_id": workflow_id, "admission": admission, "projection": self.get_projection(workflow_id)}

    def ingest_events(self, events: List[Dict[str, Any]]) -> bool:
        accepted = False
        for event in events:
            accepted = self.enqueue_event(event) or accepted
        return accepted

    def _maybe_record_command(self, event: Dict[str, Any]) -> None:
        subject = str(event.get("subject") or "")
        event_type = str(event.get("type") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        command_subject = str(
            data.get("command_subject")
            or data.get("subject")
            or (subject if subject.startswith("pocketlab.commands.") else "")
        )
        lifecycle_status = {
            "command.queued": "accepted",
            "command.published": "published",
            "command.received": "delivered",
            "command.worker_claimed": "worker_claimed",
            "command.running": "running",
            "command.succeeded": "succeeded",
            "command.dead_lettered": "failed",
            "worker.maintenance_deferred": "recovery_action",
        }.get(event_type)
        if event_type == "command.failed":
            lifecycle_status = "failed" if bool(data.get("terminal")) else "recovery_action"
        if event_type == "worker.ignored" and any(
            marker in str(data.get("reason") or "").lower()
            for marker in ("terminal", "redeliver")
        ):
            lifecycle_status = "ignored_redelivery"
        if not command_subject and lifecycle_status is None:
            return
        command_id = str(
            data.get("command_id")
            or data.get("job_id")
            or data.get("run_id")
            or event.get("trace_id")
            or event.get("id")
        )
        if not command_id:
            return
        journal = _read_json(self.command_file, {"commands": {}})
        commands = journal.setdefault("commands", {})
        existing = dict(commands.get(command_id) or {})
        existing.update(
            {
                "command_id": command_id,
                "workflow_id": event.get("workflow_id"),
                "subject": command_subject or subject,
                "event_type": event_type,
                "command": data,
                "last_event_id": event.get("id"),
                "updated_at": event.get("time") or deps.now_utc_iso(),
            }
        )
        existing.setdefault("created_at", event.get("time") or deps.now_utc_iso())
        commands[command_id] = existing
        _write_json(self.command_file, journal)

        if lifecycle_status is None:
            return
        entity_type = "control"
        entity_id = "control-plane"
        if data.get("app_id"):
            entity_type, entity_id = "app", str(data.get("app_id"))
        elif data.get("node_id") or data.get("device_id"):
            entity_type = "device"
            entity_id = str(data.get("node_id") or data.get("device_id"))
        elif data.get("run_id") or ".security." in command_subject:
            entity_type = "security"
            entity_id = str(data.get("run_id") or "security")
        summaries = {
            "accepted": "Command accepted.",
            "published": "Command published to the local event bus.",
            "delivered": "Command delivered to a worker.",
            "worker_claimed": "Worker claimed the command.",
            "running": "Command is running.",
            "succeeded": "Command completed.",
            "failed": "Command reached a terminal failure.",
            "ignored_redelivery": "Terminal command redelivery was ignored safely.",
            "recovery_action": "Command recovery or retry is in progress.",
        }
        try:
            from .lite_control_plane_store import CONTROL_PLANE

            CONTROL_PLANE.record_command(
                command_id=command_id,
                subject=command_subject or subject or "pocketlab.commands.unknown",
                status=lifecycle_status,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summaries[lifecycle_status],
                recovery_action=(
                    event_type if lifecycle_status == "recovery_action" else ""
                ),
            )
        except Exception:
            # Workflow journaling remains available if the compact SQLite projection
            # is temporarily unavailable; later domain reads can reconcile safely.
            return

    def _apply_event(
        self, current: Dict[str, Any] | None, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        return _apply_projection_event(current, event)

    def _projection_data(self) -> Dict[str, Any]:
        with self._projection_lock:
            loaded = _read_json(self.projection_file, {"workflows": {}})
            return loaded if isinstance(loaded, dict) else {"workflows": {}}

    def _prepared_projection_row(self, workflow_id: str) -> Dict[str, Any] | None:
        try:
            with fast_read_connection(timeout_ms=250) as conn:
                row = conn.execute(
                    "SELECT projection_json, revision, process_generation FROM workflow_current_state WHERE workflow_id = ?",
                    (str(workflow_id),),
                ).fetchone()
            if row is None:
                return None
            payload = json.loads(str(row["projection_json"]))
            if not isinstance(payload, dict):
                return None
            payload["revision"] = int(row["revision"])
            payload["process_generation"] = int(row["process_generation"])
            payload["data_source"] = "prepared_sqlite"
            return payload
        except (FileNotFoundError, sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
            return None

    def get_projection(self, workflow_id: str) -> Dict[str, Any]:
        prepared = self._prepared_projection_row(str(workflow_id))
        if prepared is not None:
            return prepared
        data = self._projection_data()
        fallback = dict((data.get("workflows") or {}).get(str(workflow_id)) or {"workflow_id": str(workflow_id)})
        fallback["data_source"] = "last_known_good_file"
        fallback["degraded"] = True
        fallback["degraded_reason"] = "prepared_workflow_unavailable"
        return fallback

    def _invalidate_status_cache(self) -> None:
        with self._status_cache_lock:
            self._status_cache = None
            self._status_cache_at = 0.0

    def save_projection(self, projection: Dict[str, Any]) -> bool:
        """Administrative/test-only bounded component write; normal events use the subprocess."""
        workflow_id = str(projection.get("workflow_id") or "")
        if not workflow_id:
            return False
        apply_migrations()
        material = _canonical_projection_material(projection)
        encoded_material = json.dumps(material, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        canonical_hash = hashlib.sha256(encoded_material).hexdigest()
        payload = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        now = str(projection.get("updated_at") or deps.now_utc_iso())
        changed = False
        with connection() as conn:
            with begin_immediate(conn) as tx:
                current = tx.execute(
                    "SELECT canonical_hash, revision FROM workflow_current_state WHERE workflow_id=?",
                    (workflow_id,),
                ).fetchone()
                if current is not None and str(current["canonical_hash"]) == canonical_hash:
                    with self._writer_lock:
                        self._writer_stats["coalesced_events"] += 1
                    return False
                revision = int(current["revision"] if current else 0) + 1
                tx.execute(
                    """
                    INSERT INTO workflow_current_state(
                        workflow_id, projection_json, canonical_hash, status, terminal,
                        revision, semantic_event_count, updated_at, updated_at_epoch_ms,
                        process_generation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(workflow_id) DO UPDATE SET
                        projection_json=excluded.projection_json,
                        canonical_hash=excluded.canonical_hash,
                        status=excluded.status,
                        terminal=excluded.terminal,
                        revision=excluded.revision,
                        semantic_event_count=excluded.semantic_event_count,
                        updated_at=excluded.updated_at,
                        updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                        process_generation=excluded.process_generation
                    """,
                    (
                        workflow_id,
                        payload,
                        canonical_hash,
                        str(projection.get("status") or "unknown"),
                        1 if projection.get("terminal") else 0,
                        revision,
                        int(projection.get("event_count") or 0),
                        now,
                        _epoch_ms(now),
                        0,
                    ),
                )
                changed = True
        if changed:
            self._invalidate_status_cache()
        return changed

    def iter_events(self, workflow_id: str | None = None, limit: int = 1000) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), self.history_limit))
        try:
            with fast_read_connection(timeout_ms=250) as conn:
                if workflow_id:
                    rows = conn.execute(
                        "SELECT event_json FROM workflow_event_index WHERE workflow_id=? ORDER BY observed_at_epoch_ms DESC, event_id DESC LIMIT ?",
                        (str(workflow_id), bounded),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT event_json FROM workflow_event_index ORDER BY observed_at_epoch_ms DESC, event_id DESC LIMIT ?",
                        (bounded,),
                    ).fetchall()
            events: List[Dict[str, Any]] = []
            for row in reversed(rows):
                try:
                    item = json.loads(str(row["event_json"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if isinstance(item, dict):
                    events.append(item)
            return events
        except (FileNotFoundError, sqlite3.Error):
            return []

    def reconstruct(self, workflow_id: str) -> Dict[str, Any]:
        projection = self.get_projection(workflow_id)
        return {
            "workflow_id": str(workflow_id),
            "projection": projection,
            "events": self.iter_events(workflow_id=workflow_id, limit=min(250, self.history_limit)),
            "source": projection.get("data_source") or "prepared_sqlite",
            "reconstruction": "prepared",
        }

    def rebuild_all(self) -> Dict[str, Any]:
        admission = self._enqueue_control("rebuild")
        return {
            "status": "rebuild_scheduled" if admission.get("accepted") else admission.get("status"),
            "accepted": bool(admission.get("accepted")),
            "request_id": admission.get("request_id"),
            "projection_writer": self.writer_status(),
        }

    def list_workflows(
        self, *, status: str = "", include_terminal: bool = True, limit: int = 100
    ) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 1000))
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(str(status))
        if not include_terminal:
            clauses.append("terminal = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            with fast_read_connection(timeout_ms=250) as conn:
                rows = conn.execute(
                    f"SELECT projection_json, revision, process_generation FROM workflow_current_state {where} ORDER BY updated_at_epoch_ms DESC LIMIT ?",
                    (*params, bounded),
                ).fetchall()
            items: List[Dict[str, Any]] = []
            for row in rows:
                try:
                    item = json.loads(str(row["projection_json"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if isinstance(item, dict):
                    item["revision"] = int(row["revision"])
                    item["process_generation"] = int(row["process_generation"])
                    item["data_source"] = "prepared_sqlite"
                    items.append(item)
            return items
        except (FileNotFoundError, sqlite3.Error):
            data = self._projection_data()
            items = list((data.get("workflows") or {}).values())
            if status:
                items = [item for item in items if str(item.get("status")) == status]
            if not include_terminal:
                items = [item for item in items if not item.get("terminal")]
            items.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return items[:bounded]

    def recovery_plan(
        self, *, stale_seconds: int | None = None, limit: int = 100
    ) -> Dict[str, Any]:
        stale_seconds = (
            stale_seconds
            if stale_seconds is not None
            else int(os.environ.get("POCKETLAB_WORKFLOW_STALE_SECONDS", "300"))
        )
        now_ts = time.time()
        candidates = []
        for item in self.list_workflows(include_terminal=False, limit=1000):
            updated = str(item.get("updated_at") or item.get("created_at") or "")
            stale = True
            try:
                from datetime import datetime

                parsed = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                stale = (now_ts - parsed.timestamp()) >= stale_seconds
            except Exception:
                stale = True
            if item.get("status") in {"queued", "retrying", "running"} and stale:
                candidates.append(
                    {**item, "reason": f"non-terminal for >= {stale_seconds}s"}
                )
        return {
            "status": "planned",
            "stale_seconds": stale_seconds,
            "count": len(candidates[:limit]),
            "candidates": candidates[:limit],
        }

    def command_for_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        try:
            with fast_read_connection(timeout_ms=250) as conn:
                row = conn.execute(
                    """
                    SELECT command_id, workflow_id, subject, event_type, command_json,
                           created_at, updated_at
                      FROM workflow_command_state
                     WHERE workflow_id = ? OR command_id = ?
                     ORDER BY updated_at_epoch_ms DESC
                     LIMIT 1
                    """,
                    (str(workflow_id), str(workflow_id)),
                ).fetchone()
            if row is not None:
                try:
                    command = json.loads(str(row["command_json"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    command = {}
                return {
                    "command_id": str(row["command_id"]),
                    "workflow_id": str(row["workflow_id"]),
                    "subject": str(row["subject"]),
                    "event_type": str(row["event_type"]),
                    "command": command if isinstance(command, dict) else {},
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                    "data_source": "prepared_sqlite",
                }
        except (FileNotFoundError, sqlite3.Error):
            pass
        for event in reversed(self.iter_events(workflow_id=workflow_id, limit=min(self.history_limit, 250))):
            subject = str(event.get("subject") or "")
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if subject.startswith("pocketlab.commands."):
                return {
                    "workflow_id": workflow_id,
                    "command_id": data.get("command_id") or data.get("job_id") or workflow_id,
                    "subject": subject,
                    "command": data,
                    "data_source": "prepared_event_index",
                }
        return None

    async def replay_workflow(
        self, workflow_id: str, *, as_new: bool = True
    ) -> Dict[str, Any]:
        from .nats_bus import BUS

        command_record = self.command_for_workflow(workflow_id)
        if not command_record:
            raise KeyError(f"No replayable command found for workflow {workflow_id}")
        subject = str(
            command_record.get("subject") or "pocketlab.commands.operation.execute"
        )
        command = dict(command_record.get("command") or {})
        old_id = str(command.get("command_id") or command.get("job_id") or workflow_id)
        if as_new:
            new_id = uuid.uuid4().hex
            command["command_id"] = new_id
            command["trace_id"] = new_id
            if subject == "pocketlab.commands.operation.execute":
                # Let the worker create or use a fresh job unless the caller opts
                # into the original workflow.  This prevents replay from mutating
                # an old terminal operation record.
                command.pop("job_id", None)
            command["replay_of"] = workflow_id
            command["replayed_from"] = old_id
        else:
            command["trace_id"] = command.get("trace_id") or workflow_id
            command["replay_of"] = workflow_id
        event = await BUS.publish_json(
            subject,
            "workflow.replay_requested",
            command,
            trace_id=str(command.get("trace_id") or workflow_id),
        )
        await BUS.publish_json(
            "pocketlab.events.workflow.replay_requested",
            "workflow.replay_requested",
            {
                "workflow_id": workflow_id,
                "subject": subject,
                "as_new": as_new,
                "replayed_as": command.get("command_id") or command.get("job_id"),
                "event_id": event.get("id"),
            },
            trace_id=str(command.get("trace_id") or workflow_id),
        )
        return {
            "status": "replay_requested",
            "workflow_id": workflow_id,
            "subject": subject,
            "as_new": as_new,
            "replayed_as": command.get("command_id") or command.get("job_id"),
            "event": event,
        }

    async def recover(
        self,
        *,
        stale_seconds: int | None = None,
        limit: int = 25,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        plan = self.recovery_plan(stale_seconds=stale_seconds, limit=limit)
        recovered = []
        if dry_run:
            return {**plan, "dry_run": True, "recovered": recovered}
        for item in plan["candidates"]:
            try:
                result = await self.replay_workflow(
                    str(item.get("workflow_id")), as_new=False
                )
                recovered.append(result)
            except Exception as exc:
                recovered.append(
                    {
                        "workflow_id": item.get("workflow_id"),
                        "status": "failed",
                        "error": str(exc),
                    }
                )
        return {
            **plan,
            "dry_run": False,
            "recovered": recovered,
            "recovered_count": len(recovered),
        }

    def _prepared_counts(self) -> tuple[int, Dict[str, int]]:
        try:
            with fast_read_connection(timeout_ms=250) as conn:
                rows = conn.execute(
                    "SELECT status, COUNT(*) AS count FROM workflow_current_state GROUP BY status"
                ).fetchall()
            counts = {str(row["status"] or "unknown"): int(row["count"] or 0) for row in rows}
            return sum(counts.values()), counts
        except (FileNotFoundError, sqlite3.Error):
            data = self._projection_data()
            counts: Dict[str, int] = {}
            for item in (data.get("workflows") or {}).values():
                if not isinstance(item, dict):
                    continue
                state = str(item.get("status") or "unknown")
                counts[state] = counts.get(state, 0) + 1
            return sum(counts.values()), counts

    def status(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._status_cache_lock:
            cached = self._status_cache
            if cached is not None and now - self._status_cache_at < self._status_cache_ttl:
                return {**cached, "counts": dict(cached.get("counts") or {}), "cache": "hit"}

        workflow_count, counts = self._prepared_counts()
        writer = self.writer_status()
        result = {
            "status": "degraded" if writer.get("degraded") else "ok",
            "engine": "event-sourced-workflow-engine",
            "execution_owner": "pocket-worker/workflow-subprocess",
            "workflow_count": workflow_count,
            "counts": counts,
            "history_limit": self.history_limit,
            "cache_ttl_seconds": self._status_cache_ttl,
            "prepared_read_source": "sqlite",
            "last_known_good": True,
            "projection_writer": writer,
            "sanitized": True,
        }
        with self._status_cache_lock:
            self._status_cache = {**result, "counts": dict(counts)}
            self._status_cache_at = now
        return {**result, "counts": dict(counts), "cache": "miss"}


WORKFLOW_ENGINE = EventSourcedWorkflowEngine()
