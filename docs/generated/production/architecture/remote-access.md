---
title: "Tailscale readiness"
description: "Safe tailscaled startup, Tailnet IPv4, local/Tailnet NATS listeners, joined-agent connectivity, and side-effect-free readiness reporting."
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

# Tailscale readiness

Safe tailscaled startup, Tailnet IPv4, local/Tailnet NATS listeners, joined-agent connectivity, and side-effect-free readiness reporting.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/remote-access.light.svg" aria-label="Open full-size Tailscale readiness">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/remote-access.light.svg" alt="Tailscale readiness" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/remote-access.dark.svg" alt="Tailscale readiness" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Tailscale readiness. <a href="../../../../assets/diagrams/production/views/remote-access.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Prepared read, health, readiness, diagnostics, and evidence APIs](components/api-read-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Remote-access readiness checks](components/remote-readiness.md) | decision | FastAPI read surface | pocket-api | Control API boundary |
| [tailscaled daemon](components/tailscaled.md) | process | Android/Termux server host | startup scripts | Server-host boundary |
| [Tailscale remote access](components/tailscale.md) | network | Server host and joined devices | tailscaled | Private network and Tailnet boundary |
| [Local LAN](components/lan.md) | network | Private local network | Network | Private network and Tailnet boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [Primary and secondary NATS listeners](components/nats-listeners.md) | network | Server host | pocket-nats | Server-host boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Lite node agent](components/node-agent.md) | process | Server host or joined device | PM2 | Managed-device boundary |
| [Lite agent supervisor](components/agent-supervisor.md) | process | Joined device | PM2 | Managed-device boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Local LAN | local HTTPS | Caddy same-origin proxy | control | HTTPS |
| Primary and secondary NATS listeners | listener endpoints | NATS / JetStream | control | NATS |
| React / Vite PWA | same-origin request | Caddy same-origin proxy | control | HTTPS |
| Remote-access readiness checks | readiness summary | Prepared read, health, readiness, diagnostics, and evidence APIs | data | HTTP |
| tailscaled daemon | daemon status | Remote-access readiness checks | health | Local status |
| Primary and secondary NATS listeners | listener reachability | Remote-access readiness checks | health | TCP |
| Tailscale remote access | Tailnet HTTPS | Caddy same-origin proxy | control | HTTPS |
| Tailscale remote access | Tailnet reachability | Primary and secondary NATS listeners | control | TCP |
| tailscaled daemon | provides interface | Tailscale remote access | health | Tailscale |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
