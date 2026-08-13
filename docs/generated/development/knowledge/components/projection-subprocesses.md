---
title: "Projection subprocesses"
description: "Own CPU-heavy projection reconstruction and serialization outside the API process."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Projection subprocesses

Own CPU-heavy projection reconstruction and serialization outside the API process.

## Why it exists

Own CPU-heavy projection reconstruction and serialization outside the API process.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:projection-subprocesses` |
| Owner | Prepared projections |
| Execution owner | projection scheduler |
| Data owner | SQLite prepared projections |
| Recovery owner | Projection scheduler |
| Runtime owner | pocket-api and subprocesses |
| Runtime process | projection scheduler |
| Runtime platform | Dedicated subprocesses / scheduler |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Own CPU-heavy projection reconstruction and serialization outside the API process.

## Inputs

- Compact domain events

## Outputs

- Prepared projections
- revision updates

## Health signals

- generation/committed_generation
- queue depth

## Failure modes

- pressure deferral
- subprocess exit

## Recovery behavior

- serve last committed
- restart and reconcile

## Evidence

- projection generation diagnostics

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Audit index, projection refresh, prepared projections, and domain revisions`
- depends_on: `projection_dirty_signals`
- depends_on: `projection_refresh_state`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- publishes: `pocketlab.commands`
- related_to: `pocketlab.commands.unknown`
- verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Bounded queues and reconciliation`
- depends_on: `Workflow execution`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/projection-subprocesses.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/projection_scheduler.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/workflow_projection_process.py`
