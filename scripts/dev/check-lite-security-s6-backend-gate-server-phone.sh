#!/usr/bin/env bash
set -uo pipefail
IFS=$'\n\t'

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

STATE_DIR="${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}"
DB_PATH="${POCKETLAB_LITE_DB_PATH:-$STATE_DIR/pocketlab-lite.sqlite3}"
DIRECT_BASE="${POCKETLAB_LITE_DIRECT_BASE_URL:-http://127.0.0.1:8080}"
PROXY_BASE="${POCKETLAB_LITE_PROXY_BASE_URL:-http://127.0.0.1:8443}"
PYTHON_BIN="${POCKETLAB_S6_GATE_PYTHON:-python3}"
SQLITE_BIN="${POCKETLAB_S6_GATE_SQLITE:-sqlite3}"
PM2_BIN="${POCKETLAB_S6_GATE_PM2:-pm2}"
SCAN_TIMEOUT_SECONDS="${POCKETLAB_S6_GATE_SCAN_TIMEOUT_SECONDS:-900}"
SSE_CAPTURE_SECONDS="${POCKETLAB_S6_GATE_SSE_CAPTURE_SECONDS:-35}"
REPLAY_WAIT_SECONDS="${POCKETLAB_S6_GATE_REPLAY_WAIT_SECONDS:-600}"
RUN_API_RESTART=0
RUN_RETENTION=1
KEEP_ARTIFACTS=0

usage() {
  cat <<'USAGE'
Usage: bash scripts/dev/check-lite-security-s6-backend-gate-server-phone.sh [options]

Options:
  --restart-api       Include the controlled pocket-api restart/replay gate.
  --skip-retention    Skip the isolated retention pressure gate.
  --keep-artifacts    Keep the private Termux temporary directory after the run.
  --help              Show this help.

Environment overrides:
  POCKETLAB_LITE_DB_PATH
  POCKETLAB_LITE_DIRECT_BASE_URL
  POCKETLAB_LITE_PROXY_BASE_URL
  POCKETLAB_S6_GATE_SCAN_TIMEOUT_SECONDS
  POCKETLAB_S6_GATE_SSE_CAPTURE_SECONDS
  POCKETLAB_S6_GATE_REPLAY_WAIT_SECONDS
  POCKETLAB_API_TOKEN
USAGE
}

while (($#)); do
  case "$1" in
    --restart-api) RUN_API_RESTART=1 ;;
    --skip-retention) RUN_RETENTION=0 ;;
    --keep-artifacts) KEEP_ARTIFACTS=1 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

TMP_BASE="${TMPDIR:-${PREFIX:-$HOME}/tmp}"
mkdir -p "$TMP_BASE" || {
  printf 'FAIL: cannot create Termux temporary base: %s\n' "$TMP_BASE" >&2
  exit 1
}
GATE_DIR="$(mktemp -d "$TMP_BASE/pocketlab-s6-backend-gate.XXXXXX")" || {
  printf 'FAIL: unable to create a private temporary gate directory under %s\n' "$TMP_BASE" >&2
  exit 1
}
REPORT_JSON="$GATE_DIR/report.json"
STEP_LOG="$GATE_DIR/steps.tsv"
: > "$STEP_LOG"

AUTH_ARGS=()
if [[ -n "${POCKETLAB_API_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${POCKETLAB_API_TOKEN}")
fi

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

record() {
  local status="$1" name="$2" detail="${3:-}"
  printf '%s\t%s\t%s\n' "$status" "$name" "$detail" >> "$STEP_LOG"
  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)); printf 'PASS: %s%s\n' "$name" "${detail:+ — $detail}" ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)); printf 'FAIL: %s%s\n' "$name" "${detail:+ — $detail}" >&2 ;;
    SKIP) SKIP_COUNT=$((SKIP_COUNT + 1)); printf 'SKIP: %s%s\n' "$name" "${detail:+ — $detail}" ;;
  esac
}

