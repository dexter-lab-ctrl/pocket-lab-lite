from __future__ import annotations

"""Compact worker-owned runtime diagnostics snapshots.

The worker writes one sanitized bounded snapshot. FastAPI reads it without
calling worker-local collectors or serializing the full diagnostics tree.
"""

from datetime import datetime, timezone
import json
import os
import time
from typing import Any

from ..db.connection import begin_immediate, connection, read_connection

_SCHEMA_VERSION = 1
_MAX_PAYLOAD_BYTES = 256 * 1024
_OWNER = "worker"


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
            captured_at TEXT NOT NULL,
            captured_at_epoch_ms INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            payload_bytes INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

def publish_worker_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    safe = dict(payload)
    safe.update({"schema_version": _SCHEMA_VERSION, "owner": _OWNER, "sanitized": True})
    captured_at = str(safe.get("captured_at") or _utc_now())
    encoded = json.dumps(safe, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    size = len(encoded.encode("utf-8"))
    limit = _bounded_int("POCKETLAB_RUNTIME_SNAPSHOT_MAX_BYTES", _MAX_PAYLOAD_BYTES, 16 * 1024, 1024 * 1024)
    if size > limit:
        raise ValueError("runtime_diagnostics_snapshot_too_large")
    now_ms = int(time.time() * 1000)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            _ensure_table(tx)
            tx.execute(
                """
                INSERT INTO runtime_diagnostics_snapshot(
                    owner, schema_version, captured_at, captured_at_epoch_ms,
                    payload_json, payload_bytes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    captured_at=excluded.captured_at,
                    captured_at_epoch_ms=excluded.captured_at_epoch_ms,
                    payload_json=excluded.payload_json,
                    payload_bytes=excluded.payload_bytes,
                    updated_at=excluded.updated_at
                """,
                (_OWNER, _SCHEMA_VERSION, captured_at, now_ms, encoded, size, _utc_now()),
            )
    return {"captured_at": captured_at, "payload_bytes": size, "sanitized": True}


def read_worker_snapshot() -> dict[str, Any] | None:
    with read_connection() as conn:
        _ensure_table(conn)
        row = conn.execute(
            """
            SELECT captured_at, captured_at_epoch_ms, payload_json, payload_bytes
            FROM runtime_diagnostics_snapshot
            WHERE owner = ?
            """,
            (_OWNER,),
        ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(str(row["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    age_ms = max(0, int(time.time() * 1000) - int(row["captured_at_epoch_ms"]))
    payload["snapshot_age_ms"] = age_ms
    payload["payload_bytes"] = int(row["payload_bytes"])
    payload["data_source"] = "prepared_sqlite"
    payload["sanitized"] = True
    return payload
