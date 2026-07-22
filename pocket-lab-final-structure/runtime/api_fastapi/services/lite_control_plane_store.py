from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .. import deps
from ..db.connection import database_path
from ..db.migrations import apply_migrations
from ..db.runtime import (
    SQLITE_READS,
    SQLITE_WRITER,
    SQLiteWriteDeadlineExceeded,
    SQLiteWriteRejected,
)


_LOGGER = logging.getLogger(__name__)
_ACTIVE_STATUSES = frozenset({"queued", "published", "received", "accepted", "running"})
_TERMINAL_STATUSES = frozenset(
    {"succeeded", "failed", "cancelled", "undeliverable", "timed_out"}
)
_SECRET_KEYS = re.compile(
    r"(?:token|password|secret|credential|api[_-]?key|private[_-]?key|auth|cookie|bootstrap|command_payload|raw_log|raw_evidence)",
    re.IGNORECASE,
)
_REVISION_DOMAINS = (
    "security", "fleet", "apps", "recovery", "commands", "storage", "audit",
)
_REVISION_REASONS = frozenset({
    "domain_state_changed",
    "security_state_changed",
    "fleet_state_changed",
    "apps_state_changed",
    "app_subprojection_changed",
    "recovery_state_changed",
    "command_state_changed",
    "audit_state_changed",
    "storage_state_changed",
    "database_instance_changed",
    "cursor_too_old",
    "cursor_ahead",
    "malformed_cursor",
})
_MAX_CHANGED_IDS = 32
_REVISION_EVENT_PAGE_LIMIT = 100
_REVISION_EVENT_RETENTION_COUNT = 2048
_REVISION_EVENT_RETENTION_MS = 7 * 24 * 60 * 60 * 1000
_COMMAND_LIFECYCLE_STAGES = frozenset({
    "accepted", "published", "delivered", "worker_claimed", "running", "terminal",
    "failed", "timed_out", "ignored_redelivery", "recovery_action",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_ms(value: Any = None) -> int:
    if value is None or value == "":
        return int(time.time() * 1000)
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number if number > 10_000_000_000 else number * 1000)
    text = str(value).strip()
    if not text:
        return int(time.time() * 1000)
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)
    except (TypeError, ValueError):
        return int(time.time() * 1000)


def _encode_cursor(epoch_ms: int, row_id: str) -> str:
    raw = json.dumps([int(epoch_ms), str(row_id)], separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[int, str] | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > 512:
        raise ValueError("History cursor is too long")
    try:
        padded = text + "=" * (-len(text) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(decoded, list) or len(decoded) != 2:
            raise ValueError
        epoch_ms = int(decoded[0])
        row_id = str(decoded[1])[:160]
        if epoch_ms < 0 or not row_id:
            raise ValueError
        return epoch_ms, row_id
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, base64.binascii.Error) as exc:
        raise ValueError("Invalid history cursor") from exc


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\x00", " ").strip()
    if not text:
        return ""
    if _SECRET_KEYS.search(text):
        return "Protected metadata"
    return text[:limit]


def _safe_json(value: Any, *, max_bytes: int = 4096) -> str:
    def sanitize(item: Any, depth: int = 0) -> Any:
        if depth > 4:
            return None
        if isinstance(item, dict):
            result: dict[str, Any] = {}
            for key, child in list(item.items())[:32]:
                name = str(key)[:80]
                if _SECRET_KEYS.search(name):
                    continue
                result[name] = sanitize(child, depth + 1)
            return result
        if isinstance(item, list):
            return [sanitize(child, depth + 1) for child in item[:32]]
        if isinstance(item, (str, int, float, bool)) or item is None:
            return _safe_text(item, 256) if isinstance(item, str) else item
        return _safe_text(item, 128)

    encoded = json.dumps(sanitize(value), sort_keys=True, separators=(",", ":"))
    return encoded if len(encoded.encode("utf-8")) <= max_bytes else "{}"




def _compact_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    keys = (
        "operation_id", "command_id", "action_id", "status", "summary",
        "progress", "queued_at", "started_at", "updated_at", "completed_at",
        "evidence_ref", "preview_id", "backup_id",
    )
    result = {key: value.get(key) for key in keys if value.get(key) is not None}
    if isinstance(value.get("checks"), list):
        result["checks"] = [
            {k: item.get(k) for k in ("id", "status", "summary") if item.get(k) is not None}
            for item in value["checks"][:8] if isinstance(item, dict)
        ]
    if isinstance(value.get("repair_steps"), list):
        result["repair_steps"] = [
            {k: item.get(k) for k in ("id", "status", "summary") if item.get(k) is not None}
            for item in value["repair_steps"][:8] if isinstance(item, dict)
        ]
    return result


def _compact_app_subprojection(name: str, payload: Any) -> dict[str, Any]:
    value = payload if isinstance(payload, dict) else {}
    if name == "catalog":
        access = value.get("access") if isinstance(value.get("access"), dict) else {}
        runtime = value.get("runtime") if isinstance(value.get("runtime"), dict) else {}
        actions = value.get("actions") if isinstance(value.get("actions"), dict) else {}
        return {
            key: value.get(key)
            for key in ("id", "app_id", "name", "status", "installed", "install_state", "host_device_id", "host_device_name")
            if value.get(key) is not None
        } | {
            "access": {"open_url": access.get("open_url")} if access.get("open_url") == "/apps/photoprism/" else {},
            "runtime": {"url": runtime.get("url")} if runtime.get("url") == "/apps/photoprism/" else {},
            "actions": {"open": bool(actions.get("open"))},
        }
    if name == "media":
        result = {
            key: value.get(key)
            for key in ("status", "summary", "mapping_count", "operation_running", "updated_at")
            if value.get(key) is not None
        }
        if isinstance(value.get("evidence"), dict):
            result["evidence"] = {
                key: value["evidence"].get(key)
                for key in ("status", "count", "updated_at")
                if value["evidence"].get(key) is not None
            }
        return result
    if name == "operations":
        actions = value.get("actions") if isinstance(value.get("actions"), dict) else {}
        return {
            "status": value.get("status"),
            "summary": value.get("summary"),
            "operation_running": bool(value.get("operation_running")),
            "current_action": _compact_event(value.get("current_action")),
            "last_safety_check": _compact_event(value.get("last_safety_check")),
            "last_repair": _compact_event(value.get("last_repair")),
            "actions": {
                key: _compact_event(item)
                for key, item in list(actions.items())[:8]
                if isinstance(item, dict)
            },
        }
    if name == "update":
        actions = value.get("actions") if isinstance(value.get("actions"), dict) else {}
        readiness = value.get("readiness") if isinstance(value.get("readiness"), dict) else {}
        update_action = actions.get("update_app") if isinstance(actions.get("update_app"), dict) else {}
        return {
            "status": value.get("status"),
            "summary": value.get("summary"),
            "operation_running": bool(value.get("operation_running")),
            "pending_check": _compact_event(value.get("pending_check")),
            "latest_check": _compact_event(value.get("latest_check")),
            "readiness": {
                key: readiness.get(key)
                for key in ("status", "summary", "ready", "reason")
                if readiness.get(key) is not None
            },
            "actions": {
                "update_app": {
                    key: update_action.get(key)
                    for key in ("enabled", "label", "status", "disabled_reason")
                    if update_action.get(key) is not None
                }
            },
        }
    if name == "backup":
        if value.get("kind") == "profile":
            backup = value.get("backup") if isinstance(value.get("backup"), dict) else {}
            recovery = value.get("recovery") if isinstance(value.get("recovery"), dict) else {}
            return {"kind": "profile", "backup": backup, "recovery": recovery}
        raw = value.get("payload") if value.get("kind") == "raw" and isinstance(value.get("payload"), dict) else value
        return {
            "kind": "raw",
            "payload": {
                key: raw.get(key)
                for key in (
                    "status", "summary", "default_mode", "media", "backup_target",
                    "backup_target_summary", "latest_verified_backup_id", "backup_running",
                    "restore_preview_disabled_reason", "last_checked_at",
                )
                if raw.get(key) is not None
            } | {
                "latest_backup": _compact_event(raw.get("latest_backup")),
                "pending_backup": _compact_event(raw.get("pending_backup")),
                "latest_restore_preview": _compact_event(raw.get("latest_restore_preview")),
                "restore": raw.get("restore") if isinstance(raw.get("restore"), dict) else {},
                "evidence": raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {},
            },
        }
    if name == "security":
        if value.get("kind") == "profile":
            return {"kind": "profile", "security": value.get("security") if isinstance(value.get("security"), dict) else {}}
        raw = value.get("payload") if value.get("kind") == "raw" and isinstance(value.get("payload"), dict) else value
        return {
            "kind": "raw",
            "payload": {
                key: raw.get(key)
                for key in ("status", "summary", "last_checked_at")
                if raw.get(key) is not None
            } | {"evidence": raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}},
        }
    if name == "backup_targets":
        return {
            key: value.get(key)
            for key in ("status", "summary", "ready", "available", "count", "ready_count", "target_label", "updated_at")
            if value.get(key) is not None
        }
    return value

def _normalize_status(value: Any) -> str:
    raw = str(value or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "complete": "succeeded",
        "completed": "succeeded",
        "success": "succeeded",
        "error": "failed",
        "timeout": "timed_out",
        "timedout": "timed_out",
        "in_progress": "running",
        "working": "running",
        "delivered": "received",
        "worker_claimed": "accepted",
        "terminal": "succeeded",
        "ignored_redelivery": "cancelled",
        "recovery_action": "accepted",
    }
    normalized = aliases.get(raw, raw)
    if normalized in _ACTIVE_STATUSES | _TERMINAL_STATUSES:
        return normalized
    return "unknown"


def _database_instance() -> str:
    path = database_path()
    try:
        stat = path.stat()
        material = f"{path}:{stat.st_dev}:{stat.st_ino}"
    except OSError:
        material = f"{path}:missing"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _domain_revision(conn: sqlite3.Connection, domain: str) -> int:
    row = conn.execute(
        "SELECT revision FROM domain_revisions WHERE domain = ?", (domain,)
    ).fetchone()
    return int(row["revision"] if row else 0)


def _normalize_changed_ids(values: Iterable[Any] | None) -> tuple[list[str], bool]:
    normalized: list[str] = []
    seen: set[str] = set()
    overflow = False
    for value in values or ():
        item = _safe_text(value, 120)
        if not item or item in seen:
            continue
        seen.add(item)
        if len(normalized) >= _MAX_CHANGED_IDS:
            overflow = True
            break
        normalized.append(item)
    return normalized, overflow


def _revision_reason(value: Any, domain: str) -> str:
    candidate = str(value or "").strip().lower().replace("-", "_")
    if candidate in _REVISION_REASONS:
        return candidate
    default = f"{domain}_state_changed"
    return default if default in _REVISION_REASONS else "domain_state_changed"


