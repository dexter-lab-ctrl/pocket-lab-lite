---
title: "Workflow execution"
description: "Coordinates multi-step workflow state through bounded event admission and process-isolated projection work."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: f82d3e269a91212087e920fb458fe3869473b363b8e0a4874489074018141ec5
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Workflow execution

Coordinates multi-step workflow state through bounded event admission and process-isolated projection work.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/workflow.svg" alt="" loading="lazy" decoding="async" /><span>Workflow</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/workflow-execution.light.svg" aria-label="Open full-size Workflow execution mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/workflow-execution.light.svg" alt="Workflow execution mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/workflow-execution.dark.svg" alt="Workflow execution mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Workflow execution mini architecture. <a href="../../../../../assets/diagrams/production/components/workflow-execution.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Coordinates multi-step workflow state through bounded event admission and process-isolated projection work. |
| Primary inputs | Workflow events |
| Primary outputs | Workflow current state |
| Protocols / uses | IPC queue, SQLite |
| Evidence | workflow state transitions |

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
| Architecture icon | semantic-workflow |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

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
