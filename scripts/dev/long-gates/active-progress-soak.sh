#!/usr/bin/env bash
# Phase 5 Gate 2.3: paired direct/Caddy Security Progress soak.
set -Eeuo pipefail

stage='paired-progress-sampling'
status="$(long_gate_resume_stage_status "$LONG_GATE_GATE_ID" "$stage")"
[[ "$status" == 'passed' ]] && return 0
long_gate_stage_begin "$LONG_GATE_GATE_ID" "$stage" 1
set +e
"$LONG_GATE_PYTHON" "$LONG_GATE_GROUP2_TOOL" progress-soak \
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
  --scan-count "$LONG_GATE_PROGRESS_SCAN_COUNT" \
  --sample-interval-ms "$LONG_GATE_PROGRESS_SAMPLE_INTERVAL_MS" \
  --run-timeout-seconds "$LONG_GATE_RUN_TIMEOUT_SECONDS" \
  --submission-timeout-seconds "$LONG_GATE_SUBMISSION_TIMEOUT_SECONDS" \
  --etag-check-every "$LONG_GATE_PROGRESS_ETAG_EVERY" \
  --max-projection-age-ms "$LONG_GATE_PROGRESS_MAX_AGE_MS" \
  --p95-budget-seconds "$LONG_GATE_PROGRESS_P95_BUDGET_SECONDS" \
  --max-budget-seconds "$LONG_GATE_PROGRESS_MAX_BUDGET_SECONDS" \
  $([[ "$LONG_GATE_RESUME" == '1' ]] && printf '%s' '--resume')
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  long_gate_stage_pass "$LONG_GATE_GATE_ID" "$stage" "gates/$LONG_GATE_GATE_ID"
  return 0
fi
reason="$(long_gate_gate_failure_reason "$LONG_GATE_GATE_ID")"
[[ -n "$reason" ]] || reason="Active Progress soak gate failed with exit code $rc."
long_gate_stage_fail "$LONG_GATE_GATE_ID" "$stage" "$reason" 1 1 "gates/$LONG_GATE_GATE_ID"
return "$rc"