cleanup() {
  local exit_code=$?
  "$PYTHON_BIN" - "$STEP_LOG" "$REPORT_JSON" "$PASS_COUNT" "$FAIL_COUNT" "$SKIP_COUNT" "$DB_PATH" "$GATE_DIR" <<'PY' || true
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

steps_path, report_path, passed, failed, skipped, db_path, artifact_dir = sys.argv[1:]
steps = []
for line in Path(steps_path).read_text(encoding="utf-8").splitlines():
    parts = line.split("\t", 2)
    if len(parts) < 3:
        parts += [""] * (3 - len(parts))
    steps.append({"status": parts[0], "name": parts[1], "detail": parts[2]})
payload = {
    "status": "pass" if int(failed) == 0 else "fail",
    "passed": int(passed),
    "failed": int(failed),
    "skipped": int(skipped),
    "database_path": db_path,
    "artifact_dir": artifact_dir,
    "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "steps": steps,
    "sanitized": True,
}
Path(report_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  printf '\nS6 backend gate report: %s\n' "$REPORT_JSON"
  if (( KEEP_ARTIFACTS == 0 && FAIL_COUNT == 0 )); then
    cp "$REPORT_JSON" "$STATE_DIR/s6-backend-gate-last.json" 2>/dev/null || true
    rm -rf "$GATE_DIR"
    printf 'Sanitized final report copied to: %s\n' "$STATE_DIR/s6-backend-gate-last.json"
  else
    printf 'Artifacts retained at: %s\n' "$GATE_DIR"
  fi
  if (( FAIL_COUNT > 0 )); then
    exit 1
  fi
  exit "$exit_code"
}
trap cleanup EXIT

require_command() {
  local command_name="$1"
  if command -v "$command_name" >/dev/null 2>&1; then
    record PASS "command:$command_name"
    return 0
  fi
  record FAIL "command:$command_name" "not found"
  return 1
}

for command_name in curl "$PYTHON_BIN" "$SQLITE_BIN" awk; do
  require_command "$command_name" || exit 1
done

if [[ ! -f "$DB_PATH" ]]; then
  record FAIL "production database exists" "$DB_PATH"
  exit 1
fi
record PASS "production database exists"

PROD_BEFORE_JSON="$GATE_DIR/production-before.json"
"$PYTHON_BIN" - "$DB_PATH" "$PROD_BEFORE_JSON" <<'PY'
import json
import sqlite3
import sys

path, output = sys.argv[1:]
with sqlite3.connect(path) as conn:
    quick = conn.execute("PRAGMA quick_check").fetchone()[0]
    row = conn.execute(
        "SELECT COUNT(*), MIN(event_id), MAX(event_id) FROM security_scan_progress_events"
    ).fetchone()
payload = {"quick_check": quick, "rows": row[0], "oldest": row[1], "latest": row[2]}
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True)
if quick != "ok":
    raise SystemExit(1)
PY
if (($? == 0)); then
  record PASS "production SQLite quick_check"
else
  record FAIL "production SQLite quick_check"
  exit 1
fi

if curl -fsS --max-time 5 "${AUTH_ARGS[@]}" "$DIRECT_BASE/health" >/dev/null; then
  record PASS "direct API health"
else
  record FAIL "direct API health" "$DIRECT_BASE/health"
  exit 1
fi

capture_sse() {
  local name="$1" url="$2" timeout="$3" cursor="${4:-}"
  local headers="$GATE_DIR/$name.headers" body="$GATE_DIR/$name.sse" stderr="$GATE_DIR/$name.stderr"
  local rc
  local args=(--max-time "$timeout" -NsS -D "$headers" -H 'Accept: text/event-stream')
  if [[ -n "$cursor" ]]; then
    args+=(-H "Last-Event-ID: $cursor")
  fi
  curl "${args[@]}" "${AUTH_ARGS[@]}" "$url" > "$body" 2> "$stderr"
  rc=$?
  printf '%s' "$rc" > "$GATE_DIR/$name.rc"
  if [[ "$rc" -ne 0 && "$rc" -ne 28 ]]; then
    record FAIL "$name SSE transport" "curl exit $rc"
    return 1
  fi
  record PASS "$name SSE transport" "curl exit $rc"
  return 0
}

