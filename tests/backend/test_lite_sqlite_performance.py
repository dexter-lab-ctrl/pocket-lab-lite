from __future__ import annotations

from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(target))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE", "global")
    return target


def _seed_runs(conn, count: int = 300) -> None:
    rows = []
    for index in range(count):
        profile = ("quick", "full", "app")[index % 3]
        app_id = "photoprism" if profile == "app" else ""
        epoch = 1_700_000_000_000 + index * 1_000
        rows.append(
            (
                f"security-plan-{index:04d}",
                profile,
                app_id,
                "PhotoPrism" if app_id else "",
                "succeeded",
                "Completed",
                99,
                0,
                "2026-07-20T00:00:00Z",
                "2026-07-20T00:00:00Z",
                "2026-07-20T00:00:00Z",
                epoch,
                epoch,
                epoch,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                "test",
                1,
                0,
                '{"coverage_summary":{"checked_targets":["bounded"]}}',
            )
        )
    conn.executemany(
        """
        INSERT INTO security_scan_runs(
            run_id, profile, app_id, app_label, status, summary, score,
            partial_results, requested_at, completed_at, updated_at,
            requested_at_epoch_ms, completed_at_epoch_ms, updated_at_epoch_ms,
            checks_reviewed, items_to_review, critical_count, high_count,
            medium_count, low_count, info_count, source, revision, evidence_saved,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _plan_details(conn, sql: str, parameters=()) -> list[str]:
    return [
        str(row[3])
        for row in conn.execute("EXPLAIN QUERY PLAN " + sql, parameters).fetchall()
    ]


def test_security_history_and_profile_queries_use_targeted_indexes(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import apply_migrations

    apply_migrations()
    with connection() as conn:
        _seed_runs(conn)
        plans = {
            "history": _plan_details(
                conn,
                "SELECT run_id FROM security_scan_runs "
                "ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC, run_id DESC LIMIT ?",
                (21,),
            ),
            "profile_history": _plan_details(
                conn,
                "SELECT run_id FROM security_scan_runs WHERE profile = ? AND app_id = ? "
                "ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC, run_id DESC LIMIT ?",
                ("quick", "", 21),
            ),
            "profile_latest": _plan_details(
                conn,
                "SELECT run_id FROM security_scan_runs WHERE profile = ? AND app_id = ? "
                "ORDER BY updated_at_epoch_ms DESC LIMIT 1",
                ("quick", ""),
            ),
            "app_latest": _plan_details(
                conn,
                "SELECT run_id FROM security_scan_runs WHERE profile = 'app' "
                "ORDER BY updated_at_epoch_ms DESC LIMIT 1",
            ),
        }

    expected = {
        "history": "idx_security_runs_history_cursor",
        "profile_history": "idx_security_runs_profile_history_cursor",
        "profile_latest": "idx_security_runs_profile_updated_latest",
        "app_latest": "idx_security_runs_app_updated_latest",
    }
    for name, index_name in expected.items():
        details = " | ".join(plans[name])
        assert index_name in details
        assert "TEMP B-TREE" not in details.upper()


def test_compact_history_keeps_cursor_order_without_loading_cold_metadata(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    completed_at = "2026-07-20T12:00:00Z"
    for suffix in ("a", "b", "c", "d", "e"):
        run_id = f"security-compact-{suffix}"
        repo.reserve_scan(run_id=run_id, profile="quick", requested_at=completed_at)
        repo.complete_run(
            run_id,
            completed_at=completed_at,
            summary="Completed",
            metadata={"coverage_summary": {"cold_payload": "x" * 8_000}},
        )

    first = repo.list_runs_page(limit=2, compact=True)
    second = repo.list_runs_page(
        limit=2,
        cursor_epoch_ms=first["next_cursor"]["epoch_ms"],
        cursor_run_id=first["next_cursor"]["run_id"],
        compact=True,
    )
    first_ids = [item["run_id"] for item in first["runs"]]
    second_ids = [item["run_id"] for item in second["runs"]]

    assert first_ids == sorted(first_ids, reverse=True)
    assert not set(first_ids) & set(second_ids)
    assert all("metadata" not in item for item in first["runs"] + second["runs"])
    assert repo.get_run(first_ids[0])["metadata"]["coverage_summary"]["cold_payload"]


def test_profile_snapshot_upsert_skips_noop_revision_and_timestamp_write(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    repo.reserve_scan(run_id="security-snapshot-noop", profile="quick")
    repo.complete_run(
        "security-snapshot-noop",
        completed_at="2026-07-20T12:00:00Z",
        summary="Completed",
    )
    before = repo.get_profile_snapshot("quick")

    with connection() as conn, begin_immediate(conn) as tx:
        repo._upsert_profile_snapshot(
            tx,
            "security-snapshot-noop",
            updated_at="2026-07-20T13:00:00Z",
        )

    after = repo.get_profile_snapshot("quick")
    assert after["revision"] == before["revision"]
    assert after["updated_at"] == before["updated_at"]
