from __future__ import annotations

"""Compact worker-owned runtime diagnostics snapshots.

The worker publishes one sanitized, bounded, pre-encoded JSON object. FastAPI
serves that object from a short-lived row cache without rebuilding the worker
payload on the event loop.
"""

from datetime import datetime, timezone
import json
import os
import threading
import time
from typing import Any

from ..db.connection import begin_immediate, connection, read_connection

_SCHEMA_VERSION = 1
_MAX_PAYLOAD_BYTES = 256 * 1024
_OWNER = "worker"
_CACHE_TTL_SECONDS = 1.0
_CACHE_LOCK = threading.Lock()
_RAW_CACHE_EXPIRES_AT = 0.0
_RAW_CACHE_ROW: dict[str, Any] | None = None
_RESPONSE_CACHE_KEY: tuple[int, int] | None = None
_RESPONSE_CACHE_EXPIRES_AT = 0.0
_RESPONSE_CACHE_BYTES: bytes | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _ensure_table(conn: Any) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_diagnostics_snapshot (
            owner TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            snapshot_revision INTEGER NOT NULL DEFAULT 0,
            captured_at TEXT NOT NULL,
            captured_at_epoch_ms INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            payload_bytes INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(runtime_diagnostics_snapshot)")
    }
    if "snapshot_revision" not in columns:
        conn.execute(
            "ALTER TABLE runtime_diagnostics_snapshot "
            "ADD COLUMN snapshot_revision INTEGER NOT NULL DEFAULT 0"
        )


def _invalidate_caches() -> None:
    global _RAW_CACHE_EXPIRES_AT, _RAW_CACHE_ROW
    global _RESPONSE_CACHE_KEY, _RESPONSE_CACHE_EXPIRES_AT, _RESPONSE_CACHE_BYTES
    with _CACHE_LOCK:
        _RAW_CACHE_EXPIRES_AT = 0.0
        _RAW_CACHE_ROW = None
        _RESPONSE_CACHE_KEY = None
        _RESPONSE_CACHE_EXPIRES_AT = 0.0
        _RESPONSE_CACHE_BYTES = None


