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
TOOL_ROOT="$REPO/.pocketlab-dev/mcp/playwright"
PACKAGE_JSON="$TOOL_ROOT/node_modules/@playwright/mcp/package.json"
CLI="$TOOL_ROOT/node_modules/@playwright/mcp/cli.js"
FILTER="$REPO/scripts/dev/codex/playwright_mcp_stdio_filter.mjs"
[[ -f "$PACKAGE_JSON" && -f "$CLI" && -f "$FILTER" ]] || { printf 'ERROR run setup_playwright_mcp.sh first\n' >&2; exit 2; }
[[ "$(node -p "require(process.argv[1]).version" "$PACKAGE_JSON")" == "$PLAYWRIGHT_MCP_VERSION" ]] || { printf 'ERROR unexpected Playwright MCP version\n' >&2; exit 2; }

BROWSER_JSON="$(node "$REPO/scripts/dev/lite/resolve-browser.mjs" --json)"
BROWSER_PATH="$(node -e 'const value=JSON.parse(process.argv[1]); if (!value.executable_path) process.exit(2); process.stdout.write(value.executable_path)' "$BROWSER_JSON")"
[[ -x "$BROWSER_PATH" ]] || { printf 'ERROR resolver returned a non-executable browser path\n' >&2; exit 2; }

DEV_ROOT="$REPO/.pocketlab-dev"
if [[ -e "$DEV_ROOT" ]]; then
  [[ -d "$DEV_ROOT" && ! -L "$DEV_ROOT" ]] || { printf 'ERROR unsafe Playwright MCP state directory\n' >&2; exit 2; }
else
  mkdir "$DEV_ROOT"
fi
OUTPUT_DIR="$DEV_ROOT/playwright-mcp"
if [[ -e "$OUTPUT_DIR" ]]; then
  [[ -d "$OUTPUT_DIR" && ! -L "$OUTPUT_DIR" ]] || { printf 'ERROR unsafe Playwright MCP output directory\n' >&2; exit 2; }
else
  mkdir "$OUTPUT_DIR"
fi
[[ "$(realpath -e "$OUTPUT_DIR")" == "$REPO/.pocketlab-dev/playwright-mcp" ]] || { printf 'ERROR Playwright MCP output directory escaped the repository\n' >&2; exit 2; }
cd "$REPO"
exec env -i HOME="$HOME" PATH="$PATH" LANG="${LANG:-C.UTF-8}" \
  node "$FILTER" node "$CLI" \
  --headless \
  --isolated \
  --executable-path "$BROWSER_PATH" \
  --allowed-origins 'http://127.0.0.1:*;https://127.0.0.1:*;http://localhost:*;https://localhost:*' \
  --output-dir "$OUTPUT_DIR" \
  --output-max-size 67108864 \
  --console-level warning \
  --image-responses omit \
  --snapshot-mode full \
  --codegen none
