#!/usr/bin/env bash
set -Eeuo pipefail
PYTHON="${PYTHON:-.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON=python3
"$PYTHON" -m compileall pocket-lab-final-structure/runtime
mkdir -p .pocketlab-dev/validation
PYTHONPATH=tests "$PYTHON" -m pytest -q tests/backend pocket-lab-final-structure/runtime/tests --junitxml=.pocketlab-dev/validation/pytest-backend.xml
"$PYTHON" -m ruff check pocket-lab-final-structure/runtime tests || true
