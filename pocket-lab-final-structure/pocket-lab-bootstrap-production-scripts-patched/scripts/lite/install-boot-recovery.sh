#!/usr/bin/env bash
# Install the repository-owned Termux:Boot entry and start the external PM2
# guardian. No secrets are embedded in the generated boot file.
#
# The guardian source keeps a portable /usr/bin/env bash shebang for the
# repository, but native Termux does not provide /usr/bin/env. Every supported
# Android launch therefore invokes the Termux bash binary explicitly.
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_SCRIPT_DIR="$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_SCRIPT_DIR/lib/common.sh"

GUARDIAN="$SCRIPT_DIR/runtime-guardian.sh"
BOOT_DIR="$HOME/.termux/boot"
BOOT_FILE="$BOOT_DIR/pocketlab-lite"
BOOT_LOG="$LOG_DIR/boot-recovery.log"
NETWORK_BOOT_FILE="$BOOT_DIR/00-pocketlab-network-services"
NETWORK_BOOT_LOG="$LOG_DIR/network-services-boot.log"

main() {
  SCRIPT_NAME="install-boot-recovery.sh"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  require_termux
  require_cmd bash pm2
  [[ -x "$GUARDIAN" ]] || die "Lite runtime guardian is missing or not executable: $GUARDIAN"

  mkdir -p "$BOOT_DIR"
  chmod 700 "$BOOT_DIR" 2>/dev/null || true

  cat <<EOF | atomic_write "$BOOT_FILE" 0700
#!${PREFIX}/bin/bash
set -u
export HOME="${HOME:-/data/data/com.termux/files/home}"
export PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PATH="$PREFIX/bin:$HOME/.local/bin:$PATH"
mkdir -p "$LOG_DIR"
if [[ ! -x "$PREFIX/bin/bash" ]]; then
  printf '%s\n' "[ERROR] Termux bash is missing or not executable: $PREFIX/bin/bash" >> "$BOOT_LOG"
  exit 1
fi
if [[ ! -x "$GUARDIAN" ]]; then
  printf '%s\n' "[ERROR] External runtime guardian is missing or not executable: $GUARDIAN" >> "$BOOT_LOG"
  exit 1
fi
sleep "${POCKETLAB_LITE_BOOT_DELAY_SECONDS:-8}"
if [[ "${POCKETLAB_LITE_BOOT_WAKE_LOCK:-0}" == "1" ]] && command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock >/dev/null 2>&1 || true
fi
nohup "$PREFIX/bin/bash" "$GUARDIAN" --boot >>"$BOOT_LOG" 2>&1 &
EOF

  chmod 700 "$BOOT_FILE"

  # Termux:Boot runs entries in lexical order. Keep network access recovery
  # separate from the external guardian so PM2/guardian recovery never relies
  # on Tailscale, and invoke package helpers through native Termux runtimes.
  # This file is intentionally self-contained: it must remain usable while
  # the application checkout is unavailable or PM2 is stopped.
  cat <<EOF | atomic_write "$NETWORK_BOOT_FILE" 0700
#!${PREFIX}/bin/bash
set -u
export HOME="${HOME:-/data/data/com.termux/files/home}"
export PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PATH="\$PREFIX/bin:\$HOME/.local/bin:\$PATH"
STATE_DIR="\$HOME/.pocket_lab"
LOCK_DIR="\$STATE_DIR/locks"
LOCK_FILE="\$LOCK_DIR/network-services-boot.lock"
LOG_DIR="\$HOME/pocket_lab_logs"
LOG_FILE="\$LOG_DIR/network-services-boot.log"
mkdir -p "\$LOCK_DIR" "\$LOG_DIR"

write_log() {
  printf '[%s] %s\n' "\$(date -u +%Y-%m-%dT%H:%M:%SZ)" "\$*" >>"\$LOG_FILE"
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"\$LOCK_FILE"
  flock -n 9 || exit 0
else
  LOCK_DIR_FALLBACK="\${LOCK_FILE}.d"
  if ! mkdir "\$LOCK_DIR_FALLBACK" 2>/dev/null; then
    owner="\$(awk -F= '/^pid=/{print \$2; exit}' "\$LOCK_DIR_FALLBACK/metadata" 2>/dev/null || true)"
    if [[ "\$owner" =~ ^[0-9]+\$ ]] && kill -0 "\$owner" >/dev/null 2>&1; then
      write_log "another network boot invocation is active pid=\$owner"
      exit 0
    fi
    write_log "network boot lock is held without a live owner; refusing duplicate startup"
    exit 0
  fi
  printf 'pid=%s\nstarted_at=%s\n' "\$\$" "\$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"\$LOCK_DIR_FALLBACK/metadata"
  trap 'rm -rf "\$LOCK_DIR_FALLBACK"' EXIT
fi

resolve_executable() {
  [[ -x "\$1" ]] || return 1
  readlink -f -- "\$1" 2>/dev/null || printf '%s\n' "\$1"
}

process_has_exact_executable() {
  local expected pid executable rest proc_executable
  expected="\$(resolve_executable "\$1" 2>/dev/null || true)"
  [[ -n "\$expected" ]] || return 1
  while IFS=$' \t' read -r pid executable rest; do
    [[ "\$pid" =~ ^[0-9]+\$ ]] || continue
    [[ "\$executable" == "\$expected" ]] && return 0
    proc_executable="\$(readlink -f -- "/proc/\$pid/exe" 2>/dev/null || true)"
    [[ "\$proc_executable" == "\$expected" ]] && return 0
  done < <(ps -A -o pid=,args= 2>/dev/null || true)
  return 1
}

if process_has_exact_executable "\$PREFIX/bin/sshd"; then
  write_log "sshd already running"
elif [[ -x "\$PREFIX/bin/sshd" ]]; then
  write_log "starting sshd with native Termux executable"
  nohup "\$PREFIX/bin/sshd" >>"\$LOG_FILE" 2>&1 &
else
  write_log "sshd executable is missing: \$PREFIX/bin/sshd"
fi

if process_has_exact_executable "\$PREFIX/bin/tailscaled"; then
  write_log "tailscaled already running"
elif [[ -x "\$PREFIX/bin/bash" && -x "\$PREFIX/bin/tailscaled-start" ]]; then
  write_log "starting tailscaled-start through native Termux bash"
  nohup "\$PREFIX/bin/bash" "\$PREFIX/bin/tailscaled-start" >>"\$LOG_FILE" 2>&1 &
else
  write_log "tailscaled-start or native bash is missing; local services remain eligible to start"
fi

sleep 2
process_has_exact_executable "\$PREFIX/bin/sshd" && write_log "sshd is running" || write_log "sshd did not become observable in the bounded check"
process_has_exact_executable "\$PREFIX/bin/tailscaled" && write_log "tailscaled is running" || write_log "tailscaled is not running yet; guardian/local recovery is independent"
EOF
  chmod 700 "$NETWORK_BOOT_FILE"
  pm2_save_if_nonempty >/dev/null 2>&1 || true

  # Explicit installer reruns are also the activation boundary for guardian
  # source updates. Stop any previously loaded guardian so the current checkout
  # becomes the running external recovery implementation immediately.
  if pgrep -f "[r]untime-guardian.sh" >/dev/null 2>&1; then
    pkill -f "[r]untime-guardian.sh" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      pgrep -f "[r]untime-guardian.sh" >/dev/null 2>&1 || break
      sleep 0.25
    done
  fi
  # Use the native Termux interpreter explicitly; executing the portable
  # guardian shebang directly fails on Android because /usr/bin/env is absent.
  nohup "$PREFIX/bin/bash" "$GUARDIAN" --boot >>"$BOOT_LOG" 2>&1 &

  mark_done lite_boot_recovery_ready
  log INFO "Lite Android boot recovery installed. Termux:Boot will invoke the external PM2 guardian after Android boot."
}

main "$@"
