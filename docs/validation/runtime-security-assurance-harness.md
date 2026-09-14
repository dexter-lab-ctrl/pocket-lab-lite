# Runtime Security Assurance Harness

Status: `IMPLEMENTED` for the bounded server-owned assurance foundation and
the fixed DEV-PC supply-chain lane; runtime qualification is
`RUNTIME-VALIDATED` only when a sanitized report from the target revision
says so. The command-by-command qualification record is in
[`runtime-security-assurance-qualification.md`](runtime-security-assurance-qualification.md).
Deep scanners, destructive recovery scenarios, and human identity ceremonies
remain `DEFERRED` or `HUMAN_REVIEW_REQUIRED`.

> The Runtime Security Assurance Harness is not a generic remote shell.
>
> The Server Phone is a consumer/qualification target, never the development
> workspace.

This is an operator and qualification surface for the actual Pocket Lab Lite
runtime. It is not exposed in the PWA, does not add a user navigation item,
and does not replace the existing Security, Recovery, Identity, Rules, health,
release, or monitoring controls.

## Purpose and boundaries

The harness connects the canonical threat model to controlled evidence:

```text
security/threat-model-scenarios.json
    -> registered scenario and invariant
    -> signed least-privilege admission
    -> FastAPI preflight
    -> NATS/JetStream command
    -> worker-owned registered execution
    -> normalized sanitized evidence
    -> durable result and report
    -> STRIDE / OWASP / AP-* coverage and delta
```

The target is always `local_server_host_only`. Callers cannot provide a shell
command, argv, executable path, cwd, URL, port, NATS subject, scanner flag,
environment variable, template, or filesystem path. The server selects every
execution detail from the checked-in registry and existing Security service.

The normal edge-first architecture remains authoritative:

```text
approved machine client
    -> direct loopback harness API
    -> FastAPI authorization and preflight
    -> NATS / JetStream
    -> pocket-worker
    -> existing Security or fixed assurance probe
    -> SQLite and sanitized evidence
    -> FastAPI report API
```

The frontend never connects to NATS or executes a process. FastAPI remains the
control API. Workers, agents, and supervisors retain execution and recovery
ownership. The harness does not expose SSH or create a second control plane.

## Authentication and authorization

The existing synthetic-principal harness is extended with the least-privileged
`security-assurance-runner` profile. Its lifecycle is:

```text
public Ed25519 key registration
    -> single-use signed challenge
    -> short-lived session
    -> server-owned profile and capabilities
    -> fixed target and purpose checks
    -> normal FastAPI / OPA / worker boundaries
```

Only the public key and a fingerprint are registered. SQLite stores a session
token hash, never the raw token. Private keys must remain on the approved
client, outside Git, SQLite, logs, reports, MCP output, and model context.
The principal is synthetic and cannot become a human identity, Enterprise
member, or Owner. `qualification-owner` remains a separate exceptional
profile with its existing gates and is not granted to this runner.

The assurance profile has these capabilities:

`security.assurance.run`, `read`, `cancel`, `passive`, `sast`, `sca`, `api`,
`runtime`, `threat_scenario`, `report`, and `baseline`.

The profile also has the narrowly scoped `security.assurance.cleanup`
capability. It may revoke only its own bootstrap-created principal; it cannot
revoke another principal or use the provisioning path. It has no destructive
capability and no generic equivalent of shell/process,
arbitrary filesystem, arbitrary network, arbitrary NATS, host mutation, or
Owner authority. Unknown capabilities, profiles, purposes, targets, scenarios,
and suites fail closed.

## Key-bound operator bootstrap

For automated qualification, the preferred path is an operator-approved
key-bound bootstrap. The operator starts qualification with the public-key file
and the fixed `security-assurance-runner` profile:

```text
operator starts qualification
    -> server records principal id + public-key fingerprint in process state
    -> server issues one ephemeral five-minute bootstrap grant
    -> client requests a challenge and signs the exact canonical payload
    -> FastAPI verifies key, runtime, revision, profile, purpose, target, and gates
    -> one synthetic assurance principal and one normal session are created atomically
```

The grant is process-ephemeral, one-use, revision/runtime/key bound, and is not
a bearer provisioning secret. API restart invalidates unconsumed grants. The
legacy `POCKETLAB_HARNESS_PROVISIONING_TOKEN` registration path remains for
explicit manual compatibility, but it is not required by the key-bound
qualification client and is never printed or placed in evidence.

