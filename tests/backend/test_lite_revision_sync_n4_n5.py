from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.requests import Request

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(target))
    from api_fastapi.db.connection import reset_sqlite_path_cache

    reset_sqlite_path_cache()
    return target


def _fleet_payload(*, state: str = "online", count: int = 2) -> dict:
    return {
        "status": "healthy",
        "devices": [
            {
                "id": f"device-{index}",
                "name": f"Device {index}",
                "role": "compute",
                "status": state,
                "connection": state,
                "agent_status": state,
                "supervisor_status": "healthy",
                "agent_process_status": "online",
                "last_seen_at": f"2026-07-22T14:00:{index:02d}Z",
            }
            for index in range(count)
        ],
        "remote_access": {"ready": True},
        "updated_at": "2026-07-22T14:01:00Z",
    }


def test_n4_n5_migration_revision_events_and_change_only_bump(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import apply_migrations, current_schema_version
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    assert apply_migrations() == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert current_schema_version() == 9
    store = ControlPlaneProjectionStore()
    first = store.project_fleet(_fleet_payload())
    second = store.project_fleet(_fleet_payload())
    assert first == 1
    assert second == first

    with read_connection() as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT domain, revision, changed_ids_json, reason, sanitized "
            "FROM lite_revision_events ORDER BY event_id"
        )]
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(command_lifecycle)")
        }
    assert rows == [{
        "domain": "fleet",
        "revision": 1,
        "changed_ids_json": '["device-0","device-1"]',
        "reason": "fleet_state_changed",
        "sanitized": 1,
    }]
    assert {"lifecycle_stage", "terminal_at", "ignored_redelivery", "recovery_action"}.issubset(columns)



