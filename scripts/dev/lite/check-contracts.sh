#!/usr/bin/env bash
set -euo pipefail
"${POCKETLAB_DEV_PYTHON:-.venv/bin/python}" scripts/docs/lite/generate_contracts.py check
npx --no-install redocly lint contracts/generated/lite-openapi.json
"${POCKETLAB_DEV_PYTHON:-.venv/bin/python}" scripts/docs/lite/generate_docs.py check-storybook
