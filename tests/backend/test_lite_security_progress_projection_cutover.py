from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


def _configure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str = "dual"
):
    ensure_runtime_path()
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", mode)
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE", "global")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_PUBLISHED_STALE_SECONDS", "30")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_RECEIVED_STALE_SECONDS", "30")
    from api_fastapi import deps
    from api_fastapi.services import lite_security

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    lite_security.stop_security_projection_runtime()
    with lite_security._SQLITE_PROGRESS_SNAPSHOT_LOCK:
        lite_security._SQLITE_PROGRESS_SNAPSHOT = None
        lite_security._SQLITE_PROGRESS_SNAPSHOT_DB = ""
        lite_security._SQLITE_PROGRESS_REFRESHED_AT = 0.0
        lite_security._SQLITE_PROGRESS_EPOCH = 0
    lite_security._SQLITE_PROGRESS_FAILURES = 0
    lite_security.invalidate_security_read_caches()
    return state, lite_security


def _command(run_id: str) -> dict[str, str]:
    return {
        "run_id": run_id,
        "command_id": run_id,
        "profile": "quick",
        "scope": "local",
        "requested_at": "2026-07-14T08:00:00Z",
    }


def test_committed_reservation_and_acceptance_seed_exact_first_progress(
    tmp_path, monkeypatch
):
    _, lite_security = _configure(tmp_path, monkeypatch, "dual")
    command = _command("security-first-progress")

    reservation = lite_security.reserve_scan_request(command)
    assert reservation["reserved"] is True
    queued = lite_security.split_progress_state()
    assert queued["run_id"] == command["run_id"]
    assert queued["status"] == "queued"
    assert queued["active_scan"] is True
    assert queued["percent"] >= 1
    assert queued["stage"]
    assert queued["sqlite_revision"] >= 1
    assert queued["projection_epoch"] >= 1
    assert queued["projection_source"] == "sqlite_committed"

    accepted = lite_security.mark_scan_accepted(command)
    assert accepted and accepted["run_id"] == command["run_id"]
    first_read = lite_security.split_progress_state()
    assert first_read["run_id"] == command["run_id"]
    assert first_read["status"] == "accepted"
    assert first_read["active_scan"] is True
    assert not (first_read["active_scan"] and first_read["run_id"] is None)


def test_projection_replacement_rejects_revision_percent_and_terminal_regressions(
    tmp_path, monkeypatch
):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    current = lite_security._remember_sqlite_progress(
        lite_security._sqlite_progress_payload(
            {
                "run_id": "security-monotonic",
                "profile": "quick",
                "status": "running",
                "percent": 58,
                "updated_at_epoch_ms": 2000,
                "requested_at_epoch_ms": 1000,
                "run_revision": 4,
                "domain_revision": 10,
            }
        )
    )
    older = lite_security._remember_sqlite_progress(
        lite_security._sqlite_progress_payload(
            {
                "run_id": "security-monotonic",
                "status": "running",
                "percent": 60,
                "updated_at_epoch_ms": 2100,
                "requested_at_epoch_ms": 1000,
                "run_revision": 5,
                "domain_revision": 9,
            }
        )
    )
    assert older["sqlite_revision"] == current["sqlite_revision"]
    backward_timestamp = lite_security._remember_sqlite_progress(
        lite_security._sqlite_progress_payload(
            {
                "run_id": "security-monotonic",
                "status": "running",
                "percent": 60,
                "updated_at_epoch_ms": 1900,
                "requested_at_epoch_ms": 1000,
                "run_revision": 5,
                "domain_revision": 11,
            }
        )
    )
    assert backward_timestamp["updated_at_epoch_ms"] == 2000
    older_run = lite_security._remember_sqlite_progress(
        lite_security._sqlite_progress_payload(
            {
                "run_id": "security-older-run",
                "status": "accepted",
                "percent": 5,
                "updated_at_epoch_ms": 3000,
                "requested_at_epoch_ms": 900,
                "run_revision": 1,
                "domain_revision": 12,
            }
        )
    )
    assert older_run["run_id"] == "security-monotonic"
    lower_percent = lite_security._remember_sqlite_progress(
        lite_security._sqlite_progress_payload(
            {
                "run_id": "security-monotonic",
                "status": "running",
                "percent": 42,
                "updated_at_epoch_ms": 2200,
                "requested_at_epoch_ms": 1000,
                "run_revision": 5,
                "domain_revision": 11,
            }
        )
    )
    assert lower_percent["percent"] == 58
    terminal = lite_security._remember_sqlite_progress(
        lite_security._sqlite_progress_payload(
            {
                "run_id": "security-monotonic",
                "status": "failed",
                "percent": 58,
                "updated_at_epoch_ms": 2300,
                "requested_at_epoch_ms": 1000,
                "run_revision": 6,
                "domain_revision": 12,
            }
        )
    )
    assert terminal["status"] == "failed"
    assert terminal["active_scan"] is False
    regressed_active = lite_security._remember_sqlite_progress(
        lite_security._sqlite_progress_payload(
            {
                "run_id": "security-monotonic",
                "status": "running",
                "percent": 70,
                "updated_at_epoch_ms": 2400,
                "requested_at_epoch_ms": 1000,
                "run_revision": 7,
                "domain_revision": 13,
            }
        )
    )
    assert regressed_active["status"] == "failed"
    assert regressed_active["active_scan"] is False


