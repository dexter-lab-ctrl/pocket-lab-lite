---
title: "Reconnect watchdog and supervisor recovery"
description: "Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available."
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

# Reconnect watchdog and supervisor recovery

Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available.

![Reconnect watchdog and supervisor recovery mini architecture](../../../../assets/diagrams/production/components/agent-recovery.light.svg#only-light)
![Reconnect watchdog and supervisor recovery mini architecture](../../../../assets/diagrams/production/components/agent-recovery.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Joined device |
| Started / runtime owner | agent and supervisor |
| Process owner | separate processes |
| Execution owner | Device recovery |
| Data owner | Server lifecycle state |
| Recovery owner | agent/supervisor |
| Security boundary | Managed-device boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- connection state
- PM2 state

## Outputs

- reconnect
- restart
- recovery evidence

## Protocols

- NATS
- Local process control

## Durable state

- device_recovery_history

## Health and readiness

- agent connection
- supervisor status

## Evidence

- recovery transitions

## Failure behavior

- disconnected
- stopped

## Recovery behavior

- reconnect watchdog
- supervisor restart
- guidance

## Connections

### Incoming

- Lite node agent — connection state
- Lite agent supervisor — stopped-agent recovery

### Outgoing

- reconnect/restart — Lite node agent

## Source verification

- `path` — `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`
- `path` — `pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py`

## Existing documentation

- [troubleshooting.md](../../troubleshooting.md)

## Related architecture views

- [Devices and offline recovery](../device-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
