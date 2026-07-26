#!/usr/bin/env bash
set -euo pipefail

ROOT="${POCKETLAB_BASE_DIR:-$HOME/pocket-lab-lite}"
STATE_DIR="${POCKETLAB_STATE_DIR:-$ROOT/state}"
PROXY_BASE="${POCKETLAB_PROXY_BASE:-http://127.0.0.1:8443}"
IDLE_SECONDS="${POCKETLAB_PHASE3C_IDLE_SECONDS:-60}"
READY_ATTEMPTS="${POCKETLAB_PHASE3C_READY_ATTEMPTS:-30}"
WARMUP_ATTEMPTS="${POCKETLAB_PHASE3C_WARMUP_ATTEMPTS:-20}"
QUIESCENCE_ATTEMPTS="${POCKETLAB_PHASE3C_QUIESCENCE_ATTEMPTS:-30}"
IDLE_BASELINE_ATTEMPTS="${POCKETLAB_PHASE3C_IDLE_BASELINE_ATTEMPTS:-60}"
IDLE_STABLE_SAMPLES="${POCKETLAB_PHASE3C_IDLE_STABLE_SAMPLES:-3}"
RUNTIME_MAX_TIME="${POCKETLAB_PHASE3C_RUNTIME_MAX_TIME:-30}"
RUNTIME_ATTEMPTS="${POCKETLAB_PHASE3C_RUNTIME_ATTEMPTS:-3}"
RUN_ID="phase3c-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN_DIR="$STATE_DIR/.pocketlab-dev/phase3c/$RUN_ID"
ACTIVITY_HELPER="$ROOT/scripts/dev/lib/phase3c_gate_activity.py"
mkdir -p "$RUN_DIR"

finalize_phase3c_gate() {
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
trap finalize_phase3c_gate EXIT

for value in "$IDLE_SECONDS" "$READY_ATTEMPTS" "$WARMUP_ATTEMPTS" "$QUIESCENCE_ATTEMPTS" "$IDLE_BASELINE_ATTEMPTS" "$IDLE_STABLE_SAMPLES" "$RUNTIME_MAX_TIME" "$RUNTIME_ATTEMPTS"; do
  case "$value" in ''|*[!0-9]*) echo "Phase 3C gate values must be integers" >&2; exit 2;; esac
done
[ "$IDLE_SECONDS" -le 1800 ] || { echo "POCKETLAB_PHASE3C_IDLE_SECONDS must be 1800 or less" >&2; exit 2; }
[ "$RUNTIME_MAX_TIME" -ge 10 ] && [ "$RUNTIME_MAX_TIME" -le 60 ] || { echo "POCKETLAB_PHASE3C_RUNTIME_MAX_TIME must be between 10 and 60" >&2; exit 2; }
[ "$RUNTIME_ATTEMPTS" -ge 1 ] && [ "$RUNTIME_ATTEMPTS" -le 5 ] || { echo "POCKETLAB_PHASE3C_RUNTIME_ATTEMPTS must be between 1 and 5" >&2; exit 2; }
[ "$IDLE_BASELINE_ATTEMPTS" -ge 3 ] && [ "$IDLE_BASELINE_ATTEMPTS" -le 300 ] || { echo "POCKETLAB_PHASE3C_IDLE_BASELINE_ATTEMPTS must be between 3 and 300" >&2; exit 2; }
[ "$IDLE_STABLE_SAMPLES" -eq 3 ] || { echo "POCKETLAB_PHASE3C_IDLE_STABLE_SAMPLES must be 3" >&2; exit 2; }

fetch_json() {
  local name="$1" path="$2"
  curl -fsS --connect-timeout 2 --max-time 10 "$PROXY_BASE$path" > "$RUN_DIR/$name.json"
  python3 -m json.tool "$RUN_DIR/$name.json" >/dev/null
}

