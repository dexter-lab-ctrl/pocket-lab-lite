---
title: "Audit index, projection refresh, prepared projections, and domain revisions"
description: "Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions."
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

# Audit index, projection refresh, prepared projections, and domain revisions

Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions.

![Audit index, projection refresh, prepared projections, and domain revisions mini architecture](../../../../assets/diagrams/production/components/prepared-state.light.svg#only-light)
![Audit index, projection refresh, prepared projections, and domain revisions mini architecture](../../../../assets/diagrams/production/components/prepared-state.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite |
| Started / runtime owner | scheduler / subprocesses |
| Process owner | projection services |
| Execution owner | Projection subsystem |
| Data owner | SQLite |
| Recovery owner | Projection reconciliation |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- domain revisions
- evidence

## Outputs

- prepared API reads

## Protocols

- SQLite

## Durable state

- projection_refresh_state
- domain_revisions

## Health and readiness

- dirty
- committed_generation

## Evidence

- generation diagnostics

## Failure behavior

- stale generation

## Recovery behavior

- rebuild affected domain
- serve last valid

## Connections

### Incoming

- Completion and audit evidence — indexes evidence
- Projection subprocesses — commits generation

### Outgoing

- prepared read — Prepared read, health, readiness, diagnostics, and evidence APIs
- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `audit_evidence_index`
- `sqlite_table` — `projection_refresh_state`
- `sqlite_table` — `domain_revisions`
- `sqlite_table` — `phase3b_current_state`

## Existing documentation

- [projection-catalog.md](../../../development/projection-catalog.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Frontend state ownership](../frontend-state.md)
- [Request and control flow](../request-control.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
