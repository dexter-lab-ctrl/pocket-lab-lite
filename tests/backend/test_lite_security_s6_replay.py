from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(tmp_path / "state" / "security.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    return SecuritySQLiteRepository()


def _seed(repo, run_id: str = "security-s6", events: int = 4):
    repo.reserve_scan(run_id=run_id, profile="quick")
    repo.mark_running(run_id)
    for index in range(events):
        repo.record_progress(
            run_id,
            status="running",
            stage=f"stage-{index}",
            percent=min(90, 10 + index * 10),
            message=f"Step {index}",
        )
    repo.complete_run(run_id, score=99, summary="Complete")
    return repo.list_progress_events(run_id, limit=100)


def test_replay_uses_persisted_numeric_ids_and_ascending_order(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    rows = list(reversed(_seed(repo)))
    from api_fastapi.services import lite_security

    cursor = rows[1]["event_id"]
    plan = lite_security.security_event_replay(cursor, repository=repo)
    ids = [item["event_id"] for item in plan["events"]]
    assert ids == sorted(ids)
    assert ids == [row["event_id"] for row in rows if row["event_id"] > cursor]
    assert all(isinstance(value, int) for value in ids)
    assert all(item["replayed"] is True for item in plan["events"])


def test_no_cursor_emits_canonical_snapshot_and_equal_latest_does_not_duplicate(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    rows = _seed(repo)
    from api_fastapi.services import lite_security

    first = lite_security.security_event_replay(None, repository=repo)
    assert first["outcome"] == "snapshot"
    assert first["events"][0]["snapshot"] is True
    latest = max(row["event_id"] for row in rows)
    equal = lite_security.security_event_replay(str(latest), repository=repo)
    assert equal["events"] == []
    assert equal["resume_event_id"] == latest


def test_replay_limit_and_cursor_resets_are_safe(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    rows = list(reversed(_seed(repo, events=8)))
    from api_fastapi.services import lite_security

    limited = lite_security.security_event_replay(rows[0]["event_id"], replay_limit=2, repository=repo)
    assert limited["outcome"] == "snapshot"
    assert limited["events"][0]["reset_reason"] == "replay_limit_exceeded"
    old = lite_security.security_event_replay(rows[0]["event_id"] - 1, repository=repo)
    assert old["outcome"] == "cursor_too_old"
    ahead = lite_security.security_event_replay(rows[-1]["event_id"] + 100, repository=repo)
    assert ahead["outcome"] == "cursor_ahead"
    malformed = lite_security.security_event_replay("not-a-number", repository=repo)
    assert malformed["outcome"] == "invalid_cursor"
    assert all(item.get("sanitized") for item in malformed["events"])


def test_heartbeat_has_no_persisted_id_or_database_row(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    _seed(repo)
    from api_fastapi.services import lite_security
    from api_fastapi.routers.lite import _security_sse_payload

    before = repo.get_latest_progress_event_id()
    heartbeat = lite_security.security_progress_heartbeat()
    frame = _security_sse_payload(heartbeat)
    after = repo.get_latest_progress_event_id()
    assert before == after
    assert "id:" not in frame
    assert "event: security.scan.heartbeat" in frame


def test_api_service_recreation_replays_same_sqlite_file(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    rows = list(reversed(_seed(repo)))
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    cursor = rows[1]["event_id"]
    recreated = SecuritySQLiteRepository()
    plan = lite_security.security_event_replay(cursor, repository=recreated)
    assert [item["event_id"] for item in plan["events"]] == [
        row["event_id"] for row in rows if row["event_id"] > cursor
    ]


def test_sse_frame_has_numeric_id_and_no_secret_shaped_diagnostics(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    rows = list(reversed(_seed(repo)))
    from api_fastapi.services import lite_security
    from api_fastapi.routers.lite import _security_sse_payload

    event = lite_security.security_progress_event_from_persisted(rows[-1])
    frame = _security_sse_payload(event)
    assert f"id: {event['event_id']}" in frame
    diagnostics = json.dumps(lite_security.security_event_replay_diagnostics()).lower()
    for secret in ("token=", "password=", "api_key=", "bearer "):
        assert secret not in diagnostics


def test_live_generator_only_emits_ids_after_cursor_and_completion_once(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    rows = list(reversed(_seed(repo)))
    from api_fastapi.routers import lite as lite_router
    from api_fastapi.services import lite_security

    monkeypatch.setattr(lite_security, "_security_repository", lambda: repo)
    monkeypatch.setenv("POCKETLAB_SECURITY_PROGRESS_SSE_IDLE_POLL_SECONDS", "1")
    monkeypatch.setenv("POCKETLAB_SECURITY_PROGRESS_SSE_HEARTBEAT_SECONDS", "15")
    cursor = rows[-3]["event_id"]

    class Request:
        headers = {"last-event-id": str(cursor)}
        calls = 0
        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 8

    async def collect():
        frames = []
        async for frame in lite_router._security_events_generator(Request()):
            frames.append(frame)
            if len(frames) >= 3:
                break
        return frames

    frames = asyncio.run(collect())
    ids = [int(line.split(":", 1)[1]) for frame in frames for line in frame.splitlines() if line.startswith("id:")]
    assert ids == sorted(set(ids))
    assert all(value > cursor for value in ids)
    assert sum("event: security.scan.completed" in frame for frame in frames) <= 1
