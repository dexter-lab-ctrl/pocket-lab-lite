#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

main() {
  SCRIPT_NAME="install-termux-packages.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_termux
  require_cmd pkg dpkg curl
  export DEBIAN_FRONTEND=noninteractive

  if ! is_done termux_package_metadata; then
    log INFO "Refreshing Termux package metadata safely"
    pkg update -y
    mark_done termux_package_metadata
  else
    log INFO "Termux package metadata was already refreshed"
  fi

  if [[ "${POCKET_LAB_SKIP_TERMUX_UPGRADE:-0}" != "1" ]] && ! is_done termux_package_upgrade; then
    log INFO "Running one-time Termux package upgrade"
    pkg upgrade -y
    mark_done termux_package_upgrade
  else
    log INFO "Skipping package upgrade; already done or disabled"
  fi

  local packages=(python nodejs wget unzip jq curl proot-distro caddy git mariadb openssl ncurses-utils util-linux ncurses coreutils moreutils termux-api ca-certificates gnupg tar gzip xz-utils procps gitea golang python-cryptography)
  local p
  for p in "${packages[@]}"; do ensure_pkg_installed "$p"; done
  if ! have nc; then ensure_pkg_installed netcat-openbsd || log WARN "netcat-openbsd unavailable; Python TCP fallback will be used"; fi

  if ! have pm2; then
    require_cmd npm
    log INFO "Installing PM2 globally with npm"
    npm install -g pm2
  else
    log INFO "PM2 already installed"
  fi
  log INFO "Termux base package layer is ready and safe to rerun"
}
main "$@"
