---
title: "PM2 process manager"
description: "Starts and supervises approved server-host and joined-device processes with bounded restart policies."
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

# PM2 process manager

Starts and supervises approved server-host and joined-device processes with bounded restart policies.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/pm2.svg" alt="" loading="lazy" decoding="async" /><span>PM2</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/nodejs.svg" alt="" loading="lazy" decoding="async" /><span>Node.js</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/npm.svg" alt="" loading="lazy" decoding="async" /><span>npm</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/pm2.light.svg" aria-label="Open full-size PM2 process manager mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/pm2.light.svg" alt="PM2 process manager mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/pm2.dark.svg" alt="PM2 process manager mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>PM2 process manager mini architecture. <a href="../../../../../assets/diagrams/production/components/pm2.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Starts and supervises approved server-host and joined-device processes with bounded restart policies. |
| Primary inputs | Generated process definitions |
| Primary outputs | Managed processes, status |
| Protocols / uses | Local process control |
| Evidence | process status/restart count |

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
| Architecture icon | brand-pm2 |
| Icon class | brand |
| Icon upstream | PM2 |
| Icon source revision | simple-icons-16.28.0 |
| Icon license | Simple-Icons-CC0 |
| Icon trademark note | PM2 and its logo may be trademarks of PM2; descriptive use only and no endorsement implied. |
| Technology markers | brand-nodejs, brand-npm |

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

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Runtime and PM2 process topology](../runtime-topology.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
