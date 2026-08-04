---
title: "Media readiness and app health probes"
description: "Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation."
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

# Media readiness and app health probes

Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/health.svg" alt="" loading="lazy" decoding="async" /><span>Health and readiness</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/media-app-health.light.svg" aria-label="Open full-size Media readiness and app health probes mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/media-app-health.light.svg" alt="Media readiness and app health probes mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/media-app-health.dark.svg" alt="Media readiness and app health probes mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Media readiness and app health probes mini architecture. <a href="../../../../../assets/diagrams/production/components/media-app-health.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation. |
| Primary inputs | Route/runtime/storage posture |
| Primary outputs | route_ready, media readiness |
| Protocols / uses | HTTP probes, SQLite |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | decision |
| Runs on | FastAPI / worker |
| Started / runtime owner | Lite API / worker |
| Process owner | app services |
| Execution owner | Apps domain |
| Data owner | Sanitized app projection |
| Recovery owner | App repair |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-health |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- Route/runtime/storage posture

## Outputs

- route_ready
- media readiness

## Protocols

- HTTP probes
- SQLite

## Durable state

- None declared

## Health and readiness

- operational status

## Evidence

- None declared

## Failure behavior

- media not connected
- route not ready

## Recovery behavior

- connect media safely
- repair

## Connections

### Incoming

- App lifecycle worker — refreshes canonical readiness

### Outgoing

- base-path probe — PhotoPrism

## Source verification

- `route` — `GET /api/lite/apps/photoprism/storage-preview`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_catalog_live.py`

## Existing documentation

- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
