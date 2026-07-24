#!/usr/bin/env python3
from __future__ import annotations

"""Dry-run-first import of bounded compatibility lifecycle JSON into SQLite.

SQLite remains authoritative. The compatibility JSON is canonicalized only after
an explicit --apply and after SQLite parity, quick_check and foreign-key checks
pass inside one BEGIN IMMEDIATE transaction.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

MAX_EVENTS = 500
ONE_TIME_TYPES = {
    "first_heartbeat_received",
    "first_supervisor_heartbeat",
    "first_supervisor_heartbeat_received",
    "invite_accepted",
    "first_ready",
}
REPEATABLE_TYPES = {
    "device_returned_online",
    "connection_lost",
    "repair_started",
    "repair_completed",
    "repair_failed",
    "recovery_started",
    "recovery_completed",
    "recovery_failed",
    "removal_requested",
    "removal_completed",
    "stale_device_cleanup",
}
SAFE_EVENT = re.compile(r"^[a-z0-9_.-]{1,80}$")
SECRET_TEXT = re.compile(
    r"(?:token|password|secret|credential|api[_-]?key|private[_-]?key|bearer\s+|authorization\s*[:=]|auth\s*[:=])",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _safe_key(value: Any, limit: int) -> str:
    text = _safe_text(value, limit)
    return "" if SECRET_TEXT.search(text) else text


def _safe_summary(value: Any) -> str:
    text = _safe_text(value or "Device activity recorded.", 240)
    if SECRET_TEXT.search(text):
        return "Protected lifecycle metadata recorded."
    return text or "Device activity recorded."


def _timestamp(value: Any) -> tuple[str, int] | None:
    raw = _safe_text(value, 64)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), int(parsed.timestamp() * 1000)


def _normalize_type(value: Any) -> str:
    event_type = re.sub(r"[^a-z0-9_.-]+", "_", _safe_text(value, 80).lower())
    return event_type if SAFE_EVENT.fullmatch(event_type) else "device_activity"


def _canonical_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    device_id = re.sub(
        r"[^a-z0-9_.-]+", "-",
        _safe_text(raw.get("device_id") or raw.get("node_id"), 120).lower(),
    ).strip("-._")
    if not device_id or device_id == "unknown-node":
        return None
    event_type = _normalize_type(raw.get("event_type"))
    parsed = _timestamp(raw.get("occurred_at") or raw.get("created_at"))
    if parsed is None:
        return None
    occurred_at, occurred_epoch_ms = parsed
    generation_key = _safe_key(raw.get("generation_key"), 160)
    dedupe_key = _safe_key(raw.get("dedupe_key"), 240)
    normalized_one_time = (
        "first_supervisor_heartbeat_received"
        if event_type == "first_supervisor_heartbeat" else event_type
    )
    if event_type in ONE_TIME_TYPES:
        dedupe_key = dedupe_key or f"{device_id}:{normalized_one_time}"
    elif event_type == "identity_verified":
        identity_revision = generation_key or (dedupe_key.rsplit(":", 1)[-1] if dedupe_key else "")
        if not identity_revision:
            return None
        generation_key = identity_revision
        dedupe_key = f"{device_id}:identity_verified:{identity_revision}"
    elif event_type in REPEATABLE_TYPES:
        if not generation_key:
            prefix = f"{device_id}:{event_type}:"
            generation_key = dedupe_key[len(prefix):] if dedupe_key.startswith(prefix) else ""
        if not generation_key:
            return None
        dedupe_key = f"{device_id}:{event_type}:{generation_key}"
    summary = _safe_summary(raw.get("summary"))
    reason_code = re.sub(r"[^a-z0-9_.-]+", "_", _safe_text(raw.get("reason_code"), 80).lower())
    status = re.sub(r"[^a-z0-9_.-]+", "_", _safe_text(raw.get("status") or "recorded", 32).lower())
    event_id = _safe_text(raw.get("event_id"), 120)
    material = json.dumps(
        [device_id, event_type, dedupe_key or generation_key or occurred_at, reason_code],
        separators=(",", ":"),
    )
    event_id = event_id or hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    payload = json.dumps(
        {
            "event_type": event_type,
            "reason_code": reason_code,
            "status": status,
            "summary": summary,
            "generation_key": generation_key or None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "event_id": event_id,
        "device_id": device_id,
        "node_id": device_id,
        "event_type": event_type,
        "reason_code": reason_code,
        "status": status or "recorded",
        "occurred_at": occurred_at,
        "created_at": occurred_at,
        "occurred_at_epoch_ms": occurred_epoch_ms,
        "summary": summary,
        "dedupe_key": dedupe_key or None,
        "generation_key": generation_key or None,
        "payload_checksum": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "sanitized": True,
    }


def _identity_key(event: dict[str, Any]) -> str:
    return str(event.get("dedupe_key") or event.get("event_id") or "")


def canonicalize(events: list[Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    normalized = [event for item in events if isinstance(item, dict) if (event := _canonical_event(item))]
    normalized.sort(key=lambda item: (item["occurred_at_epoch_ms"], item["event_id"]))
    kept: dict[str, dict[str, Any]] = {}
    invalid_or_duplicate = max(0, len(events) - len(normalized))
    duplicate_count = 0
    for event in normalized:
        key = _identity_key(event)
        if not key:
            invalid_or_duplicate += 1
            continue
        if key in kept:
            duplicate_count += 1
            continue
        kept[key] = event
    canonical = sorted(
        kept.values(),
        key=lambda item: (item["occurred_at_epoch_ms"], item["event_id"]),
        reverse=True,
    )[:MAX_EVENTS]
    return canonical, {
        "rows_seen": len(events),
        "canonical_rows": len(canonical),
        "duplicates_removed": duplicate_count,
        "invalid_rows_skipped": invalid_or_duplicate,
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _database_instance(database: Path) -> str:
    stat = database.stat()
    return f"{database}:{stat.st_dev}:{stat.st_ino}"


def _require_schema(conn: sqlite3.Connection) -> None:
    version = int(conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0])
    if version < 14:
        raise RuntimeError("migration 0014 must be applied before lifecycle reconciliation")
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(device_lifecycle_events)")}
    required = {"dedupe_key", "generation_key", "state_revision", "database_instance", "payload_checksum"}
    if not required.issubset(columns):
        raise RuntimeError("SQLite lifecycle schema is incomplete")


def _integrity(conn: sqlite3.Connection) -> tuple[str, int]:
    quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    foreign = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    return quick, foreign


def _ensure_device(conn: sqlite3.Connection, event: dict[str, Any], server_node_id: str, now: str) -> int:
    device_id = event["device_id"]
    row = conn.execute("SELECT source_revision FROM device_current_state WHERE device_id=?", (device_id,)).fetchone()
    if row:
        return max(1, int(row[0] or 0))
    protected = int(device_id == server_node_id)
    role = "server_host" if protected else "compute"
    conn.execute(
        """
        INSERT INTO device_current_state(
            device_id,device_name,role,ui_state,connection_state,agent_status,
            supervisor_status,pm2_status,remote_access_ready,protected_server_host,
            source_revision,last_seen_at,last_seen_epoch_ms,updated_at,updated_at_epoch_ms,summary
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            device_id, device_id, role, "Protected server host" if protected else "Waiting",
            "unknown", "unknown", "unknown", "unknown", 0, protected, 1,
            event["occurred_at"], event["occurred_at_epoch_ms"], now,
            int(datetime.now(timezone.utc).timestamp() * 1000),
            "Lifecycle state imported from bounded compatibility evidence.",
        ),
    )
    return 1


