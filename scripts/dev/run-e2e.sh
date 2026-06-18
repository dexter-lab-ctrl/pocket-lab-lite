#!/usr/bin/env bash
set -euo pipefail

echo "Running Pocket Lab broad non-visual E2E gate..."

npx playwright test \
  tests/e2e/accessibility.spec.ts \
  tests/e2e/app-store.spec.ts \
  tests/e2e/control-plane-readiness.spec.ts \
  tests/e2e/drift.spec.ts \
  tests/e2e/fault-degraded-mode.spec.ts \
  tests/e2e/fleet.spec.ts \
  tests/e2e/gitops.spec.ts \
  tests/e2e/golden-path.spec.ts \
  tests/e2e/network-contracts.spec.ts \
  tests/e2e/professional-navigation.spec.ts \
  tests/e2e/release-workflow.spec.ts \
  tests/e2e/security-posture.spec.ts \
  tests/e2e/simple-mode.spec.ts \
  tests/e2e/telemetry.spec.ts \
  tests/e2e/vault.spec.ts \
  tests/e2e/websocket-events.spec.ts \
  --workers="${POCKETLAB_E2E_WORKERS:-2}"
