from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_supervisor_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "pocket-lab-final-structure" / "runtime" / "supervisors" / "pocketlab_core_supervisor.py"
    spec = importlib.util.spec_from_file_location("pocketlab_core_supervisor", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_nats_api_status_unhealthy_detects_flush_timeout():
    supervisor = load_supervisor_module()

    assert supervisor.nats_api_status_unhealthy(None) is True
    assert supervisor.nats_api_status_unhealthy({"mode": "nats-required-unavailable", "connected": False, "fallback_reason": "nats: flush timeout"}) is True
    assert supervisor.nats_api_status_unhealthy({"mode": "nats", "connected": True, "fallback_reason": ""}) is False


def test_sanitize_redacts_sensitive_keys_and_urls():
    supervisor = load_supervisor_module()

    payload = {
        "service": "pocket-api",
        "password": "secret-value",
        "nested": {"api_key": "abc", "url": "nats://user:pass@127.0.0.1:4222"},
    }

    sanitized = supervisor.sanitize(payload)
    assert sanitized["service"] == "pocket-api"
    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["nested"]["api_key"] == "***REDACTED***"
    assert "user:pass" not in sanitized["nested"]["url"]


def test_status_summary_reports_api_nats_health():
    supervisor = load_supervisor_module()

    summary = supervisor.status_summary(
        {"pocket-nats": "online", "pocket-api": "online"},
        True,
        {"mode": "nats", "connected": True, "fallback_reason": ""},
        True,
    )

    assert summary["checks"]["nats_tcp_reachable"] is True
    assert summary["checks"]["api_nats_connected"] is True
    assert summary["checks"]["caddy_http_reachable"] is True


def test_supervisor_does_not_restart_api_for_transient_nats_client_probe(monkeypatch, tmp_path):
    supervisor_module = load_supervisor_module()
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    supervisor = supervisor_module.LiteCoreSupervisor()

    observed = {
        "services": {
            "pocket-nats": "online",
            "pocket-api": "online",
            "pocket-worker": "online",
            "caddy-proxy": "online",
            "pocket-telemetry": "online",
        },
        "checks": {
            "nats_tcp_reachable": True,
            "api_nats_connected": False,
            "caddy_http_reachable": True,
        },
        "api_nats_mode": "nats",
        "api_nats_connected": False,
        "api_nats_fallback_reason": "transient client reconnect",
    }
    calls = {"count": 0}

    def fake_collect():
        calls["count"] += 1
        return observed

    def fail_restart(service, reason):  # pragma: no cover - should not run
        raise AssertionError(f"unexpected restart for {service}: {reason}")

    monkeypatch.setattr(supervisor, "collect", fake_collect)
    monkeypatch.setattr(supervisor, "restart_pm2", fail_restart)
    monkeypatch.setattr(supervisor_module, "pm2_available", lambda: True)

    payload = supervisor.tick()

    assert payload["actions"] == [
        {
            "event": supervisor_module.API_NATS_CLIENT_UNHEALTHY_EVENT,
            "service": "pocket-api",
            "reason": "api_nats_client_probe_degraded",
            "acted": False,
        }
    ]
    assert payload["supervisor_status"] == "repairing"
    assert calls["count"] == 2
    assert "api_nats_client_unhealthy_observed" in supervisor.events_file.read_text()
