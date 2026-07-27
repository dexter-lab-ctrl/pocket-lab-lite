#!/usr/bin/env bash
# Phase 4/5 non-disruptive adaptive runtime and budget qualification.
set -Eeuo pipefail

stage='adaptive-runtime'
status="$(long_gate_resume_stage_status "$LONG_GATE_GATE_ID" "$stage")"
[[ "$status" == 'passed' ]] && return 0
long_gate_stage_begin "$LONG_GATE_GATE_ID" "$stage" 1

adaptive_tool="$LONG_GATE_REPO_ROOT/scripts/dev/lib/long_gate_adaptive_runtime.py"
if [[ ! -f "$adaptive_tool" ]]; then
  long_gate_stage_fail "$LONG_GATE_GATE_ID" "$stage" "Adaptive runtime gate helper is missing." 1 0 ""
  return 2
fi

duration="${LONG_GATE_ADAPTIVE_DURATION_SECONDS:-900}"
sample_interval="${LONG_GATE_ADAPTIVE_SAMPLE_INTERVAL_SECONDS:-15}"
set +e
"$LONG_GATE_PYTHON" "$adaptive_tool" \
  --run-dir "$LONG_GATE_RUN_DIR" \
  --run-id "$LONG_GATE_RUN_ID" \
  --gate-id "$LONG_GATE_GATE_ID" \
  --base-url "$LONG_GATE_DIRECT_BASE_URL" \
  --duration-seconds "$duration" \
  --sample-interval-seconds "$sample_interval" \
  --http-timeout "$LONG_GATE_HTTP_TIMEOUT" \
  --minimum-samples "${POCKETLAB_LONG_GATE_ADAPTIVE_MINIMUM_SAMPLES:-5}" \
  --queue-depth-budget "${POCKETLAB_LONG_GATE_ADAPTIVE_QUEUE_DEPTH_BUDGET:-12}" \
  --cpu-p99-budget-ms "${POCKETLAB_LONG_GATE_ADAPTIVE_CPU_P99_MS:-750}" \
  --wall-p99-budget-ms "${POCKETLAB_LONG_GATE_ADAPTIVE_WALL_P99_MS:-8000}" \
  --queue-wait-p99-budget-ms "${POCKETLAB_LONG_GATE_ADAPTIVE_QUEUE_WAIT_P99_MS:-20000}" \
  --max-exhaustion-ratio "${POCKETLAB_LONG_GATE_ADAPTIVE_MAX_EXHAUSTION_RATIO:-0.5}" \
  --api-p95-budget-ms "${POCKETLAB_LONG_GATE_ADAPTIVE_API_P95_MS:-750}" \
  --api-p99-budget-ms "${POCKETLAB_LONG_GATE_ADAPTIVE_API_P99_MS:-2000}" \
  --event-loop-p95-budget-ms "${POCKETLAB_LONG_GATE_ADAPTIVE_EVENT_LOOP_P95_MS:-150}" \
  --event-loop-p99-budget-ms "${POCKETLAB_LONG_GATE_ADAPTIVE_EVENT_LOOP_P99_MS:-400}" \
  --rss-growth-budget-bytes "${POCKETLAB_LONG_GATE_ADAPTIVE_RSS_GROWTH_BYTES:-67108864}" \
  --peak-rss-budget-bytes "${POCKETLAB_LONG_GATE_ADAPTIVE_PEAK_RSS_BYTES:-805306368}"
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  long_gate_stage_pass "$LONG_GATE_GATE_ID" "$stage" "gates/$LONG_GATE_GATE_ID"
  return 0
fi
reason="$(long_gate_gate_failure_reason "$LONG_GATE_GATE_ID")"
[[ -n "$reason" ]] || reason="Adaptive runtime gate failed with exit code $rc."
long_gate_stage_fail "$LONG_GATE_GATE_ID" "$stage" "$reason" 1 1 "gates/$LONG_GATE_GATE_ID"
return "$rc"
