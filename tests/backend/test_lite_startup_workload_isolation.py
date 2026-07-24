from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "pocket-lab-final-structure" / "runtime"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


router_lite = importlib.import_module("api_fastapi.routers.lite")
security_store = importlib.import_module("api_fastapi.services.lite_security_store")


def test_startup_delay_bounds_invalid_and_extreme_values(monkeypatch):
    monkeypatch.setenv("POCKETLAB_TEST_DELAY", "not-a-number")
    assert router_lite._bounded_startup_delay("POCKETLAB_TEST_DELAY", 3.0, 1.0, 10.0) == 3.0
    monkeypatch.setenv("POCKETLAB_TEST_DELAY", "-20")
    assert router_lite._bounded_startup_delay("POCKETLAB_TEST_DELAY", 3.0, 1.0, 10.0) == 1.0
    monkeypatch.setenv("POCKETLAB_TEST_DELAY", "200")
    assert router_lite._bounded_startup_delay("POCKETLAB_TEST_DELAY", 3.0, 1.0, 10.0) == 10.0


def test_staged_startup_isolates_optional_stage_failures(monkeypatch):
    calls: list[str] = []

    class Security:
        @staticmethod
        def start_security_projection_runtime():
            calls.append("security")
            raise RuntimeError("optional stage failed")

    async def fake_health(*, skip_startup_delay=False):
        calls.append(f"health:{skip_startup_delay}")
        await asyncio.Event().wait()

    def fake_warmup():
        calls.append("warmup")
        return {"apps": True, "recovery_summary": True, "recovery_details": True}

    monkeypatch.setattr(router_lite, "_bounded_startup_delay", lambda *_args: 0.0)
    monkeypatch.setattr(router_lite, "device_health_projection_sweep_loop", fake_health)
    monkeypatch.setattr(router_lite, "schedule_control_plane_projection_warmup", fake_warmup)

    async def run():
        task = asyncio.create_task(router_lite.run_staged_startup_workloads(Security))
        for _ in range(100):
            if "warmup" in calls:
                break
            await asyncio.sleep(0.001)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    assert calls[:3] == ["security", "health:True", "warmup"]


def test_security_progress_reader_revision_read(tmp_path, monkeypatch):
    db_path = tmp_path / "progress.sqlite3"
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE domain_revisions(domain TEXT PRIMARY KEY, revision INTEGER, updated_at TEXT)")
        conn.execute("INSERT INTO domain_revisions(domain, revision, updated_at) VALUES('security', 7, 'now')")

    monkeypatch.setattr(security_store, "open_fast_read_connection", lambda timeout_ms=None: sqlite3.connect(db_path))
    # Match production row-name access.
    def connection(timeout_ms=None):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr(security_store, "open_fast_read_connection", connection)

    with security_store.SecurityProgressReader() as reader:
        revision, elapsed_ms = reader.read_revision()
    assert revision == 7
    assert elapsed_ms >= 0
