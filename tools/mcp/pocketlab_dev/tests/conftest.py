from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture()
def repository_root(tmp_path: Path) -> Path:
    root = tmp_path / "pocket-lab-lite"
    (root / ".git").mkdir(parents=True)
    (root / "engineering" / "codex").mkdir(parents=True)
    (root / "AGENTS.md").write_text("test contract\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def initialize_git_repository(root: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Pocket Lab Tests"], cwd=root, check=True)
    (root / "README.md").write_text("initial\n", encoding="utf-8")
    # The repository markers are part of the clean baseline, not changes under
    # test. Stage all fixture content before the initial commit.
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
    return root
