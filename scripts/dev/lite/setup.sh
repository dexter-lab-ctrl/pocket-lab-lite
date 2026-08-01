#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f package-lock.json || ! -f package.json ]]; then
  echo 'Pocket Lab Lite setup must run from the repository root.' >&2
  exit 2
fi

if [[ ! -x .venv/bin/python ]]; then
  echo 'The existing .venv is missing. This task will not silently replace it.' >&2
  echo 'Create it explicitly with: python3 -m venv .venv' >&2
  exit 2
fi

if [[ ! -d node_modules ]]; then
  echo 'Installing the exact JavaScript dependency graph from package-lock.json (no update/upgrade).'
  PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 PUPPETEER_SKIP_DOWNLOAD=1 npm ci
else
  echo 'node_modules already exists; npm dependency installation skipped.'
fi

if ! .venv/bin/python - <<'PY' >/dev/null 2>&1
import mkdocs, yaml, jinja2, jsonschema, pytest
PY
then
  echo 'Installing only missing/satisfied Python requirements into the existing .venv.'
  .venv/bin/python -m pip install --upgrade-strategy only-if-needed -r requirements-dev.txt
else
  echo 'Python development/documentation requirements already import successfully; pip installation skipped.'
fi

bash scripts/dev/lite/setup-check.sh
