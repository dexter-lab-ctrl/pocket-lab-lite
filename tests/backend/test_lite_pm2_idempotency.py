from __future__ import annotations

import json
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


def _run_case(tmp_path: Path, status: str, *, wrong_executable: bool = False) -> list[str]:
    actions = tmp_path / f"actions-{status}.log"
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
export POCKETLAB_STATE_DIR="$TEST_HOME/pocket-lab-lite/state"
source "$COMMON_PATH"
EXPECTED_SCRIPT="$(pwd -P)/demo.py"
EXPECTED_INTERPRETER="$(command -v python3)"
export POCKETLAB_NATS_PASSWORD=test-secret-value
export POCKETLAB_PM2_POLICY_FINGERPRINT="$(pm2_policy_fingerprint demo)"
export ACTION_FILE
SPEC="$(pm2_process_spec_hash demo.py --interpreter python3 -- some-argument)"
export SPEC STATUS EXPECTED_SCRIPT EXPECTED_INTERPRETER

pm2_process_snapshot() {
  if [[ -s "$START_SNAPSHOT" ]]; then
    python3 - "$START_SNAPSHOT" <<'PY'
import json
from pathlib import Path
import sys
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["status"])
print(data["spec"])
print(data["script"])
print(data["interpreter"])
PY
    return 0
  fi
  if [[ "$STATUS" == "missing" ]]; then
    return 0
  fi
  printf '%s\n%s\n%s\n%s\n' "$STATUS" "$SPEC" "${SNAPSHOT_SCRIPT:-$EXPECTED_SCRIPT}" "$EXPECTED_INTERPRETER"
}