def test_n4_n5_security_revision_writes_sanitized_domain_event(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import begin_immediate, open_connection, read_connection
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.services import lite_security_store

    apply_migrations()
    conn = open_connection()
    try:
        with begin_immediate(conn) as tx:
            revision = lite_security_store._bump_revision(
                tx, "2026-07-22T14:02:00Z"
            )
    finally:
        conn.close()
    with read_connection() as conn:
        event = dict(conn.execute(
            "SELECT domain, revision, changed_ids_json, reason, sanitized "
            "FROM lite_revision_events WHERE domain='security'"
        ).fetchone())
    assert revision == 1
    assert event == {
        "domain": "security",
        "revision": 1,
        "changed_ids_json": "[]",
        "reason": "security_state_changed",
        "sanitized": 1,
    }

def test_n4_n5_changed_ids_are_bounded_and_replay_is_ordered(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    assert store.project_fleet(_fleet_payload(count=40)) == 1
    changed = store.revision_events_after(0)
    assert len(changed) == 1
    assert changed[0]["event_id"] == 1
    assert changed[0]["changed_ids"] == []
    assert changed[0]["sanitized"] is True
    assert len(json.dumps(changed[0])) < 2048

    assert store.project_fleet(_fleet_payload(state="offline", count=40)) == 2
    replay = store.revision_events_after(1)
    assert [item["event_id"] for item in replay] == [2]
    assert [item["revision"] for item in replay] == [2]
    window = store.revision_event_window()
    assert window["oldest_event_id"] == 1
    assert window["latest_event_id"] == 2
    assert window["retained_events"] == 2


def test_n4_n5_command_terminal_state_cannot_regress(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.record_command(
        command_id="command-terminal",
        subject="pocketlab.commands.lite.app.execute",
        status="succeeded",
        entity_type="app",
        entity_id="photoprism",
        summary="Command completed.",
    )
    revision = store.domain_revision("commands")
    store.record_command(
        command_id="command-terminal",
        subject="pocketlab.commands.lite.app.execute",
        status="ignored_redelivery",
        entity_type="app",
        entity_id="photoprism",
        summary="Terminal redelivery was ignored safely.",
    )
    store.record_command(
        command_id="command-terminal",
        subject="pocketlab.commands.lite.app.execute",
        status="running",
        entity_type="app",
        entity_id="photoprism",
        summary="Late redelivery tried to run.",
    )
    with read_connection() as conn:
        row = dict(conn.execute(
            "SELECT status, lifecycle_stage, terminal_at, ignored_redelivery "
            "FROM command_lifecycle WHERE command_id=?",
            ("command-terminal",),
        ).fetchone())
    assert row["status"] == "succeeded"
    assert row["lifecycle_stage"] == "terminal"
    assert row["terminal_at"]
    assert row["ignored_redelivery"] == 1
    assert store.domain_revision("commands") == revision + 1



def test_n4_n5_workflow_events_project_full_command_lifecycle(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.services import lite_control_plane_store, workflow_engine

    apply_migrations()
    store = lite_control_plane_store.ControlPlaneProjectionStore()
    monkeypatch.setattr(lite_control_plane_store, "CONTROL_PLANE", store)
    engine = workflow_engine.EventSourcedWorkflowEngine()
    engine._root = tmp_path / "workflows"
    engine._root.mkdir()
    engine._command_file = engine._root / "command-journal.json"
    engine._event_log = engine._root / "events.jsonl"
    engine._projection_file = engine._root / "projections.json"

    base = {
        "subject": "pocketlab.events.command.lifecycle",
        "trace_id": "command-e2e",
        "id": "event-e2e",
        "time": "2026-07-22T14:03:00Z",
        "workflow_id": "command-e2e",
        "data": {
            "command_id": "command-e2e",
            "command_subject": "pocketlab.commands.lite.app.execute",
            "app_id": "photoprism",
        },
    }
    for event_type in (
        "command.queued",
        "command.received",
        "command.worker_claimed",
        "command.running",
    ):
        engine._maybe_record_command({**base, "type": event_type})
    engine._maybe_record_command({
        **base,
        "type": "command.failed",
        "data": {**base["data"], "terminal": False},
    })
    engine._maybe_record_command({**base, "type": "command.succeeded"})
    engine._maybe_record_command({
        **base,
        "type": "worker.ignored",
        "data": {**base["data"], "reason": "terminal command redelivery"},
    })

    with read_connection() as conn:
        row = dict(conn.execute(
            "SELECT status, lifecycle_stage, ignored_redelivery, recovery_action "
            "FROM command_lifecycle WHERE command_id='command-e2e'"
        ).fetchone())
    assert row == {
        "status": "succeeded",
        "lifecycle_stage": "terminal",
        "ignored_redelivery": 1,
        "recovery_action": "command.failed",
    }
    assert store.domain_revision("commands") >= 7

def test_n4_n5_revisions_etag_and_304_are_database_instance_fenced(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.routers.lite import _lite_revisions_response
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.project_fleet(_fleet_payload())
    payload = store.revisions()
    etag = store.revisions_etag(payload)
    request = Request({"type": "http", "method": "GET", "path": "/api/lite/revisions", "headers": []})
    response = _lite_revisions_response(request, payload)
    assert response.status_code == 200
    assert response.headers["etag"] == etag
    assert response.headers["cache-control"] == "no-cache"
    assert payload["database_instance"] in etag or etag.startswith('W/"pl-revisions-')
    assert payload["event_cursor"]["latest_event_id"] == 1

    conditional = Request({
        "type": "http",
        "method": "GET",
        "path": "/api/lite/revisions",
        "headers": [(b"if-none-match", etag.encode("ascii"))],
    })
    not_modified = _lite_revisions_response(conditional, payload)
    assert not_modified.status_code == 304
    assert not_modified.body == b""


def test_n4_n5_cursor_guards_and_sse_source_contract():
    from api_fastapi.routers.lite import _parse_lite_revision_cursor

    assert _parse_lite_revision_cursor(None) == (0, False)
    assert _parse_lite_revision_cursor("42") == (42, False)
    assert _parse_lite_revision_cursor("bad") == (0, True)
    assert _parse_lite_revision_cursor("-1") == (0, True)

    router = Path("pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py").read_text()
    assert '@router.get("/events")' in router
    assert 'media_type="text/event-stream"' in router
    assert 'request.headers.get("last-event-id")' in router
    assert 'request.is_disconnected()' in router
    assert 'cursor_too_old' in router
    assert 'cursor_ahead' in router
    assert 'malformed_cursor' in router
    assert 'database_instance_changed' in router
    assert 'yield ": keepalive\\n\\n"' in router
    assert 'CONTROL_PLANE.revision_events_after' in router


def test_n4_n5_hot_query_plans_use_revision_and_lifecycle_indexes(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    plans = store.query_plan_evidence()
    assert any("idx_lite_revision_events_replay" in detail for detail in plans["revision_event_replay"])
    assert any("idx_commands_lifecycle_stage" in detail for detail in plans["command_lifecycle_stage"])

@pytest.mark.parametrize(
    ("header", "window", "reason"),
    [
        ("bad", {"database_instance": "db-a", "oldest_event_id": 1, "latest_event_id": 4}, "malformed_cursor"),
        ("99", {"database_instance": "db-a", "oldest_event_id": 1, "latest_event_id": 4}, "cursor_ahead"),
        ("1", {"database_instance": "db-a", "oldest_event_id": 5, "latest_event_id": 8}, "cursor_too_old"),
    ],
)
def test_n4_n5_sse_cursor_reset_frames_are_sanitized(monkeypatch, header, window, reason):
    import asyncio
    from api_fastapi.routers import lite as router

    class RequestStub:
        headers = {"last-event-id": header}
        query_params = {}

        async def is_disconnected(self):
            return False

    monkeypatch.setattr(router.CONTROL_PLANE, "revision_event_window", lambda: window)
    monkeypatch.setattr(router.CONTROL_PLANE, "revisions", lambda: {
        "database_instance": window["database_instance"],
        "revisions": {"fleet": 4, "apps": 2},
        "projection_version": 1,
    })

    async def consume():
        generator = router._lite_revision_events_generator(RequestStub())
        try:
            return await anext(generator)
        finally:
            await generator.aclose()

    frame = asyncio.run(consume())
    assert "event: lite.revision.reset" in frame
    payload = json.loads(next(line[6:] for line in frame.splitlines() if line.startswith("data: ")))
    assert payload["reason"] == reason
    assert payload["sanitized"] is True
    assert "token" not in frame.lower()
    assert "command_payload" not in frame.lower()


def test_n4_n5_sse_detects_database_replacement_during_live_connection(monkeypatch):
    import asyncio
    from api_fastapi.routers import lite as router

    class RequestStub:
        headers = {}
        query_params = {}

        async def is_disconnected(self):
            return False

    windows = iter([
        {"database_instance": "db-a", "oldest_event_id": 0, "latest_event_id": 0},
        {"database_instance": "db-b", "oldest_event_id": 0, "latest_event_id": 0},
    ])
    monkeypatch.setattr(router.CONTROL_PLANE, "revision_event_window", lambda: next(windows))
    monkeypatch.setattr(router.CONTROL_PLANE, "revisions", lambda: {
        "database_instance": "db-b",
        "revisions": {"fleet": 0, "apps": 0},
        "projection_version": 1,
    })

    async def consume():
        generator = router._lite_revision_events_generator(RequestStub())
        try:
            return await anext(generator)
        finally:
            await generator.aclose()

    frame = asyncio.run(consume())
    assert "database_instance_changed" in frame
    assert '"database_instance":"db-b"' in frame


def test_n4_n5_frontend_sync_source_contract_is_focused_and_cross_tab_safe():
    sync = Path("src/lib/liteRevisionSync.js").read_text(encoding="utf-8")
    bridge = Path("src/lite/LiteRevisionSyncBridge.jsx").read_text(encoding="utf-8")
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text(encoding="utf-8")

    assert "pocketlab-lite-revision-sync-v1" in sync
    assert "schema_version" in sync
    assert "sender_id" in sync
    assert "LITE_REVISION_MAX_MESSAGE_BYTES" in sync
    assert "LITE_REVISION_MAX_CHANGED_IDS" in sync
    assert "acquireLiteRevisionLeadership" in sync
    assert "LITE_REVISION_LEADER_TTL_MS = 20_000" in sync
    assert "refetchType: 'active'" in sync
    assert "queryKey: ['lite']" in sync  # database-instance reset only
    assert "new window.EventSource" in bridge
    assert "last_event_id" in bridge
    assert "BroadcastChannel" in bridge
    assert "60_000 + Math.floor(Math.random() * 7_500)" in bridge
    assert "120_000" in bridge
    assert "navigator.onLine" in bridge
    assert "visibilitychange" in bridge
    assert "applyLiteSnapshotDatabaseInstance" in snapshots
    assert "clearOfflineSafeSnapshots" in snapshots
