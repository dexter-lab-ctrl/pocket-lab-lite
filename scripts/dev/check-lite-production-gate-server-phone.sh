#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_URL="${POCKETLAB_GATE_BASE_URL:-http://127.0.0.1:8443}"
PROGRESS_URL="$BASE_URL/api/lite/security/progress"
CHECK_URL="$BASE_URL/api/lite/security/check"
NATS_STATUS_URL="$BASE_URL/api/nats/status"
TIMEOUT_SECONDS="${POCKETLAB_GATE_SCAN_TIMEOUT_SECONDS:-5400}"
MAX_PROJECTION_AGE_MS="${POCKETLAB_GATE_MAX_PROJECTION_AGE_MS:-5000}"
REPORT_DIR="${POCKETLAB_GATE_REPORT_DIR:-${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}/.pocketlab-dev/reports}"
STAMP="$(date -u +%Y%m%d-%H%M%S)-$$"
REPORT_JSON="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP.json"
SAMPLES="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-latencies.txt"
STATE_FILE="$REPORT_DIR/pocketlab-lite-production-gate-$STAMP-progress.json"
mkdir -p "$REPORT_DIR"
: > "$SAMPLES"
printf '%s' '{}' > "$STATE_FILE"

AUTH_ARGS=()
if [[ -n "${POCKETLAB_API_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${POCKETLAB_API_TOKEN}")
fi

fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
info(){ printf 'INFO: %s\n' "$*"; }

on_error(){
  local rc=$?
  local line="${BASH_LINENO[0]:-unknown}"
  printf 'FAIL: production gate aborted at line %s with exit code %s\n' "$line" "$rc" >&2
  exit "$rc"
}
trap on_error ERR
json_field(){ python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1"; }

curl_json(){
  local method="$1" url="$2" body="${3:-}" out="$4" metrics="$5"
  local args=(-fsS --max-time 5 -X "$method" "${AUTH_ARGS[@]}" -H 'Accept: application/json')
  if [[ -n "$body" ]]; then
    args+=(-H 'Content-Type: application/json' --data "$body")
  fi
  curl "${args[@]}" -o "$out" -w '%{http_code} %{time_total} %{size_download}' "$url" > "$metrics"
}

wait_for_api_ready(){
  local deadline payload metrics code seconds size last_error=""
  deadline=$(( $(date +%s) + ${POCKETLAB_GATE_API_READY_TIMEOUT_SECONDS:-120} ))

  info "Waiting for API and Security Progress readiness"
  while (( $(date +%s) <= deadline )); do
    payload="$(mktemp)"
    metrics="$(mktemp)"

    if curl_json GET "$PROGRESS_URL" '' "$payload" "$metrics"; then
      IFS=' ' read -r code seconds size < "$metrics"
      if [[ "$code" == "200" && "$size" -gt 0 ]]; then
        if python3 - "$payload" <<'PY2'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
raise SystemExit(0 if isinstance(payload, dict) and payload.get("view_model") else 1)
PY2
        then
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

latency_gate(){
  python3 - "$SAMPLES" <<'PY'
import math, statistics, sys
values=[]
for line in open(sys.argv[1], encoding="utf-8"):
    parts=line.split()
    if parts:
        values.append(float(parts[-1]))
if not values:
    raise SystemExit("no latency samples")
values.sort()
def pct(p):
    return values[min(len(values)-1, max(0, math.ceil(len(values)*p)-1))]
p50=pct(.50); p95=pct(.95); maximum=max(values)
print(f"Progress latency seconds: count={len(values)} p50={p50:.3f} p95={p95:.3f} max={maximum:.3f}")
if any(v > 5.0 for v in values):
    raise SystemExit("one or more requests exceeded five seconds")
if p95 >= 1.0:
    raise SystemExit("p95 latency is not below one second")
if maximum >= 3.0:
    raise SystemExit("maximum latency is not below three seconds")
PY
}

run_scan_gate(){
  local phase="$1" post metrics code seconds size run_id start deadline payload status projection_age
  local visible=0 seen_running=0
  post="$(mktemp)"; metrics="$(mktemp)"
  curl_json POST "$CHECK_URL" '{"profile":"quick","reason":"production gate"}' "$post" "$metrics" \
    || fail "$phase scan submission failed"
  IFS=' ' read -r code seconds size < "$metrics"
  [[ "$code" == "202" ]] || fail "$phase scan submission returned HTTP $code"
  run_id="$(cat "$post" | json_field run_id)"
  [[ -n "$run_id" ]] || fail "$phase scan submission did not return run_id"
  start="$(date +%s)"; deadline=$((start + TIMEOUT_SECONDS))
  while (( $(date +%s) <= deadline )); do
    payload="$(sample_progress "$phase")"
    if [[ "$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("run_id") or "")' <<<"$payload")" == "$run_id" ]]; then
      visible=1
      projection_age="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("projection_age_ms") or 0)' <<<"$payload")"
      if ! python3 - "$projection_age" "$MAX_PROJECTION_AGE_MS" <<'PY2'
import sys
age=float(sys.argv[1]); maximum=float(sys.argv[2])
raise SystemExit(0 if 0 <= age <= maximum else 1)
PY2
      then
        fail "$phase projection age exceeded ${MAX_PROJECTION_AGE_MS}ms after the submitted run became visible"
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
  (( seen_running == 1 )) || fail "$phase run did not advance through a running state"
  [[ "$status" =~ ^(succeeded|degraded|completed)$ ]] || fail "$phase run ended with unacceptable terminal status: $status"
  (cd "$REPO_ROOT" && python3 scripts/lite/security-db-check.py >/dev/null)
  compare="$(cd "$REPO_ROOT" && python3 scripts/lite/security-db-compare.py)"
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

wait_for_api_ready
info "Checking idle Progress path"
for _ in 1 2 3 4 5; do sample_progress idle >/dev/null; done
first_run="$(run_scan_gate dual-mode)"

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

python3 - "$REPORT_JSON" "$SAMPLES" "$first_run" "$second_run" <<'PY'
import json, math, sys
report, samples, first_run, second_run = sys.argv[1:]
values=[float(line.split()[-1]) for line in open(samples, encoding="utf-8") if line.split()]
values.sort()
def pct(p):
    return values[min(len(values)-1, max(0, math.ceil(len(values)*p)-1))]
payload={
  "status":"ready",
  "failed_gates":0,
  "security_store_mode":__import__("os").environ.get("POCKETLAB_LITE_SECURITY_STORE_MODE", "dual"),
  "first_run_id":first_run,
  "post_reconnect_run_id":second_run,
  "progress_latency_seconds":{
    "count":len(values), "p50":round(pct(.5),3),
    "p95":round(pct(.95),3), "max":round(max(values),3),
  },
  "sanitized":True,
}
json.dump(payload, open(report,"w",encoding="utf-8"), indent=2, sort_keys=True)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
info "Report: $REPORT_JSON"
