from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    db_path = tmp_path / "state" / "security.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(db_path))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    return SecuritySQLiteRepository(), db_path


def _events(repo, run_id, count, *, terminal=True):
    repo.reserve_scan(run_id=run_id, profile="quick")
    repo.mark_running(run_id)
    for index in range(count):
        repo.record_progress(
            run_id,
            status="running",
            stage=f"stage-{index}",
            percent=min(99, index + 1),
            message="Working",
        )
    if terminal:
        repo.complete_run(run_id, score=99, summary="Done")


def _age_all(db_path: Path, epoch_ms: int):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE security_scan_progress_events SET created_at_epoch_ms = ?",
            (epoch_ms,),
        )


def test_retention_preserves_active_run_and_terminal_event(tmp_path, monkeypatch):
    repo, db_path = _repo(tmp_path, monkeypatch)
    _events(repo, "security-complete", 8, terminal=True)
    _events(repo, "security-active", 8, terminal=False)
    old = int((time.time() - 90 * 86400) * 1000)
    _age_all(db_path, old)
    active_before = len(repo.list_progress_events("security-active", limit=100))
    terminal_id = repo.get_latest_progress_event("security-complete")["event_id"]
    result = repo.prune_progress_events(
        retention_days=30, max_rows=100, min_per_active_run=2, batch_size=5
    )
    assert result["rows_deleted"] <= 5
    assert len(repo.list_progress_events("security-active", limit=100)) == active_before
    assert repo.get_progress_event(terminal_id) is not None


def test_age_and_row_cap_pruning_are_bounded_and_keep_minimum(tmp_path, monkeypatch):
    repo, db_path = _repo(tmp_path, monkeypatch)
    for index in range(12):
        _events(repo, f"security-{index}", 12, terminal=True)
    old = int((time.time() - 90 * 86400) * 1000)
    _age_all(db_path, old)
    before = repo.get_latest_progress_event_id()
    first = repo.prune_progress_events(
        retention_days=30, max_rows=100, min_per_active_run=3, batch_size=7
    )
    assert first["rows_deleted"] == 7
    assert first["rows_after"] < first["rows_before"]
    assert repo.get_latest_progress_event_id() == before
    for index in range(12):
        assert len(repo.list_progress_events(f"security-{index}", limit=100)) >= 3


def test_retention_service_uses_controlled_config_and_quick_check_stays_ok(tmp_path, monkeypatch):
    repo, db_path = _repo(tmp_path, monkeypatch)
    _events(repo, "security-retain", 6, terminal=True)
    monkeypatch.setenv("POCKETLAB_SECURITY_PROGRESS_RETENTION_DAYS", "30")
    monkeypatch.setenv("POCKETLAB_SECURITY_PROGRESS_MAX_ROWS", "100")
    monkeypatch.setenv("POCKETLAB_SECURITY_PROGRESS_MIN_PER_ACTIVE_RUN", "2")
    from api_fastapi.services import lite_security

    result = lite_security.run_security_progress_retention(repository=repo, max_batches=2)
    assert result["config"] == {
        "retention_days": 30,
        "max_rows": 100,
        "min_per_active_run": 2,
        "batch_size": 500,
    }
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_retention_does_not_touch_evidence_or_wal_files(tmp_path, monkeypatch):
    repo, db_path = _repo(tmp_path, monkeypatch)
    _events(repo, "security-evidence", 3, terminal=True)
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text("safe evidence")
    wal = Path(str(db_path) + "-wal")
    shm = Path(str(db_path) + "-shm")
    before_evidence = evidence_file.read_bytes()
    before_paths = (wal.exists(), shm.exists())
    repo.prune_progress_events(retention_days=30, max_rows=100, min_per_active_run=2)
    assert evidence_file.read_bytes() == before_evidence
    assert (wal.exists(), shm.exists()) == before_paths


def test_request_handlers_do_not_invoke_retention():
    ensure_runtime_path()
    router = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text()
    for handler in ("get_lite_security_progress", "get_lite_security_events"):
        section = router.split(f"def {handler}", 1)[1].split("@router.", 1)[0]
        assert "run_security_progress_retention" not in section
