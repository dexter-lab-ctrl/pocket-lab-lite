---
title: "Command acknowledgement and reconciliation"
description: "Admission, durable delivery, claim, execution, acknowledgement, redelivery protection, queue bounds, and lifecycle reconciliation."
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

# Command acknowledgement and reconciliation

Admission, durable delivery, claim, execution, acknowledgement, redelivery protection, queue bounds, and lifecycle reconciliation.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system pl-architecture-diagram--wide">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/command-reconciliation.light.svg" aria-label="Open full-size Command acknowledgement and reconciliation">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/command-reconciliation.light.svg" alt="Command acknowledgement and reconciliation" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/command-reconciliation.dark.svg" alt="Command acknowledgement and reconciliation" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Command acknowledgement and reconciliation. <a href="../../../../assets/diagrams/production/views/command-reconciliation.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [Fleet, Apps, Security, Recovery, and Release APIs](components/api-domain-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Worker process](components/worker.md) | process | Server host | PM2 | Messaging and execution boundary |
| [Command admission and lifecycle](components/command-lifecycle.md) | process | FastAPI and worker | pocket-api / pocket-worker | Messaging and execution boundary |
| [Bounded queues and reconciliation](components/bounded-reconciliation.md) | process | FastAPI and worker processes | pocket-api / pocket-worker | Messaging and execution boundary |
| [Device command executor](components/agent-command-executor.md) | process | Node agent | node agent | Managed-device boundary |
| [App, command, and workflow state](components/app-workflow-state.md) | database | SQLite | workers | Durable-state boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| NATS / JetStream | delivers device command | Device command executor | control | NATS |
| Fleet, Apps, Security, Recovery, and Release APIs | publishes validated command | NATS / JetStream | control | NATS |
| Command admission and lifecycle | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Device command executor | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| NATS / JetStream | durable delivery | Worker process | control | JetStream |
| Worker process | claims and updates | Command admission and lifecycle | control | SQLite/NATS |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
