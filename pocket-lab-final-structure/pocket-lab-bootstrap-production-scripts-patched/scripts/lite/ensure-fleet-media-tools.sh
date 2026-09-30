#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_SCRIPTS_DIR="$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_SCRIPTS_DIR/lib/common.sh"

main() {
  SCRIPT_NAME="ensure-fleet-media-tools.sh"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  require_termux
  require_cmd pkg

  if have rclone; then
    log INFO "Fleet photo backup dependency is ready: rclone"
    exit 0
  fi

  log INFO "Installing managed Fleet photo backup dependency: rclone"
  ensure_pkg_installed rclone

  if ! have rclone; then
    log WARN "rclone is not available; device enrollment may continue with photo backup unavailable"
    exit 1
  fi

  log INFO "Fleet photo backup dependency is ready: rclone"
}

main "$@"
