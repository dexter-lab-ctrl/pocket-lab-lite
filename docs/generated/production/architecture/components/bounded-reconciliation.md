---
title: "Bounded queues and reconciliation"
description: "Bounds admission, coalesces low-value work, reconciles queue depth, and prevents unrelated lifecycle deletion."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 20bffc9aa51b0c5cedb30ae9e2be0a9cfb0925972f81f056d9792accd7d4e7ee
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Bounded queues and reconciliation

Bounds admission, coalesces low-value work, reconciles queue depth, and prevents unrelated lifecycle deletion.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/decision.svg" alt="" loading="lazy" decoding="async" /><span>Decision</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/bounded-reconciliation.light.svg" aria-label="Open full-size Bounded queues and reconciliation mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/bounded-reconciliation.light.svg" alt="Bounded queues and reconciliation mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/bounded-reconciliation.dark.svg" alt="Bounded queues and reconciliation mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Bounded queues and reconciliation mini architecture. <a href="../../../../../assets/diagrams/production/components/bounded-reconciliation.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Bounds admission, coalesces low-value work, reconciles queue depth, and prevents unrelated lifecycle deletion. |
| Primary inputs | Events, dirty signals |
| Primary outputs | Bounded work batches |
| Protocols / uses | In-process queue, IPC queue, SQLite |
| Evidence | drop/coalesce/queue metrics |

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
| Architecture icon | semantic-decision |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

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
