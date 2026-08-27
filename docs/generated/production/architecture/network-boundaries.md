---
title: "Network and trust boundaries"
description: "Browser, same-origin server host, LAN, Tailnet, NATS listeners, joined device, application container, and external release boundaries."
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

# Network and trust boundaries

Browser, same-origin server host, LAN, Tailnet, NATS listeners, joined device, application container, and external release boundaries.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/network-boundaries.light.svg" aria-label="Open full-size Network and trust boundaries">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/network-boundaries.light.svg" alt="Network and trust boundaries" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/network-boundaries.dark.svg" alt="Network and trust boundaries" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Network and trust boundaries. <a href="../../../../assets/diagrams/production/views/network-boundaries.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [Browser](components/browser.md) | ui | User device | Browser | Browser trust boundary |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Local LAN](components/lan.md) | network | Private local network | Network | Private network and Tailnet boundary |
| [Tailscale remote access](components/tailscale.md) | network | Server host and joined devices | tailscaled | Private network and Tailnet boundary |
| [tailscaled daemon](components/tailscaled.md) | process | Android/Termux server host | startup scripts | Server-host boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [FastAPI /api/lite/*](components/lite-api.md) | service | Server host | PM2 | Control API boundary |
| [Primary and secondary NATS listeners](components/nats-listeners.md) | network | Server host | pocket-nats | Server-host boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Lite node agent](components/node-agent.md) | process | Server host or joined device | PM2 | Managed-device boundary |
| [PhotoPrism](components/photoprism.md) | external-app | PROot Ubuntu on server host | PM2 / PROot Ubuntu | Application-container boundary |
| [GitHub Release](components/github-release.md) | external | GitHub | GitHub Actions | External release boundary |
| [Remote-access readiness checks](components/remote-readiness.md) | decision | FastAPI read surface | pocket-api | Control API boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Browser | loads and hosts | React / Vite PWA | control | Browser runtime |
| Caddy same-origin proxy | routes /api/lite/* | FastAPI /api/lite/* | control | HTTP |
| Caddy same-origin proxy | same-origin /apps path | PhotoPrism | control | HTTP |
| Local LAN | local HTTPS | Caddy same-origin proxy | control | HTTPS |
| Primary and secondary NATS listeners | listener endpoints | NATS / JetStream | control | NATS |
| React / Vite PWA | same-origin request | Caddy same-origin proxy | control | HTTPS |
| tailscaled daemon | daemon status | Remote-access readiness checks | health | Local status |
| Primary and secondary NATS listeners | listener reachability | Remote-access readiness checks | health | TCP |
| Tailscale remote access | Tailnet HTTPS | Caddy same-origin proxy | control | HTTPS |
| Tailscale remote access | Tailnet reachability | Primary and secondary NATS listeners | control | TCP |
| tailscaled daemon | provides interface | Tailscale remote access | health | Tailscale |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
