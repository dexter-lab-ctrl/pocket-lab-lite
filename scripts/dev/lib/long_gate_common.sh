#!/usr/bin/env bash
# Shared primitives for Pocket Lab Lite long-duration validation gates.

LONG_GATE_EXIT_INVALID_CLI=22
LONG_GATE_EXIT_LOCK_CONFLICT=23
LONG_GATE_EXIT_GATE_UNAVAILABLE=24
LONG_GATE_EXIT_BASELINE_FAILURE=25
LONG_GATE_EXIT_CHECKPOINT_CORRUPTION=26
LONG_GATE_EXIT_SANITIZATION_FAILURE=27
LONG_GATE_EXIT_FINAL_INVARIANT_FAILURE=28
LONG_GATE_EXIT_INTERRUPTED=29

long_gate_die() {
  local exit_code="$1"
  shift
  printf 'ERROR: %s\n' "$*" >&2
  return "$exit_code"
}

long_gate_info() {
  printf 'INFO: %s\n' "$*"
}

long_gate_warn() {
  printf 'WARN: %s\n' "$*" >&2
}

long_gate_require_command() {
  command -v "$1" >/dev/null 2>&1 || long_gate_die "$LONG_GATE_EXIT_INVALID_CLI" "Required command is unavailable: $1"
}

long_gate_resolve_repo_root() {
  CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd
}

long_gate_python() {
  "${LONG_GATE_PYTHON:-python3}" "$LONG_GATE_JSON_TOOL" "$@"
}

long_gate_generate_run_id() {
  long_gate_python generate-run-id
}

long_gate_safe_run_id() {
  [[ "$1" =~ ^pocketlab-long-gates-[A-Za-z0-9._-]+$ ]]
}

long_gate_default_state_dir() {
  printf '%s\n' "${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}"
}

long_gate_default_report_root() {
  printf '%s/.pocketlab-dev/long-gates\n' "$(long_gate_default_state_dir)"
}

long_gate_default_db_path() {
  local state_dir="$1"
  printf '%s\n' "${POCKETLAB_LITE_DB_PATH:-$state_dir/pocketlab-lite.sqlite3}"
}

long_gate_iso_timestamp() {
  "${LONG_GATE_PYTHON:-python3}" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
PY
}

long_gate_epoch_seconds() {
  date +%s
}

long_gate_prepare_run_layout() {
  local run_dir="$1"
  mkdir -p \
    "$run_dir/checkpoints" \
    "$run_dir/baseline" \
    "$run_dir/gates" \
    "$run_dir/samples" \
    "$run_dir/logs" \
    "$run_dir/tmp"
}

long_gate_update_state() {
  local status="${1:-}" current_gate="${2-__unchanged__}" current_stage="${3-__unchanged__}" failure_reason="${4-__unchanged__}"
  local args=(update-state --run-dir "$LONG_GATE_RUN_DIR")
  [[ -n "$status" ]] && args+=(--status "$status")
  [[ "$current_gate" != "__unchanged__" ]] && args+=(--current-gate "$current_gate")
  [[ "$current_stage" != "__unchanged__" ]] && args+=(--current-stage "$current_stage")
  [[ "$failure_reason" != "__unchanged__" ]] && args+=(--failure-reason "$failure_reason")
  long_gate_python "${args[@]}"
}

long_gate_find_resumable_run() {
  long_gate_python find-resumable --report-root "$1"
}

long_gate_init_run() {
  local gates_csv="$1" mode="$2" resume="$3"
  local args=(
    init-run
    --run-dir "$LONG_GATE_RUN_DIR"
    --run-id "$LONG_GATE_RUN_ID"
    --repo-root "$LONG_GATE_REPO_ROOT"
    --gates "$gates_csv"
    --mode "$mode"
  )
  [[ "$resume" == "1" ]] && args+=(--resume)
  long_gate_python "${args[@]}"
}

long_gate_mark_interrupted_checkpoints() {
  long_gate_python mark-interrupted --run-dir "$LONG_GATE_RUN_DIR" --run-id "$LONG_GATE_RUN_ID"
}