def publish_worker_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist one pre-encoded worker snapshot and advance its revision."""
    safe = dict(payload)
    safe.update({"schema_version": _SCHEMA_VERSION, "owner": _OWNER, "sanitized": True})
    captured_at = str(safe.get("captured_at") or _utc_now())
    encoded = json.dumps(
        safe, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    encoded_bytes = encoded.encode("utf-8")
    size = len(encoded_bytes)
    limit = _bounded_int(
        "POCKETLAB_RUNTIME_SNAPSHOT_MAX_BYTES",
        _MAX_PAYLOAD_BYTES,
        16 * 1024,
        1024 * 1024,
    )
    if size > limit:
        raise ValueError("runtime_diagnostics_snapshot_too_large")

    now_ms = int(time.time() * 1000)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _ensure_table(tx)
            tx.execute(
                """
                INSERT INTO runtime_diagnostics_snapshot(
                    owner, schema_version, snapshot_revision, captured_at,
                    captured_at_epoch_ms, payload_json, payload_bytes, updated_at
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(owner) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    snapshot_revision=runtime_diagnostics_snapshot.snapshot_revision + 1,
                    captured_at=excluded.captured_at,
                    captured_at_epoch_ms=excluded.captured_at_epoch_ms,
                    payload_json=excluded.payload_json,
                    payload_bytes=excluded.payload_bytes,
                    updated_at=excluded.updated_at
                """,
                (
                    _OWNER,
                    _SCHEMA_VERSION,
                    captured_at,
                    now_ms,
                    encoded,
                    size,
                    _utc_now(),
                ),
            )
            revision_row = tx.execute(
                "SELECT snapshot_revision FROM runtime_diagnostics_snapshot WHERE owner = ?",
                (_OWNER,),
            ).fetchone()
    _invalidate_caches()
    return {
        "captured_at": captured_at,
        "payload_bytes": size,
        "snapshot_revision": int(revision_row[0]) if revision_row else 0,
        "sanitized": True,
    }


def _read_raw_worker_row() -> dict[str, Any] | None:
    """Read the pre-encoded row with a one-second process-local cache."""
    global _RAW_CACHE_EXPIRES_AT, _RAW_CACHE_ROW
    now = time.monotonic()
    with _CACHE_LOCK:
        if _RAW_CACHE_ROW is not None and now < _RAW_CACHE_EXPIRES_AT:
            return dict(_RAW_CACHE_ROW)

    with read_connection() as conn:
        _ensure_table(conn)
        row = conn.execute(
            """
            SELECT snapshot_revision, captured_at, captured_at_epoch_ms,
                   payload_json, payload_bytes, updated_at
            FROM runtime_diagnostics_snapshot
            WHERE owner = ?
            """,
            (_OWNER,),
        ).fetchone()
    if not row:
        return None

    result = {
        "snapshot_revision": int(row["snapshot_revision"] or 0),
        "captured_at": str(row["captured_at"]),
        "captured_at_epoch_ms": int(row["captured_at_epoch_ms"]),
        "payload_json": str(row["payload_json"]),
        "payload_bytes": int(row["payload_bytes"]),
        "updated_at": str(row["updated_at"]),
    }
    with _CACHE_LOCK:
        _RAW_CACHE_ROW = dict(result)
        _RAW_CACHE_EXPIRES_AT = now + _CACHE_TTL_SECONDS
    return result


def read_worker_snapshot() -> dict[str, Any] | None:
    """Compatibility decoded read for explicit diagnostics/debug consumers."""
    row = _read_raw_worker_row()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload["snapshot_revision"] = row["snapshot_revision"]
    payload["snapshot_age_ms"] = max(
        0, int(time.time() * 1000) - row["captured_at_epoch_ms"]
    )
    payload["payload_bytes"] = row["payload_bytes"]
    payload["data_source"] = "prepared_sqlite"
    payload["sanitized"] = True
    return payload


def _append_top_level_fields(encoded_object: str, fields: dict[str, Any]) -> bytes:
    """Append small top-level fields without decoding the worker JSON object."""
    stripped = encoded_object.rstrip()
    if not stripped.endswith("}"):
        raise ValueError("runtime_diagnostics_snapshot_invalid_json_object")
    suffix = json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    # Convert {"field":...} to ,"field":...} and retain the prepared prefix.
    return (stripped[:-1] + "," + suffix[1:]).encode("utf-8")


def encoded_runtime_response(event_loop: dict[str, Any]) -> bytes:
    """Return cached response bytes built from the worker's pre-encoded payload.

    SQLite I/O is expected to run through ``asyncio.to_thread`` in the route.
    Cache invalidation is driven by the worker snapshot revision.
    """
    global _RESPONSE_CACHE_KEY, _RESPONSE_CACHE_EXPIRES_AT, _RESPONSE_CACHE_BYTES
    row = _read_raw_worker_row()
    now = time.monotonic()

    if row is None:
        revision = 0
        age_bucket = 0
        payload = {
            "event_loop": event_loop,
            "projection_scheduler": {
                "status": "starting",
                "projection_execution_owner": "worker",
                "is_execution_owner": False,
                "queued_domains": 0,
                "active_domains": 0,
                "queue": {
                    "executor_depth": 0,
                    "ready_executor_depth": 0,
                    "scheduled_future_depth": 0,
                    "followup_domains": 0,
                    "active_domains": 0,
                    "durable_pending": 0,
                    "unregistered": 0,
                },
            },
            "adaptive_runtime": {},
            "process_runtime": {},
            "hot_path": {},
            "snapshot_status": "unavailable",
            "snapshot_revision": 0,
            "retry_after_ms": 1000,
            "data_source": "api_local_fallback",
            "sanitized": True,
        }
        cache_key = (revision, age_bucket)
        with _CACHE_LOCK:
            if (
                _RESPONSE_CACHE_KEY == cache_key
                and _RESPONSE_CACHE_BYTES is not None
                and now < _RESPONSE_CACHE_EXPIRES_AT
            ):
                return _RESPONSE_CACHE_BYTES
            encoded = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            _RESPONSE_CACHE_KEY = cache_key
            _RESPONSE_CACHE_EXPIRES_AT = now + _CACHE_TTL_SECONDS
            _RESPONSE_CACHE_BYTES = encoded
            return encoded

    age_ms = max(0, int(time.time() * 1000) - row["captured_at_epoch_ms"])
    revision = int(row["snapshot_revision"])
    # Age changes are intentionally bucketed to the response-cache TTL. The
    # worker revision remains the authoritative invalidation signal.
    age_bucket = age_ms // 1000
    cache_key = (revision, age_bucket)
    with _CACHE_LOCK:
        if (
            _RESPONSE_CACHE_KEY == cache_key
            and _RESPONSE_CACHE_BYTES is not None
            and now < _RESPONSE_CACHE_EXPIRES_AT
        ):
            return _RESPONSE_CACHE_BYTES

    encoded = _append_top_level_fields(
        row["payload_json"],
        {
            "event_loop": event_loop,
            "snapshot_revision": revision,
            "snapshot_age_ms": age_ms,
            "payload_bytes": row["payload_bytes"],
            "snapshot_status": "fresh" if age_ms <= 30000 else "stale",
            "data_source": "prepared_sqlite",
        },
    )
    with _CACHE_LOCK:
        _RESPONSE_CACHE_KEY = cache_key
        _RESPONSE_CACHE_EXPIRES_AT = now + _CACHE_TTL_SECONDS
        _RESPONSE_CACHE_BYTES = encoded
    return encoded
