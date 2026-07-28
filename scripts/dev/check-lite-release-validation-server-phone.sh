#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

DIRECT_BASE_URL="${POCKETLAB_RELEASE_VALIDATION_DIRECT_URL:-http://127.0.0.1:8080}"
REPORT_ROOT="${POCKETLAB_RELEASE_VALIDATION_REPORT_ROOT:-$REPO_ROOT/state/release-validation}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="$REPORT_ROOT/release-validation-$TIMESTAMP"
LOG_DIR="$REPORT_DIR/logs"
DATA_DIR="$REPORT_DIR/data"
LONG_GATE_ROOT="$REPORT_DIR/long-gates"
HTML_REPORT="$REPORT_DIR/index.html"
SUMMARY_JSON="$REPORT_DIR/summary.json"
mkdir -p "$LOG_DIR" "$DATA_DIR" "$LONG_GATE_ROOT"
chmod 700 "$REPORT_DIR" "$LOG_DIR" "$DATA_DIR" "$LONG_GATE_ROOT" 2>/dev/null || true

SLEEP_AFTER_9E="${POCKETLAB_RELEASE_VALIDATION_SLEEP_AFTER_9E:-10}"
SLEEP_AFTER_SUBMIT="${POCKETLAB_RELEASE_VALIDATION_SLEEP_AFTER_SUBMIT:-10}"
SLEEP_AFTER_SETTLE="${POCKETLAB_RELEASE_VALIDATION_SLEEP_AFTER_SETTLE:-15}"
SLEEP_BEFORE_180="${POCKETLAB_RELEASE_VALIDATION_SLEEP_BEFORE_180:-30}"
SLEEP_BETWEEN_GATES="${POCKETLAB_RELEASE_VALIDATION_SLEEP_BETWEEN_GATES:-30}"
POLL_INTERVAL="${POCKETLAB_RELEASE_VALIDATION_POLL_INTERVAL_SECONDS:-2}"
POLL_ATTEMPTS="${POCKETLAB_RELEASE_VALIDATION_POLL_ATTEMPTS:-90}"

export RUNTIME="${RUNTIME:-$REPO_ROOT/pocket-lab-final-structure/runtime}"
export PYTHONPATH="$RUNTIME${PYTHONPATH:+:$PYTHONPATH}"
export POCKETLAB_LITE_RELEASE_REPO="${POCKETLAB_LITE_RELEASE_REPO:-dexter-lab-ctrl/pocket-lab-lite}"
export POCKETLAB_AUTO_RELEASE_APPLY="${POCKETLAB_AUTO_RELEASE_APPLY:-false}"
export POCKETLAB_RELEASE_STABLE_INTERVAL_SECONDS="${POCKETLAB_RELEASE_STABLE_INTERVAL_SECONDS:-43200}"

