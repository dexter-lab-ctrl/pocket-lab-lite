---
title: "Lite node agent"
description: "Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages."
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

# Lite node agent

Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/agent.svg" alt="" loading="lazy" decoding="async" /><span>Agent</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/node-agent.light.svg" aria-label="Open full-size Lite node agent mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/node-agent.light.svg" alt="Lite node agent mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/node-agent.dark.svg" alt="Lite node agent mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Lite node agent mini architecture. <a href="../../../../../assets/diagrams/production/components/node-agent.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **1** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages. |
| Primary inputs | NATS commands, agent environment |
| Primary outputs | heartbeat, telemetry, health |
| Protocols / uses | NATS |
| Evidence | device lifecycle events |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Server host or joined device |
| Started / runtime owner | PM2 |
| Process owner | pocketlab-agent-<node_id> |
| Execution owner | Device runtime |
| Data owner | Local identity environment; server SQLite is canonical |
| Recovery owner | Reconnect watchdog and supervisor |
| Security boundary | Managed-device boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-agent |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python |

## Inputs

- NATS commands
- agent environment

## Outputs

- heartbeat
- telemetry
- health
- command result

## Protocols

- NATS

## Durable state

- ~/.pocketlab-lite-agent.env (not documented with values)

## Health and readiness

- fresh heartbeat
- connection state

## Evidence

- device lifecycle events

## Failure behavior

- disconnected
- stopped
- identity mismatch

## Recovery behavior

- reconnect
- supervisor restart
- explicit repair/rejoin

## Connections

### Incoming

- Device command executor — executes within
- Identity, authentication, and invite guards — backend-generated bootstrap
- Reconnect watchdog and supervisor recovery — reconnect/restart
- PM2 process manager — starts/supervises

### Outgoing

- connection state — Reconnect watchdog and supervisor recovery
- publishes — Heartbeat, telemetry, and health publishers

## Source verification

- `path` — `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`
- `pm2_process` — `pocketlab-agent-<node_id>`

## Existing documentation

- [devices.md](../../devices.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Runtime and PM2 process topology](../runtime-topology.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
