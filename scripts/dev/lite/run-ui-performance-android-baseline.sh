#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

fail() {
  printf '[ui-performance-android-baseline] ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -n "${LITE_ANDROID_CDP_URL:-}" ]] || fail 'LITE_ANDROID_CDP_URL must be set by the Android CDP runner.'
[[ -n "${LITE_BASE_URL:-}" ]] || fail 'LITE_BASE_URL must be set to the exact-SHA candidate origin.'
[[ -n "${LITE_PERF_SOURCE_COMMIT:-}" ]] || fail 'LITE_PERF_SOURCE_COMMIT must be set.'
[[ "$LITE_PERF_SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail 'LITE_PERF_SOURCE_COMMIT must be an exact 40-character Git commit.'
command -v node >/dev/null 2>&1 || fail 'node is required.'
command -v powershell.exe >/dev/null 2>&1 || fail 'Windows PowerShell is required for sanitized Android state capture.'

repetitions="${LITE_ANDROID_BASELINE_REPETITIONS:-3}"
if ! [[ "$repetitions" =~ ^[0-9]+$ ]] || (( repetitions < 3 || repetitions > 5 )); then
  fail 'LITE_ANDROID_BASELINE_REPETITIONS must be an integer from 3 through 5.'
fi

staging_root=".pocketlab-dev/android-performance-baseline/${LITE_PERF_SOURCE_COMMIT}"
rm -rf "$staging_root"
mkdir -p "$staging_root"

qualifier_statuses=()
for run_index in $(seq 1 "$repetitions"); do
  run_name="$(printf 'run-%02d' "$run_index")"
  run_root="$staging_root/$run_name"
  mkdir -p "$run_root/evidence"

  node scripts/dev/lite/qualify-ui-performance-android-baseline.mjs     --label "${run_name}-before"     --samples 3     --output "$run_root/baseline-before.json"

  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass     -File scripts/dev/lite/capture-ui-performance-android-state.ps1     >"$run_root/device-state.json"

  rm -rf .pocketlab-dev/performance
  mkdir -p .pocketlab-dev/performance

  set +e
  node scripts/dev/lite/qualify-ui-performance-android-cdp.mjs
  qualifier_status=$?
  set -e
  qualifier_statuses+=("$qualifier_status")

  shopt -s nullglob
  evidence_files=(.pocketlab-dev/performance/ui-performance-android-cdp-*.json)
  shopt -u nullglob
  (( ${#evidence_files[@]} > 0 )) || fail "${run_name} produced no physical Android interaction evidence."
  cp "${evidence_files[@]}" "$run_root/evidence/"

  node scripts/dev/lite/qualify-ui-performance-android-baseline.mjs     --label "${run_name}-after"     --samples 3     --output "$run_root/baseline-after.json"

  printf '[ui-performance-android-baseline] %s captured %s interaction reports; qualifier exit=%s\n'     "$run_name" "${#evidence_files[@]}" "$qualifier_status"
done

rm -rf .pocketlab-dev/performance
mkdir -p .pocketlab-dev/performance

node scripts/dev/lite/analyze-ui-performance-android-baseline.mjs   --runs-root "$staging_root"   --output-dir .pocketlab-dev/performance   --write-summary .pocketlab-dev/performance/android-baseline-summary.json

printf '[ui-performance-android-baseline] repeated qualification complete; raw runs=%s normalized=%s\n'   "$repetitions" ".pocketlab-dev/performance"
printf '[ui-performance-android-baseline] underlying qualifier exits: %s\n' "${qualifier_statuses[*]}"
