from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/docs/release_model.py"
spec = importlib.util.spec_from_file_location("release_model_test", MODULE_PATH)
release_model = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(release_model)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def make_repo(tmp_path: Path) -> tuple[Path, list[dict[str, str]]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "docs@example.invalid")
    git(repo, "config", "user.name", "Docs Test")
    rows = []
    for idx, tag in enumerate(("lite-2026.08.12.2", "lite-2026.08.20.1"), 1):
        (repo / "sample.txt").write_text(f"release-{idx}\n", encoding="utf-8")
        git(repo, "add", "sample.txt")
        git(repo, "commit", "-q", "-m", f"release {idx}")
        commit = git(repo, "rev-parse", "HEAD")
        tree = git(repo, "rev-parse", "HEAD^{tree}")
        git(repo, "tag", tag)
        rows.append({
            "release_tag": tag,
            "source_commit": commit,
            "tree_hash": tree,
            "verification_status": "promoted",
            "published_at": f"2026-08-{12 if idx == 1 else 20:02d}T12:00:00Z",
        })
    return repo, rows


def write_promoted(repo: Path, rows: list[dict[str, str]]) -> None:
    path = repo / release_model.PROMOTED_RELEASE_EVIDENCE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "1.0.0", "releases": rows}), encoding="utf-8")


def test_one_verified_release_establishes_baseline_without_release_to_head(tmp_path: Path):
    repo, rows = make_repo(tmp_path)
    write_promoted(repo, rows[:1])
    state = release_model.comparison_state(repo)
    assert state["comparison_state"] == "baseline-only"
    assert state["baseline"] is None
    assert state["current"]["tag"] == "lite-2026.08.12.2"
    assert "release-to-HEAD comparison is forbidden" in state["baseline_policy"]


def test_two_verified_local_release_tags_enable_release_to_release_comparison(tmp_path: Path):
    repo, rows = make_repo(tmp_path)
    write_promoted(repo, rows)
    state = release_model.comparison_state(repo)
    assert state["comparison_state"] == "comparable"
    assert state["baseline"]["tag"] == "lite-2026.08.12.2"
    assert state["current"]["tag"] == "lite-2026.08.20.1"


def test_mismatched_local_tag_fails_closed_instead_of_using_head(tmp_path: Path):
    repo, rows = make_repo(tmp_path)
    rows[1] = {**rows[1], "tree_hash": "f" * 40}
    write_promoted(repo, rows)
    state = release_model.comparison_state(repo)
    # The mismatched record is not eligible for a verified comparison; no worktree/HEAD fallback occurs.
    assert state["comparison_state"] == "comparison-evidence-unavailable"
    assert state["baseline"]["tag"] == "lite-2026.08.12.2"
    assert state["current"]["tag"] == "lite-2026.08.20.1"
    assert "matching local Git tags" in state["reason"]
