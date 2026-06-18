# ruff: noqa: E402
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

RUNTIME_DIR = Path(__file__).resolve().parents[1]
for item in (str(RUNTIME_DIR),):
    if item not in sys.path:
        sys.path.insert(0, item)

os.environ.setdefault("POCKETLAB_API_TOKEN", "pocketlab-test-token")
os.environ.setdefault("POCKETLAB_ALLOW_LOCAL_WRITE", "1")
os.environ.setdefault("POCKETLAB_TEST_AUTH_BYPASS", "1")
os.environ.setdefault("POCKETLAB_NATS_REQUIRED", "0")

from api_fastapi.main import app
from api_fastapi.services import observability_status as status_service


def _probe(ok: bool = True, body: dict[str, Any] | str | None = None, *, code: int | None = 200, error: str = "") -> dict[str, Any]:
    if isinstance(body, dict):
        body_text = json.dumps(body)
    elif body is None:
        body_text = "OK" if ok else ""
    else:
        body_text = body
    return {
        "ok": ok,
        "status_code": code,
        "latency_ms": 7,
        "body": body_text,
        "truncated": False,
        "error": error,
    }


def _client() -> TestClient:
    return TestClient(
        app,
        headers={
            "Authorization": "Bearer pocketlab-test-token",
            "X-Pocket-Lab-Token": "pocketlab-test-token",
            "X-Pocket-Lab-Test": "1",
        },
    )


def _healthy_http_get(url: str, *, timeout: float) -> dict[str, Any]:
    if url.endswith("/api/v1/targets"):
        return _probe(
            body={
                "status": "success",
                "data": {
                    "activeTargets": [
                        {"health": "up", "labels": {"job": "fastapi", "instance": "127.0.0.1:8000"}},
                        {"health": "up", "labels": {"job": "nats", "instance": "127.0.0.1:8222"}},
                    ]
                },
            }
        )
    if "/query_range" in url:
        return _probe(body={"status": "success", "data": {"result": [{"values": [["1", "log one"], ["2", "log two"]]}]}})
    if url.endswith("/api/health"):
        return _probe(body={"database": "ok", "version": "test"})
    return _probe()


def test_all_observability_probes_healthy(monkeypatch) -> None:
    status_service.clear_observability_status_cache()
    monkeypatch.setattr(status_service, "_http_get", _healthy_http_get)

    snapshot = status_service.build_observability_status_snapshot(use_cache=False)

    assert snapshot["status"] == "healthy"
    assert snapshot["services"]["prometheus"]["ready"] is True
    assert snapshot["services"]["loki"]["ready"] is True
    assert snapshot["services"]["grafana"]["healthy"] is True
    assert snapshot["services"]["gatus"]["ready"] is True
    assert snapshot["services"]["promtail"]["shipping_logs"] is True
    assert snapshot["services"]["promtail"]["inferred"] is True
    assert snapshot["prometheus_targets"]["up"] == 2
    assert snapshot["prometheus_targets"]["down"] == 0


def test_one_probe_unavailable_degrades_without_crashing(monkeypatch) -> None:
    status_service.clear_observability_status_cache()

    def fake_http_get(url: str, *, timeout: float) -> dict[str, Any]:
        if url.endswith("/-/ready"):
            return _probe(False, code=None, error="connection refused")
        return _healthy_http_get(url, timeout=timeout)

    monkeypatch.setattr(status_service, "_http_get", fake_http_get)
    snapshot = status_service.build_observability_status_snapshot(use_cache=False)

    assert snapshot["status"] == "degraded"
    assert snapshot["services"]["prometheus"]["status"] == "unavailable"
    assert "connection refused" in snapshot["services"]["prometheus"]["reason"]


def test_timeout_handling_is_bounded(monkeypatch) -> None:
    status_service.clear_observability_status_cache()

    def fake_http_get(url: str, *, timeout: float) -> dict[str, Any]:
        return _probe(False, code=None, error="timed out")

    monkeypatch.setattr(status_service, "_http_get", fake_http_get)
    snapshot = status_service.build_observability_status_snapshot(use_cache=False)

    assert snapshot["status"] == "unavailable"
    assert all(service["status"] in {"unavailable", "unknown"} for service in snapshot["services"].values())


