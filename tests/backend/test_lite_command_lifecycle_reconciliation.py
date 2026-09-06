from __future__ import annotations

import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    prepare_sqlite_test_database(target, monkeypatch)
    from api_fastapi.db.migrations import apply_migrations, current_schema_version, latest_schema_version

    apply_migrations()
    assert current_schema_version() == latest_schema_version()
    return target


def _insert_command(
    database: Path,
    *,
    command_id: str,
    entity_id: str = "device-missing",
    status: str = "queued",
    updated_at_epoch_ms: int = 1_000,
    deadline_at: str | None = None,
) -> None:
    import sqlite3

    conn = sqlite3.connect(database)
    try:
        conn.execute(
            """
            INSERT INTO command_lifecycle(
                command_id,entity_type,entity_id,operation_type,status,
                created_at,updated_at,updated_at_epoch_ms,deadline_at,
                source_ref,summary,metadata_json,lifecycle_stage
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                command_id, "device", entity_id, "agent.restart", status,
                "2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z",
                updated_at_epoch_ms, deadline_at, "test", status, "{}", "accepted",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_device(database: Path, *, device_id: str, connection_state: str) -> None:
    import sqlite3

    conn = sqlite3.connect(database)
    try:
        conn.execute(
            """
            INSERT INTO device_current_state(
                device_id,device_name,role,ui_state,connection_state,agent_status,
                supervisor_status,pm2_status,updated_at,updated_at_epoch_ms,summary
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                device_id, device_id, "compute",
                "Offline" if connection_state == "offline" else "Online",
                connection_state,
                "offline" if connection_state == "offline" else "online",
                "unknown", "unknown", "2026-07-01T00:00:00Z", 1_000, "test",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _command(database: Path, command_id: str) -> dict:
    import sqlite3

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM command_lifecycle WHERE command_id=?", (command_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def test_legacy_missing_target_becomes_undeliverable_and_propagates(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    dirty: list[tuple[tuple[str, ...], str]] = []
    monkeypatch.setattr(
        lite_phase3c_projections,
        "mark_dirty",
        lambda *domains, reason="event": dirty.append((domains, reason)) or True,
    )
    _insert_command(database, command_id="legacy-missing")

    store = ControlPlaneProjectionStore()
    result = store.reconcile_command_lifecycle(
        now_epoch_ms=10_000_000,
        legacy_max_age_seconds=60,
        missing_target_grace_seconds=30,
    )

    row = _command(database, "legacy-missing")
    assert result["reconciled_count"] == 1
    assert result["reasons"] == {"target_missing": 1}
    assert row["status"] == "undeliverable"
    assert row["lifecycle_stage"] == "terminal"
    assert row["attention_status"] == "active"
    assert row["recovery_action"] == "target_missing"
    assert dirty == [(("system.activity_current", "system.activity_history"), "command_lifecycle_reconciled")]

    import sqlite3
    conn = sqlite3.connect(database)
    try:
        revisions = dict(conn.execute("SELECT domain,revision FROM domain_revisions WHERE domain IN ('commands','audit')"))
        evidence = conn.execute(
            "SELECT event_type,evidence_ref,summary FROM audit_evidence_index WHERE operation_id=?",
            ("legacy-missing",),
        ).fetchone()
    finally:
        conn.close()
    assert revisions == {"audit": 1, "commands": 1}
    assert evidence[0] == "command.reconciled.undeliverable"
    assert evidence[1] == "command-lifecycle-reconciler"
    assert "/data/data/" not in json.dumps(evidence).lower()


def test_recent_queued_command_remains_nonterminal(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    _insert_command(database, command_id="recent", updated_at_epoch_ms=9_900_000)
    result = ControlPlaneProjectionStore().reconcile_command_lifecycle(
        now_epoch_ms=10_000_000, legacy_max_age_seconds=3600, missing_target_grace_seconds=300,
    )
    assert result["reconciled_count"] == 0
    assert _command(database, "recent")["status"] == "queued"


def test_known_offline_device_respects_grace_then_becomes_undeliverable(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    _insert_device(database, device_id="offline-known", connection_state="offline")
    _insert_command(database, command_id="offline-command", entity_id="offline-known", updated_at_epoch_ms=9_900_000)
    store = ControlPlaneProjectionStore()
    recent = store.reconcile_command_lifecycle(now_epoch_ms=10_000_000, legacy_max_age_seconds=3600)
    assert recent["reconciled_count"] == 0
    old = store.reconcile_command_lifecycle(now_epoch_ms=20_000_000, legacy_max_age_seconds=60)
    assert old["reconciled_count"] == 1
    assert _command(database, "offline-command")["status"] == "undeliverable"


def test_deadline_uses_schema_valid_timed_out_status(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    _insert_command(database, command_id="deadline", deadline_at="1970-01-01T00:00:05Z", updated_at_epoch_ms=4_000)
    result = ControlPlaneProjectionStore().reconcile_command_lifecycle(now_epoch_ms=10_000)
    assert result["reasons"] == {"deadline_expired": 1}
    assert _command(database, "deadline")["status"] == "timed_out"


def test_terminal_command_never_regresses_and_reconcile_is_idempotent(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    _insert_command(database, command_id="terminal", status="succeeded")
    import sqlite3
    conn = sqlite3.connect(database)
    try:
        conn.execute("UPDATE command_lifecycle SET lifecycle_stage='terminal',terminal_at='2026-07-01T00:00:00Z' WHERE command_id='terminal'")
        conn.commit()
    finally:
        conn.close()

    store = ControlPlaneProjectionStore()
    first = store.reconcile_command_lifecycle(now_epoch_ms=10_000_000, legacy_max_age_seconds=60)
    second = store.reconcile_command_lifecycle(now_epoch_ms=20_000_000, legacy_max_age_seconds=60)
    assert first["reconciled_count"] == second["reconciled_count"] == 0
    assert _command(database, "terminal")["status"] == "succeeded"


def test_unacknowledged_failure_requires_attention_and_acknowledgement_clears_it(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.record_command(
        command_id="attention-command", subject="agent.restart", status="undeliverable",
        entity_type="device", entity_id="offline-device", summary="Could not deliver restart.",
    )
    before = lite_phase3c_projections.collect_activity_summary()
    assert before["active_operations"] == 0
    assert before["attention_required"] == 1
    assert before["status"] == "attention"

    assert store.acknowledge_command_attention("attention-command") is True
    after = lite_phase3c_projections.collect_activity_summary()
    assert after["active_operations"] == 0
    assert after["attention_required"] == 0
    assert after["status"] == "healthy"
    assert store.acknowledge_command_attention("attention-command") is False


def test_record_command_terminal_attention_and_revision_change_only(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.record_command(
        command_id="command-one", subject="agent.restart", status="undeliverable",
        entity_type="device", entity_id="offline-one", recovery_action="legacy_orphan_reconciled",
    )
    first = _command(database, "command-one")
    assert first["attention_status"] == "active"
    assert first["recovery_action"] == "legacy_orphan_reconciled"
    first_revision = store.domain_revision("commands")
    store.record_command(
        command_id="command-one", subject="agent.restart", status="undeliverable",
        entity_type="device", entity_id="offline-one", recovery_action="legacy_orphan_reconciled",
    )
    assert store.domain_revision("commands") == first_revision


def test_legacy_none_attention_can_be_acknowledged_once_without_blocking_activity(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    _insert_command(database, command_id="legacy-none", status="undeliverable")
    import sqlite3
    conn = sqlite3.connect(database)
    try:
        conn.execute(
            "UPDATE command_lifecycle SET lifecycle_stage='failed',terminal_at='2026-07-01T00:00:00Z',attention_status='none',attention_updated_at=NULL,attention_updated_at_epoch_ms=0 WHERE command_id='legacy-none'"
        )
        conn.commit()
    finally:
        conn.close()

    assert lite_phase3c_projections.collect_activity_summary()["attention_required"] == 0
    store = ControlPlaneProjectionStore()
    commands_before = store.domain_revision("commands")
    audit_before = store.domain_revision("audit")
    assert store.acknowledge_command_attention("legacy-none") is True
    assert store.acknowledge_command_attention("legacy-none") is False
    row = _command(database, "legacy-none")
    assert row["status"] == "undeliverable"
    assert row["attention_status"] == "acknowledged"
    assert store.domain_revision("commands") == commands_before + 1
    assert store.domain_revision("audit") == audit_before + 1

    conn = sqlite3.connect(database)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM audit_evidence_index WHERE operation_id=? AND event_type='command.attention_acknowledged'",
            ("legacy-none",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1
    assert lite_phase3c_projections.collect_activity_summary()["attention_required"] == 0


def test_record_command_attention_is_transition_aware_and_preserves_cleared_state(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.record_command(command_id="transition-attention", subject="agent.restart", status="queued", entity_type="device", entity_id="offline-device")
    assert _command(database, "transition-attention")["attention_status"] == "none"
    store.record_command(command_id="transition-attention", subject="agent.restart", status="undeliverable", entity_type="device", entity_id="offline-device")
    activated = _command(database, "transition-attention")
    assert activated["status"] == "undeliverable"
    assert activated["attention_status"] == "active"

    import sqlite3
    conn = sqlite3.connect(database)
    try:
        conn.execute("UPDATE command_lifecycle SET attention_status='none',attention_updated_at=NULL,attention_updated_at_epoch_ms=0 WHERE command_id='transition-attention'")
        conn.commit()
    finally:
        conn.close()

    revision = store.domain_revision("commands")
    store.record_command(command_id="transition-attention", subject="agent.restart", status="undeliverable", entity_type="device", entity_id="offline-device")
    cleared = _command(database, "transition-attention")
    assert cleared["status"] == "undeliverable"
    assert cleared["attention_status"] == "none"
    assert cleared["attention_updated_at"] is None
    assert cleared["attention_updated_at_epoch_ms"] == 0
    assert store.domain_revision("commands") == revision


def test_record_command_duplicate_and_stale_events_preserve_acknowledgement(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.record_command(command_id="acknowledged-attention", subject="agent.restart", status="undeliverable", entity_type="device", entity_id="offline-device")
    assert store.acknowledge_command_attention("acknowledged-attention") is True
    revision = store.domain_revision("commands")
    store.record_command(command_id="acknowledged-attention", subject="agent.restart", status="undeliverable", entity_type="device", entity_id="offline-device")
    row = _command(database, "acknowledged-attention")
    assert row["status"] == "undeliverable"
    assert row["attention_status"] == "acknowledged"
    assert store.domain_revision("commands") == revision
    store.record_command(command_id="acknowledged-attention", subject="agent.restart", status="succeeded", entity_type="device", entity_id="offline-device")
    row = _command(database, "acknowledged-attention")
    assert row["status"] == "undeliverable"
    assert row["attention_status"] == "acknowledged"
    assert store.domain_revision("commands") == revision


def test_new_command_ids_activate_attention_independently(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    for command_id in ("retry-one", "retry-two"):
        store.record_command(command_id=command_id, subject="agent.restart", status="undeliverable", entity_type="device", entity_id="offline-device")
        assert _command(database, command_id)["attention_status"] == "active"
