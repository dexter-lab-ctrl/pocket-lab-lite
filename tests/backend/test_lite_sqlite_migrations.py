from __future__ import annotations

import multiprocessing
import os
import sqlite3
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    path = tmp_path / "state" / "db.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(path))
    return path


def _migration_worker(database: str, queue) -> None:
    os.environ["POCKETLAB_LITE_DB_PATH"] = database
    from api_fastapi.db.migrations import apply_migrations, current_schema_version

    try:
        applied = apply_migrations()
        queue.put((True, applied, current_schema_version()))
    except Exception as exc:
        queue.put((False, type(exc).__name__, 0))


def test_lite_sqlite_migrations_are_idempotent_and_complete(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import (
        apply_migrations,
        current_schema_version,
        migration_rows,
    )

    assert apply_migrations() == [1, 2, 3, 4, 5]
    assert apply_migrations() == []
    assert current_schema_version() == 5
    assert [row["version"] for row in migration_rows()] == [1, 2, 3, 4, 5]
    with read_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
    assert {
        "schema_migrations",
        "security_scan_runs",
        "security_scan_progress_events",
        "security_scan_findings",
        "security_scan_evidence_refs",
        "security_scan_tool_runs",
        "security_profile_snapshots",
        "domain_revisions",
        "security_store_metadata",
        "security_maintenance_runs",
        "security_database_backups",
        "security_database_restores",
    }.issubset(tables)
    assert {
        "idx_security_runs_profile_completed",
        "idx_security_runs_status_updated",
        "idx_security_progress_run_event",
        "idx_security_progress_created",
        "idx_security_findings_run_severity",
        "idx_security_findings_fingerprint",
        "idx_security_evidence_run_kind",
        "idx_security_tool_runs_run",
        "idx_security_runs_delivery_state",
        "idx_security_runs_progress_latest",
        "idx_security_maintenance_kind_requested",
        "idx_security_database_backups_created",
        "idx_security_database_restores_requested",
        "idx_security_runs_history_cursor",
        "idx_security_runs_profile_history_cursor",
        "idx_security_runs_profile_updated_latest",
        "idx_security_runs_app_updated_latest",
    }.issubset(indexes)
    assert "operation_leases" not in tables


def test_lite_sqlite_migration_checksum_mismatch_fails_closed(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.migrations import MigrationChecksumError, apply_migrations

    migrations = tmp_path / "migrations"
    migrations.mkdir()
    migration = migrations / "0001_test.sql"
    migration.write_text(
        "CREATE TABLE checksum_test(id INTEGER PRIMARY KEY);\n", encoding="utf-8"
    )
    assert apply_migrations(migrations) == [1]
    migration.write_text(
        "CREATE TABLE checksum_test(id INTEGER PRIMARY KEY, changed TEXT);\n",
        encoding="utf-8",
    )
    with pytest.raises(MigrationChecksumError):
        apply_migrations(migrations)


def test_lite_sqlite_migration_rejects_newer_schema(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import MigrationError, apply_migrations

    apply_migrations()
    with connection() as conn:
        conn.execute(
            "INSERT INTO schema_migrations(version, name, applied_at, checksum) "
            "VALUES (?, ?, ?, ?)",
            (999, "future", "2026-07-10T00:00:00Z", "future-checksum"),
        )
    with pytest.raises(MigrationError, match="newer"):
        apply_migrations()


def test_lite_sqlite_failed_migration_rolls_back_all_statements(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import apply_migrations

    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_broken.sql").write_text(
        "CREATE TABLE should_rollback(id INTEGER PRIMARY KEY);\n"
        "INSERT INTO missing_table(value) VALUES ('fail');\n",
        encoding="utf-8",
    )
    with pytest.raises(sqlite3.Error):
        apply_migrations(migrations)
    with connection() as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            ("should_rollback",),
        ).fetchone()
        metadata_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            ("schema_migrations",),
        ).fetchone()
    assert table is None
    assert metadata_table is None


def test_lite_sqlite_concurrent_initializers_are_safe(tmp_path):
    ensure_runtime_path()
    database = str(tmp_path / "state" / "db.sqlite3")
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [
        context.Process(target=_migration_worker, args=(database, queue))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
        assert process.exitcode == 0
    results = [queue.get(timeout=5), queue.get(timeout=5)]
    assert all(result[0] is True for result in results)
    assert all(result[2] == 5 for result in results)
    assert sorted(len(result[1]) for result in results) == [0, 5]


def test_lite_sqlite_migration_5_upgrades_schema_4_without_data_loss(
    tmp_path, monkeypatch
):
    database = _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import (
        apply_migrations,
        current_schema_version,
        schema_dir,
    )

    old_schema = tmp_path / "schema-v4"
    old_schema.mkdir()
    for source in sorted(schema_dir().glob("000[1-4]_*.sql")):
        (old_schema / source.name).write_bytes(source.read_bytes())

    assert apply_migrations(old_schema) == [1, 2, 3, 4]
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO security_scan_runs(
                run_id, profile, app_id, app_label, status, summary,
                partial_results, requested_at, updated_at,
                requested_at_epoch_ms, updated_at_epoch_ms,
                checks_reviewed, items_to_review, critical_count,
                high_count, medium_count, low_count, info_count,
                source, revision, evidence_saved
            ) VALUES (
                'security-upgrade-v5', 'quick', '', '', 'succeeded', 'preserved',
                0, '2026-07-20T00:00:00Z', '2026-07-20T00:00:00Z',
                1784505600000, 1784505600000,
                0, 0, 0, 0, 0, 0, 0,
                'test', 1, 0
            )
            """
        )

    assert apply_migrations() == [5]
    assert current_schema_version() == 5
    with connection() as conn:
        assert conn.execute(
            "SELECT summary FROM security_scan_runs WHERE run_id = ?",
            ("security-upgrade-v5",),
        ).fetchone()["summary"] == "preserved"
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
    assert "idx_security_runs_history_cursor" in indexes
    assert database.exists()