def _lifecycle_stage(value: Any, normalized_status: str) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "queued": "accepted",
        "received": "delivered",
        "accepted": "worker_claimed",
        "succeeded": "terminal",
        "cancelled": "terminal",
        "undeliverable": "failed",
    }
    stage = aliases.get(raw, raw)
    if stage in _COMMAND_LIFECYCLE_STAGES:
        return stage
    if normalized_status == "failed":
        return "failed"
    if normalized_status == "timed_out":
        return "timed_out"
    if normalized_status in _TERMINAL_STATUSES:
        return "terminal"
    if normalized_status == "running":
        return "running"
    if normalized_status == "published":
        return "published"
    return "accepted"


def _record_revision_event(
    conn: sqlite3.Connection,
    *,
    domain: str,
    revision: int,
    at: str,
    changed_ids: Iterable[Any] | None = None,
    reason: str = "domain_state_changed",
    projection_version: int = 1,
) -> None:
    if domain not in _REVISION_DOMAINS or revision < 0:
        return
    bounded_ids, overflow = _normalize_changed_ids(changed_ids)
    payload_ids = [] if overflow else bounded_ids
    conn.execute(
        """
        INSERT OR IGNORE INTO lite_revision_events(
            database_instance, domain, revision, changed_ids_json, reason,
            projection_version, occurred_at, occurred_at_epoch_ms, sanitized
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            _database_instance(),
            domain,
            int(revision),
            json.dumps(payload_ids, sort_keys=True, separators=(",", ":")),
            _revision_reason(reason, domain),
            max(1, int(projection_version or 1)),
            at,
            _epoch_ms(at),
        ),
    )
    cutoff = _epoch_ms() - _REVISION_EVENT_RETENTION_MS
    conn.execute(
        "DELETE FROM lite_revision_events WHERE occurred_at_epoch_ms < ?",
        (cutoff,),
    )
    conn.execute(
        "DELETE FROM lite_revision_events WHERE event_id NOT IN "
        "(SELECT event_id FROM lite_revision_events ORDER BY event_id DESC LIMIT ?)",
        (_REVISION_EVENT_RETENTION_COUNT,),
    )


def _bump_revision(
    conn: sqlite3.Connection,
    domain: str,
    at: str,
    *,
    changed_ids: Iterable[Any] | None = None,
    reason: str = "domain_state_changed",
    projection_version: int = 1,
) -> int:
    conn.execute(
        """
        INSERT INTO domain_revisions(domain, revision, updated_at)
        VALUES (?, 1, ?)
        ON CONFLICT(domain) DO UPDATE SET
            revision = domain_revisions.revision + 1,
            updated_at = excluded.updated_at
        """,
        (domain, at),
    )
    revision = _domain_revision(conn, domain)
    _record_revision_event(
        conn,
        domain=domain,
        revision=revision,
        at=at,
        changed_ids=changed_ids,
        reason=reason,
        projection_version=projection_version,
    )
    return revision


def _changes(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT changes()").fetchone()
    return bool(row and int(row[0]) > 0)


def _ui_state(device: dict[str, Any], remote_ready: bool) -> str:
    role = str(device.get("role") or "").lower()
    status = str(device.get("status") or device.get("connection") or "unknown").lower()
    agent = str(device.get("agent_status") or "").lower()
    process = str(device.get("agent_process_status") or "").lower()
    supervisor = str(device.get("supervisor_status") or "").lower()
    if role == "server_host" or device.get("is_current"):
        return "Protected server host"
    if status in {"repairing", "supervisor_repairing"} or supervisor in {"repairing", "restarting"}:
        return "Repairing"
    if status in {"agent_stopped", "stopped"} or process in {"stopped", "errored", "missing"}:
        return "Agent stopped"
    if status in {"joining", "accepted"}:
        return "Joining"
    if status in {"waiting", "pending", "invited", "invite_sent"}:
        return "Waiting"
    if status in {"online", "active", "healthy"}:
        return "Online" if remote_ready else "Remote access not ready"
    return "Offline" if status in {"offline", "stale", "unhealthy"} else "Waiting"


@dataclass(frozen=True)
class PreparedRead:
    payload: dict[str, Any]
    etag: str
    source_revision: int
    projection_age_ms: int
    read_degraded: bool
    refresh_pending: bool
    timing: dict[str, float]


@dataclass
class _PreparedItem:
    payload: dict[str, Any]
    revision: int
    prepared_at: float
    database_instance: str


class PreparedProjectionUnavailable(RuntimeError):
    """A bounded prepared read has no safe snapshot available yet."""


class ControlPlaneProjectionStore:
    """Bounded SQLite projections and single-flight prepared read snapshots."""

    def __init__(self) -> None:
        self._initialized = False
        self._initialized_path = ""
        self._initialize_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._prepared: dict[str, _PreparedItem] = {}
        self._refreshing: set[str] = set()
        self._refresh_errors: dict[str, str] = {}
        self._refresh_started_at: dict[str, float] = {}
        self._last_stage_timings: dict[str, dict[str, float]] = {}
        self._cache_generation = 0
        self._refresh_generation_by_key: dict[str, int] = {}
        self._last_refresh_completed_at: dict[str, float] = {}
        self._last_build_seconds: dict[str, float] = {}
        self._consecutive_refresh_failures: dict[str, int] = {}
        self._next_refresh_allowed_at: dict[str, float] = {}
        self._singleflight_locks: dict[str, threading.Lock] = {}
        default_workers = "1" if ("com.termux" in os.environ.get("PREFIX", "") or sys.platform == "android") else "2"
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(int(os.environ.get("POCKETLAB_LITE_READ_REFRESH_WORKERS", default_workers)), 4)),
            thread_name_prefix="pocketlab-read-refresh",
        )

    def initialize(self) -> None:
        current_path = str(database_path())
        with self._initialize_lock:
            if self._initialized and self._initialized_path == current_path:
                return
            apply_migrations()
            SQLITE_READS.invalidate()
            SQLITE_WRITER.start()
            with self._cache_lock:
                self._prepared.clear()
                self._refreshing.clear()
                self._refresh_errors.clear()
                self._refresh_started_at.clear()
                self._last_stage_timings.clear()
                self._refresh_generation_by_key.clear()
                self._last_refresh_completed_at.clear()
                self._last_build_seconds.clear()
                self._consecutive_refresh_failures.clear()
                self._next_refresh_allowed_at.clear()
                self._cache_generation += 1
            self._initialized = True
            self._initialized_path = current_path

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        SQLITE_READS.close()
        SQLITE_WRITER.shutdown()

    def invalidate_after_database_replacement(self) -> None:
        SQLITE_READS.invalidate()
        with self._cache_lock:
            self._prepared.clear()
            self._refreshing.clear()
            self._refresh_errors.clear()
            self._refresh_started_at.clear()
            self._last_stage_timings.clear()
            self._refresh_generation_by_key.clear()
            self._last_refresh_completed_at.clear()
            self._last_build_seconds.clear()
            self._consecutive_refresh_failures.clear()
            self._next_refresh_allowed_at.clear()
            self._cache_generation += 1

    def invalidate_domain(self, domain: str) -> None:
        prefix = f"{str(domain or '').strip()}:"
        with self._cache_lock:
            for key in [key for key in self._prepared if key.startswith(prefix)]:
                self._prepared.pop(key, None)
                self._refresh_errors.pop(key, None)

    def _read(self, callback: Callable[[sqlite3.Connection], Any]) -> tuple[Any, float, float]:
        entry, wait_ms = SQLITE_READS.acquire(timeout_seconds=1.0)
        started = time.monotonic()
        discard = False
        try:
            result = callback(entry.connection)
            return result, wait_ms, max(0.0, (time.monotonic() - started) * 1000.0)
        except sqlite3.Error:
            discard = True
            raise
        finally:
            SQLITE_READS.release(entry, discard=discard)

    def domain_revision(self, domain: str) -> int:
        self.initialize()
        result, _, _ = self._read(lambda conn: _domain_revision(conn, domain))
        return int(result)

    def database_instance(self) -> str:
        self.initialize()
        return _database_instance()

    def revisions(self) -> dict[str, Any]:
        self.initialize()
        domains = _REVISION_DOMAINS

        def read(conn: sqlite3.Connection) -> dict[str, Any]:
            revisions = {
                str(row["domain"]): {
                    "revision": int(row["revision"]),
                    "updated_at": str(row["updated_at"] or ""),
                }
                for row in conn.execute(
                    "SELECT domain, revision, updated_at FROM domain_revisions WHERE domain IN (%s)"
                    % ",".join("?" for _ in domains),
                    domains,
                )
            }
            event_row = conn.execute(
                "SELECT COALESCE(MIN(event_id), 0) AS oldest_event_id, "
                "COALESCE(MAX(event_id), 0) AS latest_event_id, COUNT(*) AS retained_events "
                "FROM lite_revision_events WHERE database_instance=?",
                (_database_instance(),),
            ).fetchone()
            return {
                "revisions": revisions,
                "oldest_event_id": int(event_row["oldest_event_id"] or 0),
                "latest_event_id": int(event_row["latest_event_id"] or 0),
                "retained_events": int(event_row["retained_events"] or 0),
            }

        state, wait_ms, query_ms = self._read(read)
        compact_prepared = self.prepared_metrics()
        return {
            "database_instance": _database_instance(),
            "revisions": {
                domain: int((state["revisions"].get(domain) or {}).get("revision", 0))
                for domain in domains
            },
            "updated_at_by_domain": {
                domain: str((state["revisions"].get(domain) or {}).get("updated_at", ""))
                for domain in domains
            },
            "event_cursor": {
                "oldest_event_id": state["oldest_event_id"],
                "latest_event_id": state["latest_event_id"],
                "retained_events": state["retained_events"],
            },
            "connection_wait_ms": round(wait_ms, 3),
            "sqlite_query_ms": round(query_ms, 3),
            "updated_at": _utc_now(),
            "projection_version": 1,
            "prepared": {
                "prepared_keys": compact_prepared.get("prepared_keys", []),
                "refreshing": sorted((compact_prepared.get("refreshing") or {}).keys()),
                "cache_generation": int(compact_prepared.get("cache_generation") or 0),
            },
            "sanitized": True,
        }

    def revisions_etag(self, payload: dict[str, Any] | None = None) -> str:
        value = payload or self.revisions()
        material = json.dumps(
            {
                "database_instance": value.get("database_instance"),
                "revisions": value.get("revisions") or {},
                "latest_event_id": (value.get("event_cursor") or {}).get("latest_event_id", 0),
                "projection_version": value.get("projection_version", 1),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
        return f'W/"pl-revisions-{digest}"'

    def revision_event_window(self) -> dict[str, Any]:
        self.initialize()
        instance = _database_instance()

        def read(conn: sqlite3.Connection) -> dict[str, Any]:
            row = conn.execute(
                "SELECT COALESCE(MIN(event_id), 0) AS oldest_event_id, "
                "COALESCE(MAX(event_id), 0) AS latest_event_id, COUNT(*) AS retained_events "
                "FROM lite_revision_events WHERE database_instance=?",
                (instance,),
            ).fetchone()
            return {
                "database_instance": instance,
                "oldest_event_id": int(row["oldest_event_id"] or 0),
                "latest_event_id": int(row["latest_event_id"] or 0),
                "retained_events": int(row["retained_events"] or 0),
            }

        result, _, _ = self._read(read)
        return result

    def revision_events_after(self, event_id: int, *, limit: int = _REVISION_EVENT_PAGE_LIMIT) -> list[dict[str, Any]]:
        self.initialize()
        cursor = max(0, int(event_id or 0))
        bounded_limit = max(1, min(int(limit or _REVISION_EVENT_PAGE_LIMIT), _REVISION_EVENT_PAGE_LIMIT))
        instance = _database_instance()

        def read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT event_id, database_instance, domain, revision, changed_ids_json, reason, "
                "projection_version, occurred_at FROM lite_revision_events "
                "WHERE database_instance=? AND event_id>? ORDER BY event_id ASC LIMIT ?",
                (instance, cursor, bounded_limit),
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                try:
                    changed_ids = json.loads(str(row["changed_ids_json"] or "[]"))
                except json.JSONDecodeError:
                    changed_ids = []
                if not isinstance(changed_ids, list):
                    changed_ids = []
                result.append({
                    "type": "lite.revision.changed",
                    "event_id": int(row["event_id"]),
                    "domain": str(row["domain"]),
                    "revision": int(row["revision"]),
                    "database_instance": str(row["database_instance"]),
                    "changed_ids": [str(item)[:120] for item in changed_ids[:_MAX_CHANGED_IDS]],
                    "reason": _revision_reason(row["reason"], str(row["domain"])),
                    "projection_version": max(1, int(row["projection_version"] or 1)),
                    "occurred_at": str(row["occurred_at"]),
                    "sanitized": True,
                })
            return result

        result, _, _ = self._read(read)
        return result

    def _etag(self, domain: str, key: str, revision: int) -> str:
        return f'W/"pl-{_database_instance()}-{domain}-{key}-{int(revision)}"'

    def revision_etag(self, domain: str, key: str, revision: int | None = None) -> str:
        effective_revision = self.domain_revision(domain) if revision is None else int(revision)
        safe_key = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(key or "read"))[:120]
        return self._etag(str(domain or "control")[:40], safe_key, effective_revision)

    def prepared_payload(self, cache_key: str) -> dict[str, Any] | None:
        """Return the last prepared payload without starting a refresh."""
        instance = _database_instance()
        with self._cache_lock:
            item = self._prepared.get(str(cache_key))
            if item is None or item.database_instance != instance:
                return None
            return dict(item.payload)

    def wait_for_prepared(self, cache_key: str, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while time.monotonic() < deadline:
            if self.prepared_payload(cache_key) is not None:
                return True
            time.sleep(0.05)
        return self.prepared_payload(cache_key) is not None

    def _effective_stale_after_ms(self, cache_key: str, configured_ms: int) -> int:
        if int(configured_ms) <= 0:
            return 0
        with self._cache_lock:
            build_seconds = float(self._last_build_seconds.get(cache_key, 0.0))
        dynamic_ms = int(build_seconds * 5000.0)
        return max(int(configured_ms), 120_000, min(dynamic_ms, 15 * 60 * 1000))

    def _refresh_allowed(self, cache_key: str) -> bool:
        now = time.monotonic()
        with self._cache_lock:
            return now >= float(self._next_refresh_allowed_at.get(cache_key, 0.0))

    def prepared_read(
        self,
        *,
        domain: str,
        key: str,
        builder: Callable[[], dict[str, Any]],
        projector: Callable[[dict[str, Any]], int],
        stale_after_ms: int,
        max_stale_ms: int,
        deadline_seconds: float = 3.0,
        cold_start_async: bool = False,
        fallback_builder: Callable[[], dict[str, Any] | None] | None = None,
    ) -> PreparedRead:
        self.initialize()
        cache_key = f"{domain}:{key}"
        instance = _database_instance()
        now = time.monotonic()
        with self._cache_lock:
            item = self._prepared.get(cache_key)
            if item is not None and item.database_instance != instance:
                self._prepared.pop(cache_key, None)
                item = None
            refreshing = cache_key in self._refreshing
        if item is None:
            if cold_start_async:
                fallback: dict[str, Any] | None = None
                if fallback_builder is not None:
                    try:
                        fallback = fallback_builder()
                    except Exception as exc:
                        _LOGGER.warning(
                            "pocketlab.control_projection.fallback_degraded key=%s error_type=%s",
                            cache_key,
                            type(exc).__name__,
                        )
                self._start_refresh(cache_key, domain, key, builder, projector, deadline_seconds)
                if fallback:
                    revision = self.domain_revision(domain)
                    return PreparedRead(
                        payload=fallback,
                        etag=self._etag(domain, key, revision),
                        source_revision=revision,
                        projection_age_ms=max_stale_ms + 1,
                        read_degraded=True,
                        refresh_pending=True,
                        timing={
                            "connection_acquisition_ms": 0.0,
                            "sqlite_query_ms": 0.0,
                            "projection_build_ms": 0.0,
                            "serialization_ms": 0.0,
                        },
                    )
                raise PreparedProjectionUnavailable(
                    "Prepared projection is warming and no safe snapshot is available yet"
                )
            return self._refresh_now(
                cache_key, domain, key, builder, projector, deadline_seconds, True
            )
        age_ms = int(max(0.0, (now - item.prepared_at) * 1000.0))
        effective_stale_after_ms = self._effective_stale_after_ms(cache_key, stale_after_ms)
        if age_ms <= effective_stale_after_ms:
            return PreparedRead(
                payload=item.payload,
                etag=self._etag(domain, key, item.revision),
                source_revision=item.revision,
                projection_age_ms=age_ms,
                read_degraded=False,
                refresh_pending=False,
                timing={"connection_acquisition_ms": 0.0, "sqlite_query_ms": 0.0, "projection_build_ms": 0.0, "serialization_ms": 0.0},
            )
        effective_max_stale_ms = max(int(max_stale_ms), effective_stale_after_ms * 3)
        if age_ms <= effective_max_stale_ms:
            scheduled = refreshing
            if not refreshing and self._refresh_allowed(cache_key):
                self._start_refresh(cache_key, domain, key, builder, projector, deadline_seconds)
                scheduled = True
            return PreparedRead(
                payload=item.payload,
                etag=self._etag(domain, key, item.revision),
                source_revision=item.revision,
                projection_age_ms=age_ms,
                read_degraded=cache_key in self._refresh_errors,
                refresh_pending=scheduled,
                timing={"connection_acquisition_ms": 0.0, "sqlite_query_ms": 0.0, "projection_build_ms": 0.0, "serialization_ms": 0.0},
            )
        if cold_start_async:
            scheduled = refreshing
            if not refreshing and self._refresh_allowed(cache_key):
                self._start_refresh(cache_key, domain, key, builder, projector, deadline_seconds)
                scheduled = True
            return PreparedRead(
                payload=item.payload,
                etag=self._etag(domain, key, item.revision),
                source_revision=item.revision,
                projection_age_ms=age_ms,
                read_degraded=True,
                refresh_pending=scheduled,
                timing={"connection_acquisition_ms": 0.0, "sqlite_query_ms": 0.0, "projection_build_ms": 0.0, "serialization_ms": 0.0},
            )
        try:
            return self._refresh_now(
                cache_key, domain, key, builder, projector, deadline_seconds, True
            )
        except Exception:
            return PreparedRead(
                payload=item.payload,
                etag=self._etag(domain, key, item.revision),
                source_revision=item.revision,
                projection_age_ms=age_ms,
                read_degraded=True,
                refresh_pending=False,
                timing={"connection_acquisition_ms": 0.0, "sqlite_query_ms": 0.0, "projection_build_ms": 0.0, "serialization_ms": 0.0},
            )

    def warm_prepared_read(
        self,
        *,
        domain: str,
        key: str,
        builder: Callable[[], dict[str, Any]],
        projector: Callable[[dict[str, Any]], int],
        deadline_seconds: float = 3.0,
    ) -> bool:
        self.initialize()
        cache_key = f"{domain}:{key}"
        with self._cache_lock:
            item = self._prepared.get(cache_key)
            if item is not None and item.database_instance == _database_instance():
                return False
        self._start_refresh(cache_key, domain, key, builder, projector, deadline_seconds)
        return True

    def _start_refresh(
        self,
        cache_key: str,
        domain: str,
        key: str,
        builder: Callable[[], dict[str, Any]],
        projector: Callable[[dict[str, Any]], int],
        deadline_seconds: float,
    ) -> None:
        with self._cache_lock:
            now = time.monotonic()
            if cache_key in self._refreshing or now < float(self._next_refresh_allowed_at.get(cache_key, 0.0)):
                return
            self._refreshing.add(cache_key)
            self._refresh_started_at[cache_key] = time.monotonic()
            generation = self._cache_generation
            self._refresh_generation_by_key[cache_key] = generation
        self._executor.submit(
            self._background_refresh,
            cache_key,
            domain,
            key,
            builder,
            projector,
            deadline_seconds,
            generation,
        )

    def _background_refresh(self, *args: Any) -> None:
        cache_key = str(args[0])
        generation = int(args[-1])
        try:
            self._refresh_now(*args[:-1], False, generation)
        except Exception as exc:
            with self._cache_lock:
                if self._refresh_generation_by_key.get(cache_key) == generation:
                    self._refresh_errors[cache_key] = type(exc).__name__
                    failures = min(8, self._consecutive_refresh_failures.get(cache_key, 0) + 1)
                    self._consecutive_refresh_failures[cache_key] = failures
                    backoff = min(300.0, 2.0 ** failures)
                    self._next_refresh_allowed_at[cache_key] = time.monotonic() + backoff
            _LOGGER.warning(
                "pocketlab.control_projection.refresh_degraded key=%s error_type=%s",
                cache_key,
                type(exc).__name__,
            )
        finally:
            with self._cache_lock:
                if self._refresh_generation_by_key.get(cache_key) == generation:
                    self._refreshing.discard(cache_key)
                    self._refresh_started_at.pop(cache_key, None)
                    self._refresh_generation_by_key.pop(cache_key, None)

    def _refresh_now(
        self,
        cache_key: str,
        domain: str,
        key: str,
        builder: Callable[[], dict[str, Any]],
        projector: Callable[[dict[str, Any]], int],
        deadline_seconds: float,
        enforce_deadline: bool,
        expected_generation: int | None = None,
    ) -> PreparedRead:
        request_started = time.monotonic()
        with self._cache_lock:
            lock = self._singleflight_locks.setdefault(cache_key, threading.Lock())
        acquired = lock.acquire(timeout=max(0.05, min(deadline_seconds, 10.0)))
        if not acquired:
            with self._cache_lock:
                cached = self._prepared.get(cache_key)
            if cached is not None:
                return PreparedRead(
                    payload=cached.payload,
                    etag=self._etag(domain, key, cached.revision),
                    source_revision=cached.revision,
                    projection_age_ms=int(max(0.0, (time.monotonic() - cached.prepared_at) * 1000.0)),
                    read_degraded=True,
                    refresh_pending=True,
                    timing={"connection_acquisition_ms": 0.0, "sqlite_query_ms": 0.0, "projection_build_ms": 0.0, "serialization_ms": 0.0},
                )
            raise TimeoutError("Prepared read refresh deadline expired")
        try:
            with self._cache_lock:
                cached = self._prepared.get(cache_key)
            # A concurrent caller may have completed the same cold refresh while
            # this caller waited for the single-flight lock. Share that result.
            if cached is not None and cached.prepared_at >= request_started:
                return PreparedRead(
                    payload=cached.payload,
                    etag=self._etag(domain, key, cached.revision),
                    source_revision=cached.revision,
                    projection_age_ms=int(max(0.0, (time.monotonic() - cached.prepared_at) * 1000.0)),
                    read_degraded=False,
                    refresh_pending=False,
                    timing={"connection_acquisition_ms": 0.0, "sqlite_query_ms": 0.0, "projection_build_ms": 0.0, "serialization_ms": 0.0},
                )
            with self._cache_lock:
                effective_generation = self._cache_generation
            if expected_generation is not None and expected_generation != effective_generation:
                raise PreparedProjectionUnavailable("Projection generation changed before build")
            started = time.monotonic()
            payload = builder()
            built = time.monotonic()
            with self._cache_lock:
                generation_after_build = self._cache_generation
            if expected_generation is not None and expected_generation != generation_after_build:
                raise PreparedProjectionUnavailable("Projection generation changed during build")
            stage_timings = payload.pop("__projection_stage_timing_ms", {}) if isinstance(payload, dict) else {}
            if not isinstance(stage_timings, dict):
                stage_timings = {}
            with self._cache_lock:
                self._last_stage_timings[cache_key] = {
                    str(name)[:80]: round(max(0.0, float(value)), 3)
                    for name, value in list(stage_timings.items())[:24]
                    if isinstance(value, (int, float))
                }
            build_seconds = built - started
            if build_seconds > max(0.05, deadline_seconds):
                _LOGGER.warning(
                    "pocketlab.control_projection.slow_build key=%s duration_ms=%.3f deadline_ms=%.3f stages=%s",
                    cache_key, build_seconds * 1000.0, deadline_seconds * 1000.0,
                    self._last_stage_timings.get(cache_key, {}),
                )
            if enforce_deadline and built - request_started > max(0.05, deadline_seconds):
                raise TimeoutError("Prepared projection build deadline expired")
            revision = projector(payload)
            projected = time.monotonic()
            with self._cache_lock:
                generation_after_projection = self._cache_generation
            if expected_generation is not None and expected_generation != generation_after_projection:
                raise PreparedProjectionUnavailable("Projection generation changed during projection")
            item = _PreparedItem(
                payload=payload,
                revision=revision,
                prepared_at=time.monotonic(),
                database_instance=_database_instance(),
            )
            with self._cache_lock:
                self._prepared[cache_key] = item
                self._refresh_errors.pop(cache_key, None)
                self._last_build_seconds[cache_key] = max(build_seconds, self._last_build_seconds.get(cache_key, 0.0) * 0.75)
                self._last_refresh_completed_at[cache_key] = time.monotonic()
                self._consecutive_refresh_failures[cache_key] = 0
                minimum_interval = max(15.0, min(300.0, build_seconds * 2.0))
                self._next_refresh_allowed_at[cache_key] = time.monotonic() + minimum_interval
            serialization_started = time.monotonic()
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            serialization_ms = max(0.0, (time.monotonic() - serialization_started) * 1000.0)
            return PreparedRead(
                payload=payload,
                etag=self._etag(domain, key, revision),
                source_revision=revision,
                projection_age_ms=0,
                read_degraded=False,
                refresh_pending=False,
                timing={
                    "connection_acquisition_ms": 0.0,
                    "sqlite_query_ms": max(0.0, (projected - built) * 1000.0),
                    "projection_build_ms": max(0.0, (built - started) * 1000.0),
                    "serialization_ms": serialization_ms,
                },
            )
        finally:
            lock.release()
            if expected_generation is None:
                with self._cache_lock:
                    self._refreshing.discard(cache_key)

    @staticmethod
    def _decode_projection_json(value: Any) -> dict[str, Any]:
        try:
            decoded = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}

    def app_current_subprojections(
        self, app_id: str, *, max_age_seconds: float = 900.0
    ) -> dict[str, Any] | None:
        """Return bounded, sanitized App current-state projections for cold reads."""
        self.initialize()
        normalized = _safe_text(app_id, 120)
        if not normalized:
            return None

        def read(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                """
                SELECT catalog_state_json, media_state_json, operation_state_json,
                       update_state_json, backup_profile_json, security_profile_json,
                       backup_targets_json, projection_version, updated_at, updated_at_epoch_ms
                FROM app_current_state WHERE app_id=?
                """,
                (normalized,),
            ).fetchone()
            return dict(row) if row else None

        row, _, _ = self._read(read)
        if not row:
            return None
        age_ms = max(0, _epoch_ms() - int(row.get("updated_at_epoch_ms") or 0))
        if age_ms > max(1.0, float(max_age_seconds)) * 1000.0:
            return None
        payload = {
            "catalog": self._decode_projection_json(row.get("catalog_state_json")),
            "media": self._decode_projection_json(row.get("media_state_json")),
            "operations": self._decode_projection_json(row.get("operation_state_json")),
            "update": self._decode_projection_json(row.get("update_state_json")),
            "backup": self._decode_projection_json(row.get("backup_profile_json")),
            "security": self._decode_projection_json(row.get("security_profile_json")),
            "backup_targets": self._decode_projection_json(row.get("backup_targets_json")),
            "projection_version": int(row.get("projection_version") or 1),
            "projection_age_ms": age_ms,
            "updated_at": row.get("updated_at"),
            "projection_only": True,
        }
        return payload if any(payload.get(key) for key in ("catalog", "media", "operations", "update", "backup", "security", "backup_targets")) else None

    def update_app_subprojections(
        self, app_id: str, projections: dict[str, dict[str, Any]]
    ) -> int:
        """Persist compact App subprojections in one change-only transaction."""
        self.initialize()
        columns = {
            "catalog": ("catalog_state_json", 2048),
            "media": ("media_state_json", 4096),
            "operations": ("operation_state_json", 4096),
            "update": ("update_state_json", 4096),
            "backup": ("backup_profile_json", 4096),
            "security": ("security_profile_json", 2048),
            "backup_targets": ("backup_targets_json", 2048),
        }
        normalized = _safe_text(app_id, 120)
        if not normalized or not isinstance(projections, dict):
            return self.domain_revision("apps")
        encoded: dict[str, tuple[str, str]] = {}
        for name, payload in projections.items():
            column_budget = columns.get(str(name or "").strip().lower())
            if column_budget is None or not isinstance(payload, dict):
                continue
            column, budget = column_budget
            compact = _compact_app_subprojection(str(name), payload)
            encoded[column] = (_safe_json(compact, max_bytes=budget), str(name))
        if not encoded:
            return self.domain_revision("apps")
        now = _utc_now()
        now_epoch = _epoch_ms(now)

        def write(conn: sqlite3.Connection) -> int:
            selected = ", ".join(encoded)
            row = conn.execute(
                f"SELECT {selected} FROM app_current_state WHERE app_id=?",
                (normalized,),
            ).fetchone()
            if not row:
                return _domain_revision(conn, "apps")
            changed = {
                column: value
                for column, (value, _name) in encoded.items()
                if str(row[column] or "{}") != value
            }
            if not changed:
                return _domain_revision(conn, "apps")
            assignments = ", ".join(f"{column}=?" for column in changed)
            conn.execute(
                f"UPDATE app_current_state SET {assignments}, projection_version=2, updated_at=?, updated_at_epoch_ms=? WHERE app_id=?",
                (*changed.values(), now, now_epoch, normalized),
            )
            return _bump_revision(
                conn, "apps", now, changed_ids=[normalized],
                reason="app_subprojection_changed", projection_version=2,
            ) if _changes(conn) else _domain_revision(conn, "apps")

        try:
            return int(SQLITE_WRITER.submit("apps.subprojections", write, deadline_seconds=1.0))
        except (SQLiteWriteRejected, SQLiteWriteDeadlineExceeded):
            return self.domain_revision("apps")

    def update_app_subprojection(
        self, app_id: str, projection: str, payload: dict[str, Any]
    ) -> int:
        return self.update_app_subprojections(app_id, {projection: payload})

    def app_projection_snapshot(self) -> dict[str, Any] | None:
        self.initialize()
        def read(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            return [dict(row) for row in conn.execute(
                "SELECT app_id, app_name, status, installed, health_state, latest_action_id, "
                "latest_action_status, latest_backup_id, updated_at, summary "
                "FROM app_current_state ORDER BY app_name COLLATE NOCASE, app_id"
            )]
        rows, _, _ = self._read(read)
        if not rows:
            return None
        apps = [{
            "app_id": row["app_id"], "id": row["app_id"], "name": row["app_name"],
            "status": row["status"], "installed": bool(row["installed"]),
            "summary": row["summary"] or "Showing the latest saved app state.",
            "security": {"status": row["health_state"] or "unknown"},
            "current_action": ({"action_id": row["latest_action_id"], "status": row["latest_action_status"]}
                               if row["latest_action_id"] else None),
            "backup": {"latest_backup_id": row["latest_backup_id"]},
            "updated_at": row["updated_at"], "projection_only": True,
        } for row in rows]
        return {
            "status": "degraded", "summary": "Showing the latest saved app state while Pocket Lab refreshes details.",
            "apps": apps, "items": apps, "count": len(apps),
            "ready_count": sum(1 for item in apps if item.get("status") == "ready"),
            "attention_count": sum(1 for item in apps if item.get("status") not in {"ready", "healthy"}),
            "updated_at": max(str(item.get("updated_at") or "") for item in apps),
            "projection_only": True,
        }

    def recovery_projection_snapshot(self, *, details: bool = False) -> dict[str, Any] | None:
        self.initialize()
        def read(conn: sqlite3.Connection) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
            state = conn.execute(
                "SELECT status, active_operation_id, latest_backup_id, latest_preview_id, "
                "latest_restore_id, maintenance_status, updated_at, summary "
                "FROM recovery_current_state WHERE singleton_id = 1"
            ).fetchone()
            backup = conn.execute(
                "SELECT backup_id, status, verification_status, created_at, verified_at, size_bytes, summary "
                "FROM backup_manifest_index ORDER BY updated_at_epoch_ms DESC, backup_id DESC LIMIT 1"
            ).fetchone()
            return (dict(state) if state else None, dict(backup) if backup else None)
        state, backup = self._read(read)[0]
        if not state:
            return None
        payload: dict[str, Any] = {
            "status": state.get("status") or "degraded",
            "summary": state.get("summary") or "Showing the latest saved recovery state while Pocket Lab refreshes details.",
            "active_operation": ({"operation_id": state.get("active_operation_id")} if state.get("active_operation_id") else None),
            "latest_restore_preview": ({"preview_id": state.get("latest_preview_id")} if state.get("latest_preview_id") else None),
            "last_restore": ({"restore_id": state.get("latest_restore_id")} if state.get("latest_restore_id") else None),
            "maintenance": {"status": state.get("maintenance_status") or "unknown"},
            "updated_at": state.get("updated_at"),
            "projection_only": True,
        }
        if backup:
            payload["last_backup"] = backup
            payload["latest_backup"] = backup
        if details:
            payload.update({
                "view_model": "recovery-details-r3-v1", "app_backups": [],
                "app_backup_profiles": {"apps": []}, "app_lifecycle_profiles": {"apps": []},
                "backup_targets": [], "backup_target_profiles": {"targets": []},
            })
        return payload

    def prepared_metrics(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._cache_lock:
            return {
                "refreshing": {key: round(max(0.0, now - started), 3) for key, started in self._refresh_started_at.items()},
                "refresh_errors": dict(self._refresh_errors),
                "stage_timings_ms": {key: dict(value) for key, value in self._last_stage_timings.items()},
                "build_duration_ms": {key: round(value * 1000.0, 3) for key, value in self._last_build_seconds.items()},
                "refresh_backoff_seconds": {key: round(max(0.0, at - now), 3) for key, at in self._next_refresh_allowed_at.items() if at > now},
                "refresh_failures": dict(self._consecutive_refresh_failures),
                "prepared_keys": sorted(self._prepared),
                "generation": self._cache_generation,
                "sanitized": True,
            }

    def project_fleet(self, payload: dict[str, Any]) -> int:
        self.initialize()
        devices = [item for item in payload.get("devices", []) if isinstance(item, dict)]
        remote = payload.get("remote_access") if isinstance(payload.get("remote_access"), dict) else {}
        latest_invite = payload.get("latest_invite") if isinstance(payload.get("latest_invite"), dict) else None
        now = str(payload.get("updated_at") or _utc_now())
        now_epoch = _epoch_ms(now)
        commands: list[dict[str, Any]] = []
        recovery_events: list[dict[str, Any]] = []
        try:
            from . import fleet_registry

            commands = fleet_registry.list_commands(limit=500)
            events_payload = deps.core.read_json_file(
                deps.settings().state_dir / "fleet_device_events.json",
                {"events": []},
            )
            recovery_events = [
                item for item in (events_payload.get("events") or [])[:500]
                if isinstance(item, dict)
            ]
        except Exception:
            pass

        def write(conn: sqlite3.Connection) -> int:
            changed = False
            device_ids: list[str] = []
            for item in devices:
                device_id = _safe_text(item.get("id") or item.get("node_id"), 120)
                if not device_id:
                    continue
                device_ids.append(device_id)
                protected = bool(item.get("role") == "server_host" or item.get("is_current"))
                last_seen = str(item.get("last_seen_at") or item.get("last_seen") or now)
                last_seen_epoch = _epoch_ms(last_seen)
                heartbeat_id = hashlib.sha256(
                    f"{device_id}:{last_seen}:{item.get('status')}".encode("utf-8")
                ).hexdigest()[:24]
                connection_state = _safe_text(item.get("connection") or item.get("status") or "unknown", 32).lower()
                agent_status = _safe_text(item.get("agent_status") or item.get("status") or "unknown", 32).lower()
                supervisor_status = _safe_text(item.get("supervisor_status") or "unknown", 32).lower()
                pm2_status = _safe_text(item.get("agent_process_status") or "unknown", 32).lower()
                remote_ready = bool(
                    remote.get("ready")
                    and (
                        protected
                        or item.get("remote_access")
                        or str(item.get("connection") or item.get("status") or "").lower()
                        in {"online", "active", "healthy"}
                    )
                )
                summary = _safe_text(item.get("summary") or item.get("status") or "Device state recorded")
                conn.execute(
                    """
                    INSERT OR IGNORE INTO device_heartbeats(
                        device_id, heartbeat_id, source_revision, connection_state,
                        agent_status, supervisor_status, pm2_status,
                        remote_access_ready, protected_server_host, observed_at,
                        observed_at_epoch_ms, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (device_id, heartbeat_id, int(item.get("revision") or 0), connection_state,
                     agent_status, supervisor_status, pm2_status, int(remote_ready), int(protected),
                     last_seen, last_seen_epoch, summary),
                )
                changed = _changes(conn) or changed
                conn.execute(
                    """
                    INSERT INTO device_identity_guards(
                        identity_key, device_id, normalized_name, protected_server_host,
                        source, updated_at
                    ) VALUES (?, ?, ?, ?, 'fleet-projection', ?)
                    ON CONFLICT(identity_key) DO UPDATE SET
                        device_id=excluded.device_id,
                        normalized_name=excluded.normalized_name,
                        protected_server_host=excluded.protected_server_host,
                        updated_at=excluded.updated_at
                    WHERE device_identity_guards.device_id IS NOT excluded.device_id
                       OR device_identity_guards.normalized_name IS NOT excluded.normalized_name
                       OR device_identity_guards.protected_server_host IS NOT excluded.protected_server_host
                    """,
                    (device_id.lower(), device_id, _safe_text(item.get("name"), 120).lower(), int(protected), now),
                )
                changed = _changes(conn) or changed
                latest_command = next((c for c in commands if str(c.get("node_id") or "") == device_id), None)
                latest_command_id = _safe_text((latest_command or {}).get("command_id"), 120) or None
                latest_invite_id = None
                if latest_invite and _safe_text(latest_invite.get("hostname") or latest_invite.get("node_id"), 120).lower() in {
                    device_id.lower(), _safe_text(item.get("name"), 120).lower()
                }:
                    latest_invite_id = _safe_text(latest_invite.get("invite_id"), 120) or None
                latest_recovery = next((event for event in recovery_events if str(event.get("device_id") or "") == device_id), None)
                latest_recovery_id = None
                if latest_recovery:
                    latest_recovery_id = hashlib.sha256(
                        json.dumps(latest_recovery, sort_keys=True).encode("utf-8")
                    ).hexdigest()[:24]
                ui_state = _ui_state(item, remote_ready)
                conn.execute(
                    """
                    INSERT INTO device_current_state(
                        device_id, device_name, role, ui_state, connection_state,
                        agent_status, supervisor_status, pm2_status, remote_access_ready,
                        protected_server_host, source_heartbeat_id, latest_command_id,
                        latest_invite_id, latest_recovery_id, source_revision,
                        last_seen_at, last_seen_epoch_ms, updated_at, updated_at_epoch_ms, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                        device_name=excluded.device_name, role=excluded.role,
                        ui_state=excluded.ui_state, connection_state=excluded.connection_state,
                        agent_status=excluded.agent_status, supervisor_status=excluded.supervisor_status,
                        pm2_status=excluded.pm2_status, remote_access_ready=excluded.remote_access_ready,
                        protected_server_host=excluded.protected_server_host,
                        source_heartbeat_id=excluded.source_heartbeat_id,
                        latest_command_id=excluded.latest_command_id,
                        latest_invite_id=excluded.latest_invite_id,
                        latest_recovery_id=excluded.latest_recovery_id,
                        source_revision=excluded.source_revision,
                        last_seen_at=excluded.last_seen_at,
                        last_seen_epoch_ms=excluded.last_seen_epoch_ms,
                        updated_at=excluded.updated_at,
                        updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                        summary=excluded.summary
                    WHERE device_current_state.device_name IS NOT excluded.device_name
                       OR device_current_state.role IS NOT excluded.role
                       OR device_current_state.ui_state IS NOT excluded.ui_state
                       OR device_current_state.connection_state IS NOT excluded.connection_state
                       OR device_current_state.agent_status IS NOT excluded.agent_status
                       OR device_current_state.supervisor_status IS NOT excluded.supervisor_status
                       OR device_current_state.pm2_status IS NOT excluded.pm2_status
                       OR device_current_state.remote_access_ready IS NOT excluded.remote_access_ready
                       OR device_current_state.protected_server_host IS NOT excluded.protected_server_host
                       OR device_current_state.source_heartbeat_id IS NOT excluded.source_heartbeat_id
                       OR device_current_state.latest_command_id IS NOT excluded.latest_command_id
                       OR device_current_state.latest_invite_id IS NOT excluded.latest_invite_id
                       OR device_current_state.latest_recovery_id IS NOT excluded.latest_recovery_id
                       OR device_current_state.last_seen_epoch_ms IS NOT excluded.last_seen_epoch_ms
                       OR device_current_state.summary IS NOT excluded.summary
                    """,
                    (device_id, _safe_text(item.get("name") or device_id, 120), _safe_text(item.get("role") or "compute", 40),
                     ui_state, connection_state, agent_status, supervisor_status, pm2_status,
                     int(remote_ready), int(protected), heartbeat_id, latest_command_id,
                     latest_invite_id, latest_recovery_id, int(item.get("revision") or 0),
                     last_seen, last_seen_epoch, now, now_epoch, summary),
                )
                changed = _changes(conn) or changed

            if device_ids:
                placeholders = ",".join("?" for _ in device_ids)
                conn.execute(
                    f"DELETE FROM device_current_state WHERE device_id NOT IN ({placeholders})",
                    tuple(device_ids),
                )
                changed = _changes(conn) or changed
            else:
                conn.execute("DELETE FROM device_current_state")
                changed = _changes(conn) or changed

            if latest_invite:
                invite_id = _safe_text(latest_invite.get("invite_id"), 120)
                if invite_id:
                    invite_updated = str(latest_invite.get("updated_at") or latest_invite.get("created_at") or now)
                    conn.execute(
                        """
                        INSERT INTO device_invite_lifecycle(
                            invite_id, device_id, device_name, role, status, created_at,
                            expires_at, updated_at, updated_at_epoch_ms, source_revision, summary
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                        ON CONFLICT(invite_id) DO UPDATE SET
                            device_id=excluded.device_id, device_name=excluded.device_name,
                            role=excluded.role, status=excluded.status,
                            expires_at=excluded.expires_at, updated_at=excluded.updated_at,
                            updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                            summary=excluded.summary
                        WHERE device_invite_lifecycle.status IS NOT excluded.status
                           OR device_invite_lifecycle.device_id IS NOT excluded.device_id
                           OR device_invite_lifecycle.expires_at IS NOT excluded.expires_at
                        """,
                        (invite_id, _safe_text(latest_invite.get("node_id") or latest_invite.get("hostname"), 120),
                         _safe_text(latest_invite.get("hostname") or latest_invite.get("node_id"), 120),
                         _safe_text(latest_invite.get("role"), 40), _safe_text(latest_invite.get("status") or "pending", 32),
                         latest_invite.get("created_at"), latest_invite.get("expires_at"), invite_updated,
                         _epoch_ms(invite_updated), "Invite lifecycle recorded"),
                    )
                    changed = _changes(conn) or changed

            for command in commands[:500]:
                changed = self._upsert_command_row(conn, command, entity_type="device") or changed

            for event in recovery_events[:500]:
                device_id = _safe_text(event.get("device_id"), 120)
                if not device_id:
                    continue
                created_at = str(event.get("created_at") or event.get("timestamp") or now)
                recovery_id = hashlib.sha256(
                    json.dumps(event, sort_keys=True).encode("utf-8")
                ).hexdigest()[:24]
                conn.execute(
                    """
                    INSERT OR IGNORE INTO device_recovery_history(
                        recovery_id, device_id, action, status, command_id,
                        created_at, created_at_epoch_ms, source_ref, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (recovery_id, device_id, _safe_text(event.get("event_type") or "device_recovery", 80),
                     _safe_text(event.get("status") or "unknown", 32), _safe_text(event.get("command_id"), 120) or None,
                     created_at, _epoch_ms(created_at), "fleet_device_events.json", _safe_text(event.get("summary") or event.get("reason"))),
                )
                changed = _changes(conn) or changed

            conn.execute(
                "DELETE FROM device_heartbeats WHERE heartbeat_row_id NOT IN "
                "(SELECT heartbeat_row_id FROM device_heartbeats ORDER BY observed_at_epoch_ms DESC, heartbeat_row_id DESC LIMIT 4096)"
            )
            changed = _changes(conn) or changed
            conn.execute(
                "DELETE FROM device_recovery_history WHERE recovery_id NOT IN "
                "(SELECT recovery_id FROM device_recovery_history ORDER BY created_at_epoch_ms DESC, recovery_id DESC LIMIT 1000)"
            )
            changed = _changes(conn) or changed
            return _bump_revision(
                conn, "fleet", now, changed_ids=device_ids,
                reason="fleet_state_changed", projection_version=1,
            ) if changed else _domain_revision(conn, "fleet")

        try:
            revision = SQLITE_WRITER.submit("fleet.projection", write, deadline_seconds=3.0)
        except (SQLiteWriteRejected, SQLiteWriteDeadlineExceeded):
            return self.domain_revision("fleet")
        return int(revision)

    def _upsert_command_row(
        self, conn: sqlite3.Connection, command: dict[str, Any], *, entity_type: str
    ) -> bool:
        command_id = _safe_text(command.get("command_id") or command.get("job_id"), 120)
        if not command_id:
            return False
        created_at = str(command.get("created_at") or command.get("queued_at") or _utc_now())
        updated_at = str(command.get("updated_at") or command.get("finished_at") or created_at)
        raw_status = command.get("status")
        status = _normalize_status(raw_status)
        lifecycle_stage = _lifecycle_stage(raw_status, status)
        terminal_at = updated_at if status in _TERMINAL_STATUSES else None
        ignored_redelivery = int(lifecycle_stage == "ignored_redelivery")
        recovery_action = _safe_text(command.get("recovery_action"), 80) if lifecycle_stage == "recovery_action" else ""
        entity_id = _safe_text(command.get("node_id") or command.get("app_id") or command.get("entity_id") or "control-plane", 120)
        operation_type = _safe_text(command.get("command") or command.get("action_id") or command.get("operation_type"), 100)
        conn.execute(
            """
            INSERT INTO command_lifecycle(
                command_id, entity_type, entity_id, operation_type, status,
                created_at, updated_at, updated_at_epoch_ms, deadline_at,
                source_ref, summary, metadata_json, lifecycle_stage, terminal_at,
                ignored_redelivery, recovery_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(command_id) DO UPDATE SET
                status=CASE
                    WHEN excluded.lifecycle_stage IN ('ignored_redelivery','recovery_action')
                    THEN command_lifecycle.status
                    ELSE excluded.status
                END,
                updated_at=excluded.updated_at,
                updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                deadline_at=excluded.deadline_at, summary=excluded.summary,
                metadata_json=excluded.metadata_json,
                lifecycle_stage=CASE
                    WHEN excluded.lifecycle_stage = 'ignored_redelivery'
                    THEN command_lifecycle.lifecycle_stage
                    ELSE excluded.lifecycle_stage
                END,
                terminal_at=COALESCE(command_lifecycle.terminal_at, excluded.terminal_at),
                ignored_redelivery=MAX(command_lifecycle.ignored_redelivery, excluded.ignored_redelivery),
                recovery_action=CASE
                    WHEN excluded.recovery_action != '' THEN excluded.recovery_action
                    ELSE command_lifecycle.recovery_action
                END
            WHERE (excluded.lifecycle_stage IN ('ignored_redelivery','recovery_action')
                   OR command_lifecycle.status NOT IN ('succeeded','failed','cancelled','undeliverable','timed_out')
                   OR command_lifecycle.status = excluded.status)
              AND (excluded.lifecycle_stage IN ('ignored_redelivery','recovery_action')
                   OR command_lifecycle.status IS NOT excluded.status
                   OR command_lifecycle.lifecycle_stage IS NOT excluded.lifecycle_stage
                   OR command_lifecycle.updated_at_epoch_ms < excluded.updated_at_epoch_ms
                   OR command_lifecycle.summary IS NOT excluded.summary
                   OR command_lifecycle.ignored_redelivery < excluded.ignored_redelivery
                   OR command_lifecycle.recovery_action IS NOT excluded.recovery_action)
            """,
            (command_id, entity_type, entity_id, operation_type, status, created_at,
             updated_at, _epoch_ms(updated_at), command.get("deadline_at"),
             _safe_text(command.get("source_ref") or "command-lifecycle", 160),
             _safe_text(command.get("summary") or command.get("error") or status),
             _safe_json({"requested_by": command.get("requested_by"), "result_status": (command.get("result") or {}).get("status") if isinstance(command.get("result"), dict) else None}),
             lifecycle_stage, terminal_at, ignored_redelivery, recovery_action),
        )
        return _changes(conn)

    def record_command(
        self,
        *,
        command_id: str,
        subject: str,
        status: str,
        entity_type: str = "control",
        entity_id: str = "control-plane",
        summary: str = "",
        deadline_at: str | None = None,
        recovery_action: str = "",
    ) -> None:
        self.initialize()
        now = _utc_now()
        command = {
            "command_id": command_id,
            "entity_id": entity_id,
            "operation_type": subject,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "deadline_at": deadline_at,
            "summary": summary or status,
            "source_ref": "FastAPI/NATS",
            "recovery_action": recovery_action,
        }

        def write(conn: sqlite3.Connection) -> int:
            changed = self._upsert_command_row(conn, command, entity_type=entity_type)
            normalized_status = _normalize_status(status)
            conn.execute(
                """
                INSERT OR IGNORE INTO audit_evidence_index(
                    event_type, entity_type, entity_id, operation_id, status,
                    evidence_ref, created_at, created_at_epoch_ms, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"command.{normalized_status}",
                    _safe_text(entity_type, 40),
                    _safe_text(entity_id, 120),
                    _safe_text(command_id, 120),
                    normalized_status,
                    "FastAPI/NATS",
                    now,
                    _epoch_ms(now),
                    _safe_text(summary or f"Command {normalized_status}."),
                ),
            )
            audit_changed = _changes(conn)
            conn.execute(
                "DELETE FROM audit_evidence_index WHERE evidence_index_id NOT IN "
                "(SELECT evidence_index_id FROM audit_evidence_index "
                "ORDER BY created_at_epoch_ms DESC, evidence_index_id DESC LIMIT 5000)"
            )
            audit_changed = _changes(conn) or audit_changed
            if audit_changed:
                _bump_revision(
                    conn, "audit", now, changed_ids=[command_id],
                    reason="audit_state_changed", projection_version=1,
                )
            return (
                _bump_revision(
                    conn, "commands", now, changed_ids=[command_id],
                    reason="command_state_changed", projection_version=1,
                )
                if changed
                else _domain_revision(conn, "commands")
            )

        try:
            SQLITE_WRITER.submit("commands.lifecycle", write, deadline_seconds=0.5)
        except Exception:
            return

    def project_apps(self, payload: dict[str, Any]) -> int:
        self.initialize()
        apps = [item for item in (payload.get("apps") or payload.get("items") or []) if isinstance(item, dict)]
        now = str(payload.get("updated_at") or _utc_now())
        now_epoch = _epoch_ms(now)

        def write(conn: sqlite3.Connection) -> int:
            changed = False
            app_ids: list[str] = []
            for app in apps:
                app_id = _safe_text(app.get("app_id") or app.get("id"), 120)
                if not app_id:
                    continue
                app_ids.append(app_id)
                actions = app.get("actions") if isinstance(app.get("actions"), dict) else {}
                current = app.get("current_action") if isinstance(app.get("current_action"), dict) else {}
                latest_action_id = _safe_text(current.get("action_id"), 120) or None
                latest_action_status = _normalize_status(current.get("status")) if current else None
                backup = app.get("backup") if isinstance(app.get("backup"), dict) else {}
                latest_backup_id = _safe_text(backup.get("latest_backup_id"), 120) or None
                conn.execute(
                    """
                    INSERT INTO app_current_state(
                        app_id, app_name, status, installed, health_state,
                        latest_action_id, latest_action_status, latest_backup_id,
                        source_revision, updated_at, updated_at_epoch_ms, summary,
                        catalog_state_json, media_state_json, operation_state_json,
                        update_state_json, backup_profile_json, security_profile_json,
                        backup_targets_json, projection_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(app_id) DO UPDATE SET
                        app_name=excluded.app_name, status=excluded.status,
                        installed=excluded.installed, health_state=excluded.health_state,
                        latest_action_id=excluded.latest_action_id,
                        latest_action_status=excluded.latest_action_status,
                        latest_backup_id=excluded.latest_backup_id,
                        catalog_state_json=excluded.catalog_state_json,
                        media_state_json=excluded.media_state_json,
                        operation_state_json=excluded.operation_state_json,
                        update_state_json=excluded.update_state_json,
                        backup_profile_json=excluded.backup_profile_json,
                        security_profile_json=excluded.security_profile_json,
                        backup_targets_json=excluded.backup_targets_json,
                        projection_version=excluded.projection_version,
                        updated_at=excluded.updated_at,
                        updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                        summary=excluded.summary
                    WHERE app_current_state.app_name IS NOT excluded.app_name
                       OR app_current_state.status IS NOT excluded.status
                       OR app_current_state.installed IS NOT excluded.installed
                       OR app_current_state.health_state IS NOT excluded.health_state
                       OR app_current_state.latest_action_id IS NOT excluded.latest_action_id
                       OR app_current_state.latest_action_status IS NOT excluded.latest_action_status
                       OR app_current_state.latest_backup_id IS NOT excluded.latest_backup_id
                       OR app_current_state.catalog_state_json IS NOT excluded.catalog_state_json
                       OR app_current_state.media_state_json IS NOT excluded.media_state_json
                       OR app_current_state.operation_state_json IS NOT excluded.operation_state_json
                       OR app_current_state.update_state_json IS NOT excluded.update_state_json
                       OR app_current_state.backup_profile_json IS NOT excluded.backup_profile_json
                       OR app_current_state.security_profile_json IS NOT excluded.security_profile_json
                       OR app_current_state.backup_targets_json IS NOT excluded.backup_targets_json
                       OR app_current_state.summary IS NOT excluded.summary
                    """,
                    (app_id, _safe_text(app.get("name") or app_id, 120), _safe_text(app.get("status") or "unknown", 32),
                     int(bool(app.get("installed"))), _safe_text((app.get("security") or {}).get("status") if isinstance(app.get("security"), dict) else app.get("status"), 32),
                     latest_action_id, latest_action_status, latest_backup_id, int(app.get("revision") or 0),
                     now, now_epoch, _safe_text(app.get("summary")),
                     _safe_json(_compact_app_subprojection("catalog", {
                         "id": app_id, "name": app.get("name"), "status": app.get("status"),
                         "installed": bool(app.get("installed")), "host_device_id": (app.get("host_device") or {}).get("id") if isinstance(app.get("host_device"), dict) else None,
                         "host_device_name": (app.get("host_device") or {}).get("name") if isinstance(app.get("host_device"), dict) else None,
                         "access": {"open_url": "/apps/photoprism/"} if bool((actions.get("open") or {}).get("enabled")) else {},
                         "runtime": {"url": "/apps/photoprism/"} if bool((actions.get("open") or {}).get("enabled")) else {},
                         "actions": {"open": bool((actions.get("open") or {}).get("enabled"))},
                     }), max_bytes=2048),
                     _safe_json(_compact_app_subprojection("media", app.get("media")), max_bytes=4096),
                     _safe_json(_compact_app_subprojection("operations", app.get("operations")), max_bytes=4096),
                     _safe_json(_compact_app_subprojection("update", app.get("update")), max_bytes=4096),
                     _safe_json(_compact_app_subprojection("backup", {"kind": "profile", "backup": app.get("backup"), "recovery": app.get("recovery")}), max_bytes=4096),
                     _safe_json(_compact_app_subprojection("security", {"kind": "profile", "security": app.get("security")}), max_bytes=2048),
                     _safe_json(_compact_app_subprojection("backup_targets", app.get("backup_targets")), max_bytes=2048),
                     2),
                )
                changed = _changes(conn) or changed
                for action_id, action in list(actions.items())[:64]:
                    if not isinstance(action, dict):
                        continue
                    action_updated = str(action.get("last_ran_at") or action.get("updated_at") or now)
                    operation_id = _safe_text(action.get("operation_id") or action.get("receipt_id"), 120)
                    if not operation_id:
                        operation_id = hashlib.sha256(
                            f"{app_id}:{action_id}:{action_updated}:{action.get('status')}".encode("utf-8")
                        ).hexdigest()[:24]
                    conn.execute(
                        """
                        INSERT INTO app_action_lifecycle(
                            operation_id, app_id, action_id, status, created_at,
                            updated_at, updated_at_epoch_ms, source_ref, summary, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(operation_id) DO UPDATE SET
                            status=excluded.status, updated_at=excluded.updated_at,
                            updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                            summary=excluded.summary, metadata_json=excluded.metadata_json
                        WHERE app_action_lifecycle.status IS NOT excluded.status
                           OR app_action_lifecycle.updated_at_epoch_ms < excluded.updated_at_epoch_ms
                           OR app_action_lifecycle.summary IS NOT excluded.summary
                        """,
                        (operation_id, app_id, _safe_text(action_id, 100), _normalize_status(action.get("status")),
                         str(action.get("first_ran_at") or action_updated), action_updated, _epoch_ms(action_updated),
                         _safe_text(action.get("evidence_ref") or "app-lifecycle", 160),
                         _safe_text(action.get("last_result") or action.get("summary") or action.get("disabled_reason")),
                         _safe_json({"enabled": bool(action.get("enabled")), "category": action.get("category"), "risk": action.get("risk")})),
                    )
                    changed = _changes(conn) or changed
            if app_ids:
                placeholders = ",".join("?" for _ in app_ids)
                conn.execute(
                    f"DELETE FROM app_current_state WHERE app_id NOT IN ({placeholders})",
                    tuple(app_ids),
                )
                changed = _changes(conn) or changed
            conn.execute(
                "DELETE FROM app_action_lifecycle WHERE operation_id NOT IN "
                "(SELECT operation_id FROM app_action_lifecycle ORDER BY updated_at_epoch_ms DESC, operation_id DESC LIMIT 2000)"
            )
            changed = _changes(conn) or changed
            return _bump_revision(
                conn, "apps", now, changed_ids=app_ids,
                reason="apps_state_changed", projection_version=2,
            ) if changed else _domain_revision(conn, "apps")

        try:
            return int(SQLITE_WRITER.submit("apps.projection", write, deadline_seconds=3.0))
        except (SQLiteWriteRejected, SQLiteWriteDeadlineExceeded):
            return self.domain_revision("apps")

    def project_recovery(self, payload: dict[str, Any]) -> int:
        self.initialize()
        now = str(payload.get("updated_at") or payload.get("last_checked_at") or _utc_now())
        now_epoch = _epoch_ms(now)
        latest_backup = payload.get("last_backup") if isinstance(payload.get("last_backup"), dict) else payload.get("latest_backup") if isinstance(payload.get("latest_backup"), dict) else {}
        preview = payload.get("latest_restore_preview") if isinstance(payload.get("latest_restore_preview"), dict) else {}
        restore = payload.get("last_restore") if isinstance(payload.get("last_restore"), dict) else {}
        maintenance = payload.get("maintenance") if isinstance(payload.get("maintenance"), dict) else {}
        db_protection = payload.get("database_protection") if isinstance(payload.get("database_protection"), dict) else {}
        active = payload.get("active_operation") if isinstance(payload.get("active_operation"), dict) else db_protection.get("active_restore") if isinstance(db_protection.get("active_restore"), dict) else {}

        def write(conn: sqlite3.Connection) -> int:
            changed = False
            backup_id = _safe_text(latest_backup.get("backup_id") or latest_backup.get("id"), 120)
            if backup_id:
                backup_updated = str(latest_backup.get("verified_at") or latest_backup.get("created_at") or now)
                conn.execute(
                    """
                    INSERT INTO backup_manifest_index(
                        backup_id, backup_type, status, verification_status,
                        created_at, verified_at, size_bytes, source_ref,
                        updated_at, updated_at_epoch_ms, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(backup_id) DO UPDATE SET
                        status=excluded.status,
                        verification_status=excluded.verification_status,
                        verified_at=excluded.verified_at,
                        size_bytes=excluded.size_bytes,
                        updated_at=excluded.updated_at,
                        updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                        summary=excluded.summary
                    WHERE backup_manifest_index.status IS NOT excluded.status
                       OR backup_manifest_index.verification_status IS NOT excluded.verification_status
                       OR backup_manifest_index.verified_at IS NOT excluded.verified_at
                       OR backup_manifest_index.size_bytes IS NOT excluded.size_bytes
                       OR backup_manifest_index.summary IS NOT excluded.summary
                    """,
                    (backup_id, _safe_text(latest_backup.get("backup_type") or "lite", 40),
                     _safe_text(latest_backup.get("status") or "unknown", 32),
                     _safe_text(latest_backup.get("verification_status") or "unknown", 32),
                     latest_backup.get("created_at"), latest_backup.get("verified_at"), int(latest_backup.get("size_bytes") or 0),
                     _safe_text(latest_backup.get("manifest") or "backup-manifest", 160), backup_updated,
                     _epoch_ms(backup_updated), _safe_text(latest_backup.get("summary"))),
                )
                changed = _changes(conn) or changed

            operations: list[tuple[str, str, dict[str, Any]]] = []
            for operation_type, item in (("active", active), ("restore_preview", preview), ("restore", restore)):
                if item:
                    operation_id = _safe_text(item.get("operation_id") or item.get("restore_id") or item.get("preview_id") or item.get("command_id"), 120)
                    if operation_id:
                        operations.append((operation_type, operation_id, item))
            for operation_type, operation_id, item in operations:
                operation_updated = str(item.get("updated_at") or item.get("completed_at") or item.get("created_at") or now)
                conn.execute(
                    """
                    INSERT INTO recovery_operations(
                        operation_id, operation_type, status, backup_id, preview_id,
                        created_at, updated_at, updated_at_epoch_ms, source_ref,
                        summary, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(operation_id) DO UPDATE SET
                        status=excluded.status, updated_at=excluded.updated_at,
                        updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                        summary=excluded.summary, metadata_json=excluded.metadata_json
                    WHERE recovery_operations.status IS NOT excluded.status
                       OR recovery_operations.updated_at_epoch_ms < excluded.updated_at_epoch_ms
                       OR recovery_operations.summary IS NOT excluded.summary
                    """,
                    (operation_id, operation_type, _normalize_status(item.get("status") or item.get("state") or item.get("phase")),
                     _safe_text(item.get("backup_id"), 120) or None, _safe_text(item.get("preview_id"), 120) or None,
                     str(item.get("created_at") or operation_updated), operation_updated, _epoch_ms(operation_updated),
                     "recovery-projection", _safe_text(item.get("summary")),
                     _safe_json({"phase": item.get("phase"), "rollback_available": item.get("rollback_available"), "verification_status": item.get("verification_status")})),
                )
                changed = _changes(conn) or changed

            active_id = operations[0][1] if operations and operations[0][0] == "active" else None
            maintenance_status = _safe_text(maintenance.get("status") or ("active" if maintenance.get("active") else "idle"), 32)
            conn.execute(
                """
                INSERT INTO recovery_current_state(
                    singleton_id, status, active_operation_id, latest_backup_id,
                    latest_preview_id, latest_restore_id, maintenance_status,
                    source_revision, updated_at, updated_at_epoch_ms, summary
                ) VALUES (1, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT(singleton_id) DO UPDATE SET
                    status=excluded.status,
                    active_operation_id=excluded.active_operation_id,
                    latest_backup_id=excluded.latest_backup_id,
                    latest_preview_id=excluded.latest_preview_id,
                    latest_restore_id=excluded.latest_restore_id,
                    maintenance_status=excluded.maintenance_status,
                    updated_at=excluded.updated_at,
                    updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                    summary=excluded.summary
                WHERE recovery_current_state.status IS NOT excluded.status
                   OR recovery_current_state.active_operation_id IS NOT excluded.active_operation_id
                   OR recovery_current_state.latest_backup_id IS NOT excluded.latest_backup_id
                   OR recovery_current_state.latest_preview_id IS NOT excluded.latest_preview_id
                   OR recovery_current_state.latest_restore_id IS NOT excluded.latest_restore_id
                   OR recovery_current_state.maintenance_status IS NOT excluded.maintenance_status
                   OR recovery_current_state.summary IS NOT excluded.summary
                """,
                (_safe_text(payload.get("status") or "unknown", 32), active_id, backup_id or None,
                 _safe_text(preview.get("preview_id"), 120) or None, _safe_text(restore.get("restore_id"), 120) or None,
                 maintenance_status, now, now_epoch, _safe_text(payload.get("summary"))),
            )
            changed = _changes(conn) or changed
            conn.execute(
                "DELETE FROM recovery_operations WHERE operation_id NOT IN "
                "(SELECT operation_id FROM recovery_operations ORDER BY updated_at_epoch_ms DESC, operation_id DESC LIMIT 1000)"
            )
            changed = _changes(conn) or changed
            return _bump_revision(
                conn, "recovery", now,
                changed_ids=[active_id, backup_id, _safe_text(preview.get("preview_id"), 120), _safe_text(restore.get("restore_id"), 120)],
                reason="recovery_state_changed", projection_version=1,
            ) if changed else _domain_revision(conn, "recovery")

        try:
            return int(SQLITE_WRITER.submit("recovery.projection", write, deadline_seconds=3.0))
        except (SQLiteWriteRejected, SQLiteWriteDeadlineExceeded):
            return self.domain_revision("recovery")

    @staticmethod
    def _history_result(
        rows: list[sqlite3.Row],
        *,
        limit: int,
        epoch_key: str,
        id_key: str,
        revision: int,
        wait_ms: float,
        query_ms: float,
    ) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit), 100))
        has_more = len(rows) > bounded_limit
        visible = rows[:bounded_limit]
        items = [dict(row) for row in visible]
        next_cursor = (
            _encode_cursor(int(visible[-1][epoch_key]), str(visible[-1][id_key]))
            if has_more and visible
            else None
        )
        for item in items:
            metadata_json = item.pop("metadata_json", None)
            if metadata_json:
                try:
                    item["metadata"] = json.loads(str(metadata_json))
                except (TypeError, ValueError, json.JSONDecodeError):
                    item["metadata"] = {}
        return {
            "items": items,
            "count": len(items),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "source_revision": int(revision),
            "connection_wait_ms": round(wait_ms, 3),
            "sqlite_query_ms": round(query_ms, 3),
        }

    def app_action_history(
        self, app_id: str, *, limit: int = 20, cursor: str = ""
    ) -> dict[str, Any]:
        self.initialize()
        normalized_app = _safe_text(app_id, 120)
        if not normalized_app:
            raise ValueError("app_id is required")
        bounded_limit = max(1, min(int(limit), 100))
        decoded = _decode_cursor(cursor)

        def read(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            params: list[Any] = [normalized_app]
            cursor_clause = ""
            if decoded is not None:
                cursor_clause = (
                    " AND (updated_at_epoch_ms < ? OR "
                    "(updated_at_epoch_ms = ? AND operation_id < ?))"
                )
                params.extend([decoded[0], decoded[0], decoded[1]])
            params.append(bounded_limit + 1)
            return list(
                conn.execute(
                    "SELECT operation_id,app_id,action_id,status,created_at,updated_at,"
                    "updated_at_epoch_ms,source_ref,summary,metadata_json "
                    "FROM app_action_lifecycle WHERE app_id=?"
                    + cursor_clause
                    + " ORDER BY updated_at_epoch_ms DESC, operation_id DESC LIMIT ?",
                    tuple(params),
                )
            )

        rows, wait_ms, query_ms = self._read(read)
        return self._history_result(
            rows, limit=bounded_limit, epoch_key="updated_at_epoch_ms",
            id_key="operation_id", revision=self.domain_revision("apps"),
            wait_ms=wait_ms, query_ms=query_ms,
        )

    def device_recovery_history(
        self, device_id: str, *, limit: int = 20, cursor: str = ""
    ) -> dict[str, Any]:
        self.initialize()
        normalized_device = _safe_text(device_id, 120)
        if not normalized_device:
            raise ValueError("device_id is required")
        bounded_limit = max(1, min(int(limit), 100))
        decoded = _decode_cursor(cursor)

        def read(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            params: list[Any] = [normalized_device]
            cursor_clause = ""
            if decoded is not None:
                cursor_clause = (
                    " AND (created_at_epoch_ms < ? OR "
                    "(created_at_epoch_ms = ? AND recovery_id < ?))"
                )
                params.extend([decoded[0], decoded[0], decoded[1]])
            params.append(bounded_limit + 1)
            return list(
                conn.execute(
                    "SELECT recovery_id,device_id,action,status,command_id,created_at,"
                    "created_at_epoch_ms,source_ref,summary "
                    "FROM device_recovery_history WHERE device_id=?"
                    + cursor_clause
                    + " ORDER BY created_at_epoch_ms DESC, recovery_id DESC LIMIT ?",
                    tuple(params),
                )
            )

        rows, wait_ms, query_ms = self._read(read)
        return self._history_result(
            rows, limit=bounded_limit, epoch_key="created_at_epoch_ms",
            id_key="recovery_id", revision=self.domain_revision("fleet"),
            wait_ms=wait_ms, query_ms=query_ms,
        )

    def command_history(
        self, *, entity_type: str = "", entity_id: str = "", limit: int = 20, cursor: str = ""
    ) -> dict[str, Any]:
        self.initialize()
        bounded_limit = max(1, min(int(limit), 100))
        decoded = _decode_cursor(cursor)
        safe_type = _safe_text(entity_type, 40)
        safe_id = _safe_text(entity_id, 120)

        def read(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            clauses: list[str] = []
            params: list[Any] = []
            if safe_type:
                clauses.append("entity_type=?")
                params.append(safe_type)
            if safe_id:
                clauses.append("entity_id=?")
                params.append(safe_id)
            if decoded is not None:
                clauses.append(
                    "(updated_at_epoch_ms < ? OR "
                    "(updated_at_epoch_ms = ? AND command_id < ?))"
                )
                params.extend([decoded[0], decoded[0], decoded[1]])
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            params.append(bounded_limit + 1)
            return list(
                conn.execute(
                    "SELECT command_id,entity_type,entity_id,operation_type,status,"
                    "created_at,updated_at,updated_at_epoch_ms,deadline_at,source_ref,"
                    "summary,metadata_json FROM command_lifecycle"
                    + where
                    + " ORDER BY updated_at_epoch_ms DESC, command_id DESC LIMIT ?",
                    tuple(params),
                )
            )

        rows, wait_ms, query_ms = self._read(read)
        return self._history_result(
            rows, limit=bounded_limit, epoch_key="updated_at_epoch_ms",
            id_key="command_id", revision=self.domain_revision("commands"),
            wait_ms=wait_ms, query_ms=query_ms,
        )

    def recovery_operation_history(
        self, *, limit: int = 20, cursor: str = ""
    ) -> dict[str, Any]:
        self.initialize()
        bounded_limit = max(1, min(int(limit), 100))
        decoded = _decode_cursor(cursor)

        def read(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            params: list[Any] = []
            cursor_clause = ""
            if decoded is not None:
                cursor_clause = (
                    " WHERE (updated_at_epoch_ms < ? OR "
                    "(updated_at_epoch_ms = ? AND operation_id < ?))"
                )
                params.extend([decoded[0], decoded[0], decoded[1]])
            params.append(bounded_limit + 1)
            return list(
                conn.execute(
                    "SELECT operation_id,operation_type,status,backup_id,preview_id,"
                    "created_at,updated_at,updated_at_epoch_ms,source_ref,summary,metadata_json "
                    "FROM recovery_operations"
                    + cursor_clause
                    + " ORDER BY updated_at_epoch_ms DESC, operation_id DESC LIMIT ?",
                    tuple(params),
                )
            )

        rows, wait_ms, query_ms = self._read(read)
        return self._history_result(
            rows, limit=bounded_limit, epoch_key="updated_at_epoch_ms",
            id_key="operation_id", revision=self.domain_revision("recovery"),
            wait_ms=wait_ms, query_ms=query_ms,
        )

    def fleet_rows(self) -> list[dict[str, Any]]:
        self.initialize()
        rows, _, _ = self._read(
            lambda conn: [dict(row) for row in conn.execute(
                "SELECT * FROM device_current_state "
                "ORDER BY protected_server_host DESC, device_name, device_id"
            )]
        )
        return rows

    def query_plan_evidence(self) -> dict[str, list[str]]:
        self.initialize()
        queries: dict[str, tuple[str, tuple[Any, ...]]] = {
            "latest_heartbeat": (
                "SELECT heartbeat_id FROM device_heartbeats WHERE device_id=? ORDER BY observed_at_epoch_ms DESC, heartbeat_row_id DESC LIMIT 1",
                ("device-1",),
            ),
            "fleet_summary_order": (
                "SELECT device_id FROM device_current_state ORDER BY protected_server_host DESC, device_name, device_id LIMIT 100",
                (),
            ),
            "active_command": (
                "SELECT command_id FROM command_lifecycle INDEXED BY idx_commands_entity_active_latest WHERE entity_type=? AND entity_id=? AND status IN ('queued','published','received','accepted','running') ORDER BY updated_at_epoch_ms DESC, command_id DESC LIMIT 1",
                ("device", "device-1"),
            ),
            "latest_supervisor": (
                "SELECT supervisor_status FROM device_heartbeats WHERE device_id=? ORDER BY observed_at_epoch_ms DESC, heartbeat_row_id DESC LIMIT 1",
                ("device-1",),
            ),
            "stale_devices": (
                "SELECT device_id FROM device_current_state INDEXED BY idx_device_current_stale_order WHERE connection_state IN ('offline','stale') AND last_seen_epoch_ms < ? ORDER BY last_seen_epoch_ms, device_id LIMIT 100",
                (_epoch_ms() - 120000,),
            ),
            "invite_lookup": (
                "SELECT invite_id FROM device_invite_lifecycle WHERE device_id=? AND status IN ('pending','accepted','joining') ORDER BY updated_at_epoch_ms DESC LIMIT 1",
                ("device-1",),
            ),
            "device_recovery_history": (
                "SELECT recovery_id FROM device_recovery_history WHERE device_id=? ORDER BY created_at_epoch_ms DESC, recovery_id DESC LIMIT 20",
                ("device-1",),
            ),
            "app_action_history": (
                "SELECT operation_id FROM app_action_lifecycle WHERE app_id=? ORDER BY updated_at_epoch_ms DESC, operation_id DESC LIMIT 20",
                ("photoprism",),
            ),
            "command_history": (
                "SELECT command_id FROM command_lifecycle WHERE entity_type=? AND entity_id=? ORDER BY updated_at_epoch_ms DESC, command_id DESC LIMIT 20",
                ("device", "device-1"),
            ),
            "recovery_operation_history": (
                "SELECT operation_id FROM recovery_operations ORDER BY updated_at_epoch_ms DESC, operation_id DESC LIMIT 20",
                (),
            ),
            "backup_manifest_history": (
                "SELECT backup_id FROM backup_manifest_index ORDER BY updated_at_epoch_ms DESC, backup_id DESC LIMIT 20",
                (),
            ),
            "revision_event_replay": (
                "SELECT event_id FROM lite_revision_events WHERE database_instance=? AND event_id>? ORDER BY event_id ASC LIMIT 100",
                (_database_instance(), 0),
            ),
            "command_lifecycle_stage": (
                "SELECT command_id FROM command_lifecycle WHERE lifecycle_stage=? ORDER BY updated_at_epoch_ms DESC, command_id DESC LIMIT 20",
                ("running",),
            ),
        }

        def collect(conn: sqlite3.Connection) -> dict[str, list[str]]:
            return {
                name: [
                    str(row[3])
                    for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params)
                ]
                for name, (sql, params) in queries.items()
            }

        plans, _, _ = self._read(collect)
        return plans

    def metrics(self) -> dict[str, Any]:
        return {"writer": SQLITE_WRITER.snapshot(), "reads": SQLITE_READS.snapshot(), "prepared": self.prepared_metrics()}


CONTROL_PLANE = ControlPlaneProjectionStore()


def invalidate_control_plane_after_database_replacement() -> None:
    CONTROL_PLANE.invalidate_after_database_replacement()
