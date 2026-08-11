---
title: "Workflow execution"
description: "Coordinates multi-step workflow state through bounded event admission and process-isolated projection work."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Workflow execution

Coordinates multi-step workflow state through bounded event admission and process-isolated projection work.

## Why it exists

Coordinates multi-step workflow state through bounded event admission and process-isolated projection work.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:workflow-execution` |
| Owner | Workflow engine |
| Execution owner | worker and workflow projection subprocess |
| Data owner | SQLite workflow tables |
| Recovery owner | Workflow reconciliation |
| Runtime owner | pocket-worker |
| Runtime process | worker and workflow projection subprocess |
| Runtime platform | Worker / projection subprocess |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Coordinates multi-step workflow state through bounded event admission and process-isolated projection work.

## Inputs

- Workflow events

## Outputs

- Workflow current state

## Health signals

- projection subprocess health

## Failure modes

- projection lag
- subprocess exit

## Recovery behavior

- restart projection subprocess
- rebuild from journal

## Evidence

- workflow state transitions

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `App, command, and workflow state`
- depends_on: `Completion and audit evidence`
- depends_on: `Projection subprocesses`
- depends_on: `workflow_current_state`
- depends_on: `workflow_event_index`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- publishes: `pocketlab.commands`
- publishes: `pocketlab.commands.operation.execute`
- publishes: `pocketlab.events.workflow.replay_requested`
- related_to: `pocketlab.commands.unknown`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Worker process`
- uses: `App installation`
- uses: `Confirmed restore`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/workflow-execution.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/workflow_engine.py`
