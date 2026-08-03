---
title: "Runtime and PM2 process topology"
description: "Server-host, subprocess, PM2, node-agent, supervisor, PROot application, and release/projection process ownership."
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

# Runtime and PM2 process topology

Server-host, subprocess, PM2, node-agent, supervisor, PROot application, and release/projection process ownership.

![Runtime and PM2 process topology](../../../assets/diagrams/production/views/runtime-topology.light.svg#only-light)
![Runtime and PM2 process topology](../../../assets/diagrams/production/views/runtime-topology.dark.svg#only-dark)


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [PM2 process manager](components/pm2.md) | process | Server host and joined devices | PM2 | Server-host boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [FastAPI /api/lite/*](components/lite-api.md) | service | Server host | PM2 | Control API boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Worker process](components/worker.md) | process | Server host | PM2 | Messaging and execution boundary |
| [Release subprocess](components/release-subprocess.md) | process | Dedicated subprocess | pocket-worker | Messaging and execution boundary |
| [Projection subprocesses](components/projection-subprocesses.md) | process | Dedicated subprocesses / scheduler | pocket-api and subprocesses | Messaging and execution boundary |
| [Lite node agent](components/node-agent.md) | process | Server host or joined device | PM2 | Managed-device boundary |
| [Lite agent supervisor](components/agent-supervisor.md) | process | Joined device | PM2 | Managed-device boundary |
| [PROot Ubuntu application container](components/proot-ubuntu.md) | process | Android/Termux server host | proot-distro | Application-container boundary |
| [PhotoPrism](components/photoprism.md) | external-app | PROot Ubuntu on server host | PM2 / PROot Ubuntu | Application-container boundary |
| [tailscaled daemon](components/tailscaled.md) | process | Android/Termux server host | startup scripts | Server-host boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| Caddy same-origin proxy | routes /api/lite/* | FastAPI /api/lite/* | control | HTTP |
| Caddy same-origin proxy | same-origin /apps path | PhotoPrism | control | HTTP |
| NATS / JetStream | durable delivery | Worker process | control | JetStream |
| PM2 process manager | starts/supervises | Lite node agent | recovery | Local process |
| PM2 process manager | starts app process | PROot Ubuntu application container | recovery | Local process |
| PM2 process manager | starts/supervises | Lite agent supervisor | recovery | Local process |
| PROot Ubuntu application container | hosts process | PhotoPrism | control | Local process |
| Worker process | admits release work | Release subprocess | control | IPC |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
