---
title: "Command admission and lifecycle"
description: "Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Command admission and lifecycle

Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle.

## Why it exists

Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:command-lifecycle` |
| Owner | Command lifecycle |
| Execution owner | FastAPI and worker |
| Data owner | SQLite command_lifecycle |
| Recovery owner | Reconciliation |
| Runtime owner | pocket-api / pocket-worker |
| Runtime process | FastAPI and worker |
| Runtime platform | FastAPI and worker |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Tracks admission, queued, claimed, running, terminal, acknowledgement, retry, and dead-letter behavior independently from device lifecycle.

## Inputs

- Accepted command
- worker status

## Outputs

- Lifecycle events
- terminal state

## Health signals

- queue depth
- stale command count

## Failure modes

- orphaned command
- redelivery

## Recovery behavior

- reconcile without deleting device
- terminal redelivery protection

## Evidence

- queued/claimed/running/terminal

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Completion and audit evidence`
- depends_on: `command_lifecycle`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- publishes: `pocketlab.commands.operation.execute`
- publishes: `pocketlab.commands.runbook.approve`
- publishes: `pocketlab.commands.runbook.execute`
- publishes: `pocketlab.commands.runbook.reject`
- publishes: `pocketlab.events.operation.created`
- publishes: `pocketlab.events.runbook.approval_queued`
- publishes: `pocketlab.events.runbook.queued`
- publishes: `pocketlab.events.runbook.rejection_queued`
- related_to: `pocketlab.events.command.queued`
- related_to: `pocketlab.events.command.succeeded`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Worker process`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/command-lifecycle.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/action_queue.py`
