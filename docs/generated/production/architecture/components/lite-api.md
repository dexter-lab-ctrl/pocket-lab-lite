---
title: "FastAPI /api/lite/*"
description: "Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell."
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

# FastAPI /api/lite/*

Validates requests, owns safe read APIs, admits commands, and never delegates browser execution directly to NATS or shell.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/lite-api.light.svg" aria-label="Open full-size FastAPI /api/lite/* mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/lite-api.light.svg#only-light" alt="FastAPI /api/lite/* mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/lite-api.dark.svg#only-dark" alt="FastAPI /api/lite/* mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>FastAPI /api/lite/* mini architecture. <a href="../../../../../assets/diagrams/production/components/lite-api.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **1** additional connections.


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
