# Pocket Lab Lite Codex MCP architecture

## Status

`VERIFIED` for the checked-in Increment 1 repository implementation after its focused validation. Increment 2 extends that same server with bounded read-only developer diagnostics. Desktop registration and Increment 2 Desktop smoke remain `UNVALIDATED`. The MCP layer is a local developer-tool-plane capability. It is outside the Pocket Lab Lite runtime and does not add a FastAPI route, Caddy route, frontend dependency, NATS service, PM2 service, or device control path.

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

The final repository tool surface is exactly six tools. Diagnostics prefer existing generated contracts; they do not regenerate documentation, capture or promote runtime evidence, start services, make HTTP/SSH calls, or start scanners. `pm2_status` is limited to a fixed local `pm2 jlist` projection through the shared runner and excludes process environment and command data.
