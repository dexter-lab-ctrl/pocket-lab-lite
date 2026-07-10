from __future__ import annotations

import sqlite3
from typing import Any

from .connection import connection, database_path
from .migrations import apply_migrations, discover_migrations


def _safe_failure(exc: Exception) -> dict[str, Any]:
    try:
        resolved_path = str(database_path())
    except Exception:
        resolved_path = None
    return {
        "reachable": False,
        "path": resolved_path,
        "schema_current": False,
        "schema_version": 0,
        "expected_schema_version": 0,
        "migration_count": 0,
        "journal_mode": None,
        "foreign_keys": False,
        "busy_timeout_ms": None,
        "quick_check": "unavailable",
        "security_revision": None,
        "migration_checksums_valid": False,
        "error_type": type(exc).__name__,
    }


def database_health(*, initialize: bool = False) -> dict[str, Any]:
    """Inspect the local backend database without exposing table contents."""
    expected = discover_migrations()
    expected_version = expected[-1].version if expected else 0
    try:
        if initialize:
            apply_migrations()
        with connection() as conn:
            quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
            journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            foreign_keys = int(conn.execute("PRAGMA foreign_keys").fetchone()[0])
            busy_timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
            tables = {
                str(row["name"])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            migration_rows: list[dict[str, Any]] = []
            if "schema_migrations" in tables:
                migration_rows = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT version, name, applied_at, checksum "
                        "FROM schema_migrations ORDER BY version"
                    )
                ]
            revision_row = None
            if "domain_revisions" in tables:
                revision_row = conn.execute(
                    "SELECT revision FROM domain_revisions WHERE domain = ?",
                    ("security",),
                ).fetchone()
        current = int(migration_rows[-1]["version"]) if migration_rows else 0
        expected_by_version = {
            item.version: (item.name, item.checksum) for item in expected
        }
        checksums_valid = all(
            expected_by_version.get(int(row["version"]))
            == (str(row["name"]), str(row["checksum"]))
            for row in migration_rows
        )
        schema_current = (
            current == expected_version
            and len(migration_rows) == len(expected)
            and checksums_valid
            and quick_check == "ok"
        )
        return {
            "reachable": True,
            "path": str(database_path()),
            "schema_current": schema_current,
            "schema_version": current,
            "expected_schema_version": expected_version,
            "migration_count": len(migration_rows),
            "journal_mode": journal_mode,
            "foreign_keys": foreign_keys == 1,
            "busy_timeout_ms": busy_timeout,
            "quick_check": quick_check,
            "security_revision": int(revision_row["revision"])
            if revision_row
            else None,
            "migration_checksums_valid": checksums_valid,
            "error_type": None,
        }
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        failure = _safe_failure(exc)
        failure["expected_schema_version"] = expected_version
        return failure
