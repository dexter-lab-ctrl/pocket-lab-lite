#!/usr/bin/env bash
set -u

BASE="${BASE:-http://127.0.0.1:8443}"
APP_ID="${APP_ID:-photoprism}"
POLL_SECONDS="${POLL_SECONDS:-6}"
MAX_POLLS="${MAX_POLLS:-20}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

say() { printf '\n%s\n' "$*"; }
ok() { printf '✅ %s\n' "$*"; }
warn() { printf '⚠️  %s\n' "$*"; }
bad() { printf '❌ %s\n' "$*"; }

fetch_json() {
  local url="$1" out="$2"
  curl --max-time 25 -sS -w '%{http_code}' -o "$out" "$url" || true
}

post_json() {
  local url="$1" body="$2" out="$3"
  curl --max-time 35 -sS -w '%{http_code}' -o "$out" \
    -X POST "$url" -H 'Content-Type: application/json' -d "$body" || true
}

json_eval() {
  local file="$1" expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json, sys
path, expr = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path))
except Exception:
    print("")
    raise SystemExit(0)
cur = data
for part in expr.split('.'):
    if not part:
        continue
    if isinstance(cur, dict):
        cur = cur.get(part)
    elif isinstance(cur, list):
        try:
            cur = cur[int(part)]
        except Exception:
            cur = None
    else:
        cur = None
    if cur is None:
        break
if isinstance(cur, (dict, list)):
    print(json.dumps(cur))
elif cur is None:
    print("")
else:
    print(str(cur))
PY
}

summary_json() {
  local file="$1"
  python3 - "$file" <<'PY'
import json, sys
try:
    d=json.load(open(sys.argv[1]))
except Exception as exc:
    print(f"- could_not_parse_json: {exc}")
    raise SystemExit(0)
for key in ("status","accepted","action_id","operation_id","command_id","command_subject","summary","message","disabled_reason","evidence_ref"):
    if d.get(key) not in (None,"",[],{}):
        print(f"- {key}: {d.get(key)}")
progress=d.get("progress") or {}
if isinstance(progress, dict) and (progress.get("phase") or progress.get("step")):
    print(f"- progress: {progress.get('phase') or 'unknown'} — {progress.get('step') or ''}")
bus=d.get("bus") or {}
if isinstance(bus, dict) and bus:
    print(f"- bus: mode={bus.get('mode')} connected={bus.get('connected')} jetstream={bus.get('jetstream_enabled')}")
PY
}

assess_receipt() {
  local file="$1" expected="$2" label="$3"
  python3 - "$file" "$expected" "$label" <<'PY'
import json, sys
path, expected, label = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    data=json.load(open(path))
except Exception as exc:
    print(f"❌ {label}: receipt JSON could not be parsed: {exc}")
    raise SystemExit(0)
receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else data
action_id = str(receipt.get("action_id") or "")
receipt_id = str(receipt.get("receipt_id") or "")
evidence_ref = str(receipt.get("evidence_ref") or "")
proofs = receipt.get("proofs") if isinstance(receipt.get("proofs"), list) else []
badges = receipt.get("safety_badges") if isinstance(receipt.get("safety_badges"), list) else []
text = json.dumps(receipt, default=str).lower()
leaks = [w for w in ("vault root token","unseal key","password=","api_key","private key","nats://","restic password") if w in text]
print(f"\nEvidence assessment for {label}:")
print(f"- receipt_id: {receipt_id or 'not shown'}")
print(f"- action_id: {action_id or 'not shown'}")
print(f"- action_label: {receipt.get('action_label') or 'not shown'}")
print(f"- status: {receipt.get('status') or 'not shown'}")
print(f"- summary: {receipt.get('summary') or 'not shown'}")
print(f"- evidence_ref: {evidence_ref or 'not shown'}")
print(f"- proof_count: {len(proofs)}")
print(f"- safety_badges_count: {len(badges)}")
if action_id == expected:
    print(f"✅ {label}: receipt appears associated with the expected action.")
else:
    print(f"⚠️  {label}: latest receipt may not be for this action. Check action_id/action_label above.")
print(("✅" if (receipt_id or evidence_ref) else "⚠️ ") + f" {label}: receipt/evidence reference " + ("exists." if (receipt_id or evidence_ref) else "was not visible."))
print(("✅" if (proofs or badges) else "⚠️ ") + f" {label}: proof/safety evidence " + ("is present." if (proofs or badges) else "was not visible."))
print(("✅" if not leaks else "❌") + f" {label}: " + ("no obvious secret words found in receipt JSON." if not leaks else "possible secret-like terms found: "+", ".join(leaks)))
PY
}

wait_for_backup_completion() {
  local expected_backup_id="$1"
  local out="$tmpdir/backup-wait.json"
  say "Waiting for Back up app to finish before Preview restore"
  for i in $(seq 1 "$MAX_POLLS"); do
    local code
    code="$(fetch_json "$BASE/api/lite/apps/$APP_ID/backup" "$out")"
    if [ "$code" != "200" ]; then
      warn "Backup status poll $i/$MAX_POLLS failed with HTTP $code"
      sleep "$POLL_SECONDS"
      continue
    fi
    local running latest verified
    running="$(json_eval "$out" backup_running)"
    latest="$(json_eval "$out" latest_backup.backup_id)"
    verified="$(json_eval "$out" latest_backup.verification_status)"
    printf 'Backup poll %s/%s — running=%s latest=%s verification=%s\n' "$i" "$MAX_POLLS" "${running:-unknown}" "${latest:-none}" "${verified:-unknown}"
    if [ "$running" != "True" ] && [ "$running" != "true" ] && [ -n "$latest" ] && [ "$verified" = "verified" ]; then
      if [ -z "$expected_backup_id" ] || [ "$latest" = "$expected_backup_id" ]; then
        ok "Back up app completed and verified. Preview restore can run safely."
        return 0
      fi
      warn "A verified backup exists, but it is not the backup just requested yet. Waiting for current backup."
    fi
    sleep "$POLL_SECONDS"
  done
  bad "Back up app did not finish verification before the wait limit. Preview restore should remain blocked."
  return 1
}

