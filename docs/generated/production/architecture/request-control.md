---
title: "Request and control flow"
description: "Same-origin request validation, command admission, durable execution, prepared reads, and truthful UI state."
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

# Request and control flow

Same-origin request validation, command admission, durable execution, prepared reads, and truthful UI state.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system pl-architecture-diagram--wide">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/request-control.light.svg" aria-label="Open full-size Request and control flow">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/request-control.light.svg" alt="Request and control flow" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/request-control.dark.svg" alt="Request and control flow" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Request and control flow. <a href="../../../../assets/diagrams/production/views/request-control.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [User](components/user.md) | actor | Human user device | Browser | Browser trust boundary |
| [Browser](components/browser.md) | ui | User device | Browser | Browser trust boundary |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [FastAPI /api/lite/*](components/lite-api.md) | service | Server host | PM2 | Control API boundary |
| [Identity, authentication, and invite guards](components/api-guards.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Fleet, Apps, Security, Recovery, and Release APIs](components/api-domain-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Worker process](components/worker.md) | process | Server host | PM2 | Messaging and execution boundary |
| [Command admission and lifecycle](components/command-lifecycle.md) | process | FastAPI and worker | pocket-api / pocket-worker | Messaging and execution boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |
| [SQLite control-plane store](components/sqlite.md) | database | Server host | FastAPI and workers | Durable-state boundary |
| [Audit index, projection refresh, prepared projections, and domain revisions](components/prepared-state.md) | database | SQLite | scheduler / subprocesses | Durable-state boundary |
| [Prepared read, health, readiness, diagnostics, and evidence APIs](components/api-read-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Frontend state ownership](components/frontend-state.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| FastAPI /api/lite/* | dispatches domain request | Fleet, Apps, Security, Recovery, and Release APIs | control | Python |
| FastAPI /api/lite/* | validates identity and intent | Identity, authentication, and invite guards | control | Python |
| Fleet, Apps, Security, Recovery, and Release APIs | publishes validated command | NATS / JetStream | control | NATS |
| FastAPI /api/lite/* | serves safe reads | Prepared read, health, readiness, diagnostics, and evidence APIs | data | Python |
| FastAPI /api/lite/* | transactional read/write | SQLite control-plane store | data | SQLite |
| Browser | loads and hosts | React / Vite PWA | control | Browser runtime |
| Caddy same-origin proxy | routes /api/lite/* | FastAPI /api/lite/* | control | HTTP |
| Command admission and lifecycle | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Completion and audit evidence | indexes evidence | Audit index, projection refresh, prepared projections, and domain revisions | data | SQLite |
| Completion and audit evidence | sanitized lookup | Prepared read, health, readiness, diagnostics, and evidence APIs | evidence | HTTP |
| NATS / JetStream | durable delivery | Worker process | control | JetStream |
| React / Vite PWA | same-origin request | Caddy same-origin proxy | control | HTTPS |
| React / Vite PWA | selects and renders | Frontend state ownership | data | React |
| Prepared read, health, readiness, diagnostics, and evidence APIs | safe summary | Frontend state ownership | data | HTTPS |
| Audit index, projection refresh, prepared projections, and domain revisions | stored in | SQLite control-plane store | data | SQLite |
| Audit index, projection refresh, prepared projections, and domain revisions | prepared read | Prepared read, health, readiness, diagnostics, and evidence APIs | data | SQLite |
| User | uses | Browser | control | HTTPS |
| Worker process | claims and updates | Command admission and lifecycle | control | SQLite/NATS |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
