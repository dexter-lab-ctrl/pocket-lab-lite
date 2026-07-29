#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${POCKETLAB_BASE_URL:-http://127.0.0.1:8080}"
RUNTIME_JSON="$(mktemp)"
trap 'rm -f "$RUNTIME_JSON"' EXIT

curl -fsS "$BASE_URL/api/lite/diagnostics/runtime/full" > "$RUNTIME_JSON"

python3 - "$RUNTIME_JSON" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
scheduler = payload.get("projection_scheduler") or {}
mailbox = scheduler.get("mailbox") or {}
required = set(scheduler.get("required_domains") or [])
missing = set(scheduler.get("missing_required_domains") or [])
expected = {
    "apps.catalog",
    "apps.actions:photoprism",
    "apps.lifecycle",
    "fleet.summary",
    "recovery.summary",
    "recovery.details",
    "system.status",
}

checks = {
    "worker_is_authoritative": scheduler.get("authoritative_execution_registry") is True,
    "worker_snapshot_source": scheduler.get("diagnostic_source") == "worker_prepared_sqlite",
    "expected_domains_declared": expected.issubset(required),
    "required_registry_complete": not missing,
    "no_unregistered_mailbox_domains": int(mailbox.get("unregistered") or 0) == 0,
    "no_runnable_mailbox_backlog": int(mailbox.get("runnable_pending") or 0) == 0,
}
print(json.dumps({"checks": checks, "scheduler": scheduler}, indent=2))
failed = [name for name, passed in checks.items() if not passed]
if failed:
    raise SystemExit("Projection registry validation failed: " + ", ".join(failed))
PY

for endpoint in \
  catalog \
  apps/lifecycle \
  apps/photoprism/actions \
  recovery/summary \
  recovery/details \
  status \
  fleet
do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/api/lite/$endpoint")"
  printf '%-32s %s\n' "$endpoint" "$code"
  [[ "$code" == "200" ]] || exit 1
done

echo "Lite projection registry and prepared endpoints: PASS"
