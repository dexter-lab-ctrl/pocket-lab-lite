from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest


def _module():
    return importlib.import_module("api_fastapi.services.lite_database_recovery")


def _database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE security_database_restores(
                restore_id TEXT PRIMARY KEY,
                backup_id TEXT,
                preview_id TEXT,
                state TEXT,
                requested_at TEXT,
                completed_at TEXT,
                rollback_file_name TEXT,
                summary TEXT,
                metadata_json TEXT,
                sanitized INTEGER NOT NULL
            );
            CREATE TABLE recovery_current_state(
                singleton_id INTEGER PRIMARY KEY,
                status TEXT,
                active_operation_id TEXT,
                latest_backup_id TEXT,
                latest_preview_id TEXT,
                latest_restore_id TEXT,
                maintenance_status TEXT,
                source_revision INTEGER NOT NULL,
                updated_at TEXT,
                updated_at_epoch_ms INTEGER,
                summary TEXT
            );
            INSERT INTO recovery_current_state VALUES(
                1, 'healthy', NULL, 'backup-a', NULL, NULL, 'idle', 0,
                '2026-07-07T11:05:29Z', 1783422329000, 'Recovery Ready'
            );
            """
        )


def test_durable_restore_history_is_sanitized_and_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _module()
    database = tmp_path / "state.sqlite3"
    _database(database)
    with sqlite3.connect(database) as conn:
        conn.executemany(
            """
            INSERT INTO security_database_restores VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("restore-a", "backup-a", "preview-a", "completed", "2026-07-20T10:00:00Z", "2026-07-20T10:00:10Z", "/private/a", "Passed.", '{"secret":"x"}', 1),
                ("restore-b", "backup-b", "preview-b", "completed", "2026-07-20T11:00:00Z", "2026-07-20T11:00:10Z", "/private/b", "Latest passed.", '{"secret":"y"}', 1),
                ("restore-z", "backup-z", "preview-z", "completed", "2026-07-21T11:00:00Z", "2026-07-21T11:00:10Z", "/private/z", "Must be ignored.", '{}', 0),
            ],
        )
    monkeypatch.setattr(module, "database_path", lambda: database)

    snapshot = module._durable_database_restore_history()

    assert snapshot["last_restore"]["restore_id"] == "restore-b"
    assert snapshot["latest_restore_preview"] == {
        "preview_id": "preview-b",
        "backup_id": "backup-b",
        "status": "historical",
        "restore_allowed": False,
        "requires_confirmation": True,
        "summary": "A previous restore preview was recorded. Create a fresh preview before another restore.",
        "sanitized": True,
    }
    assert snapshot["restore_history"] == {
        "total": 2,
        "completed": 2,
        "incomplete": 0,
        "preview_references": 2,
    }
    assert "rollback_file_name" not in snapshot["last_restore"]
    assert "metadata_json" not in snapshot["last_restore"]


def test_reconciliation_updates_only_restore_pointers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _module()
    database = tmp_path / "state.sqlite3"
    _database(database)
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO security_database_restores VALUES(
                'restore-a', 'backup-db', 'preview-a', 'completed',
                '2026-07-20T10:00:00Z', '2026-07-20T10:00:10Z',
                '/private/a', 'Passed.', '{}', 1
            )
            """
        )
    monkeypatch.setattr(module, "database_path", lambda: database)

    result = module.reconcile_database_restore_projection()
    assert result == {"status": "reconciled", "changed": True, "sanitized": True}

    with sqlite3.connect(database) as conn:
        row = conn.execute(
            """
            SELECT status, active_operation_id, latest_backup_id, latest_preview_id,
                   latest_restore_id, maintenance_status, source_revision
            FROM recovery_current_state WHERE singleton_id = 1
            """
        ).fetchone()
    assert row == ("healthy", None, "backup-a", "preview-a", "restore-a", "idle", 1)
    assert module.reconcile_database_restore_projection()["changed"] is False


def test_empty_history_remains_non_authorizing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _module()
    database = tmp_path / "state.sqlite3"
    _database(database)
    monkeypatch.setattr(module, "database_path", lambda: database)

    snapshot = module._durable_database_restore_history()

    assert snapshot["last_restore"] is None
    assert snapshot["latest_restore_preview"] is None
    assert snapshot["restore_history"]["total"] == 0
    assert module.reconcile_database_restore_projection()["status"] == "no_history"



def test_control_plane_projection_preserves_reconciled_restore_pointers() -> None:
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/"
        "services/lite_control_plane_store.py"
    ).read_text(encoding="utf-8")

    assert (
        "latest_preview_id=COALESCE("
        "excluded.latest_preview_id, "
        "recovery_current_state.latest_preview_id"
        ")"
    ) in source

    assert (
        "latest_restore_id=COALESCE("
        "excluded.latest_restore_id, "
        "recovery_current_state.latest_restore_id"
        ")"
    ) in source

    assert (
        "recovery_current_state.latest_preview_id "
        "IS NOT COALESCE("
        "excluded.latest_preview_id, "
        "recovery_current_state.latest_preview_id"
        ")"
    ) in source

    assert (
        "recovery_current_state.latest_restore_id "
        "IS NOT COALESCE("
        "excluded.latest_restore_id, "
        "recovery_current_state.latest_restore_id"
        ")"
    ) in source


def test_recovery_ui_reads_authoritative_database_projection() -> None:
    source = Path(
        "src/lite/LiteRecovery.jsx"
    ).read_text(encoding="utf-8")

    assert (
        "useLiteResource(liteApi.databaseRecovery"
        in source
    )
    assert "data: databaseProtectionData" in source
    assert "...(databaseProtectionData || {})" in source
    assert "refreshDatabaseProtection()" in source
    assert "refresh={refreshRecovery}" in source
