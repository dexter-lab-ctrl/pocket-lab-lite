#!/usr/bin/env bash
set -Eeuo pipefail
[[ -f contracts/openapi.json ]] || bash scripts/dev/export-openapi.sh
python3 - <<'PY'
import json, re
from pathlib import Path
openapi = json.loads(Path('contracts/openapi.json').read_text())
paths = set(openapi.get('paths', {}).keys())
source = '\n'.join(p.read_text(errors='ignore') for p in Path('src').rglob('*') if p.is_file() and p.suffix in {'.js','.jsx','.ts','.tsx'})
found = set(re.findall(r"['\"](/(?:api|ready|health|ws)[^'\"`\s)]*)", source))
allow_prefix = ['/ws/']
missing = []
for item in sorted(found):
    clean = item.split('?')[0]
    if any(clean.startswith(prefix) for prefix in allow_prefix):
        continue
    if clean in ['/ready', '/health', '/healthz']:
        if clean not in paths and '/ready' not in paths:
            missing.append(clean)
        continue
    if clean not in paths:
        missing.append(clean)
if missing:
    print('Frontend API calls missing from OpenAPI:')
    for m in missing: print('  -', m)
    raise SystemExit(1)
print(f'API contract passed: {len(found)} frontend paths checked against OpenAPI')
PY
