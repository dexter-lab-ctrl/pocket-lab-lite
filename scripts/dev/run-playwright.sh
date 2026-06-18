#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p .pocketlab-dev/playwright-report .pocketlab-dev/test-results
npx playwright install --with-deps
npx playwright test --reporter=html,list
