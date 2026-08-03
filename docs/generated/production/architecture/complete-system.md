---
title: "Complete Pocket Lab Lite system map"
description: "Major deployment zones and the primary request, execution, state, evidence, device, app, remote-access, and release flows."
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

# Complete Pocket Lab Lite system map

Major deployment zones and the primary request, execution, state, evidence, device, app, remote-access, and release flows.

![Complete Pocket Lab Lite system map](../../../assets/diagrams/production/views/complete-system.light.svg#only-light)
![Complete Pocket Lab Lite system map](../../../assets/diagrams/production/views/complete-system.dark.svg#only-dark)


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [User](components/user.md) | actor | Human user device | Browser | Browser trust boundary |
| [Browser](components/browser.md) | ui | User device | Browser | Browser trust boundary |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Frontend state ownership](components/frontend-state.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [FastAPI /api/lite/*](components/lite-api.md) | service | Server host | PM2 | Control API boundary |
| [Fleet, Apps, Security, Recovery, and Release APIs](components/api-domain-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Worker process](components/worker.md) | process | Server host | PM2 | Messaging and execution boundary |
| [SQLite control-plane store](components/sqlite.md) | database | Server host | FastAPI and workers | Durable-state boundary |
| [Audit index, projection refresh, prepared projections, and domain revisions](components/prepared-state.md) | database | SQLite | scheduler / subprocesses | Durable-state boundary |
| [Lite node agent](components/node-agent.md) | process | Server host or joined device | PM2 | Managed-device boundary |
| [Lite agent supervisor](components/agent-supervisor.md) | process | Joined device | PM2 | Managed-device boundary |
| [Tailscale remote access](components/tailscale.md) | network | Server host and joined devices | tailscaled | Private network and Tailnet boundary |
| [App Catalog](components/app-catalog.md) | service | PWA plus FastAPI prepared reads | Lite UI / Lite API | Control API boundary |
| [PhotoPrism](components/photoprism.md) | external-app | PROot Ubuntu on server host | PM2 / PROot Ubuntu | Application-container boundary |
| [Security scan coordinator](components/security-coordinator.md) | service | FastAPI and worker | pocket-api / pocket-worker | Control API boundary |
| [Backup and verification engine](components/backup-engine.md) | process | Recovery worker | pocket-worker | Messaging and execution boundary |
| [Release subprocess](components/release-subprocess.md) | process | Dedicated subprocess | pocket-worker | Messaging and execution boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| FastAPI /api/lite/* | dispatches domain request | Fleet, Apps, Security, Recovery, and Release APIs | control | Python |
| Fleet, Apps, Security, Recovery, and Release APIs | publishes validated command | NATS / JetStream | control | NATS |
| FastAPI /api/lite/* | transactional read/write | SQLite control-plane store | data | SQLite |
| Browser | loads and hosts | React / Vite PWA | control | Browser runtime |
| Caddy same-origin proxy | routes /api/lite/* | FastAPI /api/lite/* | control | HTTP |
| Caddy same-origin proxy | same-origin /apps path | PhotoPrism | control | HTTP |
| App Catalog | app cards and actions | React / Vite PWA | data | HTTPS |
| Release subprocess | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Security scan coordinator | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Backup and verification engine | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Completion and audit evidence | indexes evidence | Audit index, projection refresh, prepared projections, and domain revisions | data | SQLite |
| NATS / JetStream | durable delivery | Worker process | control | JetStream |
| React / Vite PWA | same-origin request | Caddy same-origin proxy | control | HTTPS |
| React / Vite PWA | selects and renders | Frontend state ownership | data | React |
| Audit index, projection refresh, prepared projections, and domain revisions | stored in | SQLite control-plane store | data | SQLite |
| Tailscale remote access | Tailnet HTTPS | Caddy same-origin proxy | control | HTTPS |
| User | uses | Browser | control | HTTPS |
| Worker process | runs backup work | Backup and verification engine | control | Python |
| Worker process | admits release work | Release subprocess | control | IPC |
| Worker process | runs security work | Security scan coordinator | control | Python |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
