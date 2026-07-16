from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/lib/long_gate_group4.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group4_wal", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_passive_checkpoint_and_health_use_wal_without_vacuum(tmp_path: Path):
    tool = load_tool()
    db = tmp_path / "fixture.sqlite3"
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
    connection.executemany("INSERT INTO sample(value) VALUES (?)", [(str(i),) for i in range(50)])
    connection.commit()
    checkpoint = tool.passive_checkpoint(db)
    health = tool.sqlite_health(db)
    connection.close()
    assert checkpoint["ok"] is True
    assert checkpoint["busy"] >= 0
    assert checkpoint["log_pages"] >= checkpoint["checkpointed_pages"]
    assert health["quick_check"] == "ok"
    assert health["journal_mode"] == "wal"
    source = TOOL.read_text(encoding="utf-8")
    assert "wal_checkpoint(PASSIVE)" in source
    assert "VACUUM" not in source.upper()


def test_wal_evaluation_counts_contention_and_latency_budgets():
    tool = load_tool()
    failures, summary = tool.evaluate_wal_samples(
        checkpoints=[{"busy": 0, "log_pages": 10, "checkpointed_pages": 8}],
        readers=[{"ok": True, "latency_seconds": 0.02}],
        writers=[{"ok": True, "latency_seconds": 0.03}],
        storage=[{"wal_bytes": 100}, {"wal_bytes": 200}],
        wal_budget_bytes=1024,
        reader_p95_budget=1.0,
        writer_p95_budget=1.0,
        contention_retry_budget=0,
    )
    assert failures == []
    assert summary["checkpoint_progress_samples"] == 1
    assert summary["wal_peak_bytes"] == 200

    failures, _ = tool.evaluate_wal_samples(
        checkpoints=[{"busy": 1, "log_pages": 10, "checkpointed_pages": 0}] * 3,
        readers=[{"ok": False, "error": "database_locked"}],
        writers=[{"ok": False, "error": "database_locked"}],
        storage=[{"wal_bytes": 0}, {"wal_bytes": 4096}],
        wal_budget_bytes=100,
        reader_p95_budget=1.0,
        writer_p95_budget=1.0,
        contention_retry_budget=0,
    )
    assert "checkpoint_busy_sustained" in failures
    assert "wal_growth_budget_exceeded" in failures
    assert "database_lock_budget_exceeded" in failures
