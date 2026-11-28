"""Bounded migration-contract rehearsal in a synthetic in-memory SQLite DB.

Never loads candidate Python, copies user rows, opens the live DB, or changes
installed state. Restricted candidate SQL is not a compatibility proof or
authorization to migrate the production database.
"""
from __future__ import annotations

from contextlib import closing
import os
import sqlite3
import time

from ..db.migrations import discover_migrations, _statements, _ensure_metadata_table
from . import lite_release_package as package
from .lite_release_trust import TrustError

MAX_SCHEMA_BYTES = 32 * 1024 * 1024
MAX_PENDING = 32
MAX_STATEMENTS = 2000
# An explicit allowlist rather than assuming unknown SQLite operations are safe.
_ALLOWED = {getattr(sqlite3, name) for name in (
    "SQLITE_CREATE_INDEX", "SQLITE_CREATE_TABLE", "SQLITE_CREATE_TRIGGER", "SQLITE_CREATE_VIEW",
    "SQLITE_DROP_INDEX", "SQLITE_DROP_TABLE", "SQLITE_DROP_TRIGGER", "SQLITE_DROP_VIEW",
    "SQLITE_INSERT", "SQLITE_DELETE", "SQLITE_UPDATE", "SQLITE_READ", "SQLITE_SELECT",
    "SQLITE_ALTER_TABLE", "SQLITE_REINDEX", "SQLITE_ANALYZE", "SQLITE_FUNCTION", "SQLITE_RECURSIVE",
)}
_FUNCTIONS = frozenset({"abs", "coalesce", "ifnull", "nullif", "length", "lower", "upper",
    "trim", "ltrim", "rtrim", "replace", "substr", "substring", "instr", "typeof", "round",
    "count", "sum", "min", "max", "total", "avg", "hex", "quote", "printf", "format",
    "json", "json_array", "json_object", "json_extract", "json_valid", "json_type",
    "json_set", "json_remove", "json_insert", "json_replace", "json_patch", "json_quote",
    "json_array_length", "sqlite_rename_table", "sqlite_rename_column", "sqlite_rename_test",
    "sqlite_rename_quotefix", "sqlite_drop_column", "like", "glob"})


def gate():
    if os.environ.get("POCKETLAB_RELEASE_MIGRATION_REHEARSAL") != "1":
        return False
    try:
        from . import qualification_context
        return qualification_context.enabled()
    except Exception:
        return False


def _authorizer(action, first, second, database, source):
    if action not in _ALLOWED or database not in (None, "main"):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and str(second).casefold() not in _FUNCTIONS:
        return sqlite3.SQLITE_DENY
    if str(first).casefold() == "schema_migrations" or str(second).casefold() == "schema_migrations":
        if action not in (sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT):
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _execute(conn, migration, deadline_ns, *, restricted):
    conn.set_authorizer(_authorizer if restricted else None)
    try:
        for index, statement in enumerate(_statements(migration.sql)):
            if index >= MAX_STATEMENTS or time.monotonic_ns() >= deadline_ns:
                raise TrustError("migration_rehearsal_budget")
            conn.execute(statement)
    finally:
        conn.set_authorizer(None)
    conn.execute("INSERT INTO schema_migrations(version,name,applied_at,checksum) VALUES(?,?,?,?)",
                 (migration.version, migration.name, "synthetic", migration.checksum))


def assess(source_root, migration_document, *, current_schema, deadline_ns):
    if not gate():
        return {"state": "not_requested", "promotion_eligible": False}
    try:
        expected = package._inventory(migration_document, prefix=package.MIGRATION_PREFIX, suffix=".sql")
        local = discover_migrations()
        remote = discover_migrations(source_root / package.MIGRATION_PREFIX)
        if (len(remote) != len(expected) or len(local) != current_schema
                or [item.version for item in remote] != list(range(1, len(remote)+1))
                or not current_schema <= len(remote) <= current_schema + MAX_PENDING
                or any(expected.get(package.MIGRATION_PREFIX + item.path.name) != item.checksum for item in remote)
                or [(m.name, m.checksum) for m in local] != [(m.name, m.checksum) for m in remote[:current_schema]]):
            raise TrustError("migration_rehearsal_inventory_mismatch")
        with closing(sqlite3.connect(":memory:", isolation_level=None)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA temp_store=MEMORY")
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute(f"PRAGMA max_page_count={MAX_SCHEMA_BYTES // db.execute('PRAGMA page_size').fetchone()[0]}")
            db.set_progress_handler(lambda: int(time.monotonic_ns() >= deadline_ns), 1000)
            db.execute("BEGIN")
            _ensure_metadata_table(db)
            for migration in local:
                _execute(db, migration, deadline_ns, restricted=False)
            for migration in remote[current_schema:]:
                _execute(db, migration, deadline_ns, restricted=True)
            ledger = db.execute("SELECT version,name,checksum FROM schema_migrations ORDER BY version").fetchall()
            if ledger != [(m.version, m.name, m.checksum) for m in remote]:
                raise TrustError("migration_rehearsal_ledger_changed")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None or db.execute("PRAGMA quick_check(1)").fetchone() != ("ok",):
                raise TrustError("migration_rehearsal_integrity_failed")
            db.execute("ROLLBACK")
        return {"state": "synthetic_schema_rehearsed", "from_schema": current_schema,
                "to_schema": len(remote), "applied_count": len(remote)-current_schema,
                "production_data_compatible": False, "promotion_eligible": False}
    except Exception:
        # Do not expose SQL, table names, paths or data from errors.
        return {"state": "blocked", "reason_code": "migration_rehearsal_unproved", "promotion_eligible": False}
