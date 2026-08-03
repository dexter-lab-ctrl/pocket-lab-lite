---
title: "Release subprocess and atomic rollback"
description: "Repository tag and assets, verified staging, process-isolated apply, atomic PWA promotion, post-switch health, last-known-good state, and rollback."
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

# Release subprocess and atomic rollback

Repository tag and assets, verified staging, process-isolated apply, atomic PWA promotion, post-switch health, last-known-good state, and rollback.

![Release subprocess and atomic rollback](../../../assets/diagrams/production/views/release-rollback.light.svg#only-light)
![Release subprocess and atomic rollback](../../../assets/diagrams/production/views/release-rollback.dark.svg#only-dark)


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [GitHub repository](components/github-repository.md) | external | External source hosting | GitHub | External release boundary |
| [GitHub Release](components/github-release.md) | external | GitHub | GitHub Actions | External release boundary |
| [Date-based Lite tag, dist.zip, checksums, and release manifest](components/release-artifacts.md) | artifact | GitHub Release / staging | Release workflow | External release boundary |
| [Download staging and release verification](components/release-staging.md) | process | Release subprocess | pocket-worker | Messaging and execution boundary |
| [Release subprocess](components/release-subprocess.md) | process | Dedicated subprocess | pocket-worker | Messaging and execution boundary |
| [Installed release and runtime state](components/release-state.md) | database | SQLite | Release subprocess | Durable-state boundary |
| [Atomic PWA promotion](components/atomic-promotion.md) | process | Server host | release subprocess | Server-host boundary |
| [Post-switch health validation](components/post-switch-health.md) | decision | Release subprocess against local services | release subprocess | Server-host boundary |
| [Last-known-good state and rollback](components/last-known-good.md) | process | Server host / release subprocess | release subprocess | Server-host boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Date-based Lite tag, dist.zip, checksums, and release manifest | download and verify | Download staging and release verification | control | HTTPS |
| Release subprocess | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Post-switch health validation | mark current/failed | Installed release and runtime state | data | SQLite |
| Post-switch health validation | failure trigger | Last-known-good state and rollback | recovery | IPC |
| Atomic PWA promotion | serves active PWA | Caddy same-origin proxy | control | Filesystem/HTTP |
| Atomic PWA promotion | validate switched release | Post-switch health validation | health | HTTP |
| GitHub Release | publishes assets | Date-based Lite tag, dist.zip, checksums, and release manifest | data | HTTPS |
| GitHub repository | annotated tag workflow | GitHub Release | control | GitHub Actions |
| Last-known-good state and rollback | restore prior PWA | Atomic PWA promotion | recovery | Filesystem |
| Download staging and release verification | verified stage | Release subprocess | data | IPC/filesystem |
| Release subprocess | updates release state | Installed release and runtime state | data | SQLite |
| Release subprocess | apply | Atomic PWA promotion | control | Filesystem |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
