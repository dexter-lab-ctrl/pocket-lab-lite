from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database


@pytest.fixture(autouse=True)
def _quiesce_runtime_after_test():
    yield
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services.projection_scheduler import PROJECTION_SCHEDULER

    assert PROJECTION_SCHEDULER.quiesce_for_database_switch(timeout_seconds=5.0)
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    prepare_sqlite_test_database(target, monkeypatch)
    from api_fastapi.db.migrations import apply_migrations

    assert apply_migrations() == list(range(1, 23))
    return target


def test_acknowledgement_reuses_existing_audit_evidence_without_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    conn = sqlite3.connect(database)
    try:
        conn.execute(
            """
            INSERT INTO command_lifecycle(
                command_id,entity_type,entity_id,operation_type,status,
                created_at,updated_at,updated_at_epoch_ms,source_ref,summary,
                metadata_json,lifecycle_stage,terminal_at,attention_status,
                attention_updated_at,attention_updated_at_epoch_ms
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "reopened-attention", "device", "device-missing",
                "agent.restart", "undeliverable",
                "2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z",
                1782864000000, "test", "undeliverable", "{}", "failed",
                "2026-07-01T00:00:00Z", "active",
                "2026-07-01T00:00:00Z", 1782864000000,
            ),
        )
        conn.execute(
            """
            INSERT INTO audit_evidence_index(
                event_type,entity_type,entity_id,operation_id,status,evidence_ref,
                created_at,created_at_epoch_ms,summary
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                "command.attention_acknowledged", "device", "device-missing",
                "reopened-attention", "undeliverable", "command-attention",
                "2026-07-01T00:01:00Z", 1782864060000,
                "Command attention acknowledged.",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    store = ControlPlaneProjectionStore()
    commands_before = store.domain_revision("commands")
    audit_before = store.domain_revision("audit")

    assert store.acknowledge_command_attention("reopened-attention") is True
    assert store.acknowledge_command_attention("reopened-attention") is False

    conn = sqlite3.connect(database)
    try:
        state = conn.execute(
            "SELECT attention_status FROM command_lifecycle WHERE command_id=?",
            ("reopened-attention",),
        ).fetchone()[0]
        count = conn.execute(
            """
            SELECT COUNT(*) FROM audit_evidence_index
            WHERE event_type='command.attention_acknowledged'
              AND operation_id='reopened-attention'
              AND evidence_ref='command-attention'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert state == "acknowledged"
    assert count == 1
    assert store.domain_revision("commands") == commands_before + 1
    assert store.domain_revision("audit") == audit_before
