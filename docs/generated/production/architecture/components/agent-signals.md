---
title: "Heartbeat, telemetry, and health publishers"
description: "Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 765d187cae484a494c7f2602216f3c7ab49cafc2bdffd1ea1b8900f7d1e8e672
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Heartbeat, telemetry, and health publishers

Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/event.svg" alt="" loading="lazy" decoding="async" /><span>Event</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/android.svg" alt="" loading="lazy" decoding="async" /><span>Android</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/pm2.svg" alt="" loading="lazy" decoding="async" /><span>PM2</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/terminal.svg" alt="" loading="lazy" decoding="async" /><span>Terminal runtime</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/agent-signals.light.svg" aria-label="Open full-size Heartbeat, telemetry, and health publishers mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/agent-signals.light.svg" alt="Heartbeat, telemetry, and health publishers mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/agent-signals.dark.svg" alt="Heartbeat, telemetry, and health publishers mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Heartbeat, telemetry, and health publishers mini architecture. <a href="../../../../../assets/diagrams/production/components/agent-signals.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states. |
| Primary inputs | Local runtime samples |
| Primary outputs | heartbeat, telemetry, health |
| Protocols / uses | NATS |
| Evidence | device health events |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | event |
| Runs on | Node agent |
| Started / runtime owner | node agent |
| Process owner | node agent |
| Execution owner | Device runtime |
| Data owner | Server SQLite projections |
| Recovery owner | Reconnect watchdog |
| Security boundary | Managed-device boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-event |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-android, brand-pm2, brand-python, semantic-terminal |

## Inputs

- Local runtime samples

## Outputs

- heartbeat
- telemetry
- health

## Protocols

- NATS

## Durable state

- device_heartbeats
- device_health_current

## Health and readiness

- signal freshness

## Evidence

- device health events

## Failure behavior

- signal stale

## Recovery behavior

- fresh publish after reconnect

## Connections

### Incoming

- Lite node agent — publishes

### Outgoing

- updates device truth — Enrollment and device lifecycle state
- heartbeat/telemetry/health — NATS / JetStream

## Source verification

- `nats_subject` — `pocketlab.events.fleet.node_heartbeat`
- `path` — `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`

## Existing documentation

- [devices.md](../../devices.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
