from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/lib/long_gate_group2.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group2_idle", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_idle_trend_ignores_warmup_and_transient_spike():
    tool = load_tool()
    values = [10, 80, 12, 12, 13, 12, 14, 13, 12]
    trend = tool.evaluate_sustained_growth(values, warmup_samples=2, budget=10)
    assert trend["status"] == "passed"
    assert trend["sustained"] is False


def test_idle_trend_detects_sustained_growth():
    tool = load_tool()
    values = [5, 6, 10, 12, 18, 22, 30, 38, 45, 55, 65, 75]
    trend = tool.evaluate_sustained_growth(values, warmup_samples=2, budget=20)
    assert trend["status"] == "failed"
    assert trend["sustained"] is True


def test_optional_metric_unavailable_is_not_false_failure():
    tool = load_tool()
    trend = tool.evaluate_sustained_growth([None, None], warmup_samples=0, budget=1)
    assert trend["status"] == "unavailable"


def test_pm2_restart_and_exit_detection():
    tool = load_tool()
    before = {"processes": [{"name": "pocket-api", "status": "online", "restart_count": 1}, {"name": "pocket-worker", "status": "online", "restart_count": 2}]}
    after = {"processes": [{"name": "pocket-api", "status": "online", "restart_count": 2}, {"name": "pocket-worker", "status": "stopped", "restart_count": 2}]}
    restarts, exits = tool.compare_pm2(before, after)
    assert restarts == ["pocket-api"]
    assert exits == ["pocket-worker"]


def test_short_idle_simulation_uses_temp_state(monkeypatch, tmp_path: Path):
    tool = load_tool()
    samples = iter([
        {"timestamp": tool.utc_now(), "http": {"progress": {"ok": True, "time_total": 0.01}}, "resources": {"selected_rss_bytes": 100, "selected_cpu_percent": 0, "selected_fd_count": 5, "wal_bytes": 0, "log_bytes": 0}, "lifecycle": {"active_runs": []}, "durable_consumers_healthy": True, "sanitized": True},
        {"timestamp": tool.utc_now(), "http": {"progress": {"ok": True, "time_total": 0.01}}, "resources": {"selected_rss_bytes": 101, "selected_cpu_percent": 0, "selected_fd_count": 5, "wal_bytes": 0, "log_bytes": 0}, "lifecycle": {"active_runs": []}, "durable_consumers_healthy": True, "sanitized": True},
    ])
    monkeypatch.setattr(tool, "idle_light_sample", lambda *_: next(samples))
    monkeypatch.setattr(tool, "run_sqlite_tools", lambda *_: {"quick_check": "ok", "matched": True})
    monkeypatch.setattr(tool, "pm2_snapshot", lambda: {"available": False, "processes": []})
    monkeypatch.setattr(tool, "resource_snapshot", lambda **_: {"selected_rss_bytes": 101, "selected_cpu_percent": 0, "selected_fd_count": 5, "wal_bytes": 0, "log_bytes": 0, "db_bytes": 0, "evidence_bytes": 0})
    args = argparse.Namespace(
        repo_root=str(ROOT), run_dir=str(tmp_path / "run"), run_id="pocketlab-long-gates-idle-unit", gate_id="idle",
        state_dir=str(tmp_path / "state"), db_path=str(tmp_path / "state/db.sqlite3"), proxy_base_url="http://127.0.0.1:1", direct_base_url="http://127.0.0.1:2",
        connect_timeout=0.1, http_timeout=0.1, report_limit_bytes=5_000_000, resume=False,
        duration_seconds=1, sample_interval_seconds=1, heavy_check_interval_seconds=10, warmup_seconds=0,
        rss_budget_mb=1, wal_budget_mb=1, log_growth_budget_mb=1, fd_growth_budget=2, cpu_idle_threshold=20,
        cpu_growth_budget=10, stale_active_seconds=300, minimum_samples=1,
    )
    assert tool.run_idle(args) == 0
    result = json.loads((tmp_path / "run/gates/idle/result.json").read_text())
    assert result["status"] == "passed"
    assert result["samples_completed"] >= 1
    assert (tmp_path / "run/gates/idle/samples.jsonl").is_file()
