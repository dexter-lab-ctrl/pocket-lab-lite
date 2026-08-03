---
title: "App Catalog lifecycle"
description: "Catalog/action projections, same-origin PhotoPrism access, PROot runtime, worker-owned lifecycle, health/media readiness, backup, restore preview, and update lifecycle."
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

# App Catalog lifecycle

Catalog/action projections, same-origin PhotoPrism access, PROot runtime, worker-owned lifecycle, health/media readiness, backup, restore preview, and update lifecycle.

<figure class="pl-architecture-diagram pl-architecture-diagram--system pl-architecture-diagram--wide">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/apps-lifecycle.light.svg" aria-label="Open full-size App Catalog lifecycle">
      <img class="pl-architecture-diagram__image" src="../../../../assets/diagrams/production/views/apps-lifecycle.light.svg#only-light" alt="App Catalog lifecycle" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../assets/diagrams/production/views/apps-lifecycle.dark.svg#only-dark" alt="App Catalog lifecycle" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>App Catalog lifecycle. <a href="../../../../assets/diagrams/production/views/apps-lifecycle.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [App Catalog](components/app-catalog.md) | service | PWA plus FastAPI prepared reads | Lite UI / Lite API | Control API boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [PhotoPrism](components/photoprism.md) | external-app | PROot Ubuntu on server host | PM2 / PROot Ubuntu | Application-container boundary |
| [PROot Ubuntu application container](components/proot-ubuntu.md) | process | Android/Termux server host | proot-distro | Application-container boundary |
| [App lifecycle worker](components/app-lifecycle-worker.md) | process | pocket-worker | PM2 | Messaging and execution boundary |
| [Media readiness and app health probes](components/media-app-health.md) | decision | FastAPI / worker | Lite API / worker | Control API boundary |
| [App backup, restore preview, and update lifecycle](components/app-recovery-update.md) | process | Worker / release subprocess | pocket-worker | Messaging and execution boundary |
| [App, command, and workflow state](components/app-workflow-state.md) | database | SQLite | workers | Durable-state boundary |
| [Backup, restore, and checkpoint state](components/recovery-state.md) | database | SQLite and repository-owned manifests | Recovery worker | Durable-state boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Media readiness and app health probes | base-path probe | PhotoPrism | health | HTTP |
| App backup, restore preview, and update lifecycle | stores manifests/operations | Backup, restore, and checkpoint state | data | SQLite |
| App lifecycle worker | runs backup/update paths | App backup, restore preview, and update lifecycle | control | Python |
| App lifecycle worker | refreshes canonical readiness | Media readiness and app health probes | control | Python |
| Caddy same-origin proxy | same-origin /apps path | PhotoPrism | control | HTTP |
| App Catalog | app cards and actions | React / Vite PWA | data | HTTPS |
| App, command, and workflow state | catalog/action projection | App Catalog | data | SQLite |
| App lifecycle worker | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| PROot Ubuntu application container | hosts process | PhotoPrism | control | Local process |
| React / Vite PWA | same-origin request | Caddy same-origin proxy | control | HTTPS |
| App lifecycle worker | updates app state | App, command, and workflow state | data | SQLite |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
