from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/dev/lite/security_assurance_360.py"
BROWSER = ROOT / "scripts/dev/lite/security_assurance_browser.mjs"
TUNNEL = ROOT / "scripts/dev/lite/security_assurance_runtime_tunnel.py"


def _module():
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_360", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _tunnel_module():
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_runtime_tunnel", TUNNEL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _field_names(value):
    names = set()
    if isinstance(value, dict):
        for key, item in value.items():
            names.add(str(key).casefold())
            names.update(_field_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(_field_names(item))
    return names


def _safe_request(_method, path, **_kwargs):
    if path in {
        "/api/lite/harness/security-assurance/capabilities",
        "/api/lite/harness/security-assurance/runs",
    }:
        status = 403
    elif path in {
        "/debug",
        "/metrics",
        "/api/docs",
        "/api/lite/harness",
    }:
        status = 404
    else:
        status = 200
    return {
        "status": status,
        "headers": {},
        "body_bytes_observed": 0,
        "duration_ms": 1,
    }


def test_runtime_360_uses_only_fixed_runtime_targets(monkeypatch):
    probe = _module()
    monkeypatch.setattr(probe, "_request", _safe_request)
    monkeypatch.setattr(probe, "_caddy_request", _safe_request)
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
    assert result["findings"] == []


def test_runtime_360_reports_hostile_websocket_as_real_security_finding(monkeypatch):
    probe = _module()
    monkeypatch.setattr(probe, "_request", _safe_request)
    monkeypatch.setattr(probe, "_caddy_request", _safe_request)
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
    sensitive_fields = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
    assert not (sensitive_fields & _field_names(result))


def test_runtime_360_deep_provenance_stays_fixed_and_explicit(monkeypatch):
    probe = _module()
    monkeypatch.setattr(probe, "_request", _safe_request)
    monkeypatch.setattr(probe, "_caddy_request", _safe_request)
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
    assert 'identity || "127.0.0.1"' not in text
    assert 'throw new Error("runtime_tls_identity_unavailable")' in text
    assert "ignoreHTTPSErrors: false" in text
    assert 'caddy_identity: "fixed_operator_approved_identity"' in text
    # Match exact caller-facing argv tokens, not fixed Chromium implementation
    # flags such as --host-resolver-rules.
    for forbidden in (
        '"--target"',
        '"--url"',
        '"--host"',
        '"--port"',
        '"--argv"',
        '"--subject"',
        '"--wordlist"',
        '"--script"',
        '"--fixture"',
    ):
        assert forbidden not in text


def test_runtime_tunnel_uses_runtime_reported_server_and_tailnet_ips():
    tunnel = _tunnel_module()
    config = {
        "hostname": "phone.example.ts.net",
        "user": "u0_a123",
        "port": "8022",
        "batchmode": "yes",
        "passwordauthentication": "no",
        "kbdinteractiveauthentication": "no",
        "stricthostkeychecking": "yes",
        "userknownhostsfile": "/home/test/.ssh/known_hosts",
    }
    facts = tunnel._parse_runtime_facts(
        "TERMUX_OK=1\n"
        "SSH_CONNECTION=192.168.50.4 50123 192.168.50.20 8022\n"
        "REMOTE_USER=u0_a123\n"
        "TAILSCALE_IPV4=100.64.12.34\n",
        config,
        caddy_sni="pocket-lab.example.ts.net",
    )
    argv = tunnel.build_tunnel_argv(facts, config)
    assert "Hostname=192.168.50.20" in argv
    assert not any(token.startswith("HostKeyAlias=") for token in argv)
    assert argv[argv.index("-p") + 1] == "8022"
    assert argv[argv.index("-l") + 1] == "u0_a123"
    assert "127.0.0.1:18443:100.64.12.34:443" in argv
    assert argv[-1] == "pocketlab-termux"
    assert facts["server_phone_ip_source"] == "SSH_CONNECTION"
    assert facts["tailscale_ipv4_source"] == "tailscale_runtime_ip4"

    ui_argv = tunnel.build_tunnel_argv(facts, config, include_caddy_http=True)
    assert "127.0.0.1:18444:127.0.0.1:8443" in ui_argv


def test_runtime_tunnel_cli_has_no_caller_selected_network_inputs():
    text = TUNNEL.read_text(encoding="utf-8")
    assert 'SSH_ALIAS = "pocketlab-termux"' in text
    assert '"-o", f"Hostname={server_ip}"' in text
    assert 'f"127.0.0.1:{CADDY_LOCAL_PORT}:{tailscale_ip}:{CADDY_REMOTE_PORT}"' in text
    assert 'include_caddy_http: bool = False' in text
    assert 'CADDY_HTTP_LOCAL_PORT = 18444' in text
    assert '127.0.0.1:{CADDY_HTTP_LOCAL_PORT}:127.0.0.1:{CADDY_HTTP_REMOTE_PORT}' in text
    for forbidden in (
        'add_argument("--host"',
        'add_argument("--port"',
        'add_argument("--user"',
        'add_argument("--target"',
        'add_argument("--url"',
        'add_argument("--forward"',
        'add_argument("--sni"',
    ):
        assert forbidden not in text


def test_ui_runtime_tunnel_uses_bounded_stable_readiness():
    text = TUNNEL.read_text(encoding="utf-8")
    assert "UI_TUNNEL_READINESS_TIMEOUT_SECONDS = 30.0" in text
    assert "UI_TUNNEL_READY_STREAK = 3" in text
    assert "ready_streak = 0" in text
    assert "ready_streak >= UI_TUNNEL_READY_STREAK" in text
    assert "ready_streak = 0" in text[text.index("def ui_performance_runtime_tunnel"):]
