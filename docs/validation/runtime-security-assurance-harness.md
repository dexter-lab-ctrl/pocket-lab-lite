# Runtime Security Assurance Harness

Status: `IMPLEMENTED` for the bounded server-owned assurance foundation, the
fixed DEV-PC toolchain, the approved live-runtime lane, the external 360-degree
Standard/Deep/Adversarial scenario projection, and the explicit Deep
orchestrator. The new Chromium/Caddy/runtime 360 adapters are `UNVALIDATED`
until an exact-revision DEV-PC + Server Phone qualification report records
their result; runtime qualification is `RUNTIME-VALIDATED` only when a
sanitized report from the target revision says so. The command-by-command
qualification record is in
[`runtime-security-assurance-qualification.md`](runtime-security-assurance-qualification.md).
Deep is explicit and resource-governed. Destructive recovery scenarios and
human identity ceremonies remain `OUT_OF_SCOPE` or `HUMAN_REVIEW_REQUIRED`.

> The Runtime Security Assurance Harness is not a generic remote shell.
>
> The Server Phone is a consumer/qualification target, never the development
> workspace.

Use the [Security Assurance Playbook](security-assurance/README.md) for current
operator procedures, the [reference catalogs](reference/command-catalog.md)
for source-checked commands/routes, and the
[historical qualification dossier](evidence-history/runtime-security-assurance-qualification.md)
for prior run evidence. This page is the canonical architecture and contract
overview.

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
command, argv, executable path, cwd, URL, host, port, NATS subject, scanner
flag, environment variable, template, wordlist, browser script, fixture path,
or filesystem path. The server selects every
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
| Assurance run | Suite registry maximum: Smoke 1200s, Standard 1800s, Deep 7200s, Adversarial 600s | Durable run lease is independent of the authenticating session |

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
| `security/assurance/tools.yaml` | Tool inventory, platform classification, version discovery, bounded execution defaults, resource class, capability, and fixed execution contracts |
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
| `smoke` | Fast critical boundary and readiness checks plus existing Quick Security | Normal bounded run; target 180 seconds, maximum 1200 seconds on the ARM64 qualification target, based on the latest observed 922-second Quick path |
| `standard` | Normal runtime qualification plus routine browser/session/network reality | Normal bounded phone run plus 18 fixed DEV-PC external scenarios; target 900 seconds, maximum 1800 seconds |
| `deep` | Extended manual qualification across browser, code, dependencies, provenance, Recovery evidence and host posture | Explicit-only phone run plus all 36 fixed external scenarios; target 3600 seconds, maximum 7200 seconds |
| `adversarial` | Reviewed hostile-origin, malformed-state, network-boundary and bounded resilience cases | Explicit qualification-only phone run plus 29 fixed DEV-PC external scenarios; no arbitrary target and no destructive operation |

Every registered scenario declares one of:

- `PASSIVE` — inspection or source/evidence analysis with no runtime mutation.
- `SAFE_ACTIVE` — fixed controlled requests without intentional persistent
  application mutation.
- `CONTROLLED_MUTATION` — not enabled by the current safe profiles; would
  require precondition, exact cleanup, and postcondition evidence.
- `DESTRUCTIVE_QUALIFICATION` — not enabled by the current safe profiles and
  remains subject to the existing destructive safeguards.

Smoke and Standard do not run Deep-only provenance work, Recovery mutations,
human identity ceremonies, uncontrolled load, public-network scans, LAN/Tailnet
peer scans, password attacks, or user-media scans. Standard may run the fixed
Chromium/Caddy runtime adapters, but it never receives a production Owner
credential or arbitrary browser script.

### 360-degree external scenario lanes

The phone-owned `scenarios` list and the DEV-PC `external_scenarios` list are
separate by design. Phone scenarios still execute through FastAPI →
NATS/JetStream → worker. External scenarios execute only in the fixed
`dev_pc_live_runtime`/deep-provenance lanes and correlate back to the same
canonical STRIDE/OWASP/AP/control IDs.

| Lane | Registered external scenarios | Primary perspective |
| --- | ---: | --- |
| Standard | 18 | real browser/PWA, CORS/CSRF boundary, WebSocket, proxy/TLS, device/recovery authorization posture, remote-access truth |
| Deep | 36 | every Standard/Adversarial perspective plus release/dependency/app provenance, backup/restore evidence, Android/Termux posture and deeper evidence integrity |
| Adversarial | 29 | hostile origin, malformed workflow, replay/reconnect contracts, bounded availability pressure, policy/approval/exception abuse |

`playwright-runtime` drives real Chromium only against the operator-approved
fixed Caddy identity and a repository-owned hostile loopback origin.
`pocketlab-runtime-360` performs fixed Caddy HTTPS/WSS, listener, TLS,
bounded-resilience, and provenance observations. Neither adapter accepts a
runtime target from the caller.

