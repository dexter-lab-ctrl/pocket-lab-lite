#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f tests/pocket_lab_test_utils.py ]]; then
  echo "ERROR: tests/pocket_lab_test_utils.py is missing." >&2
  echo "Copy it from the full Pocket Lab repo or restore it from Patch 1 before running Lite API checks." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON:-python3}"

PYTHONPATH="tests:." "$PYTHON_BIN" - <<'PY'
from pocket_lab_test_utils import client

c = client()

read_endpoints = (
    "/api/lite/status",
    "/api/lite/catalog",
    "/api/lite/identity",
    "/api/lite/security",
    "/api/lite/fleet",
    "/api/lite/policy",
    "/api/lite/recovery",
)

for path in read_endpoints:
    response = c.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}: {response.text}"

remove = c.post("/api/lite/catalog/remove", json={"name": "demo"})
assert remove.status_code == 501, f"catalog remove should fail closed with 501, got {remove.status_code}"

restore = c.post("/api/lite/recovery/restore", json={"backup_id": "demo"})
assert restore.status_code in {400, 409, 422}, (
    f"restore without confirmation should be blocked, got {restore.status_code}: {restore.text}"
)

print("Lite API checks passed")
PY
