from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/lib/long_gate_group2.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group2_progress", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_latency_summary_has_p50_p95_and_max():
    tool = load_tool()
    summary = tool.latency_summary([0.1, 0.2, 0.3, 0.4, 1.0])
    assert summary == {"count": 5, "p50": 0.3, "p95": 1.0, "max": 1.0}


def test_direct_proxy_consistency_allows_bounded_terminal_race():
    tool = load_tool()
    ok, reason = tool.direct_proxy_consistent(
        {"run_id": "run-1", "status": "succeeded"},
        {"run_id": "run-1", "status": "running"},
        target_run_id="run-1",
    )
    assert ok is True
    assert reason == "bounded_terminal_race"


def test_direct_proxy_mismatch_is_detected():
    tool = load_tool()
    ok, reason = tool.direct_proxy_consistent(
        {"run_id": "run-1", "status": "running"},
        {"run_id": "run-2", "status": "running"},
        target_run_id="run-1",
    )
    assert ok is False
    assert "different runs" in reason


def test_unsafe_progress_cadence_is_rejected():
    tool = load_tool()
    parser = tool.build_parser()
    args = parser.parse_args([
        "progress-soak", "--repo-root", str(ROOT), "--run-dir", "/x", "--run-id", "pocketlab-long-gates-test", "--gate-id", "progress-soak",
        "--state-dir", "/x/state", "--db-path", "/x/db", "--proxy-base-url", "http://127.0.0.1:1", "--direct-base-url", "http://127.0.0.1:2",
        "--scan-count", "1", "--sample-interval-ms", "100", "--run-timeout-seconds", "10", "--submission-timeout-seconds", "2",
        "--etag-check-every", "2", "--max-projection-age-ms", "5000", "--p95-budget-seconds", "1", "--max-budget-seconds", "3",
    ])
    try:
        tool.validate_args(args)
    except ValueError as exc:
        assert "at least 200" in str(exc)
    else:
        raise AssertionError("unsafe cadence was accepted")


def test_etag_304_and_changed_200_are_valid():
    tool = load_tool()
    class FakeClient:
        def __init__(self, result): self.result = result
        def request(self, *args, **kwargs): return self.result
    prior = {"revision": 1, "percent": 10, "status": "running"}
    not_modified = tool.HttpResult(tool.utc_now(), 304, True, "", 0.01, 0.01, 0.01, '"a"', None, 0)
    check = tool.etag_check(FakeClient(not_modified), "http://x", '"a"', prior, "direct")
    assert check["valid"] is True
    changed = tool.HttpResult(tool.utc_now(), 200, True, "", 0.01, 0.01, 0.01, '"b"', {"revision": 2, "percent": 11, "status": "running"}, 10)
    check = tool.etag_check(FakeClient(changed), "http://x", '"a"', prior, "proxy")
    assert check["valid"] is True
    assert check["behavior"] == "changed"


def test_etag_same_body_200_is_invalid():
    tool = load_tool()
    class FakeClient:
        def request(self, *args, **kwargs):
            return tool.HttpResult(tool.utc_now(), 200, True, "", 0.01, 0.01, 0.01, '"a"', {"revision": 1, "percent": 10, "status": "running"}, 10)
    check = tool.etag_check(FakeClient(), "http://x", '"a"', {"revision": 1, "percent": 10, "status": "running"}, "direct")
    assert check["valid"] is False
    assert check["behavior"] == "etag_not_honored"


def test_historical_warning_lag_does_not_count_as_critical():
    tool = load_tool()
    baseline = {"critical_count": 0, "critical_stack_capture_count": 0}
    result = tool.critical_event_loop_delta(
        {
            "critical_count": 0,
            "critical_stack_captures": [],
            "latest_lag_ms": 120.0,
            "recent_lag_events": [
                {"captured_at": "2026-07-16T08:59:24Z", "lag_ms": 1641, "severity": "warning"},
            ],
        },
        baseline,
        gate_started_at="2026-07-16T09:27:00Z",
        critical_threshold_ms=1000,
    )
    assert result["critical"] is False


def test_new_critical_delta_or_stack_capture_fails():
    tool = load_tool()
    result = tool.critical_event_loop_delta(
        {
            "critical_count": 1,
            "critical_stack_captures": [{"captured_at": "2026-07-16T09:28:00Z"}],
            "latest_lag_ms": 50,
            "recent_lag_events": [],
        },
        {"critical_count": 0, "critical_stack_capture_count": 0},
        gate_started_at="2026-07-16T09:27:00Z",
        critical_threshold_ms=1000,
    )
    assert result["critical"] is True
    assert result["critical_count_delta"] == 1
    assert result["critical_stack_capture_delta"] == 1


def test_new_critical_event_after_gate_start_fails_but_old_event_does_not():
    tool = load_tool()
    result = tool.critical_event_loop_delta(
        {
            "critical_count": 0,
            "critical_stack_captures": [],
            "recent_lag_events": [
                {"captured_at": "2026-07-16T09:20:00Z", "severity": "critical", "lag_ms": 2000},
                {"captured_at": "2026-07-16T09:28:00Z", "severity": "critical", "lag_ms": 2000},
            ],
        },
        {"critical_count": 0, "critical_stack_capture_count": 0},
        gate_started_at="2026-07-16T09:27:00Z",
        critical_threshold_ms=1000,
    )
    assert result["critical"] is True
    assert result["new_critical_events"] == 1
