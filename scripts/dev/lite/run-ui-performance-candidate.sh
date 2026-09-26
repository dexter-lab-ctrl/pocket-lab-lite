#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

fail() {
  printf '[ui-performance-candidate] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail 'git is required.'
command -v npm >/dev/null 2>&1 || fail 'npm is required; activate the checked-in Node toolchain first.'

source_commit="$(git rev-parse HEAD)"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'the candidate source SHA is not an exact commit.'

printf '[ui-performance-candidate] building exact source SHA %s\n' "$source_commit"
POCKETLAB_UI_PERF_CANDIDATE=1 POCKETLAB_BUILD_ID="$source_commit" npm run build

exec python3 scripts/dev/lite/ui_performance_candidate_server.py --source-commit "$source_commit"
