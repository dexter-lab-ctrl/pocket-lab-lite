---
title: "Security and safety"
description: "Profile selection, command delivery, scanner adapters, normalized state, compact reads, sanitized evidence, and recovery."
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

# Security and safety

Profile selection, command delivery, scanner adapters, normalized state, compact reads, sanitized evidence, and recovery.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/security.light.svg" aria-label="Open full-size Security and safety">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/security.light.svg" alt="Security and safety" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/security.dark.svg" alt="Security and safety" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Security and safety. <a href="../../../../assets/diagrams/production/views/security.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Fleet, Apps, Security, Recovery, and Release APIs](components/api-domain-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Worker process](components/worker.md) | process | Server host | PM2 | Messaging and execution boundary |
| [Security scan coordinator](components/security-coordinator.md) | service | FastAPI and worker | pocket-api / pocket-worker | Control API boundary |
| [Quick, Full, and App safety checks](components/security-profiles.md) | process | Security worker | pocket-worker | Messaging and execution boundary |
| [Lynis and Trivy scanner adapters](components/scanner-adapters.md) | process | Security worker subprocesses | pocket-worker | Messaging and execution boundary |
| [Security findings and run state](components/security-state.md) | database | SQLite and compact sanitized files | Security worker | Durable-state boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |
| [Prepared read, health, readiness, diagnostics, and evidence APIs](components/api-read-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Fleet, Apps, Security, Recovery, and Release APIs | publishes validated command | NATS / JetStream | control | NATS |
| Security scan coordinator | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Completion and audit evidence | sanitized lookup | Prepared read, health, readiness, diagnostics, and evidence APIs | evidence | HTTP |
| NATS / JetStream | durable delivery | Worker process | control | JetStream |
| Quick, Full, and App safety checks | defines targets/exclusions | Lynis and Trivy scanner adapters | control | Python |
| Lynis and Trivy scanner adapters | writes normalized results | Security findings and run state | data | SQLite |
| Security scan coordinator | selects Quick/Full/App | Quick, Full, and App safety checks | control | Python |
| Security scan coordinator | runs bounded plan | Lynis and Trivy scanner adapters | control | Subprocess |
| Security scan coordinator | updates scan state | Security findings and run state | data | SQLite |
| Worker process | runs security work | Security scan coordinator | control | Python |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
