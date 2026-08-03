---
title: "PhotoPrism"
description: "Provides the verified managed photo application under a same-origin Caddy path."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 13dae80367ddf3ba183f4f77c57075516b1e463d27336c7aa834c23b5cce75a2
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# PhotoPrism

Provides the verified managed photo application under a same-origin Caddy path.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/photoprism.light.svg" aria-label="Open full-size PhotoPrism mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/photoprism.light.svg#only-light" alt="PhotoPrism mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/photoprism.dark.svg#only-dark" alt="PhotoPrism mini architecture" loading="lazy" decoding="async" />
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
| Architecture icon | infra-photoprism |

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
