---
title: "React / Vite PWA"
description: "Renders Lite screens and sends same-origin requests only to FastAPI through Caddy."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 765d187cae484a494c7f2602216f3c7ab49cafc2bdffd1ea1b8900f7d1e8e672
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# React / Vite PWA

Renders Lite screens and sends same-origin requests only to FastAPI through Caddy.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/react.svg" alt="" loading="lazy" decoding="async" /><span>React</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/vite.svg" alt="" loading="lazy" decoding="async" /><span>Vite</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/pwa.svg" alt="" loading="lazy" decoding="async" /><span>Progressive web app</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/pwa.light.svg" aria-label="Open full-size React / Vite PWA mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/pwa.light.svg" alt="React / Vite PWA mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/pwa.dark.svg" alt="React / Vite PWA mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>React / Vite PWA mini architecture. <a href="../../../../../assets/diagrams/production/components/pwa.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Renders Lite screens and sends same-origin requests only to FastAPI through Caddy. |
| Primary inputs | Prepared API responses |
| Primary outputs | Validated user requests |
| Protocols / uses | HTTPS JSON |
| Evidence | frontend lifecycle diagnostics |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | ui |
| Runs on | Browser / installed PWA |
| Started / runtime owner | Browser |
| Process owner | React |
| Execution owner | Lite UI |
| Data owner | FastAPI source of truth |
| Recovery owner | Error boundaries and browser reload |
| Security boundary | Browser trust boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | brand-react |
| Icon class | brand |
| Icon upstream | React |
| Icon source revision | simple-icons-16.28.0 |
| Icon license | Simple-Icons-CC0 |
| Icon trademark note | React and its logo may be trademarks of React; descriptive use only and no endorsement implied. |
| Technology markers | brand-vite, semantic-pwa |

## Inputs

- Prepared API responses

## Outputs

- Validated user requests

## Protocols

- HTTPS JSON

## Durable state

- None declared

## Health and readiness

- error boundary
- frontend lifecycle challenge

## Evidence

- frontend lifecycle diagnostics

## Failure behavior

- backend unavailable
- saved state stale

## Recovery behavior

- read-only saved state
- quiet revalidation

## Connections

### Incoming

- Browser — loads and hosts
- App Catalog — app cards and actions

### Outgoing

- same-origin request — Caddy same-origin proxy
- selects and renders — Frontend state ownership

## Source verification

- `path` — `src/lite/LiteApp.jsx`
- `path` — `src/lib/liteApi.js`

## Existing documentation

- [tabs.md](../../tabs.md)
- [architecture.md](../../architecture.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Audit and evidence flow](../audit-evidence.md)
- [Backup and restore](../backup-recovery.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Frontend state ownership](../frontend-state.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Request and control flow](../request-control.md)
- [Security and safety](../security.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