The four lifetimes are intentionally independent:

| Object | Default / bound | Expiry or revocation behavior |
| --- | --- | --- |
| Bootstrap grant | 5 minutes, exactly one use | Ephemeral; consumed or expired grants cannot be reused |
| Synthetic principal | 12 hours, bounded to 1–24 hours | Natural expiry blocks new sessions/runs; explicit revocation cancels active assurance work |
| Authentication session | 20 minutes, bounded to 1–60 minutes | Expiry immediately removes request authority; it does not terminate an admitted run |
| Assurance run | Suite registry maximum: Smoke 600s, Standard 1800s, Deep 7200s, Adversarial 600s | Durable run lease is independent of the authenticating session |

The client renews by issuing a new signed challenge/session before the current
session expires. It never extends or persists a raw token. A local continuity
record at `~/.pocketlab-qualification/runtime-security-assurance.json` contains
only the principal/fingerprint, key-file path, run ID, suite/scenario,
runtime/revision identity, and last event sequence. The raw session token is
held only in process memory.

## Server-owned registries

These canonical registries are the only selectable assurance vocabulary:

| File | Ownership |
| --- | --- |
| `security/assurance/tools.yaml` | Tool inventory, platform classification, version discovery, bounded execution defaults, resource class, capability, and deferred status |
| `security/assurance/suites.yaml` | Smoke, Standard, Deep, and Adversarial admission and resource budgets |
| `security/assurance/scenarios.yaml` | Executable invariant definitions and STRIDE/OWASP/control/AP relationships |
| `security/threat-model-scenarios.json` | Canonical STRIDE model and every current `AP-*` entry |

Registry validation rejects duplicate IDs, unsafe targets, non-assurance
capabilities, unknown scenario references, invalid safety classes, and any
current attack path that is not classified. The reported registry hashes make
the tested vocabulary revision-bound and reproducible.

## Profiles and safety classes

| Profile | Intended use | Default policy |
| --- | --- | --- |
| `smoke` | Fast critical boundary and readiness checks plus existing Quick Security | Normal bounded run; target 180 seconds, maximum 900 seconds on the ARM64 qualification target |
| `standard` | Normal runtime qualification and coverage | Normal bounded run; target 900 seconds, maximum 1800 seconds |
| `deep` | Extended manual qualification | Explicit-only; target 3600 seconds, maximum 7200 seconds |
| `adversarial` | Reviewed fixed local adversarial cases | Explicit qualification-only; no destructive operation |

Every registered scenario declares one of:

- `PASSIVE` — inspection or source/evidence analysis with no runtime mutation.
- `SAFE_ACTIVE` — fixed controlled requests without intentional persistent
  application mutation.
- `CONTROLLED_MUTATION` — not enabled by the current safe profiles; would
  require precondition, exact cleanup, and postcondition evidence.
- `DESTRUCTIVE_QUALIFICATION` — not enabled by the current safe profiles and
  remains subject to the existing destructive safeguards.

Smoke and Standard do not run Deep-only tools, Recovery mutations, human
identity ceremonies, uncontrolled load, public-network scans, LAN/Tailnet
peer scans, password attacks, or user-media scans.

## Toolchain

The harness reuses the existing worker-owned Quick/Full/App Security path and
its cache, SBOM, exclusion, resource, checkpoint, and evidence contracts.
The runtime registry and the DEV-PC/CI supply-chain lane are deliberately
separate. The runtime status below describes the fixed tools that the worker
can execute on a Server Phone; the static/supply-chain status describes the
fixed, sanitized capture performed on the DEV PC. Neither lane accepts caller
arguments or arbitrary targets.