def test_progress_get_path_is_memory_only_after_priming(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    command = _command("security-memory-only")
    assert lite_security.reserve_scan_request(command)["reserved"] is True

    def forbidden_repository():
        raise AssertionError("Progress GET must not open SQLite")

    monkeypatch.setattr(lite_security, "_security_repository", forbidden_repository)
    payload = lite_security.split_progress_state()
    assert payload["run_id"] == command["run_id"]
    assert payload["read_projection"] == "memory"


def test_sqlite_mode_never_promotes_compatibility_json_to_progress_authority(
    tmp_path, monkeypatch
):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    lite_security.evidence.write_state(
        {
            **lite_security.default_state(),
            "status": "accepted",
            "last_run": {"run_id": "json-must-not-win", "status": "accepted"},
            "scan_progress": {
                "run_id": "json-must-not-win",
                "status": "accepted",
                "active_scan": True,
                "percent": 17,
            },
        }
    )
    with lite_security._SQLITE_PROGRESS_SNAPSHOT_LOCK:
        lite_security._SQLITE_PROGRESS_SNAPSHOT = None
        lite_security._SQLITE_PROGRESS_SNAPSHOT_DB = str(
            lite_security._security_store_api().database_path()
        )
        lite_security._SQLITE_PROGRESS_REFRESHED_AT = 0.0
    payload = lite_security.split_progress_state()
    assert payload["status"] == "unavailable"
    assert payload["run_id"] is None
    assert payload["projection_source"] == "sqlite_unavailable"
    assert "json-must-not-win" not in json.dumps(payload)


def test_sqlite_busy_uses_only_bounded_validated_memory(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    command = _command("security-bounded-memory")
    assert lite_security.reserve_scan_request(command)["reserved"] is True
    lite_security._SQLITE_PROGRESS_FAILURES = 1
    lite_security._SQLITE_PROGRESS_REFRESHED_AT = time.monotonic()
    bounded = lite_security.split_progress_state()
    assert bounded["run_id"] == command["run_id"]
    assert bounded["read_degraded"] is True
    assert bounded["projection_source"] == "bounded_memory_projection"

    lite_security._SQLITE_PROGRESS_REFRESHED_AT = (
        time.monotonic()
        - (lite_security._SQLITE_PROGRESS_MAX_FALLBACK_AGE_MS / 1000)
        - 1
    )
    expired = lite_security.split_progress_state()
    assert expired["status"] == "unavailable"
    assert expired["run_id"] is None


def test_terminal_commit_publishes_memory_projection_immediately(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "dual")
    command = _command("security-terminal-publish")
    assert lite_security.reserve_scan_request(command)["reserved"] is True
    lite_security.mark_scan_accepted(command)
    lite_security.mark_running(command)
    completed_at = "2026-07-14T10:01:00Z"
    state = {
        **lite_security.default_state(),
        "status": "healthy",
        "summary": "No urgent safety issues found.",
        "updated_at": completed_at,
        "last_run": {
            "run_id": command["run_id"],
            "command_id": command["run_id"],
            "status": "succeeded",
            "scan_profile": "quick",
            "started_at": "2026-07-14T08:00:01Z",
            "completed_at": completed_at,
            "summary": "No urgent safety issues found.",
            "score": 100,
        },
        "scan_progress": {
            "run_id": command["run_id"],
            "status": "succeeded",
            "active_scan": False,
            "percent": 100,
            "stage": "Evidence saved",
            "updated_at": completed_at,
        },
    }
    lite_security._write_security_state(state)
    progress = lite_security.split_progress_state()
    assert progress["run_id"] == command["run_id"]
    assert progress["status"] == "succeeded"
    assert progress["active_scan"] is False
    assert progress["percent"] == 100
    assert progress["projection_source"] == "sqlite_committed"


def test_sqlite_current_state_fails_closed_without_json_authority(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    lite_security.evidence.write_state(
        {
            **lite_security.default_state(),
            "status": "accepted",
            "last_run": {"run_id": "json-authority-forbidden", "status": "accepted"},
        }
    )

    def unavailable_sqlite():
        raise sqlite3.DatabaseError("database unavailable")

    monkeypatch.setattr(lite_security, "_sqlite_state_projection", unavailable_sqlite)
    payload = lite_security.current_state()
    assert payload["status"] == "unavailable"
    assert payload["storage_backend"] == "sqlite"
    assert "json-authority-forbidden" not in json.dumps(payload)



def test_restart_primes_terminal_truth_from_sqlite_without_json(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-terminal-restart",
        profile="quick",
        requested_at="2026-07-14T08:00:00Z",
    ).reserved
    repo.mark_running(
        "security-terminal-restart", started_at="2026-07-14T08:00:01Z"
    )
    repo.complete_run(
        "security-terminal-restart",
        summary="No urgent safety issues.",
        completed_at="2026-07-14T08:01:00Z",
    )
    with lite_security._SQLITE_PROGRESS_SNAPSHOT_LOCK:
        lite_security._SQLITE_PROGRESS_SNAPSHOT = None
        lite_security._SQLITE_PROGRESS_SNAPSHOT_DB = ""
        lite_security._SQLITE_PROGRESS_REFRESHED_AT = 0.0
    result = lite_security.initialize_security_sqlite_runtime(reconcile=False)
    assert result["progress_snapshot_primed"] is True
    payload = lite_security.split_progress_state()
    assert payload["run_id"] == "security-terminal-restart"
    assert payload["status"] == "succeeded"
    assert payload["active_scan"] is False


def test_published_but_never_received_uses_published_stale_threshold(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch, "dual")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-published-only",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_command_published(
        "security-published-only", published_at="2020-01-01T00:00:01Z"
    )
    repo.mark_accepted(
        "security-published-only", accepted_at="2020-01-01T00:00:02Z"
    )
    candidates = repo.list_stale_start_candidates(
        now="2020-01-01T00:01:00Z",
        published_stale_seconds=30,
        received_stale_seconds=300,
    )
    assert candidates[0]["run_id"] == "security-published-only"
    assert candidates[0]["stale_state"] == "published_not_received"



def test_submission_stage_timing_header_is_sanitized(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, "sqlite")
    from fastapi import Response
    from api_fastapi.routers import lite

    response = Response()
    lite._record_security_submission_timing(
        response, run_id="security-timing", started=1.0, auth_done=1.01,
        reservation_done=1.02, publish_done=1.03, lifecycle_committed=1.05,
    )
    header = response.headers["server-timing"]
    for stage in ("auth", "reservation", "publish", "lifecycle_commit", "total"):
        assert f"{stage};dur=" in header
    assert "security-timing" not in header


def test_mark_scan_accepted_preserves_publish_boundary_timestamp(
    tmp_path, monkeypatch
):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    command = {
        "run_id": "security-publish-boundary",
        "command_id": "security-publish-boundary",
        "profile": "quick",
        "requested_at": "2020-01-01T00:00:00Z",
        "command_published_at": "2020-01-01T00:00:01Z",
    }
    assert lite_security.reserve_scan_request(command)["reserved"] is True
    lite_security.mark_scan_accepted(command)

    row = SecuritySQLiteRepository().get_run("security-publish-boundary")
    assert row["command_published_at"] == "2020-01-01T00:00:01Z"
    assert row["accepted_at"] >= row["command_published_at"]


def test_delivery_lifecycle_timestamps_and_state_specific_candidates(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch, "dual")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-delivery",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_command_published(
        "security-delivery", published_at="2020-01-01T00:00:01Z"
    )
    repo.mark_accepted(
        "security-delivery", accepted_at="2020-01-01T00:00:02Z"
    )
    repo.mark_command_received(
        "security-delivery",
        received_at="2020-01-01T00:00:03Z",
        delivery_attempt=2,
    )
    row = repo.get_run("security-delivery")
    assert row["command_published_at"] == "2020-01-01T00:00:01Z"
    assert row["command_received_at"] == "2020-01-01T00:00:03Z"
    assert row["delivery_attempt"] == 2
    candidates = repo.list_stale_start_candidates(
        now="2020-01-01T00:01:00Z",
        published_stale_seconds=30,
        received_stale_seconds=30,
    )
    assert candidates[0]["stale_state"] == "received_not_started"
    repo.mark_running("security-delivery", started_at="2020-01-01T00:01:01Z")
    running = repo.get_run("security-delivery")
    assert running["execution_started_at"] == "2020-01-01T00:01:01Z"
    assert repo.list_stale_start_candidates(
        now="2020-01-01T01:00:00Z",
        published_stale_seconds=30,
        received_stale_seconds=30,
    ) == []



def test_worker_receipt_repairs_missing_publication_timestamp(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, "sqlite")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-worker-repair",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    row = repo.mark_command_received(
        "security-worker-repair",
        received_at="2020-01-01T00:00:02Z",
        published_at="2020-01-01T00:00:01Z",
        delivery_attempt=1,
    )
    assert row["command_published_at"] == "2020-01-01T00:00:01Z"
    assert row["command_received_at"] == "2020-01-01T00:00:02Z"


