#!/usr/bin/env bash
# External Pocket Lab Lite guardian.
#
# This process intentionally runs outside PM2 so it can restore PM2 itself.
# It performs no bootstrap/install/update work.
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_SCRIPT_DIR="$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_SCRIPT_DIR/lib/common.sh"

RECONCILE="$SCRIPT_DIR/reconcile-runtime.sh"
INTERVAL="${POCKETLAB_RUNTIME_GUARDIAN_SECONDS:-30}"
PM2_RESTORE_COOLDOWN="${POCKETLAB_PM2_RESTORE_COOLDOWN_SECONDS:-60}"
LAST_PM2_RESTORE=0
ONCE=0

case "${1:-}" in
  --once) ONCE=1 ;;
  --boot|"") ;;
  *) die "Unknown runtime guardian argument: $1" ;;
esac

pm2_alive() {
  local pm2_home pid_file pid
  pm2_home="${PM2_HOME:-$HOME/.pm2}"
  pid_file="$pm2_home/pm2.pid"
  [[ -s "$pid_file" ]] || return 1
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

pm2_reconciler_online() {
  pm2 jlist 2>/dev/null | python3 -c '
import json,sys
try:
    items=json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
for item in items if isinstance(items,list) else []:
    if item.get("name") != "pocketlab-runtime-reconciler":
        continue
    env=item.get("pm2_env") if isinstance(item.get("pm2_env"),dict) else {}
    status=str(env.get("status") or item.get("status") or "").lower()
    version=str(env.get("version") or "").strip()
    declared=str(env.get("POCKETLAB_SERVICE_VERSION") or "").strip()
    healthy_version=bool(version and version.lower() not in {"n/a","na","unknown"} and version==declared)
    raise SystemExit(0 if status=="online" and healthy_version else 1)
raise SystemExit(1)
'
}

restore_pm2_if_needed() {
  pm2_alive && return 0
  local now
  now="$(date +%s)"
  if (( now - LAST_PM2_RESTORE < PM2_RESTORE_COOLDOWN )); then
    return 1
  fi
  LAST_PM2_RESTORE="$now"
  log WARN "PM2 daemon unavailable; attempting saved-state resurrection"
  if have timeout; then
    timeout 45 pm2 resurrect >/dev/null 2>&1 || true
  else
    pm2 resurrect >/dev/null 2>&1 || true
  fi
  sleep 2
  pm2_alive
}

converge_if_needed() {
  local reason=""
  if ! restore_pm2_if_needed; then
    reason="pm2_unavailable"
  elif ! pm2_reconciler_online; then
    reason="runtime_reconciler_missing_or_version_drift"
  fi

  [[ -n "$reason" ]] || return 0
  [[ -x "$RECONCILE" ]] || {
    log ERROR "Runtime reconciler is missing or not executable"
    return 1
  }
  log WARN "Lite runtime guardian requesting convergence reason=$reason"
  bash "$RECONCILE" --repair --reason "$reason" || return 1
  pm2 save >/dev/null 2>&1 || true
}

main() {
  SCRIPT_NAME="runtime-guardian.sh"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  require_termux
  require_cmd pm2 python3

  while true; do
    converge_if_needed || log WARN "Runtime guardian could not restore desired state on this pass"
    [[ "$ONCE" == "1" ]] && return 0
    sleep "$INTERVAL"
  done
}

main "$@"
