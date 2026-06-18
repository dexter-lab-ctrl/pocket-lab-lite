#!/usr/bin/env bash
set -Eeuo pipefail
for pidfile in .pocketlab-dev/pids/*.pid; do
  [[ -f "$pidfile" ]] || continue
  pid=$(cat "$pidfile")
  if kill -0 "$pid" >/dev/null 2>&1; then kill "$pid" || true; fi
  rm -f "$pidfile"
done
docker compose -f docker-compose.dev.yml down || true
echo 'Pocket Lab dev stack stopped'