def test_late_api_commit_repairs_publication_without_regressing_running(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch, "sqlite")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-api-repair",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_command_received(
        "security-api-repair",
        received_at="2020-01-01T00:00:02Z",
        delivery_attempt=1,
    )
    repo.mark_running(
        "security-api-repair", started_at="2020-01-01T00:00:03Z"
    )
    row = repo.mark_published_and_accepted(
        "security-api-repair",
        published_at="2020-01-01T00:00:01Z",
        accepted_at="2020-01-01T00:00:04Z",
        summary="Queued",
    )
    assert row["status"] == "running"
    assert row["command_published_at"] == "2020-01-01T00:00:01Z"
    assert row["accepted_at"] is not None
    assert row["accepted_at"] <= row["execution_started_at"]
    assert row["execution_started_at"] == "2020-01-01T00:00:03Z"
    assert row["publication_repaired_after_worker_progress"] is True


def test_memory_progress_read_avoids_validated_database_path(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "sqlite")
    command = {
        "run_id": "security-memory-identity",
        "command_id": "security-memory-identity",
        "profile": "quick",
        "requested_at": "2020-01-01T00:00:00Z",
    }
    assert lite_security.reserve_scan_request(command)["reserved"] is True

    def forbidden_database_path():
        raise AssertionError("Progress memory reads must not resolve the database path")

    monkeypatch.setattr(
        lite_security._security_store_api(), "database_path", forbidden_database_path
    )
    payload = lite_security.split_progress_state()
    assert payload["run_id"] == "security-memory-identity"
    assert payload["read_projection"] == "memory"

