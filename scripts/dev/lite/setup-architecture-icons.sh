#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${TERMUX_VERSION:-}" || "${PREFIX:-}" == *"com.termux"* || "$(uname -o 2>/dev/null || true)" == "Android" ]]; then
  echo "ERROR: Architecture icon setup is Development/CI-only and must not run in Android/Termux." >&2
  exit 3
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="${POCKETLAB_DEV_PYTHON:-${PYTHON:-python3}}"
cd "$REPO_ROOT"

case "${1:-}" in
  --check|--install-missing|--repair|--all)
    exec "$PYTHON_BIN" scripts/docs/graphviz/icon_registry.py "$@"
    ;;
  --icon)
    if [[ -z "${2:-}" ]]; then
      echo "Usage: $0 --icon <icon-id> [--repair|--install-missing|--check]" >&2
      exit 2
    fi
    icon_id="$2"
    mode="${3:---repair}"
    case "$mode" in --check|--install-missing|--repair|--all) ;; *) echo "Invalid mode: $mode" >&2; exit 2;; esac
    exec "$PYTHON_BIN" scripts/docs/graphviz/icon_registry.py "$mode" --icon "$icon_id"
    ;;
  *)
    echo "Usage: $0 {--check|--install-missing|--repair|--all|--icon <id> [mode]}" >&2
    exit 2
    ;;
esac
