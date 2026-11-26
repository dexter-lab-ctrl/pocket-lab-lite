#!/usr/bin/env bash
set -euo pipefail

echo "Running Pocket Lab Lite native non-visual E2E gate..."

npx playwright test \
  tests/e2e/lite-accessibility.spec.ts \
  tests/e2e/lite-apps-native-library.spec.ts \
  tests/e2e/lite-devices-native-workspace-qualification.spec.ts \
  tests/e2e/lite-mocked.spec.ts \
  tests/e2e/lite-recovery-native-center.spec.ts \
  tests/e2e/lite-rules-native-center-qualification.spec.ts \
  tests/e2e/lite-security-runtime.spec.ts \
  tests/e2e/lite-system-health.spec.ts \
  --workers="${POCKETLAB_E2E_WORKERS:-2}"
