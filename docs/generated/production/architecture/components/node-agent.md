---
title: "Lite node agent"
description: "Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages."
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

# Lite node agent

Connects to NATS, publishes heartbeat/telemetry/health, handles device commands, and reconnects after outages.

![Lite node agent mini architecture](../../../../assets/diagrams/production/components/node-agent.light.svg#only-light)
![Lite node agent mini architecture](../../../../assets/diagrams/production/components/node-agent.dark.svg#only-dark)

The mini diagram deterministically collapses **1** additional connections.


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
