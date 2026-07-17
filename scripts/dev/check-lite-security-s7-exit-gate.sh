#!/usr/bin/env bash
set -uo pipefail
IFS=$'\n\t'
umask 077

REPO_ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

STATE_DIR="${POCKETLAB_STATE_DIR:-$HOME/pocket-lab-lite/state}"
DB_PATH="${POCKETLAB_LITE_DB_PATH:-$STATE_DIR/pocketlab-lite.sqlite3}"
BASE_URL="${POCKETLAB_S7_GATE_BASE_URL:-http://127.0.0.1:8443}"
PYTHON_BIN="${POCKETLAB_S7_GATE_PYTHON:-python3}"
SKIP_PARITY="${POCKETLAB_S7_GATE_SKIP_PARITY:-0}"
TMP_BASE="${TMPDIR:-${PREFIX:-$HOME}/tmp}"
REPORT_PATH="${POCKETLAB_S7_GATE_REPORT:-$STATE_DIR/security-s7-exit-gate-last.json}"

AUTH_ARGS=()
if [[ -n "${POCKETLAB_API_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${POCKETLAB_API_TOKEN}")
fi

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
mkdir -p "$TMP_BASE" "$STATE_DIR" || exit 1
GATE_DIR="$(mktemp -d "$TMP_BASE/pocketlab-s7-exit-gate.XXXXXX")" || exit 1
STEP_LOG="$GATE_DIR/steps.tsv"
: > "$STEP_LOG"

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
  "$PYTHON_BIN" - "$STEP_LOG" "$REPORT_PATH" "$PASS_COUNT" "$FAIL_COUNT" "$SKIP_COUNT" <<'PY' || true
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

steps_path, report_path, passed, failed, skipped = sys.argv[1:]
steps = []
for line in Path(steps_path).read_text(encoding="utf-8").splitlines():
    status, name, detail = (line.split("\t", 2) + ["", ""])[:3]
    steps.append({"status": status, "name": name, "detail": detail})
payload = {
    "view_model": "security-s7-exit-gate-v1",
    "status": "pass" if int(failed) == 0 else "fail",
    "passed": int(passed),
    "failed": int(failed),
    "skipped": int(skipped),
    "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "steps": steps,
    "sanitized": True,
}
path = Path(report_path)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  rm -rf "$GATE_DIR"
  printf '\nS7 exit-gate report: %s\n' "$REPORT_PATH"
  if (( FAIL_COUNT > 0 )); then exit 1; fi
  exit "$exit_code"
}
trap cleanup EXIT

for command_name in curl "$PYTHON_BIN"; do
  if command -v "$command_name" >/dev/null 2>&1; then
    record PASS "command:$command_name"
  else
    record FAIL "command:$command_name" "not found"
    exit 1
  fi
done

if [[ ! -f "$DB_PATH" ]]; then
  record FAIL "Security SQLite database exists" "$DB_PATH"
  exit 1
fi

if "$PYTHON_BIN" - "$DB_PATH" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as conn:
    result = conn.execute("PRAGMA quick_check").fetchone()[0]
print(result)
raise SystemExit(0 if result == "ok" else 1)
PY
then
  record PASS "SQLite quick_check" "ok"
else
  record FAIL "SQLite quick_check"
fi

if curl -fsS --max-time 8 "${AUTH_ARGS[@]}" "$BASE_URL/health" >/dev/null; then
  record PASS "same-origin API health" "$BASE_URL"
else
  record FAIL "same-origin API health" "$BASE_URL"
fi

fetch_json() {
  local name="$1" path="$2"
  curl -fsS --max-time 15 "${AUTH_ARGS[@]}" "$BASE_URL$path" -o "$GATE_DIR/$name.json"
}

fetch_json quick '/api/lite/security/profiles/quick' || record FAIL "Quick profile endpoint"
fetch_json full '/api/lite/security/profiles/full' || record FAIL "Full profile endpoint"
fetch_json app '/api/lite/security/profiles/app?app_id=photoprism' || record FAIL "App profile endpoint"
fetch_json history '/api/lite/security/history?limit=20' || record FAIL "History first page"

if "$PYTHON_BIN" - "$GATE_DIR/quick.json" "$GATE_DIR/full.json" "$GATE_DIR/app.json" "$GATE_DIR/history.json" "$GATE_DIR/cursor.txt" <<'PY'
import json
import sys
from pathlib import Path

