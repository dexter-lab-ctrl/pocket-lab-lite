from __future__ import annotations

import importlib.util
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from starlette.requests import Request

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_DEV_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_NODE_ID", "pocket-lab-lite-server")
    monkeypatch.setenv("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")
    monkeypatch.setenv("POCKETLAB_LITE_DISABLE_PROJECTION_WARMUP", "1")
    monkeypatch.setenv("POCKETLAB_LITE_DISABLE_DEVICE_HEALTH_SWEEP", "1")
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    reset_sqlite_path_cache()
    CONTROL_PLANE.initialize()
    CONTROL_PLANE.invalidate_after_database_replacement()
    return state


def _request(path: str, etag: str = "") -> Request:
    headers = [(b"x-pocket-lab-test", b"1")]
    if etag:
        headers.append((b"if-none-match", etag.encode("utf-8")))
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8080),
    })


def _json_response(response) -> dict:
    return json.loads(response.body.decode("utf-8")) if getattr(response, "body", b"") else {}


def _wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _lifecycle_count(device_id: str, event_type: str) -> int:
    from api_fastapi.db.connection import read_connection

    with read_connection() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM device_lifecycle_events WHERE device_id=? AND event_type=?",
            (device_id, event_type),
        ).fetchone()[0])


def test_e1_one_time_lifecycle_event_is_unique_across_100_replays(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry

    for index in range(100):
        fleet_registry.append_device_lifecycle_event(
            "phone-two",
            "first_heartbeat_received",
            occurred_at=f"2026-07-24T08:{index // 60:02d}:{index % 60:02d}Z",
            dedupe_key="phone-two:first_heartbeat_received",
        )
    assert _lifecycle_count("phone-two", "first_heartbeat_received") == 1


def test_e1_concurrent_callbacks_commit_one_logical_record(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry

    def append(index: int):
        return fleet_registry.append_device_lifecycle_event(
            "phone-two",
            "first_supervisor_heartbeat",
            occurred_at=f"2026-07-24T08:00:{index:02d}Z",
            dedupe_key="phone-two:first_supervisor_heartbeat_received",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(append, range(40)))
    assert sum(1 for item in results if item["changed"]) == 1
    assert _lifecycle_count("phone-two", "first_supervisor_heartbeat") == 1


def test_e1_identity_generation_is_monotonic_and_never_uses_credential_hash(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services import fleet_registry

    credential_hash = "a" * 64
    fleet_registry.upsert_agent(
        {
            "node_id": "phone-two",
            "hostname": "Phone Two",
            "role": "compute",
            "status": "online",
            "heartbeat_at": "2026-07-24T08:00:00Z",
            "auth_token_hash": credential_hash,
        },
        event_type="fleet.node_heartbeat",
    )
    fleet_registry.upsert_agent(
        {
            "node_id": "phone-two",
            "hostname": "Phone Two",
            "role": "compute",
            "status": "online",
            "heartbeat_at": "2026-07-24T08:01:00Z",
            "auth_token_hash": credential_hash,
        },
        event_type="fleet.node_heartbeat",
    )

    with read_connection() as conn:
        rows = conn.execute(
            "SELECT dedupe_key,generation_key FROM device_lifecycle_events "
            "WHERE device_id=? AND event_type='identity_verified'",
            ("phone-two",),
        ).fetchall()
    assert [(row["dedupe_key"], row["generation_key"]) for row in rows] == [
        ("phone-two:identity_verified:1", "1")
    ]

    events_path = state / "fleet_device_events.json"
    assert _wait_for(lambda: events_path.exists())
    exported = events_path.read_text(encoding="utf-8")
    assert credential_hash not in exported
    assert "phone-two:identity_verified:1" in exported


def test_e1_identity_mismatch_and_invite_replay_fail_closed(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry

    trusted_hash = "a" * 32
    mismatched_hash = "b" * 32
    fleet_registry.upsert_agent(
        {
            "node_id": "phone-two", "hostname": "Phone Two", "status": "online",
            "heartbeat_at": "2026-07-24T08:00:00Z", "auth_token_hash": trusted_hash,
        },
        event_type="fleet.node_heartbeat",
    )
    for _ in range(2):
        blocked = fleet_registry.upsert_agent(
            {
                "node_id": "phone-two", "hostname": "Phone Two", "status": "online",
                "heartbeat_at": "2026-07-24T08:05:00Z", "auth_token_hash": mismatched_hash,
            },
            event_type="fleet.node_heartbeat",
        )
        assert blocked["auth_token_hash"] == trusted_hash
        assert blocked["identity_status"] == "verified"
    assert _lifecycle_count("phone-two", "identity_mismatch_blocked") == 1

    current_state = {
        "node_id": "phone-three", "name": "Phone Three", "role": "compute",
        "status": "joining", "connection": "waiting",
    }
    for _ in range(10):
        fleet_registry.append_device_lifecycle_event(
            "phone-three", "invite_accepted", invite_id="invite-phone-three-1",
            occurred_at="2026-07-24T08:10:00Z", current_state=current_state,
        )
    assert _lifecycle_count("phone-three", "invite_accepted") == 1
    events_path = state / "fleet_device_events.json"
    expected_key = "phone-three:invite_accepted:invite-phone-three-1"
    assert _wait_for(
        lambda: events_path.exists()
        and expected_key in events_path.read_text(encoding="utf-8")
    )
    exported = events_path.read_text(encoding="utf-8")
    assert mismatched_hash not in exported
    assert expected_key in exported


def test_e1_server_host_state_requires_explicit_protection(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    with pytest.raises(ValueError, match="explicitly protected"):
        CONTROL_PLANE.commit_device_lifecycle_transition(
            {
                "event_id": "unsafe-server-ready", "device_id": "server-shadow",
                "event_type": "first_ready", "occurred_at": "2026-07-24T08:00:00Z",
                "dedupe_key": "server-shadow:first_ready",
            },
            current_state={
                "node_id": "server-shadow", "name": "Server Shadow",
                "role": "server_host", "status": "online",
                "protected_server_host": False,
            },
        )
    assert _lifecycle_count("server-shadow", "first_ready") == 0


def test_e1_repeatable_lifecycle_generations_remain_distinct(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry

    for generation in ("offline-1", "offline-2", "offline-1"):
        fleet_registry.append_device_lifecycle_event(
            "phone-two",
            "device_returned_online",
            occurred_at="2026-07-24T08:00:00Z",
            generation_key=generation,
            dedupe_key=f"phone-two:device_returned_online:{generation}",
        )
    assert _lifecycle_count("phone-two", "device_returned_online") == 2


def test_e1_json_export_failure_does_not_rollback_sqlite(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services import fleet_registry

    monkeypatch.setattr(fleet_registry, "_write", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("export blocked")))
    event = fleet_registry.append_device_lifecycle_event(
        "phone-two", "first_ready", occurred_at="2026-07-24T08:00:00Z",
        dedupe_key="phone-two:first_ready",
    )
    assert event["changed"] is True
    assert _lifecycle_count("phone-two", "first_ready") == 1

    def export_failed() -> bool:
        with read_connection() as conn:
            row = conn.execute(
                "SELECT export_status FROM device_lifecycle_transactions WHERE event_id=?",
                (event["event_id"],),
            ).fetchone()
            return bool(row and row[0] == "failed")

    assert _wait_for(export_failed)


def test_e1_sqlite_failure_does_not_emit_compatibility_json(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    monkeypatch.setattr(
        CONTROL_PLANE,
        "commit_device_lifecycle_transition",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("writer failed")),
    )
    with pytest.raises(sqlite3.OperationalError):
        fleet_registry.append_device_lifecycle_event(
            "phone-two", "first_ready", occurred_at="2026-07-24T08:00:00Z",
            dedupe_key="phone-two:first_ready",
        )
    assert not (state / "fleet_device_events.json").exists()


def test_e1_restart_resumes_pending_compatibility_export(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services import fleet_registry

    real_submit = fleet_registry._LIFECYCLE_EXPORT_EXECUTOR.submit
    monkeypatch.setattr(
        fleet_registry._LIFECYCLE_EXPORT_EXECUTOR,
        "submit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("process stopping")),
    )
    event = fleet_registry.append_device_lifecycle_event(
        "phone-two", "first_ready", occurred_at="2026-07-24T08:00:00Z",
        dedupe_key="phone-two:first_ready",
    )
    monkeypatch.setattr(fleet_registry._LIFECYCLE_EXPORT_EXECUTOR, "submit", real_submit)
    assert fleet_registry.resume_pending_lifecycle_exports() == 1

    path = state / "fleet_device_events.json"
    assert _wait_for(lambda: path.exists() and event["event_id"] in path.read_text(encoding="utf-8"))
    with read_connection() as conn:
        status = conn.execute(
            "SELECT export_status FROM device_lifecycle_transactions WHERE event_id=?",
            (event["event_id"],),
        ).fetchone()[0]
    assert status == "exported"


def test_e1_database_instance_fence_rolls_back(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    with pytest.raises(RuntimeError, match="database instance changed"):
        CONTROL_PLANE.commit_device_lifecycle_transition(
            {
                "event_id": "fenced-event",
                "device_id": "phone-two",
                "event_type": "first_ready",
                "occurred_at": "2026-07-24T08:00:00Z",
                "dedupe_key": "phone-two:first_ready",
                "summary": "Ready.",
            },
            expected_database_instance="replaced-database",
        )
    assert _lifecycle_count("phone-two", "first_ready") == 0


def _load_reconcile_module():
    script = Path("scripts/lite/device-lifecycle-reconcile.py")
    spec = importlib.util.spec_from_file_location("device_lifecycle_reconcile", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_e1_projection_cleanup_racing_active_writes_preserves_journal(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services import fleet_registry
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    now = "2026-07-24T08:00:00Z"
    device = {
        "id": "phone-two", "node_id": "phone-two", "name": "Phone Two",
        "role": "compute", "status": "online", "connection": "online",
        "agent_status": "online", "last_seen_at": now,
    }
    CONTROL_PLANE.project_fleet({
        "status": "healthy", "devices": [device],
        "remote_access": {"ready": False, "status": "not_ready"},
        "updated_at": now,
    })

    def append_replay(_index: int):
        return fleet_registry.append_device_lifecycle_event(
            "phone-two", "first_ready", occurred_at=now,
            dedupe_key="phone-two:first_ready", current_state=device,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(append_replay, index) for index in range(20)]
        cleanup = pool.submit(
            CONTROL_PLANE.project_fleet,
            {
                "status": "degraded", "devices": [],
                "remote_access": {"ready": False, "status": "not_ready"},
                "updated_at": "2026-07-24T08:01:00Z",
            },
        )
        results = [future.result() for future in futures]
        cleanup.result()

    assert sum(1 for result in results if result["changed"]) == 1
    assert _lifecycle_count("phone-two", "first_ready") == 1
    with read_connection() as conn:
        row = conn.execute(
            "SELECT connection_state FROM device_current_state WHERE device_id=?",
            ("phone-two",),
        ).fetchone()
    assert row is not None
    assert row["connection_state"] in {"online", "offline"}


def test_e1_reconciliation_is_dry_run_first_and_preserves_generations(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    module = _load_reconcile_module()
    path = state / "fleet_device_events.json"
    payload = {
        "events": [
            {"event_id": "later", "node_id": "phone-two", "event_type": "first_heartbeat_received", "occurred_at": "2026-07-24T09:00:00Z"},
            {"event_id": "earlier", "node_id": "phone-two", "event_type": "first_heartbeat_received", "occurred_at": "2026-07-24T08:00:00Z", "summary": "token=must-not-leak"},
            {"event_id": "return-1", "node_id": "phone-two", "event_type": "device_returned_online", "occurred_at": "2026-07-24T10:00:00Z", "generation_key": "offline-1"},
            {"event_id": "return-2", "node_id": "phone-two", "event_type": "device_returned_online", "occurred_at": "2026-07-24T11:00:00Z", "generation_key": "offline-2"},
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    database = state / "pocketlab-lite.sqlite3"

    dry = module.reconcile(state_dir=state, database=database, apply=False)
    assert dry["mode"] == "dry_run"
    assert dry["canonical_rows"] == 3
    assert path.read_bytes() == before

    applied = module.reconcile(state_dir=state, database=database, apply=True)
    assert applied["parity_matched"] is True
    assert applied["quick_check"] == "ok"
    canonical = json.loads(path.read_text(encoding="utf-8"))["events"]
    first = [item for item in canonical if item["event_type"] == "first_heartbeat_received"]
    repeated = [item for item in canonical if item["event_type"] == "device_returned_online"]
    assert [item["event_id"] for item in first] == ["earlier"]
    assert first[0]["summary"] == "Protected lifecycle metadata recorded."
    assert "must-not-leak" not in path.read_text(encoding="utf-8")
    assert {item["generation_key"] for item in repeated} == {"offline-1", "offline-2"}
    assert _lifecycle_count("phone-two", "first_heartbeat_received") == 1
    assert _lifecycle_count("phone-two", "device_returned_online") == 2


def _fleet_payload(now: str) -> dict:
    return {
        "status": "healthy",
        "devices": [{
            "id": "pocket-lab-lite-server", "name": "Server Phone", "role": "server_host",
            "status": "healthy", "connection": "online", "agent_status": "online",
            "supervisor_status": "healthy", "agent_process_status": "online",
            "last_seen_at": now, "is_current": True,
            "proactive_health": {"status": "healthy", "severity": "none", "summary": "Device health is healthy.", "evaluated_at": now},
        }],
        "remote_access": {"ready": True, "status": "healthy"},
        "updated_at": now,
    }


def _apps_payload(now: str) -> dict:
    return {
        "status": "healthy",
        "apps": [{
            "app_id": "photoprism", "id": "photoprism", "name": "PhotoPrism",
            "installed": True, "status": "ready", "summary": "PhotoPrism is ready.",
            "security": {"status": "protected"},
            "operations": {"status": "idle", "summary": "No app action is running.", "actions": {}},
        }],
        "updated_at": now,
    }


def _recovery_payload(now: str) -> dict:
    return {
        "status": "healthy", "summary": "Recovery ready.",
        "last_backup": {"backup_id": "backup-1", "status": "verified", "verification_status": "verified", "created_at": now, "verified_at": now, "size_bytes": 1024},
        "maintenance": {"active": False, "status": "idle"},
        "updated_at": now,
    }


def test_e3_hot_get_handlers_serve_sqlite_without_live_collectors(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.routers import lite as router_lite
    from api_fastapi.services import lite_app_backup, lite_app_lifecycle, lite_app_update, lite_status
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    CONTROL_PLANE.project_fleet(_fleet_payload(now))
    CONTROL_PLANE.project_apps(_apps_payload(now))
    CONTROL_PLANE.update_app_subprojection("photoprism", "update", {
        "status": "ready", "summary": "Update readiness is saved.", "updated_at": now,
    })
    CONTROL_PLANE.update_app_subprojection("photoprism", "backup", {
        "status": "healthy", "summary": "App backup state is saved.",
        "latest_verified_backup_id": "backup-1", "updated_at": now,
    })
    CONTROL_PLANE.project_recovery(_recovery_payload(now))
    CONTROL_PLANE.invalidate_after_database_replacement()

    def poisoned(*_args, **_kwargs):
        raise AssertionError("live collector reached a prepared GET path")

    monkeypatch.setattr(lite_status, "lite_fleet", poisoned)
    monkeypatch.setattr(lite_app_lifecycle, "app_lifecycle_profiles", poisoned)
    monkeypatch.setattr(lite_app_update, "update_status", poisoned)
    monkeypatch.setattr(lite_app_backup, "app_backup_status", poisoned)
    monkeypatch.setattr(router_lite, "_build_lite_catalog_projection", poisoned)
    monkeypatch.setattr(router_lite, "_build_lite_recovery_summary_projection", poisoned)
    monkeypatch.setattr(router_lite, "_lite_recovery_details_payload", poisoned)

    responses = [
        router_lite.get_lite_fleet(_request("/api/lite/fleet")),
        router_lite.get_lite_fleet_health_summary(_request("/api/lite/fleet/health-summary")),
        router_lite.get_lite_app_lifecycle_profiles(_request("/api/lite/apps/lifecycle")),
        router_lite.get_lite_app_lifecycle_profile("photoprism", _request("/api/lite/apps/lifecycle/photoprism")),
        router_lite.get_lite_catalog(_request("/api/lite/catalog")),
        router_lite.get_lite_app_update_status("photoprism", _request("/api/lite/apps/photoprism/update")),
        router_lite.get_lite_app_backup_status("photoprism", _request("/api/lite/apps/photoprism/backup")),
        router_lite.get_lite_recovery_summary(_request("/api/lite/recovery/summary")),
        router_lite.get_lite_recovery_details(_request("/api/lite/recovery/details")),
    ]
    assert all(response.status_code == 200 for response in responses)
    assert all(_json_response(response).get("projection_age_ms", 0) >= 0 for response in responses if "projection_age_ms" in _json_response(response))
    assert _json_response(responses[0])["read_degraded"] is True
    assert _json_response(responses[0])["projection_only"] is True


def test_e3_no_saved_state_returns_bounded_warming_without_builder(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services import projection_scheduler
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE, PreparedProjectionUnavailable

    calls = 0

    class FakeScheduler:
        def mark_dirty(self, *_args, **_kwargs):
            return {"accepted": True, "refresh_pending": True, "retry_after_seconds": 60}
        def status(self, *_args, **_kwargs):
            return {"refresh_pending": False, "retry_after_seconds": 0}

    monkeypatch.setattr(projection_scheduler, "PROJECTION_SCHEDULER", FakeScheduler())

    def builder():
        nonlocal calls
        calls += 1
        return {"status": "healthy"}

    started = time.monotonic()
    with pytest.raises(PreparedProjectionUnavailable):
        CONTROL_PLANE.prepared_only_read(
            domain="recovery", key="missing", snapshot_builder=lambda: None,
            builder=builder, projector=CONTROL_PLANE.project_recovery,
            stale_after_ms=1_000, max_stale_ms=5_000,
        )
    assert time.monotonic() - started < 0.1
    assert calls == 0


def test_e3_prepared_etag_304_and_read_latency_are_bounded(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.routers import lite as router_lite
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    CONTROL_PLANE.project_fleet(_fleet_payload(now))
    CONTROL_PLANE.invalidate_after_database_replacement()
    durations: list[float] = []
    response = None
    for _ in range(20):
        started = time.monotonic()
        response = router_lite.get_lite_fleet(_request("/api/lite/fleet"))
        durations.append(time.monotonic() - started)
        assert response.status_code == 200
    assert sorted(durations)[18] < 0.15
    assert response is not None
    etag = response.headers["etag"]
    unchanged = router_lite.get_lite_fleet(_request("/api/lite/fleet", etag=etag))
    assert unchanged.status_code == 304


def test_e3_get_is_read_only_and_revision_change_updates_etag(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.routers import lite as router_lite
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    first_payload = _fleet_payload(now)
    CONTROL_PLANE.project_fleet(first_payload)
    CONTROL_PLANE.invalidate_after_database_replacement()
    with read_connection() as conn:
        before = {
            "fleet_revision": conn.execute(
                "SELECT revision FROM domain_revisions WHERE domain='fleet'"
            ).fetchone()[0],
            "scheduler_rows": conn.execute(
                "SELECT COUNT(*) FROM projection_refresh_state"
            ).fetchone()[0],
        }
    response = router_lite.get_lite_fleet(_request("/api/lite/fleet"))
    assert response.status_code == 200
    first_etag = response.headers["etag"]
    with read_connection() as conn:
        after = {
            "fleet_revision": conn.execute(
                "SELECT revision FROM domain_revisions WHERE domain='fleet'"
            ).fetchone()[0],
            "scheduler_rows": conn.execute(
                "SELECT COUNT(*) FROM projection_refresh_state"
            ).fetchone()[0],
        }
    assert after == before

    changed = _fleet_payload(now)
    changed["devices"][0]["summary"] = "Device state changed."
    changed["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    CONTROL_PLANE.project_fleet(changed)
    CONTROL_PLANE.invalidate_after_database_replacement()
    second = router_lite.get_lite_fleet(_request("/api/lite/fleet"))
    assert second.status_code == 200
    assert second.headers["etag"] != first_etag


def test_e3_frontend_respects_backend_retry_after_contract():
    api = Path("src/lib/liteApi.js").read_text(encoding="utf-8")
    query = Path("src/hooks/useLiteQuery.js").read_text(encoding="utf-8")
    polling = Path("src/lib/litePollingPolicy.js").read_text(encoding="utf-8")
    assert "retryAfterSeconds" in api
    assert "retry_after_seconds" in query
    assert "backendCooldownMs" in polling
    assert "Math.min(Number(retryAfterSeconds)" in polling


def _new_scheduler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, io_workers: int = 1, cpu_workers: int = 1):
    _configure(tmp_path, monkeypatch)
    monkeypatch.setenv("POCKETLAB_LITE_PROJECTION_IO_WORKERS", str(io_workers))
    monkeypatch.setenv("POCKETLAB_LITE_PROJECTION_CPU_WORKERS", str(cpu_workers))
    from api_fastapi.services.projection_scheduler import ProjectionScheduler

    return ProjectionScheduler()


def test_e4_single_flight_coalesces_and_discards_stale_generation(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob

    release = threading.Event()
    lock = threading.Lock()
    active = 0
    max_active = 0
    calls = 0
    committed: list[int] = []

    def builder():
        nonlocal active, max_active, calls
        with lock:
            active += 1
            max_active = max(max_active, active)
            calls += 1
        release.wait(1.0)
        with lock:
            active -= 1
        return {"value": calls}

    job = ProjectionJob("fleet.health", builder, lambda payload: committed.append(payload["value"]) or len(committed), 20, "io", 1.5)
    scheduler.mark_dirty("fleet.health", job=job)
    assert _wait_for(lambda: scheduler.status("fleet.health").get("active") is True)
    for _ in range(25):
        scheduler.mark_dirty("fleet.health", priority=10)
    release.set()
    assert _wait_for(lambda: scheduler.status("fleet.health").get("committed_generation") == scheduler.status("fleet.health").get("generation"), 3.0)
    status = scheduler.status("fleet.health")
    assert max_active == 1
    assert calls == 2
    assert status["coalesced_count"] >= 25
    assert status["stale_generation_count"] >= 1
    assert committed
    scheduler.shutdown(drain_seconds=1.0)


def test_e4_cross_domain_capacity_and_priority_order(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch, io_workers=1)
    from api_fastapi.services.projection_scheduler import ProjectionJob

    release = threading.Event()
    order: list[str] = []

    def blocker():
        order.append("blocker")
        release.wait(1.0)
        return {"ok": True}

    def build(name: str):
        return lambda: (order.append(name) or {"ok": True})

    scheduler.mark_dirty("blocker", job=ProjectionJob("blocker", blocker, lambda _p: 1, 1, "critical", 2.0))
    assert _wait_for(lambda: scheduler.status("blocker").get("active") is True)
    scheduler.mark_dirty("maintenance", job=ProjectionJob("maintenance", build("low"), lambda _p: 1, 90, "io", 1.0))
    scheduler.mark_dirty("commands", job=ProjectionJob("commands", build("high"), lambda _p: 1, 5, "critical", 1.0))
    release.set()
    assert _wait_for(lambda: len(order) >= 3, 3.0)
    assert order[:3] == ["blocker", "high", "low"]
    diagnostics = scheduler.diagnostics()
    assert diagnostics["io_workers"] == 1
    assert diagnostics["active_io"] <= 1
    scheduler.shutdown(drain_seconds=1.0)


def test_e4_deadline_backoff_success_reset_and_shutdown_fence(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob

    slow = ProjectionJob(
        "apps.lifecycle", lambda: (time.sleep(0.15) or {"ok": True}),
        lambda _payload: 1, 40, "cpu", 0.1,
    )
    scheduler.mark_dirty("apps.lifecycle", job=slow)
    assert _wait_for(lambda: scheduler.status("apps.lifecycle").get("failure_count") == 1, 2.0)
    status = scheduler.status("apps.lifecycle")
    assert 60 <= status["retry_after_seconds"] <= 65
    assert status["last_error_type"] == "DeadlineExceeded"

    with scheduler._condition:
        scheduler._states["apps.lifecycle"].next_retry_at = 0.0
    fast = ProjectionJob("apps.lifecycle", lambda: {"ok": True}, lambda _payload: 2, 40, "cpu", 1.0)
    scheduler.mark_dirty("apps.lifecycle", job=fast)
    assert _wait_for(lambda: scheduler.status("apps.lifecycle").get("committed_generation") == scheduler.status("apps.lifecycle").get("generation"), 2.0)
    assert scheduler.status("apps.lifecycle")["failure_count"] == 0
    scheduler.shutdown(drain_seconds=1.0)
    rejected = scheduler.mark_dirty("apps.lifecycle")
    assert rejected["accepted"] is False
    assert rejected["reason"] == "shutdown"


def test_e4_database_generation_mismatch_and_pressure_deferral(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob
    from api_fastapi.services.runtime_diagnostics import RUNTIME_DIAGNOSTICS

    release = threading.Event()
    original_instance = scheduler._database_instance()
    current = {"value": original_instance}
    monkeypatch.setattr(scheduler, "_database_instance", lambda: current["value"])

    def builder():
        release.wait(1.0)
        return {"ok": True}

    scheduler.mark_dirty("recovery.details", job=ProjectionJob("recovery.details", builder, lambda _p: 1, 60, "io", 1.5))
    assert _wait_for(lambda: scheduler.status("recovery.details").get("active") is True)
    current["value"] = "replacement"
    release.set()
    assert _wait_for(lambda: scheduler.status("recovery.details").get("last_error_type") == "DatabaseGenerationMismatch", 2.0)

    monkeypatch.setattr(RUNTIME_DIAGNOSTICS, "latest_event_loop_lag_ms", lambda: scheduler.critical_lag_ms + 1)
    with scheduler._condition:
        scheduler._states["recovery.details"].next_retry_at = 0.0
    scheduler.mark_dirty("recovery.details", job=ProjectionJob("recovery.details", lambda: {"ok": True}, lambda _p: 1, 80, "io", 1.0))
    assert _wait_for(lambda: scheduler.status("recovery.details").get("pressure_reason") == "event_loop_pressure")
    assert scheduler.status("recovery.details")["active"] is False
    scheduler.shutdown(drain_seconds=1.0)


def test_e4_dirty_signal_never_persists_diagnostics_on_request_thread(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob

    caller_thread = threading.current_thread().name
    persistence_threads: list[str] = []
    original = scheduler._persist_state_best_effort

    def record_persistence(domain, state):
        persistence_threads.append(threading.current_thread().name)
        return original(domain, state)

    monkeypatch.setattr(scheduler, "_persist_state_best_effort", record_persistence)
    scheduler.mark_dirty(
        "fleet.summary",
        job=ProjectionJob("fleet.summary", lambda: {"ok": True}, lambda _p: 1, 10, "critical", 1.0),
    )
    assert _wait_for(lambda: scheduler.status("fleet.summary").get("committed_generation") == 1)
    assert caller_thread not in persistence_threads
    scheduler.shutdown(drain_seconds=1.0)


def test_e4_timed_out_child_keeps_domain_occupied_and_queue_bounded(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob

    release = threading.Event()
    calls = 0

    def builder():
        nonlocal calls
        calls += 1
        release.wait(1.0)
        return {"ok": True}

    job = ProjectionJob("apps.catalog", builder, lambda _p: 1, 40, "cpu", 0.05)
    scheduler.mark_dirty("apps.catalog", job=job)
    assert _wait_for(lambda: scheduler.status("apps.catalog").get("active") is True)
    for _ in range(100):
        scheduler.mark_dirty("apps.catalog", priority=20)
    time.sleep(0.13)
    with scheduler._condition:
        queued_for_domain = sum(1 for item in scheduler._heap if item[2] == "apps.catalog")
    assert calls == 1
    assert scheduler.status("apps.catalog")["active"] is True
    assert queued_for_domain <= 1
    release.set()
    assert _wait_for(lambda: scheduler.status("apps.catalog").get("last_error_type") == "DeadlineExceeded")
    assert scheduler.status("apps.catalog")["retry_after_seconds"] >= 60
    scheduler.shutdown(drain_seconds=1.0)


def test_e4_capacity_is_bounded_and_executor_rejection_cools_down(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob

    for index in range(scheduler.max_domains):
        scheduler.register(ProjectionJob(f"domain-{index}", lambda: {"ok": True}, lambda _p: 1, 50, "io", 1.0))
    with pytest.raises(RuntimeError, match="capacity"):
        scheduler.register(ProjectionJob("overflow", lambda: {"ok": True}, lambda _p: 1, 50, "io", 1.0))

    rejecting = _new_scheduler(tmp_path / "reject", monkeypatch)
    rejecting.start()
    assert rejecting._io_executor is not None
    monkeypatch.setattr(rejecting._io_executor, "submit", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("rejected")))
    rejecting.mark_dirty("fleet.summary", job=ProjectionJob("fleet.summary", lambda: {"ok": True}, lambda _p: 1, 10, "critical", 1.0))
    assert _wait_for(lambda: rejecting.status("fleet.summary").get("last_error_type") == "ExecutorRejected")
    assert rejecting.status("fleet.summary")["retry_after_seconds"] >= 60
    scheduler.shutdown(drain_seconds=1.0)
    rejecting.shutdown(drain_seconds=1.0)


def test_e4_refresh_hints_do_not_invalidate_active_generation(tmp_path, monkeypatch):
    scheduler = _new_scheduler(tmp_path, monkeypatch)
    from api_fastapi.services.projection_scheduler import ProjectionJob

    release = threading.Event()
    calls = 0
    committed: list[int] = []

    def builder():
        nonlocal calls
        calls += 1
        release.wait(1.0)
        return {"value": calls}

    job = ProjectionJob(
        "fleet.summary",
        builder,
        lambda payload: committed.append(payload["value"]) or len(committed),
        20,
        "io",
        1.5,
    )
    first = scheduler.mark_dirty(
        "fleet.summary", job=job, force_followup=False
    )
    assert first["generation"] == 1
    assert _wait_for(lambda: scheduler.status("fleet.summary").get("active") is True)

    for _ in range(100):
        result = scheduler.mark_dirty(
            "fleet.summary", priority=10, force_followup=False
        )
        assert result["generation"] == 1
        assert result["coalesced"] is True

    release.set()
    assert _wait_for(
        lambda: scheduler.status("fleet.summary").get("refresh_pending") is False,
        3.0,
    )
    status = scheduler.status("fleet.summary")
    assert calls == 1
    assert committed == [1]
    assert status["generation"] == 1
    assert status["committed_generation"] == 1
    assert status["stale_generation_count"] == 0
    assert status["coalesced_count"] >= 100
    scheduler.shutdown(drain_seconds=1.0)


def test_e3_prepared_reads_use_coalescing_refresh_hints():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/"
        "lite_control_plane_store.py"
    ).read_text(encoding="utf-8")
    prepared_only = source.split("def prepared_only_read", 1)[1].split(
        "def warm_prepared_read", 1
    )[0]
    assert prepared_only.count("force_followup=False") == 2
