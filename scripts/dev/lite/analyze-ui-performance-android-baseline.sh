#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

commit="${LITE_PERF_SOURCE_COMMIT:-$(git rev-parse HEAD)}"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || {
  echo '[ui-performance-android-baseline] ERROR: exact source commit required' >&2
  exit 1
}
runs_root=".pocketlab-dev/android-performance-baseline/$commit"
[[ -d "$runs_root" ]] || {
  echo "[ui-performance-android-baseline] ERROR: no raw baseline runs for $commit" >&2
  exit 1
}
mkdir -p .pocketlab-dev/performance
exec node scripts/dev/lite/analyze-ui-performance-android-baseline.mjs   --runs-root "$runs_root"   --output-dir .pocketlab-dev/performance   --write-summary .pocketlab-dev/performance/android-baseline-summary.json "$@"
