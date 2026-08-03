---
title: "Device command executor"
description: "Executes approved device commands in the node agent and publishes truthful results."
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

# Device command executor

Executes approved device commands in the node agent and publishes truthful results.

![Device command executor mini architecture](../../../../assets/diagrams/production/components/agent-command-executor.light.svg#only-light)
![Device command executor mini architecture](../../../../assets/diagrams/production/components/agent-command-executor.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Node agent |
| Started / runtime owner | node agent |
| Process owner | node agent |
| Execution owner | Device execution |
| Data owner | Command lifecycle in server SQLite |
| Recovery owner | Command reconciliation |
| Security boundary | Managed-device boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Validated NATS command

## Outputs

- command result
- fresh heartbeat

## Protocols

- NATS
- Local process control

## Durable state

- command_lifecycle

## Health and readiness

- command progress

## Evidence

- device command result

## Failure behavior

- undeliverable
- agent disconnected

## Recovery behavior

- do not fake delivery
- retry after reconnect

## Connections

### Incoming

- NATS / JetStream — delivers device command

### Outgoing

- executes within — Lite node agent
- records sanitized lifecycle — Completion and audit evidence

## Source verification

- `nats_subject` — `pocketlab.commands.lite.device.restart`
- `path` — `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`

## Existing documentation

- [devices.md](../../devices.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [Devices and offline recovery](../device-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
