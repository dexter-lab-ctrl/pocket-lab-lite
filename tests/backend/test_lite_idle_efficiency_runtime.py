from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def test_idle_governor_uses_sustained_pressure_and_bounded_duty_cycle(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import idle_efficiency

    governor = idle_efficiency.IdleEfficiencyGovernor()
    governor.cpu_warning_percent = 10.0
    governor.cpu_critical_percent = 20.0
    governor._last_wall = 100.0
    governor._last_cpu = 10.0

    wall = iter((105.0, 110.0, 115.0))
    cpu = iter((12.0, 14.0, 16.0))
    monkeypatch.setattr(idle_efficiency.time, "monotonic", lambda: next(wall))
    monkeypatch.setattr(idle_efficiency.time, "process_time", lambda: next(cpu))
    monkeypatch.setattr(idle_efficiency.os, "getloadavg", lambda: (0.0, 0.0, 0.0))
    monkeypatch.setattr(idle_efficiency, "_memory_available_percent", lambda: 80.0)
    monkeypatch.setattr(
        idle_efficiency.RUNTIME_DIAGNOSTICS, "latest_event_loop_lag_ms", lambda: 0.0
    )

    governor.sample_now()
    assert governor.pressure_reason() == ""
    governor.sample_now()
    assert governor.pressure_reason() == "process_cpu_budget"
    snapshot = governor.sample_now()
    assert snapshot["status"] == "critical"
    assert snapshot["sanitized"] is True
    assert 0.0 < governor.optional_cooldown_seconds(1_000) <= 30.0


def test_projection_scheduler_skips_unchanged_sqlite_projection(tmp_path, monkeypatch):
    ensure_runtime_path()
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    db_path = state / "pocketlab.sqlite3"
    db_path.touch()
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(db_path))
    monkeypatch.setenv("POCKETLAB_LITE_PROJECTION_IO_WORKERS", "1")
    monkeypatch.setenv("POCKETLAB_LITE_PROJECTION_CPU_WORKERS", "1")

    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    reset_sqlite_path_cache()
    scheduler = ProjectionScheduler()
    builds = 0
    commits = 0
    unchanged = 0

    def builder():
        nonlocal builds
        builds += 1
        return {"stable": True, "nested": {"value": 1}}

    def projector(_payload):
        nonlocal commits
        commits += 1
        return commits

    def on_unchanged():
        nonlocal unchanged
        unchanged += 1

    job = ProjectionJob(
        "apps.lifecycle",
        builder,
        projector,
        20,
        "io",
        2.0,
        on_unchanged=on_unchanged,
    )
    scheduler.mark_dirty("apps.lifecycle", job=job)
    assert _wait_for(lambda: scheduler.status("apps.lifecycle").get("committed_count") == 1)
    scheduler.mark_dirty("apps.lifecycle")
    assert _wait_for(lambda: scheduler.status("apps.lifecycle").get("unchanged_count") == 1)

    status = scheduler.status("apps.lifecycle")
    assert builds == 2
    assert commits == 1
    assert unchanged == 1
    assert status["execution_count"] == 2
    assert status["committed_count"] == 1
    scheduler.shutdown(drain_seconds=1.0)


def test_projection_scheduler_event_prefix_is_single_flight(tmp_path, monkeypatch):
    ensure_runtime_path()
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    db_path = state / "pocketlab.sqlite3"
    db_path.touch()
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(db_path))
    monkeypatch.setenv("POCKETLAB_LITE_PROJECTION_IO_WORKERS", "1")

    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler

    reset_sqlite_path_cache()
    scheduler = ProjectionScheduler()
    calls: list[str] = []
    for domain in ("fleet.summary", "fleet.device-health"):
        scheduler.register(ProjectionJob(
            domain,
            lambda name=domain: calls.append(name) or {"domain": name},
            lambda _payload: 1,
            20,
            "io",
            2.0,
        ))

    assert scheduler.mark_registered_prefix_dirty("fleet") == 2
    for _ in range(50):
        scheduler.mark_registered_prefix_dirty("fleet")
    assert _wait_for(lambda: all(
        scheduler.status(domain).get("committed_generation")
        == scheduler.status(domain).get("generation")
        for domain in ("fleet.summary", "fleet.device-health")
    ))
    assert scheduler.diagnostics()["event_signal_count"] >= 102
    assert set(calls) == {"fleet.summary", "fleet.device-health"}
    assert max(calls.count("fleet.summary"), calls.count("fleet.device-health")) <= 2
    scheduler.shutdown(drain_seconds=1.0)


def test_scheduler_diagnostics_sqlite_write_is_change_only(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import projection_scheduler

    scheduler = projection_scheduler.ProjectionScheduler()
    state = projection_scheduler._DomainState(generation=1, dirty=True)
    submissions: list[str] = []

    def submit(operation, callback, *, deadline_seconds):
        submissions.append(operation)
        return None

    monkeypatch.setattr(projection_scheduler.SQLITE_WRITER, "submit", submit)
    scheduler._persist_state_best_effort("fleet.summary", state)
    scheduler._persist_state_best_effort("fleet.summary", state)
    assert submissions == ["projection.scheduler.state"]


def test_live_status_uses_one_interruptible_coordinator_and_change_only_publish(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import live_status

    sampler = live_status.LiveStatusSampler(
        telemetry_interval=300.0,
        health_interval=300.0,
        fleet_interval=300.0,
        telemetry_idle_interval=600.0,
        health_idle_interval=600.0,
        fleet_idle_interval=600.0,
    )
    publish = AsyncMock(return_value=True)
    monkeypatch.setattr(live_status.BUS, "publish_json", publish)

    async def fake_telemetry(*, source="manual"):
        sampler._last_changed["telemetry"] = False
        sampler._samples["telemetry"] += 1
        return {"source": source}

    async def fake_health(*, source="manual"):
        sampler._last_changed["health"] = False
        sampler._samples["health"] += 1
        return {"source": source}

    async def fake_fleet(*, source="manual"):
        sampler._last_changed["fleet"] = False
        sampler._samples["fleet"] += 1
        return {"source": source}

    monkeypatch.setattr(sampler, "sample_telemetry", fake_telemetry)
    monkeypatch.setattr(sampler, "sample_health", fake_health)
    monkeypatch.setattr(sampler, "sample_fleet", fake_fleet)

    async def exercise():
        await sampler.start()
        assert len(sampler._tasks) == 1
        sampler.request_sample("telemetry", "health", "fleet", reason="test_event")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and sum(sampler._samples.values()) < 3:
            await asyncio.sleep(0.01)
        status = sampler.status()
        await sampler.stop()
        return status

    status = asyncio.run(exercise())
    assert sum(status["samples"].values()) >= 3
    assert status["mode"] == "consolidated_adaptive"
    assert status["event_wakeups"] >= 1
    assert status["last_event_reason"] == "test_event"
    assert status["sanitized"] is True


def test_security_prepared_progress_carries_domain_revision():
    ensure_runtime_path()
    from api_fastapi.services import lite_security

    prepared = lite_security._prepare_security_progress(
        {
            "status": "idle",
            "sqlite_revision": 73,
            "projection_epoch": 4,
            "active_scan": False,
            "projection_age_ms": 0.0,
        },
        identity=("idle", 73),
        database_identity="database-a",
        encoded_at_monotonic=1.0,
    )
    assert prepared.domain_revision == 73
    assert prepared.projection_epoch == 4
