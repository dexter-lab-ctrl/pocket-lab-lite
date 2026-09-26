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

# The physical matrix is intentionally fixed-size. A qualifier can return
# non-zero for truthful target/gate misses, but it must still produce every
# safe interaction report before the run is eligible for baseline analysis.
# Android Chrome occasionally loses the foreground candidate tab between the
# control page and the measured page; retry the complete qualifier once from
# a clean evidence directory instead of normalizing a partial run.
expected_interaction_reports="${LITE_ANDROID_EXPECTED_INTERACTION_REPORTS:-27}"
if ! [[ "$expected_interaction_reports" =~ ^[0-9]+$ ]] || (( expected_interaction_reports < 1 )); then
  fail 'LITE_ANDROID_EXPECTED_INTERACTION_REPORTS must be a positive integer.'
fi
qualifier_attempts=3

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

  qualifier_status=1
  evidence_count=0
  evidence_files=()
  for qualifier_attempt in $(seq 1 "$qualifier_attempts"); do
    rm -rf .pocketlab-dev/performance
    mkdir -p .pocketlab-dev/performance

    set +e
    node scripts/dev/lite/qualify-ui-performance-android-cdp.mjs
    qualifier_status=$?
    set -e

    shopt -s nullglob
    evidence_files=(.pocketlab-dev/performance/ui-performance-android-cdp-*.json)
    shopt -u nullglob
    evidence_count="${#evidence_files[@]}"
    if (( evidence_count == expected_interaction_reports )); then
      break
    fi
    if (( qualifier_attempt < qualifier_attempts )); then
      printf '[ui-performance-android-baseline] %s produced %s/%s reports on attempt %s; retrying the complete qualifier from a clean evidence directory.\n' \
        "$run_name" "$evidence_count" "$expected_interaction_reports" "$qualifier_attempt" >&2
    fi
  done
  qualifier_statuses+=("$qualifier_status")

  (( evidence_count == expected_interaction_reports )) || fail "${run_name} produced ${evidence_count}/${expected_interaction_reports} physical Android interaction reports after ${qualifier_attempts} attempts."
  cp "${evidence_files[@]}" "$run_root/evidence/"

  node scripts/dev/lite/qualify-ui-performance-android-baseline.mjs     --label "${run_name}-after"     --samples 3     --output "$run_root/baseline-after.json"

  printf '[ui-performance-android-baseline] %s captured %s interaction reports; qualifier exit=%s\n'     "$run_name" "$evidence_count" "$qualifier_status"
done

rm -rf .pocketlab-dev/performance
mkdir -p .pocketlab-dev/performance

node scripts/dev/lite/analyze-ui-performance-android-baseline.mjs   --runs-root "$staging_root"   --output-dir .pocketlab-dev/performance   --write-summary .pocketlab-dev/performance/android-baseline-summary.json

printf '[ui-performance-android-baseline] repeated qualification complete; raw runs=%s normalized=%s\n'   "$repetitions" ".pocketlab-dev/performance"
printf '[ui-performance-android-baseline] underlying qualifier exits: %s\n' "${qualifier_statuses[*]}"
