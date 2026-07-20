from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "lib" / "long_gate_s8.py"
spec = importlib.util.spec_from_file_location("long_gate_s8_get_retry", MODULE_PATH)
assert spec and spec.loader
long_gate_s8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_gate_s8)


def test_get_retries_one_transient_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    api = long_gate_s8.Api("http://127.0.0.1:8443", 5.0)
    api.get_retry_attempts = 3
    api.get_retry_delay_seconds = 0.05
    calls = 0

    def request(method: str, path: str, payload=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise long_gate_s8.ApiTransportError(
                method,
                path,
                "TimeoutError",
                elapsed_seconds=5.01,
            )
        return {"status": "ready"}

    monkeypatch.setattr(api, "request", request)
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)

    assert api.get("/api/lite/recovery/maintenance") == {"status": "ready"}
    assert calls == 2
    diagnostics = api.transport_retry_snapshot()
    assert diagnostics["recovered_transport_failure_count"] == 1
    assert diagnostics["recovered_transport_failures"][0] == {
        "method": "GET",
        "path": "/api/lite/recovery/maintenance",
        "error_type": "TimeoutError",
        "elapsed_seconds": 5.01,
        "attempt": 1,
        "sanitized": True,
    }


def test_get_does_not_retry_application_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    api = long_gate_s8.Api("http://127.0.0.1:8443", 5.0)
    api.get_retry_attempts = 3
    calls = 0

    def request(method: str, path: str, payload=None):
        nonlocal calls
        calls += 1
        raise long_gate_s8.GateError("GET returned HTTP 500")

    monkeypatch.setattr(api, "request", request)

    with pytest.raises(long_gate_s8.GateError, match="HTTP 500"):
        api.get("/api/lite/recovery/maintenance")
    assert calls == 1


def test_get_exhaustion_preserves_final_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    api = long_gate_s8.Api("http://127.0.0.1:8443", 5.0)
    api.get_retry_attempts = 2
    api.get_retry_delay_seconds = 0.05
    calls = 0

    def request(method: str, path: str, payload=None):
        nonlocal calls
        calls += 1
        raise long_gate_s8.ApiTransportError(
            method,
            path,
            "ConnectionResetError",
            elapsed_seconds=0.25,
        )

    monkeypatch.setattr(api, "request", request)
    monkeypatch.setattr(long_gate_s8.time, "sleep", lambda _seconds: None)

    with pytest.raises(long_gate_s8.ApiTransportError, match="ConnectionResetError"):
        api.get("/health")
    assert calls == 2
    assert api.transport_retry_snapshot()["recovered_transport_failure_count"] == 1


def test_post_is_never_implicitly_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    api = long_gate_s8.Api("http://127.0.0.1:8443", 5.0)
    calls = 0

    def request(method: str, path: str, payload=None):
        nonlocal calls
        calls += 1
        raise long_gate_s8.ApiTransportError(
            method,
            path,
            "TimeoutError",
            elapsed_seconds=5.01,
        )

    monkeypatch.setattr(api, "request", request)

    with pytest.raises(long_gate_s8.ApiTransportError):
        api.post("/api/lite/recovery/maintenance/checkpoint", {"mode": "passive"})
    assert calls == 1
