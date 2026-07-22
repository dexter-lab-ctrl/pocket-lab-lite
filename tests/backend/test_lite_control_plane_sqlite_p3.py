from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(target))
    from api_fastapi.db.connection import reset_sqlite_path_cache

    reset_sqlite_path_cache()
    return target


def _fleet_payload() -> dict:
    return {
        "status": "healthy",
        "devices": [
            {
                "id": "pocket-lab-lite-server",
                "name": "Server Phone",
                "role": "server_host",
                "status": "healthy",
                "connection": "online",
                "last_seen_at": "2026-07-21T12:00:00Z",
                "is_current": True,
            },
            {
                "id": "phone-two",
                "name": "Phone Two",
                "role": "compute",
                "status": "active",
                "connection": "online",
                "agent_status": "online",
                "supervisor_status": "healthy",
                "agent_process_status": "online",
                "last_seen_at": "2026-07-21T12:00:01Z",
            },
            {
                "id": "phone-three",
                "name": "Phone Three",
                "role": "compute",
                "status": "agent_stopped",
                "connection": "offline",
                "agent_process_status": "stopped",
                "last_seen_at": "2026-07-21T11:00:00Z",
            },
        ],
        "remote_access": {"ready": True, "status": "healthy"},
        "latest_invite": {
            "invite_id": "invite-phone-four",
            "node_id": "phone-four",
            "hostname": "Phone Four",
            "role": "compute",
            "status": "pending",
            "created_at": "2026-07-21T12:00:00Z",
            "expires_at": "2026-07-21T13:00:00Z",
            "bootstrap_url": "https://example.invalid/?token=must-not-store",
        },
        "updated_at": "2026-07-21T12:00:02Z",
    }


def test_control_plane_migration_and_domain_revisions(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import apply_migrations, current_schema_version

    assert apply_migrations() == [1, 2, 3, 4, 5, 6]
    assert current_schema_version() == 6
    with read_connection() as conn:
        domains = {
            row["domain"]: int(row["revision"])
            for row in conn.execute("SELECT domain, revision FROM domain_revisions")
        }
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"fleet", "apps", "recovery", "commands", "storage", "audit"}.issubset(domains)
    assert {
        "device_current_state",
        "app_current_state",
        "recovery_current_state",
        "command_lifecycle",
    }.issubset(tables)


