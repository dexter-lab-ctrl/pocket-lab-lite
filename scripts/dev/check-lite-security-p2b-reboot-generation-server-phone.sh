#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$HOME/pocket-lab-lite}"
STATE_DIR="${POCKETLAB_STATE_DIR:-$ROOT_DIR/state}"
DB_PATH="${POCKETLAB_LITE_DB_PATH:-$STATE_DIR/pocketlab-lite.sqlite3}"
PROXY_BASE="${PROXY_BASE:-http://127.0.0.1:8443}"
RUN_DIR="$STATE_DIR/.pocketlab-dev/reboot-generation/$(date -u +%Y%m%dT%H%M%SZ)"
MARKER="$STATE_DIR/.pocketlab-runtime/security-progress-generation.json"

mkdir -p "$RUN_DIR"
test -w "$RUN_DIR"
cd "$ROOT_DIR"

curl -fsS "$PROXY_BASE/api/lite/security/progress" > "$RUN_DIR/progress-before.json"
python3 - "$RUN_DIR/progress-before.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
if payload.get("active_scan"):
    raise SystemExit("active Security scan blocks reboot-generation gate")
PY

python3 scripts/lite/security-db-check.py --initialize > "$RUN_DIR/database-check.json"
python3 - "$RUN_DIR/database-check.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
if payload.get("quick_check") != "ok" or not payload.get("schema_current"):
    raise SystemExit("SQLite health gate failed")
PY

python3 - "$DB_PATH" "$MARKER" "$RUN_DIR/marker-before.json" <<'PY'
import json, sqlite3, sys, uuid
from pathlib import Path

db_path, marker_path, backup_path = map(Path, sys.argv[1:])
if marker_path.is_file():
    backup_path.write_bytes(marker_path.read_bytes())
with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    latest = conn.execute("""
        SELECT run_id FROM security_scan_runs
        ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms, requested_at_epoch_ms) DESC,
                 run_id DESC LIMIT 1
    """).fetchone()
    revision = conn.execute(
        "SELECT revision FROM domain_revisions WHERE domain='security'"
    ).fetchone()
    metadata = conn.execute(
        "SELECT value_json FROM security_store_metadata WHERE metadata_key='database_instance'"
    ).fetchone()
instance_id = ""
if metadata:
    try:
        instance_id = str(json.loads(metadata[0]).get("instance_id") or "")
    except (TypeError, json.JSONDecodeError):
        pass
payload = {
    "schema_version": 2,
    "generation": uuid.uuid4().hex,
    "reason": "termux_reboot_gate_stale_marker",
    "database_instance_id": instance_id,
    "run_id": "security-stale-reboot-gate",
    "sqlite_revision": max(0, int(revision[0] if revision else 0) - 1),
    "published_at": "1970-01-01T00:00:00Z",
    "sanitized": True,
}
marker_path.parent.mkdir(parents=True, exist_ok=True)
temporary = marker_path.with_name(marker_path.name + ".gate.tmp")
temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
temporary.replace(marker_path)
PY

pm2 restart pocket-api --update-env > "$RUN_DIR/pm2-restart.txt"

ready=0
for _attempt in $(seq 1 30); do
    if curl -fsS "$PROXY_BASE/api/lite/security/progress" > "$RUN_DIR/progress-after.json"; then
        ready=1
        break
    fi
    sleep 1
done
test "$ready" -eq 1

python3 scripts/lite/security-db-compare.py --no-record > "$RUN_DIR/parity-after.json"
python3 - "$RUN_DIR/progress-after.json" "$RUN_DIR/parity-after.json" "$MARKER" <<'PY'
import json, sys
from pathlib import Path
progress = json.load(open(sys.argv[1], encoding="utf-8"))
parity = json.load(open(sys.argv[2], encoding="utf-8"))
marker = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
assert progress.get("storage_backend") == "sqlite"
assert marker.get("run_id", "") == str(progress.get("run_id") or "")
assert int(marker.get("sqlite_revision") or 0) == int(progress.get("sqlite_revision") or 0)
assert marker.get("reason") == "cold_start_sqlite_rebuild"
assert parity.get("matched") is True
print("P2B reboot-generation gate passed")
PY

printf 'Evidence: %s\n' "$RUN_DIR"
printf 'Operational note: run pm2 save only after all services are healthy.\n'
