#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

fail() {
  printf '[ui-performance-live] ERROR: %s\n' "$*" >&2
  exit 1
}

[[ "${LITE_E2E_LIVE:-}" == "1" ]] || fail "Set LITE_E2E_LIVE=1 to acknowledge live read-only qualification."
[[ -n "${LITE_BASE_URL:-}" ]] || fail "Set LITE_BASE_URL to the prepared Pocket Lab Lite origin."

case "$LITE_BASE_URL" in
  http://*|https://*) ;;
  *) fail "LITE_BASE_URL must use http:// or https://." ;;
esac

[[ "$LITE_BASE_URL" != *"@"* ]] || fail "LITE_BASE_URL must not contain embedded credentials."

status_url="${LITE_BASE_URL%/}/api/lite/status"
curl -fsS --max-time 10 -H 'Accept: application/json' "$status_url" >/dev/null   || fail "Pocket Lab Lite status endpoint is not reachable."

printf '[ui-performance-live] status preflight passed; running read-only browser qualification\n'
npm run test:perf:live
