#!/usr/bin/env bash
set -euo pipefail

ROOT="${POCKETLAB_BASE_DIR:-$HOME/pocket-lab-lite}"
STATE_DIR="${POCKETLAB_STATE_DIR:-$ROOT/state}"
PROXY_BASE="${POCKETLAB_PROXY_BASE:-http://127.0.0.1:8443}"
IDLE_SECONDS="${POCKETLAB_PHASE3B_IDLE_SECONDS:-60}"
WARMUP_ATTEMPTS="${POCKETLAB_PHASE3B_WARMUP_ATTEMPTS:-15}"
READY_ATTEMPTS="${POCKETLAB_PHASE3B_READY_ATTEMPTS:-30}"
READY_CONNECT_TIMEOUT="${POCKETLAB_PHASE3B_READY_CONNECT_TIMEOUT:-2}"
READY_MAX_TIME="${POCKETLAB_PHASE3B_READY_MAX_TIME:-10}"
QUIESCENCE_ATTEMPTS="${POCKETLAB_PHASE3B_QUIESCENCE_ATTEMPTS:-30}"
QUIESCENCE_SLEEP_SECONDS="${POCKETLAB_PHASE3B_QUIESCENCE_SLEEP_SECONDS:-2}"
RUNTIME_MAX_TIME="${POCKETLAB_PHASE3B_RUNTIME_MAX_TIME:-30}"
RUNTIME_ATTEMPTS="${POCKETLAB_PHASE3B_RUNTIME_ATTEMPTS:-3}"
RUN_ID="phase3b-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN_DIR="$STATE_DIR/.pocketlab-dev/phase3b/$RUN_ID"
mkdir -p "$RUN_DIR"

finalize_phase3b_gate() {
  local rc="$?"
  set +e
  python3 - "$RUN_DIR" "$RUN_ID" "$rc" <<'PYFINAL'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); run_id=sys.argv[2]; rc=int(sys.argv[3])
checksums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file() and p.name not in {'checksums.json','summary.json'}}
(root/'checksums.json').write_text(json.dumps(checksums,sort_keys=True,indent=2)+'\n',encoding='utf-8')
(root/'summary.json').write_text(json.dumps({'status':'passed' if rc == 0 else 'failed','run_id':run_id,'exit_code':rc,'sanitized':True},sort_keys=True,indent=2)+'\n',encoding='utf-8')
PYFINAL
  printf '%s\n' "$RUN_DIR"
  trap - EXIT
  exit "$rc"
}
trap finalize_phase3b_gate EXIT

case "$IDLE_SECONDS" in
  ''|*[!0-9]*) echo "POCKETLAB_PHASE3B_IDLE_SECONDS must be an integer" >&2; exit 2 ;;
esac
if [ "$IDLE_SECONDS" -gt 1800 ]; then
  echo "POCKETLAB_PHASE3B_IDLE_SECONDS must be 1800 or less" >&2
  exit 2
fi
case "$WARMUP_ATTEMPTS" in
  ''|*[!0-9]*) echo "POCKETLAB_PHASE3B_WARMUP_ATTEMPTS must be an integer" >&2; exit 2 ;;
esac
case "$READY_ATTEMPTS" in
  ''|*[!0-9]*) echo "POCKETLAB_PHASE3B_READY_ATTEMPTS must be an integer" >&2; exit 2 ;;
esac
case "$QUIESCENCE_ATTEMPTS" in
  ''|*[!0-9]*) echo "POCKETLAB_PHASE3B_QUIESCENCE_ATTEMPTS must be an integer" >&2; exit 2 ;;
esac
case "$QUIESCENCE_SLEEP_SECONDS" in
  ''|*[!0-9]*) echo "POCKETLAB_PHASE3B_QUIESCENCE_SLEEP_SECONDS must be an integer" >&2; exit 2 ;;
esac
case "$RUNTIME_MAX_TIME" in
  ''|*[!0-9]*) echo "POCKETLAB_PHASE3B_RUNTIME_MAX_TIME must be an integer" >&2; exit 2 ;;
esac
case "$RUNTIME_ATTEMPTS" in
  ''|*[!0-9]*) echo "POCKETLAB_PHASE3B_RUNTIME_ATTEMPTS must be an integer" >&2; exit 2 ;;
