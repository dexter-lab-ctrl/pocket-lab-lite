---
title: "Bounded queues and reconciliation"
description: "Bounds admission, coalesces low-value work, reconciles queue depth, and prevents unrelated lifecycle deletion."
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

# Bounded queues and reconciliation

Bounds admission, coalesces low-value work, reconciles queue depth, and prevents unrelated lifecycle deletion.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/bounded-reconciliation.light.svg" aria-label="Open full-size Bounded queues and reconciliation mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/bounded-reconciliation.light.svg#only-light" alt="Bounded queues and reconciliation mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/bounded-reconciliation.dark.svg#only-dark" alt="Bounded queues and reconciliation mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Bounded queues and reconciliation mini architecture. <a href="../../../../../assets/diagrams/production/components/bounded-reconciliation.light.svg">View full-size diagram</a></figcaption>
</figure>


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | FastAPI and worker processes |
| Started / runtime owner | pocket-api / pocket-worker |
| Process owner | queue owners |
| Execution owner | Schedulers and stores |
| Data owner | SQLite lifecycle state |
| Recovery owner | Reconciliation loops |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Events
- dirty signals

## Outputs

- Bounded work batches

## Protocols

- In-process queue
- IPC queue
- SQLite

## Durable state

- projection_dirty_signals

## Health and readiness

- queue capacity
- deadline counters

## Evidence

- drop/coalesce/queue metrics

## Failure behavior

- queue pressure
- orphan state

## Recovery behavior

- coalesce
- transactional reconciliation

## Connections

### Incoming

- None declared

### Outgoing

- bounds and schedules — Projection subprocesses

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/projection_scheduler.py`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py`

## Existing documentation

- [projection-catalog.md](../../../development/projection-catalog.md)

## Related architecture views

- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