run_action() {
  local action_id="$1" label="$2"
  local response="$tmpdir/response-$action_id.json" evidence="$tmpdir/evidence-$action_id.json"
  say "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  say "Running: $label"
  local code
  code="$(post_json "$BASE/api/lite/apps/$APP_ID/actions/$action_id" "{\"reason\":\"manual e2e validation for $label\"}" "$response")"
  if [ "$code" != "200" ] && [ "$code" != "202" ]; then
    bad "$label: action request failed. HTTP $code"
    cat "$response"
    return 1
  fi
  ok "$label: FastAPI accepted the action request. HTTP $code"
  summary_json "$response"
  sleep "$POLL_SECONDS"
  code="$(fetch_json "$BASE/api/lite/apps/$APP_ID/evidence" "$evidence")"
  if [ "$code" = "200" ]; then
    ok "$label: evidence endpoint returned a receipt after the action."
    assess_receipt "$evidence" "$action_id" "$label"
  else
    warn "$label: evidence endpoint returned HTTP $code"
  fi
  if [ "$action_id" = "backup_app" ]; then
    requested_backup_id="$(json_eval "$response" backup_id)"
    [ -z "$requested_backup_id" ] && requested_backup_id="$(json_eval "$response" command_id)"
    printf "%s" "$requested_backup_id" > "$tmpdir/latest-requested-backup-id"
  fi
}

check_prereqs() {
  say "Pocket Lab Lite PhotoPrism App Catalog end-to-end validation"
  say "BASE=$BASE"
  say "APP_ID=$APP_ID"
  local f="$tmpdir/status.json"
  [ "$(fetch_json "$BASE/api/lite/status" "$f")" = "200" ] && ok "Lite API is reachable at $BASE." || { bad "Lite API is not reachable."; cat "$f"; exit 1; }
  [ "$(fetch_json "$BASE/api/lite/catalog" "$f")" = "200" ] && ok "App Catalog API is reachable." || { bad "Catalog API is not reachable."; cat "$f"; exit 1; }
  [ "$(fetch_json "$BASE/api/lite/apps/$APP_ID/actions" "$f")" = "200" ] && ok "PhotoPrism action center API is reachable." || { bad "Action API is not reachable."; cat "$f"; exit 1; }
  if [ "$(fetch_json "$BASE/apps/photoprism/api/v1/status" "$f")" = "200" ]; then
    ok "PhotoPrism same-origin route is healthy: $(json_eval "$f" status)."
  else
    warn "PhotoPrism same-origin route health did not return HTTP 200."
  fi
}

check_specific_receipts() {
  local f="$tmpdir/update.json" receipt="$tmpdir/update-receipt.json"
  say "Checking update-readiness-specific receipt endpoint"
  if [ "$(fetch_json "$BASE/api/lite/apps/$APP_ID/update" "$f")" = "200" ]; then
    ok "Update readiness endpoint is reachable."
    summary_json "$f"
    local op
    op="$(json_eval "$f" latest_operation_id)"
    [ -z "$op" ] && op="$(json_eval "$f" operation_id)"
    if [ -n "$op" ] && [ "$(fetch_json "$BASE/api/lite/apps/$APP_ID/update/receipts/$op" "$receipt")" = "200" ]; then
      ok "Update-specific receipt endpoint returned receipt for operation_id=$op."
      assess_receipt "$receipt" update_app "Update readiness specific receipt"
    else
      warn "No update operation/receipt id found yet. The latest App evidence receipt is still checked above."
    fi
  else
    warn "Update readiness endpoint is not reachable."
  fi
}

main() {
  check_prereqs
  run_action check_app "Check app"
  run_action backup_app "Back up app"
  requested_backup_id="$(cat "$tmpdir/latest-requested-backup-id" 2>/dev/null || true)"
  if wait_for_backup_completion "$requested_backup_id"; then
    run_action preview_restore "Preview restore"
  else
    warn "Skipping Preview restore because the current backup has not completed yet."
  fi
  run_action repair_app "Repair"
  run_action update_app "Update readiness"
  check_specific_receipts
  say "Final App Catalog action center snapshot:"
  final="$tmpdir/final-actions.json"
  fetch_json "$BASE/api/lite/apps/$APP_ID/actions" "$final" >/dev/null
  python3 - "$final" <<'PY'
import json, sys
try: data=json.load(open(sys.argv[1]))
except Exception as exc:
    print(f"Could not parse final actions: {exc}"); raise SystemExit(0)
actions=data.get('action_list') or data.get('actions') or []
if isinstance(actions, dict):
    actions=[{'id': k, **(v if isinstance(v, dict) else {'enabled': bool(v)})} for k,v in actions.items()]
for wanted in ['check_app','backup_app','preview_restore','repair_app','update_app']:
    a=next((x for x in actions if x.get('id')==wanted), None)
    if not a:
        print(f"❌ {wanted}: missing"); continue
    print(f"- {a.get('label') or wanted}: status={a.get('status')} enabled={a.get('enabled')} result={(a.get('result') or {}).get('status') or 'none'} receipt_available={(a.get('receipt') or {}).get('available')}")
PY
  say "Done."
}

main "$@"
