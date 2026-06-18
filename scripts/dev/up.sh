#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p .pocketlab-dev/logs .pocketlab-dev/pids .pocketlab-dev/state
bash scripts/dev/run-nats-dev.sh
nohup bash scripts/dev/run-fastapi-dev.sh > .pocketlab-dev/logs/fastapi.log 2>&1 & echo $! > .pocketlab-dev/pids/fastapi.pid
sleep 3
nohup bash scripts/dev/run-worker-dev.sh > .pocketlab-dev/logs/worker.log 2>&1 & echo $! > .pocketlab-dev/pids/worker.pid
nohup npm run dev -- --host 127.0.0.1 > .pocketlab-dev/logs/frontend.log 2>&1 & echo $! > .pocketlab-dev/pids/frontend.pid
cat <<MSG
Pocket Lab dev stack is starting
Frontend:      http://127.0.0.1:5173
FastAPI:       http://127.0.0.1:8000
OpenAPI:       http://127.0.0.1:8000/docs
NATS Monitor:  http://127.0.0.1:8222
State Dir:     .pocketlab-dev/state
Logs:          .pocketlab-dev/logs
MSG
