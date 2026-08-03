---
title: "Browser"
description: "Hosts the installed or web PWA and enforces browser-origin boundaries."
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

# Browser

Hosts the installed or web PWA and enforces browser-origin boundaries.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/browser.light.svg" aria-label="Open full-size Browser mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/browser.light.svg#only-light" alt="Browser mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/browser.dark.svg#only-dark" alt="Browser mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Browser mini architecture. <a href="../../../../../assets/diagrams/production/components/browser.light.svg">View full-size diagram</a></figcaption>
</figure>


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
