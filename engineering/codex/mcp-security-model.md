# Pocket Lab Lite Codex MCP security model

## Trust boundary

`pocketlab-dev-mcp` is a local developer helper, not a Pocket Lab control plane. It does not expose arbitrary shell, SQL, SSH, Git mutation, NATS publishing, PM2 mutation, Tailscale mutation, Server Phone operations, invite issuance, release operations, or secrets.

`node_repl` and `cua_repl` are Desktop-managed and outside the repository-owned Pocket Lab MCP implementation.

## Enforced controls

- The server validates one Pocket Lab repository root before use.
- Every subprocess goes through one runner with `shell=False`, a verified fixed `cwd`, fixed argument vectors, target-specific timeouts, and captured exit status.
- MCP callers cannot provide a command, arguments, working directory, environment, revision, shell syntax, or script.
- `run_validation` resolves only an immutable allow-list. Unknown target IDs fail before subprocess execution.
- Child environments are reconstructed from a small safe variable list. Names associated with tokens, secrets, passwords, authorization, cookies, credentials, private keys, API keys, NATS credentials, or Tailscale authorization are not forwarded.
- Stdout and stderr are drained with independent 12 KiB caps (24 KiB total maximum), are redacted centrally, and report truncation.
- Every `Authorization:` header value is redacted regardless of authentication scheme. Common token, password, API key, cookie, NATS credential, Tailscale authorization, and private-key forms are also redacted. A redaction error returns only `[REDACTED]`.

## Human authorization boundary

The MCP does not grant authority for commits, pushes, merges, tags, releases, credential changes, destructive cleanup, live Server Phone actions, Termux production actions, or Desktop configuration edits. Those remain explicit human decisions under `AGENTS.md`.
