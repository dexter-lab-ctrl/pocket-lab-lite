from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "scripts/dev/lite/qualification_https_bridge.ps1"


def test_qualification_https_bridge_preserves_cookie_authority_and_streams_sse():
    source = BRIDGE.read_text(encoding="utf-8")

    assert 'listener.Prefixes.Add("http://127.0.0.1:"' in source
    assert "UseCookies = false" in source
    assert "ResponseHeadersRead" in source
    assert 'header.Key.Equals("Set-Cookie"' in source
    assert 'target.AppendHeader("Set-Cookie", value)' in source
    assert "Task.Run" in source
    assert "SemaphoreSlim" in source
    assert "ReadAsByteArrayAsync" not in source
    assert "16L * 1024L * 1024L" in source


def test_qualification_https_bridge_restricts_the_target_to_private_addresses():
    source = BRIDGE.read_text(encoding="utf-8")

    assert "ValidatePattern" in source
    assert "127\\.0\\.0\\.1" in source
    assert "172\\." in source
    assert "192\\.168\\." in source
    assert "10\\." in source
