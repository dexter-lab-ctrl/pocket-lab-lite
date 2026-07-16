#!/usr/bin/env bash
# Phase 5 Gate 4.1: SQLite WAL checkpoint pressure.
set -Eeuo pipefail
stage='wal-pressure'
[[ "$(long_gate_resume_stage_status "$LONG_GATE_GATE_ID" "$stage")" == 'passed' ]] && return 0
long_gate_stage_begin "$LONG_GATE_GATE_ID" "$stage" 1
args=(
  wal-pressure --repo-root "$LONG_GATE_REPO_ROOT" --run-dir "$LONG_GATE_RUN_DIR" --run-id "$LONG_GATE_RUN_ID"
  --gate-id "$LONG_GATE_GATE_ID" --state-dir "$(long_gate_state_dir)" --db-path "$(long_gate_db_path)"
  --proxy-base-url "$(long_gate_proxy_base_url)" --direct-base-url "$(long_gate_direct_base_url)"
  --connect-timeout "$LONG_GATE_CONNECT_TIMEOUT" --http-timeout "$LONG_GATE_HTTP_TIMEOUT"
  --report-limit-bytes "$LONG_GATE_REPORT_LIMIT_BYTES" --run-timeout-seconds "$LONG_GATE_RUN_TIMEOUT_SECONDS"
  --submission-timeout-seconds "$LONG_GATE_SUBMISSION_TIMEOUT_SECONDS" --scenario "$LONG_GATE_WAL_SCENARIO"
  --duration-seconds "$LONG_GATE_WAL_DURATION_SECONDS" --writer-interval-ms "$LONG_GATE_WAL_WRITER_INTERVAL_MS"
  --reader-interval-ms "$LONG_GATE_WAL_READER_INTERVAL_MS" --checkpoint-interval-seconds "$LONG_GATE_WAL_CHECKPOINT_INTERVAL_SECONDS"
  --health-interval-seconds "$LONG_GATE_WAL_HEALTH_INTERVAL_SECONDS" --wal-growth-budget-bytes "$LONG_GATE_WAL_GROWTH_BUDGET_BYTES"
  --reader-p95-budget-seconds "$LONG_GATE_WAL_READER_P95_SECONDS" --writer-p95-budget-seconds "$LONG_GATE_WAL_WRITER_P95_SECONDS"
  --contention-retry-budget "$LONG_GATE_WAL_CONTENTION_RETRY_BUDGET"
)
[[ "$LONG_GATE_WAL_FINAL_TRUNCATE" == '1' ]] && args+=(--final-truncate-checkpoint)
[[ "$LONG_GATE_RESUME" == '1' ]] && args+=(--resume)
set +e
"$LONG_GATE_PYTHON" "$LONG_GATE_GROUP4_TOOL" "${args[@]}"
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then long_gate_stage_pass "$LONG_GATE_GATE_ID" "$stage" "gates/$LONG_GATE_GATE_ID"; return 0; fi
reason="$(long_gate_gate_failure_reason "$LONG_GATE_GATE_ID")"; [[ -n "$reason" ]] || reason="WAL pressure gate failed with exit code $rc."
long_gate_stage_fail "$LONG_GATE_GATE_ID" "$stage" "$reason" 0 1 "gates/$LONG_GATE_GATE_ID"
return "$rc"
