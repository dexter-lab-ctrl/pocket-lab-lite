---
title: "Workflow execution"
description: "Coordinates multi-step workflow state through bounded event admission and process-isolated projection work."
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

# Workflow execution

Coordinates multi-step workflow state through bounded event admission and process-isolated projection work.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/workflow-execution.light.svg" aria-label="Open full-size Workflow execution mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/workflow-execution.light.svg#only-light" alt="Workflow execution mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/workflow-execution.dark.svg#only-dark" alt="Workflow execution mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Workflow execution mini architecture. <a href="../../../../../assets/diagrams/production/components/workflow-execution.light.svg">View full-size diagram</a></figcaption>
</figure>


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Worker / projection subprocess |
| Started / runtime owner | pocket-worker |
| Process owner | worker and workflow projection subprocess |
| Execution owner | Workflow engine |
| Data owner | SQLite workflow tables |
| Recovery owner | Workflow reconciliation |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Workflow events

## Outputs

- Workflow current state

## Protocols

- IPC queue
- SQLite

## Durable state

- workflow_current_state
- workflow_event_index

## Health and readiness

- projection subprocess health

## Evidence

- workflow state transitions

## Failure behavior

- projection lag
- subprocess exit

## Recovery behavior

- restart projection subprocess
- rebuild from journal

## Connections

### Incoming

- Worker process — executes multi-step work

### Outgoing

- updates workflow state — App, command, and workflow state
- emits compact projection events — Projection subprocesses
- records sanitized lifecycle — Completion and audit evidence

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/workflow_engine.py`
- `sqlite_table` — `workflow_current_state`

## Existing documentation

- [architecture.md](../../../development/architecture.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
