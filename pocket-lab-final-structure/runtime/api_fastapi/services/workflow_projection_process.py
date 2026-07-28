from __future__ import annotations

"""Dedicated workflow projection process.

The API and worker processes only admit compact events to a bounded filesystem
mailbox. This module owns journal append/compaction, deterministic incremental
projection updates, canonical no-op detection, bounded JSON serialization, and
SQLite persistence. It intentionally has no NATS credentials or frontend role.
"""

import gc
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import time
from typing import Any

try:  # Termux/Unix process lock; optional on Windows development hosts.
    import fcntl  # type: ignore
except Exception:  # pragma: no cover - platform dependent
    fcntl = None  # type: ignore

from .. import deps
from ..db.connection import database_path, read_connection
from ..db.runtime import SQLITE_WRITER
from ..db.migrations import apply_migrations
from .workflow_engine import (
    _append_jsonl,
    _apply_projection_event,
    _canonical_projection_material,
    _compact_workflow_event,
    _epoch_ms,
    _read_json,
    _safe_error_type,
    _write_json,
    workflow_id_for_event,
)


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _utc_now() -> str:
    return deps.now_utc_iso()


class _WorkflowDeferred(RuntimeError):
    """Internal safe-boundary deferral; the event is returned to the inbox."""


def _safe_hash(material: Any) -> tuple[str, int, float]:
    started = time.process_time()
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return digest, len(encoded), max(0.0, (time.process_time() - started) * 1000.0)


def _database_instance_id() -> str:
    path = database_path()
    try:
        stat = path.stat()
        material = f"{path}:{stat.st_dev}:{stat.st_ino}"
    except OSError:
        material = f"{path}:missing"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _memory_snapshot(cache: dict[str, Any], *, interval_seconds: float) -> dict[str, Any]:
    now = time.monotonic()
    if cache and now - float(cache.get("checked_monotonic") or 0.0) < interval_seconds:
        return cache
    total_kb = available_kb = 0
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("MemTotal:"):
                total_kb = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available_kb = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        total_kb = available_kb = 0
    percent = (available_kb / total_kb * 100.0) if total_kb > 0 else 100.0
    cache.clear()
    cache.update({
        "checked_monotonic": now,
        "available_percent": round(percent, 3),
        "source": "proc_meminfo" if total_kb > 0 else "unavailable",
    })
    return cache


def _rss_bytes() -> int:
    try:
        text = Path("/proc/self/status").read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("VmRSS:"):
                return max(0, int(line.split()[1]) * 1024)
    except (OSError, ValueError, IndexError):
        return 0
    return 0