def test_stale_release_requires_recovery_and_callback_idle(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "dual")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-stale-guard",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_accepted(
        "security-stale-guard", accepted_at="2020-01-01T00:00:01Z"
    )
    observed = lite_security.stale_accepted_runs(stale_seconds=30)
    assert lite_security.recover_stale_accepted_runs(
        stale_seconds=30,
        recovery_attempted=False,
        expected_candidates=observed,
    ) == []
    assert repo.get_run("security-stale-guard")["status"] == "accepted"
    assert lite_security.recover_stale_accepted_runs(
        stale_seconds=30,
        callback_inflight=True,
        recovery_attempted=True,
        expected_candidates=observed,
    ) == []
    assert repo.get_run("security-stale-guard")["status"] == "accepted"

    released = lite_security.recover_stale_accepted_runs(
        stale_seconds=30,
        callback_inflight=False,
        recovery_attempted=True,
        expected_candidates=observed,
        consumer_generation=3,
        recovery_count=2,
    )
    assert released[0]["run_id"] == "security-stale-guard"
    assert repo.get_run("security-stale-guard")["active_key"] is None
    retry = repo.reserve_scan(
        run_id="security-stale-retry-final",
        profile="quick",
        requested_at="2026-07-14T08:00:00Z",
    )
    assert retry.reserved is True
    evidence_rows = repo.list_evidence_refs("security-stale-guard")
    assert any(
        row["relative_path"].endswith("worker-start-recovery.json")
        for row in evidence_rows
    )
    recovery_file = next(
        lite_security.deps.settings().state_dir / row["relative_path"]
        for row in evidence_rows
        if row["relative_path"].endswith("worker-start-recovery.json")
    )
    text = recovery_file.read_text(encoding="utf-8").lower()
    for forbidden in ("password", "token", "nats://", "private_key"):
        assert forbidden not in text


