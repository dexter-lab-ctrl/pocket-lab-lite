from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path

from scripts.docs.check_security_assurance_playbooks import ROOT, collect_errors


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_security_assurance_playbook_contract_is_current_and_complete():
    assert collect_errors() == []


def test_security_assurance_new_python_sources_parse():
    for relative in (
        "scripts/dev/lite/task_runtime.py",
        "scripts/dev/lite/security_assurance_report.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_phone_task_wrapper_preserves_dev_and_scrubs_termux(monkeypatch):
    module = _load(ROOT / "scripts/dev/lite/task_runtime.py", "pocketlab_task_runtime_docs_test")
    args = type("Args", (), {"mode": "python", "dev_python": ".venv/bin/python", "command": ["scripts/dev/lite/harness.py", "status"]})()
    dev_env = {
        "PATH": os.environ.get("PATH", ""),
        "POCKETLAB_ENV": "dev",
        "POCKETLAB_STATE_DIR": ".pocketlab-dev/state",
        "STATE_DIR": ".pocketlab-dev/state",
    }
    dev_command, dev_child = module.build_command(args, dev_env)
    assert dev_command[0] == ".venv/bin/python"
    assert dev_child["POCKETLAB_STATE_DIR"] == ".pocketlab-dev/state"
    assert dev_child["POCKETLAB_ENV"] == "dev"

    monkeypatch.setattr(module.shutil, "which", lambda name, path=None: "/runtime/python3" if name == "python3" else None)
    phone_command, phone_child = module.build_command(
        args,
        {
            "TERMUX_VERSION": "0.119",
            "PATH": "/runtime",
            "POCKETLAB_ENV": "dev",
            "POCKETLAB_ENVIRONMENT": "dev",
            "POCKETLAB_STATE_DIR": ".pocketlab-dev/state",
            "STATE_DIR": ".pocketlab-dev/state",
            "TMPDIR": ".pocketlab-dev/tmp",
        },
    )
    assert phone_command[0] == "/runtime/python3"
    assert "POCKETLAB_STATE_DIR" not in phone_child
    assert "POCKETLAB_ENV" not in phone_child
    assert "POCKETLAB_ENVIRONMENT" not in phone_child
    assert "TMPDIR" not in phone_child
