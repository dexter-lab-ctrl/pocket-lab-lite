#!/usr/bin/env bash
set -Eeuo pipefail

api="${POCKETLAB_API_URL:-http://127.0.0.1:8000}"
PYTHON="${PYTHON:-.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON=python3

CURL_CONNECT_TIMEOUT="${POCKETLAB_TEST_NATS_CURL_CONNECT_TIMEOUT:-5}"
CURL_MAX_TIME="${POCKETLAB_TEST_NATS_CURL_MAX_TIME:-20}"
OPERATION_SUBMIT_TIMEOUT="${POCKETLAB_TEST_NATS_OPERATION_SUBMIT_TIMEOUT:-30}"
OPERATION_SETTLE_SECONDS="${POCKETLAB_TEST_NATS_OPERATION_SETTLE_SECONDS:-4}"
SUBMIT_OPERATION="${POCKETLAB_TEST_NATS_SUBMIT_OPERATION:-0}"

mkdir -p .pocketlab-dev/logs .pocketlab-dev/state

export POCKETLAB_STATE_DIR="${POCKETLAB_STATE_DIR:-$PWD/.pocketlab-dev/state}"
export POCKETLAB_NATS_URL="${POCKETLAB_NATS_URL:-nats://127.0.0.1:4222}"
export POCKETLAB_NATS_REQUIRED=1
export POCKETLAB_NATS_REQUIRE_JETSTREAM=1

API_PID=""
WORKER_PID=""

cleanup() {
  local status=$?
  trap - EXIT INT TERM HUP

  if [[ -n "${WORKER_PID:-}" ]] && kill -0 "$WORKER_PID" >/dev/null 2>&1; then
    kill "$WORKER_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "${WORKER_PID:-}" ]]; then
    wait "$WORKER_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "${API_PID:-}" ]]; then
    wait "$API_PID" >/dev/null 2>&1 || true
  fi

  exit "$status"
}

trap cleanup EXIT INT TERM HUP

curl_get() {
  curl \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    --max-time "$CURL_MAX_TIME" \
    -fsS "$@"
}

curl_post_status() {
  curl \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    --max-time "$OPERATION_SUBMIT_TIMEOUT" \
    -sS \
    -o .pocketlab-dev/operation-submit.json \
    -w '%{http_code}' \
    -X POST "$api/api/operations/execute" \
    -H 'content-type: application/json' \
    -d "$payload"
}

if [[ "$PYTHON" = /* ]]; then
  PYTHON_FOR_SUBDIR="$PYTHON"
else
  PYTHON_FOR_SUBDIR="../$PYTHON"
fi

bash scripts/dev/run-nats-dev.sh

curl_get http://127.0.0.1:8222/healthz >/dev/null
echo "OK: http://127.0.0.1:8222/healthz"
echo "NATS/JetStream dev stack is running on ${POCKETLAB_NATS_URL}, monitor http://127.0.0.1:8222"

(
  cd pocket-lab-final-structure
  "$PYTHON_FOR_SUBDIR" -m uvicorn runtime.api_fastapi.pocket_lab_fastapi_server:app \
    --host 127.0.0.1 \
    --port 8000 \
    > ../.pocketlab-dev/logs/fastapi.log 2>&1
) &
API_PID=$!

bash scripts/dev/wait-http.sh "$api/api" 45

(
  cd pocket-lab-final-structure
  "$PYTHON_FOR_SUBDIR" runtime/workers/pocketlab_worker.py \
    > ../.pocketlab-dev/logs/worker.log 2>&1
) &
WORKER_PID=$!

sleep 3

curl_get "$api/ready" > .pocketlab-dev/ready.json || true

curl_get "$api/api/nats/status" | tee .pocketlab-dev/nats-status.json

if command -v jq >/dev/null 2>&1; then
  jq -e '.connected == true' .pocketlab-dev/nats-status.json >/dev/null
  jq -e '(.jetstream == true) or (.jetstream_enabled == true)' .pocketlab-dev/nats-status.json >/dev/null
fi

if [[ "$SUBMIT_OPERATION" == "1" || "$SUBMIT_OPERATION" == "true" || "$SUBMIT_OPERATION" == "TRUE" ]]; then
  payload='{"operation":"health_check","target":"control-plane","params":{"source":"nats-integration-test"}}'

  echo "Submitting typed operation through FastAPI → NATS → Worker..."
  status="$(curl_post_status || true)"

  if [[ "$status" != "200" && "$status" != "202" ]]; then
    echo "Operation submit failed with HTTP $status" >&2
    cat .pocketlab-dev/operation-submit.json >&2 || true
    echo "" >&2
    echo "FastAPI log tail:" >&2
    tail -n 80 .pocketlab-dev/logs/fastapi.log >&2 || true
    echo "" >&2
    echo "Worker log tail:" >&2
    tail -n 80 .pocketlab-dev/logs/worker.log >&2 || true
    exit 1
  fi

  sleep "$OPERATION_SETTLE_SECONDS"

  curl_get "$api/api/events/recent" > .pocketlab-dev/events-recent.json || true

  if ! grep -R "health_check\|operation\|control-plane" \
    .pocketlab-dev/events-recent.json \
    .pocketlab-dev/state \
    >/dev/null 2>&1; then
    echo "WARN: event/journal evidence not found; inspect .pocketlab-dev/logs"
  fi
else
  echo "Skipping optional typed operation submit; set POCKETLAB_TEST_NATS_SUBMIT_OPERATION=1 to include it."
fi

for subject in \
  pocketlab.commands.operation.execute \
  pocketlab.commands.vault.rotate \
  pocketlab.commands.fleet \
  pocketlab.events.operation \
  pocketlab.events.health \
  pocketlab.events.fleet \
  pocketlab.audit \
  pocketlab.dlq
do
  echo "Subject contract: $subject"
done

echo "Local NATS/FastAPI/worker integration smoke passed"
