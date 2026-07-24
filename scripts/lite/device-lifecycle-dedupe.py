#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ONE_TIME_TYPES = {"first_heartbeat_received", "first_supervisor_heartbeat"}
MAX_EVIDENCE_ROWS = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


def _state_dir(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return Path(os.environ.get("POCKETLAB_STATE_DIR", str(Path.home() / "pocket-lab-lite/state"))).expanduser().resolve()


def _semantic_key(event: dict[str, Any]) -> str | None:
    event_type = _safe_text(event.get("event_type"), 80).lower()
    device_id = _safe_text(event.get("device_id") or event.get("node_id"), 120).lower()
    if not device_id or event_type not in ONE_TIME_TYPES:
        return None
    return f"{device_id}:{event_type}"


def _sort_key(event: dict[str, Any]) -> tuple[str, str]:
    return (_safe_text(event.get("occurred_at") or event.get("created_at"), 64), _safe_text(event.get("event_id"), 120))


def _dedupe_events(events: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid = [dict(item) for item in events if isinstance(item, dict)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    untouched: list[dict[str, Any]] = []
    for event in valid:
        key = _semantic_key(event)
        if key is None:
            untouched.append(event)
        else:
            grouped.setdefault(key, []).append(event)

    kept = list(untouched)
    removed: list[dict[str, Any]] = []
    for key, group in grouped.items():
        ordered = sorted(group, key=_sort_key)
        winner = ordered[0]
        winner["dedupe_key"] = key
        kept.append(winner)
        removed.extend(ordered[1:])
    kept.sort(key=_sort_key, reverse=True)
    return kept[:500], removed


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _maintenance_evidence(state: Path, *, mode: str, removed_json: int, removed_sqlite: int) -> dict[str, Any]:
    occurred_at = _now()
    material = f"{occurred_at}:{mode}:{removed_json}:{removed_sqlite}"
    return {
        "maintenance_id": "device-lifecycle-dedupe-" + hashlib.sha256(material.encode()).hexdigest()[:16],
        "kind": "device_lifecycle_dedupe",
        "mode": mode,
        "status": "succeeded",
        "removed_json_rows": removed_json,
        "removed_sqlite_rows": removed_sqlite,
        "occurred_at": occurred_at,
        "sanitized": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or remove exact duplicate one-time device lifecycle evidence.")
    parser.add_argument("--apply", action="store_true", help="Apply the bounded cleanup. Default is dry-run.")
    parser.add_argument("--state-dir", help="Pocket Lab Lite state directory.")
    parser.add_argument("--database", help="SQLite database path. Defaults to <state-dir>/pocketlab-lite.sqlite3.")
    args = parser.parse_args()

    state = _state_dir(args.state_dir)
    events_path = state / "fleet_device_events.json"
    database = Path(args.database).expanduser().resolve() if args.database else state / "pocketlab-lite.sqlite3"

    payload: dict[str, Any] = {"events": [], "updated_at": None}
    if events_path.exists():
        try:
            loaded = json.loads(events_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "sanitized": True}))
            return 2
        if not isinstance(loaded, dict):
            print(json.dumps({"status": "failed", "error_type": "InvalidLifecyclePayload", "sanitized": True}))
            return 2
        payload = loaded

    kept, removed_json = _dedupe_events(payload.get("events") if isinstance(payload.get("events"), list) else [])
    removed_sqlite = 0
    sqlite_available = database.exists()

    if args.apply:
        if events_path.exists() or kept:
            _atomic_json_write(events_path, {**payload, "events": kept, "updated_at": _now()})
        if sqlite_available:
            with sqlite3.connect(database, timeout=5.0) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("PRAGMA busy_timeout=5000")
                if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite quick_check failed before lifecycle cleanup")
                columns = {row[1] for row in conn.execute("PRAGMA table_info(device_lifecycle_events)")}
                if "dedupe_key" not in columns:
                    raise RuntimeError("migration 0013 must be applied before lifecycle cleanup")
                conn.execute("BEGIN IMMEDIATE")
                rows = conn.execute(
                    "SELECT event_row_id, device_id, event_type, occurred_at_epoch_ms, event_id "
                    "FROM device_lifecycle_events WHERE event_type IN (?, ?) "
                    "ORDER BY device_id, event_type, occurred_at_epoch_ms ASC, event_id ASC",
                    tuple(sorted(ONE_TIME_TYPES)),
                ).fetchall()
                winners: set[tuple[str, str]] = set()
                for row_id, device_id, event_type, _epoch_ms, _event_id in rows:
                    key_tuple = (str(device_id), str(event_type))
                    dedupe_key = f"{device_id}:{event_type}"
                    if key_tuple not in winners:
                        winners.add(key_tuple)
                        conn.execute("UPDATE device_lifecycle_events SET dedupe_key=? WHERE event_row_id=?", (dedupe_key, row_id))
                    else:
                        conn.execute("DELETE FROM device_lifecycle_events WHERE event_row_id=?", (row_id,))
                        removed_sqlite += 1
                if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    conn.rollback()
                    raise RuntimeError("SQLite quick_check failed after lifecycle cleanup")
                conn.commit()

        evidence = _maintenance_evidence(state, mode="apply", removed_json=len(removed_json), removed_sqlite=removed_sqlite)
        evidence_path = state / "device_lifecycle_maintenance.json"
        evidence_payload = {"items": []}
        if evidence_path.exists():
            try:
                prior = json.loads(evidence_path.read_text(encoding="utf-8"))
                if isinstance(prior, dict):
                    evidence_payload = prior
            except (OSError, json.JSONDecodeError):
                evidence_payload = {"items": []}
        items = evidence_payload.get("items") if isinstance(evidence_payload.get("items"), list) else []
        _atomic_json_write(evidence_path, {"items": [evidence, *items][:MAX_EVIDENCE_ROWS], "updated_at": evidence["occurred_at"]})
    else:
        if sqlite_available:
            with sqlite3.connect(database, timeout=5.0) as conn:
                try:
                    rows = conn.execute(
                        "SELECT device_id, event_type, COUNT(*) FROM device_lifecycle_events "
                        "WHERE event_type IN (?, ?) GROUP BY device_id, event_type HAVING COUNT(*) > 1",
                        tuple(sorted(ONE_TIME_TYPES)),
                    ).fetchall()
                    removed_sqlite = sum(max(0, int(row[2]) - 1) for row in rows)
                except sqlite3.OperationalError:
                    removed_sqlite = 0

    result = {
        "status": "ready",
        "mode": "apply" if args.apply else "dry_run",
        "json_rows_seen": len(payload.get("events") or []),
        "json_duplicates": len(removed_json),
        "sqlite_duplicates": removed_sqlite,
        "sqlite_available": sqlite_available,
        "sanitized": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