AUTH_ARGS=()
if [[ -n "${POCKETLAB_API_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${POCKETLAB_API_TOKEN}")
fi

STEPS_JSONL="$DATA_DIR/steps.jsonl"
: > "$STEPS_JSONL"

record_step() {
  local id="$1" title="$2" status="$3" started="$4" completed="$5" log="$6" detail="$7"
  python3 - "$STEPS_JSONL" "$id" "$title" "$status" "$started" "$completed" "$log" "$detail" <<'PY'
import json, sys
path, step_id, title, status, started, completed, log_path, detail = sys.argv[1:]
with open(path, 'a', encoding='utf-8') as handle:
    handle.write(json.dumps({
        'id': step_id, 'title': title, 'status': status,
        'started_at': started, 'completed_at': completed,
        'log_path': log_path, 'detail': detail,
    }, sort_keys=True) + '\n')
PY
}

iso_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
announce_sleep() {
  local seconds="$1" reason="$2"
  printf '\nSleeping %ss: %s\n' "$seconds" "$reason"
  sleep "$seconds"
}

run_9e() {
  local started completed status detail log="$LOG_DIR/9e-prepared-status.log" json="$DATA_DIR/9e-release-status.json"
  started="$(iso_now)"
  set +e
  {
    echo '=== 9E — Prepared release status ==='
    curl -fsS "${AUTH_ARGS[@]}" "$DIRECT_BASE_URL/api/lite/release" | tee "$json" | python3 -m json.tool
    python3 - "$json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
checks={
 'product': p.get('product') == 'pocket-lab-lite',
 'configured_repository': p.get('configured_repository') == 'dexter-lab-ctrl/pocket-lab-lite',
 'repository_match': p.get('repository_match') is True,
 'auto_apply_disabled': p.get('auto_apply') is False,
 'stable_interval': 21600 <= int(p.get('stable_interval_seconds') or 0) <= 86400,
 'api_thread_absent': p.get('api_thread_started') is False,
 'execution_owner': p.get('execution_owner') == 'pocket-worker/release-subprocess',
 'prepared_read_only': p.get('prepared_read_only') is True,
 'sanitized': p.get('sanitized') is True,
 'installed_identity_verified': p.get('installed_identity_verified') is True,
}
failed=[name for name, ok in checks.items() if not ok]
print({'checks': checks, 'precheck_status': p.get('status'), 'reason': p.get('reason')})
if failed:
    raise SystemExit('9E contract failures: ' + ', '.join(failed))
PY
  } >"$log" 2>&1
  rc=$?
  set -e
  completed="$(iso_now)"
  if [[ "$rc" -eq 0 ]]; then status=passed; detail='Prepared SQLite release contract is correct; an initial degraded worker-unavailable state is allowed before the manual check.'; else status=failed; detail="9E contract validation failed with exit code $rc."; fi
  record_step 9E 'Prepared release status' "$status" "$started" "$completed" "$log" "$detail"
  cat "$log"
}

run_9f_submit() {
  local started completed status detail log="$LOG_DIR/9f-submit.log" body="$DATA_DIR/9f-submit.json" headers="$DATA_DIR/9f-submit.headers"
  started="$(iso_now)"
  set +e
  {
    echo '=== 9F — Submit manual release check ==='
    code="$(curl -sS -D "$headers" -o "$body" -w '%{http_code}' "${AUTH_ARGS[@]}" -X POST "$DIRECT_BASE_URL/api/lite/release/check")"
    cat "$headers"
    python3 -m json.tool "$body"
    python3 - "$code" "$body" <<'PY'
import json, sys
code=int(sys.argv[1]); payload=json.load(open(sys.argv[2], encoding='utf-8'))
if code != 202:
    raise SystemExit(f'expected HTTP 202, received {code}')
command_id=str(payload.get('command_id') or '')
accepted=payload.get('accepted')
if not command_id and accepted is not True:
    raise SystemExit('release check response did not contain command admission evidence')
print({'http_status': code, 'command_id': command_id, 'accepted': accepted})
PY
  } >"$log" 2>&1
  rc=$?
  set -e
  completed="$(iso_now)"
  if [[ "$rc" -eq 0 ]]; then status=passed; detail='FastAPI accepted the worker-owned manual release check.'; else status=failed; detail="Manual check admission failed with exit code $rc."; fi
  record_step 9F-submit 'Manual release check admission' "$status" "$started" "$completed" "$log" "$detail"
  cat "$log"
}

run_9f_settle() {
  local started completed status detail log="$LOG_DIR/9f-settle.log" json="$DATA_DIR/9f-final-status.json"
  started="$(iso_now)"
  set +e
  {
    echo '=== 9F — Poll and validate manual release check ==='
    terminal=0
    for attempt in $(seq 1 "$POLL_ATTEMPTS"); do
      curl -fsS "${AUTH_ARGS[@]}" "$DIRECT_BASE_URL/api/lite/release" > "$json"
      python3 - "$attempt" "$json" <<'PY'
import json, sys
p=json.load(open(sys.argv[2], encoding='utf-8'))
print({'attempt': int(sys.argv[1]), 'status': p.get('status'), 'phase': p.get('phase'), 'active_generation': p.get('active_generation'), 'current_tag': p.get('current_tag'), 'latest_tag': p.get('latest_tag'), 'comparison': p.get('comparison'), 'manifest_verified': p.get('manifest_verified'), 'failure': p.get('last_failure_code')})
PY
      active="$(python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1])).get("active_generation") or 0))' "$json")"
      checked="$(python3 -c 'import json,sys; print(1 if json.load(open(sys.argv[1])).get("last_checked_at") else 0)' "$json")"
      if [[ "$active" == 0 && "$checked" == 1 ]]; then terminal=1; break; fi
      sleep "$POLL_INTERVAL"
    done
    [[ "$terminal" == 1 ]] || { echo 'manual release check did not settle before timeout' >&2; exit 2; }
    echo '--- final status ---'
    python3 -m json.tool "$json"
    python3 - "$json" <<'PY'
import datetime as dt, json, re, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
latest=str(p.get('latest_tag') or '')
m=re.fullmatch(r'lite-(\d{4})\.(\d{2})\.(\d{2})\.([1-9]\d*)', latest)
if not m: raise SystemExit(f'invalid latest Lite tag: {latest!r}')
dt.date(int(m[1]), int(m[2]), int(m[3]))
checks={
 'status_not_degraded': p.get('status') not in {'degraded','error','failed'},
 'repository_match': p.get('repository_match') is True,
 'manifest_verified': p.get('manifest_verified') is True,
 'auto_apply_disabled': p.get('auto_apply') is False,
 'no_active_generation': int(p.get('active_generation') or 0) == 0,
 'no_failure_code': not p.get('last_failure_code'),
 'latest_tag_strict': bool(m),
 'last_checked_at': bool(p.get('last_checked_at')),
}
current=str(p.get('current_tag') or p.get('installed_release_tag') or '')
if current:
    checks['current_matches_latest'] = current == latest
failed=[k for k,v in checks.items() if not v]
print({'checks': checks, 'current_tag': current, 'latest_tag': latest})
if failed: raise SystemExit('9F terminal validation failures: ' + ', '.join(failed))
PY
  } >"$log" 2>&1
  rc=$?
  set -e
  completed="$(iso_now)"
  if [[ "$rc" -eq 0 ]]; then status=passed; detail='Worker-owned release check settled with strict Lite tag, verified manifest, matching repository, and no failure.'; else status=failed; detail="Manual check terminal validation failed with exit code $rc."; fi
  record_step 9F-settle 'Manual release check completion' "$status" "$started" "$completed" "$log" "$detail"
  cat "$log"
}

run_gate() {
  local duration="$1" step_id="$2" title="$3" started completed status detail
  local log="$LOG_DIR/${step_id}.log" run_id="pocketlab-long-gates-release-${duration}-${TIMESTAMP,,}"
  started="$(iso_now)"
  set +e
  bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
    --gate adaptive-runtime \
    --duration-seconds "$duration" \
    --sample-interval-seconds 15 \
    --report-dir "$LONG_GATE_ROOT" \
    --run-id "$run_id" >"$log" 2>&1
  rc=$?
  set -e
  local result="$LONG_GATE_ROOT/$run_id/gates/adaptive-runtime/result.json"
  completed="$(iso_now)"
  if [[ "$rc" -eq 0 && -f "$result" ]] && python3 - "$result" <<'PY'
import json, sys
raise SystemExit(0 if json.load(open(sys.argv[1], encoding='utf-8')).get('status') == 'passed' else 1)
PY
  then status=passed; detail="Adaptive-runtime ${duration}-second gate passed with its generated evidence."; else status=failed; detail="Adaptive-runtime ${duration}-second gate failed or did not produce a passing result (exit $rc)."; fi
  record_step "$step_id" "$title" "$status" "$started" "$completed" "$log" "$detail"
  cat "$log"
}

generate_report() {
  python3 - "$STEPS_JSONL" "$SUMMARY_JSON" "$HTML_REPORT" "$REPORT_DIR" <<'PY'
import datetime as dt, html, json, os, pathlib, sys
steps_path, summary_path, html_path, report_dir = map(pathlib.Path, sys.argv[1:])
steps=[]
for line in steps_path.read_text(encoding='utf-8').splitlines():
    if line.strip(): steps.append(json.loads(line))
overall='passed' if steps and all(s['status']=='passed' for s in steps) else 'failed'
summary={'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z'),'overall_status':overall,'steps':steps,'report_directory':str(report_dir)}
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding='utf-8')
rows=[]
sections=[]
for s in steps:
    cls='pass' if s['status']=='passed' else 'fail'
    log_path=pathlib.Path(s['log_path'])
    try: raw=log_path.read_text(encoding='utf-8', errors='replace')
    except OSError as exc: raw=f'Unable to read log: {exc}'
    rows.append(f"<tr><td>{html.escape(s['id'])}</td><td>{html.escape(s['title'])}</td><td><span class='badge {cls}'>{html.escape(s['status'].upper())}</span></td><td>{html.escape(s['started_at'])}</td><td>{html.escape(s['completed_at'])}</td></tr>")
    sections.append(f"<section class='card'><div class='card-head'><div><div class='eyebrow'>{html.escape(s['id'])}</div><h2>{html.escape(s['title'])}</h2><p>{html.escape(s['detail'])}</p></div><span class='badge {cls}'>{html.escape(s['status'].upper())}</span></div><details open><summary>Complete captured output</summary><pre>{html.escape(raw)}</pre></details></section>")
