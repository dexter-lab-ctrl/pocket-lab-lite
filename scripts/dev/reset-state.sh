#!/usr/bin/env bash
set -Eeuo pipefail
bash scripts/dev/down.sh || true
rm -rf .pocketlab-dev/state .pocketlab-dev/logs .pocketlab-dev/pids .pocketlab-dev/observability
mkdir -p .pocketlab-dev/state .pocketlab-dev/logs .pocketlab-dev/pids
echo 'Pocket Lab local dev state reset'
