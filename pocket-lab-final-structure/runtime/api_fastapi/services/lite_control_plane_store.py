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
    "device_enrollment_changed",
    "device_identity_changed",
    "device_staleness_changed",
    "device_capabilities_changed",
    "device_dependencies_changed",
    "device_command_delivery_changed",
    "device_recovery_changed",
    "device_removal_assessment_changed",
    "device_health_changed",
    "device_attention_changed",
    "device_connection_quality_changed",
    "device_resource_pressure_changed",
    "device_recovery_pattern_changed",
    "device_version_posture_changed",
    "device_dependency_impact_changed",
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
_DEVICE_PROFILE_FIELDS = (
    "os_family", "os_name", "os_version", "security_patch", "manufacturer",
    "technical_model", "device_codename", "architecture", "android_abi", "kernel",
    "runtime_type", "termux_version", "python_version", "agent_version",
    "profile_fingerprint", "profile_status",
)
_DISPLAY_MODEL_MAX_LENGTH = 80
_DISPLAY_MODEL_UNSAFE = re.compile(
    r"(?:https?://|www\.|javascript:|data:text/html|[/\\]|<|>|\.\.|"
    r"\b(?:script|token|password|secret|api[_-]?key|bearer)\b)",
    re.IGNORECASE,
)


class DeviceProfileUpdateError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class DeviceAwarenessError(RuntimeError):
    def __init__(self, status_code: int, detail: str, *, assessment: dict[str, Any] | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.assessment = assessment or {}


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


def _optional_int(value: Any, *, minimum: int = 0, maximum: int = 2_000_000_000) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if minimum <= parsed <= maximum else None


def _optional_float(value: Any, *, minimum: float = 0.0, maximum: float = 100_000.0) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed, 3) if minimum <= parsed <= maximum else None


def validate_consumer_model_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > _DISPLAY_MODEL_MAX_LENGTH:
        raise DeviceProfileUpdateError(422, "Consumer model name must be 80 characters or fewer.")
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise DeviceProfileUpdateError(422, "Consumer model name contains unsupported characters.")
    normalized = " ".join(text.split())
    if _DISPLAY_MODEL_UNSAFE.search(normalized):
        raise DeviceProfileUpdateError(422, "Consumer model name must be a plain device label.")
    return normalized