Some scenarios intentionally emit `NOT_ASSESSED` rather than pretending to
PASS when a safe disposable fixture does not yet exist. Examples include
production-equivalent Owner session revocation, virtual-WebAuthn application
identity, invite replay, NATS command replay, Recovery mutation, and
enterprise approval/exception fixtures. The existing direct-loopback harness
proof is not injected through Caddy because doing so would weaken the proxy
trust boundary being tested.

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
| testssl.sh | `IMPLEMENTED` fixed DEV-PC live-runtime adapter with the approved Caddy SNI/loopback target | Medium; Standard, Deep, Adversarial |
| Nuclei | `IMPLEMENTED` fixed DEV-PC live-runtime adapter with one checked-in safe template and no external interaction | Heavy; Standard, Deep, Adversarial |
| nmap | `IMPLEMENTED` fixed DEV-PC live-runtime adapter with the Pocket Lab-owned forwarded listener set only | Medium; Standard, Deep, Adversarial |
| OWASP ZAP | `IMPLEMENTED` bounded API baseline adapter with fixed route/target and output cap | Heavy; Deep, Adversarial |
| `playwright-runtime` | `IMPLEMENTED / UNVALIDATED` repository-owned real-Chromium adapter; fixed Caddy identity + fixed hostile origin; no credential injection | Medium; Standard, Deep, Adversarial live-runtime lane |
| `pocketlab-runtime-360` | `IMPLEMENTED / UNVALIDATED` repository-owned Caddy HTTPS/WSS, listener, TLS, bounded resilience and provenance adapter | Medium; Standard, Deep, Adversarial live-runtime lane |

The operator-owned DEV-PC tool manager promotes external scanner tools into a
fixed receipt-backed directory outside Git. Repository-owned
`playwright-runtime` and `pocketlab-runtime-360` adapters are checked in
place and are never promoted as scanner binaries or interpreter copies. `tools:install` uses only
source-owned package/release recipes, verifies pinned checksums where the
recipe provides them, rejects archive traversal, removes temporary archives,
and records the execution lane and provenance. `tools:check` reports every
registered tool as `READY`, `NOT_APPLICABLE`, or `FAILED`; Cosign is
`NOT_APPLICABLE` when this revision has no registered signed artifact. The
tool manager executes tools sequentially, runs Syft before its Grype consumer,
and never accepts caller-supplied commands, targets, templates, rules, or
environment values.

The live-runtime adapters are DEV-PC tools testing only the approved
Server-Phone tunnel. They are not phone-native execution and do not broaden
the target beyond the fixed Pocket Lab API, Caddy TLS/WSS identity, the fixed
hostile loopback browser origin, safe Nuclei template, or registered loopback
listener ports. Raw tool output is parsed in memory or
kept in bounded disposable files and is not promoted to canonical evidence.

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
| Key-bound bootstrap, session renewal, and reattachment | `RUNTIME-VALIDATED` — `PASS` | Disposable principal, signed sessions, same run ID, 5 current-run renewals, and sanitized worker correlation |
| Smoke | `RUNTIME-VALIDATED` — `PASS` | Run `assurance-332d5d5f5c1c41caa502abb0e55e297d` at `0cfe3978…`: FastAPI → NATS/JetStream → pocket-worker → Security path |
| Standard | `RUNTIME-VALIDATED` — `PASS` | Fixed qualification policy sync reached `current`; run `assurance-4feba106906246fcbdfa66811d59c2de` completed all 11 registered scenarios |
| Safe Adversarial | `RUNTIME-VALIDATED` — `PASS` | Run `assurance-2fc46c0dbc6e4277a96d31825f480d79` completed 6 registered scenarios and 10 fixed negative probes |
| Worker restart/resume | `RUNTIME-VALIDATED` — `PASS` | Fixed `worker_restart_once` recovered the same run/operation and advanced durable checkpoints without duplicate admission |
| NATS restart/recovery | `RUNTIME-VALIDATED` — `PASS` | Fixed `nats_restart_once` recovered NATS/JetStream/worker state; no stream or consumer mutation |
| OPA restart/recovery | `RUNTIME-VALIDATED` — `PASS` | Fixed `opa_restart_once` recovered OPA readiness and the same run correlation |
| Direct outage-window fail-closed probes | `IMPLEMENTED`; runtime status is established only by the exact final-head fault evidence | Fixed one-use OPA/NATS pause→probe→restore controls; automatic restoration and readiness/revision proof are required |

The detailed command/output ledger, sanitized tool results, exact runtime
identities, coverage matrices, and cleanup evidence are maintained in
[`runtime-security-assurance-qualification.md`](runtime-security-assurance-qualification.md).

## OPA revision gate

The historical Standard blocker was an intentional policy-integrity gate, not a
scanner failure: the active OPA revision did not match the repository
candidate, so `policy_source_update_pending` was returned.

The current qualification used the fixed, qualification-only
`security.assurance.policy_sync` operation. It accepts no policy text, path,
revision, role, target, or activation option. The supervisor reconciled the
repository Safety Rules; the sanitized source state became
`source_update_required=false` with active and known-good revision
`plr-5cd9702f5cea80ae1813013f9c169169`, and Standard preflight became
`ready`. No policy file was manually rewritten, and no Owner, test-auth, or
destructive gate was enabled (`RUNTIME-VALIDATED`).

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