| Tool or path | Runtime status | Resource / suite |
| --- | --- | --- |
| `pocketlab-security` | `VERIFIED` existing worker-owned path | Heavy; Smoke, Standard, Deep |
| Lynis | `VERIFIED` native when discovered by existing Security | Heavy; Smoke, Standard, Deep |
| Trivy | `VERIFIED` native when discovered by existing Security | Heavy; Smoke, Standard, Deep |
| Bandit | `IMPLEMENTED` fixed DEV-PC/CI Python SAST capture; not a phone worker tool | Medium; Standard, Deep static lane |
| Gitleaks | `IMPLEMENTED` fixed bounded DEV-PC/CI current-tree capture; raw matches never persisted | Medium; Standard, Deep static lane |
| pip-audit | `IMPLEMENTED` fixed DEV-PC/CI dependency corroboration | Small; Standard, Deep static lane |
| npm audit | `IMPLEMENTED` fixed production package-lock audit; no network refresh in a reproducible run | Medium; Standard, Deep static lane |
| OPA | `VERIFIED` fixed loopback readiness/revision posture | Small; Standard and selected adversarial checks |
| Schemathesis | `IMPLEMENTED` fixed parity/compatibility lane; live runtime requires the approved loopback tunnel | Heavy; Standard, Deep, Adversarial static/runtime lane |
| Cosign | `IMPLEMENTED` release-only provenance/version check; no signed artifact is invented when absent | Small; Standard, Deep release lane |
| Semgrep CE | `IMPLEMENTED` fixed checked-in architecture rules on DEV PC/CI; not phone-native | Heavy; Standard, Deep static lane |
| OSV-Scanner | `IMPLEMENTED` fixed source/lockfile corroboration; unranked dev candidates remain visible | Medium; Standard, Deep static lane |
| Syft | `IMPLEMENTED` fixed bounded source/release SBOM capture; phone prefers Trivy SBOM reuse | Heavy; Deep static lane |
| Grype | `IMPLEMENTED` fixed Syft-SBOM vulnerability corroboration | Heavy; Deep static lane |
| testssl.sh | `DEFERRED` until a fixed local TLS parser is promoted | Medium; Standard, Deep |
| Nuclei | `DEFERRED`; no arbitrary templates or targets | Heavy; Standard, Deep, Adversarial |
| nmap | `UNSUPPORTED` on the current qualification target; fixed local listener evidence is retained instead | Heavy; Standard, Deep |
| OWASP ZAP | `DEFERRED` manual Deep-only candidate | Unbounded without a reviewed profile; Deep |

Deferred tools may be inventoried with a fixed version probe when their
registered suite includes them. That probe is not an assurance scan and does
not download binaries, update databases, or accept caller-supplied arguments.

The DEV-PC capture records installation origin, pinned version, checksum or
signature posture, fixed argv, bounded output, parser status, and sanitized
findings. A tool is not described as native Server Phone execution merely
because its DEV-PC binary exists. Missing Android/Termux binaries are
reported as `MISSING` or `UNSUPPORTED` with the exact reason in the
qualification dossier.

## Current qualification evidence

The continuation qualification record is intentionally split between
source/toolchain evidence and live Android/Termux evidence:

| Area | Current status | Evidence boundary |
| --- | --- | --- |
| Schema 35/36 rollback | `RUNTIME-VALIDATED` — `VERIFIED SAFE` | Disposable local-port Android/Termux-class sandbox only; no live database or Recovery API was touched |
| Key-bound bootstrap, session renewal, and reattachment | `RUNTIME-VALIDATED` — `PASS` | Disposable principal, signed sessions, same run ID, 8 final-run renewals, and sanitized worker correlation |
| Smoke | `RUNTIME-VALIDATED` — `PASS` | Final run `assurance-6a0fe6b1960f488fb83cfdba95ad57e4` at `a0937b30…`: FastAPI → NATS/JetStream → pocket-worker → Security path |
| Standard | `BLOCKED` | OPA correctly held the active policy revision at `policy_source_update_pending`; Owner-confirmed source synchronization is required |
| Safe Adversarial | `NOT_RUN` as a suite | Standard admission gate remained blocked; unit coverage and safe Smoke boundary probes remain separate evidence |
| Worker restart/resume | `UNVALIDATED` on the phone | Durable heartbeat/checkpoint behavior is covered by focused tests; no supported bounded phone fault procedure was available |
| NATS interruption/recovery | `UNVALIDATED` on the phone | No supported bounded outage procedure was available without inventing infrastructure mutation |
| OPA interruption/fail-closed | `UNVALIDATED` on the phone | Healthy OPA posture was observed; no supported bounded outage procedure was available |

The detailed command/output ledger, sanitized tool results, exact runtime
identities, coverage matrices, and cleanup evidence are maintained in
[`runtime-security-assurance-qualification.md`](runtime-security-assurance-qualification.md).

## OPA revision gate

