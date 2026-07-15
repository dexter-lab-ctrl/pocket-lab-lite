#!/usr/bin/env bash
# Phase 5 Gate 2.1: non-disruptive idle stability.
set -Eeuo pipefail

stage='endurance'
status="$(long_gate_resume_stage_status "$LONG_GATE_GATE_ID" "$stage")"
[[ "$status" == 'passed' ]] && return 0
long_gate_stage_begin "$LONG_GATE_GATE_ID" "$stage" 1
set +e
"$LONG_GATE_PYTHON" "$LONG_GATE_GROUP2_TOOL" idle \
  --repo-root "$LONG_GATE_REPO_ROOT" \
  --run-dir "$LONG_GATE_RUN_DIR" \
  --run-id "$LONG_GATE_RUN_ID" \
  --gate-id "$LONG_GATE_GATE_ID" \
  --state-dir "$(long_gate_state_dir)" \
  --db-path "$(long_gate_db_path)" \
  --proxy-base-url "$(long_gate_proxy_base_url)" \
  --direct-base-url "$(long_gate_direct_base_url)" \
  --connect-timeout "$LONG_GATE_CONNECT_TIMEOUT" \
  --http-timeout "$LONG_GATE_HTTP_TIMEOUT" \
  --report-limit-bytes "$LONG_GATE_REPORT_LIMIT_BYTES" \
  --duration-seconds "$LONG_GATE_IDLE_DURATION_SECONDS" \
  --sample-interval-seconds "$LONG_GATE_IDLE_SAMPLE_INTERVAL_SECONDS" \
  --heavy-check-interval-seconds "$LONG_GATE_IDLE_HEAVY_INTERVAL_SECONDS" \
  --warmup-seconds "$LONG_GATE_IDLE_WARMUP_SECONDS" \
  --rss-budget-mb "$LONG_GATE_IDLE_RSS_BUDGET_MB" \
  --wal-budget-mb "$LONG_GATE_IDLE_WAL_BUDGET_MB" \
  --log-growth-budget-mb "$LONG_GATE_IDLE_LOG_BUDGET_MB" \
  --fd-growth-budget "$LONG_GATE_IDLE_FD_BUDGET" \
  --cpu-idle-threshold "$LONG_GATE_IDLE_CPU_THRESHOLD" \
  $([[ "$LONG_GATE_RESUME" == '1' ]] && printf '%s' '--resume')
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  long_gate_stage_pass "$LONG_GATE_GATE_ID" "$stage" "gates/$LONG_GATE_GATE_ID"
  return 0
fi
reason="$(long_gate_gate_failure_reason "$LONG_GATE_GATE_ID")"
[[ -n "$reason" ]] || reason="Idle stability gate failed with exit code $rc."
long_gate_stage_fail "$LONG_GATE_GATE_ID" "$stage" "$reason" 1 1 "gates/$LONG_GATE_GATE_ID"
return "$rc"
