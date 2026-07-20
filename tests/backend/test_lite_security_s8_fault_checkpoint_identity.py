from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "lib" / "long_gate_s8.py"
spec = importlib.util.spec_from_file_location("long_gate_s8_fault_checkpoint", MODULE_PATH)
assert spec and spec.loader
long_gate_s8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_gate_s8)


def test_authoritative_idle_checkpoint_accepts_terminal_sqlite_identity():
    run_id = long_gate_s8.authoritative_idle_checkpoint_run_id(
        {"active_scan": False, "run_id": "run-b", "status": "succeeded"},
        {"latest_run_id": "run-b"},
    )

    assert run_id == "run-b"


def test_authoritative_idle_checkpoint_rejects_stale_progress_identity():
    try:
        long_gate_s8.authoritative_idle_checkpoint_run_id(
            {"active_scan": False, "run_id": "run-a", "status": "succeeded"},
            {"latest_run_id": "run-b"},
        )
    except long_gate_s8.GateError as exc:
        assert "authoritative SQLite run identity" in str(exc)
    else:
        raise AssertionError("expected GateError")


def test_failed_restore_gate_uses_post_fault_authoritative_checkpoint():
    source = MODULE_PATH.read_text(encoding="utf-8")
    gate_start = source.index("def failed_restore_gate()")
    gate_end = source.index('record("gate-6-failed-restore-rollback"', gate_start)
    gate_source = source[gate_start:gate_end]

    configure_at = gate_source.index('configure_worker_fault("after_sqlite_promotion")')
    settle_at = gate_source.index("settled_progress = wait_security_idle", configure_at)
    database_at = gate_source.index("pre_database = database_state(db_path)", settle_at)
    checkpoint_at = gate_source.index(
        "checkpoint_run_id = authoritative_idle_checkpoint_run_id",
        database_at,
    )
    files_at = gate_source.index("pre_files = state_file_hashes(state_dir)", checkpoint_at)
    submit_at = gate_source.index("submitted_restore = api.post", files_at)

    assert configure_at < settle_at < database_at < checkpoint_at < files_at < submit_at
    assert "Worker fault setup changed the pre-failure Security run identity" not in gate_source
    assert "restored_run_id != checkpoint_run_id" in gate_source
