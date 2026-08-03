---
title: "Projection subprocesses"
description: "Own CPU-heavy projection reconstruction and serialization outside the API process."
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

# Projection subprocesses

Own CPU-heavy projection reconstruction and serialization outside the API process.

![Projection subprocesses mini architecture](../../../../assets/diagrams/production/components/projection-subprocesses.light.svg#only-light)
![Projection subprocesses mini architecture](../../../../assets/diagrams/production/components/projection-subprocesses.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Dedicated subprocesses / scheduler |
| Started / runtime owner | pocket-api and subprocesses |
| Process owner | projection scheduler |
| Execution owner | Prepared projections |
| Data owner | SQLite prepared projections |
| Recovery owner | Projection scheduler |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Compact domain events

## Outputs

- Prepared projections
- revision updates

## Protocols

- IPC queue
- SQLite

## Durable state

- projection_refresh_state
- projection_dirty_signals

## Health and readiness

- generation/committed_generation
- queue depth

## Evidence

- projection generation diagnostics

## Failure behavior

- pressure deferral
- subprocess exit

## Recovery behavior

- serve last committed
- restart and reconcile

## Connections

### Incoming

- Bounded queues and reconciliation — bounds and schedules
- Workflow execution — emits compact projection events

### Outgoing

- commits generation — Audit index, projection refresh, prepared projections, and domain revisions

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/workflow_projection_process.py`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/projection_scheduler.py`
- `sqlite_table` — `projection_refresh_state`

## Existing documentation

- [projection-catalog.md](../../../development/projection-catalog.md)

## Related architecture views

- [Runtime and PM2 process topology](../runtime-topology.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
