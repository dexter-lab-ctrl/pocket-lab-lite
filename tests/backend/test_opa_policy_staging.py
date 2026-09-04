from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_policy_staging_tolerates_format_only_diff(tmp_path: Path) -> None:
    """A style-only Rego diff must not block governed runtime staging."""
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "lite"
        / "prepare-opa-policy.sh"
    )
    source = tmp_path / "policy"
    source.mkdir()
    (source / "policy.rego").write_text(
        "package pocketlab.test\n\nallow if { true }\n",
        encoding="utf-8",
    )

    fake_opa = tmp_path / "opa"
    fake_opa.write_text(
        """#!/usr/bin/env bash
set -eu
cmd="${1:-}"
shift || true
case "$cmd" in
  fmt)
    for arg in "$@"; do
      if [[ "$arg" == "--fail" ]]; then
        echo "unexpected diff" >&2
        exit 42
      fi
    done
    exit 0
    ;;
  check|test)
    exit 0
    ;;
  *)
    exit 64
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_opa.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "POCKETLAB_OPA_BIN": str(fake_opa),
            "POCKETLAB_OPA_POLICY_SOURCE_DIR": str(source),
            "POCKETLAB_STATE_DIR": str(tmp_path / "state"),
            "POCKETLAB_POLICY_REVISION": "plr-format-only-regression",
        }
    )
    result = subprocess.run(
        ["bash", str(script), "stage"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "OPA candidate staged revision=plr-format-only-regression" in result.stdout
    stage = tmp_path / "state" / "opa" / "stage" / "plr-format-only-regression"
    assert (stage / "manifest.json").is_file()
    assert (stage / "policy.rego").read_text(encoding="utf-8") == (source / "policy.rego").read_text(encoding="utf-8")


def test_policy_staging_keeps_semantic_gates() -> None:
    """The hotfix must not remove strict compile/test admission checks."""
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "lite"
        / "prepare-opa-policy.sh"
    )
    source = script.read_text(encoding="utf-8")

    assert 'fmt --check-result "$policy_file"' in source
    assert 'fmt --fail --check-result "$policy_file"' not in source
    assert '"$OPA_BIN" check --strict "$SOURCE_DIR"' in source
    assert '"$OPA_BIN" test --fail-on-empty "$SOURCE_DIR"' in source
