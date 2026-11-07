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

check_only=0
baseline_mode=0
access_only=0
qualification_scope="${LITE_ANDROID_QUALIFICATION_SCOPE:-all}"
relay_wsl_process=""
relay_windows_process=""
relay_owned=0

for argument in "$@"; do
  case "$argument" in
    --check-only) check_only=1 ;;
    --baseline) baseline_mode=1 ;;
    --home-only) qualification_scope=home ;;
    --access-only) access_only=1; qualification_scope=access ;;
    '') ;;
    *)
      printf '[ui-performance-android-preflight] ERROR: unknown argument: %s\n' "$argument" >&2
      exit 2
      ;;
  esac
done
case "$qualification_scope" in
  all|home|access) ;;
  *)
    printf '[ui-performance-android-preflight] ERROR: LITE_ANDROID_QUALIFICATION_SCOPE must be all, home or access.\n' >&2
    exit 2
    ;;
esac
export LITE_ANDROID_QUALIFICATION_SCOPE="$qualification_scope"

fail() {
  printf '[ui-performance-android-preflight] ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command is not available: $1"
}

cleanup() {
  set +e
  if (( relay_owned == 1 )); then
    if [[ -n "$relay_windows_process" ]] && kill -0 "$relay_windows_process" 2>/dev/null; then
      kill "$relay_windows_process" 2>/dev/null || true
      wait "$relay_windows_process" 2>/dev/null || true
    fi
    if [[ -n "$relay_wsl_process" ]] && kill -0 "$relay_wsl_process" 2>/dev/null; then
      kill "$relay_wsl_process" 2>/dev/null || true
      wait "$relay_wsl_process" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT INT TERM

need curl
need ip
need node
need git
need python3
need powershell.exe

windows_host="$(ip route | awk '/^default / {print $3; exit}')"
[[ -n "$windows_host" ]] || fail 'Could not determine the Windows host address from the WSL2 default route.'

windows_cdp_probe="$(powershell.exe -NoProfile -NonInteractive -Command '$ErrorActionPreference="Stop"; $p=Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 5; if ($p."Android-Package" -ne "com.android.chrome") { throw "not Android Chrome" }; if ($p."Protocol-Version" -ne "1.3") { throw "unexpected CDP protocol" }; [pscustomobject]@{ Browser=$p.Browser; ProtocolVersion=$p."Protocol-Version"; AndroidPackage=$p."Android-Package"; WebSocketDebuggerUrl=$p.webSocketDebuggerUrl } | ConvertTo-Json -Compress')" \
  || fail 'Windows-local Android Chrome CDP health check failed; inspect the authorized ADB forward without using elevation.'
printf '[ui-performance-android-preflight] Windows CDP health: %s\n' "$windows_cdp_probe"

mkdir -p .pocketlab-dev/performance
local_url='http://127.0.0.1:19222'
if ! curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null 2>&1; then
  wsl_ip="$(ip -4 route get "$windows_host" 2>/dev/null | awk '/src/ {for (i = 1; i <= NF; i += 1) if ($i == "src") {print $(i + 1); exit}}')"
  [[ "$wsl_ip" =~ ^172\.19\.[0-9]+\.[0-9]+$ ]] || fail 'Could not identify the private WSL IPv4 address for the standard-user relay.'

  python3 scripts/dev/lite/wsl-cdp-reverse-relay.py --listen-host "$wsl_ip" \
    >.pocketlab-dev/performance/android-cdp-wsl-relay.log 2>&1 &
  relay_wsl_process="$!"
  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
    -File scripts/dev/lite/windows-cdp-wsl-relay.ps1 -WslAddress "$wsl_ip" \
    >.pocketlab-dev/performance/android-cdp-windows-relay.log 2>&1 &
  relay_windows_process="$!"
  relay_owned=1

  for _ in {1..40}; do
    if curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null 2>&1; then
      break
    fi
    if ! kill -0 "$relay_wsl_process" 2>/dev/null || ! kill -0 "$relay_windows_process" 2>/dev/null; then
      fail 'standard-user WSL CDP relay exited before readiness.'
    fi
    sleep 0.25
  done
  curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null \
    || fail 'standard-user WSL CDP relay did not expose Android Chrome.'
fi

version_json="$(curl -fsS --connect-timeout 3 --max-time 5 "$local_url/json/version")"
cdp_port="${local_url##*:}"
node - "$version_json" "$cdp_port" <<'NODE'
const payload = JSON.parse(process.argv[2]);
const port = Number(process.argv[3]);
if (payload['Android-Package'] !== 'com.android.chrome') {
  throw new Error('local CDP endpoint is not Android Chrome');
}
if (payload['Protocol-Version'] !== '1.3') {
  throw new Error('Android Chrome CDP protocol version is not 1.3');
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

# The smoke probe above opens and closes a short-lived CDP page. On physical
# Android Chrome that can leave the owned candidate renderer backgrounded even
# though the browser remains attached and the DOM is readable. Re-activate
# the exact candidate after the probe and before either qualification mode so
# baseline control samples and interaction evidence both measure the physical
# foreground renderer.
if [[ "${POCKETLAB_ANDROID_WAKE_BEFORE_QUALIFICATION:-0}" == "1" ]]; then
  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
    -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Wake -OpenCandidate
fi

if (( baseline_mode == 1 )); then
  printf '[ui-performance-android-preflight] running repeated baseline-normalized Android qualification\n'
  exec bash scripts/dev/lite/run-ui-performance-android-baseline.sh
fi

if (( access_only == 1 )); then
  printf '[ui-performance-android-preflight] running physical Android Access-only UI performance qualification\n'
  rm -rf .pocketlab-dev/performance/ui-performance-android-access-*.json
  node scripts/dev/lite/qualify-ui-performance-android-access.mjs
  npm run check:render-budgets
  exit $?
fi

printf '[ui-performance-android-preflight] running physical Android %s UI performance qualification\n' "$qualification_scope"
rm -rf .pocketlab-dev/performance/ui-performance-android-cdp-*.json
node scripts/dev/lite/qualify-ui-performance-android-cdp.mjs
npm run check:render-budgets
