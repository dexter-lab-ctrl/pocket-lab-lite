#!/usr/bin/env bash
set -Eeuo pipefail

CADDYFILE="${POCKETLAB_CADDYFILE:-$HOME/pocket-lab-lite/caddy/Caddyfile}"

log() {
  printf '[%s] [restart-caddy-proxy] %s
' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    log "Missing required command: $1"
    exit 1
  }
}

require_cmd python3
require_cmd caddy
require_cmd pm2

python3 - <<PY2
from pathlib import Path

p = Path("$CADDYFILE")
if not p.exists():
    raise SystemExit(f"Caddyfile not found: {p}")

s = p.read_text()
s = s.replace("handle_path /apps/photoprism/* {", "handle /apps/photoprism/* {")
p.write_text(s)
PY2

caddy validate --config "$CADDYFILE" >/dev/null
pm2 delete caddy-proxy >/dev/null 2>&1 || true
pm2 start "$(command -v caddy)" --name caddy-proxy -- run --config "$CADDYFILE" >/dev/null
sleep 3
curl -fsS http://127.0.0.1:8443/api/lite/catalog >/dev/null || {
  log "Caddy started but Lite API route is not reachable on 127.0.0.1:8443"
  exit 1
}
log "Caddy proxy is healthy on 127.0.0.1:8443"
