#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MODE="${1:---check}"
shift || true
case "$MODE" in
  --plan) exec python3 "$ROOT/scripts/dev/lite/documentation_security_tools.py" plan "$@" ;;
  --check) exec python3 "$ROOT/scripts/dev/lite/documentation_security_tools.py" check "$@" ;;
  --install-missing) exec python3 "$ROOT/scripts/dev/lite/documentation_security_tools.py" install "$@" ;;
  --update) exec python3 "$ROOT/scripts/dev/lite/documentation_security_tools.py" install --update "$@" ;;
  *) echo "Usage: $0 [--plan|--check|--install-missing|--update] [--offline] [--include-optional] [--only TOOL]" >&2; exit 2 ;;
esac
