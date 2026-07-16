#!/usr/bin/env bash
# Phase 5 Gate 3.3: controlled worker restart recovery.
set -Eeuo pipefail

stage='controlled-worker-recovery'
status="$(long_gate_resume_stage_status "$LONG_GATE_GATE_ID" "$stage")"
[[ "$status" == 'passed' ]] && return 0
long_gate_stage_begin "$LONG_GATE_GATE_ID" "$stage" 1
set +e
"$LONG_GATE_PYTHON" "$LONG_GATE_GROUP3_TOOL" worker-restart \
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
  --run-timeout-seconds "$LONG_GATE_RUN_TIMEOUT_SECONDS" \
  --service-recovery-timeout-seconds "$LONG_GATE_SERVICE_RECOVERY_TIMEOUT_SECONDS" \
  --execution-evidence-timeout-seconds "$LONG_GATE_EXECUTION_EVIDENCE_TIMEOUT_SECONDS" \
  --scenario "$LONG_GATE_RECOVERY_SCENARIO" \
  $([[ "$LONG_GATE_RESUME" == '1' ]] && printf '%s' '--resume')
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  long_gate_stage_pass "$LONG_GATE_GATE_ID" "$stage" "gates/$LONG_GATE_GATE_ID"
  return 0
fi
reason="$(long_gate_gate_failure_reason "$LONG_GATE_GATE_ID")"
[[ -n "$reason" ]] || reason="Worker restart recovery gate failed with exit code $rc."
long_gate_stage_fail "$LONG_GATE_GATE_ID" "$stage" "$reason" 0 1 "gates/$LONG_GATE_GATE_ID"
return "$rc"
