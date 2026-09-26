from __future__ import annotations

import contextlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_runner():
    script = Path("scripts/dev/lite/run-ui-performance-qualified.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_ui_performance_runner", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _session_payload(token: str = "s" * 48, *, expires_in: int = 180, session_id: str = "hs-test"):
    return {
        "session_token": token,
        "session": {
            "harness_session_id": session_id,
            "expires_at": _iso(expires_in),
        },
    }


def _bridge_payload(token: str = "b" * 48, *, expires_in: int = 120):
    return {
        "browser_bridge_token": token,
        "browser_bridge": {
            "profile": "qualification-owner",
            "purpose": "ui-performance-60fps",
            "target_scope": "local_server_host_only",
            "expires_at": _iso(expires_in),
        },
    }


def _prepare_runner(monkeypatch, runner, tmp_path):
    runner.REPO_ROOT = tmp_path
    runner.DEFAULT_CONTROLLER_CHECKPOINT = tmp_path / ".pocketlab-dev/ui-performance-qualified-controller.json"
    monkeypatch.setenv("LITE_BASE_URL", "https://qualification.invalid")
    monkeypatch.delenv("POCKETLAB_TEST_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_DESTRUCTIVE", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_SESSION", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_BROWSER_BRIDGE", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_API_URL", raising=False)
    monkeypatch.setattr(runner, "ui_performance_runtime_tunnel", lambda: contextlib.nullcontext())
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/bash" if name == "bash" else None)
    monkeypatch.setattr(runner.Path, "is_file", lambda _path: True)


def test_qualified_runner_projects_only_the_fixed_browser_bridge_and_cleans_up(monkeypatch, capsys, tmp_path):
    runner = _load_runner()
    _prepare_runner(monkeypatch, runner, tmp_path)
    bridge_token = "b" * 48
    session_token = "s" * 48
    observed = {}

    monkeypatch.setattr(runner.harness_client, "bootstrap_session", lambda **kwargs: _session_payload(session_token))
    monkeypatch.setattr(runner.harness_client, "browser_bridge", lambda **kwargs: _bridge_payload(bridge_token))
    monkeypatch.setattr(
        runner.harness_client,
        "revoke_authenticated_principal",
        lambda **kwargs: observed.setdefault("cleanup", kwargs) or {"sanitized": True},
    )
    monkeypatch.setattr(runner.harness_client, "start_session", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected renewal")))
    monkeypatch.setattr(runner.harness_client, "stop_session", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected stop")))

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
        "--interaction", "live-scroll:home",
    ]) == 0

    assert observed["command"][-1].endswith("scripts/dev/lite/run-ui-performance-live.sh")
    assert observed["env"]["POCKETLAB_HARNESS_BROWSER_BRIDGE"] == bridge_token
    assert observed["env"]["LITE_QUALIFICATION_INTERACTION"] == "live-scroll:home"
    assert observed["env"]["LITE_PERF_PRESERVE_EVIDENCE"] == "1"
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
    _prepare_runner(monkeypatch, runner, tmp_path)
    monkeypatch.delenv("LITE_BASE_URL", raising=False)
    observed = {}

    monkeypatch.setattr(runner.harness_client, "bootstrap_session", lambda **kwargs: _session_payload())
    monkeypatch.setattr(runner.harness_client, "browser_bridge", lambda **kwargs: _bridge_payload())
    monkeypatch.setattr(runner.harness_client, "revoke_authenticated_principal", lambda **kwargs: {})
    monkeypatch.setattr(runner.harness_client, "start_session", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected renewal")))
    monkeypatch.setattr(runner.harness_client, "stop_session", lambda **kwargs: {})

    def fake_run(command, *, env, **kwargs):
        observed["env"] = env
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main([
        "--mode", "live",
        "--principal-id", "codex-ui-performance-qualification",
        "--key-file", str(tmp_path / "qualification.key"),
        "--interaction", "live-scroll:home",
    ]) == 0
    assert observed["env"]["LITE_BASE_URL"] == "http://127.0.0.1:18444"


def test_taskfile_qualified_live_mode_overrides_general_caddy_default():
    taskfile = Path("tasks/Taskfile.lite.yml").read_text(encoding="utf-8")
    assert (
        'LITE_BASE_URL="{{if eq .MODE "live"}}http://127.0.0.1:18444'
        '{{else}}{{.LITE_BASE_URL}}{{end}}"'
    ) in taskfile


def test_live_runner_loads_node_toolchain_for_noninteractive_controller_children():
    source = Path("scripts/dev/lite/run-ui-performance-live.sh").read_text(encoding="utf-8")
    assert 'nvm_dir="${NVM_DIR:-${HOME:-}/.nvm}"' in source
    assert 'source "$nvm_dir/nvm.sh"' in source
    assert 'nvm use "${POCKETLAB_NODE_VERSION:-24.16.0}"' in source
    assert 'command -v npm >/dev/null 2>&1 || fail' in source


def test_android_runner_loads_node_toolchain_for_noninteractive_controller_children():
    source = Path("scripts/dev/lite/run-ui-performance-android-cdp.sh").read_text(encoding="utf-8")
    assert 'nvm_dir="${NVM_DIR:-${HOME:-}/.nvm}"' in source
    assert 'source "$nvm_dir/nvm.sh"' in source
    assert 'nvm use "${POCKETLAB_NODE_VERSION:-24.16.0}"' in source
    assert 'need node' in source
    assert source.count("await browser.close().catch(() => {});") >= 2


def test_android_qualifier_uses_a_fresh_candidate_target_and_bounded_foreground_raf_probe():
    source = Path("scripts/dev/lite/qualify-ui-performance-android-cdp.mjs").read_text(encoding="utf-8")
    assert "existingCandidatePages" in source
    assert "existingCandidatePages[existingCandidatePages.length - 1] || await context.newPage()" in source
    assert "waitForVisibleWithReload" in source
    assert "bounded screen reload retries" in source
    assert "staleCandidatePages" in source
    assert "candidatePage.close()" in source
    assert "foregroundFramesReady" in source
    assert "bounded retries" in source


def test_candidate_ui_mode_supports_live_and_android_cdp_and_uses_checked_in_candidate_server():
    runner = _load_runner()
    source = Path("scripts/dev/lite/run-ui-performance-qualified.py").read_text(encoding="utf-8")
    assert "--candidate-ui" in source
    assert "--prepared-runtime" in source
    assert runner.CANDIDATE_BASE_URL == "http://127.0.0.1:18765"


def test_candidate_ui_mode_owns_the_browser_base_url(monkeypatch):
    runner = _load_runner()
    # Other backend fixtures intentionally enable their isolated test auth
    # contract at module import time.  This controller contract must exercise
    # the real operator environment boundary, so clear that test-only default
    # before asserting candidate-mode validation.
    monkeypatch.delenv("POCKETLAB_TEST_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("POCKETLAB_HARNESS_DESTRUCTIVE", raising=False)
    monkeypatch.delenv("LITE_BASE_URL", raising=False)
    assert runner._base_url("live", candidate_ui=True) == runner.CANDIDATE_BASE_URL
    assert runner._validate_operator_environment("android-cdp", candidate_ui=True) == runner.CANDIDATE_BASE_URL


def test_qualified_runner_retries_only_a_transient_preflight_failure(monkeypatch, tmp_path):
    runner = _load_runner()
    _prepare_runner(monkeypatch, runner, tmp_path)
    monkeypatch.setattr(runner.harness_client, "bootstrap_session", lambda **kwargs: _session_payload())
    monkeypatch.setattr(runner.harness_client, "browser_bridge", lambda **kwargs: _bridge_payload())
    monkeypatch.setattr(runner.harness_client, "revoke_authenticated_principal", lambda **kwargs: {})
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    outcomes = iter(
        (
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="[ui-performance-live] ERROR: Pocket Lab Lite status endpoint is not reachable.\n",
            ),
            SimpleNamespace(returncode=0, stdout="measured\n", stderr=""),
        )
    )
    calls = []

    def fake_run(*_args, **_kwargs):
        calls.append(True)
        return next(outcomes)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main([
        "--mode", "live",
        "--principal-id", "codex-ui-performance-qualification",
        "--key-file", str(tmp_path / "qualification.key"),
        "--interaction", "live-scroll:home",
    ]) == 0
    assert len(calls) == 2


def test_transient_preflight_recovery_renews_only_between_child_attempts(monkeypatch, tmp_path):
    runner = _load_runner()
    _prepare_runner(monkeypatch, runner, tmp_path)
    runner.PREFLIGHT_RETRY_ATTEMPTS = 2
    runner.PREFLIGHT_RETRY_DELAY_SECONDS = 0
    old = runner.Authority(
        "old-session",
        "old-id",
        datetime.now(timezone.utc) + timedelta(seconds=20),
        "old-bridge",
        datetime.now(timezone.utc) + timedelta(seconds=20),
    )
    replacement = runner.Authority(
        "new-session",
        "new-id",
        datetime.now(timezone.utc) + timedelta(seconds=180),
        "new-bridge",
        datetime.now(timezone.utc) + timedelta(seconds=180),
    )
    renewals = []
    child_bridges = []
    monkeypatch.setattr(
        runner,
        "_before_owner_interaction",
        lambda authority, **_kwargs: (renewals.append(authority) or (replacement, "session_rotated")),
    )
    monkeypatch.setattr(runner, "_runner_command", lambda _mode: ["fake-runner"])
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    outcomes = iter(
        (
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="[ui-performance-live] ERROR: Pocket Lab Lite status endpoint is not reachable.\n",
            ),
            SimpleNamespace(returncode=0, stdout="measured\n", stderr=""),
        )
    )

    def fake_run(_command, *, env, **_kwargs):
        child_bridges.append(env["POCKETLAB_HARNESS_BROWSER_BRIDGE"])
        return next(outcomes)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    secrets = []
    code, current = runner._run_interaction(
        SimpleNamespace(mode="live"),
        base_url="http://127.0.0.1:18444",
        authority=old,
        principal_id="owner-runner",
        key_file="/tmp/key",
        ttl_seconds=180,
        interaction="live-scroll:home",
        secrets=secrets,
    )
    assert code == 0
    assert current is replacement
    assert renewals == [old]
    assert child_bridges == ["old-bridge", "new-bridge"]
    assert "new-session" in secrets
    assert "new-bridge" in secrets


def test_qualified_runner_retries_transient_cleanup_transport(monkeypatch, tmp_path):
    runner = _load_runner()
    _prepare_runner(monkeypatch, runner, tmp_path)
    monkeypatch.setattr(runner.harness_client, "bootstrap_session", lambda **kwargs: _session_payload())
    monkeypatch.setattr(runner.harness_client, "browser_bridge", lambda **kwargs: _bridge_payload())
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    attempts = {"count": 0}

    def revoke(**_kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("harness_transport_unavailable: ConnectionResetError")
        return {"sanitized": True}

    monkeypatch.setattr(runner.harness_client, "revoke_authenticated_principal", revoke)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert runner.main([
        "--mode", "live",
        "--principal-id", "codex-ui-performance-qualification",
        "--key-file", str(tmp_path / "qualification.key"),
        "--interaction", "live-scroll:home",
    ]) == 0
    assert attempts["count"] == 3


def test_qualified_runner_accepts_lost_cleanup_response_after_clean_status(monkeypatch, tmp_path):
    runner = _load_runner()
    _prepare_runner(monkeypatch, runner, tmp_path)
    monkeypatch.setattr(runner.harness_client, "bootstrap_session", lambda **kwargs: _session_payload())
    monkeypatch.setattr(runner.harness_client, "browser_bridge", lambda **kwargs: _bridge_payload())
    monkeypatch.setattr(
        runner.harness_client,
        "revoke_authenticated_principal",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("harness_session_revoked: The harness session is no longer active.")),
    )
    monkeypatch.setattr(
        runner.harness_client,
        "status",
        lambda: {"active_sessions": 0, "principal_count": 0, "sanitized": True},
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert runner.main([
        "--mode", "live",
        "--principal-id", "codex-ui-performance-qualification",
        "--key-file", str(tmp_path / "qualification.key"),
        "--interaction", "live-scroll:home",
    ]) == 0


def test_qualified_runner_resume_preserves_existing_evidence(monkeypatch, tmp_path):
    runner = _load_runner()
    _prepare_runner(monkeypatch, runner, tmp_path)
    evidence = tmp_path / ".pocketlab-dev/performance/existing.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text('{"source_commit":"candidate"}\n', encoding="utf-8")
    checkpoint = tmp_path / ".pocketlab-dev/qualification-controller.json"
    runner._write_checkpoint(
        checkpoint,
        principal_id="codex-ui-performance-qualification",
        mode="live",
        completed={"live-scroll:home"},
        next_interaction="live-scroll:catalog",
        status="interaction_complete",
    )
    monkeypatch.setattr(runner.harness_client, "bootstrap_session", lambda **kwargs: _session_payload())
    monkeypatch.setattr(runner.harness_client, "browser_bridge", lambda **kwargs: _bridge_payload())
    monkeypatch.setattr(runner.harness_client, "revoke_authenticated_principal", lambda **kwargs: {})
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert runner.main([
        "--mode", "live",
        "--principal-id", "codex-ui-performance-qualification",
        "--key-file", str(tmp_path / "qualification.key"),
        "--interaction", "live-scroll:home",
        "--controller-checkpoint", str(checkpoint),
        "--resume",
    ]) == 0
    assert evidence.exists()


def test_before_owner_interaction_rotates_session_below_45_seconds(monkeypatch):
    runner = _load_runner()
    now = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
    old = runner.Authority(
        "old-session",
        "hs-old",
        now + timedelta(seconds=44),
        "old-bridge",
        now + timedelta(seconds=120),
    )
    replacement = runner.Authority(
        "new-session",
        "hs-new",
        now + timedelta(seconds=180),
        "new-bridge",
        now + timedelta(seconds=180),
    )
    observed = {}
    monkeypatch.setattr(
        runner,
        "_renew_session",
        lambda authority, **kwargs: observed.setdefault("old", authority) and replacement,
    )

    authority, action = runner._before_owner_interaction(
        old,
        principal_id="owner-runner",
        key_file="/tmp/key",
        ttl_seconds=180,
        now=now,
    )
    assert authority is replacement
    assert action == "session_rotated"
    assert observed["old"] is old


def test_before_owner_interaction_rotates_only_bridge_below_30_seconds(monkeypatch):
    runner = _load_runner()
    now = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
    old = runner.Authority(
        "session",
        "hs-one",
        now + timedelta(seconds=120),
        "old-bridge",
        now + timedelta(seconds=29),
    )
    monkeypatch.setattr(
        runner,
        "_mint_bridge",
        lambda token: ("new-bridge", now + timedelta(seconds=120)),
    )

    authority, action = runner._before_owner_interaction(
        old,
        principal_id="owner-runner",
        key_file="/tmp/key",
        ttl_seconds=180,
        now=now,
    )
    assert action == "bridge_rotated"
    assert authority.session_token == "session"
    assert authority.session_id == "hs-one"
    assert authority.bridge_token == "new-bridge"


def test_before_owner_interaction_keeps_healthy_authority(monkeypatch):
    runner = _load_runner()
    now = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
    healthy = runner.Authority(
        "session",
        "hs-one",
        now + timedelta(seconds=90),
        "bridge",
        now + timedelta(seconds=60),
    )
    monkeypatch.setattr(runner, "_renew_session", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected session rotation")))
    monkeypatch.setattr(runner, "_mint_bridge", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected bridge rotation")))

    authority, action = runner._before_owner_interaction(
        healthy,
        principal_id="owner-runner",
        key_file="/tmp/key",
        ttl_seconds=180,
        now=now,
    )
    assert authority is healthy
    assert action == "authority_healthy"


def test_session_rotation_uses_existing_principal_and_revokes_old_session(monkeypatch):
    runner = _load_runner()
    now = datetime.now(timezone.utc)
    old = runner.Authority(
        "old-token",
        "hs-old",
        now + timedelta(seconds=20),
        "old-bridge",
        now + timedelta(seconds=20),
    )
    observed = {}
    def fake_start_session(**kwargs):
        observed["start"] = kwargs
        return _session_payload("new-token", expires_in=180, session_id="hs-new")

    monkeypatch.setattr(runner.harness_client, "start_session", fake_start_session)
    monkeypatch.setattr(runner.harness_client, "browser_bridge", lambda **kwargs: _bridge_payload("new-bridge", expires_in=120))
    def fake_stop_session(**kwargs):
        observed["stop"] = kwargs
        return {"status": "revoked"}

    monkeypatch.setattr(runner.harness_client, "stop_session", fake_stop_session)

    renewed = runner._renew_session(
        old,
        principal_id="owner-runner",
        key_file="/tmp/key",
        ttl_seconds=180,
    )
    assert observed["start"]["principal_id"] == "owner-runner"
    assert observed["start"]["profile"] == "qualification-owner"
    assert observed["start"]["purpose"] == "ui-performance-60fps"
    assert observed["stop"] == {"session_token": "old-token", "session_id": "hs-old"}
    assert renewed.session_token == "new-token"
    assert renewed.bridge_token == "new-bridge"


def test_controller_checkpoint_contains_progress_not_credentials(monkeypatch, tmp_path):
    runner = _load_runner()
    runner.REPO_ROOT = tmp_path
    checkpoint = tmp_path / ".pocketlab-dev/qualification-controller.json"
    runner._write_checkpoint(
        checkpoint,
        principal_id="owner-runner",
        mode="live",
        completed={"live-scroll:home"},
        next_interaction="live-scroll:catalog",
        status="before_interaction",
    )
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["completed_interactions"] == ["live-scroll:home"]
    assert payload["next_interaction"] == "live-scroll:catalog"
    assert payload["contains_secrets"] is False
    serialized = checkpoint.read_text(encoding="utf-8").casefold()
    for forbidden in ("session_token", "browser_bridge_token", "private_key", "authorization"):
        assert forbidden not in serialized


def test_live_default_interaction_plan_is_bounded_and_filterable():
    runner = _load_runner()
    args = SimpleNamespace(mode="live", interaction=None)
    plan = runner._interactions(args)
    assert plan == runner.DEFAULT_LIVE_INTERACTIONS
    assert len(plan) == 26

    args = SimpleNamespace(mode="live", interaction=["live-scroll:home"])
    assert runner._interactions(args) == ("live-scroll:home",)


def test_renewal_contract_is_repository_owned():
    runner_source = Path("scripts/dev/lite/run-ui-performance-qualified.py").read_text(encoding="utf-8")
    live_spec = Path("tests/e2e/lite-performance-live.spec.ts").read_text(encoding="utf-8")
    taskfile = Path("tasks/Taskfile.lite.yml").read_text(encoding="utf-8")
    ignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "SESSION_RENEWAL_THRESHOLD_SECONDS = 45" in runner_source
    assert "BRIDGE_RENEWAL_THRESHOLD_SECONDS = 30" in runner_source
    assert "LITE_QUALIFICATION_INTERACTION" in live_spec
    assert "Unsupported live qualification interaction" in live_spec
    assert "UNAVAILABLE identity Manage Access" in live_spec
    assert "UNAVAILABLE Rules Manage" in live_spec
    assert "UNAVAILABLE recovery Manage" in live_spec
    assert "UNAVAILABLE recovery Restore" in live_spec
    assert "lite:ui:perf:qualified:" in taskfile
    assert ".pocketlab-dev/" in ignore


def test_harness_client_exposes_direct_session_stop_helper():
    source = Path("scripts/dev/lite/harness.py").read_text(encoding="utf-8")
    assert "def stop_session(*, session_token: str, session_id: str)" in source
    assert '"/api/lite/harness/session/{identifier}"' in source
