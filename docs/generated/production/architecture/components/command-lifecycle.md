---
title: "Command admission and lifecycle"
description: "Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle."
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

# Command admission and lifecycle

Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/command-lifecycle.light.svg" aria-label="Open full-size Command admission and lifecycle mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/command-lifecycle.light.svg#only-light" alt="Command admission and lifecycle mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/command-lifecycle.dark.svg#only-dark" alt="Command admission and lifecycle mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Command admission and lifecycle mini architecture. <a href="../../../../../assets/diagrams/production/components/command-lifecycle.light.svg">View full-size diagram</a></figcaption>
</figure>


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
- [Request and control flow](../request-control.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
