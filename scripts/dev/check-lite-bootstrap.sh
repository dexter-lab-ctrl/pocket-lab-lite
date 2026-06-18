#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BOOTSTRAP_DIR="pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched"
BOOTSTRAP_SCRIPT="$BOOTSTRAP_DIR/scripts/bootstrap.sh"

scripts=(
  "$BOOTSTRAP_DIR/scripts/lib/common.sh"
  "$BOOTSTRAP_DIR/scripts/bootstrap.sh"
  "$BOOTSTRAP_DIR/scripts/install-binaries.sh"
  "$BOOTSTRAP_DIR/scripts/start-dashboard.sh"
  "$BOOTSTRAP_DIR/scripts/smoke-test.sh"
)

for script in "${scripts[@]}"; do
  if [[ ! -f "$script" ]]; then
    echo "ERROR: missing required script: $script" >&2
    exit 1
  fi
  bash -n "$script"
done

echo "Bootstrap script syntax checks passed"

list_output="$(POCKET_LAB_ALLOW_NON_TERMUX=1 bash "$BOOTSTRAP_SCRIPT" --profile lite --list 2>&1)"
echo "$list_output"

if ! grep -Eq 'install_proot_ubuntu.*\[skipped\]|\[skipped\].*install_proot_ubuntu' <<<"$list_output"; then
  echo "ERROR: lite profile did not mark install_proot_ubuntu as skipped" >&2
  exit 1
fi

dry_output="$(POCKET_LAB_ALLOW_NON_TERMUX=1 bash "$BOOTSTRAP_SCRIPT" --lite --dry-run 2>&1)"
echo "$dry_output"

if ! grep -q 'Profile: lite' <<<"$dry_output"; then
  echo "ERROR: --lite dry-run did not select Profile: lite" >&2
  exit 1
fi

if ! grep -q 'Lite profile: skipping stage 2/install_proot_ubuntu' <<<"$dry_output"; then
  echo "ERROR: lite dry-run did not report PRoot skip behavior" >&2
  exit 1
fi

full_output="$(POCKET_LAB_ALLOW_NON_TERMUX=1 bash "$BOOTSTRAP_SCRIPT" --profile full --dry-run 2>&1)"
echo "$full_output"

if ! grep -q 'Profile: full' <<<"$full_output"; then
  echo "ERROR: full profile dry-run did not select Profile: full" >&2
  exit 1
fi

echo "Lite bootstrap profile checks passed"
