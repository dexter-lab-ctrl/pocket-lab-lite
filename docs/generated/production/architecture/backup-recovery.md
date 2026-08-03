---
title: "Backup and restore"
description: "Backup, verification, restore preview, confirmation, checkpoint, health validation, retention, and database recovery."
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

# Backup and restore

Backup, verification, restore preview, confirmation, checkpoint, health validation, retention, and database recovery.

<figure class="pl-architecture-diagram pl-architecture-diagram--system">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/backup-restore.light.svg" aria-label="Open full-size Backup and restore">
      <img class="pl-architecture-diagram__image" src="../../../../assets/diagrams/production/views/backup-restore.light.svg#only-light" alt="Backup and restore" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../assets/diagrams/production/views/backup-restore.dark.svg#only-dark" alt="Backup and restore" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Backup and restore. <a href="../../../../assets/diagrams/production/views/backup-restore.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Fleet, Apps, Security, Recovery, and Release APIs](components/api-domain-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Worker process](components/worker.md) | process | Server host | PM2 | Messaging and execution boundary |
| [Backup and verification engine](components/backup-engine.md) | process | Recovery worker | pocket-worker | Messaging and execution boundary |
| [Restore preview and confirmed restore](components/restore-preview.md) | process | Recovery worker | pocket-worker | Messaging and execution boundary |
| [Checkpoints and retention policy](components/checkpoints-retention.md) | process | Recovery worker | pocket-worker | Messaging and execution boundary |
| [Explicit retirement and database recovery](components/retirement-database-recovery.md) | process | FastAPI / worker | pocket-api / pocket-worker | Messaging and execution boundary |
| [Backup, restore, and checkpoint state](components/recovery-state.md) | database | SQLite and repository-owned manifests | Recovery worker | Durable-state boundary |
| [SQLite control-plane store](components/sqlite.md) | database | Server host | FastAPI and workers | Durable-state boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Fleet, Apps, Security, Recovery, and Release APIs | publishes validated command | NATS / JetStream | control | NATS |
| Backup and verification engine | verified backup input | Restore preview and confirmed restore | control | Manifest |
| Explicit retirement and database recovery | verified backup/restore | SQLite control-plane store | recovery | SQLite/filesystem |
| Backup and verification engine | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| NATS / JetStream | durable delivery | Worker process | control | JetStream |
| Restore preview and confirmed restore | creates checkpoint before apply | Checkpoints and retention policy | recovery | NATS |
| Checkpoints and retention policy | provides recovery point | Explicit retirement and database recovery | recovery | SQLite |
| Backup, restore, and checkpoint state | stored in | SQLite control-plane store | data | SQLite |
| Backup and verification engine | updates backup state | Backup, restore, and checkpoint state | data | SQLite |
| Restore preview and confirmed restore | updates restore state | Backup, restore, and checkpoint state | data | SQLite |
| Worker process | runs backup work | Backup and verification engine | control | Python |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
