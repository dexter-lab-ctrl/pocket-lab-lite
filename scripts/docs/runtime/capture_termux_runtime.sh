#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(CDPATH='' cd -- "$SCRIPT_DIR/../../.." && pwd)"
ALIAS_NAME="${POCKETLAB_TERMUX_SSH_ALIAS:-pocketlab-termux}"
CAPTURE_ROOT="${LITE_RUNTIME_CAPTURE_ROOT:-$ROOT/.pocketlab-dev/runtime-captures}"
CAPTURE_TIMEOUT="${LITE_RUNTIME_CAPTURE_TIMEOUT_SECONDS:-120}"
MAX_BYTES="${LITE_RUNTIME_CAPTURE_MAX_BYTES:-524288}"
KEEP_RAW="${LITE_RUNTIME_KEEP_RAW:-0}"
MAX_CAPTURES="${LITE_RUNTIME_MAX_CAPTURES:-8}"
MAX_AGE_DAYS="${LITE_RUNTIME_MAX_AGE_DAYS:-14}"

[[ "$CAPTURE_TIMEOUT" =~ ^[0-9]+$ ]] && ((CAPTURE_TIMEOUT >= 10 && CAPTURE_TIMEOUT <= 300)) || {
  printf '%s\n' 'ERROR invalid capture timeout' >&2; exit 2;
}
[[ "$MAX_BYTES" =~ ^[0-9]+$ ]] && ((MAX_BYTES >= 4096 && MAX_BYTES <= 2097152)) || {
  printf '%s\n' 'ERROR invalid capture size limit' >&2; exit 2;
}

command -v ssh >/dev/null 2>&1 || { printf '%s\n' 'ERROR OpenSSH client is required' >&2; exit 2; }
command -v timeout >/dev/null 2>&1 || { printf '%s\n' 'ERROR GNU timeout is required' >&2; exit 2; }
bash "$SCRIPT_DIR/check_termux_ssh.sh" >/dev/null

umask 077
mkdir -p "$CAPTURE_ROOT"
chmod 700 "$CAPTURE_ROOT"
capture_id="$(date -u +%Y%m%dT%H%M%SZ)-$(python3 - <<'PY'
import secrets
print(secrets.token_hex(4))
PY
)"
capture_dir="$CAPTURE_ROOT/$capture_id"
raw_dir="$capture_dir/raw"
sanitized_dir="$capture_dir/sanitized"
mkdir -p "$raw_dir" "$sanitized_dir"
chmod 700 "$capture_dir" "$raw_dir" "$sanitized_dir"
raw_file="$raw_dir/termux-runtime.json"
sanitized_file="$sanitized_dir/termux-runtime.json"
cleanup_failure() {
  status=$?
  if ((status != 0)); then
    rm -rf "$capture_dir"
  fi
  exit "$status"
}
trap cleanup_failure EXIT

# One bounded SSH connection streams the allowlisted probe. Raw output is never printed.
timeout --signal=TERM --kill-after=5 "${CAPTURE_TIMEOUT}s" \
  ssh -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
      -o StrictHostKeyChecking=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 \
      "$ALIAS_NAME" 'sh -s --' \
  < "$SCRIPT_DIR/termux_runtime_probe.sh" > "$raw_file"
chmod 600 "$raw_file"
actual_bytes="$(wc -c < "$raw_file")"
((actual_bytes > 0 && actual_bytes <= MAX_BYTES)) || {
  printf '%s\n' 'ERROR remote probe output exceeded the bounded capture limit' >&2
  exit 75
}

python3 - "$raw_file" "$SCRIPT_DIR/../../../schemas/runtime/termux-runtime-capture.schema.json" <<'PY'
import json, sys
from pathlib import Path
from jsonschema import Draft202012Validator
payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
schema=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
Draft202012Validator(schema).validate(payload)
PY
python3 "$SCRIPT_DIR/normalize_termux_runtime.py" --input "$raw_file" --output "$sanitized_file" >/dev/null
chmod 600 "$sanitized_file"

if [[ "$KEEP_RAW" != "1" ]]; then
  rm -rf "$raw_dir"
fi

# Retention is local-only, bounded, deterministic, and never follows symlinks.
find "$CAPTURE_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$MAX_AGE_DAYS" -print0 2>/dev/null | xargs -0r rm -rf --
mapfile -t captures < <(find "$CAPTURE_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r)
if ((${#captures[@]} > MAX_CAPTURES)); then
  for old in "${captures[@]:MAX_CAPTURES}"; do
    rm -rf -- "$CAPTURE_ROOT/$old"
  done
fi

trap - EXIT
printf 'PASS sanitized Termux runtime capture created: %s\n' "$capture_id"
