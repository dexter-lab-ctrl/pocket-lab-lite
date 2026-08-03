---
title: "Devices and offline recovery"
description: "Durable enrollment, signal freshness, command delivery, reconnect watchdog, supervisor recovery, explicit repair, and retirement."
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

# Devices and offline recovery

Durable enrollment, signal freshness, command delivery, reconnect watchdog, supervisor recovery, explicit repair, and retirement.

![Devices and offline recovery](../../../assets/diagrams/production/views/device-recovery.light.svg#only-light)
![Devices and offline recovery](../../../assets/diagrams/production/views/device-recovery.dark.svg#only-dark)


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [Fleet, Apps, Security, Recovery, and Release APIs](components/api-domain-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Enrollment and device lifecycle state](components/device-state.md) | database | SQLite | lite_control_plane_store | Durable-state boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Lite node agent](components/node-agent.md) | process | Server host or joined device | PM2 | Managed-device boundary |
| [Heartbeat, telemetry, and health publishers](components/agent-signals.md) | event | Node agent | node agent | Managed-device boundary |
| [Device command executor](components/agent-command-executor.md) | process | Node agent | node agent | Managed-device boundary |
| [Lite agent supervisor](components/agent-supervisor.md) | process | Joined device | PM2 | Managed-device boundary |
| [Reconnect watchdog and supervisor recovery](components/agent-recovery.md) | process | Joined device | agent and supervisor | Managed-device boundary |
| [Explicit retirement and database recovery](components/retirement-database-recovery.md) | process | FastAPI / worker | pocket-api / pocket-worker | Messaging and execution boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| NATS / JetStream | delivers device command | Device command executor | control | NATS |
| Lite node agent | publishes | Heartbeat, telemetry, and health publishers | health | NATS |
| Lite node agent | connection state | Reconnect watchdog and supervisor recovery | health | NATS |
| Fleet, Apps, Security, Recovery, and Release APIs | publishes validated command | NATS / JetStream | control | NATS |
| Device command executor | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Device command executor | executes within | Lite node agent | control | Python |
| NATS / JetStream | fleet events projected | Enrollment and device lifecycle state | data | NATS/SQLite |
| Reconnect watchdog and supervisor recovery | reconnect/restart | Lite node agent | recovery | NATS/process |
| Heartbeat, telemetry, and health publishers | heartbeat/telemetry/health | NATS / JetStream | health | NATS |
| Heartbeat, telemetry, and health publishers | updates device truth | Enrollment and device lifecycle state | data | SQLite |
| Lite agent supervisor | stopped-agent recovery | Reconnect watchdog and supervisor recovery | recovery | Local process |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
