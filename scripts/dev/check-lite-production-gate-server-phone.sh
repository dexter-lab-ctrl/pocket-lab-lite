#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_URL="${POCKETLAB_GATE_BASE_URL:-http://127.0.0.1:8443}"
PROGRESS_URL="$BASE_URL/api/lite/security/progress"
CHECK_URL="$BASE_URL/api/lite/security/check"
NATS_STATUS_URL="$BASE_URL/api/nats/status"
DIAGNOSTICS_URL="$BASE_URL/api/lite/diagnostics/runtime"
TIMEOUT_SECONDS="${POCKETLAB_GATE_SCAN_TIMEOUT_SECONDS:-5400}"
MAX_PROJECTION_AGE_MS="${POCKETLAB_GATE_MAX_PROJECTION_AGE_MS:-5000}"
REPORT_DIR="${POCKETLAB_GATE_REPORT_DIR:-${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}/.pocketlab-dev/reports}"
STAMP="$(date -u +%Y%m%d-%H%M%S)-$$"
REPORT_JSON="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-final.json"
SAMPLES="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-latencies.txt"
STATE_FILE="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-progress.json"
SUBMISSION_FAILURES="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-submission-latency.txt"
FAILURE_FILE="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-failure.txt"
DIAGNOSTICS_FILE="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-runtime-diagnostics.json"
mkdir -p "$REPORT_DIR"
: > "$SAMPLES"
: > "$SUBMISSION_FAILURES"
: > "$FAILURE_FILE"
printf '%s' '{}' > "$STATE_FILE"
printf '%s' '{}' > "$DIAGNOSTICS_FILE"

MAIN_BASHPID="$BASHPID"
STORE_MODE="unknown"
first_run=""
second_run="not-run"

AUTH_ARGS=()
if [[ -n "${POCKETLAB_API_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${POCKETLAB_API_TOKEN}")
fi

fail(){
  printf '%s\n' "$*" > "$FAILURE_FILE"
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}
info(){ printf 'INFO: %s\n' "$*"; }

record_unexpected_failure(){
  local exit_code="$1" line_number="$2"
  if [[ "$exit_code" -ne 0 && ! -s "$FAILURE_FILE" ]]; then
    printf 'Production gate command failed at line %s with exit code %s.\n' \
      "$line_number" "$exit_code" > "$FAILURE_FILE"
  fi
}
trap 'record_unexpected_failure "$?" "$LINENO"' ERR

capture_runtime_diagnostics(){
  local tmp_file
  tmp_file="$(mktemp)"
  if curl -fsS --max-time 3 "${AUTH_ARGS[@]}" \
    -H 'Accept: application/json' "$DIAGNOSTICS_URL" -o "$tmp_file" \
    && python3 - "$tmp_file" <<'PY2'
import json
import sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if isinstance(payload, dict) and payload.get("sanitized") is True else 1)
PY2
  then
    mv "$tmp_file" "$DIAGNOSTICS_FILE"
  else
    local curl_rc=$?
    rm -f "$tmp_file"
    python3 - "$DIAGNOSTICS_FILE" "$curl_rc" <<'PY2'
import json
import sys

path, raw_rc = sys.argv[1:]
try:
    rc = int(raw_rc)
except ValueError:
    rc = 1
error_class = "timeout" if rc == 28 else "capture_failed"
payload = {
    "capture_ok": False,
    "error_class": error_class,
    "curl_exit_code": rc,
    "timeout_seconds": 3,
    "sanitized": True,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True)
PY2
  fi
}

