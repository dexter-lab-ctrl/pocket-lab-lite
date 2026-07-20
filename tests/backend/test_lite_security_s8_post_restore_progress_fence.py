from __future__ import annotations

import importlib
from pathlib import Path


def _security_module():
    return importlib.import_module("api_fastapi.services.lite_security")


class FakeRepository:
    def __init__(self, runs: dict[str, dict]):
        self.runs = runs

    def get_run(self, run_id: str):
        return self.runs.get(run_id)


def test_restore_fence_replaces_orphaned_active_memory(monkeypatch):
    security = _security_module()
    restored_run_id = "security-restored-terminal"
    repository = FakeRepository(
        {restored_run_id: {"run_id": restored_run_id, "status": "succeeded"}}
    )

    monkeypatch.setattr(
        security,
        "_SQLITE_PROGRESS_SNAPSHOT",
        {
            "run_id": "security-orphaned-after-restore",
            "status": "accepted",
            "active_scan": True,
        },
    )
    monkeypatch.setattr(security, "_SQLITE_PROGRESS_PREPARED", object())
    monkeypatch.setattr(security, "_SQLITE_PROGRESS_SNAPSHOT_DB", "old-db")
    monkeypatch.setattr(
        security, "_SQLITE_PROGRESS_SNAPSHOT_IDENTITY", ("old", "accepted")
    )
    starting_epoch = security._SQLITE_PROGRESS_EPOCH

    def refresh(*, repository=None, run_id=None):
        assert repository is not None
        assert security._SQLITE_PROGRESS_SNAPSHOT is None
        assert security._SQLITE_PROGRESS_PREPARED is None
        return {
            "run_id": restored_run_id,
            "status": "succeeded",
            "active_scan": False,
        }

    monkeypatch.setattr(security, "_refresh_sqlite_progress_snapshot", refresh)

    result = security.fence_security_progress_after_database_restore(
        repository=repository
    )

    assert result["status"] == "passed"
    assert result["previous_run_id"] == "security-orphaned-after-restore"
    assert result["previous_active_scan"] is True
    assert result["run_id"] == restored_run_id
    assert result["scan_status"] == "succeeded"
    assert result["active_scan"] is False
    assert result["projection_epoch"] == starting_epoch + 1
    assert security._SQLITE_PROGRESS_READER_RESET.is_set()
    assert security._SQLITE_PROGRESS_DIRTY.is_set()


def test_restore_fence_fails_closed_for_missing_active_run(monkeypatch):
    security = _security_module()
    repository = FakeRepository({})

    monkeypatch.setattr(
        security,
        "_refresh_sqlite_progress_snapshot",
        lambda **_kwargs: {
            "run_id": "security-missing",
            "status": "accepted",
            "active_scan": True,
        },
    )

    try:
        security.fence_security_progress_after_database_restore(
            repository=repository
        )
    except RuntimeError as exc:
        assert "missing active run" in str(exc)
    else:
        raise AssertionError("missing restored active run was not rejected")


def test_restore_projection_refresh_uses_epoch_fence():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/"
        "lite_database_recovery.py"
    ).read_text(encoding="utf-8")

    function = source.split("def _refresh_security_projections()", 1)[1].split(
        "def _parity_check()", 1
    )[0]

    assert "fence_security_progress_after_database_restore" in function
    assert "reset_security_progress_after_database_restore" not in function
    assert function.index("invalidate_security_read_caches") < function.index(
        "fence_security_progress_after_database_restore"
    )
