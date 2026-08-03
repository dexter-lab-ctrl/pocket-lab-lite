---
title: "PM2 process manager"
description: "Starts and supervises approved server-host and joined-device processes with bounded restart policies."
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

# PM2 process manager

Starts and supervises approved server-host and joined-device processes with bounded restart policies.

![PM2 process manager mini architecture](../../../../assets/diagrams/production/components/pm2.light.svg#only-light)
![PM2 process manager mini architecture](../../../../assets/diagrams/production/components/pm2.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Server host and joined devices |
| Started / runtime owner | PM2 |
| Process owner | PM2 daemon |
| Execution owner | Runtime process management |
| Data owner | None |
| Recovery owner | PM2 plus supervisors |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Generated process definitions

## Outputs

- Managed processes
- status

## Protocols

- Local process control

## Durable state

- None declared

## Health and readiness

- pm2 status

## Evidence

- process status/restart count

## Failure behavior

- process stopped

## Recovery behavior

- bounded restart
- separate supervisor

## Connections

### Incoming

- None declared

### Outgoing

- starts/supervises — Lite agent supervisor
- starts/supervises — Lite node agent
- starts app process — PROot Ubuntu application container

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh`
- `contract` — `contracts/generated/service-catalog.json`

## Existing documentation

- [services-pm2.md](../../services-pm2.md)

## Related architecture views

- [Device onboarding](../device-onboarding.md)
- [Runtime and PM2 process topology](../runtime-topology.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
