from __future__ import annotations

import sqlite3
from pathlib import Path
import sys


_RUNTIME = (
    Path(__file__).resolve().parents[2]
    / "pocket-lab-final-structure"
    / "runtime"
)
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))


def ensure_runtime_path() -> None:
    """Keep the test importable without requiring tests to be a package."""
    if str(_RUNTIME) not in sys.path:
        sys.path.insert(0, str(_RUNTIME))


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE command_lifecycle (
            command_id TEXT PRIMARY KEY,
            entity_type TEXT,
            entity_id TEXT,
            operation_type TEXT,
            status TEXT,
            attention_status TEXT,
            updated_at_epoch_ms INTEGER
        );
        CREATE TABLE app_action_lifecycle (
            operation_id TEXT PRIMARY KEY,
            app_id TEXT,
            action_id TEXT,
            status TEXT,
            updated_at_epoch_ms INTEGER
        );
        CREATE TABLE recovery_operations (
            operation_id TEXT PRIMARY KEY,
            operation_type TEXT,
            status TEXT,
            updated_at_epoch_ms INTEGER
        );
        CREATE TABLE security_scan_runs (
            run_id TEXT PRIMARY KEY,
            profile TEXT,
            status TEXT,
            completed_at_epoch_ms INTEGER,
            updated_at_epoch_ms INTEGER,
            requested_at_epoch_ms INTEGER
        );
        CREATE TABLE audit_evidence_index (
            evidence_index_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            entity_type TEXT,
            entity_id TEXT,
            operation_id TEXT,
            status TEXT,
            created_at_epoch_ms INTEGER
        );
        """
    )
    conn.execute(
        """
        INSERT INTO command_lifecycle(
            command_id, entity_type, entity_id, operation_type,
            status, attention_status, updated_at_epoch_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "command-1",
            "device",
            "device-1",
            "agent.restart",
            "succeeded",
            "none",
            1000,
        ),
    )
    conn.commit()
    return conn


def test_activity_revision_ignores_unrelated_audit_evidence(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3c_projections as phase3c

    conn = _database()
    monkeypatch.setattr(phase3c, "_read", lambda callback: callback(conn))

    first_payload = phase3c.collect_activity_summary()
    first_revision = phase3c.activity_source_revision()

    conn.execute(
        """
        INSERT INTO audit_evidence_index(
            event_type, entity_type, entity_id, operation_id,
            status, created_at_epoch_ms
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "system.health.sampled",
            "system",
            "pocket-lab-lite-server",
            "health-sample-1",
            "healthy",
            2000,
        ),
    )
    conn.commit()

    second_payload = phase3c.collect_activity_summary()
    second_revision = phase3c.activity_source_revision()

    assert first_payload["audit_reference_count"] == 0
    assert second_payload["audit_reference_count"] == 0
    assert second_revision == first_revision

    conn.execute(
        """
        INSERT INTO audit_evidence_index(
            event_type, entity_type, entity_id, operation_id,
            status, created_at_epoch_ms
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "command.completed",
            "device",
            "device-1",
            "command-1",
            "succeeded",
            3000,
        ),
    )
    conn.commit()

    third_payload = phase3c.collect_activity_summary()
    third_revision = phase3c.activity_source_revision()

    assert third_payload["audit_reference_count"] == 1
    assert third_revision != second_revision

    conn.execute(
        """
        INSERT INTO audit_evidence_index(
            event_type, entity_type, entity_id, operation_id,
            status, created_at_epoch_ms
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "command.audit_refreshed",
            "device",
            "device-1",
            "command-1",
            "succeeded",
            4000,
        ),
    )
    conn.commit()

    fourth_payload = phase3c.collect_activity_summary()
    fourth_revision = phase3c.activity_source_revision()

    assert fourth_payload["audit_reference_count"] == 1
    assert fourth_revision == third_revision

    conn.close()
