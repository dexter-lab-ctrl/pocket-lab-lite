---
title: "Component encyclopedia"
description: "Index of canonical architecture component knowledge pages."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Component encyclopedia

| Component | Owner | Runtime | Boundary | Confidence |
| --- | --- | --- | --- | --- |
| [Device command executor](./agent-command-executor.md) | Device execution | Node agent | managed-device | verified |
| [Reconnect watchdog and supervisor recovery](./agent-recovery.md) | Device recovery | Joined device | managed-device | verified |
| [Heartbeat, telemetry, and health publishers](./agent-signals.md) | Device runtime | Node agent | managed-device | verified |
| [Lite agent supervisor](./agent-supervisor.md) | Device recovery | Joined device | managed-device | verified |
| [Fleet, Apps, Security, Recovery, and Release APIs](./api-domain-surfaces.md) | Lite API domains | FastAPI process | control-api | verified |
| [Identity, authentication, and invite guards](./api-guards.md) | Lite API | FastAPI process | control-api | verified |
| [Prepared read, health, readiness, diagnostics, and evidence APIs](./api-read-surfaces.md) | Lite API | FastAPI process | control-api | verified |
| [App Catalog](./app-catalog.md) | Apps domain | PWA plus FastAPI prepared reads | control-api | verified |
| [App lifecycle worker](./app-lifecycle-worker.md) | Apps execution | pocket-worker | messaging-execution | verified |
| [App backup, restore preview, and update lifecycle](./app-recovery-update.md) | Apps and Recovery | Worker / release subprocess | messaging-execution | verified |
| [App, command, and workflow state](./app-workflow-state.md) | Apps and workflows | SQLite | durable-state | verified |
| [Atomic PWA promotion](./atomic-promotion.md) | Release runtime | Server host | server-host | verified |
| [Backup and verification engine](./backup-engine.md) | Recovery execution | Recovery worker | messaging-execution | verified |
| [Bounded queues and reconciliation](./bounded-reconciliation.md) | Schedulers and stores | FastAPI and worker processes | messaging-execution | verified |
| [Browser](./browser.md) | Browser | User device | browser | verified |
| [Caddy same-origin proxy](./caddy.md) | Same-origin access | Server host | server-host | verified |
| [Checkpoints and retention policy](./checkpoints-retention.md) | Recovery maintenance | Recovery worker | messaging-execution | verified |
| [Command admission and lifecycle](./command-lifecycle.md) | Command lifecycle | FastAPI and worker | messaging-execution | verified |
| [Completion and audit evidence](./completion-evidence.md) | Evidence services | Worker and FastAPI | messaging-execution | verified |
| [Enrollment and device lifecycle state](./device-state.md) | Fleet domain | SQLite | durable-state | verified |
| [Frontend state ownership](./frontend-state.md) | Lite UI | Browser / installed PWA | browser | verified |
| [GitHub Release](./github-release.md) | Release workflow | GitHub | external-release | verified |
| [GitHub repository](./github-repository.md) | Repository maintainers | External source hosting | external-release | verified |
| [Invite and identity lifecycle](./invite-state.md) | Fleet onboarding | SQLite | durable-state | verified |
| [Local LAN](./lan.md) | Private network | Private local network | tailnet | verified |
| [Last-known-good state and rollback](./last-known-good.md) | Release recovery | Server host / release subprocess | server-host | verified |
| [FastAPI /api/lite/*](./lite-api.md) | Lite API | Server host | control-api | verified |
| [Media readiness and app health probes](./media-app-health.md) | Apps domain | FastAPI / worker | control-api | verified |
| [NATS / JetStream](./nats-jetstream.md) | Messaging backbone | Server host | messaging-execution | verified |
| [Primary and secondary NATS listeners](./nats-listeners.md) | NATS runtime | Server host | server-host | verified |
| [Lite node agent](./node-agent.md) | Device runtime | Server host or joined device | managed-device | verified |
| [PhotoPrism](./photoprism.md) | Managed application | PROot Ubuntu on server host | application-container | verified |
| [PM2 process manager](./pm2.md) | Runtime process management | Server host and joined devices | server-host | verified |
| [Post-switch health validation](./post-switch-health.md) | Release validation | Release subprocess against local services | server-host | verified |
| [Audit index, projection refresh, prepared projections, and domain revisions](./prepared-state.md) | Projection subsystem | SQLite | durable-state | verified |
| [Projection subprocesses](./projection-subprocesses.md) | Prepared projections | Dedicated subprocesses / scheduler | messaging-execution | verified |
| [PROot Ubuntu application container](./proot-ubuntu.md) | Application runtime | Android/Termux server host | application-container | verified |
| [React / Vite PWA](./pwa.md) | Lite UI | Browser / installed PWA | browser | verified |
| [Backup, restore, and checkpoint state](./recovery-state.md) | Recovery domain | SQLite and repository-owned manifests | durable-state | verified |
| [Date-based Lite tag, dist.zip, checksums, and release manifest](./release-artifacts.md) | Release engineering | GitHub Release / staging | external-release | verified |
| [Download staging and release verification](./release-staging.md) | Release runtime | Release subprocess | messaging-execution | verified |
| [Installed release and runtime state](./release-state.md) | Release system | SQLite | durable-state | verified |
| [Release subprocess](./release-subprocess.md) | Release runtime | Dedicated subprocess | messaging-execution | verified |
| [Remote-access readiness checks](./remote-readiness.md) | Lite API | FastAPI read surface | control-api | verified |
| [Restore preview and confirmed restore](./restore-preview.md) | Recovery execution | Recovery worker | messaging-execution | verified |
| [Explicit retirement and database recovery](./retirement-database-recovery.md) | Fleet and Recovery | FastAPI / worker | messaging-execution | verified |
| [Lynis and Trivy scanner adapters](./scanner-adapters.md) | Security execution | Security worker subprocesses | messaging-execution | verified |
| [Security scan coordinator](./security-coordinator.md) | Security domain | FastAPI and worker | control-api | verified |
| [Quick, Full, and App safety checks](./security-profiles.md) | Security policy | Security worker | messaging-execution | verified |
| [Security findings and run state](./security-state.md) | Security domain | SQLite and compact sanitized files | durable-state | verified |
| [SQLite control-plane store](./sqlite.md) | Lite control plane store | Server host | durable-state | verified |
| [Tailscale remote access](./tailscale.md) | Remote access | Server host and joined devices | tailnet | verified |
| [tailscaled daemon](./tailscaled.md) | Remote access runtime | Android/Termux server host | server-host | verified |
| [User](./user.md) | User | Human user device | browser | verified |
| [Worker process](./worker.md) | Execution plane | Server host | messaging-execution | verified |
| [Workflow execution](./workflow-execution.md) | Workflow engine | Worker / projection subprocess | messaging-execution | verified |
