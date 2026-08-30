from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pocketlab_dev_mcp import config
from pocketlab_dev_mcp.config import RepositoryRootError, validate_repository_root
from pocketlab_dev_mcp.tools.repository import RepositoryTools, classify_path

from .conftest import initialize_git_repository


def test_repo_status_handles_clean_untracked_and_detached_head(repository_root):
    root = initialize_git_repository(repository_root)
    tools = RepositoryTools(root)
    clean = tools.repo_status()
    assert clean["clean"] is True
    assert clean["origin_main"] is None
    (root / "tools" / "new.py").parent.mkdir()
    (root / "tools" / "new.py").write_text("x = 1\n", encoding="utf-8")
    changed = tools.repo_status()
    assert changed["untracked_count"] == 1
    subprocess.run(["git", "add", "tools/new.py"], cwd=root, check=True)
    assert tools.repo_status()["staged_count"] == 1
    subprocess.run(["git", "checkout", "--detach"], cwd=root, check=True, capture_output=True)
    assert tools.repo_status()["detached_head"] is True


def test_changed_files_covers_working_tree_and_missing_origin(repository_root):
    root = initialize_git_repository(repository_root)
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    tools = RepositoryTools(root)
    working_tree = tools.changed_files()
    assert working_tree["total"] == 1
    assert working_tree["files"][0]["category"] == "docs"
    comparison = tools.changed_files("branch_vs_origin_main")
    assert comparison["status"] == "error"


def test_changed_files_branch_comparison_and_path_classification(repository_root):
    root = initialize_git_repository(repository_root)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=root, check=True)
    (root / "scripts").mkdir()
    (root / "scripts" / "tool.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts/tool.sh"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "tool"], cwd=root, check=True)
    comparison = RepositoryTools(root).changed_files("branch_vs_origin_main")
    assert comparison["total"] == 1
    assert comparison["files"][0]["category"] == "scripts"
    status = RepositoryTools(root).repo_status()
    assert status["ahead"] == 1
    assert status["behind"] == 0
    assert classify_path("runtime/api.py") == "backend"
    assert classify_path("frontend/src/main.ts") == "frontend"


def test_changed_files_is_nul_safe_for_unusual_names_rename_and_delete(repository_root):
    root = initialize_git_repository(repository_root)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=root, check=True)
    unusual = ["docs/file with spaces.md", "docs/file\twith-tab.md", "docs/file\nwith-newline.md"]
    for name in unusual:
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("new\n", encoding="utf-8")
    working = RepositoryTools(root).changed_files()
    assert {entry["path"] for entry in working["files"]} == set(unusual)
    assert working["complete"] is True
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "unusual paths"], cwd=root, check=True)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=root, check=True)
    renamed_from = root / unusual[0]
    renamed_to = root / "docs/renamed file.md"
    subprocess.run(["git", "mv", str(renamed_from.relative_to(root)), str(renamed_to.relative_to(root))], cwd=root, check=True)
    (root / "README.md").unlink()
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "rename and delete"], cwd=root, check=True)
    comparison = RepositoryTools(root).changed_files("branch_vs_origin_main")
    by_path = {entry["path"]: entry["status"] for entry in comparison["files"]}
    assert by_path["docs/renamed file.md"] == "renamed"
    assert by_path["README.md"] == "deleted"


def test_git_output_truncation_is_explicit(repository_root):
    root = initialize_git_repository(repository_root)
    for index in range(300):
        (root / f"docs/long-{index:03d}-{'x' * 48}.md").parent.mkdir(exist_ok=True)
        (root / f"docs/long-{index:03d}-{'x' * 48}.md").write_text("x\n", encoding="utf-8")
    tools = RepositoryTools(root)
    status = tools.repo_status()
    changed = tools.changed_files()
    assert status["complete"] is False
    assert status["truncated"] is True
    assert changed["status"] == "incomplete"
    assert changed["complete"] is False
    assert changed["truncated"] is True


def test_repository_root_requires_matching_native_git_top_level(repository_root, tmp_path: Path, monkeypatch):
    root = initialize_git_repository(repository_root)
    assert validate_repository_root(root) == root.resolve()
    fake = tmp_path / "marker-only"
    (fake / ".git").mkdir(parents=True)
    (fake / "engineering" / "codex").mkdir(parents=True)
    (fake / "AGENTS.md").write_text("marker\n", encoding="utf-8")
    with pytest.raises(RepositoryRootError):
        validate_repository_root(fake)
    nested = root / "nested"
    (nested / ".git").mkdir(parents=True)
    (nested / "engineering" / "codex").mkdir(parents=True)
    (nested / "AGENTS.md").write_text("marker\n", encoding="utf-8")
    monkeypatch.setattr(config, "_git_top_level", lambda candidate: root.resolve())
    with pytest.raises(RepositoryRootError):
        validate_repository_root(nested)


def test_changed_files_preserves_first_character_of_unstaged_first_record(tmp_path):
    """Porcelain leading status spaces must not eat the first path character."""
    import subprocess

    from pocketlab_dev_mcp.tools.repository import RepositoryTools

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    git("init")
    git("config", "user.name", "Pocket Lab Test")
    git("config", "user.email", "pocketlab-test@example.invalid")

    target = repo / "contracts/generated/api-compatibility.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"state":"before"}\n', encoding="utf-8")

    git("add", "contracts/generated/api-compatibility.json")
    git("commit", "-m", "baseline")

    # Working-tree-only modification deliberately produces:
    #   " M contracts/generated/api-compatibility.json"
    target.write_text('{"state":"after"}\n', encoding="utf-8")

    result = RepositoryTools(repo).changed_files("working_tree")

    paths = {entry["path"] for entry in result["files"]}

    assert "contracts/generated/api-compatibility.json" in paths
    assert "ontracts/generated/api-compatibility.json" not in paths
    assert result["complete"] is True
    assert result["truncated"] is False


def test_changed_files_preserves_first_character_of_unstaged_first_record(tmp_path):
    """Porcelain leading status spaces must not eat the first path character."""
    import subprocess

    from pocketlab_dev_mcp.tools.repository import RepositoryTools

    repo = tmp_path / "repo"
    repo.mkdir()

    # Satisfy the production Pocket Lab repository-root validation contract.
    (repo / "AGENTS.md").write_text("# test repository\n", encoding="utf-8")
    (repo / "engineering/codex").mkdir(parents=True)
    (repo / "engineering/codex/README.md").write_text(
        "# Codex test marker\n",
        encoding="utf-8",
    )

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    git("init")
    git("config", "user.name", "Pocket Lab Test")
    git("config", "user.email", "pocketlab-test@example.invalid")

    target = repo / "contracts/generated/api-compatibility.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"state":"before"}\n', encoding="utf-8")

    git(
        "add",
        "AGENTS.md",
        "engineering/codex/README.md",
        "contracts/generated/api-compatibility.json",
    )
    git("commit", "-m", "baseline")

    # Working-tree-only modification deliberately produces:
    #   " M contracts/generated/api-compatibility.json"
    target.write_text('{"state":"after"}\n', encoding="utf-8")

    result = RepositoryTools(repo).changed_files("working_tree")

    paths = {entry["path"] for entry in result["files"]}

    assert "contracts/generated/api-compatibility.json" in paths
    assert "ontracts/generated/api-compatibility.json" not in paths
    assert result["complete"] is True
    assert result["truncated"] is False
