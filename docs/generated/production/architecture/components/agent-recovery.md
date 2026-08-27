---
title: "Reconnect watchdog and supervisor recovery"
description: "Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available."
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

# Reconnect watchdog and supervisor recovery

Separates running-but-disconnected recovery from stopped-agent recovery and exposes truthful guidance when no supervisor is available.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/recovery.svg" alt="" loading="lazy" decoding="async" /><span>Recovery</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/android.svg" alt="" loading="lazy" decoding="async" /><span>Android</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/pm2.svg" alt="" loading="lazy" decoding="async" /><span>PM2</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/terminal.svg" alt="" loading="lazy" decoding="async" /><span>Terminal runtime</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/agent-recovery.light.svg" aria-label="Open full-size Reconnect watchdog and supervisor recovery mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/agent-recovery.light.svg" alt="Reconnect watchdog and supervisor recovery mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/agent-recovery.dark.svg" alt="Reconnect watchdog and supervisor recovery mini architecture" loading="lazy" decoding="async" />
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
| Architecture icon | semantic-recovery |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-android, brand-pm2, brand-python, semantic-terminal |

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

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Devices and offline recovery](../device-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
