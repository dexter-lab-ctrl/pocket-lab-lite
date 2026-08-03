---
title: "Audit and evidence flow"
description: "Lifecycle producers, sanitized evidence service, durable evidence index, compact lookups, and UI-safe summaries."
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

# Audit and evidence flow

Lifecycle producers, sanitized evidence service, durable evidence index, compact lookups, and UI-safe summaries.

![Audit and evidence flow](../../../assets/diagrams/production/views/audit-evidence.light.svg#only-light)
![Audit and evidence flow](../../../assets/diagrams/production/views/audit-evidence.dark.svg#only-dark)


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [Command admission and lifecycle](components/command-lifecycle.md) | process | FastAPI and worker | pocket-api / pocket-worker | Messaging and execution boundary |
| [Workflow execution](components/workflow-execution.md) | process | Worker / projection subprocess | pocket-worker | Messaging and execution boundary |
| [App lifecycle worker](components/app-lifecycle-worker.md) | process | pocket-worker | PM2 | Messaging and execution boundary |
| [Security scan coordinator](components/security-coordinator.md) | service | FastAPI and worker | pocket-api / pocket-worker | Control API boundary |
| [Backup and verification engine](components/backup-engine.md) | process | Recovery worker | pocket-worker | Messaging and execution boundary |
| [Release subprocess](components/release-subprocess.md) | process | Dedicated subprocess | pocket-worker | Messaging and execution boundary |
| [Device command executor](components/agent-command-executor.md) | process | Node agent | node agent | Managed-device boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |
| [Audit index, projection refresh, prepared projections, and domain revisions](components/prepared-state.md) | database | SQLite | scheduler / subprocesses | Durable-state boundary |
| [Prepared read, health, readiness, diagnostics, and evidence APIs](components/api-read-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Command admission and lifecycle | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Workflow execution | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Release subprocess | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| App lifecycle worker | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Security scan coordinator | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Backup and verification engine | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Device command executor | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Completion and audit evidence | indexes evidence | Audit index, projection refresh, prepared projections, and domain revisions | data | SQLite |
| Completion and audit evidence | sanitized lookup | Prepared read, health, readiness, diagnostics, and evidence APIs | evidence | HTTP |
| Audit index, projection refresh, prepared projections, and domain revisions | prepared read | Prepared read, health, readiness, diagnostics, and evidence APIs | data | SQLite |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
