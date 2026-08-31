#!/usr/bin/env bash
set -euo pipefail

PLAYWRIGHT_MCP_VERSION="0.0.79"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="${POCKETLAB_REPO:-$(cd "$SCRIPT_DIR/../../.." && pwd -P)}"

for marker in .git AGENTS.md engineering/codex; do
  [[ -e "$REPO/$marker" ]] || { printf 'ERROR missing Pocket Lab repository marker: %s\n' "$marker" >&2; exit 2; }
done

NVM_SH="$HOME/.nvm/nvm.sh"
[[ -s "$NVM_SH" ]] || { printf 'ERROR pinned WSL2 nvm is unavailable: %s\n' "$NVM_SH" >&2; exit 2; }
# shellcheck source=/dev/null
source "$NVM_SH"
nvm use 24.16.0 >/dev/null

[[ "$(node --version)" == "v24.16.0" ]] || { printf 'ERROR Node 24.16.0 is required\n' >&2; exit 2; }
[[ "$(npm --version)" == "11.13.0" ]] || { printf 'ERROR npm 11.13.0 is required\n' >&2; exit 2; }
[[ "$(npx --version)" == "11.13.0" ]] || { printf 'ERROR npx 11.13.0 is required\n' >&2; exit 2; }

TOOL_ROOT="$REPO/.pocketlab-dev/mcp/playwright"
PACKAGE_JSON="$TOOL_ROOT/node_modules/@playwright/mcp/package.json"
PACKAGE_LOCK="$TOOL_ROOT/package-lock.json"
if [[ -f "$PACKAGE_JSON" && -f "$PACKAGE_LOCK" ]]; then
  INSTALLED_VERSION="$(node -p "require(process.argv[1]).version" "$PACKAGE_JSON")"
  if [[ "$INSTALLED_VERSION" == "$PLAYWRIGHT_MCP_VERSION" ]]; then
    printf 'PASS Playwright MCP %s is already installed\n' "$PLAYWRIGHT_MCP_VERSION"
    exit 0
  fi
fi

mkdir -p "$TOOL_ROOT"
npm install --prefix "$TOOL_ROOT" --ignore-scripts "@playwright/mcp@$PLAYWRIGHT_MCP_VERSION"

INSTALLED_VERSION="$(node -p "require(process.argv[1]).version" "$PACKAGE_JSON")"
[[ "$INSTALLED_VERSION" == "$PLAYWRIGHT_MCP_VERSION" ]] || { printf 'ERROR unexpected Playwright MCP version: %s\n' "$INSTALLED_VERSION" >&2; exit 2; }
[[ -f "$TOOL_ROOT/node_modules/@playwright/mcp/cli.js" ]] || { printf 'ERROR Playwright MCP executable is unavailable\n' >&2; exit 2; }
printf 'PASS installed Playwright MCP %s in isolated developer tooling\n' "$PLAYWRIGHT_MCP_VERSION"
