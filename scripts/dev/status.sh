#!/usr/bin/env bash
set -Eeuo pipefail
api="${POCKETLAB_API_URL:-http://127.0.0.1:8000}"
mkdir -p .pocketlab-dev/status
probe() {
  local name="$1"
  local url="$2"
  local safe_name="${name// /_}"
  local out=".pocketlab-dev/status/${safe_name}.json"

  printf '%-28s ' "$name"

  if curl -fsS "$url" > "$out" 2>/dev/null; then
    echo OK
    if command -v jq >/dev/null 2>&1; then
      jq -C . "$out" | sed 's/^/  /'
    else
      sed 's/^/  /' "$out"
    fi
  else
    echo DOWN
  fi
}
probe "FastAPI ready" "$api/ready"
probe "NATS" "$api/api/nats/status"
probe "Worker" "$api/api/workers/status"
probe "Events" "$api/api/events/status"
probe "Workflows" "$api/api/workflows/status"
probe "Reliability" "$api/api/reliability/status"
curl -fsS http://127.0.0.1:8222/healthz >/dev/null 2>&1 && echo "NATS monitor            OK http://127.0.0.1:8222" || echo "NATS monitor            DOWN"
curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1 && echo "Frontend                OK http://127.0.0.1:5173" || echo "Frontend                DOWN"
[[ -d dist ]] && echo "PWA build               present" || echo "PWA build               missing"
