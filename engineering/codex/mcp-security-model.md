# Pocket Lab Lite Codex MCP security model

## Trust boundary

`pocketlab-dev-mcp` is a local developer helper, not a Pocket Lab control plane. It does not expose arbitrary shell, SQL, SSH, Git mutation, NATS publishing, PM2 mutation, Tailscale mutation, Server Phone operations, invite issuance, release operations, or secrets. Its Increment 3 Server Phone observation is restricted to policy-owned, fixed read-only argv through the opaque machine-owned `pocketlab-termux` alias.

`node_repl` and `cua_repl` are Desktop-managed and outside the repository-owned Pocket Lab MCP implementation.

## Enforced controls

- The server validates one Pocket Lab repository root before use.
- Every subprocess goes through one runner with `shell=False`, a verified fixed `cwd`, fixed argument vectors, target-specific timeouts, and captured exit status.
- MCP callers cannot provide a command, arguments, working directory, environment, revision, shell syntax, or script.
- `run_validation` resolves only an immutable allow-list. Unknown target IDs fail before subprocess execution.
- `diagnostic_summary` resolves only nine immutable semantic IDs. It accepts no command, args, cwd, env, path, URL, hostname, port, revision, shell, query, subject, or service-name field; unknown IDs fail before any subprocess execution.
- File-backed diagnostics read only fixed repository-relative generated contracts. Local `pm2_status` uses only fixed `pm2 jlist`. Server Phone `pm2_summary` and the live portion of `nats_health` use only fixed `ssh -o BatchMode=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 pocketlab-termux python3 -c <immutable projection>`. That projection invokes read-only `pm2 jlist` and emits only a bounded allow-list of process fields before output crosses SSH. `security_run_summary` uses only one fixed credential-free loopback GET for the existing read-only security summary. All use the same runner and redaction stack, project only bounded safe fields, and never return raw SSH output, PM2 environment, command data, credentials, scanner output, or identity paths.
- Child environments are reconstructed from a small safe variable list. Names associated with tokens, secrets, passwords, authorization, cookies, credentials, private keys, API keys, NATS credentials, or Tailscale authorization are not forwarded.
- Stdout and stderr are drained with independent 12 KiB caps (24 KiB total maximum), are redacted centrally, and report truncation.
- Every `Authorization:` header value is redacted regardless of authentication scheme. Common token, password, API key, cookie, NATS credential, Tailscale authorization, and private-key forms are also redacted. A redaction error returns only `[REDACTED]`.

## Human authorization boundary

The MCP does not grant authority for commits, pushes, merges, tags, releases, credential changes, destructive cleanup, live Server Phone actions, Termux production actions, or Desktop configuration edits. Those remain explicit human decisions under `AGENTS.md`.
