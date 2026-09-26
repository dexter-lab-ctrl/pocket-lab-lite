#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

fail() {
  printf '[ui-performance-android-candidate] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v powershell.exe >/dev/null 2>&1 || fail 'Windows PowerShell is required for the owned ADB reverse mapping.'
command -v npm >/dev/null 2>&1 || fail 'npm is required; activate the checked-in Node toolchain first.'
command -v node >/dev/null 2>&1 || fail 'node is required; activate the checked-in Node toolchain first.'

baseline_mode=0
if [[ "${1:-}" == "--baseline" ]]; then
  baseline_mode=1
elif [[ -n "${1:-}" ]]; then
  fail "unknown argument: $1"
fi

source_commit="$(git rev-parse HEAD)"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'the candidate source SHA is not an exact commit.'

candidate_process=''
keepalive_process=''
cleanup() {
  set +e
  if [[ -n "$keepalive_process" ]] && kill -0 "$keepalive_process" 2>/dev/null; then
    kill "$keepalive_process" 2>/dev/null || true
    wait "$keepalive_process" 2>/dev/null || true
  fi
  if [[ -n "$candidate_process" ]] && kill -0 "$candidate_process" 2>/dev/null; then
    kill "$candidate_process" 2>/dev/null || true
    wait "$candidate_process" 2>/dev/null || true
  fi
  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
    -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Cleanup >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

printf '[ui-performance-android-candidate] building exact source SHA %s\n' "$source_commit"
# The performance mode is a compile-time Lite rendering contract. The live
# runner sets the same flag for Playwright, but the candidate bundle must also
# receive it or the physical/browser candidate would retain entrance springs,
# elevation cues, and other motion that the performance contract intentionally
# removes at the qualification boundary.
POCKETLAB_UI_PERF_CANDIDATE=1 VITE_POCKETLAB_UI_PERF_CANDIDATE=1 VITE_POCKETLAB_PERF_TEST=1 POCKETLAB_BUILD_ID="$source_commit" npm run build

python3 scripts/dev/lite/ui_performance_candidate_server.py --source-commit "$source_commit" &
candidate_process=$!

for _ in {1..240}; do
  if curl -fsS --connect-timeout 1 --max-time 2 \
      http://127.0.0.1:18765/__pocketlab_qualification__/candidate.json >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$candidate_process" 2>/dev/null; then
    fail 'candidate server exited before readiness.'
  fi
  sleep 0.25
done
curl -fsS --connect-timeout 1 --max-time 2 \
  http://127.0.0.1:18765/__pocketlab_qualification__/candidate.json >/dev/null \
  || fail 'candidate server did not expose its exact-SHA manifest.'

# Open Chrome only after the exact candidate server is serving. Opening the
# URL before the server exists can leave Android Chrome on a foreground error
# target; CDP may still attach to that target, but it will not deliver real
# renderer animation frames.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -OpenCandidate

bash scripts/dev/lite/android-candidate-keepalive.sh &
keepalive_process=$!
sleep 0.2
if ! kill -0 "$keepalive_process" 2>/dev/null; then
  fail 'the owned Android qualification keepalive exited before physical qualification started.'
fi

printf '[ui-performance-android-candidate] running physical Android qualification for %s\n' "$source_commit"
cdp_arg=""
if (( baseline_mode == 1 )); then cdp_arg="--baseline"; fi
POCKETLAB_ANDROID_WAKE_BEFORE_QUALIFICATION=1 \
LITE_BASE_URL='http://127.0.0.1:18765' \
LITE_PERF_SOURCE_COMMIT="$source_commit" \
  bash scripts/dev/lite/run-ui-performance-android-cdp.sh $cdp_arg
