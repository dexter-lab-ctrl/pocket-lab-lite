#!/usr/bin/env bash
# Common before/after baseline capture.

long_gate_capture_baseline() {
  local phase="$1"
  local output="$LONG_GATE_RUN_DIR/baseline/$phase.json"
  local args=(
    baseline
    --repo-root "$LONG_GATE_REPO_ROOT"
    --run-dir "$LONG_GATE_RUN_DIR"
    --run-id "$LONG_GATE_RUN_ID"
    --phase "$phase"
    --output "$output"
    --base-url "$(long_gate_base_url)"
    --state-dir "$(long_gate_state_dir)"
    --db-path "$(long_gate_db_path)"
  )
  [[ "${POCKETLAB_LONG_GATE_REQUIRE_LIVE_BASELINE:-0}" == "1" ]] && args+=(--require-live)
  long_gate_python "${args[@]}"
}
