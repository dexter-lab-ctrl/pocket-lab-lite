#!/usr/bin/env bash
set -Eeuo pipefail

timeout_seconds="${1:?timeout seconds required}"
shift

if [[ "$#" -lt 1 ]]; then
  echo "Usage: scripts/dev/run-validation-gate.sh <timeout_seconds> <command...>" >&2
  exit 2
fi

cleanup_processes() {
  # Keep cleanup targeted to dev/test processes only.
  pkill -f "vite preview --host 127.0.0.1" >/dev/null 2>&1 || true
  pkill -f "vite --host 127.0.0.1" >/dev/null 2>&1 || true
  pkill -f "playwright.*run-server" >/dev/null 2>&1 || true
  pkill -f "playwright.*test" >/dev/null 2>&1 || true
  pkill -f "chrome.*--remote-debugging" >/dev/null 2>&1 || true
  pkill -f "chrome.*--user-data-dir=.*playwright" >/dev/null 2>&1 || true
}

cleanup_processes

set +e
timeout --foreground --kill-after=15s "${timeout_seconds}s" "$@"
status=$?
set -e

cleanup_processes

if [[ "$status" -eq 124 || "$status" -eq 137 ]]; then
  echo "Validation gate timed out after ${timeout_seconds}s: $*" >&2
fi

exit "$status"
