# 5. Bootstrap and authentication

The qualification identity is disposable, key-bound, target-scoped, and
short-lived. The machine never receives a general-purpose provisioning bearer
credential through this workflow.

## Key custody

**[APPROVED CLIENT / DEV PC]** Generate with the existing client:

```bash
task lite:harness:keygen KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.key
```

The private key is raw Ed25519 material, mode `0600`, outside the repository.
The public key is written separately and the command prints only its bounded
fingerprint and file modes. Keep both paths out of Git, SQLite, audit events,
logs, reports, MCP arguments, and model context. The phone operator may stage
the public key through the approved qualification-start workflow; never copy
the private key to the phone repository.

## Operator-approved bootstrap

**[SERVER PHONE / operator]** Use the key-bound qualification task:

```bash
task lite:qualification:start:key-bound \
  PRINCIPAL_ID=codex-security-assurance \
  PUBLIC_KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.pub
```

The launcher fixes `security-assurance-runner`, qualification environment,
`security.assurance`, local-server scope, and all dangerous flags off. The
optional `task lite:qualification:start:key-bound:faults` task additionally
enables the fixed one-use non-destructive fault registry and should be used
only for the fault playbook.

## Proof flow

The approved client uses the current `harness.py bootstrap` implementation:

```text
operator startup approval
  → process-ephemeral five-minute one-use grant
  → grant-bound bootstrap challenge
  → exact server-issued signing payload
  → Ed25519 possession proof
  → synthetic qualification principal
  → normal short-lived harness session
```

The grant binds principal ID, public key/fingerprint, profile, purpose,
target, runtime identity, and revision. Completion verifies all bindings,
direct loopback transport, no forwarded/proxy markers, qualification mode,
and dangerous flags before atomically consuming the grant and issuing the
normal session. Bootstrap events record bounded context only; they do not
record the private key, signature, nonce, payload, or token.

The older provisioning-token path remains available for explicit/manual
compatibility. Its value must never be placed in documentation or automated
client output. The key-bound path is the recommended machine-client flow.

## Four independent lifetimes

| Object | Current policy | Consequence |
| --- | --- | --- |
| Bootstrap grant | process-ephemeral, five minutes, one use | API restart invalidates unused grants; consumed grants cannot replay |
| Synthetic principal | default 12 hours; bounded 1–24-hour policy | natural expiry denies new sessions/runs; it is not an Owner identity |
| Auth session | default 20 minutes; bounded 60-minute maximum | expiry immediately removes authority for new control requests |
| Assurance run | suite-owned durable deadline: Smoke 1200s, Standard 1800s, Deep 7200s, Adversarial 600s | run ownership continues independently after admission |

Core principle: **short authentication leases; long durable execution leases**.

## Session renewal and reattachment

The qualification client renews before expiry using a fresh server challenge
and a fresh signature. It never extends or serializes a raw token. The old
session expires naturally and may be garbage-collected later. Session expiry
does not terminate an already admitted run: the run continues under its own
deadline, worker operation, heartbeat, and checkpoint state. A restarted
client reauthenticates and reads the continuity record to reattach to the same
`run_id`; it must not submit a duplicate.

Explicit session revocation affects only that session. Explicit principal
revocation is emergency containment: it prevents new sessions/runs, marks
active runs for cancellation, and lets the worker terminate safely with a
truthful terminal state.

## Direct client commands

The bounded client can also expose these server-owned operations:

```bash
task lite:harness:status
task lite:harness:profiles
task lite:security:assurance:preflight SUITE=smoke
```

These commands require no raw credential in the documentation. Where an
authenticated operation is invoked manually, the approved client must keep
`POCKETLAB_HARNESS_SESSION` only in process memory; do not export or persist a
token as a convenience.

## Using the harness from Codex or another machine client

A machine client may inspect the repository, generate its Ed25519 key outside
Git, show the public fingerprint, use operator-approved bootstrap, authenticate
with a short-lived session, run registered suites/scenarios/fault controls,
read sanitized reports, renew sessions, reattach to an existing run, and clean
up authority it created.

A machine client may not request Owner authority, borrow human credentials,
supply arbitrary commands/targets/scanner options, publish NATS messages,
scan unrelated networks, perform destructive Recovery, read secret contents,
or edit tracked source on the Server Phone. FastAPI remains the control API and
the worker remains the execution owner.
