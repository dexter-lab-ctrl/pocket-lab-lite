# Pocket Lab Lite Codex MCP architecture

## Status

`VERIFIED` for the checked-in Increment 1 repository implementation after its focused validation. Increment 2 extends that same server with bounded read-only developer diagnostics. Increment 3 adds bounded read-only Server Phone observation through the existing machine-owned `pocketlab-termux` SSH alias. Desktop registration and Desktop smoke remain `UNVALIDATED`. The MCP layer is a local developer-tool-plane capability. It is outside the Pocket Lab Lite runtime and does not add a FastAPI route, Caddy route, frontend dependency, NATS service, PM2 service, or device control path.

```text
Codex Desktop
  → WSL Codex agent
  → stdio pocketlab-dev-mcp
  → bounded local repository and validation tooling
```

The production control plane remains:

```text
React/Vite PWA → Caddy → FastAPI /api/lite/* → NATS / JetStream
→ worker / node agent / supervisor → sanitized evidence → FastAPI reads → UI
```

## Ownership

- Repository source: `tools/mcp/pocketlab_dev/`.
- Repository launcher and transport check: `scripts/dev/codex/`.
- Local dependency environment: `.pocketlab-dev/mcp/venv` (ignored and disposable).
- Desktop registration and transport selection: machine-local Codex configuration; it is not owned by this repository.

The server runs only over stdio. It validates the configured repository root for `.git`, `AGENTS.md`, and `engineering/codex` before registering meaningful operations.

## Playwright MCP companion

`@playwright/mcp` is a separate developer-only browser MCP. It is not added to
the six-tool `pocketlab_dev` surface and does not alter the Pocket Lab runtime.

```text
Codex Desktop
  ├── pocketlab_dev → bounded repository and diagnostic tooling
  └── playwright → repository launcher → pinned WSL2 Node → external browser
```

The repository launcher is `scripts/dev/codex/run_playwright_mcp.sh`. It uses
the existing `scripts/dev/lite/resolve-browser.mjs` resolver, a pinned isolated
developer installation under `.pocketlab-dev/mcp/playwright`, and stdio.

## Tool contract

Exactly these four semantic tools are registered:

| Tool | Purpose | Inputs |
| --- | --- | --- |
| `repo_status` | Compact local Git state | none |
| `changed_files` | Classified changed paths | `scope`: `working_tree` or `branch_vs_origin_main` |
| `validation_targets` | Ordered validation allow-list | none |
| `run_validation` | One fixed validation target | `target`: allow-listed identifier |

Increment 2 adds exactly these two read-only diagnostic tools to the same server:

| Tool | Purpose | Inputs |
| --- | --- | --- |
| `diagnostic_targets` | Ordered immutable diagnostic allow-list | none |
| `diagnostic_summary` | One bounded diagnostic summary | `target`: allow-listed identifier |

The final repository tool surface is exactly six tools. Increment 3 extends the immutable diagnostic catalog to nine IDs: the existing seven plus `pm2_summary` and `security_run_summary`. `pm2_status` remains a local WSL2 `pm2 jlist` projection. `pm2_summary` is the distinct Server Phone Pocket Lab PM2 projection: its fixed remote Python projection runs read-only `pm2 jlist` and returns only bounded Pocket Lab process fields before the payload crosses SSH. `nats_health` combines that fixed Server Phone PM2 projection (when available) with promoted repository readiness evidence. `security_summary` remains repository-generated supply-chain evidence, while `security_run_summary` makes only a fixed credential-free loopback request to the existing read-only Server Phone security summary and reports unavailable if protected evidence cannot be read. No diagnostic accepts a host, command, argument, URL, path, process name, credential, or environment input; no scanner is started.
