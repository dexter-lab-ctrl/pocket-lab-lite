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

import json
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import deps

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
        self.history_limit = int(
            os.environ.get("POCKETLAB_WORKFLOW_HISTORY_LIMIT", "5000")
        )
        self._status_cache: Dict[str, Any] | None = None
        self._status_cache_at = 0.0
        self._status_cache_ttl = max(1.0, float(
            os.environ.get("POCKETLAB_WORKFLOW_STATUS_CACHE_SECONDS", "15")
        ))
        self._status_cache_lock = threading.RLock()
        self._path_lock = threading.RLock()
        self._root: Path | None = None
        self._event_log: Path | None = None
        self._projection_file: Path | None = None
        self._command_file: Path | None = None
        self._projection_lock = threading.RLock()
        self._projection_cache: Dict[str, Any] | None = None
        self._writer_queue: queue.Queue[Dict[str, Any] | None] = queue.Queue(
            maxsize=max(8, min(int(os.environ.get("POCKETLAB_WORKFLOW_WRITER_QUEUE_SIZE", "256")), 4096))
        )
        self._writer_batch_size = max(
            1, min(int(os.environ.get("POCKETLAB_WORKFLOW_WRITER_BATCH_SIZE", "32")), 256)
        )
        self._writer_thread: threading.Thread | None = None
        self._writer_stop = threading.Event()
        self._writer_lock = threading.RLock()
        self._writer_stats: Dict[str, Any] = {
            "queued": 0, "written": 0, "coalesced": 0, "dropped": 0, "failed": 0,
            "recent_max_write_ms": 0.0, "last_error_type": "", "last_write_at": "",
        }

    def _ensure_paths(self) -> None:
        if self._root is not None:
            return
        with self._path_lock:
            if self._root is not None:
                return
            root = deps.settings().state_dir / "workflows"
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

    def start_writer(self) -> None:
        with self._writer_lock:
            if self._writer_thread is not None and self._writer_thread.is_alive():
                return
            self._writer_stop.clear()
            self._writer_thread = threading.Thread(
                target=self._writer_loop, name="pocketlab-workflow-projection-writer", daemon=True
            )
            self._writer_thread.start()

    def stop_writer(self, *, drain_timeout_seconds: float = 3.0) -> None:
        thread = self._writer_thread
        if thread is None:
            return
        self._writer_stop.set()
        try:
            self._writer_queue.put_nowait(None)
        except queue.Full:
            pass
        thread.join(timeout=max(0.1, min(float(drain_timeout_seconds), 10.0)))
        self._writer_thread = None

    def enqueue_event(self, event: Dict[str, Any]) -> bool:
        if not isinstance(event, dict):
            return False
        self.start_writer()
        try:
            self._writer_queue.put_nowait(dict(event))
        except queue.Full:
            with self._writer_lock:
                self._writer_stats["dropped"] += 1
            return False
        with self._writer_lock:
            self._writer_stats["queued"] += 1
        return True

    def _writer_loop(self) -> None:
        while not self._writer_stop.is_set() or not self._writer_queue.empty():
            try:
                first = self._writer_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if first is None:
                self._writer_queue.task_done()
                continue
            batch = [first]
            while len(batch) < self._writer_batch_size:
                try:
                    item = self._writer_queue.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    self._writer_queue.task_done()
                    continue
                batch.append(item)
            started = time.monotonic()
            try:
                changed = self.ingest_events(batch)
            except Exception as exc:
                with self._writer_lock:
                    self._writer_stats["failed"] += len(batch)
                    self._writer_stats["last_error_type"] = type(exc).__name__
            else:
                duration_ms = max(0.0, (time.monotonic() - started) * 1000.0)
                with self._writer_lock:
                    self._writer_stats["written"] += len(batch)
                    if len(batch) > 1:
                        self._writer_stats["coalesced"] += len(batch) - 1
                    if not changed:
                        self._writer_stats["coalesced"] += 1
                    self._writer_stats["recent_max_write_ms"] = max(
                        float(self._writer_stats["recent_max_write_ms"]), duration_ms
                    )
                    self._writer_stats["last_write_at"] = deps.now_utc_iso()
            finally:
                for _ in batch:
                    self._writer_queue.task_done()

    def writer_status(self) -> Dict[str, Any]:
        with self._writer_lock:
            stats = dict(self._writer_stats)
        thread = self._writer_thread
        return {
            "running": bool(thread is not None and thread.is_alive()),
            "queue_depth": self._writer_queue.qsize(),
            "queue_capacity": self._writer_queue.maxsize,
            "batch_size": self._writer_batch_size,
            **stats,
        }

    def ingest_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Persist one event using the same ordered batch pipeline as the writer."""
        projections = self.ingest_events([event])
        workflow_id = workflow_id_for_event(event) if isinstance(event, dict) else ""
        return self.get_projection(workflow_id) if projections and workflow_id else {}

    def ingest_events(self, events: List[Dict[str, Any]]) -> bool:
        """Append events in order and persist one coalesced projection snapshot."""
        safe_events: List[Dict[str, Any]] = []
        for raw in events:
            if not isinstance(raw, dict):
                continue
            event = _safe(dict(raw))
            event.setdefault("time", deps.now_utc_iso())
            event.setdefault("id", uuid.uuid4().hex)
            event["workflow_id"] = workflow_id_for_event(event)
            safe_events.append(event)
        if not safe_events:
            return False
        for event in safe_events:
            _append_jsonl(self.event_log, event)
        changed = False
        with self._projection_lock:
            data = self._projection_data()
            workflows = data.setdefault("workflows", {})
            for event in safe_events:
                workflow_id = str(event["workflow_id"])
                current = dict(workflows.get(workflow_id) or {"workflow_id": workflow_id})
                projection = self._apply_event(current, event)
                if workflows.get(workflow_id) != projection:
                    workflows[workflow_id] = projection
                    changed = True
            if changed:
                data["updated_at"] = deps.now_utc_iso()
                _write_json(self.projection_file, data)
        for event in safe_events:
            self._maybe_record_command(event)
        if changed:
            self._invalidate_status_cache()
        return changed

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
        projection = WorkflowProjection(
            **{
                k: v
                for k, v in (current or {}).items()
                if k in WorkflowProjection.__annotations__
            }
        ).asdict()
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
        projection["command_id"] = str(
            data.get("command_id") or projection.get("command_id") or ""
        )
        projection["operation"] = str(
            data.get("operation") or projection.get("operation") or ""
        )
        projection["command_subject"] = str(
            data.get("command_subject")
            or data.get("subject")
            or (
                subject
                if subject.startswith("pocketlab.commands.")
                else projection.get("command_subject") or ""
            )
        )
        projection["attempts"] = max(
            int(projection.get("attempts") or 0), int(data.get("attempt") or 0)
        )
        if data.get("error"):
            projection["last_error"] = str(data.get("error"))
        if data.get("replayed_from_dead_letter") or data.get("replay_of"):
            projection["replay_of"] = str(
                data.get("replayed_from_dead_letter") or data.get("replay_of")
            )
        if data.get("replayed_as"):
            projection["replayed_as"] = str(data.get("replayed_as"))

        if etype in SUCCESS_TYPES:
            projection.update(
                {
                    "status": "succeeded",
                    "terminal": True,
                    "success": True,
                    "failed": False,
                }
            )
        elif etype in FAILURE_TYPES:
            projection.update(
                {"status": "failed", "terminal": True, "success": False, "failed": True}
            )
        elif etype in DLQ_TYPES or subject.startswith("pocketlab.dlq."):
            projection.update(
                {
                    "status": "dead_lettered",
                    "terminal": True,
                    "dead_lettered": True,
                    "success": False,
                    "failed": True,
                }
            )
        elif "retry" in etype:
            projection.update({"status": "retrying", "terminal": False})
        elif etype in ACTIVE_TYPES or subject.startswith("pocketlab.commands."):
            projection.update(
                {
                    "status": "running" if "claimed" in etype else "queued",
                    "terminal": False,
                }
            )
        elif not projection.get("terminal"):
            projection["status"] = (
                projection.get("status")
                if projection.get("status") not in {"unknown", ""}
                else "observed"
            )

        if (
            not projection.get("title")
            or projection.get("title") == "Pocket Lab workflow"
        ):
            op = (
                projection.get("operation")
                or projection.get("command_subject")
                or subject
                or workflow_id
            )
            projection["title"] = (
                str(op)
                .replace("pocketlab.commands.", "")
                .replace(".", " ")
                .strip()
                .title()
            )
        return projection

    def _projection_data(self) -> Dict[str, Any]:
        with self._projection_lock:
            if self._projection_cache is None:
                loaded = _read_json(self.projection_file, {"workflows": {}})
                self._projection_cache = loaded if isinstance(loaded, dict) else {"workflows": {}}
                self._projection_cache.setdefault("workflows", {})
            return self._projection_cache

    def get_projection(self, workflow_id: str) -> Dict[str, Any]:
        with self._projection_lock:
            data = self._projection_data()
            return dict(
                (data.get("workflows") or {}).get(str(workflow_id))
                or {"workflow_id": str(workflow_id)}
            )

    def _invalidate_status_cache(self) -> None:
        with self._status_cache_lock:
            self._status_cache = None
            self._status_cache_at = 0.0

    def save_projection(self, projection: Dict[str, Any]) -> bool:
        workflow_id = str(projection.get("workflow_id") or "")
        if not workflow_id:
            return False
        with self._projection_lock:
            data = self._projection_data()
            workflows = data.setdefault("workflows", {})
            current = workflows.get(workflow_id)
            if current == projection:
                with self._writer_lock:
                    self._writer_stats["coalesced"] += 1
                return False
            workflows[workflow_id] = dict(projection)
            data["updated_at"] = deps.now_utc_iso()
            _write_json(self.projection_file, data)
        self._invalidate_status_cache()
        return True

    def iter_events(
        self, workflow_id: str | None = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not self.event_log.exists():
            return events
        lines = self.event_log.read_text(encoding="utf-8").splitlines()
        for line in lines[-max(limit * 3, limit) :]:
            try:
                event = json.loads(line)
            except Exception:
                continue
            if workflow_id and str(
                event.get("workflow_id") or workflow_id_for_event(event)
            ) != str(workflow_id):
                continue
            events.append(event)
        events.sort(key=_event_sort_key)
        return events[-max(1, min(limit, self.history_limit)) :]

    def reconstruct(self, workflow_id: str) -> Dict[str, Any]:
        projection: Dict[str, Any] = {"workflow_id": str(workflow_id)}
        events = self.iter_events(workflow_id=workflow_id, limit=self.history_limit)
        for event in events:
            projection = self._apply_event(projection, event)
        projection["reconstructed_at"] = deps.now_utc_iso()
        projection["source"] = "event-log"
        return {
            "workflow_id": str(workflow_id),
            "projection": projection,
            "events": events,
        }

    def rebuild_all(self) -> Dict[str, Any]:
        projections: Dict[str, Any] = {}
        for event in self.iter_events(limit=self.history_limit):
            workflow_id = str(event.get("workflow_id") or workflow_id_for_event(event))
            projections[workflow_id] = self._apply_event(
                projections.get(workflow_id) or {"workflow_id": workflow_id}, event
            )
        payload = {
            "workflows": projections,
            "rebuilt_at": deps.now_utc_iso(),
            "count": len(projections),
        }
        _write_json(self.projection_file, payload)
        with self._projection_lock:
            self._projection_cache = payload
        return payload

    def list_workflows(
        self, *, status: str = "", include_terminal: bool = True, limit: int = 100
    ) -> List[Dict[str, Any]]:
        data = _read_json(self.projection_file, {"workflows": {}})
        items = list((data.get("workflows") or {}).values())
        if status:
            items = [item for item in items if str(item.get("status")) == status]
        if not include_terminal:
            items = [item for item in items if not item.get("terminal")]
        items.sort(
            key=lambda item: str(
                item.get("updated_at") or item.get("created_at") or ""
            ),
            reverse=True,
        )
        return items[: max(1, min(limit, 1000))]

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
        journal = _read_json(self.command_file, {"commands": {}})
        for item in (journal.get("commands") or {}).values():
            if str(item.get("workflow_id")) == str(workflow_id) or str(
                item.get("command_id")
            ) == str(workflow_id):
                return dict(item)
        # Fall back to command events in journal.
        for event in reversed(
            self.iter_events(workflow_id=workflow_id, limit=self.history_limit)
        ):
            subject = str(event.get("subject") or "")
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if subject.startswith("pocketlab.commands."):
                return {
                    "workflow_id": workflow_id,
                    "command_id": data.get("command_id")
                    or data.get("job_id")
                    or workflow_id,
                    "subject": subject,
                    "command": data,
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

    def status(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._status_cache_lock:
            cached = self._status_cache
            if cached is not None and now - self._status_cache_at < self._status_cache_ttl:
                return {**cached, "counts": dict(cached.get("counts") or {}), "cache": "hit"}

        projections = self.list_workflows(limit=1000)
        counts: Dict[str, int] = {}
        for item in projections:
            status = str(item.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        result = {
            "status": "ok",
            "engine": "event-sourced-workflow-engine",
            "event_log": str(self.event_log),
            "projection_file": str(self.projection_file),
            "workflow_count": len(projections),
            "counts": counts,
            "history_limit": self.history_limit,
            "cache_ttl_seconds": self._status_cache_ttl,
            "projection_writer": self.writer_status(),
        }
        with self._status_cache_lock:
            self._status_cache = {**result, "counts": dict(counts)}
            self._status_cache_at = now
        return {**result, "counts": dict(counts), "cache": "miss"}


WORKFLOW_ENGINE = EventSourcedWorkflowEngine()
