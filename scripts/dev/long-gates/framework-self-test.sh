#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

: "${LONG_GATE_RUN_DIR:?LONG_GATE_RUN_DIR is required}"
: "${LONG_GATE_RUN_ID:?LONG_GATE_RUN_ID is required}"
: "${LONG_GATE_GATE_ID:?LONG_GATE_GATE_ID is required}"

# Keep the runtime smoke test in one bounded Python process. The public shell
# checkpoint API remains available to all future gate implementations.
long_gate_python framework-self-test \
  --run-dir "$LONG_GATE_RUN_DIR" \
  --run-id "$LONG_GATE_RUN_ID" \
  --gate-id "$LONG_GATE_GATE_ID"
