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
