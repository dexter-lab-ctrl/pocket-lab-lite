from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dev" / "lite" / "task_runtime.py"


def _module():
    spec = importlib.util.spec_from_file_location("pocketlab_task_runtime", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dev_pc_keeps_repository_python_and_dev_environment():
    module = _module()
    parser_args = type("Args", (), {"mode": "python", "dev_python": ".venv/bin/python", "command": ["scripts/dev/lite/harness.py", "status"]})()
    env = {
        "PATH": os.environ.get("PATH", ""),
        "POCKETLAB_ENV": "dev",
        "POCKETLAB_STATE_DIR": ".pocketlab-dev/state",
        "STATE_DIR": ".pocketlab-dev/state",
    }
    command, child = module.build_command(parser_args, env)
    assert command[0] == ".venv/bin/python"
    assert child["POCKETLAB_ENV"] == "dev"
    assert child["POCKETLAB_STATE_DIR"] == ".pocketlab-dev/state"
    assert child["STATE_DIR"] == ".pocketlab-dev/state"


def test_termux_uses_installed_python_and_removes_dev_state(monkeypatch):
    module = _module()
    monkeypatch.setattr(module.shutil, "which", lambda name, path=None: "/runtime/python3" if name == "python3" else None)
    parser_args = type("Args", (), {"mode": "python", "dev_python": ".venv/bin/python", "command": ["scripts/dev/lite/harness.py", "status"]})()
    env = {
        "TERMUX_VERSION": "0.119",
        "PATH": "/runtime",
        "POCKETLAB_ENV": "dev",
        "POCKETLAB_ENVIRONMENT": "dev",
        "POCKETLAB_STATE_DIR": ".pocketlab-dev/state",
        "STATE_DIR": ".pocketlab-dev/state",
        "VALIDATION_DIR": ".pocketlab-dev/validation",
        "POCKETLAB_DEV_PYTHON": ".venv/bin/python",
    }
    command, child = module.build_command(parser_args, env)
    assert command[0] == "/runtime/python3"
    for key in (*module.DEV_ONLY_ENV, "POCKETLAB_ENVIRONMENT"):
        assert key not in child
    assert ".venv/bin/python" not in command


def test_termux_qualification_scrubs_dev_state_before_launcher(monkeypatch):
    module = _module()
    monkeypatch.setattr(module.shutil, "which", lambda name, path=None: "/runtime/bash" if name == "bash" else None)
    parser_args = type("Args", (), {"mode": "shell", "dev_python": ".venv/bin/python", "command": ["scripts/dev/lite/start-qualification.sh", "--bootstrap-profile", "security-assurance-runner"]})()
    command, child = module.build_command(
        parser_args,
        {
            "TERMUX_VERSION": "0.119",
            "PATH": "/runtime",
            "POCKETLAB_ENV": "dev",
            "POCKETLAB_ENVIRONMENT": "dev",
            "POCKETLAB_STATE_DIR": ".pocketlab-dev/state",
            "STATE_DIR": ".pocketlab-dev/state",
        },
    )
    assert command[0] == "/runtime/bash"
    assert "POCKETLAB_STATE_DIR" not in child
    assert "STATE_DIR" not in child
    assert "POCKETLAB_ENV" not in child
    assert "POCKETLAB_ENVIRONMENT" not in child


def test_runtime_launcher_owns_state_and_opa_path_after_scrub():
    text = (ROOT / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "start-dashboard.sh").read_text(encoding="utf-8")
    assert 'export POCKETLAB_ENVIRONMENT="${POCKETLAB_ENVIRONMENT:-production}"' in text
    assert 'export POCKETLAB_STATE_DIR="${POCKETLAB_STATE_DIR:-$POCKETLAB_BASE_DIR/state}"' in text
    assert 'export POCKETLAB_OPA_ACTIVE_POLICY_DIR="${POCKETLAB_OPA_ACTIVE_POLICY_DIR:-$POCKETLAB_STATE_DIR/opa/active}"' in text
    assert ".pocketlab-dev/state/opa/active" not in text


def test_qualification_launcher_explicitly_sets_qualification_environment():
    text = (ROOT / "scripts" / "dev" / "lite" / "start-qualification.sh").read_text(encoding="utf-8")
    assert "export POCKETLAB_ENVIRONMENT=qualification" in text
    assert "export POCKETLAB_HARNESS_ENABLED=1" in text
