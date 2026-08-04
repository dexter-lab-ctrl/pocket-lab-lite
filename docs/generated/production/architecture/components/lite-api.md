---
title: "FastAPI /api/lite/*"
description: "Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell."
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

# FastAPI /api/lite/*

Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/fastapi.svg" alt="" loading="lazy" decoding="async" /><span>FastAPI</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/lite-api.light.svg" aria-label="Open full-size FastAPI /api/lite/* mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/lite-api.light.svg" alt="FastAPI /api/lite/* mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/lite-api.dark.svg" alt="FastAPI /api/lite/* mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>FastAPI /api/lite/* mini architecture. <a href="../../../../../assets/diagrams/production/components/lite-api.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **1** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell. |
| Primary inputs | Same-origin requests |
| Primary outputs | Prepared reads, validated commands |
| Protocols / uses | HTTP JSON, NATS |
| Evidence | request lifecycle, command acceptance |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | Server host |
| Started / runtime owner | PM2 |
| Process owner | pocket-api |
| Execution owner | Lite API |
| Data owner | SQLite prepared reads |
| Recovery owner | PM2 after NATS/SQLite verification |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | brand-fastapi |
| Icon class | brand |
| Icon upstream | FastAPI |
| Icon source revision | simple-icons-16.28.0 |
| Icon license | Simple-Icons-CC0 |
| Icon trademark note | FastAPI and its logo may be trademarks of FastAPI; descriptive use only and no endorsement implied. |
| Technology markers | brand-python |

## Inputs

- Same-origin requests

## Outputs

- Prepared reads
- validated commands

## Protocols

- HTTP JSON
- NATS

## Durable state

- SQLite

## Health and readiness

- GET /health
- GET /ready

## Evidence

- request lifecycle
- command acceptance

## Failure behavior

- NATS unavailable
- SQLite unavailable

## Recovery behavior

- fail writes closed
- serve safe last committed reads

## Connections

### Incoming

- Caddy same-origin proxy — routes /api/lite/*

### Outgoing

- dispatches domain request — Fleet, Apps, Security, Recovery, and Release APIs
- validates identity and intent — Identity, authentication, and invite guards
- serves safe reads — Prepared read, health, readiness, diagnostics, and evidence APIs
- transactional read/write — SQLite control-plane store

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py`
- `pm2_process` — `pocket-api`
- `route` — `GET /api/lite/status`

## Existing documentation

- [lite-api.md](../../../../reference/api/lite-api.md)
- [api-contract.md](../../../development/api-contract.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Frontend state ownership](../frontend-state.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Request and control flow](../request-control.md)
- [Runtime and PM2 process topology](../runtime-topology.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