The Standard blocker is an intentional policy-integrity gate, not a scanner
failure. The durable active and known-good policy revision on the Server Phone
was `plr-57572c06b39bbecb75cd9dddeee620c7`, while the published feature source
prepared a different candidate revision. The active stage also did not contain
the feature’s `harness_test.rego`. OPA was healthy and served the active
revision, but the policy consistency check therefore returned
`policy_source_update_pending` and blocked Standard.

The supported source-sync path requires the existing human/Owner assurance
operation and supervisor reconciliation. No Owner credential was available
for this qualification, so no policy state was bypassed or rewritten and no
test-auth or qualification-owner gate was enabled. Standard remains
`BLOCKED` until an operator performs that approved synchronization and the
active revision is reverified.

## Non-destructive schema rollback rehearsal

The forward-only migration contract was rehearsed in an isolated disposable
sandbox on the Android/Termux-class target. A compatible old-main database
with migrations 1–34 was integrity-checked and copied immutably. The feature
runtime applied migrations 35 and 36, producing migrations 1–36 with clean
`integrity_check`, `quick_check`, and foreign-key checks. After the feature
runtime stopped, only the sandbox database was replaced by the preserved
pre-upgrade copy; the old runtime then started on the restored database and
passed health/readiness with migrations 1–34 intact.

This proves the repository-supported Model A contract:

```text
forward-only application/database upgrade
    -> verified compatible pre-upgrade database copy
    -> prior application revision
    -> healthy/readiness/integrity checks
```

It is `RUNTIME-VALIDATED` and `VERIFIED SAFE` for the isolated rehearsal, not
permission to roll back production state. No production database, Recovery
repository, user media, or destructive Recovery API was used.

## Admission and run lifecycle

Before a run is queued, FastAPI checks the exact target revision, clean
worktree, explicit qualification environment, enabled harness, disabled test
bypass/destructive/Owner gates, API `/health`, API `/ready`, Caddy health,
NATS, JetStream, worker process, resource facts, OPA when required, scanner
conflicts, and the fixed existing Security profile. PM2 `online` is recorded
separately and is never treated as API readiness.

The PM2 admission probe uses a fixed status-only query. It does not call
`pm2 jlist`, because that command includes process environments. Long-lived
Security SSE responses are admitted through a bounded header probe so a stream
that remains open is not mistaken for an unhealthy endpoint.

An unsatisfied precondition produces `BLOCKED`; it is not converted into a
security finding or a false pass. A run is `PASS`, `FAIL`, `PARTIAL`, or
`BLOCKED` based on scenario invariants, active tool status, finding policy,
cancellation, and evidence/report durability. Launching a process alone is
never a pass condition. A high/critical open finding or failed invariant fails
the suite; incomplete or medium finding results are reported as `PARTIAL`.

The request is persisted before publication and contains only a fixed command
envelope. The worker consumes the fixed assurance subject and calls the
registered runner. Redelivered terminal commands are acknowledged without
re-execution. A worker, NATS, API, timeout, or resource interruption cannot be
silently converted to `PASS`.

When an assurance run invokes the existing Quick Security path, the worker
passes the persisted assurance deadline to that path. Each scanner child is
bounded by the remaining run lease and uses the existing process-group cleanup;
post-deadline scanner work is recorded as partial and is not allowed to turn a
late result into `PASS`. The ownership probe also requires a live NATS,
JetStream, and durable worker-consumer posture; a configuration flag alone is
not treated as execution proof.

Each admitted run has a durable admission key, deadline, worker identity,
heartbeat, progress sequence, and checkpoint generation. Repeated admission of
the same principal/suite/scenario/runtime/revision returns the existing active
run ID without publishing a duplicate scanner command. Completed successful
scenario checkpoints are reused. A stale heartbeat or interrupted unit is
reconciled to `PARTIAL` and can be resumed only from a registered retry-safe,
resume-supported checkpoint. A non-retry-safe unit remains for manual review.
Client disconnect, session expiry, and reauthentication do not create a new
run. Explicit principal revocation marks active runs for cancellation; the
worker then terminates its owned process group and records a truthful terminal
result.

## Reports and findings

Reports are written under the runtime state directory, never into the Git
checkout by default:

```text
security/assurance/<run-id>/
  manifest.json
  environment.json
  toolchain.json
  findings.json
  threat-coverage.json
  owasp-coverage.json
  attack-path-results.json
  controls.json
  delta.json
  performance.json
  sanitization.json
  checksums.json
  summary.md
```

