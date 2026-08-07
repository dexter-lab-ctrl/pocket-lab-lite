---
title: "Enrollment and device lifecycle state"
description: "Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Enrollment and device lifecycle state

Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history.

## Why it exists

Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:device-state` |
| Owner | Fleet domain |
| Execution owner | FastAPI / worker |
| Data owner | SQLite |
| Recovery owner | Explicit retirement / repair |
| Runtime owner | lite_control_plane_store |
| Runtime process | FastAPI / worker |
| Runtime platform | SQLite |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history.

## Inputs

- invite acceptance
- heartbeats
- health

## Outputs

- fleet projection

## Health signals

- last seen
- health attention

## Failure modes

- offline
- stale

## Recovery behavior

- preserve enrollment
- rejoin/repair

## Evidence

- device lifecycle events

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Bootstrap artifacts are backend-generated and identity-guarded`
- depends_on: `SQLite control-plane store`
- depends_on: `device_current_state`
- depends_on: `device_enrollment_registry`
- depends_on: `device_health_current`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- recovers_with: `Device joining, waiting, or repairing`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Heartbeat, telemetry, and health publishers`
- depends_on: `Invite and identity lifecycle`
- depends_on: `NATS / JetStream`
- uses: `Add Device`
- uses: `Device bootstrap and enrollment`
- uses: `Remove Old Device`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/device-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
