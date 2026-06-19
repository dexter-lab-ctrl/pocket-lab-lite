#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="${POCKETLAB_WSL_REPO:-/home/dj/pocket-lab-lite}"
TARGET="${POCKETLAB_WINDOWS_REPO:-/mnt/h/HomeLab/Pocket-Lab/pocket-lab-app-pwa}"

MODE="dry-run"
DELETE_MODE="--delete"

usage() {
  cat <<'EOF'
Pocket Lab WSL → Windows repo sync

Usage:
  bash scripts/dev/sync-wsl-to-windows.sh              # dry-run only
  bash scripts/dev/sync-wsl-to-windows.sh --apply      # perform sync
  bash scripts/dev/sync-wsl-to-windows.sh --apply --no-delete

Environment overrides:
  POCKETLAB_WSL_REPO=/home/dj/pocket-lab-lite
  POCKETLAB_WINDOWS_REPO=/mnt/h/HomeLab/Pocket-Lab/pocket-lab-app-pwa

Default behavior:
  - Dry-run unless --apply is provided
  - Deletes target files removed from source, except excluded local/runtime dirs
  - Excludes .git, .venv, node_modules, .pocketlab-dev, caches, logs, dist, site, and release artifacts
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      MODE="apply"
      shift
      ;;
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --no-delete)
      DELETE_MODE=""
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_cmd rsync
require_cmd git

[[ -d "$SOURCE" ]] || fail "source repo does not exist: $SOURCE"
[[ -d "$TARGET" ]] || fail "target Windows mirror does not exist: $TARGET"

SOURCE_REAL="$(realpath "$SOURCE")"
TARGET_REAL="$(realpath "$TARGET")"

[[ "$SOURCE_REAL" == /home/* ]] || fail "source must be on the Linux filesystem, got: $SOURCE_REAL"
[[ "$TARGET_REAL" == /mnt/* ]] || fail "target should be a Windows-mounted path under /mnt, got: $TARGET_REAL"
[[ "$SOURCE_REAL" != "$TARGET_REAL" ]] || fail "source and target are the same path"

cd "$SOURCE_REAL"

if [[ ! -f "Taskfile.yml" || ! -d "src" || ! -d "scripts" ]]; then
  fail "source does not look like the Pocket Lab repo: $SOURCE_REAL"
fi

if [[ ! -d "$TARGET_REAL" ]]; then
  fail "target directory missing: $TARGET_REAL"
fi

mkdir -p "$SOURCE_REAL/.pocketlab-dev/logs"

STAMP="$(date -u '+%Y%m%d-%H%M%S')"
LOG_FILE="$SOURCE_REAL/.pocketlab-dev/logs/sync-wsl-to-windows-$STAMP.log"

log "Pocket Lab WSL → Windows sync"
log "Source: $SOURCE_REAL"
log "Target: $TARGET_REAL"
log "Mode:   $MODE"
log "Delete: ${DELETE_MODE:-disabled}"
log "Log:    $LOG_FILE"

log "Source git status summary:"
git status --short || true

RSYNC_ARGS=(
  -a
  --human-readable
  --itemize-changes
  --safe-links
  --exclude='.git/'
  --exclude='.venv/'
  --exclude='node_modules/'
  --exclude='.pocketlab-dev/'
  --exclude='dist/'
  --exclude='site/'
  --exclude='storybook-static/'
  --exclude='coverage/'
  --exclude='playwright-report/'
  --exclude='test-results/'
  --exclude='__pycache__/'
  --exclude='.pytest_cache/'
  --exclude='.ruff_cache/'
  --exclude='.mypy_cache/'
  --exclude='.cache/'
  --exclude='*.pyc'
  --exclude='*.pyo'
  --exclude='*.log'
  --exclude='*.tmp'
  --exclude='*.swp'
  --exclude='*.swo'
  --exclude='*.pid'
)

if [[ -n "$DELETE_MODE" ]]; then
  RSYNC_ARGS+=("$DELETE_MODE")
fi

if [[ "$MODE" == "dry-run" ]]; then
  RSYNC_ARGS+=(--dry-run)
  log "Running dry-run. No files will be changed."
else
  log "Running apply mode. Files will be copied to Windows mirror."
fi

set +e
rsync "${RSYNC_ARGS[@]}" "$SOURCE_REAL/" "$TARGET_REAL/" | tee "$LOG_FILE"
RSYNC_STATUS=${PIPESTATUS[0]}
set -e

if [[ "$RSYNC_STATUS" -ne 0 ]]; then
  fail "rsync failed with exit code $RSYNC_STATUS"
fi

log "Sync command completed successfully."

if [[ "$MODE" == "dry-run" ]]; then
  cat <<EOF

Dry-run complete.

To apply the sync, run:

  bash scripts/dev/sync-wsl-to-windows.sh --apply

To apply without deleting files from the Windows mirror, run:

  bash scripts/dev/sync-wsl-to-windows.sh --apply --no-delete

EOF
else
  cat <<EOF

Apply sync complete.

Recommended verification:

  diff -q "$SOURCE_REAL/Taskfile.yml" "$TARGET_REAL/Taskfile.yml"
  diff -q "$SOURCE_REAL/scripts/dev/check-supply-chain.sh" "$TARGET_REAL/scripts/dev/check-supply-chain.sh"
  diff -q "$SOURCE_REAL/scripts/docs/run_validation_release_gates.py" "$TARGET_REAL/scripts/docs/run_validation_release_gates.py"

EOF
fi
