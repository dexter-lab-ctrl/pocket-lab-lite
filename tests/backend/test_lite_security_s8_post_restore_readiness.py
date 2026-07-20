from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "lib" / "long_gate_s8.py"
spec = importlib.util.spec_from_file_location("long_gate_s8_readiness", MODULE_PATH)
assert spec and spec.loader
long_gate_s8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_gate_s8)


class ReadyApi:
    timeout = 10.0

    def __init__(self) -> None:
        self.summary_reads = 0
        self.progress_reads = 0

    def get(self, path: str):
        if path == "/api/lite/recovery/database":
            return {
                "restore_guard": {"unresolved": False, "rollback_failed": False},
                "maintenance": {"active": False, "state": "ready"},
            }
        if path == "/health":
            return {"status": "healthy"}
        if path == "/api/lite/status":
            return {"status": "healthy"}
        if path == "/api/lite/security/summary":
            self.summary_reads += 1
            if self.summary_reads == 1:
                raise long_gate_s8.ApiTransportError(
                    "GET", path, "TimeoutError", elapsed_seconds=10.01
                )
            return {"status": "healthy", "last_run": {"run_id": "restored-run"}}
        if path == "/api/lite/security/progress":
            self.progress_reads += 1
            return {
                "status": "succeeded",
                "run_id": "restored-run",
                "active_scan": False,
                "read_degraded": False,
                "sqlite_revision": 42,
            }
        if path == "/api/lite/security/history?limit=2":
            return {"history": [{"run_id": "restored-run"}]}
        raise AssertionError(path)


def test_post_restore_readiness_recovers_one_summary_timeout(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = ReadyApi()

    result = long_gate_s8.wait_post_restore_readiness(
        api, timeout=5.0, interval=0.0, required_consecutive=2
    )

    assert result["run_id"] == "restored-run"
    assert result["consecutive_passes"] == 2
    assert result["attempts"] == 3
    assert result["transient_transport_failures"] == [
        {
            "method": "GET",
            "path": "/api/lite/security/summary",
            "error_type": "TimeoutError",
            "elapsed_seconds": 10.01,
        }
    ]


def test_post_restore_readiness_fails_closed_on_unresolved_guard(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = ReadyApi()
    original = api.get

    def get(path: str):
        if path == "/api/lite/recovery/database":
            return {
                "restore_guard": {"unresolved": True, "rollback_failed": False},
                "maintenance": {"active": False},
            }
        return original(path)

    api.get = get

    with pytest.raises(long_gate_s8.GateError, match="unresolved restore guard"):
        long_gate_s8.wait_post_restore_readiness(api, timeout=5.0, interval=0.0)


def test_post_restore_readiness_fails_closed_on_run_identity_mismatch(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = ReadyApi()
    api.summary_reads = 1
    original = api.get

    def get(path: str):
        if path == "/api/lite/security/summary":
            return {"status": "healthy", "last_run": {"run_id": "summary-run"}}
        if path == "/api/lite/security/progress":
            return {
                "status": "succeeded",
                "run_id": "progress-run",
                "active_scan": False,
                "read_degraded": False,
            }
        return original(path)

    api.get = get

    with pytest.raises(long_gate_s8.GateError, match="run identities disagree"):
        long_gate_s8.wait_post_restore_readiness(api, timeout=5.0, interval=0.0)


def test_transport_error_includes_elapsed_seconds():
    error = long_gate_s8.ApiTransportError(
        "GET", "/api/lite/security/summary", "TimeoutError", elapsed_seconds=10.012
    )

    assert "elapsed_seconds=10.01" in str(error)
