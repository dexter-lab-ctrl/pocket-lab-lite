#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p contracts
PYTHON="${PYTHON:-.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON=python3
PYTHONPATH="pocket-lab-final-structure:${PYTHONPATH:-}" "$PYTHON" - <<'PY'
import json
from pathlib import Path
from runtime.api_fastapi.pocket_lab_fastapi_server import app
Path('contracts/openapi.json').write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + '\n')
print('Wrote contracts/openapi.json')
PY