quick_path, full_path, app_path, history_path, cursor_path = sys.argv[1:]
profiles = [json.load(open(path, encoding="utf-8")) for path in (quick_path, full_path, app_path)]
expected = [("quick", ""), ("full", ""), ("app", "photoprism")]
for payload, (profile, app_id) in zip(profiles, expected):
    assert payload.get("view_model") == "security-profile-snapshot-v2", payload
    assert payload.get("profile") == profile, payload
    assert (payload.get("app_id") or "") == app_id, payload
    assert payload.get("sanitized") is True, payload
    assert isinstance(payload.get("finding_counts"), dict), payload
    assert len(payload.get("tool_status") or []) <= 12, payload
    raw = json.dumps(payload).lower()
    for forbidden in ("password", "authorization", "nats://", "private_key", "command_payload", "raw_evidence"):
        assert forbidden not in raw, forbidden
history = json.load(open(history_path, encoding="utf-8"))
assert history.get("view_model") == "security-history-cursor-v2", history
rows = history.get("history") or []
assert len(rows) <= 20, len(rows)
assert len({row.get("run_id") for row in rows}) == len(rows), rows
for row in rows:
    for forbidden in ("findings", "evidence_refs", "tool_results"):
        assert forbidden not in row, (forbidden, row)
Path(cursor_path).write_text(str(history.get("next_cursor") or ""), encoding="utf-8")
PY
then
  record PASS "profile snapshots are independent, bounded, sanitized"
  record PASS "history first page is compact and bounded" "20 rows maximum"
else
  record FAIL "S7 profile/history payload contract"
fi

CURSOR="$(cat "$GATE_DIR/cursor.txt" 2>/dev/null || true)"
if [[ -n "$CURSOR" ]]; then
  ENCODED_CURSOR="$($PYTHON_BIN - "$CURSOR" <<'PY'
import sys, urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=""))
PY
)"
  if fetch_json older "/api/lite/security/history?limit=20&cursor=$ENCODED_CURSOR" && "$PYTHON_BIN" - "$GATE_DIR/history.json" "$GATE_DIR/older.json" <<'PY'
import json, sys
first = json.load(open(sys.argv[1], encoding="utf-8")).get("history") or []
older = json.load(open(sys.argv[2], encoding="utf-8")).get("history") or []
first_ids = {row.get("run_id") for row in first}
older_ids = {row.get("run_id") for row in older}
assert first_ids.isdisjoint(older_ids), (first_ids & older_ids)
assert len(older) <= 20
PY
  then
    record PASS "cursor loads older rows without duplicates"
  else
    record FAIL "cursor loads older rows without duplicates"
  fi
else
  record SKIP "cursor next page" "fewer than 21 history rows"
fi

if [[ "$SKIP_PARITY" == "1" ]]; then
  record SKIP "JSON/SQLite parity" "POCKETLAB_S7_GATE_SKIP_PARITY=1"
elif [[ -f scripts/lite/security-db-compare.py ]]; then
  if "$PYTHON_BIN" scripts/lite/security-db-compare.py --no-record > "$GATE_DIR/parity.json" 2> "$GATE_DIR/parity.stderr" && "$PYTHON_BIN" - "$GATE_DIR/parity.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload.get("ok") is True, payload
assert payload.get("matched") is True, payload
PY
  then
    record PASS "JSON/SQLite parity" "matched=true"
  else
    record FAIL "JSON/SQLite parity" "see compare output"
  fi
else
  record SKIP "JSON/SQLite parity" "compare script missing"
fi

if command -v pm2 >/dev/null 2>&1; then
  if pm2 jlist | "$PYTHON_BIN" -c 'import json,sys; rows=json.load(sys.stdin); required={"pocket-api","pocket-worker","pocket-nats","caddy-proxy"}; online={str(x.get("name")) for x in rows if str((x.get("pm2_env") or {}).get("status"))=="online"}; missing=sorted(required-online); print(",".join(missing)); raise SystemExit(bool(missing))'; then
    record PASS "PM2 core services online"
  else
    record FAIL "PM2 core services online"
  fi
else
  record SKIP "PM2 core services online" "pm2 not installed in this environment"
fi

if (( FAIL_COUNT == 0 )); then
  record PASS "S7 runtime exit gate"
else
  record FAIL "S7 runtime exit gate" "$FAIL_COUNT failed checks"
fi
