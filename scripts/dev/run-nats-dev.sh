#!/usr/bin/env bash
set -Eeuo pipefail
docker compose -f docker-compose.dev.yml up -d nats
bash scripts/dev/wait-http.sh http://127.0.0.1:8222/healthz 30
curl -fsS http://127.0.0.1:8222/jsz >/dev/null || echo "WARN: NATS monitor is up; JetStream details may not be exposed at /jsz"
echo "NATS/JetStream dev stack is running on nats://127.0.0.1:4222, monitor http://127.0.0.1:8222"
