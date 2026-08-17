---
title: "OPA Safety Rules policy engine"
description: "Evaluates only registered protected actions after FastAPI hard invariants and before existing NATS/worker execution; it never owns command execution."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 765d187cae484a494c7f2602216f3c7ab49cafc2bdffd1ea1b8900f7d1e8e672
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# OPA Safety Rules policy engine

Evaluates only registered protected actions after FastAPI hard invariants and before existing NATS/worker execution; it never owns command execution.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/decision.svg" alt="" loading="lazy" decoding="async" /><span>Decision</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/decision.svg" alt="" loading="lazy" decoding="async" /><span>Decision</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/opa-policy-engine.light.svg" aria-label="Open full-size OPA Safety Rules policy engine mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/opa-policy-engine.light.svg" alt="OPA Safety Rules policy engine mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/opa-policy-engine.dark.svg" alt="OPA Safety Rules policy engine mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>OPA Safety Rules policy engine mini architecture. <a href="../../../../../assets/diagrams/production/components/opa-policy-engine.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Evaluates only registered protected actions after FastAPI hard invariants and before existing NATS/worker execution; it never owns command execution. |
| Primary inputs | bounded FastAPI authorization input |
| Primary outputs | allow/deny/constraints/reason code/policy revision |
| Protocols / uses | Loopback HTTP JSON, Rego |
| Evidence | bounded authorization decision metadata |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | decision |
| Runs on | Server host loopback |
| Started / runtime owner | PM2 |
| Process owner | pocket-opa |
| Execution owner | Rules authorization |
| Data owner | Repository Rego source and bounded SQLite policy decision metadata |
| Recovery owner | Startup validation and PM2 core supervisor |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | patch-provided |
| Architecture icon | semantic-decision |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python, semantic-decision |

## Inputs

- bounded FastAPI authorization input

## Outputs

- allow/deny/constraints/reason code/policy revision

## Protocols

- Loopback HTTP JSON
- Rego

## Durable state

- policy_decisions

## Health and readiness

- loopback /health
- engine version
- active policy revision
- last decision

## Evidence

- bounded authorization decision metadata

## Failure behavior

- OPA unavailable
- OPA timeout
- invalid decision
- policy activation validation failure

## Recovery behavior

- fail closed
- preserve last-known-good policy
- restart only after validated activation

## Connections

### Incoming

- Fleet, Apps, Security, Recovery, and Release APIs — evaluates registered protected action

### Outgoing

- returns allow/deny/constraints/reason code — Fleet, Apps, Security, Recovery, and Release APIs

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_opa.py`
- `path` — `security/policies/opa/pocketlab/pocketlab.rego`
- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/prepare-opa-policy.sh`
- `pm2_process` — `pocket-opa`
- `route` — `GET /api/lite/policy`
- `sqlite_table` — `policy_decisions`

## Existing documentation

- [rules.md](../../rules.md)
- [security-boundaries.md](../../security-boundaries.md)

## Related architecture views

- None

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
