#!/usr/bin/env bash
# Reconcile Pocket Lab Lite Caddy through the canonical version-aware runtime
# path. This helper intentionally does not own PM2 process creation.
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD="$SCRIPT_DIR/../start-dashboard.sh"

log() {
  printf '[%s] [restart-caddy-proxy] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

[[ -f "$DASHBOARD" ]] || {
  log "Missing canonical Caddy runtime entrypoint: $DASHBOARD"
  exit 1
}

# start-dashboard --caddy-only owns Caddyfile rendering, validation, exact
# installed-version projection, drift repair, PM2 save, and safe reload/restart.
bash "$DASHBOARD" --lite --caddy-only

curl -fsS --connect-timeout 1 --max-time 5   http://127.0.0.1:8443/api/lite/catalog >/dev/null || {
  log "Caddy converged but Lite API route is not reachable on 127.0.0.1:8443"
  exit 1
}

log "Caddy proxy is healthy on 127.0.0.1:8443"
