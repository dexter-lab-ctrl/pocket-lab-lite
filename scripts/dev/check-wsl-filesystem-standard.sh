#!/usr/bin/env bash
set -Eeuo pipefail

ok(){ printf '[OK] %s\n  %s\n' "$1" "$2"; }
fail(){ printf '[FAIL] %s\n  %s\n' "$1" "$2" >&2; exit 1; }
warn(){ printf '[WARN] %s\n  %s\n' "$1" "$2"; }

REPORT_PATH="${POCKETLAB_WSL_FILESYSTEM_REPORT_PATH:-.pocketlab-dev/reports/wsl-filesystem-standard.json}"
EXPECTED_ROOT="${POCKETLAB_WSL_REPO_PATH:-$HOME/pocket-lab}"

mkdir -p "$(dirname "$REPORT_PATH")"

printf '\nPocket Lab WSL2 filesystem standardization check\n'
printf '================================================\n'

if [[ "$(uname -s)" != "Linux" ]]; then
  fail "Linux filesystem" "This check must run inside Ubuntu/WSL Linux."
fi

if ! grep -qi microsoft /proc/version 2>/dev/null; then
  warn "WSL marker" "Microsoft WSL marker not detected; continuing because this is Linux."
else
  ok "WSL marker" "Microsoft WSL kernel detected"
fi

if [[ ! -f "Taskfile.yml" ]]; then
  fail "Pocket Lab repo root" "Taskfile.yml not found. Run this from the Pocket Lab repo root."
fi

CURRENT_ROOT="$(pwd -P)"
EXPECTED_ROOT="$(realpath -m "$EXPECTED_ROOT")"

case "$CURRENT_ROOT" in
  /mnt/*|/run/desktop/mnt/*|/host_mnt/*)
    fail "Primary repo filesystem" "Current repo is on a mounted Windows filesystem: $CURRENT_ROOT. Use $EXPECTED_ROOT for primary development."
    ;;
esac

if [[ "$CURRENT_ROOT" != "$EXPECTED_ROOT" ]]; then
  fail "Primary repo location" "Current repo is $CURRENT_ROOT, expected $EXPECTED_ROOT. Set POCKETLAB_WSL_REPO_PATH only if intentionally overriding the standard."
fi

if [[ -e ".venv" ]]; then
  VENV_REAL="$(realpath -m .venv)"
  case "$VENV_REAL" in
    /mnt/*|/run/desktop/mnt/*|/host_mnt/*)
      fail "Python virtualenv filesystem" ".venv resolves to mounted Windows filesystem: $VENV_REAL"
      ;;
  esac
  ok "Python virtualenv filesystem" "$VENV_REAL"
else
  warn "Python virtualenv filesystem" ".venv not found yet"
fi

if [[ -e "node_modules" ]]; then
  NODE_MODULES_REAL="$(realpath -m node_modules)"
  case "$NODE_MODULES_REAL" in
    /mnt/*|/run/desktop/mnt/*|/host_mnt/*)
      fail "node_modules filesystem" "node_modules resolves to mounted Windows filesystem: $NODE_MODULES_REAL"
      ;;
  esac
  ok "node_modules filesystem" "$NODE_MODULES_REAL"
else
  warn "node_modules filesystem" "node_modules not found yet"
fi

cat > "$REPORT_PATH" <<JSON
{
  "schema": "pocketlab.wslFilesystemStandard/v1",
  "generated_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "OK",
  "current_root": "$CURRENT_ROOT",
  "expected_root": "$EXPECTED_ROOT",
  "windows_mounted_primary_repo": false
}
JSON

ok "Primary repo filesystem" "$CURRENT_ROOT"
ok "Filesystem standard report" "$REPORT_PATH"
printf 'WSL filesystem standardization check passed.\n'
