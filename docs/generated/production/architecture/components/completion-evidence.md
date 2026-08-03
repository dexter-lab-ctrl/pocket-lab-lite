---
title: "Completion and audit evidence"
description: "Records sanitized lifecycle and completion evidence for commands, devices, apps, security, recovery, and releases."
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

# Completion and audit evidence

Records sanitized lifecycle and completion evidence for commands, devices, apps, security, recovery, and releases.

![Completion and audit evidence mini architecture](../../../../assets/diagrams/production/components/completion-evidence.light.svg#only-light)
![Completion and audit evidence mini architecture](../../../../assets/diagrams/production/components/completion-evidence.dark.svg#only-dark)

The mini diagram deterministically collapses **4** additional connections.


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | event |
| Runs on | Worker and FastAPI |
| Started / runtime owner | worker / FastAPI |
| Process owner | domain owners |
| Execution owner | Evidence services |
| Data owner | SQLite evidence index and sanitized files |
| Recovery owner | Owning domain |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Lifecycle results

## Outputs

- Sanitized evidence summaries

## Protocols

- SQLite
- JSON files
- NATS events

## Durable state

- audit_evidence_index

## Health and readiness

- evidence index consistency

## Evidence

- self-describing evidence

## Failure behavior

- evidence write failure

## Recovery behavior

- fail action truthfully
- retry bounded write

## Connections

### Incoming

- Device command executor — records sanitized lifecycle
- App lifecycle worker — records sanitized lifecycle
- Backup and verification engine — records sanitized lifecycle
- Command admission and lifecycle — records sanitized lifecycle
- Release subprocess — records sanitized lifecycle
- Security scan coordinator — records sanitized lifecycle
- Workflow execution — records sanitized lifecycle

### Outgoing

- indexes evidence — Audit index, projection refresh, prepared projections, and domain revisions
- sanitized lookup — Prepared read, health, readiness, diagnostics, and evidence APIs

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_evidence_receipts.py`
- `sqlite_table` — `audit_evidence_index`

## Existing documentation

- [redaction-coverage.md](../../../development/redaction-coverage.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Audit and evidence flow](../audit-evidence.md)
- [Backup and restore](../backup-recovery.md)
- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)
- [Release subprocess and atomic rollback](../release-rollback.md)
- [Request and control flow](../request-control.md)
- [Security and safety](../security.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