The 360-degree expansion intentionally does not manufacture production human
credentials or silently automate destructive Recovery. Real Chromium,
hostile-origin, Caddy/WSS/TLS, fixed listener, route-discovery, bounded
concurrency/slow-client, and deep provenance contracts are implemented.
Authenticated Owner revocation, application-level virtual WebAuthn, invite
replay/misbinding, direct NATS command replay, Recovery replacement/restore,
Tailnet peer-side scans, Enterprise approval/exception mutation and
history-wide Gitleaks remain explicit `NOT_ASSESSED`, `PARTIAL`, or
human-review/fixed-fixture work until their server-owned disposable fixture is
present. The direct-loopback harness credential is never pushed through Caddy
to make these cases appear covered.

The fixed DEV-PC/CI manager executes Bandit, Gitleaks, pip-audit, npm audit,
Semgrep CE, OSV-Scanner, Syft, Grype, testssl.sh, Nuclei, nmap, bounded ZAP,
real Chromium through `playwright-runtime`, and the repository-owned
`pocketlab-runtime-360` adapter through fixed contracts; Cosign is reported
`NOT_APPLICABLE` when no signed artifact is registered. Those captures
do not prove native phone execution. Phone runtime qualification continues to
execute the installed worker-owned Security, Trivy/Lynis, OPA posture, fixed
harness boundary checks, and registered fault controls. Direct OPA/NATS outage
proof is provided only by the one-use pause→probe→restore controls and is
`RUNTIME-VALIDATED` only when the exact target revision report records it.

Human-only coverage is complete when the harness records
`HUMAN_REVIEW_REQUIRED`; that is not a deferred implementation. Each such
scenario must document the following review template:

| Required field | Content |
| --- | --- |
| Scenario / threat | The modeled human-governance action and threat |
| STRIDE / OWASP / AP | Applicable mappings from the canonical registries |
| Automation boundary | Why a synthetic machine must not perform the ceremony |
| Reviewer / evidence | Human reviewer role and bounded records to inspect |
| Pass / fail criteria | Explicit acceptance and rejection conditions |
| Residual risk | What remains after the manual review |

WebAuthn ceremonies, Enterprise membership/final-Owner governance, human
exception acceptance, and destructive Recovery authorization therefore remain
`HUMAN_REVIEW_REQUIRED` or `OUT_OF_SCOPE_FOR_PR_576`, without requiring unsafe
automation or blocking the assurance-harness implementation.

The current human-review-only AP scenarios have the following complete review
contracts. They are coverage classifications, not missing harness features:

| Scenario | Threat / mapping | Why automation is inappropriate | Human reviewer and bounded evidence | Pass / fail criteria | Residual risk |
| --- | --- | --- | --- | --- | --- |
| AP-09 — human identity and WebAuthn assurance misuse | Spoofing, Tampering, Elevation of Privilege; OWASP A01/A07 | A synthetic machine must not impersonate a physical user or complete a passkey ceremony | Identity/security reviewer inspects origin/RP binding, challenge purpose, signer counter, session audit, and step-up expiry | PASS only when the intended user completes the origin-bound ceremony and all bindings/audit records agree; FAIL on replay, wrong purpose/origin, counter regression, or unexplained authority | Human ceremony/social-engineering and authenticator recovery remain operational risks |
| AP-10 — Enterprise membership/final-Owner escalation | Tampering, Repudiation, Elevation of Privilege; OWASP A01/A07/A09 | Final-Owner and membership governance require an accountable human decision and cannot be delegated to the assurance principal | Enterprise Owner/security reviewer inspects membership history, independent approval, final-Owner invariant, authorization invalidation, and audit correlation | PASS when role changes are independently authorized, exact-scope, auditable, and final-Owner protection holds; FAIL on self-approval, stale membership, or role escalation | Governance/operator compromise remains outside synthetic qualification |
| AP-13 — approval and continuation integrity | Spoofing, Tampering, Repudiation, Elevation of Privilege; OWASP A01/A07/A08/A09 | Approval is a human control and the machine harness must not manufacture an approver or continuation consent | Rules reviewer inspects exact action/target/revision binding, approver eligibility, passkey step-up, one-use continuation, and retry audit | PASS when an eligible independent approver authorizes the exact request once and requester retry consumes only that continuation; FAIL on self-approval, replay, mismatch, or double-use | Human decision quality and availability remain residual risks |
| AP-14 — temporary-exception scope and expiry bypass | Tampering, Elevation of Privilege; OWASP A01/A08 | Exception acceptance changes operational policy and requires explicit human accountability | Security/Owner reviewer inspects catalog-only scope, exact app/device/human/policy revision, ≤60-minute expiry, revocation, and matching audit | PASS when scope is exact, bounded, unexpired, revocable, and independently accepted; FAIL on wildcard/global scope, expiry bypass, or reuse | Exception misuse remains a governed operational risk |

AP-08 Recovery replacement/restore mutation is separately classified
`OUT_OF_SCOPE_FOR_PR_576` for destructive qualification; its non-destructive
schema rollback rehearsal remains covered by the release-safety evidence.

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
