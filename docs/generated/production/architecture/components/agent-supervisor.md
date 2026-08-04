---
title: "Lite agent supervisor"
description: "Runs separately from the agent, reads the protected agent environment, and starts or restarts failed agents without overwriting identity."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 20bffc9aa51b0c5cedb30ae9e2be0a9cfb0925972f81f056d9792accd7d4e7ee
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Lite agent supervisor

Runs separately from the agent, reads the protected agent environment, and starts or restarts failed agents without overwriting identity.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/supervisor.svg" alt="" loading="lazy" decoding="async" /><span>Supervisor</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/agent-supervisor.light.svg" aria-label="Open full-size Lite agent supervisor mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/agent-supervisor.light.svg" alt="Lite agent supervisor mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/agent-supervisor.dark.svg" alt="Lite agent supervisor mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Lite agent supervisor mini architecture. <a href="../../../../../assets/diagrams/production/components/agent-supervisor.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Runs separately from the agent, reads the protected agent environment, and starts or restarts failed agents without overwriting identity. |
| Primary inputs | PM2 agent status, protected environment |
| Primary outputs | agent restart, sanitized recovery evidence |
| Protocols / uses | Local process control, NATS when reachable |
| Evidence | supervisor recovery |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Joined device |
| Started / runtime owner | PM2 |
| Process owner | pocketlab-agent-supervisor-<node_id> |
| Execution owner | Device recovery |
| Data owner | No canonical state |
| Recovery owner | Self / PM2 |
| Security boundary | Managed-device boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-supervisor |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python |

## Inputs

- PM2 agent status
- protected environment

## Outputs

- agent restart
- sanitized recovery evidence

## Protocols

- Local process control
- NATS when reachable

## Durable state

- None declared

## Health and readiness

- supervisor status

## Evidence

- supervisor recovery

## Failure behavior

- supervisor absent

## Recovery behavior

- UI recovery guidance
- explicit repair

## Connections

### Incoming

- PM2 process manager — starts/supervises

### Outgoing

- stopped-agent recovery — Reconnect watchdog and supervisor recovery

## Source verification

- `path` — `pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py`
- `pm2_process` — `pocketlab-agent-supervisor-<node_id>`

## Existing documentation

- [devices.md](../../devices.md)
- [troubleshooting.md](../../troubleshooting.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Devices and offline recovery](../device-recovery.md)
- [Runtime and PM2 process topology](../runtime-topology.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
