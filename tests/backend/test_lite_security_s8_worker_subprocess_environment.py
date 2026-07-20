from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dev" / "lib" / "long_gate_s8.py"


def load_module():
    spec = importlib.util.spec_from_file_location("long_gate_s8_worker_env_safe", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_worker_env(home: str) -> dict[str, object]:
    return {
        "HOME": home,
        "USER": "u0_a312",
        "LOGNAME": "u0_a312",
        "PREFIX": "/data/data/com.termux/files/usr",
        "TMPDIR": "/data/data/com.termux/files/usr/tmp",
        "PATH": "/data/data/com.termux/files/usr/bin",
        "PWD": f"{home}/pocket-lab-lite",
        "POCKETLAB_STATE_DIR": f"{home}/pocket-lab-lite/state",
        "POCKETLAB_LITE_DB_PATH": f"{home}/pocket-lab-lite/state/pocketlab-lite.sqlite3",
        "POCKETLAB_PROFILE": "lite",
        "POCKETLAB_API_TOKEN": "preserved-but-never-reported",
    }


def test_string_environment_removes_nested_and_pm2_metadata():
    module = load_module()
    source = valid_worker_env("/data/data/com.termux/files/home")
    source.update(
        {
            "pocket-worker": {},
            "NODE_APP_INSTANCE": "45",
            "PM2_HOME": "/untrusted/.pm2",
            "PM2_USAGE": "CLI",
            "unique_id": "internal",
            "axm_options": "internal",
            "pm2_internal": "internal",
            "SCALAR_INT": 3,
            "SCALAR_BOOL": True,
        }
    )

    result = module._string_environment(source)

    assert result["HOME"] == "/data/data/com.termux/files/home"
    assert result["POCKETLAB_API_TOKEN"] == "preserved-but-never-reported"
    assert result["SCALAR_INT"] == "3"
    assert result["SCALAR_BOOL"] == "True"
    for key in (
        "pocket-worker",
        "NODE_APP_INSTANCE",
        "PM2_HOME",
        "PM2_USAGE",
        "unique_id",
        "axm_options",
        "pm2_internal",
    ):
        assert key not in result


def test_string_environment_removes_invalid_posix_entries():
    module = load_module()
    source = valid_worker_env("/data/data/com.termux/files/home")
    source.update(
        {
            "": "empty-key",
            "BAD=KEY": "value",
            "NUL_KEY\x00": "value",
            "NUL_VALUE": "bad\x00value",
            "NONE_VALUE": None,
            "LIST_VALUE": ["bad"],
        }
    )

    result = module._string_environment(source)

    assert "" not in result
    assert "BAD=KEY" not in result
    assert "NUL_KEY\x00" not in result
    assert "NUL_VALUE" not in result
    assert "NONE_VALUE" not in result
    assert "LIST_VALUE" not in result


def test_worker_identity_accepts_sanitized_termux_environment(tmp_path):
    module = load_module()
    pm2_home = tmp_path / ".pm2"
    pm2_home.mkdir()
    runtime = module._string_environment(valid_worker_env(str(tmp_path)))
    runtime["PREFIX"] = "/data/data/com.termux/files/usr"
    runtime["TMPDIR"] = "/data/data/com.termux/files/usr/tmp"
    runtime["PATH"] = "/data/data/com.termux/files/usr/bin"

    identity = module._validate_worker_identity(
        runtime_env=runtime,
        control_env={"PM2_HOME": str(pm2_home)},
    )

    assert identity["HOME"] == str(tmp_path)


def test_worker_identity_rejects_database_outside_state(tmp_path):
    module = load_module()
    pm2_home = tmp_path / ".pm2"
    pm2_home.mkdir()
    runtime = module._string_environment(valid_worker_env(str(tmp_path)))
    runtime["POCKETLAB_LITE_DB_PATH"] = f"{tmp_path}/other/pocketlab-lite.sqlite3"

    with pytest.raises(module.GateError, match="database path is outside"):
        module._validate_worker_identity(
            runtime_env=runtime,
            control_env={"PM2_HOME": str(pm2_home)},
        )
