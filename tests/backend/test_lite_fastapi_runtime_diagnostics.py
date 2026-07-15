from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
import gc
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts/dev/check-lite-production-gate-server-phone.sh"
LITE_API = ROOT / "src/lib/liteApi.js"
LITE_QUERY = ROOT / "src/hooks/useLiteQuery.js"


def _configure_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    from api_fastapi import deps
    from api_fastapi.services import lite_security

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    lite_security.stop_security_projection_runtime()
    with lite_security._SQLITE_PROGRESS_SNAPSHOT_LOCK:
        lite_security._SQLITE_PROGRESS_SNAPSHOT = None
        lite_security._SQLITE_PROGRESS_PREPARED = None
        lite_security._SQLITE_PROGRESS_SNAPSHOT_DB = ""
        lite_security._SQLITE_PROGRESS_SNAPSHOT_IDENTITY = None
        lite_security._SQLITE_PROGRESS_REFRESHED_AT = 0.0
        lite_security._SQLITE_PROGRESS_VERIFIED_AT = 0.0
        lite_security._SQLITE_PROGRESS_EPOCH = 0
    with lite_security._SQLITE_PROGRESS_METRICS_LOCK:
        for key in lite_security._SQLITE_PROGRESS_METRICS:
            lite_security._SQLITE_PROGRESS_METRICS[key] = 0
    lite_security._SQLITE_PROGRESS_FAILURES = 0
    lite_security._SQLITE_PROGRESS_DIRTY.clear()
    lite_security.invalidate_security_read_caches()
    return state, lite_security


def _reserve(lite_security, run_id: str = "security-constant-progress"):
    result = lite_security.reserve_scan_request(
        {
            "run_id": run_id,
            "command_id": run_id,
            "profile": "quick",
            "scope": "local",
            "requested_at": "2026-07-15T00:00:00Z",
        }
    )
    assert result["reserved"] is True


def test_event_loop_monitor_starts_once_records_lag_and_stops_cleanly():
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(
        loop_interval_seconds=0.01,
        loop_warning_ms=1.0,
        loop_critical_ms=10.0,
        gc_slow_ms=10_000.0,
    )

    async def exercise():
        assert await diagnostics.start() is True
        task = diagnostics._loop_task
        assert task is not None
        assert await diagnostics.start() is False
        assert diagnostics._loop_task is task
        diagnostics.record_event_loop_lag(12.0)
        await asyncio.sleep(0.03)
        await diagnostics.stop()
        return task

    task = asyncio.run(exercise())
    snapshot = diagnostics.snapshot()
    assert task.done()
    assert snapshot["event_loop"]["samples"] >= 1
    assert snapshot["event_loop"]["critical_count"] >= 1
    assert snapshot["event_loop"]["monitor_running"] is False
    assert diagnostics._gc_callback not in gc.callbacks


def test_event_loop_and_request_logging_are_thresholded_and_sanitized(caplog):
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(
        loop_interval_seconds=1.0,
        loop_warning_ms=250.0,
        loop_critical_ms=1000.0,
    )
    caplog.set_level(logging.INFO)
    diagnostics.record_event_loop_lag(300.0)
    diagnostics.record_event_loop_lag(350.0)
    diagnostics.record_progress_request(
        status_code=200,
        phases={
            "middleware_to_route_ms": 4.0,
            "auth_ms": 2.0,
            "snapshot_read_ms": 0.2,
            "response_build_ms": 0.3,
            "response_send_ms": 0.4,
            "request_total_ms": 1200.0,
        },
        event_loop_lag_ms=300.0,
    )
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert messages.count("pocketlab.runtime.event_loop_lag") == 1
    assert "pocketlab.runtime.progress_request_slow" in messages
    for forbidden in ("authorization", "bearer", "token", "password", "nats://"):
        assert forbidden not in messages.lower()




def test_fast_progress_request_does_not_emit_slow_log(caplog):
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(
        loop_warning_ms=250.0,
        loop_critical_ms=1000.0,
    )
    caplog.set_level(logging.INFO)
    diagnostics.record_progress_request(
        status_code=200,
        phases={
            "middleware_to_route_ms": 1.0,
            "auth_ms": 1.0,
            "snapshot_read_ms": 0.1,
            "response_build_ms": 0.1,
            "response_send_ms": 0.1,
            "request_total_ms": 4.0,
        },
        event_loop_lag_ms=1.0,
    )
    assert not any(
        "pocketlab.runtime.progress_request_slow" in record.getMessage()
        for record in caplog.records
    )


