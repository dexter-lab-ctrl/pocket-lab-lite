---
title: "Security scan coordinator"
description: "Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 13dae80367ddf3ba183f4f77c57075516b1e463d27336c7aa834c23b5cce75a2
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Security scan coordinator

Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/security-coordinator.light.svg" aria-label="Open full-size Security scan coordinator mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/security-coordinator.light.svg#only-light" alt="Security scan coordinator mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/security-coordinator.dark.svg#only-dark" alt="Security scan coordinator mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Security scan coordinator mini architecture. <a href="../../../../../assets/diagrams/production/components/security-coordinator.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **1** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries. |
| Primary inputs | Scan request |
| Primary outputs | run state, compact summary |
| Protocols / uses | HTTP JSON, NATS, SQLite |
| Evidence | scan lifecycle |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | FastAPI and worker |
| Started / runtime owner | pocket-api / pocket-worker |
| Process owner | security services |
| Execution owner | Security domain |
| Data owner | SQLite Security state |
| Recovery owner | Security maintenance / worker recovery |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-security |

## Inputs

- Scan request

## Outputs

- run state
- compact summary

## Protocols

- HTTP JSON
- NATS
- SQLite

## Durable state

- security_scan_runs

## Health and readiness

- progress
- freshness

## Evidence

- scan lifecycle

## Failure behavior

- worker start timeout
- scanner timeout

## Recovery behavior

- consumer recovery
- terminal recovery

## Connections

### Incoming

- Worker process — runs security work

### Outgoing

- runs bounded plan — Lynis and Trivy scanner adapters
- selects Quick/Full/App — Quick, Full, and App safety checks
- updates scan state — Security findings and run state
- records sanitized lifecycle — Completion and audit evidence

## Source verification

- `route` — `POST /api/lite/security/check`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py`

## Existing documentation

- [security.md](../../security.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Security and safety](../security.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
