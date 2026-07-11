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


def _state_dir() -> Path:
    root = deps.settings().state_dir / "workflows"
    root.mkdir(parents=True, exist_ok=True)
    (root / "events").mkdir(parents=True, exist_ok=True)
    (root / "projections").mkdir(parents=True, exist_ok=True)
    (root / "commands").mkdir(parents=True, exist_ok=True)
    return root


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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
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

    @property
    def root(self) -> Path:
        return _state_dir()

    @property
    def event_log(self) -> Path:
        return self.root / "events" / "workflow_events.jsonl"

    @property
    def projection_file(self) -> Path:
        return self.root / "projections" / "workflow_projections.json"

    @property
    def command_file(self) -> Path:
        return self.root / "commands" / "command_journal.json"

    def ingest_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Persist an event and update the workflow projection.

        Called by the event bus for every event it records.  Duplicate event IDs
        are harmless because projections are reconstructed deterministically from
        the journal when needed.
        """
        if not isinstance(event, dict):
            return {}
        event = _safe(dict(event))
        event.setdefault("time", deps.now_utc_iso())
        event.setdefault("id", uuid.uuid4().hex)
        workflow_id = workflow_id_for_event(event)
        event["workflow_id"] = workflow_id
        _append_jsonl(self.event_log, event)
        projection = self._apply_event(self.get_projection(workflow_id), event)
        self.save_projection(projection)
        self._maybe_record_command(event)
        return projection

    def _maybe_record_command(self, event: Dict[str, Any]) -> None:
        subject = str(event.get("subject") or "")
        if not subject.startswith("pocketlab.commands."):
            return
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        command_id = str(
            data.get("command_id")
            or data.get("job_id")
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
                "subject": subject,
                "event_type": event.get("type"),
                "command": data,
                "last_event_id": event.get("id"),
                "updated_at": event.get("time") or deps.now_utc_iso(),
            }
        )
        existing.setdefault("created_at", event.get("time") or deps.now_utc_iso())
        commands[command_id] = existing
        _write_json(self.command_file, journal)

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

    def get_projection(self, workflow_id: str) -> Dict[str, Any]:
        data = _read_json(self.projection_file, {"workflows": {}})
        return dict(
            (data.get("workflows") or {}).get(str(workflow_id))
            or {"workflow_id": str(workflow_id)}
        )

    def _invalidate_status_cache(self) -> None:
        with self._status_cache_lock:
            self._status_cache = None
            self._status_cache_at = 0.0

    def save_projection(self, projection: Dict[str, Any]) -> None:
        data = _read_json(self.projection_file, {"workflows": {}})
        workflows = data.setdefault("workflows", {})
        workflows[str(projection.get("workflow_id"))] = projection
        data["updated_at"] = deps.now_utc_iso()
        _write_json(self.projection_file, data)
        self._invalidate_status_cache()

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
        }
        with self._status_cache_lock:
            self._status_cache = {**result, "counts": dict(counts)}
            self._status_cache_at = now
        return {**result, "counts": dict(counts), "cache": "miss"}


WORKFLOW_ENGINE = EventSourcedWorkflowEngine()