esac
[ "$RUNTIME_MAX_TIME" -ge 10 ] && [ "$RUNTIME_MAX_TIME" -le 60 ] || { echo "POCKETLAB_PHASE3B_RUNTIME_MAX_TIME must be between 10 and 60" >&2; exit 2; }
[ "$RUNTIME_ATTEMPTS" -ge 1 ] && [ "$RUNTIME_ATTEMPTS" -le 5 ] || { echo "POCKETLAB_PHASE3B_RUNTIME_ATTEMPTS must be between 1 and 5" >&2; exit 2; }

wait_for_api_ready() {
  local attempt
  for attempt in $(seq 1 "$READY_ATTEMPTS"); do
    if curl -fsS --connect-timeout "$READY_CONNECT_TIMEOUT" \
      --max-time "$READY_MAX_TIME" "$PROXY_BASE/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Pocket API did not become ready during the bounded Phase 3B readiness gate" >&2
  return 1
}

fetch_json() {
  local name="$1"
  local path="$2"
  local output="$RUN_DIR/$name.json"
  local code

  code="$(
    curl -sS --connect-timeout "$READY_CONNECT_TIMEOUT" \
      --max-time "$READY_MAX_TIME" \
      -o "$output" -w '%{http_code}' "$PROXY_BASE$path"
  )"
  if [ "$code" != "200" ]; then
    echo "Phase 3B endpoint failed: $path returned HTTP $code" >&2
    sed -n '1,80p' "$output" >&2 || true
    return 1
  fi
  if ! python3 -m json.tool "$output" >/dev/null; then
    echo "Phase 3B endpoint returned invalid JSON: $path" >&2
    return 1
  fi
}

fetch_runtime_evidence() {
  local name="$1"
  local raw="$RUN_DIR/.$name.raw"
  local attempt
  local code

  for attempt in $(seq 1 "$RUNTIME_ATTEMPTS"); do
    code="$(curl -sS --connect-timeout "$READY_CONNECT_TIMEOUT" --max-time "$RUNTIME_MAX_TIME" -o "$raw" -w '%{http_code}' "$PROXY_BASE/api/lite/diagnostics/runtime")" || code="000"
    if [ "$code" = "200" ] && python3 -m json.tool "$raw" >/dev/null 2>&1; then
      python3 - "$raw" "$RUN_DIR/$name.json" <<'PYRUNTIME'
import json,pathlib,sys
payload=json.load(open(sys.argv[1],encoding='utf-8'))
required={
 'security.progress','security.summary','system.status','system.health',
 'system.processes','system.agent','system.supervisor','system.remote_access',
 'system.nats_remote','system.fleet_probe',
}
phase=payload.get('phase3b_current_state') or {}
scheduler=payload.get('projection_scheduler') or {}
domains=scheduler.get('domains') or {}
safe={
 'phase3b_current_state':{
   'domains':{name:(phase.get('domains') or {}).get(name,{}) for name in sorted(required)},
   'payload_budget_bytes':int(phase.get('payload_budget_bytes') or 65536),
   'sanitized':True,
 },
 'projection_scheduler':{
   'domains':{name:domains.get(name,{}) for name in sorted(required)},
   'max_domains':int(scheduler.get('max_domains') or 0),
   'registered_domains':int(scheduler.get('registered_domains') or 0),
   'remaining_domain_capacity':int(scheduler.get('remaining_domain_capacity') or 0),
   'sanitized':True,
 },
 'sanitized':True,
}
pathlib.Path(sys.argv[2]).write_text(json.dumps(safe,sort_keys=True,indent=2)+'\n',encoding='utf-8')
PYRUNTIME
      rm -f "$raw"
      return 0
    fi
    echo "Phase 3B runtime diagnostics attempt $attempt/$RUNTIME_ATTEMPTS failed: HTTP $code" >&2
    sleep 2
  done
  rm -f "$raw"
  return 1
}

fetch_prepared_endpoints() {
  local suffix="$1"
  fetch_json "status$suffix" /api/lite/status
  fetch_json "fleet$suffix" /api/lite/fleet
  fetch_json "security-summary$suffix" /api/lite/security/summary
  fetch_json "security-progress$suffix" /api/lite/security/progress
  fetch_json "system-health$suffix" /api/lite/system/health
  fetch_json "system-processes$suffix" /api/lite/system/processes
  fetch_json "system-agent$suffix" /api/lite/system/agent
  fetch_json "system-supervisor$suffix" /api/lite/system/supervisor
  fetch_json "remote-access$suffix" /api/lite/remote-access/readiness
  fetch_json "nats-readiness$suffix" /api/lite/system/nats-readiness
}

