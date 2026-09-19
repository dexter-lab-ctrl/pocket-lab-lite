#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${POCKETLAB_DEV_PYTHON:-${PYTHON:-.venv/bin/python}}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi

BOOT="pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"
RUNTIME="pocket-lab-final-structure/runtime"

shell_files=(
  "$BOOT/lib/common.sh"
  "$BOOT/bootstrap.sh"
  "$BOOT/start-dashboard.sh"
  "$BOOT/smoke-test.sh"
  "$BOOT/lite/start-opa-runtime.sh"
  "$BOOT/lite/reconcile-runtime.sh"
  "$BOOT/lite/runtime-guardian.sh"
  "$BOOT/lite/install-boot-recovery.sh"
  "$BOOT/lite/install-photoprism-proot.sh"
  "$BOOT/lite/restart-caddy-proxy.sh"
)

for file in "${shell_files[@]}"; do
  [[ -f "$file" ]] || { echo "ERROR missing $file" >&2; exit 1; }
  bash -n "$file"
done
bash -n scripts/dev/check-lite-runtime-resilience-server-phone.sh
echo "PASS runtime resilience shell syntax"

"$PYTHON" -m py_compile \
  "$RUNTIME/supervisors/pocketlab_runtime_registry.py" \
  "$RUNTIME/supervisors/pocketlab_runtime_reconciler.py" \
  "$RUNTIME/supervisors/pocketlab_core_supervisor.py" \
  "$RUNTIME/agents/pocketlab_agent_supervisor.py"
echo "PASS runtime resilience Python compile"

PYTHONPATH="tests:$RUNTIME" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PYTHON" -m pytest -q \
  tests/backend/test_lite_runtime_reconciler.py \
  tests/backend/test_lite_boot_recovery.py \
  tests/backend/test_lite_core_supervisor.py \
  tests/backend/test_lite_photoprism_runtime_resilience.py \
  tests/backend/test_lite_pm2_idempotency.py \
  tests/backend/test_lite_pm2_version_projection.py

bash scripts/dev/check-lite-bootstrap.sh

reconcile_source="$BOOT/lite/reconcile-runtime.sh"
if grep -Eq 'apt-get|pkg install|proot-distro install|install_or_update_package|curl -fL' "$reconcile_source"; then
  echo "ERROR runtime reconciliation contains install/update behavior" >&2
  exit 1
fi

"$PYTHON" - <<'PY'
import importlib.util
from pathlib import Path
import sys

path = Path("pocket-lab-final-structure/runtime/supervisors/pocketlab_runtime_registry.py")
spec = importlib.util.spec_from_file_location("runtime_registry_check", path)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
names = set(module.control_plane_names())
assert names.isdisjoint(module.LEGACY_LITE_SERVICES), names & module.LEGACY_LITE_SERVICES
print("PASS Lite desired state excludes legacy Pocket Lab services")
PY

echo "PASS Pocket Lab Lite runtime resilience contract checks"
