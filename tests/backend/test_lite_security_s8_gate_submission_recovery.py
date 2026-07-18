from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "lib" / "long_gate_s8.py"
spec = importlib.util.spec_from_file_location("long_gate_s8", MODULE_PATH)
assert spec and spec.loader
long_gate_s8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_gate_s8)


class FakeApi:
    timeout = 10.0

    def __init__(self, *, timeout_on_post: bool = True) -> None:
        self.timeout_on_post = timeout_on_post
        self.post_calls = 0
        self.progress_reads = 0

    def get(self, path: str):
        assert path == "/api/lite/security/progress"
        self.progress_reads += 1
        if self.progress_reads == 1:
            return {
                "active_scan": False,
                "run_id": "old-run",
                "requested_at_epoch_ms": 1000,
                "profile": "quick",
                "status": "succeeded",
            }
        if self.progress_reads == 2:
            return {
                "active_scan": True,
                "run_id": "new-run",
                "requested_at_epoch_ms": 9_999_999_999_999,
                "profile": "quick",
                "status": "running",
            }
        return {
            "active_scan": False,
            "run_id": "new-run",
            "requested_at_epoch_ms": 9_999_999_999_999,
            "profile": "quick",
            "status": "succeeded",
            "percent": 100,
        }

    def post(self, path: str, payload: dict):
        assert path == "/api/lite/security/check"
        assert payload == {"profile": "quick"}
        self.post_calls += 1
        if self.timeout_on_post:
            raise long_gate_s8.ApiTransportError("POST", path, "TimeoutError")
        return {"run_id": "new-run"}


def test_quick_scan_adopts_new_run_after_submission_timeout(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = FakeApi(timeout_on_post=True)

    result = long_gate_s8.run_quick_scan(api, timeout=5.0)

    assert result == {
        "run_id": "new-run",
        "status": "succeeded",
        "percent": 100,
        "submission_recovered": True,
    }
    assert api.post_calls == 1


def test_quick_scan_keeps_normal_submission_path(monkeypatch):
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)
    api = FakeApi(timeout_on_post=False)

    result = long_gate_s8.run_quick_scan(api, timeout=5.0)

    assert result["run_id"] == "new-run"
    assert result["submission_recovered"] is False
    assert api.post_calls == 1


def test_quick_scan_fails_closed_when_scan_already_active():
    api = FakeApi(timeout_on_post=False)

    def active(_path: str):
        return {"active_scan": True, "run_id": "existing", "profile": "quick"}

    api.get = active

    try:
        long_gate_s8.run_quick_scan(api, timeout=5.0)
    except long_gate_s8.GateError as exc:
        assert "another scan is active" in str(exc)
    else:
        raise AssertionError("expected GateError")

    assert api.post_calls == 0
