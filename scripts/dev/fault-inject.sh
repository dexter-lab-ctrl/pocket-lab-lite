#!/usr/bin/env bash
set -Eeuo pipefail
scenario="${1:-help}"
mkdir -p .pocketlab-dev/faults
case "$scenario" in
  nats-down) docker compose -f docker-compose.dev.yml stop nats || true; echo nats-down > .pocketlab-dev/faults/current ;;
  worker-down) [[ -f .pocketlab-dev/pids/worker.pid ]] && kill "$(cat .pocketlab-dev/pids/worker.pid)" || true; echo worker-down > .pocketlab-dev/faults/current ;;
  bad-health) echo '{"overall":"degraded","services":{"vault":{"status":"sealed"}}}' > .pocketlab-dev/faults/health-engine.json; echo bad-health > .pocketlab-dev/faults/current ;;
  clear) rm -rf .pocketlab-dev/faults; mkdir -p .pocketlab-dev/faults ;;
  *) echo "Usage: $0 nats-down|worker-down|bad-health|clear" >&2; exit 2 ;;
esac
echo "Fault scenario active: $scenario"
