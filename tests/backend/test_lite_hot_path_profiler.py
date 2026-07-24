from __future__ import annotations

import time

from api_fastapi.services.hot_path_profiler import HotPathProfiler


def test_hot_path_profiler_attributes_cpu_and_wall_time(monkeypatch):
    monkeypatch.setenv("POCKETLAB_HOT_PATH_PERSIST_EVERY_RUNS", "128")
    profiler = HotPathProfiler()
    with profiler.measure("system.fleet_probe") as outcome:
        sum(index * index for index in range(10_000))
        time.sleep(0.002)
        outcome["changed"] = False
    row = profiler.snapshot()["jobs"][0]
    assert row["job"] == "system.fleet_probe"
    assert row["runs"] == 1
    assert row["cpu_ms_total"] >= 0
    assert row["wall_ms_total"] >= 1
    assert row["unchanged_commits"] == 1
    assert row["sanitized"] if "sanitized" in row else True


def test_hot_path_profiler_bounds_names_and_cardinality(monkeypatch):
    monkeypatch.setenv("POCKETLAB_HOT_PATH_MAX_JOBS", "16")
    monkeypatch.setenv("POCKETLAB_HOT_PATH_PERSIST_EVERY_RUNS", "128")
    profiler = HotPathProfiler()
    for index in range(24):
        profiler.record(f"job/{index}/secret value", wall_ms=1, cpu_ms=1)
    snapshot = profiler.snapshot()
    assert snapshot["job_count"] == 16
    assert snapshot["evictions"] == 8
    assert all(" " not in row["job"] and "/" not in row["job"] for row in snapshot["jobs"])


def test_hot_path_profiler_records_failures_without_payloads(monkeypatch):
    monkeypatch.setenv("POCKETLAB_HOT_PATH_PERSIST_EVERY_RUNS", "128")
    profiler = HotPathProfiler()
    try:
        with profiler.measure("projection.fleet"):
            raise RuntimeError("secret-token-should-not-appear")
    except RuntimeError:
        pass
    row = profiler.snapshot()["jobs"][0]
    assert row["failures"] == 1
    assert row["last_error_type"] == "RuntimeError"
    assert "secret-token" not in str(row)
