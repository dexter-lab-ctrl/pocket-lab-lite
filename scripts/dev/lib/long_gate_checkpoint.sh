#!/usr/bin/env bash
# Atomic checkpoint wrappers for future long-duration gate implementations.

long_gate_checkpoint_transition() {
  local gate_id="$1" stage_id="$2" status="$3" failure_reason="${4:-}" evidence_refs="${5:-}" resume_safe="${6:-1}" retryable="${7:-1}"
  long_gate_python checkpoint \
    --run-dir "$LONG_GATE_RUN_DIR" \
    --run-id "$LONG_GATE_RUN_ID" \
    --gate-id "$gate_id" \
    --stage-id "$stage_id" \
    --status "$status" \
    --failure-reason "$failure_reason" \
    --evidence-refs "$evidence_refs" \
    --resume-safe "$resume_safe" \
    --retryable "$retryable"
}

long_gate_stage_begin() {
  local gate_id="$1" stage_id="$2" resume_safe="${3:-1}"
  long_gate_update_state running "$gate_id" "$stage_id" ""
  long_gate_checkpoint_transition "$gate_id" "$stage_id" running "" "" "$resume_safe" 1
}

long_gate_stage_pass() {
  local gate_id="$1" stage_id="$2" evidence_refs="${3:-}"
  long_gate_checkpoint_transition "$gate_id" "$stage_id" passed "" "$evidence_refs" 1 1
  long_gate_update_state running "$gate_id" "" ""
}

long_gate_stage_fail() {
  local gate_id="$1" stage_id="$2" reason="$3" retryable="${4:-1}" resume_safe="${5:-1}" evidence_refs="${6:-}"
  [[ -n "$reason" ]] || reason="Stage failed without a supplied reason."
  long_gate_checkpoint_transition "$gate_id" "$stage_id" failed "$reason" "$evidence_refs" "$resume_safe" "$retryable"
  long_gate_update_state failed "$gate_id" "$stage_id" "$reason"
}

long_gate_stage_skip() {
  local gate_id="$1" stage_id="$2" reason="${3:-Stage skipped.}"
  long_gate_checkpoint_transition "$gate_id" "$stage_id" skipped "$reason" "" 1 1
}

long_gate_stage_unavailable() {
  local gate_id="$1" stage_id="$2" reason="$3"
  long_gate_checkpoint_transition "$gate_id" "$stage_id" unavailable "$reason" "" 1 1
}

long_gate_resume_stage_status() {
  local gate_id="$1" stage_id="$2"
  long_gate_python checkpoint-status \
    --run-dir "$LONG_GATE_RUN_DIR" \
    --run-id "$LONG_GATE_RUN_ID" \
    --gate-id "$gate_id" \
    --stage-id "$stage_id"
}

long_gate_checkpoint_read() {
  local gate_id="$1"
  cat "$LONG_GATE_RUN_DIR/checkpoints/$gate_id.json"
}