validate_sse_contract() {
  local name="$1" require_heartbeat="$2"
  "$PYTHON_BIN" - "$GATE_DIR/$name.headers" "$GATE_DIR/$name.sse" "$require_heartbeat" <<'PY'
import json
import re
import sys
from pathlib import Path

headers_path, body_path, require_heartbeat_raw = sys.argv[1:]
headers = Path(headers_path).read_text(encoding="utf-8", errors="replace").lower()
text = Path(body_path).read_text(encoding="utf-8", errors="replace")
assert "content-type: text/event-stream" in headers, headers
assert "cache-control: no-cache" in headers, headers
frames = [frame for frame in text.split("\n\n") if frame.strip()]
assert frames, "no SSE frames"
numeric_ids = []
heartbeats = 0
for frame in frames:
    event_type = ""
    event_id = None
    payload = {}
    for line in frame.splitlines():
        if line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip()
        elif line.startswith("id:"):
            value = line.split(":", 1)[1].strip()
            assert re.fullmatch(r"\d+", value), f"non-numeric SSE id: {value}"
            event_id = int(value)
            numeric_ids.append(event_id)
        elif line.startswith("data:"):
            payload = json.loads(line.split(":", 1)[1].strip())
    if event_type == "security.scan.heartbeat":
        heartbeats += 1
        assert event_id is None, "heartbeat has an SSE id"
        assert payload.get("sanitized") is True, payload
assert numeric_ids, "no persisted numeric SSE id"
assert numeric_ids == sorted(set(numeric_ids)), numeric_ids
if require_heartbeat_raw == "1":
    assert heartbeats >= 1, "no heartbeat observed"
print(json.dumps({"numeric_ids": numeric_ids, "heartbeats": heartbeats, "status": "pass"}))
PY
}

capture_sse direct "$DIRECT_BASE/api/lite/security/events" "$SSE_CAPTURE_SECONDS" || true
if validate_sse_contract direct 1 > "$GATE_DIR/direct-contract.json" 2> "$GATE_DIR/direct-contract.stderr"; then
  record PASS "direct numeric IDs, heartbeat without ID, long-lived stream"
else
  record FAIL "direct numeric IDs, heartbeat without ID, long-lived stream" "see direct-contract.stderr"
fi

capture_sse proxy "$PROXY_BASE/api/lite/security/events" "$SSE_CAPTURE_SECONDS" || true
if validate_sse_contract proxy 1 > "$GATE_DIR/proxy-contract.json" 2> "$GATE_DIR/proxy-contract.stderr"; then
  record PASS "proxy numeric IDs, heartbeat without ID, long-lived stream"
else
  record FAIL "proxy numeric IDs, heartbeat without ID, long-lived stream" "see proxy-contract.stderr"
fi

# Start or reuse a Quick Scan and capture its run id.
PROGRESS_JSON="$GATE_DIR/progress.json"
SUBMISSION_JSON="$GATE_DIR/submission.json"
if ! curl -fsS --max-time 10 "${AUTH_ARGS[@]}" "$PROXY_BASE/api/lite/security/progress" -o "$PROGRESS_JSON"; then
  record FAIL "read Security progress"
  exit 1
fi
IFS=$'\t' read -r ACTIVE RUN_ID < <("$PYTHON_BIN" - "$PROGRESS_JSON" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding="utf-8"))
print(("1" if p.get("active_scan") else "0") + "\t" + (p.get("run_id") or ""))
PY
)
if [[ "$ACTIVE" != "1" ]]; then
  if ! curl -fsS --max-time 20 -X POST "${AUTH_ARGS[@]}" -H 'Accept: application/json' -H 'Content-Type: application/json' --data '{"profile":"quick"}' "$PROXY_BASE/api/lite/security/check" -o "$SUBMISSION_JSON"; then
    record FAIL "submit Quick Scan"
    exit 1
  fi
  RUN_ID="$("$PYTHON_BIN" - "$SUBMISSION_JSON" <<'PY'
import json,sys
p=json.load(open(sys.argv[1], encoding="utf-8"))
print(p.get("run_id") or p.get("job_id") or "")
PY
)"
  [[ -n "$RUN_ID" ]] || { record FAIL "submit Quick Scan" "missing run id"; exit 1; }
  record PASS "submit Quick Scan" "$RUN_ID"
fi

