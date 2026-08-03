---
title: "Reconnect watchdog and supervisor recovery"
description: "Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available."
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

# Reconnect watchdog and supervisor recovery

Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/agent-recovery.light.svg" aria-label="Open full-size Reconnect watchdog and supervisor recovery mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/agent-recovery.light.svg#only-light" alt="Reconnect watchdog and supervisor recovery mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/agent-recovery.dark.svg#only-dark" alt="Reconnect watchdog and supervisor recovery mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Reconnect watchdog and supervisor recovery mini architecture. <a href="../../../../../assets/diagrams/production/components/agent-recovery.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available. |
| Primary inputs | connection state, PM2 state |
| Primary outputs | reconnect, restart, recovery evidence |
| Protocols / uses | NATS, Local process control |
| Evidence | recovery transitions |

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
| Architecture icon | infra-supervisor |

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
