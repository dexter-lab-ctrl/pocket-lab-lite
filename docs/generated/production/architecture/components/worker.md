---
title: "Worker process"
description: "Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work."
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

# Worker process

Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/worker.svg" alt="" loading="lazy" decoding="async" /><span>Worker</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/worker.light.svg" aria-label="Open full-size Worker process mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/worker.light.svg" alt="Worker process mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/worker.dark.svg" alt="Worker process mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Worker process mini architecture. <a href="../../../../../assets/diagrams/production/components/worker.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **3** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work. |
| Primary inputs | JetStream commands |
| Primary outputs | Domain state, events, evidence |
| Protocols / uses | NATS, SQLite |
| Evidence | command received/running/terminal |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Server host |
| Started / runtime owner | PM2 |
| Process owner | pocket-worker |
| Execution owner | Execution plane |
| Data owner | Domain state via services |
| Recovery owner | Durable-consumer watchdog / PM2 |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-worker |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python |

## Inputs

- JetStream commands

## Outputs

- Domain state
- events
- evidence

## Protocols

- NATS
- SQLite

## Durable state

- command_lifecycle
- domain tables

## Health and readiness

- worker heartbeat
- durable consumer health

## Evidence

- command received/running/terminal

## Failure behavior

- consumer stale
- subprocess timeout

## Recovery behavior

- consumer re-enrollment
- bounded retry

## Connections

### Incoming

- NATS / JetStream — durable delivery

### Outgoing

- runs app work — App lifecycle worker
- runs backup work — Backup and verification engine
- claims and updates — Command admission and lifecycle
- admits release work — Release subprocess
- runs security work — Security scan coordinator
- executes multi-step work — Workflow execution

## Source verification

- `path` — `pocket-lab-final-structure/runtime/workers/pocketlab_worker.py`
- `pm2_process` — `pocket-worker`

## Existing documentation

- [services-pm2.md](../../services-pm2.md)
- [service-catalog.md](../../../development/service-catalog.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)
- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Request and control flow](../request-control.md)
- [Runtime and PM2 process topology](../runtime-topology.md)
- [Security and safety](../security.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