ACTIVE_READY=0
for ((attempt=1; attempt<=60; attempt++)); do
  if curl -fsS --max-time 10 "${AUTH_ARGS[@]}" "$PROXY_BASE/api/lite/security/progress" -o "$PROGRESS_JSON"; then
    IFS=$'\t' read -r ACTIVE CURRENT_RUN < <("$PYTHON_BIN" - "$PROGRESS_JSON" <<'PY'
import json,sys
p=json.load(open(sys.argv[1], encoding="utf-8"))
print(("1" if p.get("active_scan") else "0") + "\t" + (p.get("run_id") or ""))
PY
)
    if [[ "$ACTIVE" == "1" && "$CURRENT_RUN" == "$RUN_ID" ]]; then
      ACTIVE_READY=1
      break
    fi
  fi
  sleep 1
done
if (( ACTIVE_READY == 0 )); then
  record FAIL "Quick Scan became active" "$RUN_ID"
  exit 1
fi
record PASS "Quick Scan became active" "$RUN_ID"

capture_sse early "$PROXY_BASE/api/lite/security/events" 8 || true
CURSOR="$(awk '/^id:[[:space:]]*[0-9]+[[:space:]]*$/{value=$0; sub(/^id:[[:space:]]*/,"",value); sub(/[[:space:]]*$/,"",value); print value; exit}' "$GATE_DIR/early.sse")"
if [[ ! "$CURSOR" =~ ^[0-9]+$ ]]; then
  record FAIL "capture numeric replay cursor" "cursor=$CURSOR"
  exit 1
fi
record PASS "capture numeric replay cursor" "$CURSOR"

if "$PYTHON_BIN" - "$DB_PATH" "$CURSOR" "$RUN_ID" <<'PY'
import sqlite3,sys
path,cursor,run_id=sys.argv[1:]
with sqlite3.connect(path) as conn:
    row=conn.execute("SELECT run_id FROM security_scan_progress_events WHERE event_id=?", (int(cursor),)).fetchone()
assert row and row[0] == run_id, (row, run_id)
PY
then
  record PASS "cursor exists in SQLite and matches run"
else
  record FAIL "cursor exists in SQLite and matches run"
  exit 1
fi

LATEST="$CURSOR"
for ((attempt=1; attempt<=REPLAY_WAIT_SECONDS; attempt++)); do
  LATEST="$("$SQLITE_BIN" "$DB_PATH" 'SELECT COALESCE(MAX(event_id),0) FROM security_scan_progress_events;')"
  if [[ "$LATEST" =~ ^[0-9]+$ ]] && (( LATEST > CURSOR )); then
    break
  fi
  sleep 1
done
if [[ ! "$LATEST" =~ ^[0-9]+$ ]] || (( LATEST <= CURSOR )); then
  record FAIL "new persisted event after cursor" "cursor=$CURSOR latest=$LATEST"
  exit 1
fi
record PASS "new persisted event after cursor" "cursor=$CURSOR latest=$LATEST"

if (( RUN_API_RESTART == 1 )); then
  if ! command -v "$PM2_BIN" >/dev/null 2>&1; then
    record FAIL "controlled API restart" "pm2 not found"
    exit 1
  fi
  if "$PM2_BIN" restart pocket-api >/dev/null; then
    record PASS "controlled API restart"
  else
    record FAIL "controlled API restart"
    exit 1
  fi
  READY=0
  for ((attempt=1; attempt<=60; attempt++)); do
    if curl -fsS --max-time 5 "${AUTH_ARGS[@]}" "$DIRECT_BASE/health" >/dev/null; then READY=1; break; fi
    sleep 1
  done
  if (( READY == 1 )); then record PASS "API ready after restart"; else record FAIL "API ready after restart"; exit 1; fi
else
  record SKIP "controlled API restart replay" "use --restart-api"
fi

capture_sse reconnect "$PROXY_BASE/api/lite/security/events" 15 "$CURSOR" || true
if "$PYTHON_BIN" - "$CURSOR" "$RUN_ID" "$GATE_DIR/reconnect.sse" <<'PY'
import json,re,sys
from pathlib import Path
cursor=int(sys.argv[1]); run_id=sys.argv[2]; text=Path(sys.argv[3]).read_text(encoding="utf-8", errors="replace")
items=[]
for frame in [f for f in text.split("\n\n") if f.strip()]:
    event_type=""; event_id=None; payload={}
    for line in frame.splitlines():
        if line.startswith("event:"): event_type=line.split(":",1)[1].strip()
        elif line.startswith("id:"):
            value=line.split(":",1)[1].strip(); assert re.fullmatch(r"\d+", value), value; event_id=int(value)
        elif line.startswith("data:"): payload=json.loads(line.split(":",1)[1].strip())
    if event_type == "security.scan.heartbeat":
        assert event_id is None
    elif event_id is not None:
        items.append((event_id,payload))
