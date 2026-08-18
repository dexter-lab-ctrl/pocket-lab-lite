from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/bootstrap.sh"
HEALTH = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/bootstrap-stage-health.sh"


def _run_helper(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True)

    opa = fake_bin / "opa"
    opa.write_text("#!/usr/bin/env bash\n[[ ${1:-} == version ]] && { echo 'Version: 1.19.0'; exit 0; }\nexit 0\n")
    opa.chmod(0o755)

    pm2 = fake_bin / "pm2"
    pm2.write_text("#!/usr/bin/env bash\n[[ ${1:-} == describe && ${2:-} == pocket-opa ]]\n")
    pm2.chmod(0o755)

    curl = fake_bin / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        "url=${@: -1}\n"
        "case $url in\n"
        "  http://127.0.0.1:8181/health) printf '{}';;\n"
        "  http://127.0.0.1:8080/api/lite/policy)\n"
        "    if [[ -n ${FAKE_POLICY_JSON:-} ]]; then\n"
        "      printf '%s' \"$FAKE_POLICY_JSON\"\n"
        "    else\n"
        "      printf '{}'\n"
        "    fi\n"
        "    ;;\n"
        "  *) exit 22;;\n"
        "esac\n"
    )
    curl.chmod(0o755)

    state = tmp_path / "state"
    active = state / "opa" / "active"
    active.mkdir(parents=True)
    (active / "pocketlab.rego").write_text("package pocketlab\n")
    (active / "revision.txt").write_text("test-revision\n")

    script = f"""
set -Eeuo pipefail
is_done() {{ [[ \"${{1:-}}\" == lite_opa_ready ]]; }}
source {HEALTH!s}
export PATH={fake_bin!s}:$PATH
export POCKETLAB_STATE_DIR={state!s}
{body}
"""
    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_bootstrap_invalidates_stale_lite_capability_markers() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'source "$LITE_STAGE_HEALTH"' in source
    assert 'pocketlab_lite_stage_completion_is_valid "$id"' in source
    assert "Ignoring stale Lite bootstrap marker" in source
    assert "completed but its Lite capability contract is not satisfied" in source
    assert "current source/runtime contract" in source


def test_install_binaries_marker_requires_usable_opa(tmp_path: Path) -> None:
    result = _run_helper(
        tmp_path,
        'pocketlab_lite_stage_completion_is_valid install_binaries; printf "%s" "$POCKETLAB_LITE_STAGE_HEALTH_REASON"',
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_start_dashboard_marker_requires_current_ready_rules_projection(tmp_path: Path) -> None:
    healthy = _run_helper(
        tmp_path / "healthy",
        """
export FAKE_POLICY_JSON='{"status":"ready","engine":{"healthy":true,"endpoint_exposed_to_browser":false},"active_policy":{"bundle_ready":true}}'
pocketlab_lite_stage_completion_is_valid start_dashboard
""",
    )
    assert healthy.returncode == 0, healthy.stderr

    legacy = _run_helper(
        tmp_path / "legacy",
        """
export FAKE_POLICY_JSON='{"status":"healthy"}'
if pocketlab_lite_stage_completion_is_valid start_dashboard; then
  exit 9
fi
printf '%s' "$POCKETLAB_LITE_STAGE_HEALTH_REASON"
""",
    )
    assert legacy.returncode == 0, legacy.stderr
    assert legacy.stdout == "FastAPI Rules projection is not bound to the ready OPA runtime"


def test_start_dashboard_marker_fails_when_opa_capability_marker_is_missing(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True)
    opa = fake_bin / "opa"
    opa.write_text("#!/usr/bin/env bash\nexit 0\n")
    opa.chmod(0o755)

    script = f"""
set -Eeuo pipefail
is_done() {{ return 1; }}
source {HEALTH!s}
export PATH={fake_bin!s}:$PATH
if pocketlab_lite_stage_completion_is_valid install_binaries; then
  exit 9
fi
printf '%s' "$POCKETLAB_LITE_STAGE_HEALTH_REASON"
"""
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "OPA capability marker is missing"
