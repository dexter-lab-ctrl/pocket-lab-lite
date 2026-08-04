---
title: "Audit and evidence flow"
description: "Lifecycle producers, sanitized evidence service, durable evidence index, compact lookups, and UI-safe summaries."
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

# Audit and evidence flow

Lifecycle producers, sanitized evidence service, durable evidence index, compact lookups, and UI-safe summaries.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system pl-architecture-diagram--wide">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/audit-evidence.light.svg" aria-label="Open full-size Audit and evidence flow">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/audit-evidence.light.svg" alt="Audit and evidence flow" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/audit-evidence.dark.svg" alt="Audit and evidence flow" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Audit and evidence flow. <a href="../../../../assets/diagrams/production/views/audit-evidence.light.svg">View full-size diagram</a></figcaption>
</figure>


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
