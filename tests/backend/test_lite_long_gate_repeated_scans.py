from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/lib/long_gate_group2.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group2_repeated", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resume_tracks_existing_active_run_without_resubmission():
    tool = load_tool()
    state = {"tracked_run_id": "run-1", "submission_started": True}
    assert tool.resume_scan_decision(state, {"run_id": "run-1", "status": "running"}) == "monitor"
    assert tool.resume_scan_decision(state, {"run_id": "run-1", "status": "succeeded"}) == "finalize"


def test_resume_fails_closed_on_ambiguous_submission():
    tool = load_tool()
    assert tool.resume_scan_decision({"tracked_run_id": "", "submission_started": True}, {}) == "ambiguous"
    assert tool.resume_scan_decision({"tracked_run_id": "run-1", "submission_started": True}, {"run_id": "run-2", "status": "running"}) == "ambiguous"


def test_sequential_submission_allowed_only_without_prior_submission():
    tool = load_tool()
    assert tool.resume_scan_decision({"tracked_run_id": "", "submission_started": False}, {}) == "submit"


def test_progress_regression_is_run_scoped():
    tool = load_tool()
    samples = [
        {"run_id": "a", "percent": 10, "revision": 1},
        {"run_id": "b", "percent": 5, "revision": 1},
        {"run_id": "a", "percent": 9, "revision": 2},
    ]
    regressions = tool.progress_regressions(samples)
    assert len(regressions) == 1
    assert regressions[0]["run_id"] == "a"
    assert regressions[0]["field"] == "percent"


def test_finding_result_is_distinct_from_infrastructure_failure():
    tool = load_tool()
    assert "degraded" in tool.TERMINAL_SUCCESS_STATUSES
    assert "failed" in tool.TERMINAL_FAILURE_STATUSES


def test_late_run_latency_trend_detects_material_degradation():
    tool = load_tool()
    trend = tool.compare_latency_groups([10, 11, 12, 50, 55, 60], ratio_budget=2, absolute_budget=20)
    assert trend["status"] == "failed"
    stable = tool.compare_latency_groups([10, 11, 12, 13, 14, 15], ratio_budget=2, absolute_budget=20)
    assert stable["status"] == "passed"
