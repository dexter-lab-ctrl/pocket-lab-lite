#!/usr/bin/env bash
set -Eeuo pipefail
PYTHON="${PYTHON:-.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON=python3
mkdir -p "${POCKETLAB_STATE_DIR:-.pocketlab-dev/state}" .pocketlab-dev/logs
export POCKETLAB_STATE_DIR="${POCKETLAB_STATE_DIR:-.pocketlab-dev/state}"
export POCKETLAB_NATS_URL="${POCKETLAB_NATS_URL:-nats://127.0.0.1:4222}"
export POCKETLAB_NATS_REQUIRED="${POCKETLAB_NATS_REQUIRED:-1}"
export POCKETLAB_NATS_REQUIRE_JETSTREAM="${POCKETLAB_NATS_REQUIRE_JETSTREAM:-1}"
cd pocket-lab-final-structure
exec ../$PYTHON runtime/workers/pocketlab_worker.py
