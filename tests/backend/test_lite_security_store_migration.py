from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_legacy_state(root: Path) -> tuple[dict, list[Path]]:
    runs = root / "runs"
    latest_evidence = root / "evidence" / "security-latest"
    runs.mkdir(parents=True)
    latest_evidence.mkdir(parents=True)
    older = {
        "run_id": "security-older",
        "status": "succeeded",
        "scan_profile": "full",
        "summary": "Older",
        "score": 94,
        "requested_at": "2026-07-10T08:00:00Z",
        "completed_at": "2026-07-10T08:05:00Z",
        "evidence_refs": [
            "security/evidence/security-older/missing-summary.json"
        ],
    }
    latest = {
        "run_id": "security-latest",
        "status": "succeeded",
        "scan_profile": "quick",
        "summary": "Done",
        "score": 98,
        "requested_at": "2026-07-10T09:00:00Z",
        "started_at": "2026-07-10T09:01:00Z",
        "completed_at": "2026-07-10T09:05:00Z",
        "low_count": 1,
        "tool_results": {
            "trivy": {
                "status": "completed",
                "finding_count": 1,
                "token": "tool-secret",
            }
        },
        "evidence_refs": [
            "security/evidence/security-latest/summary.json"
        ],
    }
    state = {
        "status": "healthy",
        "score": 98,
        "updated_at": "2026-07-10T09:05:00Z",
        "last_run": latest,
        "history": [latest, older],
        "findings": [
            {
                "id": "f1",
                "source": "trivy",
                "severity": "low",
                "summary": "Review token=legacy-secret",
            }
        ],
        "evidence_refs": latest["evidence_refs"],
        "scan_progress": {
            "run_id": "security-latest",
            "status": "succeeded",
            "percent": 100,
            "stage": "complete",
        },
    }
    state_path = root / "security_state.json"
    older_path = runs / "security-older.json"
    latest_path = runs / "security-latest.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    older_path.write_text(json.dumps(older), encoding="utf-8")
    latest_path.write_text(json.dumps(latest), encoding="utf-8")
    (runs / "malformed.json").write_text("{not-json", encoding="utf-8")
    evidence_path = latest_evidence / "summary.json"
    evidence_path.write_text(json.dumps({"safe": True}), encoding="utf-8")
    return state, [state_path, older_path, latest_path, evidence_path]


def test_lite_security_legacy_import_is_previewable_idempotent_and_non_destructive(
    tmp_path, monkeypatch
):
    ensure_runtime_path()
    state_dir = tmp_path / "state"
    security = state_dir / "security"
    state, source_paths = _write_legacy_state(security)
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH", str(state_dir / "pocketlab-lite.sqlite3")
    )
    source_hashes = {path: _sha(path) for path in source_paths}

    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    preview = repo.import_legacy_state(source_root=security, preview=True)
    assert preview["runs_seen"] == 2
    assert preview["runs_imported"] == 2
    assert preview["malformed_optional_files"] == ["malformed.json"]
    assert repo.list_runs() == []

    first = repo.import_legacy_state(
        source_root=security, hash_evidence=True
    )
    second = repo.import_legacy_state(source_root=security)
    assert first["runs_imported"] == 2
    assert second["runs_imported"] == 0
    assert second["runs_skipped"] == 2
    assert "unchanged" in second["warnings"][0].lower()
    assert len(repo.list_runs()) == 2
    assert len(repo.list_findings("security-latest")) == 1
    finding_text = str(repo.list_findings("security-latest"))
    assert "legacy-secret" not in finding_text
    assert "***REDACTED***" in finding_text

    latest_refs = repo.list_evidence_refs("security-latest")
    assert latest_refs[0]["sha256"] == _sha(
        security / "evidence" / "security-latest" / "summary.json"
    )
    missing_refs = repo.list_evidence_refs("security-older")
    assert missing_refs[0]["metadata"]["missing"] is True
    assert repo.compare_json_state(state)["matched"] is True

    with read_connection() as conn:
        metadata = conn.execute(
            "SELECT value_json FROM security_store_metadata WHERE metadata_key = ?",
            ("legacy_import:last",),
        ).fetchone()[0]
        database_text = "\n".join(
            str(row[0])
            for row in conn.execute(
                "SELECT summary FROM security_scan_runs UNION ALL "
                "SELECT metadata_json FROM security_scan_tool_runs"
            )
        )
    assert str(tmp_path) not in metadata
    assert "tool-secret" not in database_text
    for path, checksum in source_hashes.items():
        assert _sha(path) == checksum


