from __future__ import annotations

import contextlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_runner():
    script = Path("scripts/dev/lite/run-ui-performance-qualified.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_ui_performance_runner", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qualified_runner_projects_only_the_fixed_browser_bridge_and_cleans_up(monkeypatch, capsys, tmp_path):
    runner = _load_runner()
    bridge_token = "b" * 48
    session_token = "s" * 48
    observed = {}

    monkeypatch.setenv("LITE_BASE_URL", "https://qualification.invalid")
    monkeypatch.delenv("POCKETLAB_TEST_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_DESTRUCTIVE", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_SESSION", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_BROWSER_BRIDGE", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_API_URL", raising=False)
    monkeypatch.setattr(runner, "ui_performance_runtime_tunnel", lambda: contextlib.nullcontext())
    monkeypatch.setattr(
        runner.harness_client,
        "bootstrap_session",
        lambda **kwargs: {
            "session_token": session_token,
            "session": {"harness_session_id": "hs-test"},
            "kwargs": kwargs,
        },
    )
    monkeypatch.setattr(
        runner.harness_client,
        "browser_bridge",
        lambda **kwargs: {
            "browser_bridge_token": bridge_token,
            "browser_bridge": {
                "profile": "qualification-owner",
                "purpose": "ui-performance-60fps",
                "target_scope": "local_server_host_only",
            },
        },
    )
    monkeypatch.setattr(
        runner.harness_client,
        "revoke_authenticated_principal",
        lambda **kwargs: observed.setdefault("cleanup", kwargs) or {"sanitized": True},
    )
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/bash" if name == "bash" else None)
    monkeypatch.setattr(runner.Path, "is_file", lambda _path: True)

    def fake_run(command, *, cwd, env, stdin, capture_output, text, timeout, check):
        observed["command"] = command
        observed["env"] = env
        observed["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout="qualification output\n", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main([
        "--mode", "live",
        "--principal-id", "codex-ui-performance-qualification",
        "--key-file", str(tmp_path / "qualification.key"),
    ]) == 0

    assert observed["command"][-1].endswith("scripts/dev/lite/run-ui-performance-live.sh")
    assert observed["env"]["POCKETLAB_HARNESS_BROWSER_BRIDGE"] == bridge_token
    assert observed["env"]["LITE_BASE_URL"] == "https://qualification.invalid"
    assert "POCKETLAB_HARNESS_SESSION" not in observed["env"]
    assert "POCKETLAB_HARNESS_API_URL" not in observed["env"]
    assert "POCKETLAB_TEST_AUTH_BYPASS" not in observed["env"]
    assert observed["cleanup"] == {"session_token": session_token}
    output = capsys.readouterr().out
    assert bridge_token not in output
    assert session_token not in output


def test_qualified_runner_rejects_preexisting_test_bypass(monkeypatch):
    runner = _load_runner()
    monkeypatch.setenv("LITE_BASE_URL", "https://qualification.invalid")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "1")
    try:
        runner.main([
            "--mode", "live",
            "--principal-id", "codex-ui-performance-qualification",
            "--key-file", "/tmp/qualification.key",
        ])
    except ValueError as exc:
        assert "TEST_AUTH_BYPASS" in str(exc)
    else:
        raise AssertionError("preexisting test-auth bypass was accepted")


def test_qualified_runner_defaults_live_browser_to_owned_caddy_forward(monkeypatch, tmp_path):
    runner = _load_runner()
    observed = {}
    bridge_token = "b" * 48
    session_token = "s" * 48
    monkeypatch.delenv("LITE_BASE_URL", raising=False)
    monkeypatch.delenv("POCKETLAB_TEST_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_DESTRUCTIVE", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_SESSION", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_BROWSER_BRIDGE", raising=False)
    monkeypatch.setattr(runner, "ui_performance_runtime_tunnel", lambda: contextlib.nullcontext())
    monkeypatch.setattr(
        runner.harness_client,
        "bootstrap_session",
        lambda **kwargs: {"session_token": session_token},
    )
    monkeypatch.setattr(
        runner.harness_client,
        "browser_bridge",
        lambda **kwargs: {
            "browser_bridge_token": bridge_token,
            "browser_bridge": {
                "profile": runner.PROFILE,
                "purpose": runner.PURPOSE,
                "target_scope": runner.TARGET_SCOPE,
            },
        },
    )
    monkeypatch.setattr(runner.harness_client, "revoke_authenticated_principal", lambda **kwargs: {})
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/bash" if name == "bash" else None)
    monkeypatch.setattr(runner.Path, "is_file", lambda _path: True)

    def fake_run(command, *, env, **kwargs):
        observed["env"] = env
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main([
        "--mode", "live",
        "--principal-id", "codex-ui-performance-qualification",
        "--key-file", str(tmp_path / "qualification.key"),
    ]) == 0
    assert observed["env"]["LITE_BASE_URL"] == "http://127.0.0.1:18444"