def test_prometheus_targets_up_down_summary(monkeypatch) -> None:
    status_service.clear_observability_status_cache()

    def fake_http_get(url: str, *, timeout: float) -> dict[str, Any]:
        if url.endswith("/api/v1/targets"):
            return _probe(
                body={
                    "status": "success",
                    "data": {
                        "activeTargets": [
                            {"health": "up", "labels": {"job": "api", "instance": "127.0.0.1:8000"}},
                            {"health": "down", "labels": {"job": "worker", "instance": "127.0.0.1:9000"}, "lastError": "scrape failed"},
                        ]
                    },
                }
            )
        return _healthy_http_get(url, timeout=timeout)

    monkeypatch.setattr(status_service, "_http_get", fake_http_get)
    snapshot = status_service.build_observability_status_snapshot(use_cache=False)

    assert snapshot["prometheus_targets"]["status"] == "degraded"
    assert snapshot["prometheus_targets"]["up"] == 1
    assert snapshot["prometheus_targets"]["down"] == 1
    assert snapshot["prometheus_targets"]["down_targets"][0]["job"] == "worker"


def test_prometheus_targets_endpoint_unavailable(monkeypatch) -> None:
    status_service.clear_observability_status_cache()

    def fake_http_get(url: str, *, timeout: float) -> dict[str, Any]:
        if url.endswith("/api/v1/targets"):
            return _probe(False, code=503, error="service unavailable")
        return _healthy_http_get(url, timeout=timeout)

    monkeypatch.setattr(status_service, "_http_get", fake_http_get)
    snapshot = status_service.build_observability_status_snapshot(use_cache=False)

    assert snapshot["prometheus_targets"]["status"] == "unavailable"
    assert snapshot["prometheus_targets"]["total"] == 0


def test_promtail_degraded_when_no_recent_loki_logs(monkeypatch) -> None:
    status_service.clear_observability_status_cache()

    def fake_http_get(url: str, *, timeout: float) -> dict[str, Any]:
        if "/query_range" in url:
            return _probe(body={"status": "success", "data": {"result": []}})
        return _healthy_http_get(url, timeout=timeout)

    monkeypatch.setattr(status_service, "_http_get", fake_http_get)
    snapshot = status_service.build_observability_status_snapshot(use_cache=False)

    assert snapshot["services"]["promtail"]["status"] == "degraded"
    assert snapshot["services"]["promtail"]["shipping_logs"] is False
    assert snapshot["services"]["promtail"]["inferred"] is True


def test_loki_query_failure_does_not_crash_endpoint(monkeypatch) -> None:
    status_service.clear_observability_status_cache()

    def fake_http_get(url: str, *, timeout: float) -> dict[str, Any]:
        if "/query_range" in url:
            return _probe(False, code=500, error="bad loki query")
        return _healthy_http_get(url, timeout=timeout)

    monkeypatch.setattr(status_service, "_http_get", fake_http_get)
    response = _client().get("/api/observability/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["services"]["promtail"]["status"] == "unknown"
    assert payload["status"] == "degraded"


def test_cache_behavior(monkeypatch) -> None:
    status_service.clear_observability_status_cache()
    calls = {"count": 0}

    def fake_http_get(url: str, *, timeout: float) -> dict[str, Any]:
        calls["count"] += 1
        return _healthy_http_get(url, timeout=timeout)

    monkeypatch.setattr(status_service, "_http_get", fake_http_get)
    first = status_service.build_observability_status_snapshot(use_cache=True)
    second = status_service.build_observability_status_snapshot(use_cache=True)

    assert first["cached"] is False
    assert second["cached"] is True
    assert calls["count"] == 6


def test_no_secrets_exposed_in_response(monkeypatch) -> None:
    status_service.clear_observability_status_cache()
    monkeypatch.setenv("POCKETLAB_GRAFANA_URL", "http://admin:super-secret@127.0.0.1:3050")
    monkeypatch.setattr(status_service, "_http_get", _healthy_http_get)

    payload = status_service.build_observability_status_snapshot(use_cache=False)
    encoded = json.dumps(payload)

    assert "super-secret" not in encoded
    assert "admin:super-secret" not in encoded
    assert "127.0.0.1:3050/api/health" in encoded
