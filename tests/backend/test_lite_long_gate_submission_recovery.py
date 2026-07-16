from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
FAULTS = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_gate_faults.py"
GROUP3 = ROOT / "scripts/dev/lib/long_gate_group3.py"
ROUTER = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def request(headers=None, host="127.0.0.1"):
    return SimpleNamespace(headers=headers or {}, client=SimpleNamespace(host=host))


def write_activation(module, root: Path, token: str, delay_ms: int = 5000, expires: float = 9999999999.0):
    os.environ["POCKETLAB_STATE_DIR"] = str(root)
    path = module.submission_delay_activation_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "scenario": module.SUBMISSION_DELAY_SCENARIO,
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "delay_ms": delay_ms,
        "expires_at_epoch": expires,
    }), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_fault_injection_is_disabled_by_default_and_requires_all_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load(FAULTS, "lite_gate_faults_test_default")
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    token = "a" * 32
    marker = {"x-pocketlab-gate-scenario": module.SUBMISSION_DELAY_SCENARIO, "x-pocketlab-gate-token": token}
    assert module.authorized_submission_delay_ms(request(marker), now_epoch=1) == 0
    write_activation(module, tmp_path, token)
    assert module.authorized_submission_delay_ms(request({}), now_epoch=1) == 0
    assert module.authorized_submission_delay_ms(request(marker, host="10.0.0.2"), now_epoch=1) == 0
    assert module.authorized_submission_delay_ms(request({**marker, "x-pocketlab-gate-token": "b" * 32}), now_epoch=1) == 0
    assert module.authorized_submission_delay_ms(request(marker), now_epoch=1) == 5000



def test_authorized_hook_delays_only_matching_loopback_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load(FAULTS, "lite_gate_faults_test_async")
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    token = "e" * 32
    write_activation(module, tmp_path, token, delay_ms=123)
    observed: list[float] = []

    async def fake_sleep(seconds: float):
        observed.append(seconds)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    matching = request({
        module.SUBMISSION_DELAY_HEADER: module.SUBMISSION_DELAY_SCENARIO,
        module.SUBMISSION_TOKEN_HEADER: token,
    })
    unrelated = request({module.SUBMISSION_DELAY_HEADER: "other"})
    assert asyncio.run(module.maybe_delay_submission_response(unrelated)) == 0
    assert observed == []
    assert asyncio.run(module.maybe_delay_submission_response(matching)) == 123
    assert observed == [pytest.approx(0.123)]

def test_activation_must_be_owner_only_unexpired_and_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load(FAULTS, "lite_gate_faults_test_bounds")
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    token = "c" * 32
    marker = {"x-pocketlab-gate-scenario": module.SUBMISSION_DELAY_SCENARIO, "x-pocketlab-gate-token": token}
    path = write_activation(module, tmp_path, token, delay_ms=module.MAX_SUBMISSION_DELAY_MS)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert module.authorized_submission_delay_ms(request(marker), now_epoch=1) == module.MAX_SUBMISSION_DELAY_MS
    path.chmod(0o644)
    assert module.authorized_submission_delay_ms(request(marker), now_epoch=1) == 0
    path.chmod(0o600)
    payload = json.loads(path.read_text())
    payload["delay_ms"] = module.MAX_SUBMISSION_DELAY_MS + 1
    path.write_text(json.dumps(payload))
    path.chmod(0o600)
    assert module.authorized_submission_delay_ms(request(marker), now_epoch=1) == 0
    payload["delay_ms"] = 5000
    payload["expires_at_epoch"] = 1
    path.write_text(json.dumps(payload))
    path.chmod(0o600)
    assert module.authorized_submission_delay_ms(request(marker), now_epoch=2) == 0


def test_fault_hook_is_after_durable_lifecycle_commit_and_before_response():
    text = ROUTER.read_text(encoding="utf-8")
    endpoint = text.split('@router.post("/security/check"', 1)[1].split('@router.post("/security/scan"', 1)[0]
    assert endpoint.index("lite_security.finalize_scan_submission") < endpoint.index("maybe_delay_submission_response")
    assert endpoint.index("maybe_delay_submission_response") < endpoint.rindex("return queued")
    frontend = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "src").rglob("*") if path.is_file()
    )
    assert "X-PocketLab-Gate" not in frontend


def test_group3_activation_cleanup_and_duplicate_execution_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load(GROUP3, "long_gate_group3_submission_test")
    ctx = SimpleNamespace(state_dir=tmp_path, run_id="pocketlab-long-gates-test")
    token = "d" * 32
    path = module.create_activation(ctx, token, 5000, lifetime_seconds=30)
    payload = json.loads(path.read_text())
    assert token not in path.read_text()
    assert payload["token_sha256"] == hashlib.sha256(token.encode()).hexdigest()
    assert module.disable_activation(ctx) is True
    assert not path.exists()
    rows = [
        {"run_id": "a", "command_id": "cmd", "status": "succeeded"},
        {"run_id": "a", "command_id": "cmd", "status": "succeeded"},
    ]
    assert module.duplicate_terminal_success(rows, "cmd") is False
    rows.append({"run_id": "b", "command_id": "cmd", "status": "completed"})
    assert module.duplicate_terminal_success(rows, "cmd") is True


def test_submission_resume_rediscovers_without_repeating_write():
    source = GROUP3.read_text(encoding="utf-8")
    resume_block = source.split('if state.get("activation_created"):', 1)[1].split('else:', 1)[0]
    assert "find_new_run" in resume_block
    assert "submit_quick" not in resume_block
    assert "refusing to resubmit" in resume_block
