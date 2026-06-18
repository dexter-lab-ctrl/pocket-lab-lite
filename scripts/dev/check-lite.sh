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
