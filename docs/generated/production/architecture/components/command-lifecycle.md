---
title: "Command admission and lifecycle"
description: "Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle."
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

# Command admission and lifecycle

Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/workflow.svg" alt="" loading="lazy" decoding="async" /><span>Workflow</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/command-lifecycle.light.svg" aria-label="Open full-size Command admission and lifecycle mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/command-lifecycle.light.svg" alt="Command admission and lifecycle mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/command-lifecycle.dark.svg" alt="Command admission and lifecycle mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Command admission and lifecycle mini architecture. <a href="../../../../../assets/diagrams/production/components/command-lifecycle.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle. |
| Primary inputs | Accepted command, worker status |
| Primary outputs | Lifecycle events, terminal state |
| Protocols / uses | NATS, SQLite |
| Evidence | queued/claimed/running/terminal |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | FastAPI and worker |
| Started / runtime owner | pocket-api / pocket-worker |
| Process owner | FastAPI and worker |
| Execution owner | Command lifecycle |
| Data owner | SQLite command_lifecycle |
| Recovery owner | Reconciliation |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-workflow |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- Accepted command
- worker status

## Outputs

- Lifecycle events
- terminal state

## Protocols

- NATS
- SQLite

## Durable state

- command_lifecycle

## Health and readiness

- queue depth
- stale command count

## Evidence

- queued/claimed/running/terminal

## Failure behavior

- orphaned command
- redelivery

## Recovery behavior

- reconcile without deleting device
- terminal redelivery protection

## Connections

### Incoming

- Worker process — claims and updates

### Outgoing

- records sanitized lifecycle — Completion and audit evidence

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/action_queue.py`
- `sqlite_table` — `command_lifecycle`
- `nats_subject` — `pocketlab.events.command.succeeded`

## Existing documentation

- [lite-events.md](../../../development/lite-events.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Request and control flow](../request-control.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
