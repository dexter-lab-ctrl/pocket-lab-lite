from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dev" / "lib" / "long_gate_s8.py"


def load_module():
    spec = importlib.util.spec_from_file_location("long_gate_s8_env_preservation", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_pm2_home(tmp_path: Path) -> Path:
    home = tmp_path / ".pm2"
    home.mkdir()
    (home / "rpc.sock").touch()
    (home / "pub.sock").touch()
    return home


def worker_env(*, home: str, **overrides: str) -> dict[str, str]:
    env = {
        "HOME": home,
        "USER": "u0_a312",
        "LOGNAME": "u0_a312",
        "PREFIX": "/termux/usr",
        "TMPDIR": "/termux/usr/tmp",
        "PATH": "/termux/usr/bin",
        "PWD": f"{home}/pocket-lab-lite",
        "POCKETLAB_STATE_DIR": f"{home}/pocket-lab-lite/state",
        "POCKETLAB_LITE_DB_PATH": f"{home}/pocket-lab-lite/state/pocketlab-lite.sqlite3",
        "POCKETLAB_PROFILE": "lite",
        "POCKETLAB_API_TOKEN": "must-not-leak",
        "POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS": "0",
        "POCKETLAB_LITE_S8_FAULT_POINT": "",
    }
    env.update(overrides)
    return env


def pm2_list(
    *,
    runtime_env: dict[str, str],
    status: str = "online",
    pid: int = 100,
    restart_time: int = 2,
    enabled: bool = False,
    point: str = "",
) -> str:
    process_env = dict(runtime_env)
    process_env["POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS"] = "1" if enabled else "0"
    process_env["POCKETLAB_LITE_S8_FAULT_POINT"] = point
    return json.dumps(
        [
            {
                "name": "pocket-worker",
                "pid": pid,
                "pm2_env": {
                    "status": status,
                    "restart_time": restart_time,
                    "username": "u0_a312",
                    "env": process_env,
                },
            }
        ]
    )


def test_proot_controller_identity_is_not_forwarded(monkeypatch, tmp_path):
    module = load_module()
    pm2_home = make_pm2_home(tmp_path)
    host_home = str(pm2_home.parent)
    baseline = worker_env(home=host_home)

    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(pm2_home))
    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_BIN", "/termux/bin/pm2")
    monkeypatch.setenv("HOME", "/root")
    monkeypatch.setenv("USER", "root")
    monkeypatch.setenv("PATH", "/usr/bin")

    calls: list[tuple[list[str], dict[str, str]]] = []
    responses = iter(
        [
            subprocess.CompletedProcess([], 0, pm2_list(runtime_env=baseline), ""),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess(
                [],
                0,
                pm2_list(
                    runtime_env=baseline,
                    pid=101,
                    restart_time=3,
                    enabled=True,
                    point="after_sqlite_promotion",
                ),
                "",
            ),
        ]
    )

    def fake_run(command, **kwargs):
        calls.append((command, kwargs["env"].copy()))
        return next(responses)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module.configure_worker_fault("after_sqlite_promotion")

    restart_env = calls[1][1]
    assert restart_env["PM2_HOME"] == str(pm2_home)
    assert restart_env["HOME"] == host_home
    assert restart_env["USER"] == "u0_a312"
    assert restart_env["PATH"] == "/termux/usr/bin"
    assert restart_env["PREFIX"] == "/termux/usr"
    assert restart_env["TMPDIR"] == "/termux/usr/tmp"
    assert restart_env["POCKETLAB_STATE_DIR"] == f"{host_home}/pocket-lab-lite/state"
    assert restart_env["POCKETLAB_LITE_DB_PATH"].endswith("pocketlab-lite.sqlite3")
    assert restart_env["POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS"] == "1"
    assert restart_env["POCKETLAB_LITE_S8_FAULT_POINT"] == "after_sqlite_promotion"


def test_host_home_mismatch_fails_before_restart(monkeypatch, tmp_path):
    module = load_module()
    pm2_home = make_pm2_home(tmp_path)
    contaminated = worker_env(home="/root", USER="root")
    calls: list[list[str]] = []

    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(pm2_home))

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess([], 0, pm2_list(runtime_env=contaminated), "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(module.GateError, match="runtime HOME does not match"):
        module.configure_worker_fault("after_sqlite_promotion")

    assert calls == [["pm2", "jlist"]]


def test_runtime_identity_drift_is_recovered_and_fails_closed(monkeypatch, tmp_path):
    module = load_module()
    pm2_home = make_pm2_home(tmp_path)
    host_home = str(pm2_home.parent)
    baseline = worker_env(home=host_home)
    drifted = worker_env(home="/root", USER="root", PATH="/usr/bin")
    calls: list[tuple[list[str], dict[str, str]]] = []
    responses = iter(
        [
            subprocess.CompletedProcess([], 0, pm2_list(runtime_env=baseline), ""),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess(
                [],
                0,
                pm2_list(
                    runtime_env=drifted,
                    pid=101,
                    restart_time=3,
                    enabled=True,
                    point="after_sqlite_promotion",
                ),
                "",
            ),
            subprocess.CompletedProcess([], 0, "", ""),
        ]
    )

    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(pm2_home))

    def fake_run(command, **kwargs):
        calls.append((command, kwargs["env"].copy()))
        return next(responses)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(module.GateError, match="identity drifted.*recovered"):
        module.configure_worker_fault("after_sqlite_promotion")

    recovery_env = calls[-1][1]
    assert recovery_env["HOME"] == host_home
    assert recovery_env["USER"] == "u0_a312"
    assert recovery_env["PATH"] == "/termux/usr/bin"
    assert recovery_env["POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS"] == "0"
    assert recovery_env["POCKETLAB_LITE_S8_FAULT_POINT"] == ""


def test_public_fault_state_remains_sanitized(monkeypatch, tmp_path):
    module = load_module()
    pm2_home = make_pm2_home(tmp_path)
    baseline = worker_env(home=str(pm2_home.parent))

    monkeypatch.setenv("POCKETLAB_S8_GATE_WORKER_PM2_HOME", str(pm2_home))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            0,
            pm2_list(
                runtime_env=baseline,
                enabled=True,
                point="after_sqlite_promotion",
            ),
            "",
        ),
    )

    result = module.worker_fault_environment()

    assert result == {
        "checked": True,
        "enabled": True,
        "point": "after_sqlite_promotion",
        "sanitized": True,
    }
    assert "must-not-leak" not in json.dumps(result)
