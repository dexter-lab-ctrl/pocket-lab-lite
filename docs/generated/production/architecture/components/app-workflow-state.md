---
title: "App, command, and workflow state"
description: "Stores canonical app current/action lifecycle and workflow command/current/event state."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 13dae80367ddf3ba183f4f77c57075516b1e463d27336c7aa834c23b5cce75a2
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# App, command, and workflow state

Stores canonical app current/action lifecycle and workflow command/current/event state.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/app-workflow-state.light.svg" aria-label="Open full-size App, command, and workflow state mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/app-workflow-state.light.svg#only-light" alt="App, command, and workflow state mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/app-workflow-state.dark.svg#only-dark" alt="App, command, and workflow state mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>App, command, and workflow state mini architecture. <a href="../../../../../assets/diagrams/production/components/app-workflow-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Stores canonical app current/action lifecycle and workflow command/current/event state. |
| Primary inputs | app lifecycle and workflow events |
| Primary outputs | app and workflow projections |
| Protocols / uses | SQLite |
| Evidence | action lifecycle |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite |
| Started / runtime owner | workers |
| Process owner | app/workflow services |
| Execution owner | Apps and workflows |
| Data owner | SQLite |
| Recovery owner | Reconciliation |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-state |

## Inputs

- app lifecycle and workflow events

## Outputs

- app and workflow projections

## Protocols

- SQLite

## Durable state

- app_current_state
- app_action_lifecycle
- workflow_current_state

## Health and readiness

- state revision

## Evidence

- action lifecycle

## Failure behavior

- stale action
- orphan command

## Recovery behavior

- reconcile independently

## Connections

### Incoming

- App lifecycle worker — updates app state
- Workflow execution — updates workflow state

### Outgoing

- catalog/action projection — App Catalog
- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `app_current_state`
- `sqlite_table` — `app_action_lifecycle`
- `sqlite_table` — `workflow_current_state`
- `sqlite_table` — `workflow_command_state`

## Existing documentation

- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
