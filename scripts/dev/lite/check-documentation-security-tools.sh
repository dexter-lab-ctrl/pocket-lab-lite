#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
INSTALL_ROOT="${POCKETLAB_DOC_SECURITY_TOOL_ROOT:-$ROOT/.pocketlab-dev/tools/documentation-security}"
export PATH="$INSTALL_ROOT/bin:$PATH"
exec python3 "$ROOT/scripts/dev/lite/documentation_security_tools.py" check "$@"
