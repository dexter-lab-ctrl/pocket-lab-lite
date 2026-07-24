from __future__ import annotations

import os
import sqlite3
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(target))
    monkeypatch.setenv("POCKETLAB_LITE_DB_BUSY_TIMEOUT_MS", "20000")
    monkeypatch.setenv("POCKETLAB_LITE_DB_SYNCHRONOUS", "NORMAL")
    monkeypatch.setenv("POCKETLAB_LITE_DB_WAL_AUTOCHECKPOINT", "1000")
    return target


def test_lite_sqlite_path_defaults_to_state_dir(tmp_path, monkeypatch):
    ensure_runtime_path()
    connection_module = importlib.import_module("api_fastapi.db.connection")

    monkeypatch.delenv("POCKETLAB_LITE_DB_PATH", raising=False)
    monkeypatch.setattr(
        connection_module.deps,
        "settings",
        lambda: SimpleNamespace(state_dir=tmp_path / "state"),
    )
    assert connection_module.database_path() == (
        tmp_path / "state" / "pocketlab-lite.sqlite3"
    ).resolve()


def test_lite_sqlite_connection_applies_required_policy(tmp_path, monkeypatch):
    target = _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection, online_backup, read_connection
    from api_fastapi.db.health import database_health
    from api_fastapi.db.migrations import apply_migrations

    assert apply_migrations() == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    with connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 20000
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
        assert conn.execute("PRAGMA temp_store").fetchone()[0] == 2  # MEMORY
        assert conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0] == 1000
    with read_connection() as conn:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    health = database_health()
    assert health["reachable"] is True
    assert health["schema_current"] is True
    assert health["schema_version"] == 13
    assert health["journal_mode"] == "wal"
    assert health["foreign_keys"] is True
    assert health["busy_timeout_ms"] == 20000
    assert health["quick_check"] == "ok"
    assert health["security_revision"] == 0
    assert health["migration_checksums_valid"] is True
    assert target.exists()
    backup = online_backup(tmp_path / "backup" / "security.sqlite3")
    assert backup.exists()
    if os.name == "posix":
        assert target.stat().st_mode & 0o077 == 0
        assert backup.stat().st_mode & 0o077 == 0


def test_lite_sqlite_connections_are_separate_and_transactions_roll_back(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import begin_immediate, open_connection
    from api_fastapi.db.migrations import apply_migrations

    apply_migrations()
    first = open_connection()
    second = open_connection()
    try:
        assert first is not second
        with pytest.raises(RuntimeError):
            with begin_immediate(first) as tx:
                tx.execute(
                    "INSERT INTO security_store_metadata(metadata_key, value_json, updated_at) "
                    "VALUES (?, ?, ?)",
                    ("rollback-test", "{}", "2026-07-10T00:00:00Z"),
                )
                raise RuntimeError("force rollback")
        assert (
            second.execute(
                "SELECT COUNT(*) FROM security_store_metadata "
                "WHERE metadata_key = ?",
                ("rollback-test",),
            ).fetchone()[0]
            == 0
        )
    finally:
        first.close()
        second.close()


def test_lite_sqlite_connection_rejects_unbounded_or_unsafe_settings(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import SQLiteConfigurationError, sqlite_settings

    monkeypatch.setenv("POCKETLAB_LITE_DB_SYNCHRONOUS", "UNTRUSTED")
    with pytest.raises(SQLiteConfigurationError):
        sqlite_settings()
    monkeypatch.setenv("POCKETLAB_LITE_DB_SYNCHRONOUS", "NORMAL")
    monkeypatch.setenv("POCKETLAB_LITE_DB_BUSY_TIMEOUT_MS", "999999")
    with pytest.raises(SQLiteConfigurationError):
        sqlite_settings()
    monkeypatch.setenv("POCKETLAB_LITE_DB_BUSY_TIMEOUT_MS", "20000")
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", "/storage/emulated/0/pocketlab.sqlite3")
    with pytest.raises(SQLiteConfigurationError):
        sqlite_settings()
    connection_module = importlib.import_module("api_fastapi.db.connection")
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(connection_module._REPOSITORY_ROOT / "pocketlab.sqlite3"),
    )
    with pytest.raises(SQLiteConfigurationError):
        sqlite_settings()


def test_lite_sqlite_health_reports_corruption_without_raising(tmp_path, monkeypatch):
    target = _configure(tmp_path, monkeypatch)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not-a-sqlite-database")
    from api_fastapi.db.health import database_health

    health = database_health()
    assert health["reachable"] is False
    assert health["schema_current"] is False
    assert health["quick_check"] == "unavailable"
    assert health["error_type"] in {"DatabaseError", "OperationalError"}


def test_write_connection_reports_creation_stages(tmp_path, monkeypatch):
    from api_fastapi.db.connection import connection

    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(tmp_path / "timed.sqlite3"))
    timing = {}
    with connection(timing_sink=timing) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS timed_test(id INTEGER PRIMARY KEY)")
    assert timing["path_resolve_ms"] >= 0
    assert timing["sqlite_connect_ms"] >= 0
    assert timing["pragma_setup_ms"] >= 0
    assert timing["total_ms"] >= 0

def test_lite_sqlite_path_cache_reuses_resolution_and_can_reset(tmp_path, monkeypatch):
    connection_module = importlib.import_module("api_fastapi.db.connection")
    first = tmp_path / "one.sqlite3"
    second = tmp_path / "two.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(first))
    connection_module.reset_sqlite_path_cache()
    assert connection_module.database_path() == first.resolve()
    assert connection_module.database_path() is connection_module.database_path()
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(second))
    assert connection_module.database_path() == second.resolve()
    connection_module.reset_sqlite_path_cache()
    assert connection_module.database_path() == second.resolve()


def test_lite_sqlite_wal_fast_path_does_not_repeat_journal_transition():
    from api_fastapi.db.connection import _enable_wal_with_retry

    class _Result:
        @staticmethod
        def fetchone():
            return ("wal",)

    class _Connection:
        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(statement)
            if statement == "PRAGMA journal_mode":
                return _Result()
            raise AssertionError(f"unexpected journal transition: {statement}")

    conn = _Connection()
    assert _enable_wal_with_retry(conn, 20_000) == "wal"
    assert conn.statements == ["PRAGMA journal_mode"]