The durable SQLite schema uses migration `0035_security_assurance.sql` for the
assurance domain and migration `0036_assurance_execution_lifecycle.sql` for
the durable run lease/checkpoint state. It stores run, scenario, tool-result,
checkpoint, and normalized finding rows. A finding has
a stable key and includes severity, confidence, component, asset, trust
boundary, STRIDE categories, OWASP 2021 IDs where applicable, attack paths,
controls, CWE/CVE identifiers when safely available, remediation, bounded
evidence references, runtime target, and baseline state.

Baseline states are `NEW`, `EXISTING`, `RESOLVED`, `REGRESSED`, and
`UNCHANGED`. Baselines are restricted to the same suite, selected scenario,
and admitting synthetic principal. The report separates tool execution status
from scenario status and finding delta so an incomplete scanner is not
mistaken for a clean result.

The primary framework is STRIDE. OWASP Top 10 2021 is a reference mapping,
not a replacement for the canonical threat model. All current `AP-01` through
`AP-14` paths are classified as `EXECUTABLE_NOW`, `PARTIALLY_EXECUTABLE`,
`STATIC_EVIDENCE_ONLY`, `HUMAN_REVIEW_REQUIRED`, or `OUT_OF_SCOPE`. Static and
human-review classifications are coverage bookkeeping, not automatic risk
acceptance or exploitability decisions.

## Resource governance

The assurance layer delegates heavy scanning to existing Security resource and
cache policy. It also enforces one active assurance run, one heavy scanner at
a time, fixed local targets, bounded HTTP responses, fixed version probes,
bounded report sizes, and process-group cleanup for its own probes. Existing
Trivy database/SBOM and revision-bound cache reuse remains authoritative.

The report records sanitized available memory, free storage, battery/charging,
temperature, and load facts when the platform supplies them. Android values
that cannot be measured are left unavailable; a fallback is not presented as
measured data. Resource stop, timeout, cancellation, or scanner degradation is
`PARTIAL` or `BLOCKED`, never a false `PASS`.

## Redaction and exclusions

All durable reports, audit summaries, command envelopes, and returned reports
pass through the existing security redaction policy. The harness never stores
or returns private keys, raw session/provisioning tokens, passwords, hashes,
API keys, cookies, CSRF values, Authorization headers, NATS credentials,
Tailscale auth keys, recovery encryption material, raw secret matches, raw
scanner output, user media, PhotoPrism media, or backup payload contents.

The existing Security exclusion policy remains in force for Android shared
storage, PhotoPrism media/cache/log areas, runtime state, large caches, and
other excluded paths. Source-boundary checks inspect only bounded Git-tracked
frontend source and fixed repository files; they do not traverse runtime or
user storage.

## API and CLI

The operator API is direct-loopback-only and uses the existing signed harness
session. Its bounded surface is:

```text
GET  /api/lite/harness/security-assurance/capabilities
GET  /api/lite/harness/security-assurance/suites
GET  /api/lite/harness/security-assurance/preflight?suite_id=smoke
POST /api/lite/harness/security-assurance/runs
GET  /api/lite/harness/security-assurance/runs
GET  /api/lite/harness/security-assurance/runs/{run_id}
GET  /api/lite/harness/security-assurance/runs/{run_id}/findings
GET  /api/lite/harness/security-assurance/runs/{run_id}/events?after=0
POST /api/lite/harness/security-assurance/runs/{run_id}/resume
GET  /api/lite/harness/security-assurance/runs/{run_id}/report
POST /api/lite/harness/security-assurance/runs/{run_id}/cancel
```

The request body accepts only a registered `suite_id`, optional registered
`scenario_id`, and an optional same-principal baseline run ID. The CLI and
Taskfile expose `check`, `preflight`, `smoke`, `standard`, `deep`,
`adversarial`, `scenario`, `report`, `compare`, and the bounded `qualify`
workflow. The harness client also exposes `keygen` and `bootstrap`; their
output recursively removes session tokens, signatures, challenge payloads,
nonces, and other secret-shaped fields. There is no `COMMAND=` or arbitrary
command fallback.

## Caddy boundary

Caddy strips every known qualification and harness proof header on API,
health, readiness, Security SSE, WebSocket, OpenAPI, docs, and ReDoc proxy
handlers. The fixed Caddy scenario sends forged markers through the Caddy
listener and expects the assurance endpoint to remain unauthenticated. A
valid signed assurance session is accepted only on the direct loopback API
path, after the same target/profile/purpose checks.

