#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"
cd "$REPO_ROOT"

PYTHON="${POCKETLAB_DEV_PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON=python3; fi
RAW_DIR=".pocketlab-dev/raw-har"
SAFE_DIR=".pocketlab-dev/validation/har"

cleanup_raw_har() {
  rm -rf -- "$RAW_DIR"
}
trap cleanup_raw_har EXIT INT TERM

bash "$SCRIPT_DIR/frontend-resource-preflight.sh" mocked || exit $?

rm -rf -- "$RAW_DIR"
mkdir -p "$RAW_DIR" "$SAFE_DIR"

set +e
bash "$SCRIPT_DIR/dev-scratch.sh" run playwright -- \
  env VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked \
  npx playwright test \
    tests/e2e/lite-mocked.spec.ts \
    --project=mocked-desktop --project=mocked-mobile
status=$?
set -e

for raw in "$RAW_DIR"/*.har; do
  [[ -f "$raw" ]] || continue
  name="$(basename "$raw" .har)"
  "$PYTHON" scripts/dev/lite/har_tool.py sanitize \
    --input "$raw" --output "$SAFE_DIR/${name}.sanitized.har"
  "$PYTHON" scripts/dev/lite/har_tool.py inspect \
    --input "$SAFE_DIR/${name}.sanitized.har" \
    > "$SAFE_DIR/${name}.inspection.json"
done

if (( status != 0 )); then
  printf 'ERROR mocked Playwright failed with status %s\n' "$status" >&2
  printf 'INFO resource snapshot after failure (no automatic cleanup):\n' >&2
  free -h >&2 || true
  df -h /tmp "$(bash "$SCRIPT_DIR/dev-scratch.sh" path playwright)" >&2 || true
fi

exit "$status"
