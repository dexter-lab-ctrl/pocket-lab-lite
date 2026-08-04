---
title: "SQLite and projection architecture"
description: "Canonical domain state, revision tracking, process-isolated projection work, prepared reads, and safe frontend snapshots."
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

# SQLite and projection architecture

Canonical domain state, revision tracking, process-isolated projection work, prepared reads, and safe frontend snapshots.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/data-projections.light.svg" aria-label="Open full-size SQLite and projection architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/data-projections.light.svg" alt="SQLite and projection architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/data-projections.dark.svg" alt="SQLite and projection architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>SQLite and projection architecture. <a href="../../../../assets/diagrams/production/views/data-projections.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [SQLite control-plane store](components/sqlite.md) | database | Server host | FastAPI and workers | Durable-state boundary |
| [Enrollment and device lifecycle state](components/device-state.md) | database | SQLite | lite_control_plane_store | Durable-state boundary |
| [Invite and identity lifecycle](components/invite-state.md) | database | SQLite | Lite API | Durable-state boundary |
| [App, command, and workflow state](components/app-workflow-state.md) | database | SQLite | workers | Durable-state boundary |
| [Security findings and run state](components/security-state.md) | database | SQLite and compact sanitized files | Security worker | Durable-state boundary |
| [Backup, restore, and checkpoint state](components/recovery-state.md) | database | SQLite and repository-owned manifests | Recovery worker | Durable-state boundary |
| [Installed release and runtime state](components/release-state.md) | database | SQLite | Release subprocess | Durable-state boundary |
| [Audit index, projection refresh, prepared projections, and domain revisions](components/prepared-state.md) | database | SQLite | scheduler / subprocesses | Durable-state boundary |
| [Projection subprocesses](components/projection-subprocesses.md) | process | Dedicated subprocesses / scheduler | pocket-api and subprocesses | Messaging and execution boundary |
| [Bounded queues and reconciliation](components/bounded-reconciliation.md) | process | FastAPI and worker processes | pocket-api / pocket-worker | Messaging and execution boundary |
| [Prepared read, health, readiness, diagnostics, and evidence APIs](components/api-read-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Frontend state ownership](components/frontend-state.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Invite and identity lifecycle | accepted enrollment | Enrollment and device lifecycle state | data | SQLite |
| Projection subprocesses | commits generation | Audit index, projection refresh, prepared projections, and domain revisions | data | SQLite |
| Bounded queues and reconciliation | bounds and schedules | Projection subprocesses | control | IPC |
| Prepared read, health, readiness, diagnostics, and evidence APIs | safe summary | Frontend state ownership | data | HTTPS |
| Enrollment and device lifecycle state | stored in | SQLite control-plane store | data | SQLite |
| Invite and identity lifecycle | stored in | SQLite control-plane store | data | SQLite |
| App, command, and workflow state | stored in | SQLite control-plane store | data | SQLite |
| Security findings and run state | stored in | SQLite control-plane store | data | SQLite |
| Backup, restore, and checkpoint state | stored in | SQLite control-plane store | data | SQLite |
| Installed release and runtime state | stored in | SQLite control-plane store | data | SQLite |
| Audit index, projection refresh, prepared projections, and domain revisions | stored in | SQLite control-plane store | data | SQLite |
| Audit index, projection refresh, prepared projections, and domain revisions | prepared read | Prepared read, health, readiness, diagnostics, and evidence APIs | data | SQLite |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