def test_recovery_grace_period_change_prevents_terminalization(tmp_path, monkeypatch):
    _, lite_security = _configure(tmp_path, monkeypatch, "dual")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-grace-change",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_accepted(
        "security-grace-change", accepted_at="2020-01-01T00:00:01Z"
    )
    observed = lite_security.stale_accepted_runs(stale_seconds=30)
    repo.mark_command_received(
        "security-grace-change",
        received_at="2020-01-01T00:10:00Z",
        delivery_attempt=2,
    )
    released = lite_security.recover_stale_accepted_runs(
        stale_seconds=30,
        recovery_attempted=True,
        expected_candidates=observed,
    )
    assert released == []
    row = repo.get_run("security-grace-change")
    assert row["status"] == "accepted"
    assert row["active_key"] is not None



def test_concurrent_running_transition_prevents_stale_compare_and_set(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch, "dual")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    assert repo.reserve_scan(
        run_id="security-cas-race",
        profile="quick",
        requested_at="2020-01-01T00:00:00Z",
    ).reserved
    repo.mark_accepted("security-cas-race", accepted_at="2020-01-01T00:00:01Z")
    candidate = repo.list_stale_start_candidates(
        now="2020-01-01T00:10:00Z",
        published_stale_seconds=30,
        received_stale_seconds=30,
    )[0]
    repo.mark_running("security-cas-race", started_at="2020-01-01T00:10:01Z")
    failed = repo.fail_stale_start_run(
        "security-cas-race",
        expected_status=candidate["status"],
        expected_revision=candidate["revision"],
        expected_updated_at_epoch_ms=candidate["updated_at_epoch_ms"],
        expected_active_key=candidate["active_key"],
        completed_at="2020-01-01T00:10:02Z",
    )
    assert failed is None
    assert repo.get_run("security-cas-race")["status"] == "running"
    assert repo.get_run("security-cas-race")["active_key"] is not None
