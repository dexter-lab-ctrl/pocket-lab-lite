from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


def _configure_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str = "dual"):
    ensure_runtime_path()
    state = isolated_state_dir(tmp_path)
    database = state / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", mode)
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE", "global")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_RECENT_COMPLETION_SECONDS", "45")
    monkeypatch.delenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", raising=False)

    from api_fastapi import deps
    from api_fastapi.services import lite_security

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    lite_security.invalidate_security_read_caches()
    return state, database


def _iso(base: datetime, seconds: int = 0) -> str:
    return (base + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def test_s3_dual_write_lifecycle_keeps_sqlite_authoritative_and_json_compatible(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    command = {
        "run_id": "security-dual-lifecycle",
        "command_id": "security-dual-lifecycle",
        "profile": "quick",
        "scope": "local",
        "reason": "test",
        "requested_at": "2026-07-10T10:00:00Z",
    }
    reservation = lite_security.reserve_scan_request(command)
    assert reservation["reserved"] is True

    repo = SecuritySQLiteRepository()
    assert repo.get_run(command["run_id"])["status"] == "queued"
    assert lite_security.read_run(command["run_id"]) is None

    # NATS publication occurs outside the transaction; JSON projection follows.
    lite_security.record_queued_run(command)
    assert lite_security.read_run(command["run_id"])["status"] == "queued"
    lite_security.mark_scan_accepted(command)
    assert repo.get_run(command["run_id"])["status"] == "accepted"
    assert lite_security.read_run(command["run_id"])["status"] == "accepted"

    run = lite_security.mark_running(command)
    assert repo.get_run(command["run_id"])["status"] == "running"
    assert lite_security.read_run(command["run_id"])["status"] == "running"

    evidence_ref = lite_security.evidence.write_evidence(
        command["run_id"], "summary.json", {"summary": "Safe result"}
    )
    findings = [
        {
            "id": "finding-low",
            "source": "trivy",
            "severity": "low",
            "summary": "Review package metadata",
            "recommendation": "Keep packages current",
        }
    ]
    run.update(
        {
            "status": "succeeded",
            "summary": "No urgent safety issues.",
            "completed_at": "2026-07-10T10:02:00Z",
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 1,
            "info_count": 0,
            "tool_results": {
                "trivy": {"status": "completed", "finding_count": 1}
            },
            "evidence_refs": [evidence_ref],
            "execution_timeline": [
                {"id": "evidence", "title": "Evidence saved", "status": "completed"}
            ],
        }
    )
    final_state = lite_security.build_state(run, findings, [evidence_ref])
    lite_security._write_security_state(final_state)
    lite_security._write_run_projection(run)

    stored = repo.get_run(command["run_id"])
    assert stored["status"] == "succeeded"
    assert stored["active_key"] is None
    assert stored["low_count"] == 1
    assert repo.get_active_scan() is None
    assert len(repo.list_findings(command["run_id"])) == 1
    assert len(repo.list_tool_runs(command["run_id"])) == 1
    assert len(repo.list_evidence_refs(command["run_id"])) == 1
    assert repo.get_profile_snapshot("quick")["latest_run_id"] == command["run_id"]
    assert lite_security.read_run(command["run_id"])["status"] == "succeeded"
    assert lite_security.current_state()["last_run"]["run_id"] == command["run_id"]



def test_s3_json_projection_failure_keeps_committed_sqlite_truth(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    command = {
        "run_id": "security-projection-degraded",
        "command_id": "security-projection-degraded",
        "profile": "quick",
        "scope": "local",
        "requested_at": "2026-07-10T10:00:00Z",
    }
    assert lite_security.reserve_scan_request(command)["reserved"] is True
    lite_security.record_queued_run(command)
    run = lite_security.mark_running(command)
    run.update(
        {
            "status": "succeeded",
            "summary": "No urgent safety issues.",
            "completed_at": "2026-07-10T10:01:00Z",
            "tool_results": {},
            "evidence_refs": [],
        }
    )
    state = lite_security.build_state(run, [], [])

    def fail_projection(_payload):
        raise OSError("private path must not be returned")

    monkeypatch.setattr(lite_security.evidence, "write_state", fail_projection)
    result = lite_security._write_security_state(state)
    assert result["last_run"]["run_id"] == command["run_id"]

    stored = SecuritySQLiteRepository().get_run(command["run_id"])
    assert stored["status"] == "succeeded"
    assert stored["active_key"] is None
    with read_connection() as conn:
        row = conn.execute(
            "SELECT value_json FROM security_store_metadata WHERE metadata_key = ?",
            (f"json_projection:{command['run_id']}",),
        ).fetchone()
    assert row is not None
    assert '"degraded":true' in row["value_json"]
    assert "private path" not in row["value_json"]



def test_s3_startup_reconciliation_projects_interrupted_run_and_recovery_evidence(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STALE_ACTIVE_SECONDS", "900")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_FULL_STALE_ACTIVE_SECONDS", "3600")
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-startup-stale",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_running(
        "security-startup-stale", started_at="2020-01-01T00:00:01Z"
    )
    repo.record_progress(
        "security-startup-stale",
        status="running",
        stage="Checking Pocket Lab files",
        percent=42,
        message="Working",
        created_at="2020-01-01T00:00:02Z",
    )

    result = lite_security.initialize_security_sqlite_runtime(reconcile=True)
    assert result["reconciled"] == [
        {"run_id": "security-startup-stale", "profile": "quick"}
    ]
    stored = repo.get_run("security-startup-stale")
    assert stored["status"] == "failed"
    assert stored["current_percent"] == 42
    refs = repo.list_evidence_refs("security-startup-stale")
    assert any(ref["relative_path"].endswith("startup-recovery.json") for ref in refs)
    projected = lite_security.read_run("security-startup-stale")
    assert projected["status"] == "failed"
    assert lite_security.current_state()["last_run"]["run_id"] == "security-startup-stale"


def test_s4_recent_completion_window_and_app_identity_are_transactional(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    base = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    assert repo.reserve_scan(
        run_id="security-window", profile="quick", requested_at=_iso(base)
    ).reserved
    repo.complete_run(
        "security-window", summary="Done", completed_at=_iso(base, 10)
    )

    at_44 = repo.reserve_scan(
        run_id="security-window-44",
        profile="quick",
        requested_at=_iso(base, 54),
        recent_completion_seconds=45,
    )
    assert at_44.reserved is False
    assert at_44.reason == "recent_completion"
    assert at_44.run["run_id"] == "security-window"

    after_window = repo.reserve_scan(
        run_id="security-window-46",
        profile="quick",
        requested_at=_iso(base, 56),
        recent_completion_seconds=45,
    )
    assert after_window.reserved is True
    repo.fail_run(
        "security-window-46",
        failure_code="test_cleanup",
        failure_message="Test cleanup",
        completed_at=_iso(base, 57),
    )

    app_first = repo.reserve_scan(
        run_id="security-app-first",
        profile="app",
        app_id="photoprism",
        requested_at=_iso(base, 100),
    )
    app_duplicate = repo.reserve_scan(
        run_id="security-app-second",
        profile="app",
        app_id="photoprism",
        requested_at=_iso(base, 101),
    )
    assert app_first.reserved is True
    assert app_duplicate.reserved is False
    assert app_duplicate.reason == "active"
    assert app_duplicate.run["run_id"] == "security-app-first"
    assert app_duplicate.run["app_id"] == "photoprism"



def test_s4_api_concurrency_guard_publishes_one_worker_command(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.services.nats_bus import BUS
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    published: list[tuple[str, str, dict]] = []
    BUS.connected = True
    BUS.js = object()

    async def fake_publish(subject, event_type, data=None, *, trace_id=None):
        published.append((subject, event_type, data or {}))

    monkeypatch.setattr(BUS, "publish_json", fake_publish)
    http = client()
    first = http.post("/api/lite/security/check", json={"profile": "quick"})
    second = http.post("/api/lite/security/check", json={"profile": "quick"})

    assert first.status_code == 202
    assert second.status_code == 202
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["deduplicated"] is False
    assert second_payload["deduplicated"] is True
    assert second_payload["run_id"] == first_payload["run_id"]
    assert sum(
        1
        for subject, _, _ in published
        if subject == "pocketlab.commands.lite.security.scan"
    ) == 1
    active = SecuritySQLiteRepository().get_active_scan()
    assert active["run_id"] == first_payload["run_id"]



def test_s4_api_publish_failure_marks_submit_failed_and_releases_active_key(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from fastapi import HTTPException
    from api_fastapi.routers import lite as lite_router
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    async def fail_submit(*_args, **_kwargs):
        raise HTTPException(status_code=503, detail="worker queue unavailable")

    monkeypatch.setattr(lite_router, "submit_domain_command", fail_submit)
    response = client().post(
        "/api/lite/security/check", json={"profile": "quick"}
    )
    assert response.status_code == 503

    repo = SecuritySQLiteRepository()
    latest = repo.get_latest_run()
    assert latest["status"] == "failed"
    assert latest["failure_code"] == "submit_failed"
    assert latest["active_key"] is None
    assert repo.get_active_scan() is None


def test_s4_submit_failure_releases_active_key_and_stale_reconciliation_preserves_progress(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    command = {
        "run_id": "security-submit-failed",
        "command_id": "security-submit-failed",
        "profile": "quick",
        "scope": "local",
        "requested_at": "2026-07-10T08:00:00Z",
    }
    assert lite_security.reserve_scan_request(command)["reserved"] is True
    lite_security.fail_scan_submission(command["run_id"])

    repo = SecuritySQLiteRepository()
    failed = repo.get_run(command["run_id"])
    assert failed["status"] == "failed"
    assert failed["failure_code"] == "submit_failed"
    assert failed["active_key"] is None
    assert repo.get_active_scan() is None

    repo.reserve_scan(
        run_id="security-abandoned",
        profile="full",
        requested_at="2026-07-10T00:00:00Z",
    )
    repo.mark_running("security-abandoned", started_at="2026-07-10T00:00:01Z")
    repo.record_progress(
        "security-abandoned",
        status="running",
        stage="Pocket Lab files checked",
        percent=42,
        message="Working",
        created_at="2026-07-10T00:00:02Z",
    )
    reconciled = repo.reconcile_stale_runs(
        now="2026-07-10T12:00:00Z", stale_seconds=900
    )
    assert {item["run_id"] for item in reconciled} == {"security-abandoned"}
    abandoned = repo.get_run("security-abandoned")
    assert abandoned["status"] == "failed"
    assert abandoned["failure_code"] == "interrupted"
    assert abandoned["current_percent"] == 42
    assert abandoned["active_key"] is None
    assert repo.get_profile_snapshot("full")["latest_run_id"] == "security-abandoned"
    late = repo.record_progress(
        "security-abandoned", status="running", stage="late", percent=80
    )
    assert late["ignored_terminal"] is True
    assert repo.get_run("security-abandoned")["status"] == "failed"


def test_s4_transaction_rollback_leaves_no_partial_reservation(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.services import lite_security_store

    repo = lite_security_store.SecuritySQLiteRepository()

    def fail_revision(*_args, **_kwargs):
        raise RuntimeError("forced revision failure")

    monkeypatch.setattr(lite_security_store, "_bump_revision", fail_revision)
    with pytest.raises(RuntimeError, match="forced revision failure"):
        repo.reserve_scan(run_id="security-rollback", profile="quick")
    assert repo.get_run("security-rollback") is None
    assert repo.get_active_scan() is None



def test_s5_dual_mode_keeps_json_reads_until_sqlite_read_flag_is_enabled(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(run_id="security-dual-read", profile="quick").reserved
    repo.complete_run(
        "security-dual-read", summary="Done", score=99, completed_at="2026-07-10T09:00:00Z"
    )

    lite_security.invalidate_security_read_caches()
    json_summary = lite_security.summary_state()
    assert json_summary.get("storage_backend") != "sqlite"

    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    lite_security.invalidate_security_read_caches()
    sqlite_summary = lite_security.summary_state()
    assert sqlite_summary["storage_backend"] == "sqlite"
    assert sqlite_summary["last_run"]["run_id"] == "security-dual-read"


def test_s5_sqlite_compact_reads_keep_contract_etag_and_keyset_pagination(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "sqlite")
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    base = datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)
    for index in range(3):
        run_id = f"security-read-{index}"
        requested = _iso(base, index * 60)
        completed = _iso(base, index * 60 + 30)
        assert repo.reserve_scan(
            run_id=run_id, profile="quick", requested_at=requested
        ).reserved
        repo.mark_running(run_id, started_at=_iso(base, index * 60 + 1))
        repo.record_progress(
            run_id,
            status="running",
            stage="Checking Pocket Lab files",
            percent=58,
            message="Working",
            created_at=_iso(base, index * 60 + 2),
        )
        repo.complete_run(
            run_id,
            summary="No urgent safety issues.",
            score=99 - index,
            completed_at=completed,
            counts={"low": 1},
            findings=[
                {
                    "id": f"finding-{index}",
                    "source": "trivy",
                    "severity": "low",
                    "summary": "Review package metadata",
                }
            ],
            evidence_refs=[f"security/evidence/{run_id}/summary.json"],
            tool_results={"trivy": {"status": "completed", "finding_count": 1}},
            metadata={
                "coverage_summary": {"profile": "quick", "checked_targets": ["Pocket Lab files"]},
                "execution_timeline": [
                    {"id": "evidence", "title": "Evidence saved", "status": "completed"}
                ],
            },
        )

    lite_security.invalidate_security_read_caches()
    summary = lite_security.summary_state()
    progress = lite_security.split_progress_state()
    freshness = lite_security.split_freshness_state()
    profile = lite_security.split_profile_state("quick")
    first_page = lite_security.split_history_state(limit=2)
    second_page = lite_security.split_history_state(
        limit=2, cursor=first_page["next_cursor"]
    )
    details = lite_security.split_run_details_state("security-read-2")
    evidence_summary = lite_security.split_evidence_summary_state("security-read-2")

    for payload in (summary, progress, freshness, profile, first_page, details, evidence_summary):
        assert payload["storage_backend"] == "sqlite"
        assert "password" not in str(payload).lower()
        assert "private_key" not in str(payload).lower()
    assert summary["last_run"]["run_id"] == "security-read-2"
    assert progress["run_id"] == "security-read-2"
    assert profile["profile"] == "quick"
    assert len(first_page["history"]) == 2
    assert first_page["has_more"] is True
    assert isinstance(first_page["next_cursor"], str)
    assert [item["run_id"] for item in second_page["history"]] == ["security-read-0"]
    assert details["run_id"] == "security-read-2"
    assert "technical_json" not in str(details)
    assert evidence_summary["run_id"] == "security-read-2"

    http = client()
    response = http.get("/api/lite/security/summary")
    assert response.status_code == 200
    assert response.json()["storage_backend"] == "sqlite"
    etag = response.headers["etag"]
    not_modified = http.get(
        "/api/lite/security/summary", headers={"If-None-Match": etag}
    )
    assert not_modified.status_code == 304
    assert not_modified.headers["cache-control"] == "no-cache"


def test_cutover_hotfix_keeps_terminal_stage_canonical_with_evidence_timeline(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "dual")
    from api_fastapi.services import lite_security

    base_run = {
        "run_id": "security-terminal-stage",
        "scan_profile": "quick",
        "requested_at": "2026-07-10T10:00:00Z",
        "started_at": "2026-07-10T10:00:01Z",
        "execution_timeline": [
            {"id": "evidence", "title": "Evidence saved", "status": "completed"}
        ],
    }

    for status, expected in (
        ("succeeded", "Safety check complete"),
        ("degraded", "Safety check complete"),
        ("cancelled", "Safety check complete"),
        ("failed", "Safety check needs review"),
    ):
        progress = lite_security.scan_progress_for_run({**base_run, "status": status})
        assert progress["stage"] == expected
        assert progress["percent"] == 100


def test_cutover_hotfix_compact_sqlite_reads_do_not_build_global_projection(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch, "sqlite")
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-lightweight-reads",
        profile="quick",
        requested_at="2026-07-10T10:00:00Z",
    ).reserved
    repo.mark_running(
        "security-lightweight-reads", started_at="2026-07-10T10:00:01Z"
    )
    repo.complete_run(
        "security-lightweight-reads",
        summary="No urgent safety issues.",
        score=99,
        completed_at="2026-07-10T10:01:00Z",
        metadata={
            "coverage_summary": {"checked_targets": ["Pocket Lab files"]},
            "execution_timeline": [
                {"id": "evidence", "title": "Evidence saved", "status": "completed"}
            ],
        },
    )

    def fail_global_projection():
        raise AssertionError("compact endpoint rebuilt the global SQLite projection")

    monkeypatch.setattr(lite_security, "_sqlite_state_projection", fail_global_projection)
    lite_security.invalidate_security_read_caches()

    assert lite_security.summary_state()["storage_backend"] == "sqlite"
    assert lite_security.split_progress_state()["storage_backend"] == "sqlite"
    assert lite_security.split_freshness_state()["storage_backend"] == "sqlite"
    assert lite_security.split_profile_state("quick")["storage_backend"] == "sqlite"
    assert lite_security.split_history_state(limit=20)["storage_backend"] == "sqlite"
