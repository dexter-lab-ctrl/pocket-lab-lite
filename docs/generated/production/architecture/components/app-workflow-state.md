---
title: "App, command, and workflow state"
description: "Stores canonical app current/action lifecycle and workflow command/current/event state."
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

# App, command, and workflow state

Stores canonical app current/action lifecycle and workflow command/current/event state.

![App, command, and workflow state mini architecture](../../../../assets/diagrams/production/components/app-workflow-state.light.svg#only-light)
![App, command, and workflow state mini architecture](../../../../assets/diagrams/production/components/app-workflow-state.dark.svg#only-dark)


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
