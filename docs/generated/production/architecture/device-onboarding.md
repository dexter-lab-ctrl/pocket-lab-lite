---
title: "Device onboarding"
description: "Backend-owned invite creation, identity guards, bootstrap artifact, agent/supervisor start, and first heartbeat."
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

# Device onboarding

Backend-owned invite creation, identity guards, bootstrap artifact, agent/supervisor start, and first heartbeat.



## Architecture diagram

<figure class="pl-architecture-diagram pl-architecture-diagram--system">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/device-onboarding.light.svg" aria-label="Open full-size Device onboarding">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/device-onboarding.light.svg" alt="Device onboarding" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/device-onboarding.dark.svg" alt="Device onboarding" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Device onboarding. <a href="../../../../assets/diagrams/production/views/device-onboarding.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [FastAPI /api/lite/*](components/lite-api.md) | service | Server host | PM2 | Control API boundary |
| [Identity, authentication, and invite guards](components/api-guards.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Invite and identity lifecycle](components/invite-state.md) | database | SQLite | Lite API | Durable-state boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |
| [PM2 process manager](components/pm2.md) | process | Server host and joined devices | PM2 | Server-host boundary |
| [Lite node agent](components/node-agent.md) | process | Server host or joined device | PM2 | Managed-device boundary |
| [Lite agent supervisor](components/agent-supervisor.md) | process | Joined device | PM2 | Managed-device boundary |
| [Heartbeat, telemetry, and health publishers](components/agent-signals.md) | event | Node agent | node agent | Managed-device boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Enrollment and device lifecycle state](components/device-state.md) | database | SQLite | lite_control_plane_store | Durable-state boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Lite node agent | publishes | Heartbeat, telemetry, and health publishers | health | NATS |
| FastAPI /api/lite/* | validates identity and intent | Identity, authentication, and invite guards | control | Python |
| Identity, authentication, and invite guards | backend-generated bootstrap | Lite node agent | control | Shell artifact |
| Invite and identity lifecycle | accepted enrollment | Enrollment and device lifecycle state | data | SQLite |
| NATS / JetStream | fleet events projected | Enrollment and device lifecycle state | data | NATS/SQLite |
| PM2 process manager | starts/supervises | Lite node agent | recovery | Local process |
| PM2 process manager | starts/supervises | Lite agent supervisor | recovery | Local process |
| Heartbeat, telemetry, and health publishers | heartbeat/telemetry/health | NATS / JetStream | health | NATS |
| Identity, authentication, and invite guards | stores invite/identity state | Invite and identity lifecycle | data | SQLite |
| Heartbeat, telemetry, and health publishers | updates device truth | Enrollment and device lifecycle state | data | SQLite |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
