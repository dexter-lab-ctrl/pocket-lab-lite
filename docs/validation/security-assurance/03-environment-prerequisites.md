# 3. Environment prerequisites

Use this page before authentication or a suite. A failed prerequisite is an
honest `BLOCKED` result, not a security finding.

## DEV PC

**[DEV PC]** Verify:

- the candidate is the exact reviewed/published SHA;
- the working tree is clean apart from explicitly preserved user-owned files;
- the repository virtual environment and approved Node toolchain are usable;
- the tool manager's fixed receipts are available;
- free disk space is sufficient for the selected lane and transient files;
- only approved local/loopback tunnel targets are configured;
- no private key, session token, provisioning token, or user data is under the
  repository.

Run the static checks without starting the phone runtime:

```bash
git status --short --branch
git rev-parse HEAD
task lite:security:assurance:check
task lite:security:assurance:tools:check
```

## Server Phone

**[SERVER PHONE]** Confirm before admission:

```bash
git status --short --branch
git rev-parse HEAD
pm2 status
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/ready
```

The phone must be a consumer of a published revision. A clean worktree is
required before and after qualification. Do not use `pm2 jlist` in a report or
chat transcript because it can expose process environments.

## Qualification gates

The key-bound startup path must have these effective values:

| Gate | Required value |
| --- | --- |
| Environment | `qualification` |
| Harness | enabled only for the explicit window |
| Harness destructive | off |
| Qualification Owner | off |
| Test-auth bypass | off |
| Bootstrap profile | `security-assurance-runner` only |
| Purpose | `security.assurance` |
| Target | `local_server_host_only` |
| Principal class | qualification |
| Transport | direct loopback; no forwarded/proxy markers |

The normal production launcher must reject harness authority. See [16 —
default-off verification](16-cleanup-default-off.md).

## Runtime readiness

Smoke requires health/readiness, NATS/JetStream, worker availability, and the
existing Security path. Standard and Deep additionally require current OPA
policy readiness and the fixed DEV-PC tool receipts for their selected lanes.
The preflight response identifies the exact blocker and registry hashes; do
not infer readiness from a process list.

## Scope exclusions

The assurance source and tool manager exclude PhotoPrism/user media, Android
shared storage, backup payload contents, runtime state that is not in the
registered source scope, generated/cache paths covered by existing exclusion
policy, unrelated hosts, and arbitrary network ranges. If a tool cannot honor
the registered exclusions, mark it `FAILED` or `UNSUPPORTED`; do not broaden
its target.
