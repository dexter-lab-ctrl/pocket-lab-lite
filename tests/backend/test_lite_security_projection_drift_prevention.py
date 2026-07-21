from __future__ import annotations

import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_projection_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "dual")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    yield


def _completed_run(completed_at: str = "2026-07-20T19:55:40Z"):
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    run_id = "security-projection-fence"
    repo.reserve_scan(run_id=run_id, profile="quick", requested_at=completed_at)
    repo.mark_running(run_id, started_at=completed_at)
    repo.complete_run(
        run_id,
        completed_at=completed_at,
        score=98,
        summary="Completed",
        findings=[],
        evidence_refs=[],
        tool_results={},
    )
    return repo, run_id


def _write_authoritative_projections():
    from api_fastapi.services import lite_security, lite_security_evidence

    repo = lite_security._security_repository()
    latest = repo.get_latest_run()
    projected = lite_security._sqlite_run_payload(
        repo, latest, include_details=True, include_related=True
    )
    lite_security._write_run_projection(projected)
    _, state, _ = lite_security._sqlite_state_projection()
    lite_security_evidence.write_state(state)
    lite_security.write_compact_security_state(state)


def test_projection_compare_normalizes_equivalent_iso_timestamps():
    from api_fastapi.services.lite_security_store import _compare_projections

    left = {"latest_completed_at": "2026-07-20T19:55:40Z"}
    right = {"latest_completed_at": "2026-07-20T19:55:40.000000+00:00"}

    result = _compare_projections(left, right)

    assert result["matched"] is True
    assert result["mismatch_fields"] == []


def test_repair_rebuilds_only_json_projection_and_preserves_revision():
    from api_fastapi.services import lite_security, lite_security_evidence

    repo, run_id = _completed_run()
    _write_authoritative_projections()
    revision_before = repo.get_domain_revision()["revision"]

    run_path = lite_security_evidence.runs_dir() / f"{run_id}.json"
    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    run_payload["completed_at"] = "2026-07-20T19:55:39Z"
    run_path.write_text(json.dumps(run_payload), encoding="utf-8")

    state_path = lite_security_evidence.state_path()
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["last_run"]["completed_at"] = "2026-07-20T19:55:39Z"
    for item in state_payload.get("history", []):
        if item.get("run_id") == run_id:
            item["completed_at"] = "2026-07-20T19:55:39Z"
    state_path.write_text(json.dumps(state_payload), encoding="utf-8")

    before = repo.compare_legacy_source(record=False)
    assert before["mismatch_fields"] == ["latest_completed_at"]
    assert before["repairable_derived_only"] is True

    result = lite_security.repair_security_projection_drift(record=True)

    assert result["matched"] is True
    assert result["repaired"] is True
    assert result["repair_attempted"] is True
    assert result["runs_deleted"] == 0
    assert result["domain_revision_unchanged"] is True
    assert repo.get_domain_revision()["revision"] == revision_before
    assert repo.compare_legacy_source(record=False)["matched"] is True


def test_repair_fails_closed_for_non_derived_mismatch():
    from api_fastapi.services import lite_security, lite_security_evidence

    repo, run_id = _completed_run()
    _write_authoritative_projections()
    revision_before = repo.get_domain_revision()["revision"]

    run_path = lite_security_evidence.runs_dir() / f"{run_id}.json"
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    run_path.write_text(json.dumps(payload), encoding="utf-8")

    result = lite_security.repair_security_projection_drift(record=True)

    assert result["matched"] is False
    assert result["repair_attempted"] is False
    assert result["repaired"] is False
    assert result["repair_blocked_reason"] == "non_derived_mismatch"
    assert repo.get_domain_revision()["revision"] == revision_before
