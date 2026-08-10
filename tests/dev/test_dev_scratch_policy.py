from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "scripts" / "dev" / "lite" / "dev-scratch.sh"


def test_dev_scratch_policy_defaults_to_repo_local_namespace():
    env = os.environ.copy()
    env.pop("POCKETLAB_DEV_TMPDIR", None)
    result = subprocess.run(
        ["bash", str(POLICY), "path", "pytest"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout.strip()) == (
        ROOT / ".pocketlab-dev" / "tmp" / "pytest"
    ).resolve()


def test_dev_scratch_policy_honors_explicit_root_override(tmp_path):
    root = tmp_path / "custom-scratch"
    env = os.environ.copy()
    env["POCKETLAB_DEV_TMPDIR"] = str(root)
    result = subprocess.run(
        ["bash", str(POLICY), "path", "schemaspy"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout.strip()) == (root / "schemaspy").resolve()


def test_dev_scratch_policy_rejects_path_traversal_namespace():
    result = subprocess.run(
        ["bash", str(POLICY), "path", "../escape"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "invalid scratch namespace" in result.stderr


def test_shared_dev_scratch_contract_is_wired_to_heavy_consumers():
    """Heavy dev tooling must consume the shared scratch policy correctly."""
    taskfile = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")
    policy = (
        ROOT / "scripts" / "dev" / "lite" / "dev-scratch.sh"
    ).read_text(encoding="utf-8")
    gate = (
        ROOT / "scripts" / "dev" / "lite" / "run-gate.sh"
    ).read_text(encoding="utf-8")
    playwright = (
        ROOT / "playwright.docs.config.ts"
    ).read_text(encoding="utf-8")
    schemaspy = (
        ROOT / "scripts" / "docs" / "sqlite" / "generate_schemaspy.py"
    ).read_text(encoding="utf-8")
    security = (
        ROOT
        / "scripts"
        / "dev"
        / "lite"
        / "documentation_security_tools.py"
    ).read_text(encoding="utf-8")
    conftest = (
        ROOT / "conftest.py"
    ).read_text(encoding="utf-8")

    # Canonical ownership of the shared variable belongs to the root
    # Taskfile and reusable scratch helper.
    assert "POCKETLAB_DEV_TMPDIR" in taskfile
    assert "POCKETLAB_DEV_TMPDIR" in policy

    # run-gate.sh consumes the policy by sourcing the helper and activating
    # a namespaced environment. It intentionally does not duplicate the
    # POCKETLAB_DEV_TMPDIR implementation.
    assert 'source "$SCRIPT_DIR/dev-scratch.sh"' in gate
    assert 'pocketlab_dev_scratch_activate "gate-${TIER}"' in gate

    # Direct consumers derive their own namespaced scratch locations from
    # the shared root.
    assert "POCKETLAB_DEV_TMPDIR" in playwright
    assert "POCKETLAB_DEV_TMPDIR" in schemaspy
    assert "POCKETLAB_DEV_TMPDIR" in security
    assert "POCKETLAB_DEV_TMPDIR" in conftest

    assert "'playwright'" in playwright
    assert '"schemaspy"' in schemaspy
    assert '"security-tools"' in security
    assert 'root / "pytest"' in conftest

    # The reusable helper must export standard tempfile variables for child
    # processes, including MkDocs, Playwright, Python, and Node tooling.
    assert 'export POCKETLAB_DEV_TMPDIR="$root"' in policy
    assert 'export TMPDIR="$path"' in policy
    assert 'export TMP="$path"' in policy
    assert 'export TEMP="$path"' in policy

def test_scratch_helper_is_development_only_and_does_not_touch_runtime():
    source = POLICY.read_text(encoding="utf-8")
    forbidden = (
        "pocketlab_node_agent.py",
        "pocketlab_agent_supervisor.py",
        "POCKETLAB_NATS_URL=",
        "POCKETLAB_STATE_DIR=",
        "pm2 restart",
        "tailscale up",
    )
    assert not any(item in source for item in forbidden)


def test_mkdocs_serve_executes_inside_docs_scratch_namespace():
    """Task delegates to one wrapper that owns MkDocs scratch execution."""
    taskfile = (
        ROOT / "tasks" / "Taskfile.docs.yml"
    ).read_text(encoding="utf-8")
    wrapper = (
        ROOT / "scripts" / "dev" / "lite" / "serve-docs.sh"
    ).read_text(encoding="utf-8")

    # Extract only the lite:docs:serve task block.
    start = taskfile.find("  lite:docs:serve:")
    assert start >= 0

    remainder = taskfile[start:]

    import re

    next_task = re.search(
        r"\n  [A-Za-z0-9_.:-]+:\s*\n",
        remainder[1:],
    )

    if next_task:
        end = 1 + next_task.start()
        serve = remainder[:end]
    else:
        serve = remainder

    # Task is orchestration only. It must delegate to the canonical wrapper.
    assert "lite:dev:scratch:prepare" in serve
    assert "scripts/dev/lite/serve-docs.sh" in serve

    # Do not duplicate the MkDocs/scratch implementation in the Taskfile.
    assert "dev-scratch.sh run docs --" not in serve
    assert "{{.PYTHON}} -m mkdocs serve" not in serve

    # The wrapper owns scratch activation and MkDocs execution.
    assert 'dev-scratch.sh" run docs --' in wrapper
    assert '"$PYTHON" -m mkdocs serve' in wrapper
    assert "--strict" in wrapper
    assert "POCKETLAB_DOCS_DEV_ADDR" in wrapper

    # The wrapper must resolve and enter the repository before execution.
    assert 'REPO_ROOT=' in wrapper
    assert 'cd "$REPO_ROOT"' in wrapper
