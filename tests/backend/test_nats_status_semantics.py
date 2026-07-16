from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "pocket-lab-final-structure/runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))


def load(name: str):
    module = importlib.import_module("api_fastapi.services.nats_bus")
    return importlib.reload(module)


def test_connected_status_distinguishes_current_and_historical_errors(monkeypatch):
    module = load("nats_bus_status_semantics")
    bus = module.PocketLabEventBus()
    bus._last_error = "ConnectionRefusedError: historical"
    bus._last_error_at = "2026-07-16T12:00:00Z"
    bus._last_connected_at = ""
    monkeypatch.setattr(bus, "_client_is_connected", lambda: True)
    payload = bus.status()
    assert payload["connected"] is True
    assert payload["last_error"] == ""
    assert payload["current_error"] == ""
    assert payload["last_historical_error"] == "ConnectionRefusedError: historical"
    assert payload["last_error_at"] == "2026-07-16T12:00:00Z"
    assert payload["last_connected_at"]


def test_disconnected_status_exposes_current_error(monkeypatch):
    module = load("nats_bus_status_disconnected")
    bus = module.PocketLabEventBus()
    bus._last_error = "ConnectionRefusedError: current"
    bus._last_error_at = "2026-07-16T12:01:00Z"
    monkeypatch.setattr(bus, "_client_is_connected", lambda: False)
    payload = bus.status()
    assert payload["connected"] is False
    assert payload["last_error"] == "ConnectionRefusedError: current"
    assert payload["current_error"] == "ConnectionRefusedError: current"
    assert payload["last_historical_error"] == "ConnectionRefusedError: current"
