from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
COMMON = (
    ROOT
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
    / "lib"
    / "common.sh"
)


def _run_case(tmp_path: Path, status: str) -> list[str]:
    actions = tmp_path / f"actions-{status}.log"
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
export POCKETLAB_STATE_DIR="$TEST_HOME/pocket-lab-lite/state"
source "$COMMON_PATH"
export POCKETLAB_PM2_POLICY_FINGERPRINT="$(pm2_policy_fingerprint demo)"
export ACTION_FILE
SPEC="$(pm2_process_spec_hash python3 -- demo.py)"
export SPEC STATUS

pm2_process_snapshot() {
  if [[ "$STATUS" == "missing" ]]; then
    return 1
  fi
  printf '%s\n%s\n' "$STATUS" "$SPEC"
}

pm2() {
  case "${1:-}" in
    restart|start|delete)
      printf '%s\n' "$1" >>"$ACTION_FILE"
      ;;
    *)
      return 0
      ;;
  esac
}

pm2_ensure_process demo python3 -- demo.py
python3 - "$TEST_HOME/pocket-lab-lite/state/runtime/desired-process-specs.json" "$SPEC" <<'PY'
import json
from pathlib import Path
import sys
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["schema"] == "pocketlab.pm2-desired-process-specs/v1"
assert payload["schema_version"] == 1 and payload["sanitized"] is True
assert payload["processes"]["demo"] == sys.argv[2]
PY
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
            "ACTION_FILE": str(actions),
            "STATUS": status,
        }
    )
    completed = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    if not actions.exists():
        return []
    return [line.strip() for line in actions.read_text().splitlines() if line.strip()]


def test_second_healthy_convergence_performs_zero_pm2_mutations(tmp_path):
    assert _run_case(tmp_path, "online") == []


def test_stopped_matching_process_restarts_without_delete_recreate(tmp_path):
    assert _run_case(tmp_path, "stopped") == ["restart"]


def test_missing_process_definition_is_created(tmp_path):
    assert _run_case(tmp_path, "missing") == ["start"]


def test_transient_app_operation_variables_do_not_change_process_spec_hash(tmp_path):
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"
export POCKETLAB_LITE_APP_OPERATION_ID=first-operation
export POCKETLAB_PHOTOPRISM_PACKAGE_URL=https://example.invalid/one
export POCKETLAB_LITE_SECURE_ORIGIN=https://example.invalid
A="$(pm2_process_spec_hash bash -- -lc 'demo')"
export POCKETLAB_LITE_APP_OPERATION_ID=second-operation
export POCKETLAB_PHOTOPRISM_PACKAGE_URL=https://example.invalid/two
unset POCKETLAB_LITE_SECURE_ORIGIN
B="$(pm2_process_spec_hash bash -- -lc 'demo')"
test "$A" = "$B"
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
        }
    )
    subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )



def test_pm2_process_snapshot_parses_jlist_json(tmp_path):
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"

pm2() {
  case "${1:-}" in
    jlist)
      printf '%s\n' '[{"name":"demo","pm2_env":{"status":"online","POCKETLAB_PROCESS_SPEC_HASH":"abc123"}}]'
      ;;
    *)
      return 0
      ;;
  esac
}

snapshot="$(pm2_process_snapshot demo)"
test "$(printf '%s\n' "$snapshot" | sed -n '1p')" = "online"
test "$(printf '%s\n' "$snapshot" | sed -n '2p')" = "abc123"
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
        }
    )
    completed = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_managed_process_spec_hash_changes_when_pm2_policy_changes(tmp_path):
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"

HASH_FILE="$TEST_HOME/hash.txt"
mkdir -p "$TEST_HOME"

pm2_process_snapshot() {
  return 1
}

pm2() {
  if [[ "${1:-}" == "start" ]]; then
    mkdir -p "$(dirname "$HASH_FILE")"
    printf '%s\n' "$POCKETLAB_PROCESS_SPEC_HASH" >"$HASH_FILE"
  fi
}

pm2_ensure_process pocket-api python3 -- demo.py
A="$(cat "$HASH_FILE")"
export POCKETLAB_PM2_POCKET_API_KILL_TIMEOUT_MS=17000
pm2_ensure_process pocket-api python3 -- demo.py
B="$(cat "$HASH_FILE")"
test -n "$A"
test -n "$B"
test "$A" != "$B"
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
        }
    )
    completed = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_runtime_only_observation_variables_do_not_change_process_spec_hash(tmp_path):
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"
export POCKETLAB_RUNTIME_OBSERVED_RSS_MB=111
export POCKETLAB_PM2_OBSERVED_RESTART_GENERATION=1
A="$(pm2_process_spec_hash python3 -- demo.py)"
export POCKETLAB_RUNTIME_OBSERVED_RSS_MB=999
export POCKETLAB_PM2_OBSERVED_RESTART_GENERATION=77
B="$(pm2_process_spec_hash python3 -- demo.py)"
test "$A" = "$B"
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
        }
    )
    completed = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
