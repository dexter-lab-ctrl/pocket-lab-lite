from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/dev/lite/security_assurance_360.py"
BROWSER = ROOT / "scripts/dev/lite/security_assurance_browser.mjs"


def _module():
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_360", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _safe_request(_method, path, **_kwargs):
    status = 404 if path in {
        "/debug",
        "/metrics",
        "/api/docs",
        "/api/lite/harness",
    } else 200
    return {
        "status": status,
        "headers": {},
        "body_bytes_observed": 0,
        "duration_ms": 1,
    }


def test_runtime_360_uses_only_fixed_runtime_targets(monkeypatch):
    probe = _module()
    monkeypatch.setattr(probe, "_request", _safe_request)
    monkeypatch.setattr(
        probe,
        "_websocket_handshake",
        lambda *, hostile_origin: {
            "accepted": False,
            "origin_class": "hostile" if hostile_origin else "same-origin",
        },
    )
    monkeypatch.setattr(probe, "_tcp", lambda _port: True)
    monkeypatch.setattr(
        probe,
        "_tls_identity",
        lambda: {"status": "PASS", "identity": "fixed_caddy_identity"},
    )

    result = probe.run("standard")

    assert result["target"] == "fixed_server_phone_runtime_tunnels"
    assert result["sanitized"] is True
    assert result["raw_response_bodies_persisted"] is False
    assert result["scenario_results"]["cross-origin-session-abuse"]["status"] == "PASS"
    assert result["scenario_results"]["csrf-protected-mutation"]["status"] == "PASS"
    assert result["scenario_results"]["owner-session-lifecycle"]["status"] == "NOT_ASSESSED"
    assert result["findings"] == []


def test_runtime_360_reports_hostile_websocket_as_real_security_finding(monkeypatch):
    probe = _module()
    monkeypatch.setattr(probe, "_request", _safe_request)
    monkeypatch.setattr(
        probe,
        "_websocket_handshake",
        lambda *, hostile_origin: {
            "accepted": bool(hostile_origin),
            "origin_class": "hostile" if hostile_origin else "same-origin",
        },
    )
    monkeypatch.setattr(probe, "_tcp", lambda _port: True)
    monkeypatch.setattr(
        probe,
        "_tls_identity",
        lambda: {"status": "PASS", "identity": "fixed_caddy_identity"},
    )
    monkeypatch.setattr(
        probe,
        "_bounded_burst",
        lambda: {
            "request_count": 8,
            "max_concurrency": 2,
            "duration_ms": 4,
            "successful": 8,
            "statuses": [200] * 8,
        },
    )
    monkeypatch.setattr(
        probe,
        "_slow_client_probe",
        lambda: {
            "slow_connections": 2,
            "hold_ms": 250,
            "health_status_during_hold": 200,
        },
    )

    result = probe.run("adversarial")

    assert result["scenario_results"]["websocket-auth-boundary"]["status"] == "FAIL"
    finding = next(row for row in result["findings"] if row["scenario_id"] == "websocket-auth-boundary")
    assert finding["severity"] == "high"
    assert "cookie" not in str(result).casefold()
    assert "authorization" not in str(result).casefold()


def test_runtime_360_deep_provenance_stays_fixed_and_explicit(monkeypatch):
    probe = _module()
    monkeypatch.setattr(probe, "_request", _safe_request)
    monkeypatch.setattr(
        probe,
        "_websocket_handshake",
        lambda *, hostile_origin: {"accepted": False},
    )
    monkeypatch.setattr(probe, "_tcp", lambda _port: True)
    monkeypatch.setattr(probe, "_tls_identity", lambda: {"status": "PASS"})
    monkeypatch.setattr(
        probe,
        "_bounded_burst",
        lambda: {
            "request_count": 8,
            "max_concurrency": 2,
            "duration_ms": 5,
            "successful": 8,
            "statuses": [200] * 8,
        },
    )
    monkeypatch.setattr(
        probe,
        "_release_provenance",
        lambda: {
            "dist_present": False,
            "signed_artifact_manifest_present": False,
            "status": "PASS",
        },
    )

    result = probe.run("deep")
    assert result["scenario_results"]["release-artifact-tamper"]["status"] == "NOT_ASSESSED"
    assert result["scenario_results"]["dependency-confusion-and-lock-integrity"]["status"] == "PASS"
    assert result["scenario_results"]["restore-transaction-integrity"]["status"] == "NOT_ASSESSED"


def test_runtime_360_rejects_unregistered_suite():
    probe = _module()
    with pytest.raises(ValueError, match="suite_not_registered"):
        probe.run("smoke")


def test_browser_adapter_exposes_only_registered_suite_cli_and_fixed_targets():
    text = BROWSER.read_text(encoding="utf-8")
    assert '["standard", "deep", "adversarial"]' in text
    assert "process.argv.slice(2)" in text
    assert "args.length !== 1" in text
    assert "CADDY_PORT = 18443" in text
    assert "ATTACKER_PORT = 18991" in text
    assert "credentials_injected: false" in text
    assert "storage_values_read: false" in text
    for forbidden in (
        "--target",
        "--url",
        "--host",
        "--port",
        "--argv",
        "--subject",
        "--wordlist",
        "--script",
        "--fixture",
    ):
        assert forbidden not in text
