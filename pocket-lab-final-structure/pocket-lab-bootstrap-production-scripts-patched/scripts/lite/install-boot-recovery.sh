#!/usr/bin/env bash
# Install the repository-owned Termux:Boot entry and start the external PM2
# guardian. No secrets are embedded in the generated boot file.
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
#!/data/data/com.termux/files/usr/bin/bash
set -u
export HOME="${HOME:-/data/data/com.termux/files/home}"
export PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PATH="$PREFIX/bin:$HOME/.local/bin:$PATH"
mkdir -p "$LOG_DIR"
sleep "${POCKETLAB_LITE_BOOT_DELAY_SECONDS:-8}"
if [[ "${POCKETLAB_LITE_BOOT_WAKE_LOCK:-0}" == "1" ]] && command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock >/dev/null 2>&1 || true
fi
nohup "$GUARDIAN" --boot >>"$BOOT_LOG" 2>&1 &
EOF

  chmod 700 "$BOOT_FILE"
  pm2 save >/dev/null 2>&1 || true

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
  nohup "$GUARDIAN" --boot >>"$BOOT_LOG" 2>&1 &

  mark_done lite_boot_recovery_ready
  log INFO "Lite Android boot recovery installed. Termux:Boot will invoke the external PM2 guardian after Android boot."
}

main "$@"
