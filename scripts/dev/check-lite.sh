#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

bash scripts/dev/check-lite-bootstrap.sh
bash scripts/dev/check-lite-api.sh

python3 -m pytest -q \
  tests/backend/test_import_app.py \
  tests/backend/test_ready.py \
  tests/backend/test_nats_required.py \
  tests/backend/test_lite_api.py

if [[ ! -x node_modules/.bin/vite ]]; then
  echo "ERROR: frontend dependencies are missing. Run npm install or npm ci, then rerun this check." >&2
  exit 1
fi

npm run build
mkdocs build --strict

echo "Pocket Lab Lite validation passed"

# Pocket Lab Lite network listener regression checks
START_DASHBOARD_SCRIPT="pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh"

if ! grep -Fq ':${DASH_PORT} {' "$START_DASHBOARD_SCRIPT"; then
  echo "ERROR: Lite Caddy generator must emit a host-agnostic :${DASH_PORT} listener"
  exit 1
fi

if grep -Fq 'http://127.0.0.1:${DASH_PORT} {' "$START_DASHBOARD_SCRIPT"; then
  echo "ERROR: Lite Caddy generator must not bind dashboard only to 127.0.0.1"
  exit 1
fi

if ! grep -Fq 'listen: 0.0.0.0:4222' "$START_DASHBOARD_SCRIPT"; then
  echo "ERROR: Lite NATS generator must expose the client listener for fleet agents"
  exit 1
fi

if ! grep -Fq 'http: 127.0.0.1:8222' "$START_DASHBOARD_SCRIPT"; then
  echo "ERROR: Lite NATS monitoring endpoint should remain localhost-only"
  exit 1
fi

