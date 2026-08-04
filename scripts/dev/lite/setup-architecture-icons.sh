#!/usr/bin/env bash
set -Eeuo pipefail

if [[ -n "${TERMUX_VERSION:-}" || "${PREFIX:-}" == *"com.termux"* || "$(uname -o 2>/dev/null || true)" == "Android" ]]; then
  echo "ERROR: Architecture icon setup is Development/CI-only and must not run in Android/Termux." >&2
  exit 3
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="${POCKETLAB_DEV_PYTHON:-${PYTHON:-python3}}"
cd "$REPO_ROOT"

exec "$PYTHON_BIN" scripts/docs/graphviz/icon_registry.py "$@"
