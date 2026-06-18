#!/usr/bin/env bash
set -Eeuo pipefail
PYTHON="${PYTHON:-.venv/bin/python}"; [[ -x "$PYTHON" ]] || PYTHON=python3
"$PYTHON" -m pytest -q tests/nats/test_subject_permissions.py
