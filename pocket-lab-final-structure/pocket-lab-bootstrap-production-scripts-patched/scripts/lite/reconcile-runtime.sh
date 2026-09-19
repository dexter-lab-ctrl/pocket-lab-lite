#!/usr/bin/env bash
# Pocket Lab Lite runtime convergence entrypoint.
#
# This script is deliberately NOT bootstrap. It never installs packages,
# downloads applications, initializes legacy services, or rewrites secrets.
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_SCRIPT_DIR="$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_SCRIPT_DIR/lib/common.sh"

DASHBOARD="$ROOT_SCRIPT_DIR/start-dashboard.sh"
MODE="manual"
REASON="manual_reconcile"

sanitize_reason() {
  printf '%s' "${1:-manual_reconcile}" | tr -cd 'A-Za-z0-9_.:-' | cut -c1-120
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --boot)
      MODE="boot"
      REASON="android_boot"
      shift
      ;;
    --repair)
      MODE="repair"
      shift
      ;;
    --reason)
      [[ "${2:-}" != "" ]] || die "--reason requires a value"
      REASON="$(sanitize_reason "$2")"
      shift 2
      ;;
    --reason=*)
      REASON="$(sanitize_reason "${1#--reason=}")"
      shift
      ;;
    *)
      die "Unknown runtime reconciliation argument: $1"
      ;;
  esac
done

write_evidence() {
  local status="$1"
  local evidence_dir="${POCKETLAB_STATE_DIR:-$POCKET_LAB_BASE_DIR/state}/runtime-reconciler"
  local file="$evidence_dir/last-convergence.json"
  mkdir -p "$evidence_dir"
  python3 - "$file" "$status" "$MODE" "$REASON" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
path, status, mode, reason = sys.argv[1:5]
payload = {
    "status": status,
    "mode": mode,
    "reason": reason,
    "converged_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "bootstrap_ran": False,
    "downloads_allowed": False,
    "legacy_services_allowed": False,
    "sanitized": True,
}
tmp = Path(path + ".tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(Path(path))
PY
}

main() {
  SCRIPT_NAME="reconcile-runtime.sh"
  acquire_lock "$SCRIPT_NAME"
  ensure_root_dirs
  require_termux
  require_cmd bash python3 pm2
  [[ -f "$DASHBOARD" ]] || die "Lite dashboard runtime script is missing"

  export POCKETLAB_PROFILE=lite
  export POCKETLAB_LITE=1
  export POCKETLAB_RECONCILE_ONLY=1

  log INFO "Reconciling Pocket Lab Lite runtime mode=$MODE reason=$REASON"
  if bash "$DASHBOARD" --lite --reconcile-only; then
    pm2 save >/dev/null 2>&1 || true
    write_evidence "converged"
    log INFO "Pocket Lab Lite runtime converged"
    return 0
  fi

  write_evidence "degraded"
  die "Pocket Lab Lite runtime did not converge"
}

main "$@"
