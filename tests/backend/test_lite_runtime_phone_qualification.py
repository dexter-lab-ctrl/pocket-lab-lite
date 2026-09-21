from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "dev" / "check-lite-runtime-resilience-server-phone.sh"


def test_server_phone_runtime_preflights_fail_with_explicit_diagnostics():
    source = SCRIPT.read_text(encoding="utf-8")

    expected = (
        "Termux:Boot entry missing or not executable",
        "external runtime guardian is not running",
        "PM2 pid file missing or empty",
        "PM2 pid file does not contain a numeric PID",
        "PM2 daemon PID",
        "Lite API /health is not reachable",
        "Lite API /ready is not reachable",
        "pm2 jlist failed while reading Lite runtime topology",
        "Tailscale is installed but tailscaled is not running",
        "PhotoPrism is installed but proot-distro is unavailable",
        "PhotoPrism is installed but Ubuntu PRoot is unavailable",
        "PhotoPrism local runtime is not reachable",
        "PhotoPrism same-origin route is not reachable through Caddy",
    )

    for message in expected:
        assert message in source


def test_server_phone_runtime_preflights_emit_positive_progress_markers():
    source = SCRIPT.read_text(encoding="utf-8")

    for marker in (
        "PASS Termux:Boot recovery entry installed",
        "PASS external runtime guardian running",
        "PASS PM2 daemon running",
        "PASS Lite API health reachable",
        "PASS Lite API readiness reachable",
        "PASS required Lite PM2 topology online",
        "PASS every required Lite PM2 service projects its exact installed version",
        "PASS legacy Pocket Lab PM2 services absent",
    ):
        assert marker in source
