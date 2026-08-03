---
title: "Fleet, Apps, Security, Recovery, and Release APIs"
description: "Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution."
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

# Fleet, Apps, Security, Recovery, and Release APIs

Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/api-domain-surfaces.light.svg" aria-label="Open full-size Fleet, Apps, Security, Recovery, and Release APIs mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/api-domain-surfaces.light.svg#only-light" alt="Fleet, Apps, Security, Recovery, and Release APIs mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/api-domain-surfaces.dark.svg#only-dark" alt="Fleet, Apps, Security, Recovery, and Release APIs mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Fleet, Apps, Security, Recovery, and Release APIs mini architecture. <a href="../../../../../assets/diagrams/production/components/api-domain-surfaces.light.svg">View full-size diagram</a></figcaption>
</figure>


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
