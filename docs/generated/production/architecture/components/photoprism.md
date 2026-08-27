---
title: "PhotoPrism"
description: "Provides the verified managed photo application under a same-origin Caddy path."
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

# PhotoPrism

Provides the verified managed photo application under a same-origin Caddy path.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/photoprism.svg" alt="" loading="lazy" decoding="async" /><span>PhotoPrism</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/ubuntu.svg" alt="" loading="lazy" decoding="async" /><span>Ubuntu</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/photoprism.light.svg" aria-label="Open full-size PhotoPrism mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/photoprism.light.svg" alt="PhotoPrism mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/photoprism.dark.svg" alt="PhotoPrism mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>PhotoPrism mini architecture. <a href="../../../../../assets/diagrams/production/components/photoprism.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Provides the verified managed photo application under a same-origin Caddy path. |
| Primary inputs | Same-origin app route, approved media mapping |
| Primary outputs | PhotoPrism UI and health |
| Protocols / uses | HTTP behind Caddy |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | external-app |
| Runs on | PROot Ubuntu on server host |
| Started / runtime owner | PM2 / PROot Ubuntu |
| Process owner | pocketlab-app-photoprism |
| Execution owner | Managed application |
| Data owner | PhotoPrism application data |
| Recovery owner | App lifecycle worker |
| Security boundary | Application-container boundary |
| Supported platforms | Android/Termux, ARM64 |
| Verification | verified |
| Architecture icon | brand-photoprism |
| Icon class | brand |
| Icon upstream | PhotoPrism |
| Icon source revision | logo-black.svg-2021-01-21 |
| Icon license | PhotoPrism-brand-asset |
| Icon trademark note | PhotoPrism is a registered trademark; use does not imply endorsement. |
| Technology markers | brand-ubuntu |

## Inputs

- Same-origin app route
- approved media mapping

## Outputs

- PhotoPrism UI and health

## Protocols

- HTTP behind Caddy

## Durable state

- None declared

## Health and readiness

- base-path status probe

## Evidence

- None declared

## Failure behavior

- route 404
- process stopped

## Recovery behavior

- route-aware repair
- process recovery

## Connections

### Incoming

- Caddy same-origin proxy — same-origin /apps path
- PROot Ubuntu application container — hosts process
- Media readiness and app health probes — base-path probe

### Outgoing

- None declared

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-photoprism-proot.sh`
- `literal` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-photoprism-proot.sh` contains `pocketlab-app-photoprism`

## Existing documentation

- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Runtime and PM2 process topology](../runtime-topology.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