def test_gc_monitor_failure_is_fail_safe(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import runtime_diagnostics

    class BrokenCallbacks:
        def __contains__(self, _item):
            raise RuntimeError("callback registry unavailable")

    diagnostics = runtime_diagnostics.RuntimeDiagnostics(loop_interval_seconds=0.01)
    monkeypatch.setattr(runtime_diagnostics.gc, "callbacks", BrokenCallbacks())

    async def exercise():
        assert await diagnostics.start() is True
        await asyncio.sleep(0)
        await diagnostics.stop()

    asyncio.run(exercise())
    assert diagnostics.snapshot()["event_loop"]["monitor_running"] is False


def test_gc_callback_records_bounded_metrics_without_retaining_objects():
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(gc_slow_ms=10_000.0)
    diagnostics._gc_callback("start", {"generation": 1})
    diagnostics._gc_callback(
        "stop",
        {"generation": 1, "collected": 7, "uncollectable": 0},
    )
    snapshot = diagnostics.snapshot()["gc"]
    generation = snapshot["generations"]["generation_1"]
    assert generation["collections"] == 1
    assert generation["collected"] == 7
    assert generation["uncollectable"] == 0
    assert diagnostics._gc_started == {}


def test_prepared_progress_reuses_static_bytes_and_avoids_request_work(
    tmp_path, monkeypatch
):
    _, lite_security = _configure_sqlite(tmp_path, monkeypatch)
    _reserve(lite_security)

    prepared, _age = lite_security.prepared_security_progress()
    prefix = prepared.body_prefix
    etag = prepared.etag
    epoch = prepared.projection_epoch
    assert etag.startswith('W/"security-')
    assert json.loads(prepared.body_for_age(3.25))["projection_age_ms"] == 3.25
    with pytest.raises(FrozenInstanceError):
        prepared.etag = 'W/"changed"'

    def forbidden(*_args, **_kwargs):
        raise AssertionError("constant-cost Progress route invoked forbidden work")

    monkeypatch.setattr(lite_security, "_security_repository", forbidden)
    monkeypatch.setattr(lite_security, "_sqlite_progress_database_identity", forbidden)
    monkeypatch.setattr(lite_security, "split_progress_state", forbidden)
    monkeypatch.setattr(lite_security, "compact_response_etag", forbidden)
    monkeypatch.setattr(lite_security, "json", SimpleNamespace(dumps=forbidden))
    monkeypatch.setattr(lite_security, "copy", SimpleNamespace(deepcopy=forbidden))

    http = client()
    response = http.get("/api/lite/security/progress")
    assert response.status_code == 200
    assert response.headers["etag"] == etag
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert int(response.headers["content-length"]) == len(response.content)
    assert "snapshot;dur=" in response.headers["server-timing"]
    assert response.json()["run_id"] == "security-constant-progress"
    assert response.json()["projection_epoch"] == epoch

    not_modified = http.get(
        "/api/lite/security/progress", headers={"If-None-Match": etag}
    )
    assert not_modified.status_code == 304
    assert not_modified.content == b""
    assert "content-length" not in not_modified.headers
    prepared_after, _ = lite_security.prepared_security_progress()
    assert prepared_after is prepared
    assert prepared_after.body_prefix is prefix
    assert prepared_after.etag == etag


def test_unchanged_refresh_keeps_epoch_etag_and_prepared_reference(
    tmp_path, monkeypatch
):
    _, lite_security = _configure_sqlite(tmp_path, monkeypatch)
    _reserve(lite_security, "security-unchanged")
    repository = lite_security._security_repository()
    # The first reader pass may normalize the reservation's run revision.
    lite_security._refresh_sqlite_progress_snapshot_timed(repository=repository)
    before, _ = lite_security.prepared_security_progress()
    epoch = before.projection_epoch

    _payload, timings = lite_security._refresh_sqlite_progress_snapshot_timed(
        repository=repository
    )
    after, _ = lite_security.prepared_security_progress()

    assert timings["published"] == 0.0
    assert after is before
    assert after.etag == before.etag
    assert after.projection_epoch == epoch

    lite_security.mark_scan_accepted(
        {
            "run_id": "security-unchanged",
            "command_id": "security-unchanged",
            "profile": "quick",
            "accepted_at": "2026-07-15T00:00:01Z",
        }
    )
    changed, _ = lite_security.prepared_security_progress()
    assert changed is not before
    assert changed.etag != before.etag
    assert changed.projection_epoch > epoch


def test_dirty_notifications_coalesce_and_refresher_counters_are_bounded(
    tmp_path, monkeypatch
):
    _, lite_security = _configure_sqlite(tmp_path, monkeypatch)
    _reserve(lite_security, "security-refresher-counters")
    lite_security._SQLITE_PROGRESS_DIRTY.clear()
    lite_security.mark_security_progress_dirty()
    lite_security.mark_security_progress_dirty()
    assert (
        lite_security.security_progress_runtime_diagnostics()[
            "coalesced_dirty_notifications"
        ]
        >= 1
    )

    monkeypatch.setattr(
        lite_security, "_SQLITE_PROGRESS_ACTIVE_INTERVAL_SECONDS", 0.03
    )
    monkeypatch.setattr(
        lite_security, "_SQLITE_PROGRESS_IDLE_INTERVAL_SECONDS", 0.03
    )
    try:
        lite_security.start_security_projection_runtime()
        time.sleep(0.14)
        lite_security.mark_security_progress_dirty()
        lite_security.mark_security_progress_dirty()
        time.sleep(0.08)
    finally:
        lite_security.stop_security_projection_runtime()
    metrics = lite_security.security_progress_runtime_diagnostics()
    assert metrics["signaled_refreshes"] >= 1
    assert metrics["periodic_refreshes"] >= 1
    assert metrics["successful_refreshes"] >= 1
    assert metrics["unchanged_refreshes"] >= 1
    assert metrics["consecutive_immediate_wakeups"] <= 3


def test_runtime_diagnostics_endpoint_is_authenticated_bounded_and_sanitized(
    tmp_path, monkeypatch
):
    _configure_sqlite(tmp_path, monkeypatch)
    http = client()
    response = http.get("/api/lite/diagnostics/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sanitized"] is True
    assert set(payload) >= {"event_loop", "gc", "progress_requests", "security_progress"}
    rendered = response.text.lower()
    for forbidden in ("database_path", "authorization", "api_token", "nats://", "private_key"):
        assert forbidden not in rendered


def test_frontend_304_contract_and_production_gate_thresholds_are_preserved():
    api = LITE_API.read_text()
    query = LITE_QUERY.read_text()
    gate = GATE.read_text()

    assert "response.status === 304" in api
    assert "__liteNotModified" in api
    assert "queryClient.getQueryData(resolvedQueryKey)" in query
    assert "DIAGNOSTICS_URL" in gate
    assert '"runtime_diagnostics": runtime_diagnostics' in gate
    assert 'p95 >= 1.0' in gate
    assert 'maximum >= 3.0' in gate
    assert 'MAX_PROJECTION_AGE_MS' in gate
    assert "Production gate command failed at line" in gate

def test_fast_request_during_ambient_lag_is_not_classified_slow(caplog):
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(loop_warning_ms=250.0, loop_critical_ms=1000.0)
    caplog.set_level(logging.INFO)
    diagnostics.record_progress_request(
        status_code=200,
        phases={"request_total_ms": 8.0, "snapshot_read_ms": 0.1},
        event_loop_lag_ms=2200.0,
    )
    payload = diagnostics.snapshot()["progress_requests"]
    assert payload["slow_request_count"] == 0
    assert payload["requests_during_critical_lag"] == 1
    assert payload["recent_slow_requests"] == []
    assert not any("progress_request_slow" in r.getMessage() for r in caplog.records)


def test_active_operation_is_bounded_and_attached_to_lag_event():
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(loop_warning_ms=10.0, loop_critical_ms=20.0)
    token = diagnostics.begin_operation("security.scan.nats_publish")
    diagnostics.record_event_loop_lag(25.0)
    diagnostics.end_operation(token)
    payload = diagnostics.snapshot()["event_loop"]
    assert payload["recent_lag_events"][-1]["active_operations"] == ["security.scan.nats_publish"]
    assert payload["active_operations"] == []
    assert payload["recent_operations"][-1]["name"] == "security.scan.nats_publish"


def test_event_loop_and_gc_logs_are_rate_limited(caplog):
    ensure_runtime_path()
    from api_fastapi.services.runtime_diagnostics import RuntimeDiagnostics

    diagnostics = RuntimeDiagnostics(loop_warning_ms=10.0, loop_critical_ms=20.0, gc_slow_ms=0.01)
    diagnostics._loop_log_interval_seconds = 60.0
    diagnostics._gc_log_interval_seconds = 60.0
    caplog.set_level(logging.WARNING)
    diagnostics.record_event_loop_lag(25.0)
    diagnostics.record_event_loop_lag(30.0)
    diagnostics._gc_callback("start", {"generation": 0})
    time.sleep(0.001)
    diagnostics._gc_callback("stop", {"generation": 0, "collected": 0, "uncollectable": 0})
    diagnostics._gc_callback("start", {"generation": 0})
    time.sleep(0.001)
    diagnostics._gc_callback("stop", {"generation": 0, "collected": 0, "uncollectable": 0})
    messages = [r.getMessage() for r in caplog.records]
    assert sum("event_loop_lag" in m for m in messages) == 1
    assert sum("gc_pause" in m for m in messages) == 1
    snapshot = diagnostics.snapshot()
    assert snapshot["event_loop"]["suppressed_log_count"] >= 1
    assert snapshot["gc"]["suppressed_log_count"] >= 1
