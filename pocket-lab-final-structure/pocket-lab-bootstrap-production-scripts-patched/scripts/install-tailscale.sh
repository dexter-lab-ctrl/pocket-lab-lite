#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

TAILSCALE_DIR="${TAILSCALE_DIR:-$POCKET_LAB_BASE_DIR/tailscale}"
TAILSCALE_INSTALLER="${TAILSCALE_INSTALLER:-$TAILSCALE_DIR/tailscale_installer.sh}"
TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-pocket-lab}"
TAILSCALE_AUTHKEY="${TAILSCALE_AUTHKEY:-}"
TAILSCALE_LOGIN_TIMEOUT_SECONDS="${TAILSCALE_LOGIN_TIMEOUT_SECONDS:-60}"

ensure_tailscale_dependencies() {
  if have pkg; then
    log INFO "Ensuring Tailscale Termux service dependencies"
    ensure_pkg_installed runit || true
    ensure_pkg_installed termux-services || true
    apt --fix-broken install -y || true
    dpkg --configure -a || true
  fi
}

tailscale_status_ok() {
  have tailscale-cli || return 1
  tailscale-cli status >/dev/null 2>&1 && tailscale-cli ip >/dev/null 2>&1
}

show_tailscale_status() {
  if ! have tailscale-cli; then
    log WARN "tailscale-cli is not available"
    return 0
  fi
  log INFO "Tailscale status:"
  tailscale-cli status || true
  log INFO "Tailscale IPs:"
  tailscale-cli ip || true
}

run_tailscale_enrollment() {
  if ! have tailscale-cli; then
    log WARN "tailscale-cli not available after install; manual enrollment may be required"
    return 1
  fi

  if tailscale_status_ok; then
    log INFO "Tailscale already authenticated"
    show_tailscale_status
    return 0
  fi

  log INFO "Starting Tailscale enrollment"
  if [[ -n "$TAILSCALE_AUTHKEY" ]]; then
    tailscale-cli up --hostname="$TAILSCALE_HOSTNAME" --authkey="$TAILSCALE_AUTHKEY" || true
  else
    log INFO "No TAILSCALE_AUTHKEY provided; interactive browser authentication may be required"
    log INFO "If a login URL appears, approve the device, then rerun this stage"
    if have timeout; then
      timeout "$TAILSCALE_LOGIN_TIMEOUT_SECONDS" tailscale-cli up --hostname="$TAILSCALE_HOSTNAME" || true
    else
      tailscale-cli up --hostname="$TAILSCALE_HOSTNAME" || true
    fi
  fi

  if tailscale_status_ok; then
    log INFO "Tailscale authentication completed"
    show_tailscale_status
    return 0
  fi

  show_tailscale_status
  die "Tailscale is installed but not authenticated yet. Complete browser auth or set TAILSCALE_AUTHKEY, then rerun this stage."
}

main() {
  SCRIPT_NAME="install-tailscale.sh"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  require_termux
  require_cmd curl
  ensure_dir_perm "$TAILSCALE_DIR" 700

  ensure_tailscale_dependencies

  if [[ ! -x "$TAILSCALE_INSTALLER" ]]; then
    log INFO "Fetching Tailscale Termux installer"
    download_file https://raw.githubusercontent.com/bropines/tailscale-termux-cli/main/remote-install.sh "$TAILSCALE_INSTALLER"
    chmod +x "$TAILSCALE_INSTALLER"
  else
    log INFO "Tailscale installer already present"
  fi

  log INFO "Running Tailscale installer/update"
  bash "$TAILSCALE_INSTALLER" || {
    log WARN "Tailscale installer returned non-zero; attempting dependency repair"
    apt --fix-broken install -y || true
    dpkg --configure -a || true
    bash "$TAILSCALE_INSTALLER"
  }

  cat <<ENVEOF | atomic_write "$TAILSCALE_DIR/.env" 0600
TS_SOCKS5_PORT=1055
TAILSCALE_HOSTNAME=${TAILSCALE_HOSTNAME}
ENVEOF

  if have tailscaled-start; then
    tailscaled-start || log WARN "tailscaled-start returned non-zero"
  fi

  sleep 2
  run_tailscale_enrollment
  mark_done tailscale_installed
  log INFO "Tailscale script completed safely"
}
main "$@"
