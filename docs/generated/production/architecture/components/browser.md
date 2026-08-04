---
title: "Browser"
description: "Hosts the installed or web PWA and enforces browser-origin boundaries."
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

# Browser

Hosts the installed or web PWA and enforces browser-origin boundaries.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/browser.svg" alt="" loading="lazy" decoding="async" /><span>Browser</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/browser.light.svg" aria-label="Open full-size Browser mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/browser.light.svg" alt="Browser mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/browser.dark.svg" alt="Browser mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Browser mini architecture. <a href="../../../../../assets/diagrams/production/components/browser.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Hosts the installed or web PWA and enforces browser-origin boundaries. |
| Primary inputs | HTML, CSS, JavaScript, SVG |
| Primary outputs | Same-origin HTTP requests |
| Protocols / uses | HTTPS |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | ui |
| Runs on | User device |
| Started / runtime owner | Browser |
| Process owner | Browser |
| Execution owner | Browser |
| Data owner | None |
| Recovery owner | Browser reload / service-worker update |
| Security boundary | Browser trust boundary |
| Supported platforms | Browser, Android, Desktop |
| Verification | verified |
| Architecture icon | semantic-browser |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- HTML, CSS, JavaScript, SVG

## Outputs

- Same-origin HTTP requests

## Protocols

- HTTPS

## Durable state

- None declared

## Health and readiness

- page load
- service worker readiness

## Evidence

- None declared

## Failure behavior

- None declared

## Recovery behavior

- None declared

## Connections

### Incoming

- User — uses

### Outgoing

- loads and hosts — React / Vite PWA

## Source verification

- `path` — `index.html`
- `path` — `vite.config.js`

## Existing documentation

- [caddy-access.md](../../caddy-access.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Frontend state ownership](../frontend-state.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Request and control flow](../request-control.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
