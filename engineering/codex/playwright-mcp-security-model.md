# Playwright MCP security model

`VERIFIED` repository configuration: Playwright MCP is developer tooling only;
it is not part of FastAPI, Caddy, NATS, PM2, a node agent, or the Server Phone.

The repository launcher uses the official `@playwright/mcp` package pinned to
`0.0.79`, Node 24.16.0 from WSL2 nvm, and the existing Pocket Lab external
browser resolver. It runs over stdio in headless, isolated-profile mode. Output
is constrained to the ignored `.pocketlab-dev/playwright-mcp` directory with a
64 MiB upstream output-eviction threshold.

The default command does not enable extension mode, CDP, a server port, a proxy,
unrestricted file access, permission grants, a storage state, a user-data
directory, saved sessions/traces/videos, or vision/PDF/devtools capabilities.
It does not block service workers, so PWA behavior remains representative.

The upstream core tool catalog also contains `browser_run_code_unsafe`. A small
repository-owned stdio protocol filter allow-lists only ordinary accessibility
navigation and interaction tools, hides non-allow-listed tools from discovery,
and rejects a direct call before it reaches the official server. This is a
transport guard, not a browser implementation.

The launcher configures loopback `allowed-origins` for local development
surfaces. This is defense in depth only: upstream documents that origin
allowlisting is not a complete browser network sandbox and does not govern
redirects. Developers must still treat MCP navigation as an authorized local
development action and must not use this configuration for Server Phone access
or production control-plane operations.
