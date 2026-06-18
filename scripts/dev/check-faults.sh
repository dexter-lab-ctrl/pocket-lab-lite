#!/usr/bin/env bash
set -euo pipefail
FAULTS_WORKERS="${POCKETLAB_FAULTS_WORKERS:-2}"

echo "Running Pocket Lab enterprise fault/degraded-mode gate..."

echo "1) Backend degraded/fail-closed contracts"
if [ -f tests/backend/test_fault_degraded_mode.py ]; then
  .venv/bin/python -m pytest -q tests/backend/test_fault_degraded_mode.py
else
  echo "WARN: tests/backend/test_fault_degraded_mode.py not found; skipping backend fault contracts"
fi

echo "2) Frontend degraded-mode operator journeys"
npx playwright test \
  tests/e2e/fault-degraded-mode.spec.ts \
  tests/e2e/control-plane-readiness.spec.ts \
  tests/e2e/telemetry.spec.ts \
  tests/e2e/websocket-events.spec.ts \
  --workers=${FAULTS_WORKERS}

echo "Enterprise fault/degraded-mode gate passed."
