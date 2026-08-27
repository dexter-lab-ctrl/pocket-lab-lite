---
title: "Prepared read, health, readiness, diagnostics, and evidence APIs"
description: "Serves side-effect-free prepared projections, health/readiness, compact diagnostics, and sanitized evidence lookups."
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

# Prepared read, health, readiness, diagnostics, and evidence APIs

Serves side-effect-free prepared projections, health/readiness, compact diagnostics, and sanitized evidence lookups.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/api-surface.svg" alt="" loading="lazy" decoding="async" /><span>API surface</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/api-read-surfaces.light.svg" aria-label="Open full-size Prepared read, health, readiness, diagnostics, and evidence APIs mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/api-read-surfaces.light.svg" alt="Prepared read, health, readiness, diagnostics, and evidence APIs mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/api-read-surfaces.dark.svg" alt="Prepared read, health, readiness, diagnostics, and evidence APIs mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Prepared read, health, readiness, diagnostics, and evidence APIs mini architecture. <a href="../../../../../assets/diagrams/production/components/api-read-surfaces.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **1** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Serves side-effect-free prepared projections, health/readiness, compact diagnostics, and sanitized evidence lookups. |
| Primary inputs | Prepared projections, compact evidence indexes |
| Primary outputs | Safe GET responses |
| Protocols / uses | HTTP JSON |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | FastAPI process |
| Started / runtime owner | pocket-api |
| Process owner | FastAPI |
| Execution owner | Lite API |
| Data owner | Prepared SQLite projections |
| Recovery owner | Projection scheduler and owning workers |
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

- Prepared projections
- compact evidence indexes

## Outputs

- Safe GET responses

## Protocols

- HTTP JSON

## Durable state

- prepared projections
- audit_evidence_index

## Health and readiness

- revision
- freshness
- ETag

## Evidence

- None declared

## Failure behavior

- stale projection

## Recovery behavior

- serve last committed generation
- focused invalidation

## Connections

### Incoming

- FastAPI /api/lite/* — serves safe reads
- Audit index, projection refresh, prepared projections, and domain revisions — prepared read
- Remote-access readiness checks — readiness summary
- Completion and audit evidence — sanitized lookup

### Outgoing

- safe summary — Frontend state ownership

## Source verification

- `route` — `GET /api/lite/system/health`
- `route` — `GET /api/lite/diagnostics/runtime`
- `route` — `GET /api/lite/events`
- `contract` — `contracts/generated/projection-catalog.json`

## Existing documentation

- [health-diagnostics.md](../../health-diagnostics.md)
- [projection-catalog.md](../../../development/projection-catalog.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Frontend state ownership](../frontend-state.md)
- [Request and control flow](../request-control.md)
- [SQLite and projection architecture](../data-projections.md)
- [Security and safety](../security.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
