---
title: "Enrollment and device lifecycle state"
description: "Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history."
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

# Enrollment and device lifecycle state

Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/durable-state.svg" alt="" loading="lazy" decoding="async" /><span>Durable state</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/device-state.light.svg" aria-label="Open full-size Enrollment and device lifecycle state mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/device-state.light.svg" alt="Enrollment and device lifecycle state mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/device-state.dark.svg" alt="Enrollment and device lifecycle state mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Enrollment and device lifecycle state mini architecture. <a href="../../../../../assets/diagrams/production/components/device-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Retains enrolled devices across connectivity loss and separates durable enrollment, current state, health, supervisor state, and recovery history. |
| Primary inputs | invite acceptance, heartbeats, health |
| Primary outputs | fleet projection |
| Protocols / uses | SQLite |
| Evidence | device lifecycle events |

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
| Architecture icon | semantic-durable-state |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

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

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
