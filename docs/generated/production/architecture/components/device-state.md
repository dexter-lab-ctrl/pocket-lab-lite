---
title: "Enrollment and device lifecycle state"
description: "Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history."
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

# Enrollment and device lifecycle state

Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history.

![Enrollment and device lifecycle state mini architecture](../../../../assets/diagrams/production/components/device-state.light.svg#only-light)
![Enrollment and device lifecycle state mini architecture](../../../../assets/diagrams/production/components/device-state.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite |
| Started / runtime owner | lite_control_plane_store |
| Process owner | FastAPI / worker |
| Execution owner | Fleet domain |
| Data owner | SQLite |
| Recovery owner | Explicit retirement / repair |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- invite acceptance
- heartbeats
- health

## Outputs

- fleet projection

## Protocols

- SQLite

## Durable state

- device_enrollment_registry
- device_current_state
- device_health_current

## Health and readiness

- last seen
- health attention

## Evidence

- device lifecycle events

## Failure behavior

- offline
- stale

## Recovery behavior

- preserve enrollment
- rejoin/repair

## Connections

### Incoming

- Heartbeat, telemetry, and health publishers — updates device truth
- Invite and identity lifecycle — accepted enrollment
- NATS / JetStream — fleet events projected

### Outgoing

- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `device_enrollment_registry`
- `sqlite_table` — `device_current_state`
- `sqlite_table` — `device_health_current`
- `sqlite_table` — `device_recovery_history`

## Existing documentation

- [devices.md](../../devices.md)

## Related architecture views

- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