def test_fleet_projection_is_bounded_sanitized_and_change_only(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    first = store.project_fleet(_fleet_payload())
    second = store.project_fleet(_fleet_payload())

    assert first == 1
    assert second == first
    rows = store.fleet_rows()
    assert len(rows) == 3
    by_id = {row["device_id"]: row for row in rows}
    assert by_id["pocket-lab-lite-server"]["ui_state"] == "Protected server host"
    assert by_id["phone-two"]["ui_state"] == "Online"
    assert by_id["phone-three"]["ui_state"] == "Agent stopped"
    assert len({row["device_id"] for row in rows}) == len(rows)

    with read_connection() as conn:
        invite = dict(
            conn.execute(
                "SELECT * FROM device_invite_lifecycle WHERE invite_id=?",
                ("invite-phone-four",),
            ).fetchone()
        )
        serialized = json.dumps(invite).lower()
        heartbeat_count = int(
            conn.execute("SELECT COUNT(*) FROM device_heartbeats").fetchone()[0]
        )
    assert "token" not in serialized
    assert "bootstrap" not in serialized
    assert heartbeat_count == 3


def test_app_and_recovery_projection_skip_noop_revision_bumps(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    apps = {
        "apps": [
            {
                "app_id": "photoprism",
                "name": "PhotoPrism",
                "installed": True,
                "status": "ready",
                "summary": "PhotoPrism is ready.",
                "security": {"status": "protected"},
                "backup": {"latest_backup_id": "app-backup-1"},
                "actions": {
                    "check_app": {
                        "status": "succeeded",
                        "last_ran_at": "2026-07-21T12:00:00Z",
                        "last_result": "Protected app",
                        "enabled": True,
                        "category": "safety",
                    }
                },
            }
        ],
        "updated_at": "2026-07-21T12:00:00Z",
    }
    recovery = {
        "status": "healthy",
        "summary": "Recovery ready",
        "last_backup": {
            "backup_id": "backup-1",
            "status": "verified",
            "verification_status": "verified",
            "created_at": "2026-07-21T10:00:00Z",
            "verified_at": "2026-07-21T10:02:00Z",
            "size_bytes": 1234,
        },
        "latest_restore_preview": {
            "preview_id": "preview-1",
            "backup_id": "backup-1",
            "status": "ready",
            "created_at": "2026-07-21T11:00:00Z",
            "summary": "Preview ready",
        },
        "maintenance": {"active": False, "status": "idle"},
        "updated_at": "2026-07-21T12:00:00Z",
    }

    assert store.project_apps(apps) == 1
    assert store.project_apps(apps) == 1
    assert store.project_recovery(recovery) == 1
    assert store.project_recovery(recovery) == 1

    with read_connection() as conn:
        app = dict(conn.execute("SELECT * FROM app_current_state").fetchone())
        current = dict(conn.execute("SELECT * FROM recovery_current_state").fetchone())
        backup = dict(conn.execute("SELECT * FROM backup_manifest_index").fetchone())
    assert app["latest_backup_id"] == "app-backup-1"
    assert current["latest_preview_id"] == "preview-1"
    assert backup["verification_status"] == "verified"


def test_command_lifecycle_and_audit_index_are_bounded_and_sanitized(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.record_command(
        command_id="command-1",
        subject="pocketlab.commands.node.restart_agent",
        status="queued",
        entity_type="device",
        entity_id="phone-two",
        summary="Restart Agent queued.",
    )
    store.record_command(
        command_id="command-1",
        subject="pocketlab.commands.node.restart_agent",
        status="completed",
        entity_type="device",
        entity_id="phone-two",
        summary="Restart Agent completed.",
    )

    with read_connection() as conn:
        command = dict(
            conn.execute(
                "SELECT command_id,status,entity_type,entity_id,metadata_json "
                "FROM command_lifecycle WHERE command_id=?",
                ("command-1",),
            ).fetchone()
        )
        audit = [
            dict(row)
            for row in conn.execute(
                "SELECT event_type,status,evidence_ref,summary "
                "FROM audit_evidence_index WHERE operation_id=? "
                "ORDER BY created_at_epoch_ms,evidence_index_id",
                ("command-1",),
            )
        ]
        revisions = {
            row["domain"]: int(row["revision"])
            for row in conn.execute(
                "SELECT domain,revision FROM domain_revisions "
                "WHERE domain IN ('commands','audit')"
            )
        }

    assert command["status"] == "succeeded"
    assert command["entity_type"] == "device"
    assert command["entity_id"] == "phone-two"
    metadata = json.loads(command["metadata_json"])
    assert set(metadata) <= {"requested_by", "result_status"}
    assert not any(marker in command["metadata_json"].lower() for marker in ("token", "password", "secret"))
    assert [row["event_type"] for row in audit] == ["command.queued", "command.succeeded"]
    assert all(row["evidence_ref"] == "FastAPI/NATS" for row in audit)
    assert revisions["commands"] == 2
    assert revisions["audit"] == 2


def test_fleet_hot_queries_use_targeted_indexes(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.project_fleet(_fleet_payload())
    plans = store.query_plan_evidence()

    expected = {
        "latest_heartbeat": "idx_device_heartbeats_latest",
        "fleet_summary_order": "idx_device_current_fleet_order",
        "active_command": "idx_commands_entity_active_latest",
        "latest_supervisor": "idx_device_heartbeats_latest",
        "stale_devices": "idx_device_current_stale_order",
        "invite_lookup": "idx_device_invites_active_latest",
        "device_recovery_history": "idx_device_recovery_history",
        "app_action_history": "idx_app_actions_history",
        "command_history": "idx_commands_entity_history",
        "recovery_operation_history": "idx_recovery_operations_updated",
        "backup_manifest_history": "idx_backup_manifest_created",
    }
    for name, index_name in expected.items():
        details = " | ".join(plans[name])
        assert index_name in details
        assert "TEMP B-TREE" not in details.upper()


def test_single_writer_queue_is_bounded_and_reports_sanitized_metrics(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLiteWriteRejected, SQLiteWriteService

    apply_migrations()
    writer = SQLiteWriteService(max_queue=1)
    entered = threading.Event()
    release = threading.Event()

    def blocking(conn):
        entered.set()
        release.wait(2)
        conn.execute(
            "INSERT INTO domain_revisions(domain,revision,updated_at) VALUES ('writer-test-one',1,'now') "
            "ON CONFLICT(domain) DO UPDATE SET revision=revision+1, updated_at=excluded.updated_at"
        )
        return 1

    first_result = []
    first = threading.Thread(
        target=lambda: first_result.append(
            writer.submit("blocking", blocking, deadline_seconds=3)
        )
    )
    first.start()
    assert entered.wait(1)

    second = threading.Thread(
        target=lambda: writer.submit(
            "queued",
            lambda conn: conn.execute(
                "INSERT INTO domain_revisions(domain,revision,updated_at) VALUES ('writer-test-two',1,'now') "
                "ON CONFLICT(domain) DO UPDATE SET revision=revision+1, updated_at=excluded.updated_at"
            ),
            deadline_seconds=3,
        )
    )
    second.start()
    time.sleep(0.05)
    with pytest.raises(SQLiteWriteRejected):
        writer.submit("overflow", lambda conn: None, deadline_seconds=0.2)
    release.set()
    first.join(3)
    second.join(3)
    metrics = writer.snapshot()
    writer.shutdown()

    assert first_result == [1]
    assert metrics["rejected_writes"] >= 1
    assert metrics["queue_capacity"] == 1
    assert metrics["sanitized"] is True
    assert "queue_wait_ms_avg" in metrics
    assert "transaction_ms_avg" in metrics


def test_read_connection_generation_invalidation_reopens_connection(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLiteReadConnectionManager

    apply_migrations()
    manager = SQLiteReadConnectionManager(max_connections=1)
    first, _ = manager.acquire()
    first_connection = first.connection
    manager.release(first)
    second, _ = manager.acquire()
    assert second.connection is first_connection
    manager.release(second)

    generation = manager.invalidate()
    third, _ = manager.acquire()
    assert third.generation == generation
    assert third.connection is not first_connection
    manager.release(third)
    manager.close()


def test_prepared_read_etag_is_revision_and_database_instance_fenced(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    payload = _fleet_payload()
    first = store.prepared_read(
        domain="fleet",
        key="summary",
        builder=lambda: payload,
        projector=store.project_fleet,
        stale_after_ms=10_000,
        max_stale_ms=20_000,
    )
    second = store.prepared_read(
        domain="fleet",
        key="summary",
        builder=lambda: payload,
        projector=store.project_fleet,
        stale_after_ms=10_000,
        max_stale_ms=20_000,
    )
    assert first.etag == second.etag
    assert first.source_revision == 1
    assert second.projection_age_ms >= 0

    # Atomic database replacement changes the database-instance fence even when
    # a restored database carries the same domain revision.
    replacement = database.with_suffix(".replacement.sqlite3")
    replacement.write_bytes(database.read_bytes())
    replacement.replace(database)
    store.invalidate_after_database_replacement()
    third = store.prepared_read(
        domain="fleet",
        key="summary",
        builder=lambda: payload,
        projector=store.project_fleet,
        stale_after_ms=10_000,
        max_stale_ms=20_000,
    )
    assert third.etag != first.etag


def test_async_lite_routes_do_not_add_blocking_io_calls():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text(encoding="utf-8")
    forbidden = ("subprocess.run(", "time.sleep(", "urllib.request.urlopen(")
    for marker in forbidden:
        assert marker not in source
    assert "CONTROL_PLANE.prepared_read" in source
    assert "_control_plane_prepared_response" in source


def test_prepared_read_coalesces_concurrent_cold_refreshes(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    calls = 0
    calls_lock = threading.Lock()
    release = threading.Event()

    def builder():
        nonlocal calls
        with calls_lock:
            calls += 1
        release.wait(1)
        return {"status": "healthy", "devices": [], "updated_at": "2026-07-21T12:00:00Z"}

    results = []

    def read():
        results.append(
            store.prepared_read(
                domain="fleet",
                key="coalesced",
                builder=builder,
                projector=store.project_fleet,
                stale_after_ms=10_000,
                max_stale_ms=20_000,
                deadline_seconds=2.0,
            )
        )

    first = threading.Thread(target=read)
    second = threading.Thread(target=read)
    first.start()
    time.sleep(0.05)
    second.start()
    release.set()
    first.join(3)
    second.join(3)

    assert calls == 1
    assert len(results) == 2
    assert results[0].etag == results[1].etag


def test_control_plane_response_has_timing_etag_and_304_without_sensitive_headers():
    from starlette.requests import Request
    from api_fastapi.routers.lite import _control_plane_prepared_response
    from api_fastapi.services.lite_control_plane_store import PreparedRead

    prepared = PreparedRead(
        payload={"status": "healthy", "devices": []},
        etag='W/"pl-instance-fleet-summary-7"',
        source_revision=7,
        projection_age_ms=12,
        read_degraded=False,
        refresh_pending=False,
        timing={
            "connection_acquisition_ms": 0.2,
            "sqlite_query_ms": 0.4,
            "projection_build_ms": 1.2,
            "serialization_ms": 0.1,
        },
    )
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    response = _control_plane_prepared_response(request, prepared, view_model="fleet-test")
    assert response.status_code == 200
    assert response.headers["etag"] == prepared.etag
    assert "connection;dur=" in response.headers["server-timing"]
    assert response.headers["x-pocketlab-source-revision"] == "7"
    assert not any(
        marker in json.dumps(dict(response.headers)).lower()
        for marker in ("password", "secret", "token", "command_payload")
    )

    conditional = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"if-none-match", prepared.etag.encode("ascii"))],
        }
    )
    not_modified = _control_plane_prepared_response(
        conditional, prepared, view_model="fleet-test"
    )
    assert not_modified.status_code == 304
    assert not_modified.body == b""


def test_frontend_uses_conditional_reads_and_safe_revision_snapshots():
    api = Path("src/lib/liteApi.js").read_text(encoding="utf-8")
    keys = Path("src/lib/liteQueryClient.js").read_text(encoding="utf-8")
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text(encoding="utf-8")
    status_hook = Path("src/hooks/useLiteStatus.js").read_text(encoding="utf-8")

    assert "appLifecycle: conditionalGet('/api/lite/apps/lifecycle')" in api
    assert "fleet: conditionalGet('/api/lite/fleet')" in api
    assert "domainRevisions: conditionalGet('/api/lite/revisions')" in api
    assert "recoveryDetails: conditionalGet('/api/lite/recovery/details')" in api
    assert "appActionHistory:" in api
    assert "deviceRecoveryHistory:" in api
    assert "commandHistory:" in api
    assert "recoveryOperations:" in api
    assert "domainRevisions: () => ['lite', 'revisions']" in keys
    assert "appLifecycle: () => ['lite', 'apps', 'lifecycle']" in keys
    assert "appActionHistory:" in keys
    assert "deviceRecoveryHistory:" in keys
    assert "commandHistory:" in keys
    assert "recoveryOperations:" in keys
    assert "'/api/lite/revisions'" in snapshots
    assert "'/api/lite/apps/lifecycle'" in snapshots
    assert "liteQueryPaths.domainRevisions" in status_hook
    assert "liteQueryPaths.appLifecycle" in status_hook


def test_keyset_history_pages_are_bounded_and_duplicate_free(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi import deps
    from api_fastapi.services import fleet_registry
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    events = [
        {
            "device_id": "phone-two",
            "event_type": "agent_recovery",
            "status": "succeeded",
            "command_id": f"recovery-command-{index}",
            "created_at": f"2026-07-21T12:0{index}:00Z",
            "summary": f"Recovery {index}",
        }
        for index in range(4)
    ]
    monkeypatch.setattr(fleet_registry, "list_commands", lambda limit=500: [])
    monkeypatch.setattr(
        deps.core,
        "read_json_file",
        lambda path, default: {"events": events}
        if str(path).endswith("fleet_device_events.json")
        else default,
    )

    store = ControlPlaneProjectionStore()
    store.project_fleet(_fleet_payload())
    for index in range(4):
        timestamp = f"2026-07-21T13:0{index}:00Z"
        store.project_apps(
            {
                "apps": [
                    {
                        "app_id": "photoprism",
                        "name": "PhotoPrism",
                        "installed": True,
                        "status": "ready",
                        "actions": {
                            "check_app": {
                                "operation_id": f"app-operation-{index}",
                                "status": "succeeded",
                                "last_ran_at": timestamp,
                                "last_result": f"Check {index}",
                            }
                        },
                    }
                ],
                "updated_at": timestamp,
            }
        )
        store.project_recovery(
            {
                "status": "healthy",
                "latest_restore_preview": {
                    "preview_id": f"preview-{index}",
                    "status": "ready",
                    "created_at": timestamp,
                    "summary": f"Preview {index}",
                },
                "updated_at": timestamp,
            }
        )
        store.record_command(
            command_id=f"command-{index}",
            subject="pocketlab.commands.node.restart_agent",
            status="succeeded",
            entity_type="device",
            entity_id="phone-two",
            summary=f"Command {index}",
        )

    def assert_two_pages(loader, id_key):
        first = loader(limit=2)
        second = loader(limit=2, cursor=first["next_cursor"])
        assert first["count"] == 2
        assert first["has_more"] is True
        assert first["next_cursor"]
        assert {row[id_key] for row in first["items"]}.isdisjoint(
            {row[id_key] for row in second["items"]}
        )
        assert first["source_revision"] >= 1
        assert first["sqlite_query_ms"] >= 0

    assert_two_pages(
        lambda **kwargs: store.app_action_history("photoprism", **kwargs),
        "operation_id",
    )
    assert_two_pages(
        lambda **kwargs: store.device_recovery_history("phone-two", **kwargs),
        "recovery_id",
    )
    assert_two_pages(
        lambda **kwargs: store.command_history(
            entity_type="device", entity_id="phone-two", **kwargs
        ),
        "command_id",
    )
    assert_two_pages(store.recovery_operation_history, "operation_id")

    with pytest.raises(ValueError, match="Invalid history cursor"):
        store.command_history(cursor="not-a-valid-cursor")


def test_history_routes_are_keyset_paginated_and_revision_etagged():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text(encoding="utf-8")
    store_source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py"
    ).read_text(encoding="utf-8")

    for route in (
        '/apps/{app_id}/action-history',
        '/fleet/devices/{device_id}/recovery-history',
        '/commands/history',
        '/recovery/operations',
    ):
        assert route in source
    assert "_control_plane_history_response" in source
    assert "If-None-Match" not in source  # header matching stays centralized and case-safe
    assert "if_none_match_matches" in source
    assert " OFFSET " not in store_source.upper()
    assert "next_cursor" in store_source


def test_writer_disk_full_failure_rolls_back_and_service_recovers(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    import sqlite3
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLiteWriteService

    apply_migrations()
    writer = SQLiteWriteService(max_queue=4)

    def disk_full(conn):
        conn.execute(
            "INSERT INTO domain_revisions(domain,revision,updated_at) "
            "VALUES ('disk-full-test',1,'now')"
        )
        raise sqlite3.OperationalError("database or disk is full")

    with pytest.raises(sqlite3.OperationalError, match="disk is full"):
        writer.submit("disk-full", disk_full, deadline_seconds=1)

    result = writer.submit(
        "after-disk-full",
        lambda conn: conn.execute(
            "INSERT INTO domain_revisions(domain,revision,updated_at) "
            "VALUES ('after-disk-full',1,'now')"
        ).rowcount,
        deadline_seconds=1,
    )
    metrics = writer.snapshot()
    writer.shutdown()

    with read_connection() as conn:
        failed_row = conn.execute(
            "SELECT revision FROM domain_revisions WHERE domain='disk-full-test'"
        ).fetchone()
        recovered_row = conn.execute(
            "SELECT revision FROM domain_revisions WHERE domain='after-disk-full'"
        ).fetchone()
    assert result == 1
    assert failed_row is None
    assert int(recovered_row[0]) == 1
    assert metrics["rollback_count"] >= 1


def test_concurrent_reads_and_single_writer_commands_remain_consistent(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    errors = []

    def write(index):
        try:
            store.record_command(
                command_id=f"concurrent-command-{index:03d}",
                subject="pocketlab.commands.node.restart_agent",
                status="succeeded",
                entity_type="device",
                entity_id="phone-two",
                summary="Concurrent command.",
            )
        except Exception as exc:  # pragma: no cover - assertion captures unexpected paths
            errors.append(exc)

    def read():
        try:
            for _ in range(20):
                store.command_history(
                    entity_type="device", entity_id="phone-two", limit=25
                )
        except Exception as exc:  # pragma: no cover - assertion captures unexpected paths
            errors.append(exc)

    writers = [threading.Thread(target=write, args=(index,)) for index in range(40)]
    readers = [threading.Thread(target=read) for _ in range(4)]
    for thread in writers + readers:
        thread.start()
    for thread in writers + readers:
        thread.join(5)

    page = store.command_history(
        entity_type="device", entity_id="phone-two", limit=100
    )
    assert errors == []
    assert page["count"] == 40
    assert len({item["command_id"] for item in page["items"]}) == 40
    assert store.metrics()["writer"]["write_count"] >= 40


def test_expired_stale_refresh_returns_truthful_degraded_snapshot(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    payload = {"status": "healthy", "devices": [], "updated_at": "2026-07-21T12:00:00Z"}
    first = store.prepared_read(
        domain="fleet",
        key="degraded",
        builder=lambda: payload,
        projector=store.project_fleet,
        stale_after_ms=0,
        max_stale_ms=0,
    )
    time.sleep(0.01)

    def fail_builder():
        raise OSError("bounded source unavailable")

    degraded = store.prepared_read(
        domain="fleet",
        key="degraded",
        builder=fail_builder,
        projector=store.project_fleet,
        stale_after_ms=0,
        max_stale_ms=0,
    )
    assert degraded.payload == first.payload
    assert degraded.etag == first.etag
    assert degraded.read_degraded is True
    assert degraded.refresh_pending is False


def test_cold_prepared_read_returns_sqlite_fallback_and_refreshes_in_background(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    payload = {
        "apps": [{
            "app_id": "photoprism", "name": "PhotoPrism", "installed": True,
            "status": "ready", "summary": "Saved app state",
        }],
        "updated_at": "2026-07-21T12:00:00Z",
    }
    assert store.project_apps(payload) == 1

    def slow_builder():
        time.sleep(0.15)
        return {
            "apps": [{
                "app_id": "photoprism", "name": "PhotoPrism", "installed": True,
                "status": "ready", "summary": "Fresh app state",
            }],
            "updated_at": "2026-07-21T12:01:00Z",
            "__projection_stage_timing_ms": {"catalog": 120.0, "storage": 20.0},
        }

    started = time.monotonic()
    first = store.prepared_read(
        domain="apps", key="lifecycle", builder=slow_builder,
        projector=store.project_apps, stale_after_ms=10_000, max_stale_ms=60_000,
        deadline_seconds=0.05, cold_start_async=True,
        fallback_builder=store.app_projection_snapshot,
    )
    elapsed = time.monotonic() - started
    assert elapsed < 0.10
    assert first.read_degraded is True
    assert first.refresh_pending is True
    assert first.payload["projection_only"] is True

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        second = store.prepared_read(
            domain="apps", key="lifecycle", builder=slow_builder,
            projector=store.project_apps, stale_after_ms=10_000, max_stale_ms=60_000,
            deadline_seconds=0.05, cold_start_async=True,
            fallback_builder=store.app_projection_snapshot,
        )
        if not second.read_degraded and not second.refresh_pending:
            break
        time.sleep(0.02)
    assert second.payload["apps"][0]["summary"] == "Fresh app state"
    metrics = store.prepared_metrics()
    assert metrics["stage_timings_ms"]["apps:lifecycle"]["catalog"] == 120.0
    assert metrics["sanitized"] is True


def test_cold_prepared_read_without_snapshot_fails_fast_with_controlled_signal(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import (
        ControlPlaneProjectionStore, PreparedProjectionUnavailable,
    )

    store = ControlPlaneProjectionStore()
    started = time.monotonic()
    with pytest.raises(PreparedProjectionUnavailable):
        store.prepared_read(
            domain="recovery", key="summary",
            builder=lambda: (time.sleep(0.2) or {"status": "healthy"}),
            projector=store.project_recovery, stale_after_ms=10_000, max_stale_ms=60_000,
            deadline_seconds=0.05, cold_start_async=True,
            fallback_builder=lambda: None,
        )
    assert time.monotonic() - started < 0.10


def test_database_replacement_fence_clears_prepared_refresh_state(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.warm_prepared_read(
        domain="apps", key="lifecycle",
        builder=lambda: (time.sleep(0.1) or {"apps": [], "updated_at": "2026-07-21T12:00:00Z"}),
        projector=store.project_apps, deadline_seconds=0.05,
    )
    assert "apps:lifecycle" in store.prepared_metrics()["refreshing"]
    store.invalidate_after_database_replacement()
    metrics = store.prepared_metrics()
    assert metrics["refreshing"] == {}
    assert metrics["prepared_keys"] == []
