import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


MODULE_PATH = Path("scripts/dev/lib/long_gate_s8.py")


def load_module():
    spec = importlib.util.spec_from_file_location(
        "long_gate_s8_loader_isolation",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_pm2_home(tmp_path: Path) -> Path:
    home = tmp_path / "host" / ".pm2"
    home.mkdir(parents=True)
    (home / "rpc.sock").touch()
    (home / "pub.sock").touch()
    return home


def worker_runtime_env(host_home: str) -> dict[str, object]:
    return {
        "HOME": host_home,
        "USER": "u0_a312",
        "LOGNAME": "u0_a312",
        "PREFIX": "/data/data/com.termux/files/usr",
        "TMPDIR": "/data/data/com.termux/files/usr/tmp",
        "PATH": "/data/data/com.termux/files/usr/bin",
        "PWD": f"{host_home}/pocket-lab-lite",
        "POCKETLAB_PROFILE": "lite",
        "POCKETLAB_STATE_DIR": f"{host_home}/pocket-lab-lite/state",
        "POCKETLAB_LITE_DB_PATH": (
            f"{host_home}/pocket-lab-lite/state/pocketlab-lite.sqlite3"
        ),
        "POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS": "0",
        "POCKETLAB_LITE_S8_FAULT_POINT": "",
        "LD_PRELOAD": (
            "/data/data/com.termux/files/usr/lib/"
            "libtermux-exec-ld-preload.so"
        ),
        "LD_LIBRARY_PATH": "/data/data/com.termux/files/usr/lib",
        "LIBRARY_PATH": "/data/data/com.termux/files/usr/lib",
        "CPATH": "/data/data/com.termux/files/usr/include",
        "C_INCLUDE_PATH": "/data/data/com.termux/files/usr/include",
        "CPLUS_INCLUDE_PATH": "/data/data/com.termux/files/usr/include/c++",
        "pocket-worker": {},
    }


def pm2_list(
    *,
    runtime_env: dict[str, object],
    status: str = "online",
    pid: int = 100,
    restart_time: int = 2,
    enabled: bool = False,
    point: str = "",
) -> str:
    env = dict(runtime_env)
    env["POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS"] = "1" if enabled else "0"
    env["POCKETLAB_LITE_S8_FAULT_POINT"] = point

    return json.dumps(
        [
            {
                "name": "pocket-worker",
                "pid": pid,
                "pm2_env": {
                    "status": status,
                    "restart_time": restart_time,
                    "username": "u0_a312",
                    "env": env,
                },
            }
        ]
    )


@pytest.mark.parametrize(
    "key",
    [
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "LIBRARY_PATH",
        "CPATH",
        "C_INCLUDE_PATH",
        "CPLUS_INCLUDE_PATH",
    ],
)
def test_string_environment_removes_cross_runtime_loader_variables(key):
    module = load_module()
    source = worker_runtime_env("/data/data/com.termux/files/home")

    sanitized = module._string_environment(source)

    assert key not in sanitized
    assert sanitized["HOME"] == "/data/data/com.termux/files/home"
    assert sanitized["PREFIX"] == "/data/data/com.termux/files/usr"
    assert sanitized["POCKETLAB_PROFILE"] == "lite"
    assert "pocket-worker" not in sanitized
    module._validate_subprocess_environment(sanitized)


def test_primary_restart_never_receives_loader_variables(monkeypatch, tmp_path):
    module = load_module()
    pm2_home = make_pm2_home(tmp_path)
    host_home = str(pm2_home.parent)
    baseline = worker_runtime_env(host_home)
    calls: list[tuple[list[str], dict[str, str]]] = []

    responses = iter(
        [
            subprocess.CompletedProcess(
                [],
                0,
                pm2_list(runtime_env=baseline),
                "",
            ),
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

    monkeypatch.setenv(
        "POCKETLAB_S8_GATE_WORKER_PM2_HOME",
        str(pm2_home),
    )

    def fake_run(command, **kwargs):
        calls.append((list(command), dict(kwargs["env"])))
        return next(responses)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module.configure_worker_fault("after_sqlite_promotion")

    restart_calls = [
        (command, env)
        for command, env in calls
        if "restart" in command
    ]
    assert len(restart_calls) == 1

    command, restart_env = restart_calls[0]
    assert command[-2:] == ["pocket-worker", "--update-env"]

    for key in (
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "LIBRARY_PATH",
        "CPATH",
        "C_INCLUDE_PATH",
        "CPLUS_INCLUDE_PATH",
    ):
        assert key not in restart_env

    assert restart_env["PM2_HOME"] == str(pm2_home)
    assert restart_env["HOME"] == host_home
    assert restart_env["POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS"] == "1"
    assert (
        restart_env["POCKETLAB_LITE_S8_FAULT_POINT"]
        == "after_sqlite_promotion"
    )


def test_recovery_restart_never_receives_loader_variables(monkeypatch, tmp_path):
    module = load_module()
    pm2_home = make_pm2_home(tmp_path)
    host_home = str(pm2_home.parent)
    baseline = worker_runtime_env(host_home)
    drifted = dict(baseline)
    drifted["HOME"] = "/root"
    drifted["USER"] = "root"
    calls: list[tuple[list[str], dict[str, str]]] = []

    responses = iter(
        [
            subprocess.CompletedProcess(
                [],
                0,
                pm2_list(runtime_env=baseline),
                "",
            ),
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

    monkeypatch.setenv(
        "POCKETLAB_S8_GATE_WORKER_PM2_HOME",
        str(pm2_home),
    )

    def fake_run(command, **kwargs):
        calls.append((list(command), dict(kwargs["env"])))
        return next(responses)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(module.GateError, match="identity drifted.*recovered"):
        module.configure_worker_fault("after_sqlite_promotion")

    restart_calls = [
        (command, env)
        for command, env in calls
        if "restart" in command
    ]
    assert len(restart_calls) == 2

    _, recovery_env = restart_calls[-1]

    for key in (
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "LIBRARY_PATH",
        "CPATH",
        "C_INCLUDE_PATH",
        "CPLUS_INCLUDE_PATH",
    ):
        assert key not in recovery_env

    assert recovery_env["PM2_HOME"] == str(pm2_home)
    assert recovery_env["HOME"] == host_home
    assert recovery_env["POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS"] == "0"
    assert recovery_env["POCKETLAB_LITE_S8_FAULT_POINT"] == ""
