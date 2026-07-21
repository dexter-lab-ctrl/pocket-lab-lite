from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    yield


def test_marker_inspection_distinguishes_absent_invalid_and_valid(tmp_path):
    from api_fastapi.services import lite_security_generation

    module = importlib.reload(lite_security_generation)
    assert module.inspect_security_progress_generation()["status"] == "absent"

    path = module.marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    assert module.inspect_security_progress_generation()["status"] == "invalid"

    marker = module.publish_security_progress_generation(
        run_id="security-current",
        sqlite_revision=42,
        database_instance_id="database-current",
        published_at="2026-07-21T10:00:00Z",
        reason="cold_start_sqlite_rebuild",
    )
    inspected = module.inspect_security_progress_generation()
    assert inspected["status"] == "valid"
    assert inspected["marker"] == marker
    assert marker["schema_version"] == 2
    assert marker["database_instance_id"] == "database-current"
    assert not list(path.parent.glob("*.tmp"))


def test_startup_repairs_stale_marker_without_bumping_domain_revision(monkeypatch):
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    instance_id = repo.get_or_create_database_instance_id()
    revision_before = repo.get_domain_revision()["revision"]
    monkeypatch.setattr(
        lite_security.lite_security_generation,
        "inspect_security_progress_generation",
        lambda: {
            "status": "valid",
            "marker": {
                "generation": "stale-generation",
                "run_id": "security-old",
                "sqlite_revision": max(0, revision_before - 1),
                "database_instance_id": instance_id,
            },
            "sanitized": True,
        },
    )
    monkeypatch.setattr(
        lite_security,
        "_current_progress_generation_identity",
        lambda _repo=None: {
            "run_id": "security-current",
            "sqlite_revision": revision_before,
            "database_instance_id": instance_id,
        },
    )

    result = lite_security.recover_security_progress_generation_at_startup(
        repository=repo
    )

    assert result["status"] == "passed"
    assert result["repaired"] is True
    marker = json.loads(
        lite_security.lite_security_generation.marker_path().read_text(
            encoding="utf-8"
        )
    )
    assert marker["run_id"] == "security-current"
    assert marker["sqlite_revision"] == revision_before
    assert marker["database_instance_id"] == instance_id
    assert repo.get_domain_revision()["revision"] == revision_before


def test_startup_keeps_matching_marker_without_republish(monkeypatch):
    from api_fastapi.services import lite_security

    marker = {
        "generation": "matching-generation",
        "run_id": "security-current",
        "sqlite_revision": 55,
        "database_instance_id": "database-current",
        "sanitized": True,
    }
    monkeypatch.setattr(
        lite_security.lite_security_generation,
        "inspect_security_progress_generation",
        lambda: {"status": "valid", "marker": marker, "sanitized": True},
    )
    monkeypatch.setattr(
        lite_security,
        "_current_progress_generation_identity",
        lambda _repo=None: {
            "run_id": "security-current",
            "sqlite_revision": 55,
            "database_instance_id": "database-current",
        },
    )
    monkeypatch.setattr(
        lite_security.lite_security_generation,
        "publish_security_progress_generation",
        lambda **_kwargs: pytest.fail("matching marker must not be republished"),
    )

    class Repo:
        def record_progress_generation_recovery(self, _result):
            pass

    result = lite_security.recover_security_progress_generation_at_startup(
        repository=Repo()
    )
    assert result["repaired"] is False
    assert lite_security._SQLITE_PROGRESS_GENERATION_TOKEN == "matching-generation"


def test_live_missing_marker_fails_with_service_unavailable_exception(monkeypatch):
    from api_fastapi.services import lite_security

    monkeypatch.setattr(
        lite_security.lite_security_generation,
        "inspect_security_progress_generation",
        lambda: {"status": "absent", "marker": None, "sanitized": True},
    )
    monkeypatch.setattr(lite_security, "_SQLITE_PROGRESS_GENERATION_CHECKED_AT", 0.0)
    monkeypatch.setattr(
        lite_security, "_SQLITE_PROGRESS_GENERATION_CHECK_INTERVAL_SECONDS", 0.0
    )
    with pytest.raises(lite_security.SecurityProgressGenerationUnavailable):
        lite_security._observe_durable_security_progress_generation()


def test_progress_route_maps_generation_failure_to_sanitized_503():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text(encoding="utf-8")
    body = source.split('async def get_lite_security_progress', 1)[1].split(
        '@router.get("/security/history")', 1
    )[0]
    assert "SecurityProgressGenerationUnavailable" in body
    assert "status_code=503" in body
    assert '"retryable": True' in body
    assert '"sanitized": True' in body
