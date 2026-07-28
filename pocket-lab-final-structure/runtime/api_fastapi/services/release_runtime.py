from __future__ import annotations

"""Worker-owned release runtime with a process-isolated metadata boundary.

FastAPI is read/admission only.  The worker owns scheduling and durable release
leases.  Network metadata parsing and other allocation-heavy release work run
in a bounded subprocess.  SQLite stores one compact prepared projection and
rejects stale completions by generation and worker identity.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time
from typing import Any, Callable, Mapping

from ..db.connection import begin_immediate, connection, read_connection

_OWNER = "release"
_SCHEMA_VERSION = 1
_MAX_PREPARED_BYTES = 64 * 1024
_PROCESS_GENERATION = os.environ.get("POCKETLAB_RELEASE_WORKER_GENERATION", "").strip() or (
    f"{os.getpid()}-{secrets.token_hex(8)}"
)
_PROCESS_LOCK = threading.RLock()
_PROCESS_STATE: dict[str, Any] = {
    "process_alive": False,
    "process_pid": 0,
    "active_operation": "",
    "started_at": "",
    "last_completed_at": "",
    "last_error_type": "",
    "last_error_at": "",
}
_OPERATION_LOCK: asyncio.Lock | None = None

_SECRET_KEYS = {
    "authorization",
    "api_key",
    "token",
    "password",
    "secret",
    "cookie",
    "headers",
}


class ReleaseRuntimeError(RuntimeError):
    pass


class ReleaseOwnershipError(ReleaseRuntimeError):
    pass


class ReleaseOperationInProgress(ReleaseRuntimeError):
    pass


class ReleaseStaleResult(ReleaseRuntimeError):
    pass


class ReleaseSubprocessError(ReleaseRuntimeError):
    def __init__(
        self,
        code: str,
        message: str = "Release subprocess failed",
        *,
        metrics: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code or "release_subprocess_failed")[:80]
        self.metrics = dict(metrics or {})


@dataclass(frozen=True)
class ReleaseLease:
    claimed: bool
    generation: int
    operation: str
    command_id: str
    worker_generation: str
    coalesced: bool = False
    deduplicated: bool = False
    retry_after_seconds: int = 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_ms() -> int:
    return int(time.time() * 1000)


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


def _process_role() -> str:
    return str(os.environ.get("POCKETLAB_PROCESS_ROLE", "api") or "api").strip().lower()


def execution_allowed() -> bool:
    return _process_role() == "worker"


def _require_worker() -> None:
    if not execution_allowed():
        raise ReleaseOwnershipError("release_execution_is_worker_owned")


def worker_generation() -> str:
    return _PROCESS_GENERATION


def _operation_lock() -> asyncio.Lock:
    global _OPERATION_LOCK
    if _OPERATION_LOCK is None:
        _OPERATION_LOCK = asyncio.Lock()
    return _OPERATION_LOCK


def _ensure_row(conn: sqlite3.Connection) -> None:
    now = _utc_now()
    conn.execute(
        """
        INSERT OR IGNORE INTO release_runtime_projection(
            owner, schema_version, phase, status, current_tag, latest_tag,
            update_available, payload_json, payload_bytes, created_at, updated_at,
            updated_at_epoch_ms
        ) VALUES (?, ?, 'unknown', 'degraded', 'unknown', 'unknown', 0, '{}', 2, ?, ?, ?)
        """,
        (_OWNER, _SCHEMA_VERSION, now, now, _epoch_ms()),
    )


def initialize_release_runtime() -> None:
    from ..db.migrations import apply_migrations

    apply_migrations()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _ensure_row(tx)


def _safe_text(value: Any, limit: int = 240) -> str:
    return str(value or "").replace("\x00", " ").strip()[:limit]


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in list(value.items())[:64]:
            name = _safe_text(key, 80)
            if not name or name.lower() in _SECRET_KEYS:
                continue
            result[name] = _sanitize(child, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, depth=depth + 1) for item in list(value)[:64]]
    if isinstance(value, str):
        return _safe_text(value, 2048)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_text(value, 160)


def _canonical_release(payload: Mapping[str, Any]) -> dict[str, Any]:
    latest = payload.get("latest_release") if isinstance(payload.get("latest_release"), Mapping) else {}
    asset = latest.get("artifact") if isinstance(latest.get("artifact"), Mapping) else {}
    operations = payload.get("operations") if isinstance(payload.get("operations"), list) else []
    compact_operations: list[dict[str, Any]] = []
    for item in operations[:16]:
        if not isinstance(item, Mapping):
            continue
        compact_operations.append(
            {
                "operation": _safe_text(item.get("operation"), 80),
                "stage": _safe_text(item.get("stage"), 80),
                "status": _safe_text(item.get("status"), 32),
                "job_id": _safe_text(item.get("job_id"), 120) or None,
            }
        )
    return {
        "phase": _safe_text(payload.get("phase") or "unknown", 32),
        "current_tag": _safe_text(payload.get("current_tag") or "unknown", 120),
        "latest_tag": _safe_text(payload.get("latest_tag") or "unknown", 120),
        "update_available": bool(payload.get("update_available")),
        "auto_apply": bool(payload.get("auto_apply")),
        "latest_release": {
            "tag_name": _safe_text(latest.get("tag_name"), 120),
            "name": _safe_text(latest.get("name"), 240),
            "html_url": _safe_text(latest.get("html_url"), 1024),
            "published_at": _safe_text(latest.get("published_at"), 80) or None,
            "draft": bool(latest.get("draft")),
            "prerelease": bool(latest.get("prerelease")),
            "body_excerpt": _safe_text(latest.get("body_excerpt"), 1024),
            "artifact": {
                "name": _safe_text(asset.get("name"), 240),
                "size": max(0, int(asset.get("size") or 0)),
                "digest": _safe_text(asset.get("digest"), 160),
                "verification_status": _safe_text(
                    asset.get("verification_status") or "metadata_only", 40
                ),
            },
        },
        "applied_release": _sanitize(payload.get("applied_release") or {}),
        "operations": compact_operations,
        "last_known_good": bool(payload.get("last_known_good", True)),
        "sanitized": True,
    }


def _encode_canonical(payload: Mapping[str, Any]) -> tuple[dict[str, Any], str, str, int]:
    canonical = _canonical_release(payload)
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    size = len(encoded.encode("utf-8"))
    limit = _bounded_int(
        "POCKETLAB_RELEASE_PREPARED_MAX_BYTES",
        _MAX_PREPARED_BYTES,
        4 * 1024,
        256 * 1024,
    )
    if size > limit:
        raise ReleaseRuntimeError("release_prepared_projection_too_large")
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return canonical, encoded, digest, size


def _read_row() -> dict[str, Any] | None:
    try:
        with read_connection() as conn:
            row = conn.execute(
                "SELECT * FROM release_runtime_projection WHERE owner = ?", (_OWNER,)
            ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return None
        raise
    return dict(row) if row else None


def _row_payload(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "phase": "unknown",
            "status": "degraded",
            "current_tag": "unknown",
            "latest_tag": "unknown",
            "update_available": False,
            "auto_apply": False,
            "last_known_good": False,
            "reason": "release_projection_unavailable",
            "retry_after_seconds": 30,
            "execution_owner": "pocket-worker/release-subprocess",
            "api_thread_started": False,
            "prepared_read_only": True,
            "sanitized": True,
        }
    try:
        payload = json.loads(str(row.get("payload_json") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update(
        {
            "phase": str(row.get("phase") or payload.get("phase") or "unknown"),
            "status": str(row.get("status") or "degraded"),
            "current_tag": str(row.get("current_tag") or payload.get("current_tag") or "unknown"),
            "latest_tag": str(row.get("latest_tag") or payload.get("latest_tag") or "unknown"),
            "update_available": bool(row.get("update_available")),
            "projection_revision": int(row.get("projection_revision") or 0),
            "operation_generation": int(row.get("operation_generation") or 0),
            "active_generation": int(row.get("active_generation") or 0),
            "active_operation": str(row.get("active_operation") or ""),
            "active_command_id": str(row.get("active_command_id") or ""),
            "last_checked_at": row.get("last_checked_at"),
            "last_success_at": row.get("last_success_at"),
            "last_failure_at": row.get("last_failure_at"),
            "last_failure_code": str(row.get("last_failure_code") or ""),
            "last_terminal_command_id": str(row.get("last_terminal_command_id") or ""),
            "last_terminal_status": str(row.get("last_terminal_status") or ""),
            "last_terminal_generation": int(row.get("last_terminal_generation") or 0),
            "data_source": "prepared_sqlite",
            "execution_owner": "pocket-worker/release-subprocess",
            "api_thread_started": False,
            "prepared_read_only": True,
            "sanitized": True,
        }
    )
    if payload["status"] == "degraded":
        payload.setdefault("last_known_good", bool(row.get("canonical_hash")))
        payload.setdefault("reason", payload["last_failure_code"] or "release_worker_unavailable")
        payload.setdefault("retry_after_seconds", 30)
    return payload


def read_release_status() -> dict[str, Any]:
    return _row_payload(_read_row())


def claim_release_operation(
    operation: str,
    command_id: str,
    *,
    lease_seconds: int | None = None,
) -> ReleaseLease:
    _require_worker()
    operation = _safe_text(operation, 32)
    command_id = _safe_text(command_id, 160) or f"release-{secrets.token_hex(8)}"
    bounded_lease = lease_seconds or _bounded_int(
        "POCKETLAB_RELEASE_LEASE_SECONDS", 120, 30, 3600
    )
    now_ms = _epoch_ms()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _ensure_row(tx)
            row = tx.execute(
                "SELECT * FROM release_runtime_projection WHERE owner = ?", (_OWNER,)
            ).fetchone()
            assert row is not None
            if (
                str(row["last_terminal_command_id"] or "") == command_id
                and str(row["last_terminal_status"] or "")
            ):
                tx.execute(
                    "UPDATE release_runtime_projection SET deduplicated_requests = deduplicated_requests + 1, updated_at = ?, updated_at_epoch_ms = ? WHERE owner = ?",
                    (_utc_now(), now_ms, _OWNER),
                )
                return ReleaseLease(
                    claimed=False,
                    generation=int(row["last_terminal_generation"] or 0),
                    operation=operation,
                    command_id=command_id,
                    worker_generation=str(row["worker_generation"] or _PROCESS_GENERATION),
                    deduplicated=True,
                    retry_after_seconds=0,
                )
            active_generation = int(row["active_generation"] or 0)
            lease_expires = int(row["lease_expires_epoch_ms"] or 0)
            active_command = str(row["active_command_id"] or "")
            active_worker = str(row["worker_generation"] or "")
            expired_takeover = bool(active_generation and lease_expires <= now_ms)
            if active_generation and lease_expires > now_ms:
                retry = max(1, int((lease_expires - now_ms + 999) / 1000))
                tx.execute(
                    "UPDATE release_runtime_projection SET coalesced_requests = coalesced_requests + 1, updated_at = ?, updated_at_epoch_ms = ? WHERE owner = ?",
                    (_utc_now(), now_ms, _OWNER),
                )
                return ReleaseLease(
                    claimed=False,
                    generation=active_generation,
                    operation=str(row["active_operation"] or operation),
                    command_id=active_command,
                    worker_generation=active_worker,
                    coalesced=True,
                    retry_after_seconds=retry,
                )
            generation = int(row["operation_generation"] or 0) + 1
            phase = "checking" if operation == "check" else "applying"
            counter = "checks_started" if operation == "check" else "applies_started"
            tx.execute(
                f"""
                UPDATE release_runtime_projection SET
                    operation_generation = ?, active_generation = ?, active_operation = ?,
                    active_command_id = ?, lease_expires_epoch_ms = ?, worker_generation = ?,
                    phase = ?, status = 'running', {counter} = {counter} + 1,
                    subprocess_restarts = subprocess_restarts + ?,
                    updated_at = ?, updated_at_epoch_ms = ?
                WHERE owner = ?
                """,
                (
                    generation,
                    generation,
                    operation,
                    command_id,
                    now_ms + bounded_lease * 1000,
                    _PROCESS_GENERATION,
                    phase,
                    1 if expired_takeover else 0,
                    _utc_now(),
                    now_ms,
                    _OWNER,
                ),
            )
    return ReleaseLease(
        claimed=True,
        generation=generation,
        operation=operation,
        command_id=command_id,
        worker_generation=_PROCESS_GENERATION,
    )


def renew_release_lease(lease: ReleaseLease, *, lease_seconds: int | None = None) -> bool:
    _require_worker()
    bounded_lease = lease_seconds or _bounded_int(
        "POCKETLAB_RELEASE_LEASE_SECONDS", 120, 30, 3600
    )
    now_ms = _epoch_ms()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            cursor = tx.execute(
                """
                UPDATE release_runtime_projection
                SET lease_expires_epoch_ms = ?, updated_at = ?, updated_at_epoch_ms = ?
                WHERE owner = ? AND active_generation = ? AND worker_generation = ?
                  AND lease_expires_epoch_ms >= ?
                """,
                (
                    now_ms + bounded_lease * 1000,
                    _utc_now(),
                    now_ms,
                    _OWNER,
                    lease.generation,
                    lease.worker_generation,
                    now_ms,
                ),
            )
    return cursor.rowcount == 1


def update_release_stage(
    lease: ReleaseLease,
    *,
    phase: str,
    status: str = "running",
) -> dict[str, Any]:
    _require_worker()
    now_ms = _epoch_ms()
    stale = False
    with connection() as conn:
        with begin_immediate(conn) as tx:
            cursor = tx.execute(
                """
                UPDATE release_runtime_projection
                SET phase = ?, status = ?, updated_at = ?, updated_at_epoch_ms = ?
                WHERE owner = ? AND active_generation = ? AND worker_generation = ?
                  AND lease_expires_epoch_ms >= ?
                """,
                (
                    _safe_text(phase, 32),
                    _safe_text(status, 24),
                    _utc_now(),
                    now_ms,
                    _OWNER,
                    lease.generation,
                    lease.worker_generation,
                    now_ms,
                ),
            )
            stale = cursor.rowcount != 1
    if stale:
        _record_stale_rejection()
        raise ReleaseStaleResult("release_generation_fence_rejected_stage")
    return read_release_status()

def _record_stale_rejection() -> None:
    now = _utc_now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                "UPDATE release_runtime_projection SET stale_results_rejected = stale_results_rejected + 1, updated_at = ?, updated_at_epoch_ms = ? WHERE owner = ?",
                (now, _epoch_ms(), _OWNER),
            )


def commit_release_result(
    lease: ReleaseLease,
    payload: Mapping[str, Any],
    *,
    subprocess_metrics: Mapping[str, Any] | None = None,
    complete_operation: bool = True,
) -> dict[str, Any]:
    _require_worker()
    canonical, encoded, digest, size = _encode_canonical(payload)
    metrics = dict(subprocess_metrics or {})
    now = _utc_now()
    now_ms = _epoch_ms()
    changed = False
    stale = False
    with connection() as conn:
        with begin_immediate(conn) as tx:
            row = tx.execute(
                "SELECT * FROM release_runtime_projection WHERE owner = ?", (_OWNER,)
            ).fetchone()
            stale = bool(
                row is None
                or int(row["active_generation"] or 0) != lease.generation
                or str(row["worker_generation"] or "") != lease.worker_generation
                or int(row["lease_expires_epoch_ms"] or 0) < now_ms
            )
            if not stale:
                changed = str(row["canonical_hash"] or "") != digest
                phase = str(canonical.get("phase") or "current")
                current_tag = str(canonical.get("current_tag") or "unknown")
                latest_tag = str(canonical.get("latest_tag") or "unknown")
                update_available = 1 if canonical.get("update_available") else 0
                operation_completed_counter = (
                    "checks_completed" if lease.operation == "check" else "applies_completed"
                )
                assignments = [
                    "phase = ?",
                    "status = 'healthy'",
                    "current_tag = ?",
                    "latest_tag = ?",
                    "update_available = ?",
                    "last_checked_at = ?",
                    "last_success_at = ?",
                    "last_failure_code = ''",
                    "last_terminal_command_id = ?",
                    "last_terminal_status = 'succeeded'",
                    "last_terminal_generation = ?",
                    f"{operation_completed_counter} = {operation_completed_counter} + 1",
                    "subprocess_recycles = subprocess_recycles + 1",
                    "last_subprocess_pid = ?",
                    "last_subprocess_exit_code = ?",
                    "last_cpu_ms = ?",
                    "last_wall_ms = ?",
                    "last_peak_rss_bytes = ?",
                    "last_bytes_read = ?",
                    "last_files_examined = ?",
                    "updated_at = ?",
                    "updated_at_epoch_ms = ?",
                ]
                values: list[Any] = [
                    phase,
                    current_tag,
                    latest_tag,
                    update_available,
                    now,
                    now,
                    lease.command_id,
                    lease.generation,
                    int(metrics.get("pid") or 0),
                    int(metrics.get("exit_code") or 0),
                    float(metrics.get("cpu_ms") or 0.0),
                    float(metrics.get("wall_ms") or 0.0),
                    int(metrics.get("peak_rss_bytes") or 0),
                    int(metrics.get("bytes_read") or 0),
                    int(metrics.get("files_examined") or 0),
                    now,
                    now_ms,
                ]
                if changed:
                    assignments.extend(
                        [
                            "projection_revision = projection_revision + 1",
                            "canonical_hash = ?",
                            "payload_json = ?",
                            "payload_bytes = ?",
                            "writes_committed = writes_committed + 1",
                        ]
                    )
                    values.extend([digest, encoded, size])
                else:
                    assignments.extend(
                        [
                            "unchanged_results = unchanged_results + 1",
                            "writes_skipped = writes_skipped + 1",
                        ]
                    )
                if complete_operation:
                    assignments.extend(
                        [
                            "active_generation = 0",
                            "active_operation = ''",
                            "active_command_id = ''",
                            "lease_expires_epoch_ms = 0",
                        ]
                    )
                values.extend([_OWNER, lease.generation, lease.worker_generation])
                cursor = tx.execute(
                    "UPDATE release_runtime_projection SET "
                    + ", ".join(assignments)
                    + " WHERE owner = ? AND active_generation = ? AND worker_generation = ? AND lease_expires_epoch_ms >= ?",
                    tuple(values + [now_ms]),
                )
                stale = cursor.rowcount != 1
    if stale:
        _record_stale_rejection()
        raise ReleaseStaleResult("release_generation_fence_rejected_result")
    result = read_release_status()
    result["changed"] = changed
    return result

def fail_release_operation(
    lease: ReleaseLease,
    *,
    failure_code: str,
    phase: str = "error",
    deadline_exceeded: bool = False,
    subprocess_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _require_worker()
    metrics = dict(subprocess_metrics or {})
    now = _utc_now()
    now_ms = _epoch_ms()
    stale = False
    with connection() as conn:
        with begin_immediate(conn) as tx:
            assignments = [
                "phase = ?",
                "status = 'degraded'",
                "last_failure_at = ?",
                "last_failure_code = ?",
                "last_terminal_command_id = ?",
                "last_terminal_status = 'failed'",
                "last_terminal_generation = ?",
                "subprocess_recycles = subprocess_recycles + 1",
                "last_subprocess_pid = ?",
                "last_subprocess_exit_code = ?",
                "last_cpu_ms = ?",
                "last_wall_ms = ?",
                "last_peak_rss_bytes = ?",
                "last_bytes_read = ?",
                "last_files_examined = ?",
                "active_generation = 0",
                "active_operation = ''",
                "active_command_id = ''",
                "lease_expires_epoch_ms = 0",
                "updated_at = ?",
                "updated_at_epoch_ms = ?",
            ]
            if deadline_exceeded:
                assignments.extend([
                    "deadline_exceeded = deadline_exceeded + 1",
                    "subprocess_restarts = subprocess_restarts + 1",
                ])
            values: list[Any] = [
                _safe_text(phase, 32),
                now,
                _safe_text(failure_code, 80),
                lease.command_id,
                lease.generation,
                int(metrics.get("pid") or 0),
                metrics.get("exit_code"),
                float(metrics.get("cpu_ms") or 0.0),
                float(metrics.get("wall_ms") or 0.0),
                int(metrics.get("peak_rss_bytes") or 0),
                int(metrics.get("bytes_read") or 0),
                int(metrics.get("files_examined") or 0),
                now,
                now_ms,
                _OWNER,
                lease.generation,
                lease.worker_generation,
            ]
            cursor = tx.execute(
                "UPDATE release_runtime_projection SET "
                + ", ".join(assignments)
                + " WHERE owner = ? AND active_generation = ? AND worker_generation = ? AND lease_expires_epoch_ms >= ?",
                tuple(values + [now_ms]),
            )
            stale = cursor.rowcount != 1
    if stale:
        _record_stale_rejection()
        raise ReleaseStaleResult("release_generation_fence_rejected_failure")
    return read_release_status()


def record_pressure_deferral(reason: str) -> dict[str, Any]:
    _require_worker()
    now = _utc_now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _ensure_row(tx)
            tx.execute(
                """
                UPDATE release_runtime_projection
                SET pressure_deferred = pressure_deferred + 1,
                    status = CASE WHEN canonical_hash = '' THEN 'degraded' ELSE status END,
                    last_failure_code = CASE WHEN canonical_hash = '' THEN ? ELSE last_failure_code END,
                    updated_at = ?, updated_at_epoch_ms = ?
                WHERE owner = ?
                """,
                (_safe_text(reason, 80), now, _epoch_ms(), _OWNER),
            )
    return read_release_status()


def release_runtime_diagnostics() -> dict[str, Any]:
    row = _read_row()
    payload = _row_payload(row)
    with _PROCESS_LOCK:
        process = dict(_PROCESS_STATE)
    if row is None:
        counters: dict[str, Any] = {}
    else:
        counters = {
            key: int(row.get(key) or 0)
            for key in (
                "checks_started",
                "checks_completed",
                "applies_started",
                "applies_completed",
                "unchanged_results",
                "writes_skipped",
                "writes_committed",
                "coalesced_requests",
                "deduplicated_requests",
                "pressure_deferred",
                "deadline_exceeded",
                "stale_results_rejected",
                "subprocess_restarts",
                "subprocess_recycles",
            )
        }
    return {
        "execution_owner": "pocket-worker/release-subprocess",
        "configured_owner": "worker",
        "process_role": _process_role(),
        "api_thread_started": False,
        "prepared_read_only": _process_role() == "api",
        "process_alive": bool(process.get("process_alive")),
        "process_pid": int(process.get("process_pid") or 0),
        "active_operation": str(process.get("active_operation") or payload.get("active_operation") or ""),
        "queue_depth": 1 if payload.get("active_generation") else 0,
        "queue_capacity": 1,
        "operation_generation": int(payload.get("operation_generation") or 0),
        "active_generation": int(payload.get("active_generation") or 0),
        "phase": payload.get("phase"),
        "status": payload.get("status"),
        "last_failure_code": payload.get("last_failure_code"),
        "last_cpu_ms": float(row.get("last_cpu_ms") or 0.0) if row else 0.0,
        "last_wall_ms": float(row.get("last_wall_ms") or 0.0) if row else 0.0,
        "last_peak_rss_bytes": int(row.get("last_peak_rss_bytes") or 0) if row else 0,
        "last_bytes_read": int(row.get("last_bytes_read") or 0) if row else 0,
        "last_files_examined": int(row.get("last_files_examined") or 0) if row else 0,
        **counters,
        "sanitized": True,
    }


def _memory_pressure_reason() -> str:
    minimum_percent = _bounded_float(
        "POCKETLAB_RELEASE_MEMORY_MIN_AVAILABLE_PERCENT", 7.0, 1.0, 50.0
    )
    try:
        total = available = 0
        for line in Path("/proc/meminfo").read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available = int(line.split()[1])
        if total > 0 and (available / total * 100.0) < minimum_percent:
            return "memory_pressure"
    except (OSError, ValueError, IndexError):
        return ""
    return ""


def release_admission_reason() -> str:
    return _memory_pressure_reason()


def _set_process_state(**fields: Any) -> None:
    with _PROCESS_LOCK:
        _PROCESS_STATE.update(fields)


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "POCKETLAB_PROCESS_ROLE": "release-subprocess",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "BLIS_NUM_THREADS": "1",
            "PYTHONHASHSEED": "0",
        }
    )
    return env


async def execute_release_subprocess(
    operation: str,
    request_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_worker()
    operation = _safe_text(operation, 32)
    if operation not in {"check", "download", "verify"}:
        raise ReleaseRuntimeError("unsupported_release_subprocess_operation")
    body = json.dumps(
        {"operation": operation, **_sanitize(dict(request_payload))},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    if len(body) > 64 * 1024:
        raise ReleaseRuntimeError("release_subprocess_request_too_large")
    timeout = _bounded_float(
        "POCKETLAB_RELEASE_SUBPROCESS_TIMEOUT_SECONDS", 20.0, 2.0, 300.0
    )
    started = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "api_fastapi.services.release_update_process",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_subprocess_env(),
        start_new_session=(os.name != "nt"),
        limit=128 * 1024,
    )
    _set_process_state(
        process_alive=True,
        process_pid=int(process.pid or 0),
        active_operation=operation,
        started_at=_utc_now(),
        last_error_type="",
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(body), timeout=timeout)
    except asyncio.CancelledError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        _set_process_state(
            process_alive=False,
            process_pid=0,
            active_operation="",
            last_completed_at=_utc_now(),
            last_error_type="CancelledError",
            last_error_at=_utc_now(),
        )
        raise
    except asyncio.TimeoutError as exc:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        metrics = {
            "pid": int(process.pid or 0),
            "exit_code": process.returncode,
            "wall_ms": round((time.monotonic() - started) * 1000.0, 3),
        }
        _set_process_state(
            process_alive=False,
            process_pid=0,
            active_operation="",
            last_completed_at=_utc_now(),
            last_error_type="TimeoutError",
            last_error_at=_utc_now(),
        )
        raise ReleaseSubprocessError(
            "release_subprocess_timeout",
            "Release subprocess exceeded its deadline",
            metrics=metrics,
        ) from exc
    finally:
        if process.returncode is not None:
            _set_process_state(
                process_alive=False,
                process_pid=0,
                active_operation="",
                last_completed_at=_utc_now(),
            )
    wall_ms = round((time.monotonic() - started) * 1000.0, 3)
    if len(stdout) > 128 * 1024:
        raise ReleaseSubprocessError(
            "release_subprocess_output_too_large",
            metrics={
                "pid": int(process.pid or 0),
                "exit_code": process.returncode,
                "wall_ms": wall_ms,
            },
        )
    try:
        envelope = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _set_process_state(last_error_type=type(exc).__name__, last_error_at=_utc_now())
        raise ReleaseSubprocessError(
            "release_subprocess_invalid_output",
            metrics={
                "pid": int(process.pid or 0),
                "exit_code": process.returncode,
                "wall_ms": wall_ms,
            },
        ) from exc
    if not isinstance(envelope, dict):
        raise ReleaseSubprocessError("release_subprocess_invalid_output")
    child_metrics = envelope.get("metrics") if isinstance(envelope.get("metrics"), dict) else {}
    metrics = {
        "pid": int(process.pid or 0),
        "exit_code": int(process.returncode or 0),
        "wall_ms": float(child_metrics.get("wall_ms") or wall_ms),
        "cpu_ms": float(child_metrics.get("cpu_ms") or 0.0),
        "peak_rss_bytes": int(child_metrics.get("peak_rss_bytes") or 0),
        "bytes_read": int(child_metrics.get("bytes_read") or 0),
        "files_examined": int(child_metrics.get("files_examined") or 0),
    }
    if process.returncode != 0 or not bool(envelope.get("ok")):
        code = _safe_text(envelope.get("error_code") or "release_subprocess_failed", 80)
        _set_process_state(last_error_type=code, last_error_at=_utc_now())
        raise ReleaseSubprocessError(code, metrics=metrics)
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise ReleaseSubprocessError(
            "release_subprocess_missing_result", metrics=metrics
        )
    return _sanitize(result), metrics


def build_check_request() -> dict[str, Any]:
    return {
        "source_url": str(
            os.environ.get(
                "POCKETLAB_GITHUB_RELEASES_API",
                "https://api.github.com/repos/"
                + str(
                    os.environ.get(
                        "POCKETLAB_GITHUB_REPO", "dexter-lab-ctrl/pocket-lab"
                    )
                ).strip()
                + "/releases/latest",
            )
        ),
        "current_tag": str(os.environ.get("POCKETLAB_RELEASE_TAG", "v1.0.0")),
        "auto_apply": str(os.environ.get("POCKETLAB_AUTO_RELEASE_APPLY", "true")).lower()
        in {"1", "true", "yes", "on"},
        "artifact_name": str(
            os.environ.get("POCKETLAB_RELEASE_ARTIFACT_NAME", "dist.zip")
        ),
        "network_timeout_seconds": _bounded_float(
            "POCKETLAB_RELEASE_NETWORK_TIMEOUT_SECONDS", 10.0, 1.0, 60.0
        ),
        "max_metadata_bytes": _bounded_int(
            "POCKETLAB_RELEASE_METADATA_MAX_BYTES", 2 * 1024 * 1024, 16 * 1024, 8 * 1024 * 1024
        ),
    }


async def run_release_check(
    command_id: str,
    *,
    source: str = "manual",
    existing_lease: ReleaseLease | None = None,
) -> dict[str, Any]:
    _require_worker()
    async with _operation_lock():
        lease = existing_lease or claim_release_operation("check", command_id)
        if not lease.claimed:
            status = read_release_status()
            return {
                **status,
                "coalesced": bool(lease.coalesced),
                "deduplicated": bool(lease.deduplicated),
                "retry_after_seconds": lease.retry_after_seconds,
            }
        reason = release_admission_reason()
        if reason:
            record_pressure_deferral(reason)
            return fail_release_operation(
                lease,
                failure_code=reason,
                phase="waiting",
            )
        metrics: dict[str, Any] = {}
        try:
            result, metrics = await execute_release_subprocess("check", build_check_request())
            payload = {
                **result,
                "phase": "available" if result.get("update_available") else "current",
                "last_known_good": True,
                "source": _safe_text(source, 32),
            }
            return commit_release_result(lease, payload, subprocess_metrics=metrics)
        except ReleaseSubprocessError as exc:
            return fail_release_operation(
                lease,
                failure_code=exc.code,
                phase="error",
                deadline_exceeded=exc.code == "release_subprocess_timeout",
                subprocess_metrics=exc.metrics or metrics,
            )
        except Exception as exc:
            return fail_release_operation(
                lease,
                failure_code=type(exc).__name__,
                phase="error",
                subprocess_metrics=metrics,
            )


async def begin_release_apply(command_id: str) -> ReleaseLease:
    _require_worker()
    async with _operation_lock():
        return claim_release_operation("apply", command_id, lease_seconds=_bounded_int(
            "POCKETLAB_RELEASE_APPLY_LEASE_SECONDS", 1800, 120, 7200
        ))


async def check_for_apply(lease: ReleaseLease) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_worker()
    if not lease.claimed or lease.operation != "apply":
        raise ReleaseOwnershipError("invalid_release_apply_lease")
    if not renew_release_lease(lease, lease_seconds=_bounded_int(
        "POCKETLAB_RELEASE_APPLY_LEASE_SECONDS", 1800, 120, 7200
    )):
        raise ReleaseStaleResult("release_apply_lease_lost")
    update_release_stage(lease, phase="checking")
    return await execute_release_subprocess("check", build_check_request())


def finalize_release_apply(
    lease: ReleaseLease,
    payload: Mapping[str, Any],
    *,
    subprocess_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return commit_release_result(
        lease,
        payload,
        subprocess_metrics=subprocess_metrics,
        complete_operation=True,
    )


def fail_release_apply(
    lease: ReleaseLease,
    failure_code: str,
    *,
    subprocess_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return fail_release_operation(
        lease,
        failure_code=failure_code,
        phase="error",
        subprocess_metrics=subprocess_metrics,
    )


def compatibility_update_state(**fields: Any) -> dict[str, Any]:
    """Compatibility-only prepared update for legacy callers in worker role.

    It is deliberately unavailable in FastAPI and never starts background work.
    New release execution must use generation-fenced functions above.
    """
    _require_worker()
    lease = claim_release_operation("apply", f"compat-{secrets.token_hex(8)}")
    if not lease.claimed:
        raise ReleaseOperationInProgress("release_operation_in_progress")
    current = read_release_status()
    return finalize_release_apply(lease, {**current, **fields})
