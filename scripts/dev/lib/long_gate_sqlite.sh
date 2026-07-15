#!/usr/bin/env bash
# SQLite path and bounded health helpers. These never initialize or mutate the database.

long_gate_state_dir() {
  printf '%s\n' "${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}"
}

long_gate_db_path() {
  local state_dir
  state_dir="$(long_gate_state_dir)"
  printf '%s\n' "${POCKETLAB_LITE_DB_PATH:-$state_dir/pocketlab-lite.sqlite3}"
}

long_gate_sqlite_health_json() {
  local output="$1"
  (
    cd "$LONG_GATE_REPO_ROOT"
    POCKETLAB_STATE_DIR="$(long_gate_state_dir)" \
    POCKETLAB_LITE_DB_PATH="$(long_gate_db_path)" \
    "${LONG_GATE_PYTHON:-python3}" scripts/lite/security-db-check.py > "$output"
  )
}

long_gate_sqlite_parity_json() {
  local output="$1"
  (
    cd "$LONG_GATE_REPO_ROOT"
    POCKETLAB_STATE_DIR="$(long_gate_state_dir)" \
    POCKETLAB_LITE_DB_PATH="$(long_gate_db_path)" \
    "${LONG_GATE_PYTHON:-python3}" scripts/lite/security-db-compare.py --no-record > "$output"
  )
}
