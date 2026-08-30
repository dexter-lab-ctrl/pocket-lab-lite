#!/usr/bin/env bash
set -euo pipefail

REPO="${POCKETLAB_REPO:-$HOME/pocket-lab-lite}"
REPO="$(cd "$REPO" && pwd -P)"
for marker in .git AGENTS.md engineering/codex; do
  [[ -e "$REPO/$marker" ]] || {
    printf 'ERROR missing Pocket Lab repository marker: %s\n' "$marker" >&2
    exit 2
  }
done

PYTHON="$REPO/.pocketlab-dev/mcp/venv/bin/python"
LAUNCHER="$REPO/scripts/dev/codex/run_pocketlab_mcp.sh"
[[ -x "$PYTHON" ]] || { printf 'ERROR MCP Python is unavailable\n' >&2; exit 2; }
[[ -x "$LAUNCHER" ]] || { printf 'ERROR MCP launcher is unavailable\n' >&2; exit 2; }
"$PYTHON" -c 'import pocketlab_dev_mcp' >/dev/null
bash -n "$LAUNCHER" "$REPO/scripts/dev/codex/check_mcp_dev.sh"

REPO="$REPO" LAUNCHER="$LAUNCHER" "$PYTHON" - <<'PY'
from __future__ import annotations

import os

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

EXPECTED_TOOLS = {
    "repo_status",
    "changed_files",
    "validation_targets",
    "run_validation",
}


async def smoke() -> None:
    server = StdioServerParameters(
        command=os.environ["LAUNCHER"],
        cwd=os.environ["REPO"],
        env={"POCKETLAB_REPO": os.environ["REPO"]},
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == EXPECTED_TOOLS, names
            repo_status = await session.call_tool("repo_status", {})
            assert isinstance(repo_status.structured_content, dict)
            assert repo_status.structured_content.get("repo_root") == os.environ["REPO"]
            targets = await session.call_tool("validation_targets", {})
            assert isinstance(targets.structured_content, dict)
            assert isinstance(targets.structured_content.get("targets"), list)


anyio.run(smoke)
PY

printf 'PASS pocketlab-dev-mcp transport\n'
printf 'PASS tool contract: 4 tools\n'
printf 'PASS repo_status\n'
printf 'PASS validation_targets\n'
