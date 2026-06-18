#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p .pocketlab-dev/logs
tail -n 80 -f .pocketlab-dev/logs/*.log