ids=[i[0] for i in items]
assert ids, "no replay/live persisted events"
assert all(i > cursor for i in ids), (cursor,ids)
assert ids == sorted(set(ids)), ids
assert any(p.get("run_id") == run_id for _,p in items), items
assert any(p.get("replayed") is True for _,p in items), items
assert not any(p.get("reset") for _,p in items), items
print(json.dumps({"ids":ids,"status":"pass"}))
PY
then
  record PASS "replay strictly after Last-Event-ID, ascending and duplicate-free"
  record PASS "replay-to-live/API-restart durable transition"
else
  record FAIL "replay strictly after Last-Event-ID, ascending and duplicate-free"
fi

# Cursor reset tests use an isolated database copy only.
RESET_DIR="$GATE_DIR/reset-db"
mkdir -p "$RESET_DIR"
RESET_DB="$RESET_DIR/pocketlab-lite-reset.sqlite3"
"$SQLITE_BIN" "$DB_PATH" ".backup '$RESET_DB'"
"$SQLITE_BIN" "$RESET_DB" 'DELETE FROM security_scan_progress_events WHERE event_id < (SELECT MAX(event_id)-24 FROM security_scan_progress_events);'
if PYTHONPATH=pocket-lab-final-structure/runtime POCKETLAB_STATE_DIR="$RESET_DIR" POCKETLAB_LITE_DB_PATH="$RESET_DB" "$PYTHON_BIN" - <<'PY'
from api_fastapi.services import lite_security
from api_fastapi.services.lite_security_store import SecuritySQLiteRepository
repo=SecuritySQLiteRepository()
oldest=repo.get_oldest_progress_event_id(); latest=repo.get_latest_progress_event_id()
assert oldest and latest and oldest > 1
cases=((str(oldest-1),"cursor_too_old"),(str(latest+100),"cursor_ahead"),("malformed-cursor","invalid_cursor"))
for cursor,outcome in cases:
    plan=lite_security.security_event_replay(cursor, repository=repo)
    assert plan.get("outcome") == outcome, plan
    assert plan.get("sanitized") is True, plan
    events=plan.get("events") or []
    assert events, plan
    payload=events[0]
    assert payload.get("snapshot") is True, payload
    assert payload.get("reset") is True, payload
    assert payload.get("reset_reason") == outcome, payload
    assert payload.get("sanitized") is True, payload
PY
then
  record PASS "stale, ahead, and malformed cursor resets"
else
  record FAIL "stale, ahead, and malformed cursor resets"
fi

if (( RUN_RETENTION == 1 )); then
  RET_DIR="$GATE_DIR/retention-db"
  mkdir -p "$RET_DIR"
  RET_DB="$RET_DIR/pocketlab-lite-retention.sqlite3"
  "$SQLITE_BIN" "$DB_PATH" ".backup '$RET_DB'"
  if PYTHONPATH=pocket-lab-final-structure/runtime POCKETLAB_STATE_DIR="$RET_DIR" POCKETLAB_LITE_DB_PATH="$RET_DB" "$PYTHON_BIN" - "$RET_DB" <<'PY'
import json
import sqlite3
import sys
from api_fastapi.services import lite_security
from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

