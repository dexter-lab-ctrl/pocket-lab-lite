#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

fail() {
  printf '[ui-performance-android-recovery] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v curl >/dev/null 2>&1 || fail 'curl is required.'
command -v git >/dev/null 2>&1 || fail 'git is required.'
command -v node >/dev/null 2>&1 || fail 'node is required; activate the repository Node toolchain first.'
command -v npm >/dev/null 2>&1 || fail 'npm is required; activate the repository Node toolchain first.'
command -v powershell.exe >/dev/null 2>&1 || fail 'Windows PowerShell is required for the owned ADB reverse mapping.'

baseline_mode=0
for argument in "$@"; do
  case "$argument" in
    --baseline) baseline_mode=1 ;;
    '') ;;
    *) fail "unknown argument: $argument" ;;
  esac
done

source_commit="$(git rev-parse HEAD)"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'the candidate source SHA is not an exact commit.'

cdp_url="${LITE_ANDROID_CDP_URL:-http://127.0.0.1:9222}"
base_url='http://127.0.0.1:18765'

CDP_URL="$cdp_url" node --input-type=module <<'NODE'
const endpoint = new URL(process.env.CDP_URL);
if (!['http:', 'https:'].includes(endpoint.protocol) || endpoint.username || endpoint.password) {
  throw new Error('LITE_ANDROID_CDP_URL must be a credential-free HTTP(S) URL.');
}
const response = await fetch(new URL('/json/version', endpoint));
if (!response.ok) throw new Error('Android Chrome CDP version endpoint was not healthy.');
const payload = await response.json();
if (payload['Android-Package'] !== 'com.android.chrome') throw new Error('CDP endpoint is not Android Chrome.');
if (payload['Protocol-Version'] !== '1.3') throw new Error('Android Chrome CDP protocol version is not 1.3.');
const websocket = new URL(payload.webSocketDebuggerUrl);
if (!['127.0.0.1', 'localhost'].includes(websocket.hostname)) throw new Error('CDP websocket is not localhost-bound.');
console.log(`[ui-performance-android-recovery] Android Chrome ${payload.Browser || 'unknown'} CDP ${payload['Protocol-Version']}`);
NODE

candidate_process=''
cleanup() {
  set +e
  if [[ -n "$candidate_process" ]] && kill -0 "$candidate_process" 2>/dev/null; then
    kill "$candidate_process" 2>/dev/null || true
    wait "$candidate_process" 2>/dev/null || true
  fi
  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
    -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Cleanup >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

printf '[ui-performance-android-recovery] building exact source SHA %s\n' "$source_commit"
POCKETLAB_UI_PERF_CANDIDATE=1 \
VITE_POCKETLAB_UI_PERF_CANDIDATE=1 \
VITE_POCKETLAB_PERF_TEST=1 \
POCKETLAB_BUILD_ID="$source_commit" \
  npm run build

python3 scripts/dev/lite/ui_performance_candidate_server.py --source-commit "$source_commit" &
candidate_process=$!

for _ in {1..240}; do
  if curl -fsS --connect-timeout 1 --max-time 2 \
      "$base_url/__pocketlab_qualification__/candidate.json" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$candidate_process" 2>/dev/null; then
    fail 'candidate server exited before readiness.'
  fi
  sleep 0.25
done
manifest="$(curl -fsS --connect-timeout 1 --max-time 2 "$base_url/__pocketlab_qualification__/candidate.json")" || fail 'candidate manifest was not reachable.'
MANIFEST="$manifest" SOURCE_COMMIT="$source_commit" node --input-type=module <<'NODE'
const manifest = JSON.parse(process.env.MANIFEST);
if (manifest.source_commit !== process.env.SOURCE_COMMIT || manifest.sanitized !== true) {
  throw new Error('candidate manifest source identity mismatch');
}
NODE

powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -OpenCandidate

export LITE_ANDROID_CDP_URL="$cdp_url"
export LITE_BASE_URL="$base_url"
export LITE_PERF_SOURCE_COMMIT="$source_commit"
export LITE_ANDROID_QUALIFICATION_SCOPE=recovery

if (( baseline_mode == 1 )); then
  export LITE_ANDROID_EXPECTED_INTERACTION_REPORTS=4
  export LITE_ANDROID_BASELINE_REPETITIONS="${LITE_ANDROID_BASELINE_REPETITIONS:-3}"
  printf '[ui-performance-android-recovery] running three-or-more paired baseline control runs\n'
  bash scripts/dev/lite/run-ui-performance-android-baseline.sh
else
  printf '[ui-performance-android-recovery] running Recovery-only physical Android interaction matrix\n'
  rm -f .pocketlab-dev/performance/ui-performance-android-recovery-*.json
  node scripts/dev/lite/qualify-ui-performance-android-recovery.mjs
  npm run check:render-budgets
fi
