from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_security_commit_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "dual")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    yield


def _terminal_payload(run_id: str):
    from api_fastapi.services import lite_security

    completed_at = "2026-07-19T18:05:39Z"
    run = {
        "run_id": run_id,
        "command_id": run_id,
        "profile": "quick",
        "scan_profile": "quick",
        "status": "succeeded",
        "summary": "Quick safety check completed.",
        "score": 97,
        "requested_at": completed_at,
        "started_at": completed_at,
        "completed_at": completed_at,
        "updated_at": completed_at,
        "partial_results": False,
        "checks_reviewed": 3,
        "items_to_review": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
        "tool_results": {},
        "coverage_summary": {},
        "execution_timeline": [],
        "evidence_refs": [],
    }
    state = {
        **lite_security.default_state(),
        "status": "healthy",
        "summary": run["summary"],
        "score": run["score"],
        "updated_at": completed_at,
        "last_run": run,
        "history": [run],
        "findings": [],
        "evidence_refs": [],
        "checks_reviewed": 3,
        "items_to_review": 0,
    }
    return run, state


def test_terminal_finalizer_commits_and_reads_back_before_projection():
    from api_fastapi.services import lite_security

    run_id = "security-worker-sqlite-commit-a"
    run, state = _terminal_payload(run_id)

    result = lite_security._finalize_security_scan_result(
        run=run,
        state=state,
        findings=[],
        evidence_refs=[],
    )

    receipt = result["commit"]
    assert receipt["status"] == "committed"
    assert receipt["sqlite_committed"] is True
    assert receipt["run_id"] == run_id
    assert receipt["terminal_status"] == "succeeded"

    stored = lite_security._security_repository().get_run(run_id)
    assert stored is not None
    assert stored["status"] == "succeeded"
    assert stored["completed_at"]
    assert result["run"]["run_id"] == run_id
    assert result["run"]["status"] == "succeeded"


def test_terminal_finalizer_fails_closed_when_sqlite_write_is_missing(monkeypatch):
    from api_fastapi.services import lite_security

    run_id = "security-worker-sqlite-commit-missing"
    run, state = _terminal_payload(run_id)
    monkeypatch.setattr(lite_security, "_write_security_state", lambda payload: payload)

    with pytest.raises(
        lite_security.SecurityTerminalCommitError,
        match="not found in authoritative storage",
    ):
        lite_security._finalize_security_scan_result(
            run=run,
            state=state,
            findings=[],
            evidence_refs=[],
        )


def test_domain_handler_does_not_publish_completion_without_commit(monkeypatch):
    from api_fastapi.services import domain_commands, lite_security

    run_id = "security-worker-domain-no-commit"
    run, state = _terminal_payload(run_id)
    published: list[str] = []

    async def fake_publish(subject, event_type, data=None, *, trace_id=None):
        published.append(subject)

    def fake_scan(command):
        return {
            "run": run,
            "state": state,
            "findings": [],
            "evidence_refs": [],
            "commit": {
                "status": "not_required",
                "run_id": run_id,
                "sqlite_committed": False,
            },
        }

    monkeypatch.setattr(domain_commands, "_publish", fake_publish)
    monkeypatch.setattr(lite_security, "run_security_scan", fake_scan)

    with pytest.raises(
        lite_security.SecurityTerminalCommitError,
        match="not found in authoritative storage",
    ):
        asyncio.run(
            domain_commands.handle_lite_security_scan(
                {"command_id": run_id, "run_id": run_id, "profile": "quick"}
            )
        )

    assert "pocketlab.events.lite.security.scan.completed" not in published
    assert "pocketlab.audit.lite.security.scan.completed" not in published
