#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

fail() {
  printf '[ui-performance-android-apps] ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command is not available: $1"
}

mode="single"
if [[ "${1:-}" == "--baseline" ]]; then
  mode="baseline"
elif [[ -n "${1:-}" ]]; then
  fail "unknown argument: $1"
fi

need curl
need ip
need node
need npm
need powershell.exe
need python3
need socat
need ss
need git

if [[ ! -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]] && ! command -v node >/dev/null 2>&1; then
  fail 'The checked-in Node toolchain is not available.'
fi
if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  nvm use "${POCKETLAB_NODE_VERSION:-24.16.0}" >/dev/null 2>&1 || true
fi

source_commit="$(git rev-parse HEAD)"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'The candidate source SHA is not an exact commit.'

candidate_process=''
candidate_owned=0
owned_socat_pid=''
output_dir=".pocketlab-dev/performance/android-apps-${source_commit}"

cleanup() {
  set +e
  if [[ -n "$candidate_process" ]] && kill -0 "$candidate_process" 2>/dev/null; then
    kill "$candidate_process" 2>/dev/null || true
    wait "$candidate_process" 2>/dev/null || true
  fi
  if (( candidate_owned == 1 )); then
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
      -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Cleanup >/dev/null 2>&1 || true
  fi
  if [[ -n "$owned_socat_pid" ]] && kill -0 "$owned_socat_pid" 2>/dev/null; then
    kill "$owned_socat_pid" 2>/dev/null || true
    wait "$owned_socat_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Fail closed if a recorded candidate belongs to another active qualification.
# The official cleanup helper is used only after this session has successfully
# acquired the candidate state below.
candidate_state_probe="$(powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command '$path = Join-Path $env:LOCALAPPDATA "PocketLab\ui-performance-android-candidate.json"; if (Test-Path $path -PathType Leaf) { exit 1 } else { exit 0 }' 2>/dev/null; printf '%s' "$?")"
[[ "$candidate_state_probe" == "0" ]] || fail 'An existing Pocket Lab Android candidate state is present; refusing to take ownership of its reverse mapping.'

printf '[ui-performance-android-apps] building exact source SHA %s\n' "$source_commit"
POCKETLAB_UI_PERF_CANDIDATE=1 \
VITE_POCKETLAB_UI_PERF_CANDIDATE=1 \
VITE_POCKETLAB_PERF_TEST=1 \
POCKETLAB_BUILD_ID="$source_commit" \
npm run build

python3 scripts/dev/lite/ui_performance_candidate_server.py --source-commit "$source_commit" &
candidate_process=$!
for _ in {1..240}; do
  if curl -fsS --connect-timeout 1 --max-time 2 \
      http://127.0.0.1:18765/__pocketlab_qualification__/candidate.json >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$candidate_process" 2>/dev/null; then
    fail 'The candidate server exited before readiness.'
  fi
  sleep 0.25
done
curl -fsS --connect-timeout 1 --max-time 2 \
  http://127.0.0.1:18765/__pocketlab_qualification__/candidate.json >/dev/null \
  || fail 'The candidate server did not expose its exact-SHA manifest.'

# The candidate helper refuses to replace an unowned reverse mapping and
# records the exact selected device before emitting READY. From this point the
# state is owned by this bounded qualification and cleanup is authorized.
candidate_owned=1
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -OpenCandidate

bridge_port="${POCKETLAB_ANDROID_CDP_BRIDGE_PORT:-19222}"
local_port="${POCKETLAB_ANDROID_CDP_LOCAL_PORT:-9222}"
windows_host="$(ip route | awk '/^default / {print $3; exit}')"
[[ -n "$windows_host" ]] || fail 'Could not determine the Windows host from the WSL2 default route.'
bridge_url="http://${windows_host}:${bridge_port}"
local_url="http://127.0.0.1:${local_port}"

curl -fsS --connect-timeout 3 --max-time 5 "$bridge_url/json/version" >/dev/null \
  || fail "The owned Windows Android CDP bridge is not reachable at ${windows_host}:${bridge_port}."

mkdir -p "$output_dir"
if ! curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | grep -Eq "127\\.0\\.0\\.1:${local_port}[[:space:]]"; then
    fail "127.0.0.1:${local_port} is occupied by a non-CDP listener; refusing to replace it."
  fi
  nohup socat \
    "TCP-LISTEN:${local_port},bind=127.0.0.1,reuseaddr,fork" \
    "TCP:${windows_host}:${bridge_port}" \
    >"$output_dir/android-cdp-socat.log" 2>&1 &
  owned_socat_pid="$!"
  for _ in {1..20}; do
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
const websocket = new URL(payload.webSocketDebuggerUrl);
if (!['127.0.0.1', 'localhost'].includes(websocket.hostname) || Number(websocket.port) !== port) {
  throw new Error('CDP websocket is not looped back through the WSL local port');
}
console.log('[ui-performance-android-apps] Android Chrome ' + (payload.Browser || 'version unknown') + ' via CDP ' + (payload['Protocol-Version'] || 'unknown'));
NODE

export LITE_ANDROID_CDP_URL="$local_url"
export LITE_BASE_URL='http://127.0.0.1:18765'
export LITE_PERF_SOURCE_COMMIT="$source_commit"
export LITE_ANDROID_APPS_OUTPUT_DIR="$output_dir"
export LITE_ANDROID_CDP_DEVICE_IDENTITY_VERIFIED=1
export LITE_ANDROID_CDP_BRIDGE_IDENTITY_VERIFIED=1
export LITE_ANDROID_CANDIDATE_REVERSE_VERIFIED=1

node --input-type=module <<'NODE'
import { chromium } from '@playwright/test';
const browser = await chromium.connectOverCDP(process.env.LITE_ANDROID_CDP_URL);
try {
  const contexts = browser.contexts();
  if (!contexts.length) throw new Error('Android Chrome exposed no browser context.');
  console.log('[ui-performance-android-apps] CDP attach passed: contexts=' + contexts.length + ' pages=' + contexts.reduce((total, context) => total + context.pages().length, 0));
} finally {
  await browser.close().catch(() => {});
}
NODE

# The preflight CDP client is intentionally disconnected before measurement.
# Re-activate the exact ADB-reverse candidate target through the official
# helper at that boundary so Android Chrome delivers foreground RAF callbacks
# to the measured Apps page.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Wake -OpenCandidate

run_apps_qualifier() {
  local status=0
  set +e
  node scripts/dev/lite/qualify-ui-performance-android-apps.mjs
  status=$?
  set -e
  return "$status"
}

if [[ "$mode" == 'single' ]]; then
  printf '[ui-performance-android-apps] running Apps-only physical qualification for %s\n' "$source_commit"
  qualifier_status=0
  run_apps_qualifier || qualifier_status=$?
else
  repetitions="${LITE_ANDROID_APPS_BASELINE_REPETITIONS:-3}"
  [[ "$repetitions" =~ ^[3-5]$ ]] || fail 'LITE_ANDROID_APPS_BASELINE_REPETITIONS must be 3 through 5.'
  run_id="$(date -u +%Y%m%dT%H%M%SZ)"
  staging_root=".pocketlab-dev/android-performance-baseline/${source_commit}-apps-only-${run_id}"
  mkdir -p "$staging_root"
  qualifier_status=0
  printf '[ui-performance-android-apps] running %s Apps-only baseline repetitions for %s\n' "$repetitions" "$source_commit"
  for run_index in $(seq 1 "$repetitions"); do
    run_name="$(printf 'run-%02d' "$run_index")"
    run_root="$staging_root/$run_name"
    mkdir -p "$run_root/evidence"
    node scripts/dev/lite/qualify-ui-performance-android-baseline.mjs \
      --label "${run_name}-apps-before" \
      --samples 3 \
      --output "$run_root/baseline-before.json"
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
      -File scripts/dev/lite/capture-ui-performance-android-state.ps1 \
      >"$run_root/device-state.json"
    LITE_ANDROID_APPS_OUTPUT_DIR="$run_root/evidence" run_apps_qualifier || run_status=$?
    run_status="${run_status:-0}"
    if (( run_status != 0 )); then qualifier_status=2; fi
    shopt -s nullglob
    evidence_files=("$run_root/evidence"/ui-performance-android-cdp-apps-*.json)
    shopt -u nullglob
    (( ${#evidence_files[@]} > 0 )) || fail "${run_name} produced no Apps interaction reports."
    node scripts/dev/lite/qualify-ui-performance-android-baseline.mjs \
      --label "${run_name}-apps-after" \
      --samples 3 \
      --output "$run_root/baseline-after.json"
    printf '[ui-performance-android-apps] %s captured %s Apps interaction reports; qualifier exit=%s\n' \
      "$run_name" "${#evidence_files[@]}" "$run_status"
    unset run_status
  done
  baseline_output=".pocketlab-dev/performance/android-apps-baseline-${source_commit}-${run_id}"
  node scripts/dev/lite/analyze-ui-performance-android-baseline.mjs \
    --runs-root "$staging_root" \
    --output-dir "$baseline_output" \
    --write-summary "$baseline_output/summary.json"
  printf '[ui-performance-android-apps] baseline attribution reports: %s\n' "$baseline_output"
fi

# The Apps-only qualifier writes scoped evidence and owns its physical gates.
# Do not run the repository-wide evidence checker here: it reads the shared
# .pocketlab-dev/performance tree and would re-evaluate unrelated historical
# Home/Devices samples as part of this Apps qualification.
exit "${qualifier_status:-0}"