path=sys.argv[1]
repo=SecuritySQLiteRepository()
with sqlite3.connect(path) as conn:
    before=conn.execute("SELECT COUNT(*) FROM security_scan_progress_events").fetchone()[0]
    terminals={row[0] for row in conn.execute("""
        SELECT MAX(pe.event_id)
        FROM security_scan_progress_events pe
        JOIN security_scan_runs r ON r.run_id=pe.run_id
        WHERE r.status IN ('succeeded','degraded','failed','cancelled')
        GROUP BY pe.run_id
    ") if row[0] is not None}
    active=conn.execute("""
        SELECT COUNT(*) FROM security_scan_runs
        WHERE status IN ('queued','accepted','running','working','in_progress')
    """).fetchone()[0]
assert active == 0, f"isolated copy unexpectedly has {active} active runs"
first=repo.prune_progress_events(retention_days=1,max_rows=200,min_per_active_run=1,batch_size=25)
assert first.get("status") == "completed", first
assert first.get("sanitized") is True, first
assert 0 < int(first.get("rows_deleted") or 0) <= 25, first
assert int(first.get("rows_after")) == before-int(first.get("rows_deleted")), first
with sqlite3.connect(path) as conn:
    missing=[event_id for event_id in terminals if conn.execute("SELECT 1 FROM security_scan_progress_events WHERE event_id=?",(event_id,)).fetchone() is None]
assert not missing, missing
import os
os.environ.update({
 "POCKETLAB_SECURITY_PROGRESS_RETENTION_DAYS":"1",
 "POCKETLAB_SECURITY_PROGRESS_MAX_ROWS":"200",
 "POCKETLAB_SECURITY_PROGRESS_MIN_PER_ACTIVE_RUN":"1",
 "POCKETLAB_SECURITY_PROGRESS_PRUNE_BATCH_SIZE":"25",
})
result=lite_security.run_security_progress_retention(repository=repo,max_batches=20)
assert result.get("status") == "completed", result
assert result.get("sanitized") is True, result
assert result.get("row_cap_satisfied") is True, result
assert int(result.get("rows_after")) <= 200, result
with sqlite3.connect(path) as conn:
    missing=[event_id for event_id in terminals if conn.execute("SELECT 1 FROM security_scan_progress_events WHERE event_id=?",(event_id,)).fetchone() is None]
    quick=conn.execute("PRAGMA quick_check").fetchone()[0]
    metadata=conn.execute("SELECT value_json FROM security_store_metadata WHERE metadata_key='progress_retention:last'").fetchone()
assert not missing, missing
assert quick == "ok", quick
assert metadata, "missing retention metadata"
meta=json.loads(metadata[0])
assert meta.get("sanitized") is True, meta
assert meta.get("status") == "completed", meta
assert meta.get("row_cap_satisfied") is True, meta
print(json.dumps({"first_batch":first,"aggregate":result,"metadata":meta},sort_keys=True))
PY
  then
    record PASS "real bounded retention deletion"
    record PASS "row-cap convergence and terminal preservation"
    record PASS "sanitized retention metadata and isolated SQLite integrity"
  else
    record FAIL "isolated retention pressure gate"
  fi
else
  record SKIP "isolated retention pressure gate" "--skip-retention"
fi

PROD_AFTER_JSON="$GATE_DIR/production-after.json"
"$PYTHON_BIN" - "$DB_PATH" "$PROD_AFTER_JSON" <<'PY'
import json,sqlite3,sys
path,output=sys.argv[1:]
with sqlite3.connect(path) as conn:
    quick=conn.execute("PRAGMA quick_check").fetchone()[0]
    row=conn.execute("SELECT COUNT(*),MIN(event_id),MAX(event_id) FROM security_scan_progress_events").fetchone()
json.dump({"quick_check":quick,"rows":row[0],"oldest":row[1],"latest":row[2]},open(output,"w",encoding="utf-8"),sort_keys=True)
PY
if "$PYTHON_BIN" - "$PROD_BEFORE_JSON" "$PROD_AFTER_JSON" <<'PY'
import json,sys
before=json.load(open(sys.argv[1],encoding="utf-8")); after=json.load(open(sys.argv[2],encoding="utf-8"))
assert after["quick_check"] == "ok", after
assert after["oldest"] == before["oldest"], (before,after)
assert after["rows"] >= before["rows"], (before,after)
assert after["latest"] >= before["latest"], (before,after)
PY
then
  record PASS "production database unchanged by pressure tests"
else
  record FAIL "production database unchanged by pressure tests"
fi

if (( FAIL_COUNT == 0 )); then
  record PASS "S6 backend runtime validation gate"
else
  record FAIL "S6 backend runtime validation gate" "$FAIL_COUNT failed checks"
fi
