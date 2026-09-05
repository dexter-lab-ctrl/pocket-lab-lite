from __future__ import annotations

import asyncio
import json

import pytest
from starlette.requests import Request

from pocket_lab_test_utils import ensure_runtime_path, load_fastapi_app, prepare_sqlite_test_database


def _configure(tmp_path, monkeypatch):
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    return prepare_sqlite_test_database(target, monkeypatch)


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


def test_revision_schema_is_current_and_fleet_bumps_only_on_change(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import current_schema_version, latest_schema_version
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    assert current_schema_version() == latest_schema_version()
    store = ControlPlaneProjectionStore()
    first = store.project_fleet(_fleet_payload())
    second = store.project_fleet(_fleet_payload())
    assert first == 1
    assert second == first

    with read_connection() as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT domain,revision,changed_ids_json,reason,sanitized "
            "FROM lite_revision_events ORDER BY event_id"
        )]
        columns = {row[1] for row in conn.execute("PRAGMA table_info(command_lifecycle)")}
    assert len(rows) == 1
    assert rows[0]["domain"] == "fleet"
    assert rows[0]["revision"] == 1
    assert rows[0]["sanitized"] == 1
    assert json.loads(rows[0]["changed_ids_json"]) == ["device-0", "device-1"]
    assert rows[0]["reason"] in {
        "device_identity_changed",
        "device_enrollment_changed",
        "fleet_state_changed",
    }
    assert {"lifecycle_stage", "terminal_at", "ignored_redelivery", "recovery_action"}.issubset(columns)


def test_security_store_revision_is_domain_state_not_duplicate_lite_sse_evidence(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import begin_immediate, open_connection, read_connection
    from api_fastapi.services import lite_security_store

    conn = open_connection()
    try:
        with begin_immediate(conn) as tx:
            revision = lite_security_store._bump_revision(tx, "2026-07-22T14:02:00Z")
    finally:
        conn.close()
    with read_connection() as conn:
        row = conn.execute("SELECT revision FROM domain_revisions WHERE domain='security'").fetchone()
    assert revision == 1
    assert int(row["revision"]) == 1


def test_changed_ids_are_bounded_and_replay_is_ordered(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    assert store.project_fleet(_fleet_payload(count=40)) == 1
    changed = store.revision_events_after(0)
    assert len(changed) == 1
    assert changed[0]["event_id"] == 1
    assert changed[0]["sanitized"] is True
    assert len(changed[0]["changed_ids"]) <= 32
    assert len(json.dumps(changed[0])) < 2048

    assert store.project_fleet(_fleet_payload(state="offline", count=40)) == 2
    replay = store.revision_events_after(1)
    assert [item["event_id"] for item in replay] == [2]
    assert [item["revision"] for item in replay] == [2]
    window = store.revision_event_window()
    assert window["oldest_event_id"] == 1
    assert window["latest_event_id"] == 2
    assert window["retained_events"] == 2


def test_command_terminal_state_cannot_regress(tmp_path, monkeypatch):
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
            "SELECT status,lifecycle_stage,terminal_at,ignored_redelivery "
            "FROM command_lifecycle WHERE command_id='command-terminal'"
        ).fetchone())
    assert row["status"] == "succeeded"
    assert row["lifecycle_stage"] == "terminal"
    assert row["terminal_at"]
    assert row["ignored_redelivery"] == 1
    assert store.domain_revision("commands") >= revision


def test_revisions_etag_and_304_are_database_instance_fenced(tmp_path, monkeypatch):
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


def test_revision_sse_route_is_registered_and_cursor_parser_fails_safe():
    from api_fastapi.routers.lite import _parse_lite_revision_cursor

    assert _parse_lite_revision_cursor(None) == (0, False)
    assert _parse_lite_revision_cursor("42") == (42, False)
    assert _parse_lite_revision_cursor("bad") == (0, True)
    assert _parse_lite_revision_cursor("-1") == (0, True)
    paths = {getattr(route, "path", "") for route in load_fastapi_app().routes}
    assert "/api/lite/events" in paths
    assert "/api/lite/revisions" in paths


@pytest.mark.parametrize(
    ("header", "window", "reason"),
    [
        ("bad", {"database_instance": "db-a", "oldest_event_id": 1, "latest_event_id": 4}, "malformed_cursor"),
        ("99", {"database_instance": "db-a", "oldest_event_id": 1, "latest_event_id": 4}, "cursor_ahead"),
        ("1", {"database_instance": "db-a", "oldest_event_id": 5, "latest_event_id": 8}, "cursor_too_old"),
    ],
)
def test_sse_cursor_reset_frames_are_sanitized(monkeypatch, header, window, reason):
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


def test_sse_detects_database_replacement_during_live_connection(monkeypatch):
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


def test_frontend_revision_sync_remains_focused_and_cross_tab_safe():
    sync = open("src/lib/liteRevisionSync.js", encoding="utf-8").read()
    bridge = open("src/lite/LiteRevisionSyncBridge.jsx", encoding="utf-8").read()
    snapshots = open("src/lib/liteSafeSnapshots.js", encoding="utf-8").read()

    assert "pocketlab-lite-revision-sync-v1" in sync
    assert "LITE_REVISION_MAX_MESSAGE_BYTES" in sync
    assert "LITE_REVISION_MAX_CHANGED_IDS" in sync
    assert "acquireLiteRevisionLeadership" in sync
    assert "refetchType: 'active'" in sync
    assert "new window.EventSource" in bridge
    assert "BroadcastChannel" in bridge
    assert "navigator.onLine" in bridge
    assert "visibilitychange" in bridge
    assert "applyLiteSnapshotDatabaseInstance" in snapshots
    assert "clearOfflineSafeSnapshots" in snapshots
