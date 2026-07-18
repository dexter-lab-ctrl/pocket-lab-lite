from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "lib" / "long_gate_s8.py"
spec = importlib.util.spec_from_file_location("long_gate_s8_idle_reconciliation", MODULE_PATH)
assert spec and spec.loader
long_gate_s8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_gate_s8)


class FakeApi:
    timeout = 10.0

    def __init__(self, summary: dict, history: dict | None = None) -> None:
        self.summary = summary
        self.history = history or {"history": []}

    def get(self, path: str):
        if path == "/api/lite/security/progress":
            return {
                "active_scan": True,
                "run_id": "completed-run",
                "requested_at_epoch_ms": 2000,
                "profile": "quick",
                "status": "accepted",
            }
        if path == "/api/lite/security/summary":
            return self.summary
        assert path == "/api/lite/security/history?limit=20"
        return self.history


def test_wait_security_idle_reconciles_exact_terminal_run_from_summary(monkeypatch):
    api = FakeApi(
        {
            "last_run": {
                "run_id": "completed-run",
                "requested_at_epoch_ms": 2000,
                "scan_profile": "quick",
                "status": "succeeded",
                "percent": 100,
            },
            "history": [],
        }
    )
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)

    result = long_gate_s8.wait_security_idle(api, timeout=5.0)

    assert result["run_id"] == "completed-run"
    assert result["status"] == "succeeded"
    assert result["active_scan"] is False
    assert result["idle_reconciled"] is True
    assert result["stale_progress_status"] == "accepted"


def test_wait_security_idle_does_not_mask_newer_nonterminal_run(monkeypatch):
    api = FakeApi(
        {
            "last_run": {
                "run_id": "completed-run",
                "requested_at_epoch_ms": 2000,
                "scan_profile": "quick",
                "status": "succeeded",
                "percent": 100,
            },
            "history": [
                {
                    "run_id": "newer-run",
                    "requested_at_epoch_ms": 3000,
                    "scan_profile": "quick",
                    "status": "running",
                    "percent": 20,
                }
            ],
        }
    )
    monkeypatch.setenv("POCKETLAB_S8_GATE_SECURITY_IDLE_TIMEOUT", "15")
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)

    try:
        long_gate_s8.wait_security_idle(api, timeout=0.01)
    except long_gate_s8.GateError as exc:
        assert "Security scan idle precondition" in str(exc)
    else:
        raise AssertionError("expected GateError")


def test_wait_security_idle_prefers_persisted_terminal_over_newer_stale_progress(monkeypatch):
    api = FakeApi(
        {"last_run": {}, "history": []},
        history={
            "history": [
                {
                    "run_id": "completed-run",
                    "requested_at_epoch_ms": 2000,
                    "scan_profile": "quick",
                    "status": "succeeded",
                    "percent": 100,
                }
            ]
        },
    )
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)

    result = long_gate_s8.wait_security_idle(api, timeout=5.0)

    assert result["run_id"] == "completed-run"
    assert result["status"] == "succeeded"
    assert result["idle_reconciled"] is True


def test_scan_candidate_terminal_precedence_is_run_scoped():
    accepted = {
        "run_id": "same-run",
        "status": "accepted",
        "requested_at_epoch_ms": 9000,
    }
    succeeded = {
        "run_id": "same-run",
        "status": "succeeded",
        "requested_at_epoch_ms": 2000,
    }

    assert long_gate_s8._prefer_scan_candidate(accepted, succeeded) is True
    assert long_gate_s8._prefer_scan_candidate(succeeded, accepted) is False
