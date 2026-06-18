#!/usr/bin/env bash
set -Eeuo pipefail
python3 - <<'PY'
import json
from pathlib import Path
try:
    import jsonschema
except Exception:
    raise SystemExit('Install jsonschema: .venv/bin/pip install jsonschema')
checks = [
    ('contracts/schemas/telemetry.schema.json', 'tests/fixtures/telemetry_normal.json'),
    ('contracts/schemas/telemetry.schema.json', 'tests/fixtures/telemetry_low_disk.json'),
    ('contracts/schemas/health.schema.json', 'tests/fixtures/health_all_green.json'),
    ('contracts/schemas/health.schema.json', 'tests/fixtures/health_vault_sealed.json'),
]
for schema_path, fixture_path in checks:
    schema = json.loads(Path(schema_path).read_text())
    payload = json.loads(Path(fixture_path).read_text())
    jsonschema.validate(payload, schema)
    print(f'OK {fixture_path} validates against {schema_path}')
PY
