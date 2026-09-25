#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

# The renewable controller launches this script from Python, so a non-
# interactive WSL shell may not have the operator's checked-in Node toolchain
# on PATH. Load the same nvm installation used by the repository WSL checks
# before invoking the Node-owned Android/CDP qualifier.
if ! command -v node >/dev/null 2>&1; then
  nvm_dir="${NVM_DIR:-${HOME:-}/.nvm}"
  if [[ -s "$nvm_dir/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    source "$nvm_dir/nvm.sh"
    nvm use "${POCKETLAB_NODE_VERSION:-24.16.0}" >/dev/null 2>&1 || true
  fi
fi

bridge_port="${POCKETLAB_ANDROID_CDP_BRIDGE_PORT:-19222}"
local_port="${POCKETLAB_ANDROID_CDP_LOCAL_PORT:-9222}"
check_only=0
baseline_mode=0
owned_socat_pid=""

if [[ "${1:-}" == "--check-only" ]]; then
  check_only=1
elif [[ "${1:-}" == "--baseline" ]]; then
  baseline_mode=1
elif [[ -n "${1:-}" ]]; then
  printf '[ui-performance-android-preflight] ERROR: unknown argument: %s\n' "$1" >&2
  exit 2
fi

fail() {
  printf '[ui-performance-android-preflight] ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command is not available: $1"
}

cleanup() {
  if [[ -n "$owned_socat_pid" ]] && kill -0 "$owned_socat_pid" 2>/dev/null; then
    kill "$owned_socat_pid" 2>/dev/null || true
    wait "$owned_socat_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

need curl
need ip
need node
need socat
need git

windows_host="$(ip route | awk '/^default / {print $3; exit}')"
[[ -n "$windows_host" ]] || fail 'Could not determine the Windows host address from the WSL2 default route.'

bridge_url="http://${windows_host}:${bridge_port}"
local_url="http://127.0.0.1:${local_port}"

if ! curl -fsS --connect-timeout 3 --max-time 5 "$bridge_url/json/version" >/dev/null; then
  fail "Windows CDP bridge is not reachable at ${windows_host}:${bridge_port}. Run prepare-ui-performance-android-cdp.ps1 from elevated Windows PowerShell."
fi

mkdir -p .pocketlab-dev/performance
socat_log=".pocketlab-dev/performance/android-cdp-socat.log"

if ! curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | grep -Eq "127\.0\.0\.1:${local_port}[[:space:]]"; then
    fail "127.0.0.1:${local_port} is already in use, but it is not serving Android Chrome CDP."
  fi

  nohup socat \
    "TCP-LISTEN:${local_port},bind=127.0.0.1,reuseaddr,fork" \
    "TCP:${windows_host}:${bridge_port}" \
    >"$socat_log" 2>&1 &
  owned_socat_pid="$!"

  for _ in $(seq 1 20); do
    if curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

version_json="$(curl -fsS --connect-timeout 3 --max-time 5 "$local_url/json/version")"
node - "$version_json" "$local_port" <<'NODE'
const payload = JSON.parse(process.argv[2]);
const port = Number(process.argv[3]);
if (payload['Android-Package'] !== 'com.android.chrome') {
  throw new Error('local CDP endpoint is not Android Chrome');
}
const ws = new URL(payload.webSocketDebuggerUrl);
if (!['127.0.0.1', 'localhost'].includes(ws.hostname) || Number(ws.port) !== port) {
  throw new Error('CDP websocket is not looped back through WSL local port ' + port + ': ' + payload.webSocketDebuggerUrl);
}
console.log('[ui-performance-android-preflight] Android Chrome ' + (payload.Browser || 'version unknown') + ' via CDP ' + (payload['Protocol-Version'] || 'unknown'));
NODE

export LITE_ANDROID_CDP_URL="$local_url"

node --input-type=module <<'NODE'
import { chromium } from '@playwright/test';

const browser = await chromium.connectOverCDP(process.env.LITE_ANDROID_CDP_URL);
try {
  const contexts = browser.contexts();
  if (!contexts.length) throw new Error('Android Chrome exposed no browser context.');
  const pageCount = contexts.reduce((count, context) => count + context.pages().length, 0);
  console.log('[ui-performance-android-preflight] Playwright CDP attach passed: contexts=' + contexts.length + ' pages=' + pageCount);
} finally {
  // Disconnect this short-lived preflight client before the full qualifier
  // attaches.  browser.close() closes Playwright's CDP transport here; it
  // does not close the remote Android Chrome process or unrelated tabs.
  await browser.close().catch(() => {});
}
process.exit(0);
NODE

if [[ -n "${LITE_BASE_URL:-}" ]]; then
  case "$LITE_BASE_URL" in
    http://*|https://*) ;;
    *) fail 'LITE_BASE_URL must use http:// or https://.' ;;
  esac
  [[ "$LITE_BASE_URL" != *"@"* ]] || fail 'LITE_BASE_URL must not contain embedded credentials.'

  node --input-type=module <<'NODE'
import { chromium } from '@playwright/test';

const browser = await chromium.connectOverCDP(process.env.LITE_ANDROID_CDP_URL);
try {
  const contexts = browser.contexts();
  if (!contexts.length) throw new Error('Android Chrome exposed no browser context.');
  const context = contexts[0];
  const page = await context.newPage();
  try {
    const target = new URL(process.env.LITE_BASE_URL);
    target.searchParams.set('screen', 'home');
    await page.goto(target.href, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.locator('[data-lite-screen-id="home"]').waitFor({ state: 'visible', timeout: 20_000 });
    console.log('[ui-performance-android-preflight] physical Android Pocket Lab Home smoke test passed');
  } finally {
    await page.close().catch(() => {});
  }
} finally {
  // Release the short-lived smoke-test CDP transport before the measured
  // qualifier opens its own connection to the physical renderer.
  await browser.close().catch(() => {});
}
process.exit(0);
NODE
elif (( check_only == 0 )); then
  fail 'Set LITE_BASE_URL to the Pocket Lab Lite origin reachable by Android Chrome.'
else
  printf '[ui-performance-android-preflight] NOTE: LITE_BASE_URL is unset; CDP is ready but Pocket Lab page loading was not checked.\n'
fi

if (( check_only == 1 )); then
  printf '[ui-performance-android-preflight] GO: DEV-PC to physical Android Chrome CDP is ready.\n'
  exit 0
fi

if [[ -z "${LITE_PERF_SOURCE_COMMIT:-}" ]]; then
  LITE_PERF_SOURCE_COMMIT="$(git rev-parse HEAD)"
  export LITE_PERF_SOURCE_COMMIT
fi
[[ "$LITE_PERF_SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail 'LITE_PERF_SOURCE_COMMIT must be an exact 40-character Git commit.'

printf '[ui-performance-android-preflight] source commit: %s\n' "$LITE_PERF_SOURCE_COMMIT"
if (( baseline_mode == 1 )); then
  printf '[ui-performance-android-preflight] running repeated baseline-normalized Android qualification\n'
  exec bash scripts/dev/lite/run-ui-performance-android-baseline.sh
fi

printf '[ui-performance-android-preflight] running physical Android UI performance qualification\n'
rm -rf .pocketlab-dev/performance/ui-performance-android-cdp-*.json
node scripts/dev/lite/qualify-ui-performance-android-cdp.mjs
npm run check:render-budgets
