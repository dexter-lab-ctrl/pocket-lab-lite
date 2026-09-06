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
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(path.parent))
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.runtime import SQLITE_READS

    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    return path


def _migration_worker(database: str, queue) -> None:
    os.environ["POCKETLAB_LITE_DB_PATH"] = database
    os.environ["POCKETLAB_STATE_DIR"] = str(Path(database).parent)
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations, current_schema_version
    from api_fastapi.db.runtime import SQLITE_READS

    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
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
        latest_schema_version,
        migration_rows,
        migration_versions,
    )

    expected = migration_versions()
    assert expected and expected == sorted(set(expected))
    assert apply_migrations() == expected
    assert apply_migrations() == []
    assert current_schema_version() == latest_schema_version() == expected[-1]
    assert [row["version"] for row in migration_rows()] == expected
    with read_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert {
        "schema_migrations",
        "security_scan_runs",
        "device_current_state",
        "device_system_profiles",
        "device_awareness_state",
        "command_lifecycle",
        "recovery_current_state",
        "audit_evidence_index",
        "lite_revision_events",
        "projection_refresh_state",
        "release_runtime_projection",
        "lite_installed_release_identity",
        "human_identities",
        "enterprise_memberships",
        "policy_decisions",
    }.issubset(tables)
    assert {
        "idx_device_current_fleet_order",
        "idx_device_awareness_staleness",
        "idx_lite_revision_events_replay",
    }.issubset(indexes)
    assert "operation_leases" not in tables


def test_lite_sqlite_migration_checksum_mismatch_fails_closed(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.migrations import MigrationChecksumError, apply_migrations

    migrations = tmp_path / "migrations"
    migrations.mkdir()
    migration = migrations / "0001_test.sql"
    migration.write_text("CREATE TABLE checksum_test(id INTEGER PRIMARY KEY);\n", encoding="utf-8")
    assert apply_migrations(migrations) == [1]
    migration.write_text("CREATE TABLE checksum_test(id INTEGER PRIMARY KEY, changed TEXT);\n", encoding="utf-8")
    with pytest.raises(MigrationChecksumError):
        apply_migrations(migrations)


def test_lite_sqlite_migration_rejects_newer_schema(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import MigrationError, apply_migrations

    apply_migrations()
    with connection() as conn:
        conn.execute(
            "INSERT INTO schema_migrations(version, name, applied_at, checksum) VALUES (?, ?, ?, ?)",
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
            "SELECT name FROM sqlite_master WHERE type='table' AND name='should_rollback'"
        ).fetchone()
        metadata = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
    assert table is None
    assert metadata is None


def test_lite_sqlite_concurrent_initializers_are_safe(tmp_path):
    ensure_runtime_path()
    from api_fastapi.db.migrations import latest_schema_version, migration_versions

    database = str(tmp_path / "state" / "db.sqlite3")
    expected = migration_versions()
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [context.Process(target=_migration_worker, args=(database, queue)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
        assert process.exitcode == 0
    results = [queue.get(timeout=5), queue.get(timeout=5)]
    assert all(result[0] is True for result in results)
    assert all(result[2] == latest_schema_version() for result in results)
    assert sorted(len(result[1]) for result in results) == [0, len(expected)]


def _copy_schema_prefix(target: Path, *, through: int) -> None:
    from api_fastapi.db.migrations import schema_dir

    target.mkdir()
    for source in sorted(schema_dir().glob("*.sql")):
        version = int(source.name.split("_", 1)[0])
        if version <= through:
            (target / source.name).write_bytes(source.read_bytes())


def test_lite_sqlite_migration_5_upgrades_schema_4_without_data_loss(tmp_path, monkeypatch):
    database = _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import apply_migrations, latest_schema_version, migration_versions

    old_schema = tmp_path / "schema-v4"
    _copy_schema_prefix(old_schema, through=4)
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
                0, 0, 0, 0, 0, 0, 0, 'test', 1, 0
            )
            """
        )
    assert apply_migrations() == [version for version in migration_versions() if version >= 5]
    assert latest_schema_version() == migration_versions()[-1]
    with connection() as conn:
        assert conn.execute(
            "SELECT summary FROM security_scan_runs WHERE run_id='security-upgrade-v5'"
        ).fetchone()["summary"] == "preserved"
    assert database.exists()


def test_lite_sqlite_migration_14_upgrades_schema_13_without_data_loss(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import apply_migrations, migration_versions

    schema_v13 = tmp_path / "schema-v13"
    _copy_schema_prefix(schema_v13, through=13)
    assert apply_migrations(schema_v13) == [version for version in migration_versions(schema_v13)]
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO device_current_state(
                device_id,device_name,role,ui_state,connection_state,agent_status,
                supervisor_status,pm2_status,remote_access_ready,protected_server_host,
                source_revision,last_seen_at,last_seen_epoch_ms,updated_at,
                updated_at_epoch_ms,summary
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "phone-two", "Phone Two", "compute", "Online", "online", "online",
                "healthy", "online", 1, 0, 1, "2026-07-24T08:00:00Z",
                1784880000000, "2026-07-24T08:00:00Z", 1784880000000,
                "Existing device state.",
            ),
        )
        conn.execute(
            """
            INSERT INTO device_lifecycle_events(
                event_id,device_id,event_type,reason_code,status,occurred_at,
                occurred_at_epoch_ms,summary,sanitized,source_revision,dedupe_key
            ) VALUES (?,?,?,?,?,?,?,?,1,?,?)
            """,
            (
                "existing-first-heartbeat", "phone-two", "first_heartbeat_received", "",
                "recorded", "2026-07-24T08:00:00Z", 1784880000000,
                "Existing lifecycle evidence.", 1,
                "phone-two:first_heartbeat_received",
            ),
        )
    assert apply_migrations() == [version for version in migration_versions() if version >= 14]
    with connection() as conn:
        preserved = conn.execute(
            "SELECT event_id,dedupe_key FROM device_lifecycle_events WHERE event_id='existing-first-heartbeat'"
        ).fetchone()
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert preserved["event_id"] == "existing-first-heartbeat"
    assert preserved["dedupe_key"] == "phone-two:first_heartbeat_received"


def test_migration_17_backfills_terminal_command_attention(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import apply_migrations, migration_versions

    pre17 = tmp_path / "pre17"
    _copy_schema_prefix(pre17, through=16)
    assert apply_migrations(pre17) == [version for version in migration_versions(pre17)]
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO command_lifecycle(
                command_id,entity_type,entity_id,operation_type,status,
                created_at,updated_at,updated_at_epoch_ms,source_ref,summary,
                metadata_json,lifecycle_stage,terminal_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "pre17-undeliverable", "device", "offline-device", "agent.restart",
                "undeliverable", "2026-07-01T00:00:00Z", "2026-07-01T00:01:00Z",
                60000, "test", "undeliverable", "{}", "failed",
                "2026-07-01T00:01:00Z",
            ),
        )
    assert apply_migrations() == [version for version in migration_versions() if version >= 17]
    with connection() as conn:
        row = conn.execute(
            "SELECT attention_status,attention_updated_at,attention_updated_at_epoch_ms "
            "FROM command_lifecycle WHERE command_id='pre17-undeliverable'"
        ).fetchone()
    assert tuple(row) == ("active", "2026-07-01T00:01:00Z", 60000)
