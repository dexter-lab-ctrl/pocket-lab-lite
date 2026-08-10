#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"

cd "$REPO_ROOT"

PYTHON="${POCKETLAB_DEV_PYTHON:-${PYTHON:-.venv/bin/python}}"

exec bash "$SCRIPT_DIR/dev-scratch.sh" run docs -- \
  "$PYTHON" -m mkdocs serve \
  --strict \
  --dev-addr "${POCKETLAB_DOCS_DEV_ADDR:-127.0.0.1:8001}"
