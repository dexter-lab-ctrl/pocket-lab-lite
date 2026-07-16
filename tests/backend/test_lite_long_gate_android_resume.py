from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/lib/long_gate_group4.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group4_android", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def isolate_state(tmp_path: Path):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    yield state


def test_frontend_report_analysis_detects_leaks_and_process_recreation():
    tool = load_tool()
    reports = [
        {"frontend_session_id": "a", "active_event_source_count": 1, "active_poll_timer_count": 0, "visibility_listener_count": 1, "online_listener_count": 1, "offline_listener_count": 1, "backend_reconciliation_count": 1},
        {"frontend_session_id": "b", "active_event_source_count": 0, "active_poll_timer_count": 1, "visibility_listener_count": 1, "online_listener_count": 1, "offline_listener_count": 1, "backend_reconciliation_count": 2, "write_actions_blocked": True},
    ]
    summary = tool.analyze_frontend_reports(reports)
    assert summary["process_recreated"] is True
    assert summary["simultaneous_sse_and_polling"] is False
    assert summary["event_source_leak"] is False
    assert summary["timer_leak"] is False
    assert summary["listener_leak"] is False
    assert summary["backend_state_reconciled"] is True
    assert summary["write_actions_blocked_while_stale"] is True


def test_lifecycle_diagnostics_are_inert_without_activation():
    challenge = client().get("/api/lite/diagnostics/frontend-lifecycle/challenge")
    assert challenge.status_code == 200
    assert challenge.json()["active"] is False
    record = client().post(
        "/api/lite/diagnostics/frontend-lifecycle",
        json={"challenge_id": "not-active", "report": {"frontend_session_id": "session"}},
    )
    assert record.status_code == 200
    assert record.json()["accepted"] is False


def test_lifecycle_report_is_allowlisted_and_sanitized(isolate_state: Path):
    from api_fastapi.services import lite_lifecycle_diagnostics, lite_security_evidence

    challenge_id = "phase5-android-challenge-1234"
    lite_security_evidence.write_json(
        lite_lifecycle_diagnostics.activation_path(),
        {"challenge_id": challenge_id, "expires_at_epoch": 4102444800, "sanitized": True},
    )
    lite_lifecycle_diagnostics.activation_path().chmod(0o600)
    response = client().post(
        "/api/lite/diagnostics/frontend-lifecycle",
        json={
            "challenge_id": challenge_id,
            "report": {
                "frontend_session_id": "session-a",
                "active_event_source_count": 1,
                "authorization": "Bearer must-not-appear",
                "backend_run_id": "run-1",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is True
    reports = list(lite_lifecycle_diagnostics.reports_dir().glob(f"{challenge_id}-*.json"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "authorization" not in text.lower()
    assert "must-not-appear" not in text
