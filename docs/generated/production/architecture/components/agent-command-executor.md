---
title: "Device command executor"
description: "Executes approved device commands in the node agent and publishes truthful results."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 13dae80367ddf3ba183f4f77c57075516b1e463d27336c7aa834c23b5cce75a2
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Device command executor

Executes approved device commands in the node agent and publishes truthful results.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/agent-command-executor.light.svg" aria-label="Open full-size Device command executor mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/agent-command-executor.light.svg#only-light" alt="Device command executor mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/agent-command-executor.dark.svg#only-dark" alt="Device command executor mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Device command executor mini architecture. <a href="../../../../../assets/diagrams/production/components/agent-command-executor.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Executes approved device commands in the node agent and publishes truthful results. |
| Primary inputs | Validated NATS command |
| Primary outputs | command result, fresh heartbeat |
| Protocols / uses | NATS, Local process control |
| Evidence | device command result |

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
| Architecture icon | infra-agent |

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