prime_json() {
  local name="$1" path="$2" code
  code="$(curl -sS --connect-timeout 2 --max-time 10 -o "$RUN_DIR/$name.json" -w '%{http_code}' "$PROXY_BASE$path")"
  python3 -m json.tool "$RUN_DIR/$name.json" >/dev/null
  case "$code" in 200|503) ;; *) echo "Unexpected HTTP $code while priming $path" >&2; return 1;; esac
}

fetch_runtime_evidence() {
  local name="$1"
  local raw="$RUN_DIR/.$name.raw"
  local attempt
  local code

  for attempt in $(seq 1 "$RUNTIME_ATTEMPTS"); do
    code="$(curl -sS --connect-timeout 2 --max-time "$RUNTIME_MAX_TIME" -o "$raw" -w '%{http_code}' "$PROXY_BASE/api/lite/diagnostics/runtime")" || code="000"
    if [ "$code" = "200" ] && python3 -m json.tool "$raw" >/dev/null 2>&1; then
      python3 - "$raw" "$RUN_DIR/$name.json" <<'PYRUNTIME'
import json,pathlib,sys
payload=json.load(open(sys.argv[1],encoding='utf-8'))
required={
 'system.telemetry_thresholds','system.storage_pressure',
 'system.sqlite_health','system.activity_summary',
}
phase3c=payload.get('phase3c_current_state') or {}
scheduler=payload.get('projection_scheduler') or {}
domains=scheduler.get('domains') or {}
safe={
 'phase3c_current_state':{
   'domains':{name:(phase3c.get('domains') or {}).get(name,{}) for name in sorted(required)},
   'payload_budget_bytes':int(phase3c.get('payload_budget_bytes') or 65536),
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
    echo "Phase 3C runtime diagnostics attempt $attempt/$RUNTIME_ATTEMPTS failed: HTTP $code" >&2
    sleep 2
  done
  rm -f "$raw"
  return 1
}


activity_semantic_sample() {
  python3 "$ACTIVITY_HELPER" sample "$1" "$2"
}

activity_sample_matches() {
  python3 "$ACTIVITY_HELPER" matches "$1" "$2"
}

activity_scheduler_quiescent() {
  local runtime="$1"
  python3 - "$runtime" <<'PYQUIET'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
s=((p.get('projection_scheduler') or {}).get('domains') or {}).get('system.activity_summary') or {}
busy=[key for key in ('refresh_pending','active','queued','followup_requested') if bool(s.get(key))]
if busy:
    print(json.dumps({'system.activity_summary':busy},sort_keys=True),file=sys.stderr)
    raise SystemExit(1)
PYQUIET
}

wait_for_semantic_idle_baseline() {
  local stable=0 attempt=0 previous="$RUN_DIR/.activity-baseline-previous.json"
  local candidate="$RUN_DIR/.activity-baseline-candidate.json"
  rm -f "$previous" "$candidate"
  for attempt in $(seq 1 "$IDLE_BASELINE_ATTEMPTS"); do
    fetch_json activity-summary-baseline-candidate /api/lite/system/activity-summary
    if ! activity_semantic_sample "$RUN_DIR/activity-summary-baseline-candidate.json" "$candidate"; then
      stable=0; rm -f "$previous" "$candidate"; sleep 2; continue
    fi
    if ! fetch_runtime_evidence runtime-baseline-candidate || ! activity_scheduler_quiescent "$RUN_DIR/runtime-baseline-candidate.json"; then
      stable=0; rm -f "$previous" "$candidate"; sleep 2; continue
    fi
    if [ -s "$previous" ] && activity_sample_matches "$previous" "$candidate"; then
      stable=$((stable + 1))
    else
      stable=1
    fi
    cp "$candidate" "$previous"
    if [ "$stable" -ge "$IDLE_STABLE_SAMPLES" ]; then
      cp "$RUN_DIR/activity-summary-baseline-candidate.json" "$RUN_DIR/activity-summary.json"
      cp "$RUN_DIR/runtime-baseline-candidate.json" "$RUN_DIR/runtime.json"
      cp "$candidate" "$RUN_DIR/activity-baseline.json"
      rm -f "$previous" "$candidate"
      return 0
    fi
    sleep 2
  done
  rm -f "$previous" "$candidate"
  echo "Phase 3C semantic-idle baseline did not stabilize" >&2
  return 1
}

verify_activity_remained_idle() {
  python3 "$ACTIVITY_HELPER" observe "$RUN_DIR/activity-baseline.json" "$1" "$RUN_DIR/activity-after.json"
}

ready=0
for _ in $(seq 1 "$READY_ATTEMPTS"); do
  if curl -fsS --connect-timeout 2 --max-time 10 "$PROXY_BASE/health" >/dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
[ "$ready" -eq 1 ] || { echo "Pocket API did not become ready during the bounded Phase 3C gate" >&2; exit 1; }

for path in telemetry-thresholds storage-pressure sqlite-health activity-summary; do
  prime_json "$path" "/api/lite/system/$path"
done

validate_runtime() {
  local input="$1" output="$2"
  python3 - "$input" "$output" <<'PY'
import json, pathlib, sys
payload=json.load(open(sys.argv[1], encoding='utf-8'))
phase=(payload.get('phase3c_current_state') or {}).get('domains') or {}
scheduler=(payload.get('projection_scheduler') or {}).get('domains') or {}
required={
 'system.telemetry_thresholds','system.storage_pressure',
 'system.sqlite_health','system.activity_summary',
}
problems={
 'missing': sorted(required-set(phase)),
 'unprepared': sorted(name for name in required if not (phase.get(name) or {}).get('prepared')),
 'unregistered': sorted(name for name in required if not (scheduler.get(name) or {}).get('registered')),
 'callbacks_disabled': sorted(name for name in required if not (scheduler.get(name) or {}).get('source_revision_enabled')),
 'invalid_source_revision': sorted(name for name in required if int((scheduler.get(name) or {}).get('source_revision') or 0) <= 0),
 'invalid_projection_revision': sorted(name for name in required if int((phase.get(name) or {}).get('projection_revision') or 0) <= 0),
 'not_executed': sorted(name for name in required if int((scheduler.get(name) or {}).get('execution_count') or 0) < 1),
 'not_committed': sorted(name for name in required if int((scheduler.get(name) or {}).get('committed_count') or 0) < 1),
 'failures': sorted(name for name in required if int((scheduler.get(name) or {}).get('failure_count') or 0) > 0),
 'stale_generations': sorted(name for name in required if int((scheduler.get(name) or {}).get('stale_generation_count') or 0) > 0),
 'oversized': sorted(name for name in required if int((phase.get(name) or {}).get('payload_bytes') or 0) > int((payload.get('phase3c_current_state') or {}).get('payload_budget_bytes') or 65536)),
}
active={key:value for key,value in problems.items() if value}
encoded=json.dumps({'phase3c':phase},sort_keys=True).lower()
leaks=[value for value in ('password=','token=','nats://','/data/data/','-----begin') if value in encoded]
if leaks:
    active['unsafe_payload_markers']=leaks
if active:
    print(json.dumps(active, sort_keys=True), file=sys.stderr); raise SystemExit(1)
metrics={name:{
 'source_revision':int(scheduler[name].get('source_revision') or 0),
 'projection_revision':int(phase[name].get('projection_revision') or 0),
 'execution_count':int(scheduler[name].get('execution_count') or 0),
 'committed_count':int(scheduler[name].get('committed_count') or 0),
 'unchanged_count':int(scheduler[name].get('unchanged_count') or 0),
 'failure_count':int(scheduler[name].get('failure_count') or 0),
 'stale_generation_count':int(scheduler[name].get('stale_generation_count') or 0),
 'refresh_pending':bool(scheduler[name].get('refresh_pending')),
 'followup_requested':bool(scheduler[name].get('followup_requested')),
 'payload_bytes':int(phase[name].get('payload_bytes') or 0),
} for name in sorted(required)}
pathlib.Path(sys.argv[2]).write_text(json.dumps(metrics,sort_keys=True,indent=2)+'\n',encoding='utf-8')
PY
}

warm=0
for _ in $(seq 1 "$WARMUP_ATTEMPTS"); do
  fetch_runtime_evidence runtime
  if validate_runtime "$RUN_DIR/runtime.json" "$RUN_DIR/before.json"; then warm=1; break; fi
  sleep 2
done
[ "$warm" -eq 1 ] || { echo "Phase 3C projections did not become ready during bounded warm-up" >&2; exit 1; }

if command -v pm2 >/dev/null 2>&1; then
  pm2 jlist | python3 -c 'import json,sys; print(json.dumps([{"name":str(x.get("name") or "")[:80],"status":str((x.get("pm2_env") or {}).get("status") or "unknown")[:24],"restarts":int((x.get("pm2_env") or {}).get("restart_time") or 0)} for x in json.load(sys.stdin) if isinstance(x,dict)],sort_keys=True))' > "$RUN_DIR/pm2-sanitized.json"
fi

if [ "$IDLE_SECONDS" -gt 0 ]; then
  wait_for_semantic_idle_baseline
  validate_runtime "$RUN_DIR/runtime.json" "$RUN_DIR/before.json"
  sleep "$IDLE_SECONDS"
  for path in telemetry-thresholds storage-pressure sqlite-health activity-summary; do
    fetch_json "$path-after-idle" "/api/lite/system/$path"
  done
  settled=0
  for _ in $(seq 1 "$QUIESCENCE_ATTEMPTS"); do
    fetch_runtime_evidence runtime-after-idle
    if python3 - "$RUN_DIR/runtime-after-idle.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
s=(p.get('projection_scheduler') or {}).get('domains') or {}
required={'system.telemetry_thresholds','system.storage_pressure','system.sqlite_health','system.activity_summary'}
busy={n:[k for k in ('refresh_pending','active','queued','followup_requested') if bool((s.get(n) or {}).get(k))] for n in required}
busy={k:v for k,v in busy.items() if v}
if busy: print(json.dumps(busy,sort_keys=True),file=sys.stderr); raise SystemExit(1)
PY
    then settled=1; break; fi
    sleep 2
  done
  [ "$settled" -eq 1 ] || { echo "Phase 3C scheduler did not become quiescent" >&2; exit 1; }
  verify_activity_remained_idle "$RUN_DIR/activity-summary-after-idle.json"
  validate_runtime "$RUN_DIR/runtime-after-idle.json" "$RUN_DIR/after.json"
  python3 - "$RUN_DIR/before.json" "$RUN_DIR/after.json" <<'PY'
import json,sys
before=json.load(open(sys.argv[1],encoding='utf-8')); after=json.load(open(sys.argv[2],encoding='utf-8'))
report={}
for name in sorted(before):
    a,b=before[name],after[name]
    delta=b['committed_count']-a['committed_count']
    if b['failure_count'] or b['stale_generation_count'] or b['refresh_pending'] or b['followup_requested']:
        raise SystemExit(f'Phase 3C idle failure: {name}')
    if delta > 2: raise SystemExit(f'Phase 3C commit churn: {name} delta={delta}')
    report[name]={'source_revision_stable':b['source_revision']==a['source_revision'],'commit_delta':delta,'unchanged_delta':b['unchanged_count']-a['unchanged_count']}
if not any(item['unchanged_delta'] > 0 for item in report.values()):
    raise SystemExit('no unchanged-source skip was observed after the idle read cycle')
print(json.dumps({'status':'passed','domains':report,'sanitized':True},sort_keys=True))
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
