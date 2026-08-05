#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
ALIAS_NAME="${POCKETLAB_TERMUX_SSH_ALIAS:-pocketlab-termux}"
OUTPUT_DIR="${VALIDATION_DIR:-$ROOT/.pocketlab-dev/validation}/parity/termux"
OUTPUT="$OUTPUT_DIR/recovery-readonly.json"
mkdir -p "$OUTPUT_DIR"

if ! command -v task >/dev/null 2>&1 || ! (cd "$ROOT" && task lite:runtime:ssh:check >/dev/null 2>&1); then
  printf '{"schema_version":"1.0.0","status":"runtime-unavailable","sanitized":true,"reason":"managed SSH alias unavailable"}\n' > "$OUTPUT"
  printf 'UNAVAILABLE live Termux parity; recorded runtime-unavailable\n' >&2
  exit 2
fi

remote_json="$(ssh -o BatchMode=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 "$ALIAS_NAME" \
  'curl -fsS --max-time 8 http://127.0.0.1:8080/api/lite/recovery/summary' 2>/dev/null || true)"

if [[ -z "$remote_json" ]]; then
  printf '{"schema_version":"1.0.0","status":"partial-failure","sanitized":true,"reason":"read-only recovery summary unavailable"}\n' > "$OUTPUT"
  printf 'PARTIAL live Termux recovery summary unavailable\n' >&2
  exit 3
fi

REMOTE_JSON="$remote_json" OUTPUT="$OUTPUT" python3 - <<'PY'
import json, os
from pathlib import Path
payload = json.loads(os.environ['REMOTE_JSON'])
allowed = {
    'status': payload.get('status'),
    'summary': payload.get('summary'),
    'source_revision': payload.get('source_revision'),
    'projection_status': payload.get('projection_status'),
    'saved_state': payload.get('saved_state'),
}
result = {'schema_version': '1.0.0', 'status': 'observed', 'sanitized': True, 'recovery_summary': allowed}
Path(os.environ['OUTPUT']).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
PY
printf 'PASS live Termux read-only parity observation recorded\n'
