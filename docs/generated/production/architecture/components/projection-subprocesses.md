---
title: "Projection subprocesses"
description: "Own CPU-heavy projection reconstruction and serialization outside the API process."
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

# Projection subprocesses

Own CPU-heavy projection reconstruction and serialization outside the API process.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/projection.svg" alt="" loading="lazy" decoding="async" /><span>Projection</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/projection-subprocesses.light.svg" aria-label="Open full-size Projection subprocesses mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/projection-subprocesses.light.svg" alt="Projection subprocesses mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/projection-subprocesses.dark.svg" alt="Projection subprocesses mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Projection subprocesses mini architecture. <a href="../../../../../assets/diagrams/production/components/projection-subprocesses.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Own CPU-heavy projection reconstruction and serialization outside the API process. |
| Primary inputs | Compact domain events |
| Primary outputs | Prepared projections, revision updates |
| Protocols / uses | IPC queue, SQLite |
| Evidence | projection generation diagnostics |

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
| Architecture icon | semantic-projection |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

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
