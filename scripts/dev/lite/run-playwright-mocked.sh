#!/usr/bin/env bash
set -uo pipefail

PYTHON="${POCKETLAB_DEV_PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON=python3; fi
RAW_DIR=".pocketlab-dev/raw-har"
SAFE_DIR=".pocketlab-dev/validation/har"
rm -rf "$RAW_DIR"
mkdir -p "$RAW_DIR" "$SAFE_DIR"

set +e
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test \
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
rm -rf "$RAW_DIR"
exit "$status"