def _normalized_device_profile(item: dict[str, Any]) -> dict[str, Any]:
    profile = item.get("system_profile") if isinstance(item.get("system_profile"), dict) else {}
    health = item.get("system_health") if isinstance(item.get("system_health"), dict) else {}
    profile_collected_at = _safe_text(profile.get("collected_at") or profile.get("profile_updated_at"), 64)
    health_collected_at = _safe_text(health.get("collected_at") or health.get("health_updated_at"), 64)
    load_average = health.get("load_average") if isinstance(health.get("load_average"), list) else []
    result = {
        "profile_schema_version": _optional_int(profile.get("schema_version"), minimum=1, maximum=100) or 1,
        **{field: _safe_text(profile.get(field), 160) for field in _DEVICE_PROFILE_FIELDS},
        "android_api_level": _optional_int(profile.get("android_api_level"), minimum=1, maximum=999),
        "supervisor_version": _safe_text(item.get("supervisor_version"), 80),
        "uptime_seconds": _optional_int(health.get("uptime_seconds"), minimum=0, maximum=20 * 365 * 86400),
        "load_average_1m": _optional_float(health.get("load_average_1m") if health.get("load_average_1m") is not None else (load_average[0] if len(load_average) > 0 else None)),
        "load_average_5m": _optional_float(health.get("load_average_5m") if health.get("load_average_5m") is not None else (load_average[1] if len(load_average) > 1 else None)),
        "load_average_15m": _optional_float(health.get("load_average_15m") if health.get("load_average_15m") is not None else (load_average[2] if len(load_average) > 2 else None)),
        "load_status": _safe_text(health.get("load_status") or "unavailable", 32).lower(),
        "uptime_status": _safe_text(health.get("uptime_status") or health.get("collection_status") or "unavailable", 32).lower(),
        "profile_collected_at": profile_collected_at or None,
        "profile_collected_at_epoch_ms": _epoch_ms(profile_collected_at) if profile_collected_at else 0,
        "health_collected_at": health_collected_at or None,
        "health_collected_at_epoch_ms": _epoch_ms(health_collected_at) if health_collected_at else 0,
    }
    if not result["profile_status"]:
        result["profile_status"] = _safe_text(profile.get("collection_status") or "unavailable", 32).lower()
    return result




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
        self._build_futures_by_key: dict[str, concurrent.futures.Future[Any]] = {}
        self._workload_admission_lock = threading.Lock()
        self._workload_admission: dict[str, tuple[str, int, float]] = {}
        self._workload_admission_generation = 0
        default_workers = "1" if ("com.termux" in os.environ.get("PREFIX", "") or sys.platform == "android") else "2"
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(int(os.environ.get("POCKETLAB_LITE_READ_REFRESH_WORKERS", default_workers)), 4)),
            thread_name_prefix="pocketlab-read-refresh",
        )
        build_default = "1" if ("com.termux" in os.environ.get("PREFIX", "") or sys.platform == "android") else "2"
        try:
            build_workers = max(1, min(int(os.environ.get("POCKETLAB_LITE_PROJECTION_BUILD_WORKERS", build_default)), 2))
        except (TypeError, ValueError):
            build_workers = int(build_default)
        self._build_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=build_workers,
            thread_name_prefix="pocketlab-projection-build",
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
                self._build_futures_by_key.clear()
                self._cache_generation += 1
            with self._workload_admission_lock:
                self._workload_admission.clear()
                self._workload_admission_generation += 1
            self._initialized = True
            self._initialized_path = current_path

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._build_executor.shutdown(wait=False, cancel_futures=True)
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
            self._build_futures_by_key.clear()
            self._cache_generation += 1
        with self._workload_admission_lock:
            self._workload_admission.clear()
            self._workload_admission_generation += 1

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


    def try_acquire_workload(self, domain: str, owner: str) -> tuple[str, int] | None:
        """Acquire one process-local workload lease for a projection domain."""
        safe_domain = re.sub(r"[^a-z0-9_.-]+", "-", str(domain or "").strip().lower())[:80]
        safe_owner = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(owner or "").strip())[:120]
        if not safe_domain or not safe_owner:
            return None
        with self._workload_admission_lock:
            current = self._workload_admission.get(safe_domain)
            if current is not None:
                return None
            self._workload_admission_generation += 1
            generation = self._workload_admission_generation
            self._workload_admission[safe_domain] = (safe_owner, generation, time.monotonic())
            return safe_owner, generation

    def release_workload(self, domain: str, lease: tuple[str, int] | None) -> None:
        if lease is None:
            return
        safe_domain = re.sub(r"[^a-z0-9_.-]+", "-", str(domain or "").strip().lower())[:80]
        with self._workload_admission_lock:
            current = self._workload_admission.get(safe_domain)
            if current is not None and current[0] == lease[0] and current[1] == lease[1]:
                self._workload_admission.pop(safe_domain, None)

    def workload_busy(self, domain: str) -> bool:
        safe_domain = re.sub(r"[^a-z0-9_.-]+", "-", str(domain or "").strip().lower())[:80]
        with self._workload_admission_lock:
            return safe_domain in self._workload_admission

    @staticmethod
    def _refresh_backoff_seconds(cache_key: str, failures: int) -> float:
        base = (60.0, 120.0, 300.0)[min(max(int(failures), 1) - 1, 2)]
        digest = hashlib.sha256(f"{cache_key}:{failures}".encode("utf-8")).digest()
        jitter = int.from_bytes(digest[:2], "big") / 65535.0 * 0.10
        return min(330.0, base * (1.0 + jitter))

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
            build_future = self._build_futures_by_key.get(cache_key)
            if build_future is not None and not build_future.done():
                return
            if build_future is not None and build_future.done():
                self._build_futures_by_key.pop(cache_key, None)
            if cache_key in self._refreshing or now < float(self._next_refresh_allowed_at.get(cache_key, 0.0)):
                return
            self._refreshing.add(cache_key)
            self._refresh_started_at[cache_key] = time.monotonic()
            generation = self._cache_generation
            scheduled_database_path = str(database_path())
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
            scheduled_database_path,
        )

    def _background_refresh(self, *args: Any) -> None:
        cache_key = str(args[0])
        generation = int(args[-2])
        scheduled_database_path = str(args[-1])
        try:
            self._refresh_now(
                *args[:-2],
                False,
                generation,
                scheduled_database_path,
            )
        except Exception as exc:
            failures = 0
            with self._cache_lock:
                if self._refresh_generation_by_key.get(cache_key) == generation:
                    self._refresh_errors[cache_key] = type(exc).__name__
                    failures = min(8, self._consecutive_refresh_failures.get(cache_key, 0) + 1)
                    self._consecutive_refresh_failures[cache_key] = failures
                    backoff = self._refresh_backoff_seconds(cache_key, failures)
                    self._next_refresh_allowed_at[cache_key] = time.monotonic() + backoff
                    saved_state = cache_key in self._prepared
                else:
                    backoff = 0.0
                    saved_state = False
            if isinstance(exc, TimeoutError):
                _LOGGER.warning(
                    "pocketlab.control_projection.refresh_timeout key=%s deadline_ms=%.0f "
                    "saved_state=%s retry_seconds=%.0f failures=%d",
                    cache_key,
                    max(0.05, min(float(args[5]), 30.0)) * 1000.0,
                    str(saved_state).lower(),
                    backoff,
                    failures,
                )
            else:
                _LOGGER.exception(
                    "pocketlab.control_projection.refresh_degraded key=%s error_type=%s "
                    "retry_seconds=%.0f failures=%d",
                    cache_key, type(exc).__name__, backoff, failures,
                )
        finally:
            with self._cache_lock:
                if self._refresh_generation_by_key.get(cache_key) == generation:
                    self._refreshing.discard(cache_key)
                    self._refresh_started_at.pop(cache_key, None)
                    self._refresh_generation_by_key.pop(cache_key, None)

    def _build_with_deadline(
        self,
        cache_key: str,
        domain: str,
        builder: Callable[[], dict[str, Any]],
        deadline_seconds: float,
    ) -> dict[str, Any]:
        timeout = max(0.05, min(float(deadline_seconds), 30.0))
        owner = f"prepared:{cache_key}"
        lease = self.try_acquire_workload(domain, owner)
        if lease is None:
            raise PreparedProjectionUnavailable("Projection domain is already busy")
        try:
            future = self._build_executor.submit(builder)
        except RuntimeError as exc:
            self.release_workload(domain, lease)
            raise PreparedProjectionUnavailable("Projection builder is shutting down") from exc

        with self._cache_lock:
            self._build_futures_by_key[cache_key] = future

        def release_completed(completed: concurrent.futures.Future[Any]) -> None:
            self.release_workload(domain, lease)
            with self._cache_lock:
                if self._build_futures_by_key.get(cache_key) is completed:
                    self._build_futures_by_key.pop(cache_key, None)

        future.add_done_callback(release_completed)
        try:
            payload = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError("Prepared projection build deadline expired") from exc
        if not isinstance(payload, dict):
            raise TypeError("Prepared projection builder must return a mapping")
        return payload

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
        expected_database_path: str | None = None,
    ) -> PreparedRead:
        request_started = time.monotonic()
        scheduled_database_path = expected_database_path or str(database_path())
        if str(database_path()) != scheduled_database_path:
            raise PreparedProjectionUnavailable(
                "Projection database changed before refresh"
            )
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
            if str(database_path()) != scheduled_database_path:
                raise PreparedProjectionUnavailable(
                    "Projection database changed before build"
                )
            started = time.monotonic()
            payload = self._build_with_deadline(cache_key, domain, builder, deadline_seconds)
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
            if str(database_path()) != scheduled_database_path:
                raise PreparedProjectionUnavailable(
                    "Projection database changed before commit"
                )
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

    def _upsert_device_profile_row(
        self,
        conn: sqlite3.Connection,
        *,
        device_id: str,
        item: dict[str, Any],
        updated_at: str,
        updated_at_epoch_ms: int,
    ) -> bool:
        incoming = _normalized_device_profile(item)
        has_profile = bool(
            incoming.get("profile_fingerprint")
            or incoming.get("technical_model")
            or incoming.get("os_name")
            or incoming.get("uptime_seconds") is not None
        )
        existing_row = conn.execute(
            "SELECT * FROM device_system_profiles WHERE node_id=?",
            (device_id,),
        ).fetchone()
        if not has_profile and existing_row is None:
            return False
        existing = dict(existing_row) if existing_row else {}
        if existing and (
            not incoming.get("profile_fingerprint")
            or incoming["profile_collected_at_epoch_ms"] < int(existing.get("profile_collected_at_epoch_ms") or 0)
        ):
            for field in ("profile_schema_version", *_DEVICE_PROFILE_FIELDS, "android_api_level", "profile_collected_at", "profile_collected_at_epoch_ms"):
                incoming[field] = existing.get(field)
        if existing and incoming["health_collected_at_epoch_ms"] < int(existing.get("health_collected_at_epoch_ms") or 0):
            for field in ("uptime_seconds", "load_average_1m", "load_average_5m", "load_average_15m", "load_status", "uptime_status", "health_collected_at", "health_collected_at_epoch_ms"):
                incoming[field] = existing.get(field)
        consumer_model_name = str(existing.get("consumer_model_name") or "")
        columns = (
            "profile_schema_version", "os_family", "os_name", "os_version",
            "android_api_level", "security_patch", "manufacturer", "technical_model",
            "device_codename", "architecture", "android_abi", "kernel", "runtime_type",
            "termux_version", "python_version", "agent_version", "supervisor_version",
            "profile_fingerprint", "profile_status", "uptime_seconds", "load_average_1m",
            "load_average_5m", "load_average_15m", "load_status", "uptime_status", "profile_collected_at",
            "profile_collected_at_epoch_ms", "health_collected_at", "health_collected_at_epoch_ms",
        )
        next_values = tuple(incoming.get(column) for column in columns)
        prior_values = tuple(existing.get(column) for column in columns) if existing else None
        if prior_values == next_values:
            return False
        revision = int(existing.get("revision") or 0) + 1
        conn.execute(
            f"""
            INSERT INTO device_system_profiles(
                node_id, {', '.join(columns)}, consumer_model_name,
                updated_at, updated_at_epoch_ms, revision
            ) VALUES ({', '.join('?' for _ in range(len(columns) + 5))})
            ON CONFLICT(node_id) DO UPDATE SET
                {', '.join(f'{column}=excluded.{column}' for column in columns)},
                consumer_model_name=device_system_profiles.consumer_model_name,
                updated_at=excluded.updated_at,
                updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                revision=excluded.revision
            """,
            (device_id, *next_values, consumer_model_name, updated_at, updated_at_epoch_ms, revision),
        )
        return _changes(conn)

    @staticmethod
    def _public_device_profile(row: dict[str, Any]) -> dict[str, Any]:
        consumer = _safe_text(row.get("consumer_model_name"), _DISPLAY_MODEL_MAX_LENGTH)
        technical = _safe_text(row.get("technical_model"), 160)
        codename = _safe_text(row.get("device_codename"), 160)
        display_model = consumer or technical or codename or "Device"
        uptime_seconds = _optional_int(row.get("uptime_seconds"), maximum=20 * 365 * 86400)
        uptime_label = "Unavailable"
        if uptime_seconds is not None:
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes = remainder // 60
            parts = []
            if days:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes or not parts:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            uptime_label = ", ".join(parts[:2])
        loads = [
            _optional_float(row.get("load_average_1m")),
            _optional_float(row.get("load_average_5m")),
            _optional_float(row.get("load_average_15m")),
        ]
        profile_collected = _safe_text(row.get("profile_collected_at"), 64)
        health_collected = _safe_text(row.get("health_collected_at"), 64)
        profile_age_ms = max(0, _epoch_ms() - int(row.get("profile_collected_at_epoch_ms") or 0)) if profile_collected else None
        profile_freshness = "current" if profile_age_ms is not None and profile_age_ms <= 24 * 60 * 60 * 1000 else "stale" if profile_collected else "unavailable"
        load_1m = loads[0]
        load_status = _safe_text(row.get("load_status"), 32).lower()
        if not load_status:
            load_status = "unavailable" if load_1m is None else "reported"
        return {
            "system_profile": {
                "schema_version": int(row.get("profile_schema_version") or 1),
                "revision": int(row.get("revision") or 0),
                "os_family": _safe_text(row.get("os_family"), 80),
                "os_name": _safe_text(row.get("os_name"), 120),
                "os_version": _safe_text(row.get("os_version"), 80),
                "android_api_level": _optional_int(row.get("android_api_level"), maximum=999),
                "security_patch": _safe_text(row.get("security_patch"), 32),
                "manufacturer": _safe_text(row.get("manufacturer"), 120),
                "technical_model": technical,
                "device_codename": codename,
                "consumer_model_name": consumer,
                "display_model": display_model,
                "model_label_source": (
                    "user_selected" if consumer else
                    "technical_fallback" if technical else
                    "codename_fallback" if codename else
                    "generic_fallback"
                ),
                "technical_identity_source": "agent",
                "architecture": _safe_text(row.get("architecture"), 80),
                "android_abi": _safe_text(row.get("android_abi"), 80),
                "kernel": _safe_text(row.get("kernel"), 160),
                "runtime_type": _safe_text(row.get("runtime_type") or "unknown", 40),
                "termux_version": _safe_text(row.get("termux_version"), 80),
                "python_version": _safe_text(row.get("python_version"), 80),
                "agent_version": _safe_text(row.get("agent_version"), 80),
                "supervisor_version": _safe_text(row.get("supervisor_version"), 80),
                "collection_status": _safe_text(row.get("profile_status") or "unavailable", 32),
                "profile_status": _safe_text(row.get("profile_status") or "unavailable", 32),
                "collected_at": profile_collected or None,
                "profile_updated_at": profile_collected or None,
                "freshness": profile_freshness,
            },
            "system_health": {
                "uptime_seconds": uptime_seconds,
                "uptime_label": uptime_label,
                "load_average": loads,
                "load_status": load_status,
                "collection_status": _safe_text(row.get("uptime_status") or "unavailable", 32),
                "collected_at": health_collected or None,
                "health_updated_at": health_collected or None,
            },
        }

    @staticmethod
    def _json_value(value: Any, fallback: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        try:
            decoded = json.loads(str(value or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback
        if isinstance(fallback, list):
            return decoded if isinstance(decoded, list) else fallback
        return decoded if isinstance(decoded, dict) else fallback

    @staticmethod
    def _public_awareness(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "enrollment": ControlPlaneProjectionStore._json_value(row.get("enrollment_json"), {}),
            "identity": ControlPlaneProjectionStore._json_value(row.get("trust_json"), {}),
            "last_seen_state": ControlPlaneProjectionStore._json_value(row.get("last_seen_json"), {}),
            "capability_states": ControlPlaneProjectionStore._json_value(row.get("capabilities_json"), []),
            "capabilities": ControlPlaneProjectionStore._json_value(row.get("capabilities_json"), []),
            "dependencies": ControlPlaneProjectionStore._json_value(row.get("dependencies_json"), {}),
            "removal_assessment": ControlPlaneProjectionStore._json_value(row.get("removal_assessment_json"), {}),
            "enrollment_status": _safe_text(row.get("enrollment_status"), 40),
            "identity_status": _safe_text(row.get("identity_status"), 40),
            "staleness_state": _safe_text(row.get("staleness_state"), 40),
            "command_delivery_status": _safe_text(row.get("command_delivery_status"), 40),
            "awareness_revision": int(row.get("revision") or 0),
            "updated_at": _safe_text(row.get("updated_at"), 64),
        }

    @staticmethod
    def _public_device_health(
        row: dict[str, Any],
        attention_items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        reasons = ControlPlaneProjectionStore._json_value(row.get("reason_codes_json"), [])
        reasons = [
            _safe_text(item, 80)
            for item in (reasons if isinstance(reasons, list) else [])[:16]
            if _safe_text(item, 80)
        ]
        return {
            "model_version": 1,
            "node_id": _safe_text(row.get("device_id"), 120),
            "status": _safe_text(row.get("health_status") or "unknown", 40),
            "severity": _safe_text(row.get("health_severity") or "none", 24),
            "summary": _safe_text(row.get("summary") or "Device health is not available yet.", 240),
            "reason_codes": reasons,
            "attention_items": (attention_items or [])[:64],
            "attention_count": min(64, max(0, int(row.get("attention_count") or 0))),
            "recommended_action": _safe_text(row.get("recommendation_code") or "review_device", 80),
            "recommended_action_target": _safe_text(row.get("recommendation_target"), 120) or None,
            "last_evaluated_at": _safe_text(row.get("last_evaluated_at"), 64) or None,
            "health_revision": _safe_text(row.get("health_revision"), 80),
            "source_revision": max(0, int(row.get("source_revision") or 0)),
            "revision": max(0, int(row.get("revision") or 0)),
            "source_freshness": ControlPlaneProjectionStore._json_value(row.get("source_freshness_json"), {}),
            "resources": ControlPlaneProjectionStore._json_value(row.get("resources_json"), {}),
            "connection": ControlPlaneProjectionStore._json_value(row.get("connection_json"), {}),
            "recovery": ControlPlaneProjectionStore._json_value(row.get("recovery_json"), {}),
            "versions": ControlPlaneProjectionStore._json_value(row.get("versions_json"), {}),
            "dependency_impact": ControlPlaneProjectionStore._json_value(row.get("dependency_impact_json"), {}),
            "sanitized": True,
        }

    @staticmethod
    def _public_health_attention(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _safe_text(row.get("attention_id"), 120),
            "node_id": _safe_text(row.get("device_id"), 120),
            "reason_code": _safe_text(row.get("reason_code"), 80),
            "category": _safe_text(row.get("category"), 40),
            "severity": _safe_text(row.get("severity"), 24),
            "status": _safe_text(row.get("status"), 24),
            "summary": _safe_text(row.get("summary"), 240),
            "recommendation": _safe_text(row.get("recommendation"), 280),
            "recommended_action": _safe_text(row.get("recommendation_code"), 80),
            "created_at": _safe_text(row.get("created_at"), 64) or None,
            "updated_at": _safe_text(row.get("updated_at"), 64) or None,
            "resolved_at": _safe_text(row.get("resolved_at"), 64) or None,
            "source_revision": max(0, int(row.get("source_revision") or 0)),
        }

    def _upsert_device_health_row(
        self,
        conn: sqlite3.Connection,
        *,
        device_id: str,
        item: dict[str, Any],
        updated_at: str,
        updated_at_epoch_ms: int,
    ) -> tuple[bool, set[str]]:
        health = item.get("proactive_health") if isinstance(item.get("proactive_health"), dict) else {}
        if not health:
            return False, set()
        resources = health.get("resources") if isinstance(health.get("resources"), dict) else {}
        connection = health.get("connection") if isinstance(health.get("connection"), dict) else {}
        recovery = health.get("recovery") if isinstance(health.get("recovery"), dict) else {}
        versions = health.get("versions") if isinstance(health.get("versions"), dict) else {}
        dependency = health.get("dependency_impact") if isinstance(health.get("dependency_impact"), dict) else {}
        reasons = [
            _safe_text(value, 80)
            for value in (health.get("reason_codes") or [])[:16]
            if _safe_text(value, 80)
        ]
        resource_statuses = [
            _safe_text(value.get("status"), 24)
            for value in resources.values()
            if isinstance(value, dict)
        ]
        resource_rank = {"unknown": -1, "normal": 0, "watch": 1, "low": 2, "critical": 3}
        resource_status = max(resource_statuses or ["unknown"], key=lambda value: resource_rank.get(value, -1))
        evaluated_at = _safe_text(health.get("last_evaluated_at") or updated_at, 64)
        values = {
            "health_status": _safe_text(health.get("status") or "unknown", 40),
            "health_severity": _safe_text(health.get("severity") or "none", 24),
            "resource_status": resource_status,
            "connection_status": _safe_text(connection.get("status") or "unknown", 40),
            "recovery_status": _safe_text(recovery.get("status") or "unknown", 40),
            "version_status": _safe_text(versions.get("status") or "unknown", 40),
            "dependency_impact_status": _safe_text(dependency.get("status") or "unknown", 40),
            "reason_codes_json": _safe_json(reasons, max_bytes=4096),
            "recommendation_code": _safe_text(health.get("recommended_action") or "review_device", 80),
            "recommendation_target": _safe_text(health.get("recommended_action_target"), 120) or None,
            "attention_count": min(64, max(0, int(health.get("attention_count") or 0))),
            "health_revision": _safe_text(health.get("health_revision"), 80),
            "source_revision": max(0, int(health.get("source_revision") or 0)),
            "source_freshness_json": _safe_json(health.get("source_freshness") or {}, max_bytes=8192),
            "resources_json": _safe_json(resources, max_bytes=12288),
            "connection_json": _safe_json(connection, max_bytes=8192),
            "recovery_json": _safe_json(recovery, max_bytes=8192),
            "versions_json": _safe_json(versions, max_bytes=8192),
            "dependency_impact_json": _safe_json(dependency, max_bytes=12288),
            "summary": _safe_text(health.get("summary") or "Device health is not available yet.", 240),
            "last_evaluated_at": evaluated_at,
            "last_evaluated_at_epoch_ms": _epoch_ms(evaluated_at),
        }
        existing_row = conn.execute(
            "SELECT * FROM device_health_current WHERE device_id=?", (device_id,)
        ).fetchone()
        existing = dict(existing_row) if existing_row else {}
        # The evaluator revision intentionally contains threshold buckets and
        # lifecycle material, not raw metric values. Treat it as the compare-
        # and-set fence so normal telemetry drift cannot write on every heartbeat.
        health_changed = not existing or existing.get("health_revision") != values["health_revision"]
        reasons_changed: set[str] = set()
        if health_changed:
            reasons_changed.add("device_health_changed")
            if not existing or existing.get("resource_status") != values["resource_status"]:
                reasons_changed.add("device_resource_pressure_changed")
            if not existing or existing.get("connection_status") != values["connection_status"]:
                reasons_changed.add("device_connection_quality_changed")
            if not existing or existing.get("recovery_status") != values["recovery_status"]:
                reasons_changed.add("device_recovery_pattern_changed")
            if not existing or existing.get("version_status") != values["version_status"]:
                reasons_changed.add("device_version_posture_changed")
            if not existing or existing.get("dependency_impact_status") != values["dependency_impact_status"]:
                reasons_changed.add("device_dependency_impact_changed")
            revision = int(existing.get("revision") or 0) + 1
            columns = list(values.keys())
            conn.execute(
                f"""
                INSERT INTO device_health_current(
                    device_id, {', '.join(columns)}, updated_at, updated_at_epoch_ms, revision
                ) VALUES ({', '.join('?' for _ in range(len(columns) + 4))})
                ON CONFLICT(device_id) DO UPDATE SET
                    {', '.join(f'{column}=excluded.{column}' for column in columns)},
                    updated_at=excluded.updated_at,
                    updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                    revision=excluded.revision
                """,
                (device_id, *(values[column] for column in columns), updated_at, updated_at_epoch_ms, revision),
            )
            previous_state = _safe_text(existing.get("health_status") or "unknown", 40)
            new_state = values["health_status"]
            transition_material = json.dumps(
                [device_id, previous_state, new_state, values["health_revision"]],
                separators=(",", ":"),
            )
            event_id = hashlib.sha256(transition_material.encode("utf-8")).hexdigest()[:24]
            conn.execute(
                """
                INSERT OR IGNORE INTO device_health_transitions(
                    event_id, device_id, previous_state, new_state, reason_codes_json,
                    summary, occurred_at, occurred_at_epoch_ms, source_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, device_id, previous_state, new_state,
                    values["reason_codes_json"], values["summary"], evaluated_at,
                    values["last_evaluated_at_epoch_ms"], values["source_revision"],
                ),
            )

        attention_changed = False
        active_ids: list[str] = []
        for raw in (health.get("attention_items") or [])[:64]:
            if not isinstance(raw, dict):
                continue
            attention_id = _safe_text(raw.get("id"), 120)
            reason_code = _safe_text(raw.get("reason_code"), 80)
            if not attention_id or not reason_code:
                continue
            active_ids.append(attention_id)
            created_at = _safe_text(raw.get("created_at") or evaluated_at, 64)
            item_updated_at = _safe_text(raw.get("updated_at") or evaluated_at, 64)
            conn.execute(
                """
                INSERT INTO device_health_attention(
                    attention_id, device_id, reason_code, category, severity, status,
                    summary, recommendation, recommendation_code, created_at,
                    created_at_epoch_ms, updated_at, updated_at_epoch_ms,
                    resolved_at, resolved_at_epoch_ms, source_revision
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, NULL, 0, ?)
                ON CONFLICT(attention_id) DO UPDATE SET
                    category=excluded.category,
                    severity=excluded.severity,
                    status=CASE
                        WHEN device_health_attention.status='acknowledged' THEN 'acknowledged'
                        ELSE 'active'
                    END,
                    summary=excluded.summary,
                    recommendation=excluded.recommendation,
                    recommendation_code=excluded.recommendation_code,
                    updated_at=excluded.updated_at,
                    updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                    resolved_at=NULL,
                    resolved_at_epoch_ms=0,
                    source_revision=excluded.source_revision
                WHERE device_health_attention.category IS NOT excluded.category
                   OR device_health_attention.severity IS NOT excluded.severity
                   OR device_health_attention.status NOT IN ('active','acknowledged')
                   OR device_health_attention.summary IS NOT excluded.summary
                   OR device_health_attention.recommendation IS NOT excluded.recommendation
                   OR device_health_attention.recommendation_code IS NOT excluded.recommendation_code
                """,
                (
                    attention_id, device_id, reason_code,
                    _safe_text(raw.get("category") or "device", 40),
                    _safe_text(raw.get("severity") or "low", 24),
                    _safe_text(raw.get("summary") or "Device needs review.", 240),
                    _safe_text(raw.get("recommendation") or "Review the device.", 280),
                    _safe_text(raw.get("recommended_action") or "review_device", 80),
                    created_at, _epoch_ms(created_at), item_updated_at,
                    _epoch_ms(item_updated_at), max(0, int(raw.get("source_revision") or 0)),
                ),
            )
            attention_changed = bool(_changes(conn)) or attention_changed
        if active_ids:
            placeholders = ",".join("?" for _ in active_ids)
            conn.execute(
                f"""
                UPDATE device_health_attention
                   SET status='resolved', resolved_at=?, resolved_at_epoch_ms=?,
                       updated_at=?, updated_at_epoch_ms=?
                 WHERE device_id=? AND status IN ('active','acknowledged')
                   AND attention_id NOT IN ({placeholders})
                """,
                (updated_at, updated_at_epoch_ms, updated_at, updated_at_epoch_ms, device_id, *active_ids),
            )
        else:
            conn.execute(
                """
                UPDATE device_health_attention
                   SET status='resolved', resolved_at=?, resolved_at_epoch_ms=?,
                       updated_at=?, updated_at_epoch_ms=?
                 WHERE device_id=? AND status IN ('active','acknowledged')
                """,
                (updated_at, updated_at_epoch_ms, updated_at, updated_at_epoch_ms, device_id),
            )
        attention_changed = bool(_changes(conn)) or attention_changed
        if attention_changed:
            reasons_changed.add("device_attention_changed")
        return bool(health_changed or attention_changed), reasons_changed

    def _upsert_device_awareness_row(
        self,
        conn: sqlite3.Connection,
        *,
        device_id: str,
        item: dict[str, Any],
        updated_at: str,
        updated_at_epoch_ms: int,
    ) -> tuple[bool, set[str]]:
        enrollment = item.get("enrollment") if isinstance(item.get("enrollment"), dict) else {}
        identity = item.get("identity") if isinstance(item.get("identity"), dict) else {}
        last_seen = item.get("last_seen_state") if isinstance(item.get("last_seen_state"), dict) else {}
        capabilities = item.get("capability_states") if isinstance(item.get("capability_states"), list) else item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        dependencies = item.get("dependencies") if isinstance(item.get("dependencies"), dict) else {}
        removal = item.get("removal_assessment") if isinstance(item.get("removal_assessment"), dict) else {}
        identity_verified_at = identity.get("verified_at")
        last_identity_mismatch_at = identity.get("last_mismatch_at")
        last_blocked_join_at = identity.get("last_blocked_join_at")
        last_seen_at = last_seen.get("last_seen_at")
        capability_json = _safe_json(capabilities, max_bytes=32768)
        dependency_json = _safe_json(dependencies, max_bytes=32768)
        removal_json = _safe_json(removal, max_bytes=16384)
        trust_json = _safe_json(identity, max_bytes=16384)
        enrollment_json = _safe_json(enrollment, max_bytes=16384)
        # Persist only stable source timestamps and lifecycle state. Derived age
        # counters change every second and must not advance the device-scoped
        # awareness revision between removal assessment and confirmation.
        stable_last_seen = {
            key: value
            for key, value in last_seen.items()
            if key not in {
                "heartbeat_age_seconds",
                "supervisor_age_seconds",
                "connection_age_seconds",
            }
        }
        last_seen_json = _safe_json(stable_last_seen, max_bytes=16384)
        capability_revision = hashlib.sha256(capability_json.encode("utf-8")).hexdigest()[:20]
        assessment_revision = _safe_text(removal.get("assessment_revision"), 80)
        recovery_status = "repairing" if dependencies.get("recovery_in_progress") else _safe_text(dependencies.get("last_recovery_result") or "idle", 40)
        values = {
            "enrollment_status": _safe_text(enrollment.get("status") or item.get("enrollment_status") or "not_enrolled", 40),
            "identity_status": _safe_text(identity.get("status") or item.get("identity_status") or "pending", 40),
            "identity_verified_at": identity_verified_at,
            "identity_verified_at_epoch_ms": _epoch_ms(identity_verified_at) if identity_verified_at else 0,
            "identity_mismatch_count": max(0, int(identity.get("mismatch_count") or 0)),
            "last_identity_mismatch_at": last_identity_mismatch_at,
            "last_identity_mismatch_at_epoch_ms": _epoch_ms(last_identity_mismatch_at) if last_identity_mismatch_at else 0,
            "blocked_join_count": max(0, int(identity.get("blocked_join_count") or 0)),
            "last_blocked_join_at": last_blocked_join_at,
            "repair_required": int(bool(identity.get("repair_required"))),
            "last_seen_at": last_seen_at,
            "last_seen_at_epoch_ms": _epoch_ms(last_seen_at) if last_seen_at else 0,
            "last_seen_source": _safe_text(last_seen.get("last_seen_source") or "unknown", 40),
            "staleness_state": _safe_text(last_seen.get("staleness_state") or item.get("staleness_state") or "unknown", 40),
            "command_delivery_status": _safe_text(dependencies.get("command_delivery_status") or "unknown", 40),
            "supervisor_status": _safe_text(dependencies.get("supervisor_status") or item.get("supervisor_status") or "unknown", 40),
            "recovery_status": recovery_status,
            "hosted_app_count": max(0, int(dependencies.get("hosted_app_count") or 0)),
            "backup_dependency_count": max(0, int(dependencies.get("backup_set_count") or 0)),
            "storage_dependency_count": max(0, int(dependencies.get("storage_dependency_count") or 0)),
            "capability_revision": capability_revision,
            "capabilities_json": capability_json,
            "dependencies_json": dependency_json,
            "removal_safe": int(bool(removal.get("safe_to_remove"))),
            "removal_assessment_revision": assessment_revision,
            "removal_assessment_json": removal_json,
            "trust_json": trust_json,
            "enrollment_json": enrollment_json,
            "last_seen_json": last_seen_json,
        }
        existing_row = conn.execute(
            "SELECT * FROM device_awareness_state WHERE device_id=?", (device_id,)
        ).fetchone()
        existing = dict(existing_row) if existing_row else {}
        compared = tuple(values.keys())
        if existing and all(existing.get(key) == values[key] for key in compared):
            return False, set()
        reasons: set[str] = set()
        if not existing or existing.get("enrollment_status") != values["enrollment_status"]:
            reasons.add("device_enrollment_changed")
        if not existing or any(existing.get(key) != values[key] for key in (
            "identity_status", "identity_verified_at", "identity_mismatch_count",
            "last_identity_mismatch_at", "blocked_join_count", "last_blocked_join_at",
            "repair_required",
        )):
            reasons.add("device_identity_changed")
        if not existing or any(existing.get(key) != values[key] for key in (
            "last_seen_source", "staleness_state",
        )):
            reasons.add("device_staleness_changed")
        if not existing or existing.get("capability_revision") != capability_revision:
            reasons.add("device_capabilities_changed")
        if not existing or existing.get("dependencies_json") != dependency_json:
            reasons.add("device_dependencies_changed")
        if not existing or existing.get("command_delivery_status") != values["command_delivery_status"]:
            reasons.add("device_command_delivery_changed")
        if not existing or existing.get("recovery_status") != recovery_status:
            reasons.add("device_recovery_changed")
        if not existing or existing.get("removal_assessment_revision") != assessment_revision:
            reasons.add("device_removal_assessment_changed")
        revision = int(existing.get("revision") or 0) + 1
        columns = list(values.keys())
        conn.execute(
            f"""
            INSERT INTO device_awareness_state(
                device_id, {', '.join(columns)}, updated_at, updated_at_epoch_ms, revision
            ) VALUES ({', '.join('?' for _ in range(len(columns) + 4))})
            ON CONFLICT(device_id) DO UPDATE SET
                {', '.join(f'{column}=excluded.{column}' for column in columns)},
                updated_at=excluded.updated_at,
                updated_at_epoch_ms=excluded.updated_at_epoch_ms,
                revision=excluded.revision
            """,
            (device_id, *(values[column] for column in columns), updated_at, updated_at_epoch_ms, revision),
        )
        return bool(_changes(conn)), reasons

    def device_health_map(self) -> dict[str, dict[str, Any]]:
        self.initialize()

        def read(conn: sqlite3.Connection) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
            current = list(conn.execute(
                "SELECT * FROM device_health_current ORDER BY device_id"
            ))
            attention = list(conn.execute(
                "SELECT * FROM device_health_attention "
                "WHERE status IN ('active','acknowledged') "
                "ORDER BY device_id, updated_at_epoch_ms DESC, attention_id DESC"
            ))
            return current, attention

        (current_rows, attention_rows), _, _ = self._read(read)
        attention_by_device: dict[str, list[dict[str, Any]]] = {}
        for row in attention_rows:
            public = self._public_health_attention(dict(row))
            attention_by_device.setdefault(str(public.get("node_id") or ""), []).append(public)
        return {
            str(row["device_id"]): self._public_device_health(
                dict(row), attention_by_device.get(str(row["device_id"]), [])
            )
            for row in current_rows
        }

    def fleet_health_summary(self) -> dict[str, Any]:
        self.initialize()

        def read(conn: sqlite3.Connection) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
            states = list(conn.execute(
                "SELECT health_status, health_severity, COUNT(*) AS count "
                "FROM device_health_current GROUP BY health_status, health_severity"
            ))
            attention = list(conn.execute(
                "SELECT category, severity, COUNT(*) AS count "
                "FROM device_health_attention WHERE status IN ('active','acknowledged') "
                "GROUP BY category, severity"
            ))
            return states, attention

        (state_rows, attention_rows), wait_ms, query_ms = self._read(read)
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        total = 0
        for row in state_rows:
            count = int(row["count"] or 0)
            total += count
            status = _safe_text(row["health_status"] or "unknown", 40)
            severity = _safe_text(row["health_severity"] or "none", 24)
            by_status[status] = by_status.get(status, 0) + count
            by_severity[severity] = by_severity.get(severity, 0) + count
        attention_by_category: dict[str, int] = {}
        attention_total = 0
        for row in attention_rows:
            count = int(row["count"] or 0)
            attention_total += count
            category = _safe_text(row["category"] or "device", 40)
            attention_by_category[category] = attention_by_category.get(category, 0) + count
        return {
            "status": "ready",
            "device_count": total,
            "attention_count": attention_total,
            "by_status": by_status,
            "by_severity": by_severity,
            "attention_by_category": attention_by_category,
            "source_revision": self.domain_revision("fleet"),
            "connection_wait_ms": round(wait_ms, 3),
            "sqlite_query_ms": round(query_ms, 3),
            "sanitized": True,
        }

    def device_health(self, device_id: str) -> dict[str, Any]:
        self.initialize()
        normalized = _safe_text(device_id, 120)
        if not normalized:
            raise DeviceAwarenessError(404, "Device was not found.")

        def read(conn: sqlite3.Connection) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
            current = conn.execute(
                "SELECT * FROM device_health_current WHERE device_id=?", (normalized,)
            ).fetchone()
            attention = list(conn.execute(
                "SELECT * FROM device_health_attention "
                "WHERE device_id=? AND status IN ('active','acknowledged') "
                "ORDER BY updated_at_epoch_ms DESC, attention_id DESC LIMIT 64",
                (normalized,),
            ))
            return current, attention

        (current_row, attention_rows), wait_ms, query_ms = self._read(read)
        if not current_row:
            raise DeviceAwarenessError(404, "Device health is not available yet.")
        health = self._public_device_health(
            dict(current_row), [self._public_health_attention(dict(row)) for row in attention_rows]
        )
        return {
            "status": "ready",
            "health": health,
            "source_revision": self.domain_revision("fleet"),
            "connection_wait_ms": round(wait_ms, 3),
            "sqlite_query_ms": round(query_ms, 3),
            "updated_at": health.get("last_evaluated_at"),
        }

    def device_health_history(
        self, device_id: str, *, limit: int = 20, cursor: str = ""
    ) -> dict[str, Any]:
        self.initialize()
        normalized = _safe_text(device_id, 120)
        if not normalized:
            raise ValueError("device_id is required")
        bounded_limit = max(1, min(int(limit), 100))
        decoded = _decode_cursor(cursor)

        def read(conn: sqlite3.Connection) -> tuple[bool, list[sqlite3.Row]]:
            exists = conn.execute(
                "SELECT 1 FROM device_current_state WHERE device_id=? LIMIT 1",
                (normalized,),
            ).fetchone() is not None
            params: list[Any] = [normalized]
            cursor_clause = ""
            if decoded is not None:
                cursor_clause = (
                    " AND (occurred_at_epoch_ms < ? OR "
                    "(occurred_at_epoch_ms = ? AND event_id < ?))"
                )
                params.extend([decoded[0], decoded[0], decoded[1]])
            params.append(bounded_limit + 1)
            rows = list(conn.execute(
                "SELECT event_id,device_id AS node_id,previous_state,new_state,"
                "reason_codes_json,summary,occurred_at,occurred_at_epoch_ms,source_revision "
                "FROM device_health_transitions WHERE device_id=?"
                + cursor_clause
                + " ORDER BY occurred_at_epoch_ms DESC,event_id DESC LIMIT ?",
                tuple(params),
            ))
            return exists, rows

        (exists, rows), wait_ms, query_ms = self._read(read)
        if not exists:
            raise DeviceAwarenessError(404, "Device was not found.")
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["reason_codes"] = self._json_value(item.pop("reason_codes_json", "[]"), [])
            item["sanitized"] = True
            items.append(item)
        return self._history_result(
            items, limit=bounded_limit, epoch_key="occurred_at_epoch_ms",
            id_key="event_id", revision=self.domain_revision("fleet"),
            wait_ms=wait_ms, query_ms=query_ms,
        )

    def device_profile_map(self) -> dict[str, dict[str, Any]]:
        self.initialize()
        rows, _, _ = self._read(
            lambda conn: [dict(row) for row in conn.execute(
                "SELECT * FROM device_system_profiles ORDER BY node_id"
            )]
        )
        return {str(row["node_id"]): self._public_device_profile(row) for row in rows}

    def device_details(self, device_id: str) -> dict[str, Any]:
        self.initialize()
        normalized = _safe_text(device_id, 120)
        if not normalized:
            raise DeviceAwarenessError(404, "Device was not found.")

        def read(conn: sqlite3.Connection) -> tuple[
            sqlite3.Row | None, sqlite3.Row | None, sqlite3.Row | None,
            sqlite3.Row | None, list[sqlite3.Row]
        ]:
            current = conn.execute(
                "SELECT * FROM device_current_state WHERE device_id=?", (normalized,)
            ).fetchone()
            profile = conn.execute(
                "SELECT * FROM device_system_profiles WHERE node_id=?", (normalized,)
            ).fetchone()
            awareness = conn.execute(
                "SELECT * FROM device_awareness_state WHERE device_id=?", (normalized,)
            ).fetchone()
            health = conn.execute(
                "SELECT * FROM device_health_current WHERE device_id=?", (normalized,)
            ).fetchone()
            attention = list(conn.execute(
                "SELECT * FROM device_health_attention "
                "WHERE device_id=? AND status IN ('active','acknowledged') "
                "ORDER BY updated_at_epoch_ms DESC, attention_id DESC LIMIT 64",
                (normalized,),
            ))
            return current, profile, awareness, health, attention

        (current_row, profile_row, awareness_row, health_row, attention_rows), wait_ms, query_ms = self._read(read)
        if not current_row:
            raise DeviceAwarenessError(404, "Device was not found.")
        current = dict(current_row)
        payload: dict[str, Any] = {
            "id": current["device_id"],
            "node_id": current["device_id"],
            "name": current.get("device_name") or current["device_id"],
            "role": current.get("role") or "compute",
            "status": current.get("ui_state") or current.get("connection_state") or "unknown",
            "connection": current.get("connection_state") or "unknown",
            "agent_status": current.get("agent_status") or "unknown",
            "supervisor_status": current.get("supervisor_status") or "unknown",
            "agent_process_status": current.get("pm2_status") or "unknown",
            "remote_access": bool(current.get("remote_access_ready")),
            "is_current": bool(current.get("protected_server_host")),
            "protected_server_host": bool(current.get("protected_server_host")),
            "last_seen_at": current.get("last_seen_at"),
            "summary": current.get("summary") or "Device state recorded.",
        }
        if profile_row:
            payload.update(self._public_device_profile(dict(profile_row)))
        if awareness_row:
            payload.update(self._public_awareness(dict(awareness_row)))
        if health_row:
            health = self._public_device_health(
                dict(health_row), [self._public_health_attention(dict(row)) for row in attention_rows]
            )
            payload["proactive_health"] = health
            payload["health_status"] = health.get("status")
            payload["health_severity"] = health.get("severity")
            payload["attention_count"] = health.get("attention_count")
        revision = self.domain_revision("fleet")
        return {
            "status": "ready",
            "device": payload,
            "source_revision": revision,
            "connection_wait_ms": round(wait_ms, 3),
            "sqlite_query_ms": round(query_ms, 3),
            "updated_at": payload.get("updated_at") or current.get("updated_at"),
        }

    def device_lifecycle_history(
        self, device_id: str, *, limit: int = 20, cursor: str = ""
    ) -> dict[str, Any]:
        self.initialize()
        normalized = _safe_text(device_id, 120)
        if not normalized:
            raise ValueError("device_id is required")
        bounded_limit = max(1, min(int(limit), 100))
        decoded = _decode_cursor(cursor)

        def read(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            params: list[Any] = [normalized]
            cursor_clause = ""
            if decoded is not None:
                cursor_clause = (
                    " AND (occurred_at_epoch_ms < ? OR "
                    "(occurred_at_epoch_ms = ? AND event_id < ?))"
                )
                params.extend([decoded[0], decoded[0], decoded[1]])
            params.append(bounded_limit + 1)
            return list(conn.execute(
                "SELECT event_id,device_id AS node_id,event_type,reason_code,status,"
                "occurred_at,occurred_at_epoch_ms,summary,sanitized "
                "FROM device_lifecycle_events WHERE device_id=?"
                + cursor_clause
                + " ORDER BY occurred_at_epoch_ms DESC,event_id DESC LIMIT ?",
                tuple(params),
            ))

        rows, wait_ms, query_ms = self._read(read)
        return self._history_result(
            rows, limit=bounded_limit, epoch_key="occurred_at_epoch_ms",
            id_key="event_id", revision=self.domain_revision("fleet"),
            wait_ms=wait_ms, query_ms=query_ms,
        )

    def device_removal_assessment(self, device_id: str) -> dict[str, Any]:
        details = self.device_details(device_id)
        device = details.get("device") if isinstance(details.get("device"), dict) else {}
        assessment = device.get("removal_assessment") if isinstance(device.get("removal_assessment"), dict) else {}
        if not assessment:
            raise DeviceAwarenessError(409, "Removal impact is still being prepared.")
        return {
            **assessment,
            "node_id": device.get("id") or device_id,
            "source_revision": int(details.get("source_revision") or 0),
            "awareness_revision": int(device.get("awareness_revision") or 0),
            "offline_authorization": False,
            "summary": (
                "Safe to remove after confirmation."
                if assessment.get("safe_to_remove")
                else "Review dependencies before removing this device."
            ),
        }

    def validate_device_removal_assessment(
        self,
        device_id: str,
        *,
        assessment_revision: str,
        expected_awareness_revision: int | None,
    ) -> dict[str, Any]:
        current = self.device_removal_assessment(device_id)
        if not bool(current.get("safe_to_remove")):
            blockers = current.get("blockers") if isinstance(current.get("blockers"), list) else []
            first = blockers[0].get("summary") if blockers and isinstance(blockers[0], dict) else "This device is not safe to remove."
            raise DeviceAwarenessError(409, str(first), assessment=current)
        supplied = _safe_text(assessment_revision, 80)
        current_revision = _safe_text(current.get("assessment_revision"), 80)
        if not supplied or supplied != current_revision:
            raise DeviceAwarenessError(
                409,
                "Device responsibilities changed. Review removal impact again.",
                assessment=current,
            )
        if expected_awareness_revision is None or int(expected_awareness_revision) != int(current.get("awareness_revision") or 0):
            raise DeviceAwarenessError(
                409,
                "Device responsibilities changed. Review removal impact again.",
                assessment=current,
            )
        return current

    def update_device_consumer_model(
        self,
        node_id: str,
        value: Any,
        *,
        expected_profile_revision: int | None = None,
        expected_consumer_model_name: str | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        device_id = _safe_text(node_id, 120)
        if not device_id:
            raise DeviceProfileUpdateError(404, "Device was not found.")
        consumer_model_name = validate_consumer_model_name(value)
        now = _utc_now()
        now_epoch = _epoch_ms(now)

        def write(conn: sqlite3.Connection) -> dict[str, Any]:
            device = conn.execute(
                "SELECT device_id, protected_server_host FROM device_current_state WHERE device_id=?",
                (device_id,),
            ).fetchone()
            if not device:
                raise DeviceProfileUpdateError(404, "Device was not found.")
            protected_server_host = bool(device["protected_server_host"])
            existing_row = conn.execute(
                "SELECT * FROM device_system_profiles WHERE node_id=?",
                (device_id,),
            ).fetchone()
            existing = dict(existing_row) if existing_row else {}
            existing_profile_revision = int(existing.get("revision") or 0)
            if str(existing.get("consumer_model_name") or "") == consumer_model_name:
                public = self._public_device_profile(existing) if existing else {
                    "system_profile": {"consumer_model_name": consumer_model_name, "display_model": consumer_model_name or "Unknown model"},
                    "system_health": {},
                }
                return {
                    "changed": False,
                    "revision": _domain_revision(conn, "fleet"),
                    "profile_revision": existing_profile_revision,
                    **public,
                }
            existing_consumer_model_name = str(existing.get("consumer_model_name") or "")
            if expected_consumer_model_name is not None:
                expected_consumer = validate_consumer_model_name(expected_consumer_model_name)
                if expected_consumer != existing_consumer_model_name:
                    raise DeviceProfileUpdateError(
                        409,
                        "The display model changed in another tab. Review the latest value and try again.",
                    )
            elif expected_profile_revision is not None and int(expected_profile_revision) != existing_profile_revision:
                # Compatibility fence for older clients. New clients compare the
                # display-only field so routine health/profile telemetry cannot
                # create false conflicts while the model sheet is open.
                raise DeviceProfileUpdateError(409, "Device details changed in another tab. Refresh and try again.")
            if existing:
                conn.execute(
                    "UPDATE device_system_profiles SET consumer_model_name=?, updated_at=?, updated_at_epoch_ms=?, revision=revision+1 WHERE node_id=?",
                    (consumer_model_name, now, now_epoch, device_id),
                )
            else:
                conn.execute(
                    "INSERT INTO device_system_profiles(node_id, consumer_model_name, updated_at, updated_at_epoch_ms, revision) VALUES (?, ?, ?, ?, 1)",
                    (device_id, consumer_model_name, now, now_epoch),
                )
            profile_revision = int(
                conn.execute(
                    "SELECT revision FROM device_system_profiles WHERE node_id=?",
                    (device_id,),
                ).fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO audit_evidence_index(
                    event_type, entity_type, entity_id, operation_id, status, evidence_ref,
                    created_at, created_at_epoch_ms, summary
                ) VALUES ('device.display_model.updated', 'device', ?, ?, 'succeeded',
                          'sqlite:device_system_profiles', ?, ?, ?)
                """,
                (
                    device_id,
                    f"device-display-model-{device_id}-{profile_revision}",
                    now,
                    now_epoch,
                    (
                        "Protected server display model updated."
                        if protected_server_host and consumer_model_name
                        else "Protected server display model cleared."
                        if protected_server_host
                        else "Device display model updated."
                        if consumer_model_name
                        else "Device display model cleared."
                    ),
                ),
            )
            _bump_revision(conn, "audit", now, changed_ids=[device_id], reason="audit_state_changed", projection_version=1)
            revision = _bump_revision(conn, "fleet", now, changed_ids=[device_id], reason="fleet_state_changed", projection_version=2)
            updated = dict(conn.execute("SELECT * FROM device_system_profiles WHERE node_id=?", (device_id,)).fetchone())
            return {
                "changed": True,
                "revision": revision,
                "profile_revision": profile_revision,
                **self._public_device_profile(updated),
            }

        result = SQLITE_WRITER.submit("fleet.display_model", write, deadline_seconds=1.0)
        self.invalidate_domain("fleet")
        return dict(result)

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
            awareness_reasons: set[str] = set()
            health_changed_ids: set[str] = set()
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
                changed = self._upsert_device_profile_row(
                    conn,
                    device_id=device_id,
                    item=item,
                    updated_at=now,
                    updated_at_epoch_ms=now_epoch,
                ) or changed
                awareness_changed, device_reasons = self._upsert_device_awareness_row(
                    conn,
                    device_id=device_id,
                    item=item,
                    updated_at=now,
                    updated_at_epoch_ms=now_epoch,
                )
                changed = awareness_changed or changed
                awareness_reasons.update(device_reasons)
                health_changed, health_reasons = self._upsert_device_health_row(
                    conn,
                    device_id=device_id,
                    item=item,
                    updated_at=now,
                    updated_at_epoch_ms=now_epoch,
                )
                if health_changed:
                    health_changed_ids.add(device_id)
                changed = health_changed or changed
                awareness_reasons.update(health_reasons)
                for event in (item.get("recent_lifecycle") or [])[:50]:
                    if not isinstance(event, dict):
                        continue
                    event_id = _safe_text(event.get("event_id"), 120)
                    event_type = _safe_text(event.get("event_type") or "device_activity", 80)
                    occurred_at = _safe_text(event.get("occurred_at") or now, 64)
                    if not event_id or not event_type or not occurred_at:
                        continue
                    dedupe_key = _safe_text(event.get("dedupe_key"), 240)
                    if not dedupe_key and event_type in {"first_heartbeat_received", "first_supervisor_heartbeat"}:
                        dedupe_key = f"{device_id}:{event_type}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO device_lifecycle_events(
                            event_id, device_id, event_type, reason_code, status,
                            occurred_at, occurred_at_epoch_ms, summary, sanitized, source_revision, dedupe_key
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            event_id, device_id, event_type,
                            _safe_text(event.get("reason_code"), 80),
                            _safe_text(event.get("status") or "recorded", 32),
                            occurred_at, _epoch_ms(occurred_at),
                            _safe_text(event.get("summary") or "Device activity recorded.", 240),
                            int(item.get("revision") or 0),
                            dedupe_key or None,
                        ),
                    )
                    changed = _changes(conn) or changed

            if device_ids:
                placeholders = ",".join("?" for _ in device_ids)
                conn.execute(
                    f"DELETE FROM device_health_current WHERE device_id NOT IN ({placeholders})",
                    tuple(device_ids),
                )
                changed = _changes(conn) or changed
                conn.execute(
                    f"DELETE FROM device_current_state WHERE device_id NOT IN ({placeholders})",
                    tuple(device_ids),
                )
                changed = _changes(conn) or changed
            else:
                conn.execute("DELETE FROM device_health_current")
                changed = _changes(conn) or changed
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
            conn.execute(
                "DELETE FROM device_lifecycle_events WHERE event_row_id NOT IN "
                "(SELECT event_row_id FROM device_lifecycle_events ORDER BY occurred_at_epoch_ms DESC, event_row_id DESC LIMIT 4096)"
            )
            changed = _changes(conn) or changed
            conn.execute(
                "DELETE FROM device_health_transitions WHERE transition_row_id NOT IN "
                "(SELECT transition_row_id FROM device_health_transitions "
                "ORDER BY occurred_at_epoch_ms DESC, transition_row_id DESC LIMIT 2048)"
            )
            changed = _changes(conn) or changed
            conn.execute(
                "DELETE FROM device_health_attention WHERE status='resolved' AND attention_id NOT IN "
                "(SELECT attention_id FROM device_health_attention WHERE status='resolved' "
                "ORDER BY updated_at_epoch_ms DESC, attention_id DESC LIMIT 1024)"
            )
            changed = _changes(conn) or changed
            reason_priority = (
                "device_attention_changed", "device_health_changed",
                "device_connection_quality_changed", "device_resource_pressure_changed",
                "device_recovery_pattern_changed", "device_version_posture_changed",
                "device_dependency_impact_changed",
                "device_identity_changed", "device_enrollment_changed",
                "device_dependencies_changed", "device_capabilities_changed",
                "device_removal_assessment_changed", "device_command_delivery_changed",
                "device_recovery_changed", "device_staleness_changed",
            )
            focused_reason = next((reason for reason in reason_priority if reason in awareness_reasons), "fleet_state_changed")
            focused_ids = (
                sorted(health_changed_ids)
                if focused_reason.startswith("device_health_")
                or focused_reason in {
                    "device_attention_changed",
                    "device_connection_quality_changed",
                    "device_resource_pressure_changed",
                    "device_recovery_pattern_changed",
                    "device_version_posture_changed",
                    "device_dependency_impact_changed",
                }
                else device_ids
            )
            return _bump_revision(
                conn, "fleet", now, changed_ids=focused_ids,
                reason=focused_reason, projection_version=4,
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
            "device_system_profile": (
                "SELECT node_id, technical_model, consumer_model_name, uptime_seconds FROM device_system_profiles WHERE node_id=?",
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
            "device_health_current": (
                "SELECT health_status, health_severity, health_revision FROM device_health_current WHERE device_id=?",
                ("device-1",),
            ),
            "device_health_attention": (
                "SELECT attention_id FROM device_health_attention WHERE device_id=? AND status IN ('active','acknowledged') ORDER BY updated_at_epoch_ms DESC, attention_id DESC LIMIT 20",
                ("device-1",),
            ),
            "device_health_history": (
                "SELECT event_id FROM device_health_transitions WHERE device_id=? ORDER BY occurred_at_epoch_ms DESC, event_id DESC LIMIT 20",
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