status_label=overall.upper(); status_cls='pass' if overall=='passed' else 'fail'
doc=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pocket Lab Lite Release Validation</title><style>
:root{{--bg:#07111f;--panel:#0d1b2d;--panel2:#10243b;--text:#e8f1fb;--muted:#9fb0c3;--line:#28405a;--good:#43d17b;--bad:#ff6b6b;--accent:#77b7ff}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top right,#183b61 0,#07111f 42%);color:var(--text);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}main{{max-width:1180px;margin:auto;padding:32px 18px 72px}}.hero{{background:linear-gradient(135deg,rgba(119,183,255,.18),rgba(67,209,123,.08));border:1px solid var(--line);border-radius:24px;padding:28px;box-shadow:0 24px 70px rgba(0,0,0,.28)}}h1{{font-size:clamp(30px,5vw,54px);margin:4px 0 10px}}h2{{margin:2px 0 6px}}p{{color:var(--muted)}}.eyebrow{{letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-size:12px;font-weight:750}}.badge{{display:inline-flex;border-radius:999px;padding:7px 12px;font-weight:800;font-size:12px;letter-spacing:.08em}}.badge.pass{{color:#071b10;background:var(--good)}}.badge.fail{{color:#250707;background:var(--bad)}}.summary{{overflow:auto;margin:22px 0}}table{{width:100%;border-collapse:collapse;background:rgba(13,27,45,.86);border:1px solid var(--line);border-radius:16px;overflow:hidden}}th,td{{padding:13px 14px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}th{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}}.card{{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:20px;padding:20px;margin:18px 0;box-shadow:0 16px 45px rgba(0,0,0,.2)}}.card-head{{display:flex;gap:18px;justify-content:space-between;align-items:flex-start}}details{{margin-top:16px}}summary{{cursor:pointer;color:var(--accent);font-weight:700}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#050b13;border:1px solid #20354a;border-radius:14px;padding:16px;max-height:620px;overflow:auto;color:#d8e6f5;font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}}footer{{color:var(--muted);text-align:center;margin-top:30px}}@media(max-width:700px){{.card-head{{flex-direction:column}}th,td{{white-space:normal}}}}
</style></head><body><main><header class="hero"><div class="eyebrow">Pocket Lab Lite · Server Phone</div><h1>Native Release Validation</h1><span class="badge {status_cls}">{status_label}</span><p>Prepared status, manual worker-owned release check, and adaptive-runtime qualification with complete captured evidence.</p><p>Generated {html.escape(summary['generated_at'])}</p></header><div class="summary"><table><thead><tr><th>Step</th><th>Validation</th><th>Result</th><th>Started</th><th>Completed</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>{''.join(sections)}<footer>Report directory: {html.escape(str(report_dir))}</footer></main></body></html>'''
html_path.write_text(doc, encoding='utf-8')
PY
}

main() {
  echo "Pocket Lab Lite release validation report: $REPORT_DIR"
  run_9e || true
  announce_sleep "$SLEEP_AFTER_9E" 'allowing prepared state and worker heartbeats to settle after 9E'
  run_9f_submit || true
  announce_sleep "$SLEEP_AFTER_SUBMIT" 'allowing NATS delivery and release subprocess admission after 9F submission'
  run_9f_settle || true
  announce_sleep "$SLEEP_AFTER_SETTLE" 'allowing release projection, SQLite and process diagnostics to quiesce'
  announce_sleep "$SLEEP_BEFORE_180" 'cooldown before the 180-second adaptive-runtime gate'
  run_gate 180 adaptive-180 '180-second adaptive-runtime gate' || true
  announce_sleep "$SLEEP_BETWEEN_GATES" 'cooldown between adaptive-runtime gates'
  run_gate 900 adaptive-900 '900-second adaptive-runtime gate' || true
  generate_report
  echo
  echo "HTML report: $HTML_REPORT"
  echo "JSON summary: $SUMMARY_JSON"
  python3 - "$SUMMARY_JSON" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
print({'overall_status':p['overall_status'],'steps':{s['id']:s['status'] for s in p['steps']}})
raise SystemExit(0 if p['overall_status']=='passed' else 1)
PY
}
main "$@"
