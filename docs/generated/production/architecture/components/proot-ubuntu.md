---
title: "PROot Ubuntu application container"
description: "Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency."
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

# PROot Ubuntu application container

Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/ubuntu.svg" alt="" loading="lazy" decoding="async" /><span>Ubuntu</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/terminal.svg" alt="" loading="lazy" decoding="async" /><span>Terminal runtime</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/proot-ubuntu.light.svg" aria-label="Open full-size PROot Ubuntu application container mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/proot-ubuntu.light.svg" alt="PROot Ubuntu application container mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/proot-ubuntu.dark.svg" alt="PROot Ubuntu application container mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>PROot Ubuntu application container mini architecture. <a href="../../../../../assets/diagrams/production/components/proot-ubuntu.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Hosts verified applications such as PhotoPrism without making documentation tooling or the browser a runtime dependency. |
| Primary inputs | Generated app environment |
| Primary outputs | App process |
| Protocols / uses | Local process / HTTP |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Android/Termux server host |
| Started / runtime owner | proot-distro |
| Process owner | PM2-launched PROot process |
| Execution owner | Application runtime |
| Data owner | Application-owned state |
| Recovery owner | App lifecycle worker |
| Security boundary | Application-container boundary |
| Supported platforms | Android/Termux, ARM64 |
| Verification | verified |
| Architecture icon | brand-ubuntu |
| Icon class | brand |
| Icon upstream | Ubuntu |
| Icon source revision | simple-icons-16.28.0 |
| Icon license | Simple-Icons-CC0 |
| Icon trademark note | Ubuntu and its logo may be trademarks of Ubuntu; descriptive use only and no endorsement implied. |
| Technology markers | semantic-terminal |

## Inputs

- Generated app environment

## Outputs

- App process

## Protocols

- Local process / HTTP

## Durable state

- None declared

## Health and readiness

- process status

## Evidence

- None declared

## Failure behavior

- guest unavailable

## Recovery behavior

- explicit install/repair

## Connections

### Incoming

- PM2 process manager — starts app process

### Outgoing

- hosts process — PhotoPrism

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-proot-ubuntu.sh`
- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-photoprism-proot.sh`

## Existing documentation

- [android-termux.md](../../android-termux.md)
- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Runtime and PM2 process topology](../runtime-topology.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