write_final_report(){
  local exit_code="$1"
  python3 - "$REPORT_JSON" "$SAMPLES" "$SUBMISSION_FAILURES" "$FAILURE_FILE" \
    "$STATE_FILE" "$DIAGNOSTICS_FILE" "$STORE_MODE" "$first_run" "$second_run" "$exit_code" <<'PY'
import json
import math
import sys
from pathlib import Path

(
    report_path,
    samples_path,
    submission_failures_path,
    failure_path,
    state_path,
    diagnostics_path,
    store_mode,
    first_run,
    second_run,
    exit_code_raw,
) = sys.argv[1:]

exit_code = int(exit_code_raw)
failure_reason = Path(failure_path).read_text(encoding="utf-8").strip()
if exit_code != 0 and not failure_reason:
    failure_reason = f"Production gate exited with code {exit_code}."
try:
    runtime_diagnostics = json.loads(
        Path(diagnostics_path).read_text(encoding="utf-8") or "{}"
    )
except (OSError, json.JSONDecodeError):
    runtime_diagnostics = {}
if not isinstance(runtime_diagnostics, dict) or runtime_diagnostics.get("sanitized") is not True:
    runtime_diagnostics = {}
submission_failures = [
    line.strip()
    for line in Path(submission_failures_path).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
values = []
for line in Path(samples_path).read_text(encoding="utf-8").splitlines():
    parts = line.split()
    if parts:
        try:
            values.append(float(parts[-1]))
        except ValueError:
            pass
values.sort()

def percentile(p):
    if not values:
        return None
    return values[min(len(values) - 1, max(0, math.ceil(len(values) * p) - 1))]

try:
    last_progress = json.loads(Path(state_path).read_text(encoding="utf-8") or "{}")
except (OSError, json.JSONDecodeError):
    last_progress = {}

failed_gates = int(exit_code != 0) + len(submission_failures)
payload = {
    "status": "ready" if failed_gates == 0 else "not_ready",
    "failed_gates": failed_gates,
    "failure_reason": failure_reason,
    "submission_latency_failures": submission_failures,
    "security_store_mode": store_mode or "unknown",
    "first_run_id": first_run,
    "post_reconnect_run_id": second_run,
    "last_progress": last_progress,
    "runtime_diagnostics": runtime_diagnostics,
    "progress_latency_seconds": {
        "count": len(values),
        "p50": round(percentile(0.50), 3) if values else None,
        "p95": round(percentile(0.95), 3) if values else None,
        "max": round(max(values), 3) if values else None,
    },
    "exit_code": exit_code,
    "sanitized": True,
}
Path(report_path).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

finalize_on_exit(){
  local exit_code=$?
  [[ "$BASHPID" == "$MAIN_BASHPID" ]] || return "$exit_code"
  trap - EXIT
  capture_runtime_diagnostics
  write_final_report "$exit_code"
  info "Report: $REPORT_JSON"
  exit "$exit_code"
}
trap finalize_on_exit EXIT

json_field(){ python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1"; }

curl_json(){
  local method="$1" url="$2" body="${3:-}" out="$4" metrics="$5"
  local args=(-fsS --max-time 5 -X "$method" "${AUTH_ARGS[@]}" -H 'Accept: application/json')
  if [[ -n "$body" ]]; then
    args+=(-H 'Content-Type: application/json' --data "$body")
  fi
  curl "${args[@]}" -o "$out" -w '%{http_code} %{time_total} %{size_download}\n' "$url" > "$metrics"
}

wait_for_api_ready(){
  local deadline payload metrics code seconds size
  local curl_rc json_rc
  local last_error=""

  deadline=$(( $(date +%s) + ${POCKETLAB_GATE_API_READY_TIMEOUT_SECONDS:-120} ))

  info "Waiting for API and Security Progress readiness"

  while (( $(date +%s) <= deadline )); do
    payload="$(mktemp)"
    metrics="$(mktemp)"

    set +e
    curl_json GET "$PROGRESS_URL" '' "$payload" "$metrics"
    curl_rc=$?
    set -e

    if (( curl_rc == 0 )); then
      code=""
      seconds=""
      size=""

      IFS=' ' read -r code seconds size < "$metrics"

      if [[ "$code" == "200" && "${size:-0}" -gt 0 ]]; then
        set +e
        python3 - "$payload" <<'PY2'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

valid = (
    isinstance(payload, dict)
    and bool(payload.get("view_model"))
    and isinstance(payload.get("active_scan"), bool)
)

raise SystemExit(0 if valid else 1)
PY2
        json_rc=$?
        set -e

        if (( json_rc == 0 )); then
          rm -f "$payload" "$metrics"
          info "API and Security Progress are ready"
          return 0
        fi

        last_error="Progress response was not a valid view model"
      else
        last_error="Progress returned HTTP ${code:-unknown} with ${size:-0} bytes"
      fi
    else
      last_error="Progress request failed or exceeded five seconds"
    fi

    rm -f "$payload" "$metrics"
    sleep 2
  done

  fail "API readiness timed out after ${POCKETLAB_GATE_API_READY_TIMEOUT_SECONDS:-120}s: ${last_error:-unknown error}"
}

assert_progress_monotonic(){
  local payload="$1"
  python3 - "$STATE_FILE" "$payload" <<'PY'
import json, sys
state_path, payload_path = sys.argv[1:]
prior = json.load(open(state_path, encoding="utf-8"))
current = json.load(open(payload_path, encoding="utf-8"))
status = str(current.get("status") or "").lower()
active = bool(current.get("active_scan"))
run_id = current.get("run_id")
if status in {"queued", "accepted", "running", "working", "in_progress"} and not run_id:
    raise SystemExit("active status has no run_id")
if status in {"queued", "accepted", "running", "working", "in_progress"} and not active:
    raise SystemExit("active status contradicts active_scan=false")
if status in {"succeeded", "degraded", "failed", "cancelled", "canceled", "completed"} and active:
    raise SystemExit("terminal status contradicts active_scan=true")
if prior:
    if prior.get("run_id") and current.get("run_id") and prior["run_id"] != current["run_id"]:
        if int(current.get("requested_at_epoch_ms") or 0) < int(prior.get("requested_at_epoch_ms") or 0):
            raise SystemExit("run_id regressed")
    if prior.get("run_id") == current.get("run_id"):
        for key in ("sqlite_revision", "updated_at_epoch_ms"):
            if int(current.get(key) or 0) < int(prior.get(key) or 0):
                raise SystemExit(f"{key} regressed")
        if int(current.get("percent") or 0) < int(prior.get("percent") or 0):
            raise SystemExit("percent regressed")
        terminal = {"succeeded", "degraded", "failed", "cancelled", "canceled", "completed"}
        if str(prior.get("status") or "").lower() in terminal and active:
            raise SystemExit("terminal state returned to active")
json.dump(current, open(state_path, "w", encoding="utf-8"), sort_keys=True)
PY
}

sample_progress(){
  local label="$1" payload metrics code seconds size
  payload="$(mktemp)"; metrics="$(mktemp)"
  if ! curl_json GET "$PROGRESS_URL" '' "$payload" "$metrics"; then
    rm -f "$payload" "$metrics"
    fail "$label Progress request failed or exceeded five seconds"
  fi
  IFS=' ' read -r code seconds size < "$metrics"
  [[ "$code" == "200" || "$code" == "304" ]] || fail "$label returned HTTP $code"
  [[ "$size" -gt 0 || "$code" == "304" ]] || fail "$label returned an empty reply"
  printf '%s %s\n' "$label" "$seconds" >> "$SAMPLES"
  if [[ "$code" == "200" ]]; then
    if ! assert_progress_monotonic "$payload"; then
      rm -f "$payload" "$metrics"
      fail "$label Progress response violated monotonic state rules"
    fi
    cat "$payload"
  else
    cat "$STATE_FILE"
  fi
  rm -f "$payload" "$metrics"
}

wait_for_nats_reconnect(){
  local deadline payload metrics code seconds size
  deadline=$(( $(date +%s) + ${POCKETLAB_GATE_NATS_RECONNECT_TIMEOUT_SECONDS:-60} ))
  while (( $(date +%s) <= deadline )); do
    payload="$(mktemp)"; metrics="$(mktemp)"
    if curl_json GET "$NATS_STATUS_URL" '' "$payload" "$metrics"; then
      IFS=' ' read -r code seconds size < "$metrics"
      if [[ "$code" == "200" ]] && python3 - "$payload" <<'PY2'
import json, sys
payload=json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if payload.get("connected") is True and payload.get("watchdog_running") is True else 1)
PY2
      then
        rm -f "$payload" "$metrics"
        return 0
      fi
    fi
    rm -f "$payload" "$metrics"
    sleep 1
  done
  fail "FastAPI NATS client did not reconnect within the controlled timeout"
}

recover_timed_out_submission(){
  local prior_run="$1" started_ms="$2" deadline payload metrics code seconds size
  local candidate_run requested_ms status
  deadline=$(( $(date +%s) + ${POCKETLAB_GATE_SUBMISSION_RECOVERY_SECONDS:-8} ))
  while (( $(date +%s) <= deadline )); do
    payload="$(mktemp)"; metrics="$(mktemp)"
    if curl_json GET "$PROGRESS_URL" '' "$payload" "$metrics"; then
      IFS=' ' read -r code seconds size < "$metrics"
      if [[ "$code" == "200" && "$size" -gt 0 ]]; then
        candidate_run="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("run_id") or "")' "$payload")"
        requested_ms="$(python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1])).get("requested_at_epoch_ms") or 0))' "$payload")"
        status="$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1])).get("status") or "").lower())' "$payload")"
        if [[ -n "$candidate_run" && "$candidate_run" != "$prior_run" ]] \
          && (( requested_ms >= started_ms - 2000 )) \
          && [[ "$status" =~ ^(queued|accepted|running|working|in_progress|succeeded|degraded|completed|failed|cancelled|canceled)$ ]]; then
          rm -f "$payload" "$metrics"
          printf '%s' "$candidate_run"
          return 0
        fi
      fi
    fi
    rm -f "$payload" "$metrics"
    sleep 0.4
  done
  return 1
}

latency_gate(){
  local output rc
  set +e
  output="$(python3 - "$SAMPLES" <<'PYLAT'
import math, sys
values=[]
for line in open(sys.argv[1], encoding="utf-8"):
    parts=line.split()
    if parts:
        values.append(float(parts[-1]))
if not values:
    print("no latency samples", file=sys.stderr)
    raise SystemExit(1)
values.sort()
def pct(p):
    return values[min(len(values)-1, max(0, math.ceil(len(values)*p)-1))]
p50=pct(.50); p95=pct(.95); maximum=max(values)
print(f"Progress latency seconds: count={len(values)} p50={p50:.3f} p95={p95:.3f} max={maximum:.3f}")
failures=[]
if any(v > 5.0 for v in values): failures.append("one or more requests exceeded five seconds")
if p95 >= 1.0: failures.append("p95 latency is not below one second")
if maximum >= 3.0: failures.append("maximum latency is not below three seconds")
if failures:
    print("; ".join(failures), file=sys.stderr)
    raise SystemExit(1)
PYLAT
  2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$output"
  if (( rc != 0 )); then
    fail "Progress latency gate failed: ${output//$'\n'/; }"
  fi
}

submission_latency_gate(){
  if [[ -s "$SUBMISSION_FAILURES" ]]; then
    fail "one or more scan submissions exceeded the production response-latency limit: $(tr '\n' ';' < "$SUBMISSION_FAILURES")"
  fi
}

required_gate_functions(){
  local name
  for name in latency_gate submission_latency_gate capture_runtime_diagnostics write_final_report run_scan_gate sample_progress; do
    declare -F "$name" >/dev/null || fail "production gate is missing required function: $name"
  done
}


run_scan_gate(){
  local phase="$1" post metrics code seconds size run_id start deadline payload status projection_age
  local active_scan execution_started_at freshness_deadline=0
  local visible=0 seen_running=0 seen_execution=0 freshness_converged=0
  local curl_rc prior_payload prior_run submission_started_ms recovered_run
  post="$(mktemp)"; metrics="$(mktemp)"; prior_payload="$(mktemp)"
  if ! curl -fsS --max-time 5 "${AUTH_ARGS[@]}" "$PROGRESS_URL" -o "$prior_payload"; then
    rm -f "$post" "$metrics" "$prior_payload"
    fail "$phase could not capture pre-submission Progress state"
  fi
  prior_run="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("run_id") or "")' "$prior_payload")"
  submission_started_ms="$(python3 -c 'import time; print(int(time.time() * 1000))')"

  set +e
  curl_json POST "$CHECK_URL" '{"profile":"quick","reason":"production gate"}' "$post" "$metrics"
  curl_rc=$?
  set -e

  if (( curl_rc != 0 )); then
    recovered_run="$(recover_timed_out_submission "$prior_run" "$submission_started_ms" || true)"
    if [[ -z "$recovered_run" ]]; then
      rm -f "$post" "$metrics" "$prior_payload"
      fail "$phase scan submission timed out and no new run became visible"
    fi
    run_id="$recovered_run"
    printf '%s response_timeout_but_run_visible run_id=%s\n' "$phase" "$run_id" >> "$SUBMISSION_FAILURES"
    printf 'INFO: %s submission response exceeded five seconds; preserving visible run %s for validation\n' \
      "$phase" "$run_id" >&2
  else
    IFS=' ' read -r code seconds size < "$metrics"
    [[ "$code" == "202" ]] || fail "$phase scan submission returned HTTP $code"
    run_id="$(cat "$post" | json_field run_id)"
    [[ -n "$run_id" ]] || fail "$phase scan submission did not return run_id"
    if ! python3 - "$seconds" "${POCKETLAB_GATE_SUBMISSION_MAX_SECONDS:-5}" <<'PY2'
import sys
raise SystemExit(0 if float(sys.argv[1]) < float(sys.argv[2]) else 1)
PY2
    then
      printf '%s slow_response seconds=%s run_id=%s\n' "$phase" "$seconds" "$run_id" >> "$SUBMISSION_FAILURES"
    fi
  fi

  rm -f "$prior_payload"
  start="$(date +%s)"; deadline=$((start + TIMEOUT_SECONDS))
  while (( $(date +%s) <= deadline )); do
    payload="$(sample_progress "$phase")"
    if [[ "$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("run_id") or "")' <<<"$payload")" == "$run_id" ]]; then
      visible=1
      projection_age="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("projection_age_ms") or 0)' <<<"$payload")"
      active_scan="$(python3 -c 'import json,sys; print("1" if json.load(sys.stdin).get("active_scan") else "0")' <<<"$payload")"
      execution_started_at="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("execution_started_at") or "")' <<<"$payload")"
      [[ -n "$execution_started_at" ]] && seen_execution=1
      if [[ "$active_scan" == "1" ]]; then
        if python3 - "$projection_age" "$MAX_PROJECTION_AGE_MS" <<'PY2'
import sys
age=float(sys.argv[1]); maximum=float(sys.argv[2])
raise SystemExit(0 if 0 <= age <= maximum else 1)
PY2
        then
          freshness_converged=1
        elif (( freshness_converged == 1 )); then
          fail "$phase active projection age exceeded ${MAX_PROJECTION_AGE_MS}ms after freshness had converged"
        else
          if (( freshness_deadline == 0 )); then
            freshness_deadline=$(( $(date +%s) + ${POCKETLAB_GATE_ACTIVE_FRESHNESS_CONVERGENCE_SECONDS:-6} ))
          elif (( $(date +%s) > freshness_deadline )); then
            fail "$phase active projection age did not converge below ${MAX_PROJECTION_AGE_MS}ms within ${POCKETLAB_GATE_ACTIVE_FRESHNESS_CONVERGENCE_SECONDS:-6}s"
          fi
        fi
      fi
    fi
    if (( visible == 0 && $(date +%s) - start > 2 )); then
      fail "$phase submitted run_id did not appear within two seconds"
    fi
    status="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("status") or "").lower())' <<<"$payload")"
    [[ "$status" =~ ^(running|working|in_progress)$ ]] && seen_running=1
    if [[ "$status" =~ ^(succeeded|degraded|failed|cancelled|canceled|completed)$ ]] && (( visible == 1 )); then
      break
    fi
    sleep 0.4
  done
  (( visible == 1 )) || fail "$phase run never became visible"
  if (( seen_running == 0 && seen_execution == 0 )); then
    fail "$phase run has no durable execution evidence"
  fi
  [[ "$status" =~ ^(succeeded|degraded|completed)$ ]] || fail "$phase run ended with unacceptable terminal status: $status"
  if ! (cd "$REPO_ROOT" && python3 scripts/lite/security-db-check.py >/dev/null); then
    fail "$phase SQLite database check failed"
  fi
  if ! compare="$(cd "$REPO_ROOT" && python3 scripts/lite/security-db-compare.py)"; then
    fail "$phase JSON/SQLite comparison command failed"
  fi
  python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("matched") is True and not d.get("mismatch_fields")' <<<"$compare" \
    || fail "$phase JSON/SQLite parity failed"
  if pgrep -f '[l]ynis|[t]rivy' >/dev/null 2>&1; then
    fail "$phase scanner descendants remain after terminal completion"
  fi
  for _ in 1 2 3; do sample_progress "$phase-post-terminal" >/dev/null; done
  rm -f "$post" "$metrics"
  printf '%s' "$run_id"
}

worker_pid(){
  pm2 jlist 2>/dev/null | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(next((r.get("pid","") for r in rows if r.get("name")=="pocket-worker"),""))'
}

required_gate_functions
wait_for_api_ready
info "Checking idle Progress path"
for _ in 1 2 3 4 5; do sample_progress idle >/dev/null; done
STORE_MODE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("storage_backend") or "unknown")' "$STATE_FILE")"
first_run="$(run_scan_gate "${STORE_MODE}-mode")"

if [[ "${POCKETLAB_GATE_RESTART_NATS:-0}" == "1" ]]; then
  before_pid="$(worker_pid)"; [[ -n "$before_pid" ]] || fail "could not read pocket-worker PID"
  pm2 restart pocket-nats >/dev/null
  wait_for_nats_reconnect
  sleep "${POCKETLAB_GATE_WORKER_RECONNECT_SETTLE_SECONDS:-2}"
  after_pid="$(worker_pid)"
  [[ "$before_pid" == "$after_pid" ]] || fail "pocket-worker PID changed across NATS restart"
  second_run="$(run_scan_gate post-reconnect)"
else
  second_run="not-run"
  info "NATS restart gate skipped; set POCKETLAB_GATE_RESTART_NATS=1 for the controlled reconnect gate"
fi

latency_gate
(cd "$REPO_ROOT" && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/backend/test_lite_security_progress_projection_cutover.py \
  tests/backend/test_lite_worker_recovery.py -k 'stale or projection or redeliver')

submission_latency_gate || fail "one or more scan submissions exceeded the production response-latency limit"
