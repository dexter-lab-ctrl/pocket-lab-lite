# Playwright MCP validation

Install the isolated developer-only package, then validate its launcher and
stdio tool contract from the native WSL checkout:

```bash
scripts/dev/codex/setup_playwright_mcp.sh
bash -n scripts/dev/codex/setup_playwright_mcp.sh \
  scripts/dev/codex/run_playwright_mcp.sh \
  scripts/dev/codex/check_playwright_mcp.sh
scripts/dev/codex/check_playwright_mcp.sh
```

The check verifies Node 24.16.0, the exact pinned package, the official
executable, the repository browser resolver, and real stdio initialization with
the allow-listed navigation/snapshot/click/close tools. It also proves that the
upstream `browser_run_code_unsafe` tool is neither listed nor callable. It does not navigate a page,
contact the Server Phone, use credentials, or change application runtime state.

Desktop registration is machine-local and occurs only after repository checks:

```bash
codex mcp add playwright -- \
  /home/$USER/pocket-lab-lite/scripts/dev/codex/run_playwright_mcp.sh
```

After a Desktop restart, smoke only a mocked loopback Pocket Lab surface with a
single navigation, accessibility snapshot, safe tab navigation, second
snapshot, and browser close. Playwright Test remains the deterministic browser
qualification system; the MCP does not replace it.
