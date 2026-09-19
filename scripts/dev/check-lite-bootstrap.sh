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
  "$BOOTSTRAP_DIR/scripts/lite/reconcile-runtime.sh"
  "$BOOTSTRAP_DIR/scripts/lite/runtime-guardian.sh"
  "$BOOTSTRAP_DIR/scripts/lite/install-boot-recovery.sh"
  "$BOOTSTRAP_DIR/scripts/lite/install-photoprism-proot.sh"
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

for legacy_stage in init_vault init_mariadb start_gitea seed_gitops_repo; do
  if ! grep -Eq "${legacy_stage}.*\\[skipped\\]|\\[skipped\\].*${legacy_stage}" <<<"$list_output"; then
    echo "ERROR: Lite profile did not skip legacy stage: $legacy_stage" >&2
    exit 1
  fi
done

if grep -Eq 'install_lite_boot_recovery.*\[skipped\]|\[skipped\].*install_lite_boot_recovery' <<<"$list_output"; then
  echo "ERROR: Lite boot recovery stage must not be skipped in Lite profile" >&2
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

for legacy_stage in "4/init_vault" "5/init_mariadb" "6/start_gitea" "7/seed_gitops_repo"; do
  if ! grep -q "Lite profile: skipping stage $legacy_stage" <<<"$dry_output"; then
    echo "ERROR: Lite dry-run did not skip legacy stage $legacy_stage" >&2
    exit 1
  fi
done

if ! grep -q 'Dry-run: would execute stage 13/install_lite_boot_recovery' <<<"$dry_output"; then
  echo "ERROR: Lite dry-run did not include Android boot recovery stage" >&2
  exit 1
fi

full_output="$(POCKET_LAB_ALLOW_NON_TERMUX=1 bash "$BOOTSTRAP_SCRIPT" --profile full --dry-run 2>&1)"
echo "$full_output"

if ! grep -q 'Profile: full' <<<"$full_output"; then
  echo "ERROR: full profile dry-run did not select Profile: full" >&2
  exit 1
fi

echo "Lite bootstrap profile checks passed"
