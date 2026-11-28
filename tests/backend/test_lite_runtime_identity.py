"""Prepared runtime identity tests; no process or network probes are used."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()


def _values():
    return {
        "coordinated_generation": "gen-7",
        "authenticated_source_commit": "a" * 40,
        "installed_artifact_sha256": "b" * 64,
        "installed_source_inventory_sha256": "c" * 64,
        "fastapi_process_identity_sha256": "d" * 64,
        "worker_process_identity_sha256": "e" * 64,
        "core_supervisor_identity_sha256": "f" * 64,
        "runtime_reconciler_identity_sha256": "0" * 64,
        "loaded_policy_revision": "plr-known-good",
        "loaded_policy_module_sha256": "1" * 64,
        "loaded_policy_data_sha256": "2" * 64,
        "frontend_generation": "gen-7",
        "sqlite_schema_version": 67,
        "sqlite_migration_ledger_sha256": "3" * 64,
    }


def _database(monkeypatch, tmp_path):
    from api_fastapi.db.connection import reset_sqlite_path_cache
    path = tmp_path / "state" / "identity.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(path))
    reset_sqlite_path_cache()
    from api_fastapi.db.migrations import apply_migrations
    apply_migrations()
    return path


def test_runtime_identity_is_unknown_until_an_owner_publishes_evidence(monkeypatch, tmp_path):
    _database(monkeypatch, tmp_path)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services import lite_runtime_identity as identity
    with read_connection() as conn:
        result = identity.public_projection(conn)
    assert result["status"] == "unknown"
    assert result["reason_code"] == "runtime_identity_unavailable"
    assert result["execution_eligible"] is False


def test_runtime_identity_is_canonical_and_converged(monkeypatch, tmp_path):
    _database(monkeypatch, tmp_path)
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_runtime_identity as identity
    observation = identity.build_observation(status="stable", reason_code="converged", **_values())
    with connection() as conn:
        result = identity.record(conn, observation)
        assert result["status"] == "stable"
        assert result["converged"] is True
        assert identity.require_converged(conn, generation="gen-7")["coordinated_generation"] == "gen-7"


def test_runtime_identity_stale_and_corrupt_evidence_fail_closed(monkeypatch, tmp_path):
    _database(monkeypatch, tmp_path)
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_runtime_identity as identity
    old = datetime.now(timezone.utc) - timedelta(minutes=5)
    observation = identity.build_observation(
        status="stable", reason_code="converged", observed_at=old.isoformat().replace("+00:00", "Z"),
        stale_after=(old + timedelta(seconds=30)).isoformat().replace("+00:00", "Z"), **_values())
    with connection() as conn:
        identity.record(conn, observation)
        stale = identity.public_projection(conn)
        assert stale["status"] == "unknown"
        assert stale["reason_code"] == "runtime_identity_stale"
        conn.execute("UPDATE lite_runtime_identity_projection SET installed_artifact_sha256=?", ("4" * 64,))
        corrupt = identity.public_projection(conn)
    assert corrupt["status"] == "unknown"
    assert corrupt["reason_code"] == "runtime_identity_corrupt"


def test_runtime_identity_rejects_forged_or_partial_observations():
    from api_fastapi.services import lite_runtime_identity as identity
    with pytest.raises(ValueError, match="runtime_identity_incomplete"):
        identity.build_observation(status="stable", reason_code="converged", **{
            key: value for key, value in _values().items() if key != "worker_process_identity_sha256"
        })
    observation = identity.build_observation(status="stable", reason_code="converged", **_values())
    observation["identity_sha256"] = "5" * 64
    with pytest.raises(ValueError, match="runtime_identity_digest_mismatch"):
        # record() verifies the identity digest before touching the database.
        identity.record(sqlite3.connect(":memory:"), observation)
