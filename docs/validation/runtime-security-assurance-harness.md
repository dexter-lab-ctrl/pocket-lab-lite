# Runtime Security Assurance Harness

Status: `IMPLEMENTED` for the bounded server-owned assurance foundation;
runtime qualification is `RUNTIME-VALIDATED` only when a sanitized report from
the target revision says so. Deep scanners, destructive recovery scenarios,
and human identity ceremonies remain `DEFERRED` or `HUMAN_REVIEW_REQUIRED`.

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

It has no destructive capability and no generic equivalent of shell/process,
arbitrary filesystem, arbitrary network, arbitrary NATS, host mutation, or
Owner authority. Unknown capabilities, profiles, purposes, targets, scenarios,
and suites fail closed.

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
| `smoke` | Fast critical boundary and readiness checks plus existing Quick Security | Normal bounded run; target 180 seconds, maximum 600 seconds |
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
The status below describes this repository’s supported integration, not proof
that a particular Server Phone has every binary installed.

| Tool or path | Runtime status | Resource / suite |
| --- | --- | --- |
| `pocketlab-security` | `VERIFIED` existing worker-owned path | Heavy; Smoke, Standard, Deep |
| Lynis | `VERIFIED` native when discovered by existing Security | Heavy; Smoke, Standard, Deep |
| Trivy | `VERIFIED` native when discovered by existing Security | Heavy; Smoke, Standard, Deep |
| Bandit | `DEFERRED` version inventory only | Medium; Standard, Deep |
| Gitleaks | `DEFERRED` version inventory only; raw matches never persisted | Medium; Smoke, Standard, Deep |
| pip-audit | `DEFERRED` | Small; Standard, Deep |
| npm audit | `DEFERRED`; no network refresh in a reproducible run | Medium; Standard, Deep |
| OPA | `VERIFIED` fixed loopback readiness/revision posture | Small; Standard and selected adversarial checks |
| Schemathesis | `DEFERRED` compatibility lane; no promoted route allowlist | Heavy; Standard, Deep, Adversarial |
| Cosign | `DEFERRED` release workflow inventory only | Small; Standard, Deep |
| Semgrep CE | `DEFERRED` compatibility lane | Heavy; Standard, Deep |
| OSV-Scanner | `DEFERRED`; existing Trivy identity remains authoritative | Medium; Standard, Deep |
| Syft | `DEFERRED`; Trivy SBOM reuse is preferred | Heavy; Deep |
| Grype | `DEFERRED` secondary SBOM corroboration | Heavy; Deep |
| testssl.sh | `DEFERRED` until a fixed local TLS parser is promoted | Medium; Standard, Deep |
| Nuclei | `DEFERRED`; no arbitrary templates or targets | Heavy; Standard, Deep, Adversarial |
| nmap | `DEFERRED`; fixed local listener evidence is used instead | Heavy; Standard, Deep |
| OWASP ZAP | `DEFERRED` manual Deep-only candidate | Unbounded without a reviewed profile; Deep |

Deferred tools may be inventoried with a fixed version probe when their
registered suite includes them. That probe is not an assurance scan and does
not download binaries, update databases, or accept caller-supplied arguments.

## Admission and run lifecycle

Before a run is queued, FastAPI checks the exact target revision, clean
worktree, explicit qualification environment, enabled harness, disabled test
bypass/destructive/Owner gates, API `/health`, API `/ready`, Caddy health,
NATS, JetStream, worker process, resource facts, OPA when required, scanner
conflicts, and the fixed existing Security profile. PM2 `online` is recorded
separately and is never treated as API readiness.

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

The durable SQLite schema is migration `0035_security_assurance.sql` and
stores run, scenario, tool-result, and normalized finding rows. A finding has
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
GET  /api/lite/harness/security-assurance/runs/{run_id}/report
POST /api/lite/harness/security-assurance/runs/{run_id}/cancel
```

The request body accepts only a registered `suite_id`, optional registered
`scenario_id`, and an optional same-principal baseline run ID. The CLI and
Taskfile expose `check`, `preflight`, `smoke`, `standard`, `deep`,
`adversarial`, `scenario`, `report`, and `compare`. There is no `COMMAND=` or
arbitrary command fallback.

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
4. Start the explicit qualification profile with the existing
   `scripts/dev/lite/start-qualification.sh` contract. Keep test bypass,
   destructive, and qualification-owner flags off.
5. Create the private Ed25519 key on the approved client in a `0600` file
   outside Git. Register only the public principal through the supported
   provisioning path and request a short-lived assurance session.
6. Run Smoke, inspect the sanitized report, and run Standard only when the
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
or failed atomic evidence write prevents a clean `PASS`. The existing Security
service remains responsible for scanner checkpoint/resume and its own
reconciliation.

The current safe increment intentionally does not automatically execute
Recovery replacement/restore mutation, OPA outage injection, worker-kill
fault injection, Tailnet/LAN scans, browser WebAuthn ceremonies, Enterprise
membership/final-Owner scenarios, arbitrary API fuzzing, ZAP, Nuclei,
Semgrep, Syft, Grype, or history-wide Gitleaks. These remain
`DEFERRED`, `STATIC_EVIDENCE_ONLY`, or `HUMAN_REVIEW_REQUIRED` until each has
a reviewed fixed target/parser/resource/cleanup contract.

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
