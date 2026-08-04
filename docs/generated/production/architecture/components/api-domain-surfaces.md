---
title: "Fleet, Apps, Security, Recovery, and Release APIs"
description: "Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution."
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

# Fleet, Apps, Security, Recovery, and Release APIs

Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/api-surface.svg" alt="" loading="lazy" decoding="async" /><span>API surface</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/api-domain-surfaces.light.svg" aria-label="Open full-size Fleet, Apps, Security, Recovery, and Release APIs mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/api-domain-surfaces.light.svg" alt="Fleet, Apps, Security, Recovery, and Release APIs mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/api-domain-surfaces.dark.svg" alt="Fleet, Apps, Security, Recovery, and Release APIs mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Fleet, Apps, Security, Recovery, and Release APIs mini architecture. <a href="../../../../../assets/diagrams/production/components/api-domain-surfaces.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution. |
| Primary inputs | User intent, domain state |
| Primary outputs | Domain summaries, accepted commands |
| Protocols / uses | HTTP JSON, NATS |
| Evidence | domain lifecycle evidence |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | FastAPI process |
| Started / runtime owner | pocket-api |
| Process owner | FastAPI |
| Execution owner | Lite API domains |
| Data owner | Domain SQLite state |
| Recovery owner | Domain worker / supervisor |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-api-surface |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python |

## Inputs

- User intent
- domain state

## Outputs

- Domain summaries
- accepted commands

## Protocols

- HTTP JSON
- NATS

## Durable state

- domain current-state tables

## Health and readiness

- domain revisions
- projection freshness

## Evidence

- domain lifecycle evidence

## Failure behavior

- command undeliverable
- domain stale

## Recovery behavior

- explicit retry
- reconciliation

## Connections

### Incoming

- FastAPI /api/lite/* — dispatches domain request

### Outgoing

- publishes validated command — NATS / JetStream

## Source verification

- `route` — `GET /api/lite/fleet`
- `route` — `GET /api/lite/catalog`
- `route` — `GET /api/lite/security/summary`
- `route` — `GET /api/lite/recovery/summary`
- `route` — `GET /api/lite/release`

## Existing documentation

- [devices.md](../../devices.md)
- [apps.md](../../apps.md)
- [security.md](../../security.md)
- [recovery.md](../../recovery.md)
- [release.md](../../release.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)
- [Command acknowledgement and reconciliation](../command-reconciliation.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Devices and offline recovery](../device-recovery.md)
- [Frontend state ownership](../frontend-state.md)
- [Request and control flow](../request-control.md)
- [Security and safety](../security.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
