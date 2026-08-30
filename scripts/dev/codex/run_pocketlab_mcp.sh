#!/usr/bin/env bash
set -euo pipefail

REPO="${POCKETLAB_REPO:-$HOME/pocket-lab-lite}"
REPO="$(cd "$REPO" && pwd -P)"

for marker in .git AGENTS.md engineering/codex; do
  if [[ ! -e "$REPO/$marker" ]]; then
    printf 'ERROR missing Pocket Lab repository marker: %s\n' "$marker" >&2
    exit 2
  fi
done

PYTHON="$REPO/.pocketlab-dev/mcp/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  printf 'ERROR MCP virtual environment is unavailable: %s\n' "$PYTHON" >&2
  exit 2
fi

cd "$REPO"
exec env POCKETLAB_REPO="$REPO" "$PYTHON" -m pocketlab_dev_mcp.server
