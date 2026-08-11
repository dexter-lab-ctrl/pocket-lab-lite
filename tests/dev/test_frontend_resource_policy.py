from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VITE = ROOT / "vite.config.js"
VSCODE = ROOT / ".vscode" / "settings.json"
RUNNER = ROOT / "scripts" / "dev" / "lite" / "run-playwright-mocked.sh"
PREFLIGHT = ROOT / "scripts" / "dev" / "lite" / "frontend-resource-preflight.sh"

TRANSIENT_PATTERNS = (
    "**/.pocketlab-dev/**",
    "**/site/**",
    "**/storybook-static/**",
    "**/playwright-report/**",
    "**/test-results/**",
    "**/allure-results/**",
    "**/dist/**",
)


def test_vite_ignores_transient_artifacts_and_fails_closed_on_port_collision():
    source = VITE.read_text(encoding="utf-8")
    assert "server:" in source
    assert "strictPort: true" in source
    assert "watch:" in source
    assert "ignored:" in source
    for pattern in TRANSIENT_PATTERNS:
        assert repr(pattern) in source


def test_vscode_ignores_transient_artifacts_for_watch_and_search():
    settings = json.loads(VSCODE.read_text(encoding="utf-8"))
    for key in ("files.watcherExclude", "search.exclude"):
        configured = settings[key]
        for pattern in TRANSIENT_PATTERNS:
            assert configured.get(pattern) is True


def test_mocked_runner_uses_preflight_and_disk_backed_playwright_scratch():
    source = RUNNER.read_text(encoding="utf-8")
    assert "frontend-resource-preflight.sh" in source
    assert 'dev-scratch.sh" run playwright --' in source
    assert "VITE_POCKETLAB_MOCKS=1" in source
    assert "LITE_E2E_MODE=mocked" in source
    assert "trap cleanup_raw_har EXIT INT TERM" in source
    assert "NODE_OPTIONS=" not in source


def test_frontend_preflight_is_bounded_and_non_destructive():
    source = PREFLIGHT.read_text(encoding="utf-8")
    assert "POCKETLAB_FRONTEND_MIN_MEMORY_MIB" in source
    assert "POCKETLAB_FRONTEND_MIN_SCRATCH_GIB" in source
    assert "MemAvailable" in source
    assert "scancode-*" in source
    assert "cleanup is intentionally manual" in source
    assert "rm -rf" not in source
    assert "--max-old-space-size" in source
    assert "NODE_OPTIONS" in source


def test_frontend_preflight_rejects_invalid_resource_limits_before_test_launch():
    env = os.environ.copy()
    env["POCKETLAB_FRONTEND_MIN_MEMORY_MIB"] = "not-a-number"
    result = subprocess.run(
        ["bash", str(PREFLIGHT), "mocked"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "must be an integer" in result.stderr