pm2() {
    case "${1:-}" in
    jlist)
      printf '%s\n' '[{"name":"demo","pm_id":42}]'
      ;;
    restart|start|delete)
      if [[ "$1" == "start" ]]; then
        if [[ "$2" == /* ]]; then
          cp "$2" "$ECOSYSTEM_CAPTURE"
          printf '%s\n' "$2" >"$START_PATH"
          printf '%s\n' "$@" >"$START_ARGS"
          python3 - "$2" "$START_SNAPSHOT" "$POCKETLAB_PROCESS_SPEC_HASH" <<'PY'
import json
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text(encoding="utf-8")
encoded = source.split("const app = ", 1)[1].split(";\napp.env", 1)[0]
app = json.loads(encoded)
script = app["script"]
if not Path(script).is_absolute():
    script = str((Path(app.get("cwd") or Path.cwd()) / script).resolve())
payload = {
    "status": "online",
    "spec": sys.argv[3],
    "script": script,
    "interpreter": app.get("interpreter") or "node",
}
Path(sys.argv[2]).write_text(json.dumps(payload), encoding="utf-8")
PY
        else
          # Kept for callers that exercise the old name-based PM2 stub path;
          # the production convergence path recreates stopped definitions from
          # their process-specific ecosystem file.
          printf 'online\n%s\n%s\n%s\n' \
            "$POCKETLAB_PROCESS_SPEC_HASH" "$EXPECTED_SCRIPT" "$EXPECTED_INTERPRETER" >"$START_SNAPSHOT"
        fi
      fi
      if [[ "$1" == "delete" ]]; then
        STATUS=missing
        export STATUS
        printf '%s\n' "${2:-}" >"$DELETE_TARGET"
      fi
      printf '%s\n' "$1" >>"$ACTION_FILE"
      ;;
    *)
      return 0
      ;;
  esac
}

pm2_ensure_process demo demo.py --interpreter python3 -- some-argument
python3 - "$TEST_HOME/pocket-lab-lite/state/runtime/desired-process-specs.json" "$SPEC" <<'PY'
import json
from pathlib import Path
import sys
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["schema"] == "pocketlab.pm2-desired-process-specs/v1"
assert payload["schema_version"] == 1 and payload["sanitized"] is True
assert payload["processes"]["demo"] == sys.argv[2]
assert len(payload["launches"]["demo"]) == 64
PY
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
            "ACTION_FILE": str(actions),
            "DELETE_TARGET": str(tmp_path / f"delete-target-{status}.txt"),
            "ECOSYSTEM_CAPTURE": str(tmp_path / f"ecosystem-{status}.js"),
            "START_PATH": str(tmp_path / f"start-path-{status}.txt"),
            "START_ARGS": str(tmp_path / f"start-args-{status}.txt"),
            "START_SNAPSHOT": str(tmp_path / f"snapshot-{status}.json"),
            "STATUS": status,
        }
    )
    if wrong_executable:
        env["SNAPSHOT_SCRIPT"] = str(tmp_path / "wrong-executable")
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


def test_stopped_matching_process_recreates_from_its_ecosystem_definition(tmp_path):
    # PM2 7/Termux can attach a queued sibling definition when either `start`
    # or `restart` resumes a stopped process by name. Recreate from the
    # process-specific ecosystem file and verify its launch identity instead.
    assert _run_case(tmp_path, "stopped") == ["delete", "start"]
    assert (tmp_path / "delete-target-stopped.txt").read_text().strip() == "42"


def test_missing_process_definition_is_created(tmp_path):
    assert _run_case(tmp_path, "missing") == ["start"]


def test_wrong_executable_is_replaced_even_when_process_hash_matches(tmp_path):
    assert _run_case(tmp_path, "online", wrong_executable=True) == ["delete", "start"]


def test_stopping_wrong_executable_waits_for_pm2_removal_before_restart(tmp_path):
    assert _run_case(tmp_path, "stopping", wrong_executable=True) == ["delete", "start"]


def test_process_start_uses_temporary_ecosystem_config_without_serializing_secrets(tmp_path):
    assert _run_case(tmp_path, "missing") == ["start"]
    source = (tmp_path / "ecosystem-missing.js").read_text(encoding="utf-8")
    start_path = Path((tmp_path / "start-path-missing.txt").read_text(encoding="utf-8").strip())
    assert start_path.name == "demo.config.cjs"
    assert start_path.parent.name == "pm2-ecosystems"
    assert (tmp_path / "start-args-missing.txt").read_text(encoding="utf-8").splitlines() == [
        "start",
        str(start_path),
    ]
    assert "app.env = process.env;" in source
    assert "test-secret-value" not in source
    encoded_app = source.split("const app = ", 1)[1].split(";\napp.env", 1)[0]
    app = json.loads(encoded_app)
    assert app["name"] == "demo"
    assert app["script"] == "demo.py"
    assert app["interpreter"].endswith("python3")
    assert app["args"] == ["some-argument"]
    assert "--min-uptime" not in source


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


def test_desired_policy_fingerprint_changes_process_spec_identity(tmp_path):
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"
export POCKETLAB_PM2_POLICY_FINGERPRINT=policy-one
A="$(pm2_process_spec_hash demo.py --interpreter python3)"
export POCKETLAB_PM2_POLICY_FINGERPRINT=policy-two
B="$(pm2_process_spec_hash demo.py --interpreter python3)"
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
      printf '%s\n' '[{"name":"demo","pm2_env":{"status":"online","POCKETLAB_PROCESS_SPEC_HASH":"abc123","pm_exec_path":"/opt/demo.py","exec_interpreter":"/usr/bin/python3"}}]'
      ;;
    *)
      return 0
      ;;
  esac
}

snapshot="$(pm2_process_snapshot demo)"
test "$(printf '%s\n' "$snapshot" | sed -n '1p')" = "online"
test "$(printf '%s\n' "$snapshot" | sed -n '2p')" = "abc123"
test "$(printf '%s\n' "$snapshot" | sed -n '3p')" = "/opt/demo.py"
test "$(printf '%s\n' "$snapshot" | sed -n '4p')" = "/usr/bin/python3"
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
SNAPSHOT_FILE="$TEST_HOME/snapshot.txt"
EXPECTED_SCRIPT="$(pwd -P)/python3"
EXPECTED_INTERPRETER="none"
mkdir -p "$TEST_HOME"

pm2_process_snapshot() {
  if [[ -s "$SNAPSHOT_FILE" ]]; then
    cat "$SNAPSHOT_FILE"
    return 0
  fi
  return 0
}

pm2() {
  if [[ "${1:-}" == "delete" ]]; then
    : >"$SNAPSHOT_FILE"
  fi
  if [[ "${1:-}" == "start" ]]; then
    mkdir -p "$(dirname "$HASH_FILE")"
    printf '%s\n' "$POCKETLAB_PROCESS_SPEC_HASH" >"$HASH_FILE"
    printf 'online\n%s\n%s\n%s\n' "$POCKETLAB_PROCESS_SPEC_HASH" "$EXPECTED_SCRIPT" "$EXPECTED_INTERPRETER" >"$SNAPSHOT_FILE"
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