def test_lite_security_import_handles_empty_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    security = tmp_path / "state" / "security"
    security.mkdir(parents=True)
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    preview = repo.import_legacy_state(source_root=security, preview=True)
    applied = repo.import_legacy_state(source_root=security)
    assert preview["runs_seen"] == preview["runs_imported"] == 0
    assert applied["runs_seen"] == applied["runs_imported"] == 0
    assert repo.list_runs() == []


def test_lite_security_import_rolls_back_interrupted_transaction(
    tmp_path, monkeypatch
):
    ensure_runtime_path()
    security = tmp_path / "state" / "security"
    _write_legacy_state(security)
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()

    def fail_findings(*_args, **_kwargs):
        raise RuntimeError("interrupted import")

    monkeypatch.setattr(repo, "_replace_findings", fail_findings)
    with pytest.raises(RuntimeError, match="interrupted"):
        repo.import_legacy_state(source_root=security)
    assert repo.list_runs() == []


def test_lite_security_shadow_compare_detects_only_bounded_field_names(
    tmp_path, monkeypatch
):
    ensure_runtime_path()
    security = tmp_path / "state" / "security"
    state, _ = _write_legacy_state(security)
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    repo.import_legacy_state(source_root=security)
    assert repo.compare_json_state(state, record=False)["matched"] is True
    changed = {**state, "score": 12, "last_run": {**state["last_run"], "score": 12}}
    mismatch = repo.compare_json_state(changed, record=False)
    assert mismatch["matched"] is False
    assert mismatch["mismatch_fields"] == ["score"]
    serialized = json.dumps(mismatch)
    assert "legacy-secret" not in serialized
    assert "tool-secret" not in serialized


def test_lite_security_import_fails_safely_for_malformed_core_state(
    tmp_path, monkeypatch
):
    ensure_runtime_path()
    security = tmp_path / "state" / "security"
    security.mkdir(parents=True)
    (security / "security_state.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    from api_fastapi.services.lite_security_store import (
        SecuritySQLiteRepository,
        SecurityStoreError,
    )

    with pytest.raises(SecurityStoreError):
        SecuritySQLiteRepository().import_legacy_state(source_root=security)


def test_lite_security_shadow_failure_does_not_break_json_path_or_log_payload(
    tmp_path, monkeypatch, caplog
):
    ensure_runtime_path()
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "json")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_SHADOW_READ", "1")
    from api_fastapi.services import lite_security, lite_security_store

    def fail_shadow(_state):
        raise RuntimeError("token=must-not-be-logged")

    monkeypatch.setattr(lite_security_store, "shadow_compare_if_enabled", fail_shadow)
    state = {"summary": "JSON remains authoritative", "token": "must-not-be-logged"}
    with caplog.at_level("WARNING"):
        assert lite_security._shadow_compare_sqlite_state(state) is None
    assert "RuntimeError" in caplog.text
    assert "must-not-be-logged" not in caplog.text


