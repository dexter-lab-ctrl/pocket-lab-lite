from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_generation_marker_is_atomic_sanitized_and_outside_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    from api_fastapi.services import lite_security_generation

    module = importlib.reload(lite_security_generation)
    marker = module.publish_security_progress_generation(
        run_id="security-test-terminal",
        sqlite_revision=42,
        published_at="2026-07-20T12:00:00Z",
    )

    path = module.marker_path()
    assert path == tmp_path / ".pocketlab-runtime" / "security-progress-generation.json"
    assert path.name != "pocketlab-lite.sqlite3"
    assert marker["sanitized"] is True
    assert marker["run_id"] == "security-test-terminal"
    assert marker["sqlite_revision"] == 42
    assert module.read_security_progress_generation() == marker
    assert json.loads(path.read_text(encoding="utf-8"))["generation"]
    assert not list(path.parent.glob("*.tmp"))


def test_api_observer_fences_once_per_generation(monkeypatch):
    from api_fastapi.services import lite_security

    marker = {
        "generation": "generation-a",
        "run_id": "security-restored-terminal",
        "sqlite_revision": 77,
        "sanitized": True,
    }
    calls = []

    monkeypatch.setattr(
        lite_security.lite_security_generation,
        "read_security_progress_generation",
        lambda: dict(marker),
    )
    monkeypatch.setattr(
        lite_security,
        "fence_security_progress_after_database_restore",
        lambda: calls.append("fenced") or {
            "status": "passed",
            "run_id": "security-restored-terminal",
            "sqlite_revision": 77,
        },
    )
    monkeypatch.setattr(lite_security, "_SQLITE_PROGRESS_GENERATION_TOKEN", "")
    monkeypatch.setattr(lite_security, "_SQLITE_PROGRESS_GENERATION_CHECKED_AT", 0.0)
    monkeypatch.setattr(
        lite_security,
        "_SQLITE_PROGRESS_GENERATION_CHECK_INTERVAL_SECONDS",
        0.0,
    )

    lite_security._observe_durable_security_progress_generation()
    lite_security._observe_durable_security_progress_generation()

    assert calls == ["fenced"]
    assert lite_security._SQLITE_PROGRESS_GENERATION_TOKEN == "generation-a"


def test_api_observer_fails_closed_on_identity_mismatch(monkeypatch):
    from api_fastapi.services import lite_security

    monkeypatch.setattr(
        lite_security.lite_security_generation,
        "read_security_progress_generation",
        lambda: {
            "generation": "generation-b",
            "run_id": "security-authoritative",
            "sqlite_revision": 81,
            "sanitized": True,
        },
    )
    monkeypatch.setattr(
        lite_security,
        "fence_security_progress_after_database_restore",
        lambda: {
            "status": "passed",
            "run_id": "security-stale",
            "sqlite_revision": 80,
        },
    )
    monkeypatch.setattr(lite_security, "_SQLITE_PROGRESS_GENERATION_TOKEN", "")
    monkeypatch.setattr(lite_security, "_SQLITE_PROGRESS_GENERATION_CHECKED_AT", 0.0)
    monkeypatch.setattr(
        lite_security,
        "_SQLITE_PROGRESS_GENERATION_CHECK_INTERVAL_SECONDS",
        0.0,
    )

    try:
        lite_security._observe_durable_security_progress_generation()
    except RuntimeError as exc:
        assert "did not match promoted SQLite" in str(exc)
    else:
        raise AssertionError("generation mismatch must fail closed")


def test_restore_projection_refresh_publishes_generation_after_fence():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/"
        "lite_database_recovery.py"
    ).read_text(encoding="utf-8")
    body = source.split("def _refresh_security_projections()", 1)[1].split(
        "def _parity_check()", 1
    )[0]

    fence_index = body.index("fence_security_progress_after_database_restore")
    publish_index = body.index("publish_security_progress_generation")
    return_index = body.index('"generation": generation')

    assert fence_index < publish_index < return_index
    assert 'reason="database_projection_refresh"' in body
    assert "sqlite_revision" in body