wait_for_scheduler_quiescent() {
  local output_name="$1"
  local attempt

  for attempt in $(seq 1 "$QUIESCENCE_ATTEMPTS"); do
    fetch_runtime_evidence "$output_name"

    if python3 - "$RUN_DIR/$output_name.json" <<'PYQ'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
scheduler = (payload.get("projection_scheduler") or {}).get("domains") or {}

required = {
    "security.progress",
    "security.summary",
    "system.status",
    "system.health",
    "system.processes",
    "system.agent",
    "system.supervisor",
    "system.remote_access",
    "system.nats_remote",
    "system.fleet_probe",
}

busy = {}
for name in sorted(required):
    row = scheduler.get(name) or {}
    reasons = [
        key
        for key in (
            "refresh_pending",
            "active",
            "queued",
            "followup_requested",
        )
        if bool(row.get(key))
    ]
    if reasons:
        busy[name] = reasons

if busy:
    print(
        json.dumps(
            {"scheduler_not_quiescent": busy},
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    raise SystemExit(1)
PYQ
    then
      return 0
    fi

    sleep "$QUIESCENCE_SLEEP_SECONDS"
  done

  echo "Phase 3B scheduler did not become quiescent after the idle read cycle" >&2
  return 1
}

validate_runtime() {
  local runtime_path="$1"
  local metrics_path="$2"
  python3 - "$runtime_path" "$metrics_path" <<'PY'
import json, pathlib, sys
payload=json.load(open(sys.argv[1], encoding="utf-8"))
metrics_path=pathlib.Path(sys.argv[2])
phase3b=payload.get("phase3b_current_state") or {}
prepared_domains=phase3b.get("domains") or {}
scheduler=((payload.get("projection_scheduler") or {}).get("domains") or {})
required={
 "security.progress", "security.summary", "system.status", "system.health",
 "system.processes", "system.agent", "system.supervisor",
 "system.remote_access", "system.nats_remote", "system.fleet_probe",
}
missing=sorted(required-set(prepared_domains))
unprepared=sorted(name for name in required if not (prepared_domains.get(name) or {}).get("prepared"))
unregistered=sorted(name for name in required if not (scheduler.get(name) or {}).get("registered"))
callbacks=sorted(name for name in required if not (scheduler.get(name) or {}).get("source_revision_enabled"))
invalid_source=sorted(name for name in required if int((scheduler.get(name) or {}).get("source_revision") or 0) <= 0)
invalid_projection=sorted(name for name in required if int((prepared_domains.get(name) or {}).get("projection_revision") or 0) <= 0)
not_executed=sorted(
    name
    for name in required
    if int((scheduler.get(name) or {}).get("execution_count") or 0) < 1
)
no_successful_outcome=sorted(
    name
    for name in required
    if (
        int((scheduler.get(name) or {}).get("committed_count") or 0)
        + int((scheduler.get(name) or {}).get("unchanged_count") or 0)
    ) < 1
)
failed=sorted(name for name in required if int((scheduler.get(name) or {}).get("failure_count") or 0) > 0)
stale=sorted(name for name in required if int((scheduler.get(name) or {}).get("stale_generation_count") or 0) > 0)
errors=sorted(name for name in required if str((scheduler.get(name) or {}).get("last_error_type") or ""))
problems={
 "missing":missing, "unprepared":unprepared, "unregistered":unregistered,
 "callbacks_disabled":callbacks, "invalid_source_revision":invalid_source,
 "invalid_projection_revision":invalid_projection, "not_executed":not_executed,
 "no_successful_outcome":no_successful_outcome, "failed":failed,
 "stale_generation":stale,
 "last_errors":errors,
}
active={key:value for key,value in problems.items() if value}
if active:
    print(json.dumps(active, sort_keys=True), file=sys.stderr)
    raise SystemExit(1)
metrics={
 name:{
   "source_revision":int(scheduler[name].get("source_revision") or 0),
   "projection_revision":int(prepared_domains[name].get("projection_revision") or 0),
   "execution_count":int(scheduler[name].get("execution_count") or 0),
   "committed_count":int(scheduler[name].get("committed_count") or 0),
   "unchanged_count":int(scheduler[name].get("unchanged_count") or 0),
   "failure_count":int(scheduler[name].get("failure_count") or 0),
   "stale_generation_count":int(scheduler[name].get("stale_generation_count") or 0),
   "refresh_pending":bool(scheduler[name].get("refresh_pending")),
   "followup_requested":bool(scheduler[name].get("followup_requested")),
 }
 for name in sorted(required)
}
metrics_path.write_text(json.dumps(metrics, sort_keys=True, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"status":"passed","domains":len(required),"sanitized":True}, sort_keys=True))
PY
}

wait_for_api_ready
fetch_prepared_endpoints ""
ready=0
for attempt in $(seq 1 "$WARMUP_ATTEMPTS"); do
  fetch_runtime_evidence runtime
  if validate_runtime "$RUN_DIR/runtime.json" "$RUN_DIR/scheduler-before.json"; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  echo "Phase 3B projections did not become ready during bounded warm-up" >&2
  exit 1
fi

pm2 jlist | python3 -c '
import json, sys
rows=json.load(sys.stdin)
print(json.dumps([
  {"name": str(row.get("name") or "")[:80],
   "status": str((row.get("pm2_env") or {}).get("status") or "unknown")[:24],
   "restarts": int((row.get("pm2_env") or {}).get("restart_time") or 0)}
  for row in rows if isinstance(row, dict)
], sort_keys=True))
' > "$RUN_DIR/pm2-sanitized.json"

if command -v tailscale-cli >/dev/null 2>&1; then
  tailscale-cli ip -4 2>/dev/null | sed -n '1p' > "$RUN_DIR/tailscale-ip.txt" || true
elif command -v tailscale >/dev/null 2>&1; then
  tailscale ip -4 2>/dev/null | sed -n '1p' > "$RUN_DIR/tailscale-ip.txt" || true
else
  : > "$RUN_DIR/tailscale-ip.txt"
fi

if [ "$IDLE_SECONDS" -gt 0 ]; then
  sleep "$IDLE_SECONDS"
  fetch_prepared_endpoints "-after-idle"

  # The reads above may legitimately schedule stale-while-refreshing work.
  # Wait for that bounded reconciliation to settle before asserting the
  # strict final idle state. Persistent invalidation loops still time out.
  wait_for_scheduler_quiescent "runtime-after-idle"

  validate_runtime "$RUN_DIR/runtime-after-idle.json" "$RUN_DIR/scheduler-after.json"
  python3 - "$RUN_DIR/scheduler-before.json" "$RUN_DIR/scheduler-after.json" <<'PY'
import json, sys
before=json.load(open(sys.argv[1], encoding="utf-8"))
after=json.load(open(sys.argv[2], encoding="utf-8"))
report={}
for name in sorted(before):
    first=before[name]
    second=after[name]
    source_changed=second["source_revision"] != first["source_revision"]
    commit_delta=second["committed_count"]-first["committed_count"]
    unchanged_delta=second["unchanged_count"]-first["unchanged_count"]
    if second["failure_count"] or second["stale_generation_count"]:
        raise SystemExit(f"scheduler failure/stale generation after idle: {name}")
    if second["refresh_pending"] or second["followup_requested"]:
        raise SystemExit(f"scheduler still pending after idle: {name}")
    if commit_delta > 2:
        raise SystemExit(f"unexpected commit churn after idle: {name} delta={commit_delta}")
    report[name]={
      "source_revision_stable":not source_changed,
      "commit_delta":commit_delta,
      "unchanged_delta":unchanged_delta,
    }
if not any(item["unchanged_delta"] > 0 for item in report.values()):
    raise SystemExit("no unchanged-source skip was observed after the idle read cycle")
print(json.dumps({"status":"passed","domains":report,"sanitized":True}, sort_keys=True))
PY
fi

python3 - "$RUN_DIR" <<'PYSAFE'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1])
markers=('password=','token=','nats://','/data/data/','-----begin')
leaks={}
for path in sorted(root.glob('*.json')):
    text=path.read_text(encoding='utf-8',errors='replace').lower()
    found=[marker for marker in markers if marker in text]
    if found: leaks[path.name]=found
if leaks:
    print(json.dumps({'unsafe_evidence_markers':leaks},sort_keys=True),file=sys.stderr)
    raise SystemExit(1)
PYSAFE