def test_history_projection_uses_shared_deterministic_order_after_sorting(
    tmp_path, monkeypatch
):
    ensure_runtime_path()
    security = tmp_path / "state" / "security"
    security.mkdir(parents=True)
    runs = [
        {
            "run_id": "security-b",
            "status": "succeeded",
            "scan_profile": "quick",
            "requested_at": "2026-07-18T09:00:00Z",
            "updated_at": "2026-07-18T09:02:00Z",
        },
        {
            "run_id": "security-a",
            "status": "succeeded",
            "scan_profile": "quick",
            "requested_at": "2026-07-18T09:00:00Z",
            "updated_at": "2026-07-18T09:02:00Z",
        },
        {
            "run_id": "security-latest",
            "status": "succeeded",
            "scan_profile": "quick",
            "requested_at": "2026-07-18T10:00:00Z",
            "completed_at": "2026-07-18T10:01:00Z",
        },
    ]
    state = {
        "last_run": runs[2],
        "history": list(reversed(runs)),
        "scan_progress": {},
    }
    (security / "security_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    run_dir = security / "runs"
    run_dir.mkdir()
    for item in runs:
        (run_dir / f'{item["run_id"]}.json').write_text(
            json.dumps(item), encoding="utf-8"
        )

    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    from api_fastapi.services.lite_security_store import (
        DEFAULT_HISTORY_LIMIT,
        SecuritySQLiteRepository,
        _json_shadow_projection,
    )

    repo = SecuritySQLiteRepository()
    repo.import_legacy_state(source_root=security, reconcile=True)
    expected = ["security-latest", "security-b", "security-a"]
    assert _json_shadow_projection(state)["latest_run_ids"] == expected
    assert repo._sqlite_shadow_projection()["latest_run_ids"] == expected
    assert len(repo._sqlite_shadow_projection()["latest_run_ids"]) <= DEFAULT_HISTORY_LIMIT
    assert [item["run_id"] for item in repo.list_runs_page(limit=3)["runs"]] == expected


def test_reconcile_deletes_only_noncanonical_runs_and_converges_atomically(
    tmp_path, monkeypatch
):
    ensure_runtime_path()
    security = tmp_path / "state" / "security"
    state, _ = _write_legacy_state(security)
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    from api_fastapi.db.connection import connection
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    repo.import_legacy_state(source_root=security)
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO security_scan_runs(
                run_id, profile, app_id, app_label, status, summary,
                partial_results, requested_at, updated_at,
                requested_at_epoch_ms, updated_at_epoch_ms,
                checks_reviewed, items_to_review, critical_count,
                high_count, medium_count, low_count, info_count,
                source, revision, evidence_saved
            ) VALUES (
                'stale-run', 'quick', '', '', 'succeeded', 'stale',
                0, '2026-07-19T00:00:00Z', '2026-07-19T00:00:00Z',
                1784419200000, 1784419200000,
                0, 0, 0, 0, 0, 0, 0,
                'test', 1, 0
            )
            """
        )
        conn.commit()

    before_revision = repo.get_domain_revision()["revision"]
    report = repo.import_legacy_state(
        source_root=security, force=True, reconcile=True
    )
    after_revision = repo.get_domain_revision()["revision"]

    assert report["reconciled"] is True
    assert report["runs_deleted"] == 1
    assert report["parity_matched"] is True
    assert after_revision == before_revision + 1
    assert {item["run_id"] for item in repo.list_runs(limit=100)} == {
        "security-latest",
        "security-older",
    }
    assert repo.compare_json_state(state, record=False)["matched"] is True


def test_reconcile_rolls_back_when_parity_does_not_converge(tmp_path, monkeypatch):
    ensure_runtime_path()
    security = tmp_path / "state" / "security"
    _write_legacy_state(security)
    monkeypatch.setenv(
        "POCKETLAB_LITE_DB_PATH",
        str(tmp_path / "state" / "pocketlab-lite.sqlite3"),
    )
    from api_fastapi.services.lite_security_store import (
        SecuritySQLiteRepository,
        SecurityStoreError,
    )

    repo = SecuritySQLiteRepository()
    monkeypatch.setattr(
        repo,
        "_compare_json_state_with_connection",
        lambda *_args, **_kwargs: {"matched": False},
    )
    with pytest.raises(SecurityStoreError, match="did not converge"):
        repo.import_legacy_state(source_root=security, reconcile=True)
    assert repo.list_runs(limit=100) == []
