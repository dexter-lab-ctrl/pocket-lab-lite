---
title: "App, command, and workflow state"
description: "Stores canonical app current/action lifecycle and workflow command/current/event state."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# App, command, and workflow state

Stores canonical app current/action lifecycle and workflow command/current/event state.

## Why it exists

Stores canonical app current/action lifecycle and workflow command/current/event state.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:app-workflow-state` |
| Owner | Apps and workflows |
| Execution owner | app/workflow services |
| Data owner | SQLite |
| Recovery owner | Reconciliation |
| Runtime owner | workers |
| Runtime process | app/workflow services |
| Runtime platform | SQLite |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Stores canonical app current/action lifecycle and workflow command/current/event state.

## Inputs

- app lifecycle and workflow events

## Outputs

- app and workflow projections

## Health signals

- state revision

## Failure modes

- stale action
- orphan command

## Recovery behavior

- reconcile independently

## Evidence

- action lifecycle

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `App Catalog`
- depends_on: `SQLite control-plane store`
- depends_on: `app_action_lifecycle`
- depends_on: `app_current_state`
- depends_on: `workflow_current_state`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- recovers_with: `App installation failure`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `App lifecycle worker`
- depends_on: `Workflow execution`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/app-workflow-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
