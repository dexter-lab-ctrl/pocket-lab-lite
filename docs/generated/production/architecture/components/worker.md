---
title: "Worker process"
description: "Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work."
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

# Worker process

Consumes durable commands and owns backend execution for apps, security, recovery, releases, and lifecycle work.

![Worker process mini architecture](../../../../assets/diagrams/production/components/worker.light.svg#only-light)
![Worker process mini architecture](../../../../assets/diagrams/production/components/worker.dark.svg#only-dark)

The mini diagram deterministically collapses **3** additional connections.


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