class WorkflowProjectionProcess:
    def __init__(self) -> None:
        self.generation = _bounded_int("POCKETLAB_WORKFLOW_PROCESS_GENERATION", 1, 1, 2_000_000_000)
        state_override = str(os.environ.get("POCKETLAB_STATE_DIR") or "").strip()
        state_dir = Path(state_override).expanduser() if state_override else deps.settings().state_dir
        self.root = state_dir / "workflows"
        self.mailbox = self.root / "mailbox"
        self.inbox = self.mailbox / "inbox"
        self.processing = self.mailbox / "processing"
        self.failed = self.mailbox / "failed"
        self.runtime_dir = self.root / "runtime"
        self.event_log = self.root / "events" / "workflow_events.jsonl"
        self.compat_projection = self.root / "projections" / "workflow_projections.json"
        self.command_file = self.root / "commands" / "command_journal.json"
        self.status_file = self.runtime_dir / "process_status.json"
        self.lock_file = self.runtime_dir / "projection.lock"
        for path in (self.inbox, self.processing, self.failed, self.runtime_dir, self.event_log.parent, self.compat_projection.parent, self.command_file.parent):
            path.mkdir(parents=True, exist_ok=True)

        self.batch_max_events = _bounded_int("POCKETLAB_WORKFLOW_BATCH_MAX_EVENTS", 24, 1, 256)
        self.batch_cpu_ms = _bounded_float("POCKETLAB_WORKFLOW_BATCH_CPU_MS", 35.0, 1.0, 2_000.0)
        self.batch_wall_ms = _bounded_float("POCKETLAB_WORKFLOW_BATCH_WALL_MS", 100.0, 5.0, 10_000.0)
        self.serialized_bytes_max = _bounded_int("POCKETLAB_WORKFLOW_SERIALIZED_BYTES_MAX", 64 * 1024, 4 * 1024, 2 * 1024 * 1024)
        self.projection_item_max = _bounded_int("POCKETLAB_WORKFLOW_PROJECTION_ITEM_MAX", 64, 16, 1_024)
        self.reconcile_max_rows = _bounded_int("POCKETLAB_WORKFLOW_RECONCILE_MAX_ROWS", 1_000, 100, 10_000)
        self.reconcile_workflow_max = _bounded_int("POCKETLAB_WORKFLOW_RECONCILE_WORKFLOW_MAX", 256, 16, 2_048)
        self.updates_per_workflow_batch = _bounded_int("POCKETLAB_WORKFLOW_UPDATES_PER_WORKFLOW_BATCH", 8, 1, 128)
        self.sqlite_deadline_seconds = _bounded_float("POCKETLAB_WORKFLOW_SQLITE_DEADLINE_SECONDS", 2.0, 0.1, 10.0)
        self.history_limit = _bounded_int("POCKETLAB_WORKFLOW_HISTORY_LIMIT", 5000, 100, 100_000)
        self.event_retention = _bounded_int("POCKETLAB_WORKFLOW_EVENT_INDEX_LIMIT", self.history_limit * 2, 500, 200_000)
        self.journal_max_bytes = _bounded_int("POCKETLAB_WORKFLOW_JOURNAL_MAX_BYTES", 16 * 1024 * 1024, 256 * 1024, 256 * 1024 * 1024)
        self.recycle_event_count = _bounded_int("POCKETLAB_WORKFLOW_RECYCLE_EVENT_COUNT", 10_000, 100, 1_000_000)
        self.recycle_batch_count = _bounded_int("POCKETLAB_WORKFLOW_RECYCLE_BATCH_COUNT", 2_000, 10, 100_000)
        self.recycle_rss_bytes = _bounded_int("POCKETLAB_WORKFLOW_RECYCLE_RSS_BYTES", 256 * 1024 * 1024, 64 * 1024 * 1024, 4 * 1024 * 1024 * 1024)
        self.memory_min_available_percent = _bounded_float("POCKETLAB_WORKFLOW_MEMORY_MIN_AVAILABLE_PERCENT", 8.0, 1.0, 80.0)
        self.memory_probe_seconds = _bounded_float("POCKETLAB_WORKFLOW_MEMORY_PROBE_SECONDS", 5.0, 1.0, 60.0)
        self.poll_seconds = _bounded_float("POCKETLAB_WORKFLOW_POLL_SECONDS", 0.15, 0.02, 5.0)
        self.stagger_ms = int(hashlib.sha256(b"workflow-projection").hexdigest()[:4], 16) % _bounded_int("POCKETLAB_WORKFLOW_STAGGER_MAX_MS", 500, 0, 5_000) if _bounded_int("POCKETLAB_WORKFLOW_STAGGER_MAX_MS", 500, 0, 5_000) else 0

        self.stop_requested = False
        self.started_at = _utc_now()
        self.database_instance = ""
        self.processed_events = 0
        self.batch_count = 0
        self.canonical_noop_count = 0
        self.canonical_change_count = 0
        self.hash_cpu_ms = 0.0
        self.hash_input_bytes = 0
        self.serialization_ms = 0.0
        self.serialized_bytes = 0
        self.memory_pressure_deferred_count = 0
        self.cpu_budget_deferred_count = 0
        self.failed_events = 0
        self.last_error_type = ""
        self.last_error_at = ""
        self.last_success_at = ""
        self.last_batch_size = 0
        self.last_batch_started_at = ""
        self.last_batch_completed_at = ""
        self.last_batch_wall_ms = 0.0
        self.last_batch_cpu_ms = 0.0
        self.last_batch_serialized_bytes = 0
        self.last_batch_allocation_bytes = 0
        self.pressure_deferred_count = 0
        self.last_known_good_revision = 0
        self.next_batch_due_ms = self.stagger_ms
        self._memory_cache: dict[str, Any] = {}
        self._lock_handle: Any = None

    def _acquire_lock(self) -> None:
        handle = self.lock_file.open("a+")
        if fcntl is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.close()
                raise RuntimeError("workflow_projection_process_already_running") from exc
        self._lock_handle = handle
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()

    def _recover_processing(self) -> None:
        for path in sorted(self.processing.glob("*.json")):
            target = self.inbox / path.name
            try:
                if target.exists():
                    path.unlink(missing_ok=True)
                else:
                    os.replace(path, target)
            except OSError:
                continue

    def _status(self, **extra: Any) -> dict[str, Any]:
        inbox = list(self.inbox.glob("*.json"))
        oldest_age_ms = 0
        if inbox:
            try:
                oldest = min(path.stat().st_mtime for path in inbox)
                oldest_age_ms = max(0, int((time.time() - oldest) * 1000))
            except OSError:
                oldest_age_ms = 0
        return {
            "process_alive": not self.stop_requested,
            "process_pid": os.getpid(),
            "process_generation": self.generation,
            "execution_owner": "pocket-worker/workflow-subprocess",
            "started_at": self.started_at,
            "heartbeat_at": _utc_now(),
            "queue_depth": len(inbox),
            "oldest_queue_age_ms": oldest_age_ms,
            "processed_events": self.processed_events,
            "batch_count": self.batch_count,
            "last_batch_size": self.last_batch_size,
            "last_batch_started_at": self.last_batch_started_at,
            "last_batch_completed_at": self.last_batch_completed_at,
            "last_batch_wall_ms": round(self.last_batch_wall_ms, 3),
            "last_batch_cpu_ms": round(self.last_batch_cpu_ms, 3),
            "last_batch_serialized_bytes": self.last_batch_serialized_bytes,
            "last_batch_allocation_bytes": self.last_batch_allocation_bytes,
            "serialization_ms": round(self.serialization_ms, 3),
            "serialized_bytes": self.serialized_bytes,
            "allocation_bytes": self.serialized_bytes,
            "canonical_noop_count": self.canonical_noop_count,
            "canonical_change_count": self.canonical_change_count,
            "hash_cpu_ms": round(self.hash_cpu_ms, 3),
            "hash_input_bytes": self.hash_input_bytes,
            "memory_pressure_deferred_count": self.memory_pressure_deferred_count,
            "cpu_budget_deferred_count": self.cpu_budget_deferred_count,
            "pressure_deferred_count": self.pressure_deferred_count,
            "last_error_type": self.last_error_type,
            "last_error_at": self.last_error_at,
            "last_success_at": self.last_success_at,
            "last_known_good_revision": self.last_known_good_revision,
            "next_batch_due_ms": self.next_batch_due_ms,
            "stagger_ms": self.stagger_ms,
            "rss_bytes": _rss_bytes(),
            "database_ready": database_path().exists(),
            "database_instance": self.database_instance,
            "sanitized": True,
            **extra,
        }

    def _write_status(self, **extra: Any) -> None:
        try:
            _write_json(self.status_file, self._status(**extra))
        except OSError:
            return

    def _compact_journal_if_needed(self) -> None:
        try:
            if self.event_log.stat().st_size <= self.journal_max_bytes:
                return
            lines = self.event_log.read_text(encoding="utf-8", errors="replace").splitlines()
            retained = lines[-self.history_limit :]
            tmp = self.event_log.with_suffix(".jsonl.compact.tmp")
            tmp.write_text("\n".join(retained) + ("\n" if retained else ""), encoding="utf-8")
            os.replace(tmp, self.event_log)
        except OSError:
            return

    def _prepared_projection(self, conn: sqlite3.Connection, workflow_id: str) -> tuple[dict[str, Any], str, int, int]:
        row = conn.execute(
            "SELECT projection_json, canonical_hash, revision, process_generation FROM workflow_current_state WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return {"workflow_id": workflow_id}, "", 0, 0
        try:
            payload = json.loads(str(row["projection_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {"workflow_id": workflow_id}
        return (
            payload if isinstance(payload, dict) else {"workflow_id": workflow_id},
            str(row["canonical_hash"]),
            int(row["revision"]),
            int(row["process_generation"]),
        )

    def _record_command(self, conn: sqlite3.Connection, event: dict[str, Any]) -> None:
        subject = str(event.get("subject") or "")
        event_type = str(event.get("type") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        command_subject = str(data.get("command_subject") or data.get("subject") or (subject if subject.startswith("pocketlab.commands.") else ""))
        if not command_subject and not event_type.startswith("command."):
            return
        command_id = str(data.get("command_id") or data.get("job_id") or data.get("run_id") or event.get("trace_id") or event.get("id") or "")
        if not command_id:
            return
        now = str(event.get("time") or _utc_now())
        command_json = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(command_json.encode("utf-8")) > self.serialized_bytes_max:
            command_json = "{}"
        conn.execute(
            """
            INSERT INTO workflow_command_state(
                command_id, workflow_id, subject, event_type, command_json,
                created_at, updated_at, updated_at_epoch_ms, process_generation, database_instance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(command_id) DO UPDATE SET
                workflow_id=excluded.workflow_id,
                subject=excluded.subject,
                event_type=excluded.event_type,
                command_json=excluded.command_json,
                updated_at=excluded.updated_at,
                updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                process_generation=excluded.process_generation,
                database_instance=excluded.database_instance
            """,
            (command_id, str(event.get("workflow_id") or workflow_id_for_event(event)), command_subject or subject, event_type, command_json, now, now, _epoch_ms(now), self.generation, self.database_instance),
        )

    def _record_control_plane_command(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "")
        subject = str(event.get("subject") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
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
        if lifecycle_status is None:
            return
        command_id = str(data.get("command_id") or data.get("job_id") or data.get("run_id") or event.get("trace_id") or event.get("id") or "")
        if not command_id:
            return
        entity_type = "control"
        entity_id = "control-plane"
        if data.get("app_id"):
            entity_type, entity_id = "app", str(data.get("app_id"))
        elif data.get("node_id") or data.get("device_id"):
            entity_type, entity_id = "device", str(data.get("node_id") or data.get("device_id"))
        elif data.get("run_id") or ".security." in subject:
            entity_type, entity_id = "security", str(data.get("run_id") or "security")
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
                subject=str(data.get("command_subject") or data.get("subject") or subject or "pocketlab.commands.unknown"),
                status=lifecycle_status,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summaries[lifecycle_status],
                recovery_action=event_type if lifecycle_status == "recovery_action" else "",
            )
        except Exception:
            return

    def _process_event(
        self,
        path: Path,
        *,
        remaining_serialized_bytes: int,
        workflow_updates: dict[str, int],
    ) -> str:
        processing = self.processing / path.name
        try:
            os.replace(path, processing)
        except OSError:
            return "skipped"
        try:
            raw = json.loads(processing.read_text(encoding="utf-8"))
            event = _compact_workflow_event(raw)
            if not event:
                raise ValueError("invalid_workflow_event")
            event_id = str(event["id"])
            workflow_id = str(event["workflow_id"])
            if workflow_updates.get(workflow_id, 0) >= self.updates_per_workflow_batch:
                raise _WorkflowDeferred("per_workflow_batch_budget")
            event_json = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            event_bytes = len(event_json.encode("utf-8"))
            if event_bytes > self.serialized_bytes_max:
                raise ValueError("workflow_event_too_large")

            def write(tx: sqlite3.Connection) -> dict[str, Any]:
                if self.database_instance and _database_instance_id() != self.database_instance:
                    raise RuntimeError("workflow_database_instance_changed")
                duplicate = tx.execute(
                    "SELECT 1 FROM workflow_event_index WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if duplicate is not None:
                    return {"duplicate": True}
                current, current_hash, revision, current_generation = self._prepared_projection(tx, workflow_id)
                if current_generation > self.generation:
                    raise RuntimeError("stale_workflow_process_generation")
                candidate = _apply_projection_event(current, event)
                if len(candidate) > self.projection_item_max:
                    raise ValueError("workflow_projection_item_budget_exceeded")
                candidate_hash, hash_bytes, hash_ms = _safe_hash(
                    _canonical_projection_material(candidate)
                )
                now = str(event.get("time") or _utc_now())
                changed = candidate_hash != current_hash
                serialized_bytes = 0
                serialize_ms = 0.0
                next_revision = revision
                projection_json = ""
                if changed:
                    serialize_started = time.process_time()
                    projection_json = json.dumps(
                        candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    )
                    serialize_ms = max(0.0, (time.process_time() - serialize_started) * 1000.0)
                    serialized_bytes = len(projection_json.encode("utf-8"))
                    if serialized_bytes > self.serialized_bytes_max:
                        raise ValueError("workflow_projection_too_large")
                    if serialized_bytes > max(0, int(remaining_serialized_bytes)):
                        raise _WorkflowDeferred("batch_serialization_budget")
                    next_revision = revision + 1

                tx.execute(
                    "INSERT INTO workflow_event_index(event_id, workflow_id, event_type, subject, event_json, observed_at, observed_at_epoch_ms, process_generation, database_instance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_id, workflow_id, str(event.get("type") or ""), str(event.get("subject") or ""), event_json, now, _epoch_ms(now), self.generation, self.database_instance),
                )
                self._record_command(tx, event)
                if changed:
                    tx.execute(
                        """
                        INSERT INTO workflow_current_state(
                            workflow_id, projection_json, canonical_hash, status, terminal,
                            revision, semantic_event_count, updated_at, updated_at_epoch_ms,
                            process_generation, database_instance
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(workflow_id) DO UPDATE SET
                            projection_json=excluded.projection_json,
                            canonical_hash=excluded.canonical_hash,
                            status=excluded.status,
                            terminal=excluded.terminal,
                            revision=excluded.revision,
                            semantic_event_count=excluded.semantic_event_count,
                            updated_at=excluded.updated_at,
                            updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                            process_generation=excluded.process_generation,
                            database_instance=excluded.database_instance
                        """,
                        (workflow_id, projection_json, candidate_hash, str(candidate.get("status") or "unknown"), 1 if candidate.get("terminal") else 0, next_revision, int(candidate.get("event_count") or 0), str(candidate.get("updated_at") or now), _epoch_ms(candidate.get("updated_at") or now), self.generation, self.database_instance),
                    )
                count = tx.execute("SELECT COUNT(*) AS count FROM workflow_event_index").fetchone()
                excess = max(0, int(count["count"] if count else 0) - self.event_retention)
                if excess:
                    tx.execute(
                        "DELETE FROM workflow_event_index WHERE event_id IN (SELECT event_id FROM workflow_event_index ORDER BY observed_at_epoch_ms ASC, event_id ASC LIMIT ?)",
                        (min(excess, 1_000),),
                    )
                return {
                    "duplicate": False,
                    "changed": changed,
                    "revision": next_revision,
                    "hash_bytes": hash_bytes,
                    "hash_ms": hash_ms,
                    "serialize_ms": serialize_ms,
                    "serialized_bytes": serialized_bytes,
                }

            result = SQLITE_WRITER.submit(
                "workflow.projection.event", write, deadline_seconds=self.sqlite_deadline_seconds
            )
            if result.get("duplicate"):
                processing.unlink(missing_ok=True)
                self.canonical_noop_count += 1
                return "duplicate"
            self.hash_cpu_ms += float(result.get("hash_ms") or 0.0)
            self.hash_input_bytes += int(result.get("hash_bytes") or 0)
            changed = bool(result.get("changed"))
            if changed:
                self.serialization_ms += float(result.get("serialize_ms") or 0.0)
                self.serialized_bytes += int(result.get("serialized_bytes") or 0)
                self.canonical_change_count += 1
                self.last_known_good_revision = max(
                    self.last_known_good_revision, int(result.get("revision") or 0)
                )
            else:
                self.canonical_noop_count += 1

            self._record_control_plane_command(event)
            try:
                _append_jsonl(self.event_log, event)
            except OSError as exc:
                self.last_error_type = _safe_error_type(exc)
                self.last_error_at = _utc_now()
            processing.unlink(missing_ok=True)
            workflow_updates[workflow_id] = workflow_updates.get(workflow_id, 0) + 1
            self.processed_events += 1
            self.last_success_at = _utc_now()
            return "changed" if changed else "noop"
        except _WorkflowDeferred as exc:
            self.pressure_deferred_count += 1
            if "serialization" in str(exc):
                self.cpu_budget_deferred_count += 1
            try:
                os.replace(processing, self.inbox / processing.name)
            except OSError:
                pass
            return "deferred"
        except Exception as exc:
            self.failed_events += 1
            self.last_error_type = _safe_error_type(exc)
            self.last_error_at = _utc_now()
            target = self.failed / processing.name
            try:
                os.replace(processing, target)
                _write_json(target.with_suffix(".error.json"), {
                    "status": "failed",
                    "error_type": self.last_error_type,
                    "failed_at": self.last_error_at,
                    "process_generation": self.generation,
                    "sanitized": True,
                })
            except OSError:
                pass
            return "failed"

    def _rebuild_all(self, control_path: Path) -> None:
        processing = self.processing / control_path.name
        try:
            os.replace(control_path, processing)
        except OSError:
            return
        projections: dict[str, dict[str, Any]] = {}
        try:
            with read_connection() as conn:
                rows = conn.execute(
                    "SELECT event_json FROM workflow_event_index ORDER BY observed_at_epoch_ms DESC, event_id DESC LIMIT ?",
                    (self.reconcile_max_rows,),
                ).fetchall()
            for row in reversed(rows):
                try:
                    event = _compact_workflow_event(json.loads(str(row["event_json"])))
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
                if not event:
                    continue
                workflow_id = str(event["workflow_id"])
                projections[workflow_id] = _apply_projection_event(
                    projections.get(workflow_id) or {"workflow_id": workflow_id}, event
                )
                if len(projections) >= self.reconcile_workflow_max:
                    break

            def write(tx: sqlite3.Connection) -> dict[str, Any]:
                if self.database_instance and _database_instance_id() != self.database_instance:
                    raise RuntimeError("workflow_database_instance_changed")
                changed = 0
                max_revision = 0
                hash_bytes_total = 0
                hash_ms_total = 0.0
                for workflow_id, projection in projections.items():
                    material_hash, hash_bytes, hash_ms = _safe_hash(
                        _canonical_projection_material(projection)
                    )
                    payload = json.dumps(
                        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    )
                    if len(payload.encode("utf-8")) > self.serialized_bytes_max:
                        continue
                    row = tx.execute(
                        "SELECT revision, process_generation, canonical_hash FROM workflow_current_state WHERE workflow_id=?",
                        (workflow_id,),
                    ).fetchone()
                    if row is not None and int(row["process_generation"]) > self.generation:
                        raise RuntimeError("stale_workflow_process_generation")
                    if row is not None and str(row["canonical_hash"]) == material_hash:
                        continue
                    revision = int(row["revision"] if row else 0) + 1
                    tx.execute(
                        """
                        INSERT INTO workflow_current_state(workflow_id, projection_json, canonical_hash, status, terminal, revision, semantic_event_count, updated_at, updated_at_epoch_ms, process_generation, database_instance)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(workflow_id) DO UPDATE SET projection_json=excluded.projection_json, canonical_hash=excluded.canonical_hash, status=excluded.status, terminal=excluded.terminal, revision=excluded.revision, semantic_event_count=excluded.semantic_event_count, updated_at=excluded.updated_at, updated_at_epoch_ms=excluded.updated_at_epoch_ms, process_generation=excluded.process_generation, database_instance=excluded.database_instance
                        """,
                        (workflow_id, payload, material_hash, str(projection.get("status") or "unknown"), 1 if projection.get("terminal") else 0, revision, int(projection.get("event_count") or 0), str(projection.get("updated_at") or _utc_now()), _epoch_ms(projection.get("updated_at")), self.generation, self.database_instance),
                    )
                    changed += 1
                    max_revision = max(max_revision, revision)
                    hash_bytes_total += hash_bytes
                    hash_ms_total += hash_ms
                return {
                    "changed": changed,
                    "max_revision": max_revision,
                    "hash_bytes": hash_bytes_total,
                    "hash_ms": hash_ms_total,
                }

            result = SQLITE_WRITER.submit(
                "workflow.projection.reconcile", write, deadline_seconds=self.sqlite_deadline_seconds
            )
            self.hash_input_bytes += int(result.get("hash_bytes") or 0)
            self.hash_cpu_ms += float(result.get("hash_ms") or 0.0)
            self.canonical_change_count += int(result.get("changed") or 0)
            self.last_known_good_revision = max(
                self.last_known_good_revision, int(result.get("max_revision") or 0)
            )
            processing.unlink(missing_ok=True)
            self.last_success_at = _utc_now()
        except Exception as exc:
            self.last_error_type = _safe_error_type(exc)
            self.last_error_at = _utc_now()
            try:
                os.replace(processing, self.failed / processing.name)
            except OSError:
                pass

    def _write_compat_snapshot(self) -> None:
        """Write the legacy aggregate only at bounded batch boundaries."""
        try:
            with read_connection() as conn:
                rows = conn.execute(
                    "SELECT workflow_id, projection_json FROM workflow_current_state ORDER BY updated_at_epoch_ms DESC LIMIT ?",
                    (self.history_limit,),
                ).fetchall()
            workflows: dict[str, Any] = {}
            retained_bytes = 0
            truncated = False
            for row in rows:
                raw = str(row["projection_json"])
                raw_bytes = len(raw.encode("utf-8"))
                if retained_bytes + raw_bytes > self.serialized_bytes_max:
                    truncated = True
                    break
                try:
                    workflows[str(row["workflow_id"])] = json.loads(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                retained_bytes += raw_bytes
            _write_json(self.compat_projection, {
                "workflows": workflows,
                "updated_at": _utc_now(),
                "source": "workflow_projection_process",
                "truncated": truncated,
            })
        except Exception as exc:
            self.last_error_type = _safe_error_type(exc)
            self.last_error_at = _utc_now()

    def run(self) -> int:
        self._acquire_lock()
        apply_migrations()
        self.database_instance = _database_instance_id()
        self._recover_processing()
        self._write_status(status="starting")
        if self.stagger_ms:
            time.sleep(self.stagger_ms / 1000.0)
        self._write_status(status="running")

        while not self.stop_requested:
            memory = _memory_snapshot(self._memory_cache, interval_seconds=self.memory_probe_seconds)
            under_pressure = float(memory.get("available_percent") or 100.0) < self.memory_min_available_percent
            files = sorted(self.inbox.glob("*.json"), key=lambda path: (path.stat().st_mtime, path.name))
            if not files:
                self.next_batch_due_ms = int(self.poll_seconds * 1000)
                self._write_status(status="idle", memory_pressure=under_pressure, memory_source=memory.get("source"))
                time.sleep(self.poll_seconds)
                continue
            if under_pressure:
                # Preserve terminal/critical events by processing one compact item;
                # defer reconciliation and normal batch growth.
                control_only = [path for path in files if path.name.startswith("control-")]
                if control_only:
                    self.memory_pressure_deferred_count += len(control_only)
                    time.sleep(min(1.0, self.poll_seconds * 4))
                    self._write_status(status="degraded", degraded_reason="memory_pressure")
                    continue
                files = files[:1]

            batch_started_wall = time.monotonic()
            batch_started_cpu = time.process_time()
            serialized_before = self.serialized_bytes
            self.last_batch_started_at = _utc_now()
            processed = 0
            workflow_updates: dict[str, int] = {}
            for path in files[: self.batch_max_events]:
                cpu_ms = max(0.0, (time.process_time() - batch_started_cpu) * 1000.0)
                wall_ms = max(0.0, (time.monotonic() - batch_started_wall) * 1000.0)
                if cpu_ms >= self.batch_cpu_ms or wall_ms >= self.batch_wall_ms:
                    self.cpu_budget_deferred_count += max(0, len(files) - processed)
                    self.pressure_deferred_count += max(0, len(files) - processed)
                    break
                if path.name.startswith("control-rebuild-"):
                    self._rebuild_all(path)
                    outcome = "changed"
                else:
                    outcome = self._process_event(
                        path,
                        remaining_serialized_bytes=max(0, self.serialized_bytes_max - (self.serialized_bytes - serialized_before)),
                        workflow_updates=workflow_updates,
                    )
                if outcome == "deferred":
                    break
                processed += 1
            self.batch_count += 1
            self.last_batch_size = processed
            self.last_batch_cpu_ms = max(0.0, (time.process_time() - batch_started_cpu) * 1000.0)
            self.last_batch_wall_ms = max(0.0, (time.monotonic() - batch_started_wall) * 1000.0)
            self.last_batch_serialized_bytes = max(0, self.serialized_bytes - serialized_before)
            self.last_batch_allocation_bytes = self.last_batch_serialized_bytes
            self.last_batch_completed_at = _utc_now()
            self._compact_journal_if_needed()
            if self.batch_count % _bounded_int("POCKETLAB_WORKFLOW_COMPAT_SNAPSHOT_BATCHES", 10, 1, 1000) == 0:
                self._write_compat_snapshot()
            self._write_status(status="running", memory_pressure=under_pressure, memory_source=memory.get("source"))
            if self.batch_count % 20 == 0:
                gc.collect()
            rss = _rss_bytes()
            if self.processed_events >= self.recycle_event_count or self.batch_count >= self.recycle_batch_count or (rss and rss >= self.recycle_rss_bytes):
                self._write_status(status="recycling", recycle_reason="bounded_threshold")
                SQLITE_WRITER.shutdown(timeout_seconds=2.0)
                return 75
        self._write_status(status="stopped", process_alive=False)
        SQLITE_WRITER.shutdown(timeout_seconds=2.0)
        return 0


def main() -> int:
    runtime = WorkflowProjectionProcess()

    def _stop(*_: Any) -> None:
        runtime.stop_requested = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _stop)
        except Exception:
            pass
    try:
        return runtime.run()
    except Exception as exc:
        runtime.last_error_type = _safe_error_type(exc)
        runtime.last_error_at = _utc_now()
        runtime._write_status(status="failed", process_alive=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
