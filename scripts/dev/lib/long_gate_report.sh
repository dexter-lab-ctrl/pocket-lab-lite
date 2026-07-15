#!/usr/bin/env bash
# Evidence, gate result, sanitization, checksum, and final aggregation helpers.

long_gate_write_json() {
  local output="$1" json_payload="${2:-}"
  if [[ -n "$json_payload" ]]; then
    long_gate_python write-json --output "$output" --json "$json_payload"
  else
    long_gate_python write-json --output "$output"
  fi
}

long_gate_append_jsonl() {
  local output="$1" json_payload="$2"
  long_gate_python append-jsonl --output "$output" --json "$json_payload"
}

long_gate_write_gate_result() {
  local gate_id="$1" status="$2" phase5_gate="$3" framework_validation="$4" started_at="$5" duration_seconds="$6"
  local failure_reason="${7:-}" failed_stage="${8:-}" retryable="${9:-1}" resume_safe="${10:-1}" evidence_refs="${11:-}"
  long_gate_python gate-result \
    --run-dir "$LONG_GATE_RUN_DIR" \
    --run-id "$LONG_GATE_RUN_ID" \
    --gate-id "$gate_id" \
    --status "$status" \
    --phase5-gate "$phase5_gate" \
    --framework-validation "$framework_validation" \
    --started-at "$started_at" \
    --duration-seconds "$duration_seconds" \
    --failure-reason "$failure_reason" \
    --failed-stage "$failed_stage" \
    --retryable "$retryable" \
    --resume-safe "$resume_safe" \
    --evidence-refs "$evidence_refs"
}

long_gate_evaluate_invariants() {
  long_gate_python evaluate-invariants \
    --run-id "$LONG_GATE_RUN_ID" \
    --before "$LONG_GATE_RUN_DIR/baseline/before.json" \
    --after "$LONG_GATE_RUN_DIR/baseline/after.json" \
    --output "$LONG_GATE_RUN_DIR/invariants.json"
}

long_gate_scan_sanitization() {
  long_gate_python sanitize-scan \
    --run-dir "$LONG_GATE_RUN_DIR" \
    --run-id "$LONG_GATE_RUN_ID" \
    --output "$LONG_GATE_RUN_DIR/sanitization.json"
}

long_gate_generate_checksums() {
  long_gate_python checksums \
    --run-dir "$LONG_GATE_RUN_DIR" \
    --run-id "$LONG_GATE_RUN_ID" \
    --output "$LONG_GATE_RUN_DIR/checksums.json"
}

long_gate_aggregate_summary() {
  long_gate_python aggregate \
    --run-dir "$LONG_GATE_RUN_DIR" \
    --run-id "$LONG_GATE_RUN_ID" \
    --output "$LONG_GATE_RUN_DIR/summary.json"
}

long_gate_gate_failure_reason() {
  local gate_id="$1"
  local path="$LONG_GATE_RUN_DIR/gates/$gate_id/result.json"
  [[ -f "$path" ]] || return 0
  "$LONG_GATE_PYTHON" - "$path" <<'PY'
import json, sys
try:
    payload = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("")
else:
    print(str(payload.get("failure_reason") or ""))
PY
}
