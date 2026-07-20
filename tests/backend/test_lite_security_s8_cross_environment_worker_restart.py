from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dev" / "lib" / "long_gate_s8.py"


def load_module():
    spec = importlib.util.spec_from_file_location("long_gate_s8_cross_pm2", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pm2_list(*, status="online", pid=100, restart_time=2, enabled=False, point=""):
    configured_pm2_home = os.environ.get(
        "POCKETLAB_S8_GATE_WORKER_PM2_HOME",
        "/tmp/pocketlab-test/.pm2",
    )
    runtime_home = str(Path(configured_pm2_home).parent)

    runtime_env = {
        "HOME": runtime_home,
        "USER": "u0_a312",
        "LOGNAME": "u0_a312",
        "PREFIX": "/termux/usr",
        "TMPDIR": "/termux/usr/tmp",
        "PATH": "/termux/usr/bin",
        "PWD": f"{runtime_home}/pocket-lab-lite",
        "POCKETLAB_STATE_DIR": f"{runtime_home}/pocket-lab-lite/state",
        "POCKETLAB_LITE_DB_PATH": (
            f"{runtime_home}/pocket-lab-lite/state/pocketlab-lite.sqlite3"
        ),
        "POCKETLAB_PROFILE": "lite",
        "POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS": "1" if enabled else "0",
        "POCKETLAB_LITE_S8_FAULT_POINT": point,
    }

    return json.dumps(
        [
            {
                "name": "pocket-worker",
                "pid": pid,
                "pm2_env": {
                    "status": status,
                    "restart_time": restart_time,
                    "username": "u0_a312",
                    "env": runtime_env,
                },
            }
        ]
    )


def make_pm2_home(tmp_path: Path) -> Path:
    home = tmp_path / ".pm2"
    home.mkdir()
    (home / "rpc.sock").touch()
    (home / "pub.sock").touch()
    return home


def test_explicit_host_pm2_context_is_used_for_restart(monkeypatch, tmp_path):
    module = load_module()
    home = make_pm2_home(tmp_path)
    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(home))
    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_BIN", "/termux/bin/pm2")
    calls = []
    responses = iter([
        subprocess.CompletedProcess([], 0, pm2_list(), ""),
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, pm2_list(pid=101, restart_time=3, enabled=True, point="after_sqlite_promotion"), ""),
    ])
    def fake_run(command, **kwargs):
        calls.append((command, kwargs["env"].copy()))
        return next(responses)
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    module.configure_worker_fault("after_sqlite_promotion")
    assert calls[0][0] == ["/termux/bin/pm2", "jlist"]
    assert calls[1][0] == ["/termux/bin/pm2", "restart", "pocket-worker", "--update-env"]
    assert all(call_env["PM2_HOME"] == str(home) for _, call_env in calls)


def test_proot_root_fails_closed_without_explicit_pm2_home(monkeypatch):
    module = load_module()
    monkeypatch.delenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", raising=False)
    monkeypatch.setattr(module.Path, "home", classmethod(lambda cls: Path("/root")))
    with pytest.raises(module.GateError, match="requires POCKETLAB_S8_GATE_WORKER_PM2_HOME"):
        module._worker_pm2_context()


def test_wrong_or_empty_pm2_daemon_is_rejected(monkeypatch, tmp_path):
    module = load_module()
    home = make_pm2_home(tmp_path)
    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(home))
    monkeypatch.setattr(module.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 0, "[]", ""))
    with pytest.raises(module.GateError, match="pocket-worker is unavailable"):
        module.worker_fault_environment()


def test_fault_environment_uses_same_host_context(monkeypatch, tmp_path):
    module = load_module()
    home = make_pm2_home(tmp_path)
    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(home))
    seen = {}
    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs["env"].copy()
        return subprocess.CompletedProcess([], 0, pm2_list(enabled=True, point="after_sqlite_promotion"), "")
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.worker_fault_environment()
    assert seen["command"][-1] == "jlist"
    assert seen["env"]["PM2_HOME"] == str(home)
    assert result == {
        "checked": True,
        "enabled": True,
        "point": "after_sqlite_promotion",
        "sanitized": True,
    }
    assert "PM2_HOME" not in result


def test_restart_waits_for_requested_environment(monkeypatch, tmp_path):
    module = load_module()
    home = make_pm2_home(tmp_path)
    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(home))
    responses = iter([
        subprocess.CompletedProcess([], 0, pm2_list(), ""),
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, pm2_list(status="launching", pid=0), ""),
        subprocess.CompletedProcess([], 0, pm2_list(pid=101, restart_time=3, enabled=False), ""),
        subprocess.CompletedProcess([], 0, pm2_list(pid=101, restart_time=3, enabled=True, point="after_sqlite_promotion"), ""),
    ])
    monkeypatch.setattr(module.subprocess, "run", lambda *_a, **_k: next(responses))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    module.configure_worker_fault("after_sqlite_promotion")
