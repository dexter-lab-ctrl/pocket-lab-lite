#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${LONG_GATE_RUN_DIR:?LONG_GATE_RUN_DIR is required}"
: "${LONG_GATE_GATE_ID:?LONG_GATE_GATE_ID is required}"
: "${LONG_GATE_REPO_ROOT:?LONG_GATE_REPO_ROOT is required}"

platform="${POCKETLAB_S8_GATE_PLATFORM:-}"
if [[ -z "$platform" ]]; then
  if [[ "${PREFIX:-}" == *com.termux* ]]; then
    platform="termux"
  else
    platform="ubuntu"
  fi
fi
case "$platform" in
  termux|ubuntu) ;;
  *) printf 'ERROR: POCKETLAB_S8_GATE_PLATFORM must be termux or ubuntu\n' >&2; return 22 ;;
esac

state_dir="${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}"
db_path="${POCKETLAB_LITE_DB_PATH:-$state_dir/pocketlab-lite.sqlite3}"
gate_dir="$LONG_GATE_RUN_DIR/gates/$LONG_GATE_GATE_ID"
mkdir -p "$gate_dir"

"${LONG_GATE_PYTHON:-python3}" \
  "$LONG_GATE_REPO_ROOT/scripts/dev/lib/long_gate_s8.py" \
  --base-url "${LONG_GATE_PROXY_BASE_URL:-http://127.0.0.1:8443}" \
  --db-path "$db_path" \
  --output "$gate_dir/s8-gates.json" \
  --platform "$platform" \
  --http-timeout "${POCKETLAB_S8_GATE_HTTP_TIMEOUT_SECONDS:-${LONG_GATE_HTTP_TIMEOUT:-10}}" \
  --operation-timeout "${POCKETLAB_S8_GATE_OPERATION_TIMEOUT_SECONDS:-600}" \
  --scan-timeout "${POCKETLAB_S8_GATE_SCAN_TIMEOUT_SECONDS:-1800}"
