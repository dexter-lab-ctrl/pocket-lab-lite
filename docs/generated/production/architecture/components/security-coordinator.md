---
title: "Security scan coordinator"
description: "Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 70e1e3dd1be588ab4eada0a05875282ebd5daa117f0b647e4f50d7977fccef16
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Security scan coordinator

Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries.

![Security scan coordinator mini architecture](../../../../assets/diagrams/production/components/security-coordinator.light.svg#only-light)
![Security scan coordinator mini architecture](../../../../assets/diagrams/production/components/security-coordinator.dark.svg#only-dark)

The mini diagram deterministically collapses **1** additional connections.


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