The proxy assertion is runtime evidence only when the listener is actually
probed on the target. A source/header inspection is labelled `UNVALIDATED`
with respect to a live Caddy process.

## Server Phone qualification procedure

All source and Git authoring happens on the DEV PC. The Server Phone only
fetches and consumes an already-published revision for qualification.

1. On the DEV PC, record `origin/main`, create the feature branch, validate,
   and publish the exact feature commit.
2. On the Server Phone, record `git rev-parse HEAD`,
   `git status --short --branch`, PM2, and bounded health/readiness facts.
3. Fetch and consume only the published feature commit using the established
   Lite deployment procedure. Do not edit source or create development Git
   state on the phone.
4. Create the private Ed25519 key on the approved client in a `0600` file
   outside Git. Copy or otherwise provide only its public key to the operator.
5. Start the explicit qualification profile with
   `--bootstrap-principal-id`, `--bootstrap-public-key-file`, and the fixed
   `--bootstrap-profile security-assurance-runner`. Keep test bypass,
   destructive, and qualification-owner flags off. The server-side launcher
   records only the fingerprint and does not accept a private key.
6. Run the bounded `security_assurance.py qualify` workflow. It performs the
   key proof, authenticated preflight, Smoke, automatic renewal/reattachment,
   and cleanup. Inspect the sanitized report, and run Standard only when the
   resource guard and operator review allow it. Deep and Adversarial require
   explicit qualification intent.
7. If a source defect is found, preserve sanitized evidence, return to the
   DEV PC, add a regression test and targeted fix, publish the new commit, and
   rerun against that exact revision. Never patch the phone checkout.
8. Revoke temporary sessions/principals as appropriate, stop qualification,
   restore normal startup, verify all dangerous flags are off, and prove the
   phone worktree is clean.

The final report must distinguish `VERIFIED` source facts,
`RUNTIME-VALIDATED` phone observations, `BLOCKED` infrastructure gates,
`PARTIAL` execution, and `UNVALIDATED` or `DEFERRED` scope. A local test or
MCP response is not evidence of live Android/Termux behavior.

## Failure recovery and limitations

FastAPI, worker, NATS, scanner, timeout, and resource interruptions remain
visible in the durable lifecycle. NATS/JetStream redelivery uses the existing
worker path; a terminal assurance row is not re-executed. An incomplete report
or failed atomic evidence write prevents a clean `PASS`. API startup and worker
startup reconcile stale run leases; a fresh heartbeat means execution may
continue, while a stale heartbeat becomes `PARTIAL` and never `PASS`. The
client can reauthenticate and reattach to the same run ID after a disconnect.
Authentication session expiry does not terminate an already admitted Security
Assurance run. Explicit principal revocation is stronger: it marks active runs
for safe cancellation and prevents new sessions/runs.

The current safe increment intentionally does not automatically execute
Recovery replacement/restore mutation, OPA outage injection, worker-kill
fault injection, Tailnet/LAN scans, browser WebAuthn ceremonies, Enterprise
membership/final-Owner scenarios, arbitrary API fuzzing, ZAP, Nuclei,
testssl.sh, or history-wide Gitleaks. Fixed DEV-PC/CI captures now execute
Bandit, Gitleaks, pip-audit, npm audit, Semgrep CE, OSV-Scanner, Syft, Grype,
OPA checks/tests, and release provenance checks where the required artifact
exists. Those captures do not prove native phone execution. Phone runtime
qualification remains limited to the installed worker-owned Security,
Trivy/Lynis, OPA posture, and fixed harness boundary checks; the remaining
items are `DEFERRED`, `STATIC_EVIDENCE_ONLY`, `UNSUPPORTED`, or
`HUMAN_REVIEW_REQUIRED` until a reviewed fixed target/parser/resource/cleanup
contract and supported runtime procedure exist.

Use these local checks without enabling qualification or changing runtime
state:

```bash
task lite:security:assurance:check
PYTHONPATH="$PWD/pocket-lab-final-structure/runtime" \
  python3 -m py_compile \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_assurance.py
task lite:docs:check
```

The Server Phone is a consumer/qualification target, never the development
workspace. Runtime status is established only by the exact sanitized report
and the before/after consumer-only evidence for that phone.
