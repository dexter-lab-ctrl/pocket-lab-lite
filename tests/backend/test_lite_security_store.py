from __future__ import annotations

from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "json")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE", "global")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    return SecuritySQLiteRepository()


def test_lite_security_store_reserves_deduplicates_progress_and_completes(
    tmp_path, monkeypatch
):
    repo = _repo(tmp_path, monkeypatch)
    first = repo.reserve_scan(run_id="security-one", profile="quick")
    duplicate = repo.reserve_scan(run_id="security-two", profile="full")
    assert first.reserved is True
    assert duplicate.reserved is False
    assert duplicate.reason == "active"
    assert duplicate.run["run_id"] == "security-one"

    running = repo.mark_running("security-one")
    assert running["status"] == "running"
    progress = repo.record_progress(
        "security-one",
        status="running",
        stage="trivy_running",
        percent=42,
        message="Checking files",
        payload={"token": "do-not-store"},
    )
    repeated = repo.record_progress(
        "security-one",
        status="running",
        stage="trivy_running",
        percent=42,
        message="Checking files",
        payload={"token": "do-not-store"},
    )
    assert progress["deduplicated"] is False
    assert repeated["deduplicated"] is True
    assert repo.get_progress("security-one")["percent"] == 42

    result = repo.complete_run(
        "security-one",
        score=99,
        summary="Completed",
        counts={"low": 1},
        findings=[
            {
                "id": "finding-1",
                "source": "trivy",
                "severity": "low",
                "summary": "Review this item",
                "recommendation": "token=do-not-store",
            },
            {
                "id": "finding-1",
                "source": "trivy",
                "severity": "low",
                "summary": "Duplicate input",
            },
        ],
        evidence_refs=[
            "security/evidence/security-one/summary.json",
            "security/evidence/security-one/summary.json",
        ],
        tool_results={"trivy": {"status": "completed", "finding_count": 1}},
    )
    assert result["run"]["status"] == "succeeded"
    assert result["run"]["active_key"] is None
    assert repo.get_active_scan() is None
    assert repo.get_profile_snapshot("quick")["latest_run_id"] == "security-one"
    assert len(repo.list_findings("security-one")) == 1
    assert len(repo.list_evidence_refs("security-one")) == 1
    assert repo.list_evidence_refs("security-one")[0]["relative_path"].startswith(
        "security/evidence/security-one/"
    )
    finding_text = str(repo.list_findings("security-one"))
    assert "do-not-store" not in finding_text
    assert "***REDACTED***" in finding_text


def test_lite_security_store_recent_completion_snapshot_revision_and_history_bounds(
    tmp_path, monkeypatch
):
    repo = _repo(tmp_path, monkeypatch)
    initial_revision = repo.get_summary()["revision"]
    repo.reserve_scan(run_id="security-first", profile="quick")
    repo.complete_run("security-first", score=98, summary="First")
    first_snapshot = repo.get_profile_snapshot("quick")
    recent = repo.reserve_scan(
        run_id="security-too-soon",
        profile="quick",
        recent_completion_seconds=45,
    )
    assert recent.reserved is False
    assert recent.reason == "recent_completion"
    assert recent.run["run_id"] == "security-first"

    repo.reserve_scan(run_id="security-second", profile="quick")
    repo.complete_run("security-second", score=99, summary="Second")
    second_snapshot = repo.get_profile_snapshot("quick")
    assert first_snapshot["revision"] == 1
    assert second_snapshot["revision"] == 2
    assert second_snapshot["latest_run_id"] == "security-second"
    assert repo.get_summary()["revision"] > initial_revision

    for index in range(105):
        run_id = f"security-history-{index:03d}"
        repo.reserve_scan(run_id=run_id, profile="full")
        repo.complete_run(run_id, score=90, summary="History")
    assert len(repo.list_runs(limit=1000)) == 100
    assert len(repo.list_runs(limit=1)) == 1


def test_lite_security_store_validates_modes_profiles_statuses_and_paths(
    tmp_path, monkeypatch
):
    repo = _repo(tmp_path, monkeypatch)
    from api_fastapi.services.lite_security_store import (
        InvalidSecurityStoreValue,
        security_store_mode,
        sqlite_shadow_read_enabled,
    )

    monkeypatch.delenv("POCKETLAB_LITE_SECURITY_STORE_MODE", raising=False)
    monkeypatch.delenv(
        "POCKETLAB_LITE_SECURITY_SQLITE_SHADOW_READ", raising=False
    )
    assert security_store_mode() == "json"
    assert sqlite_shadow_read_enabled() is False
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "invalid")
    with pytest.raises(InvalidSecurityStoreValue):
        security_store_mode()
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "json")
    with pytest.raises(InvalidSecurityStoreValue):
        repo.reserve_scan(
            run_id="security-app", profile="app", app_id="unsupported"
        )
    with pytest.raises(InvalidSecurityStoreValue):
        repo.reserve_scan(run_id="security-profile", profile="quick'; DROP TABLE x;--")
    repo.reserve_scan(run_id="security-status", profile="quick")
    with pytest.raises(InvalidSecurityStoreValue):
        repo.record_progress("security-status", status="unknown-status")
    with pytest.raises(InvalidSecurityStoreValue):
        repo.record_progress("security-status", status="running", percent=101)


def test_lite_security_store_queries_are_parameterized(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    repo.reserve_scan(run_id="security-safe", profile="quick")
    repo.complete_run("security-safe", summary="Safe")
    assert repo.get_run("security-safe") is not None
    assert repo.get_run("security-safe'; DROP TABLE security_scan_runs;--") is None
    assert repo.get_run("security-safe") is not None