def _sqlite_has(conn: sqlite3.Connection, event: dict[str, Any]) -> bool:
    if event.get("dedupe_key"):
        row = conn.execute(
            "SELECT payload_checksum FROM device_lifecycle_events WHERE dedupe_key=?",
            (event["dedupe_key"],),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT payload_checksum FROM device_lifecycle_events WHERE event_id=?",
            (event["event_id"],),
        ).fetchone()
    if not row:
        return False
    checksum = str(row[0] or "")
    return not checksum or checksum == event["payload_checksum"]


def reconcile(*, state_dir: Path, database: Path, apply: bool) -> dict[str, Any]:
    events_path = state_dir / "fleet_device_events.json"
    payload: dict[str, Any] = {"events": [], "updated_at": None}
    if events_path.exists():
        loaded = json.loads(events_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError("compatibility lifecycle JSON must be an object")
        payload = loaded
    rows = payload.get("events") if isinstance(payload.get("events"), list) else []
    canonical, stats = canonicalize(rows)
    result: dict[str, Any] = {
        "status": "ready",
        "mode": "apply" if apply else "dry_run",
        **stats,
        "database_exists": database.exists(),
        "imported_rows": 0,
        "already_present_rows": 0,
        "parity_matched": False,
        "quick_check": "not_run",
        "foreign_key_violations": 0,
        "sanitized": True,
    }
    if not database.exists():
        return result
    conn = sqlite3.connect(database, timeout=10.0)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        _require_schema(conn)
        quick, foreign = _integrity(conn)
        if quick != "ok" or foreign:
            raise RuntimeError("SQLite integrity check failed before reconciliation")
        result["quick_check"] = quick
        result["foreign_key_violations"] = foreign
        result["already_present_rows"] = sum(1 for event in canonical if _sqlite_has(conn, event))
        result["parity_matched"] = result["already_present_rows"] == len(canonical)
        if not apply:
            return result

        instance = _database_instance(database)
        server_node_id = re.sub(
            r"[^a-z0-9_.-]+", "-",
            _safe_text(os.environ.get("POCKETLAB_NODE_ID") or "pocket-lab-lite-server", 120).lower(),
        ).strip("-._")
        now = _now()
        conn.execute("BEGIN IMMEDIATE")
        imported = 0
        for event in reversed(canonical):
            if _sqlite_has(conn, event):
                continue
            state_revision = _ensure_device(conn, event, server_node_id, now)
            conn.execute(
                """
                INSERT INTO device_lifecycle_events(
                    event_id,device_id,event_type,reason_code,status,occurred_at,
                    occurred_at_epoch_ms,summary,sanitized,source_revision,dedupe_key,
                    generation_key,state_revision,database_instance,payload_checksum
                ) VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?,?,?)
                ON CONFLICT DO NOTHING
                """,
                (
                    event["event_id"], event["device_id"], event["event_type"],
                    event["reason_code"], event["status"], event["occurred_at"],
                    event["occurred_at_epoch_ms"], event["summary"], state_revision,
                    event.get("dedupe_key"), event.get("generation_key"), state_revision,
                    instance, event["payload_checksum"],
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                transaction_id = hashlib.sha256(
                    f"reconcile:{instance}:{event['device_id']}:{_identity_key(event)}".encode("utf-8")
                ).hexdigest()[:32]
                conn.execute(
                    """
                    INSERT OR IGNORE INTO device_lifecycle_transactions(
                        transaction_id,device_id,event_id,event_type,dedupe_key,generation_key,
                        state_revision,database_instance,status,export_status,export_attempts,
                        occurred_at,occurred_at_epoch_ms,created_at,updated_at,summary
                    ) VALUES (?,?,?,?,?,?,?,?,?,'exported',1,?,?,?,?,?)
                    """,
                    (
                        transaction_id, event["device_id"], event["event_id"], event["event_type"],
                        event.get("dedupe_key"), event.get("generation_key"), state_revision,
                        instance, "reconciled", event["occurred_at"], event["occurred_at_epoch_ms"],
                        now, now, event["summary"],
                    ),
                )
                imported += 1
        parity = all(_sqlite_has(conn, event) for event in canonical)
        quick, foreign = _integrity(conn)
        if not parity or quick != "ok" or foreign:
            conn.execute("ROLLBACK")
            raise RuntimeError("lifecycle reconciliation parity or integrity check failed")
        if imported:
            conn.execute(
                """
                INSERT INTO domain_revisions(domain,revision,updated_at) VALUES('fleet',1,?)
                ON CONFLICT(domain) DO UPDATE SET revision=domain_revisions.revision+1,updated_at=excluded.updated_at
                """,
                (now,),
            )
        conn.execute("COMMIT")
        result.update(
            imported_rows=imported,
            already_present_rows=len(canonical) - imported,
            parity_matched=True,
            quick_check=quick,
            foreign_key_violations=foreign,
        )
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    _atomic_write(events_path, {**payload, "events": canonical, "updated_at": _now()})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run or import bounded compatibility device lifecycle JSON into authoritative SQLite."
    )
    parser.add_argument("--apply", action="store_true", help="Apply import and canonical JSON rewrite. Default is dry-run.")
    parser.add_argument("--state-dir", help="Pocket Lab Lite state directory.")
    parser.add_argument("--database", help="SQLite database path. Defaults to <state-dir>/pocketlab-lite.sqlite3.")
    args = parser.parse_args()
    state = Path(args.state_dir or os.environ.get("POCKETLAB_STATE_DIR", str(Path.home() / "pocket-lab-lite/state"))).expanduser().resolve()
    database = Path(args.database).expanduser().resolve() if args.database else state / "pocketlab-lite.sqlite3"
    try:
        result = reconcile(state_dir=state, database=database, apply=bool(args.apply))
    except (OSError, ValueError, RuntimeError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "sanitized": True}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
