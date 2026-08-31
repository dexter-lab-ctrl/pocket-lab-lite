#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="${POCKETLAB_REPO:-$(cd "$SCRIPT_DIR/../../.." && pwd -P)}"
SETUP="$REPO/scripts/dev/codex/setup_playwright_mcp.sh"
LAUNCHER="$REPO/scripts/dev/codex/run_playwright_mcp.sh"
FILTER="$REPO/scripts/dev/codex/playwright_mcp_stdio_filter.mjs"
PYTHON="$REPO/.pocketlab-dev/mcp/venv/bin/python"

for marker in .git AGENTS.md engineering/codex; do
  [[ -e "$REPO/$marker" ]] || { printf 'ERROR missing Pocket Lab repository marker: %s\n' "$marker" >&2; exit 2; }
done
[[ -x "$SETUP" && -x "$LAUNCHER" ]] || { printf 'ERROR Playwright MCP scripts must be executable\n' >&2; exit 2; }
[[ -f "$FILTER" ]] || { printf 'ERROR Playwright MCP stdio filter is unavailable\n' >&2; exit 2; }
[[ -x "$PYTHON" ]] || { printf 'ERROR Pocket Lab MCP Python is unavailable\n' >&2; exit 2; }

bash -n "$SETUP" "$LAUNCHER" "$0"
node --check "$FILTER"
rg -q 'PLAYWRIGHT_MCP_VERSION="0\.0\.79"' "$SETUP" "$LAUNCHER"
! rg -n '@latest' "$SETUP" "$LAUNCHER" "$FILTER"
rg -q 'scripts/dev/lite/resolve-browser\.mjs' "$LAUNCHER"
rg -q '\.pocketlab-dev/playwright-mcp' "$LAUNCHER"
rg -q -- '--headless' "$LAUNCHER"
rg -q -- '--isolated' "$LAUNCHER"
rg -q -- '--allowed-origins' "$LAUNCHER"
rg -q -- '--output-max-size 67108864' "$LAUNCHER"
for forbidden in --extension --allow-unrestricted-file-access --cdp-endpoint --port --grant-permissions --no-sandbox --block-service-workers --storage-state --user-data-dir --save-session --save-trace --save-video --caps; do
  ! rg -q -- "$forbidden" "$LAUNCHER"
done
rg -q "browser_run_code_unsafe" "$FILTER"
"$SETUP"
source "$HOME/.nvm/nvm.sh"
nvm use 24.16.0 >/dev/null
[[ "$(node --version)" == "v24.16.0" ]] || { printf 'ERROR Node 24.16.0 is required\n' >&2; exit 2; }
node "$REPO/scripts/dev/lite/resolve-browser.mjs" --json >/dev/null

REPO="$REPO" LAUNCHER="$LAUNCHER" "$PYTHON" - <<'PY'
from __future__ import annotations

import os

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.exceptions import MCPError


async def smoke() -> None:
    server = StdioServerParameters(
        command=os.environ["LAUNCHER"],
        cwd=os.environ["REPO"],
        env={
            "POCKETLAB_REPO": os.environ["REPO"],
            "HOME": os.environ["HOME"],
            "PLAYWRIGHT_MCP_CDP_ENDPOINT": "http://127.0.0.1:1",
            "PLAYWRIGHT_MCP_EXTENSION": "true",
        },
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            expected = {
                "browser_click", "browser_close", "browser_drag", "browser_fill_form",
                "browser_find", "browser_handle_dialog", "browser_hover", "browser_navigate",
                "browser_navigate_back", "browser_press_key", "browser_resize", "browser_select_option",
                "browser_snapshot", "browser_tabs", "browser_type", "browser_wait_for",
            }
            assert names == expected, names
            for name, arguments in (
                ("browser_run_code_unsafe", {"code": "async () => 1"}),
                ("browser_future_power_tool", {}),
            ):
                try:
                    await session.call_tool(name, arguments)
                except MCPError as error:
                    assert "not enabled" in str(error)
                else:
                    raise AssertionError(f"unapproved tool was forwarded: {name}")


anyio.run(smoke)
PY

printf 'PASS Playwright MCP package, browser resolver, and stdio core-tool contract\n'
