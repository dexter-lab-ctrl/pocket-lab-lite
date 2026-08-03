---
title: "Heartbeat, telemetry, and health publishers"
description: "Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states."
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

# Heartbeat, telemetry, and health publishers

Publish fresh runtime signals used to derive Online, Offline, Stale, Agent stopped, and Remote access not ready states.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/agent-signals.light.svg" aria-label="Open full-size Heartbeat, telemetry, and health publishers mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/agent-signals.light.svg#only-light" alt="Heartbeat, telemetry, and health publishers mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/agent-signals.dark.svg#only-dark" alt="Heartbeat, telemetry, and health publishers mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Heartbeat, telemetry, and health publishers mini architecture. <a href="../../../../../assets/diagrams/production/components/agent-signals.light.svg">View full-size diagram</a></figcaption>
</figure>


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

- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
