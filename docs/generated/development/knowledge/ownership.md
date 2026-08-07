---
title: "Ownership encyclopedia"
description: "System/subsystem ownership without personal names."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Ownership encyclopedia

| Component | Owner | Execution | Data | Recovery | Runtime |
| --- | --- | --- | --- | --- | --- |
| Device command executor | Device execution | node agent | Command lifecycle in server SQLite | Command reconciliation | node agent |
| Reconnect watchdog and supervisor recovery | Device recovery | separate processes | Server lifecycle state | agent/supervisor | agent and supervisor |
| Heartbeat, telemetry, and health publishers | Device runtime | node agent | Server SQLite projections | Reconnect watchdog | node agent |
| Lite agent supervisor | Device recovery | pocketlab-agent-supervisor-<node_id> | No canonical state | Self / PM2 | PM2 |
| Fleet, Apps, Security, Recovery, and Release APIs | Lite API domains | FastAPI | Domain SQLite state | Domain worker / supervisor | pocket-api |
| Identity, authentication, and invite guards | Lite API | FastAPI | SQLite identity and invite state | Explicit repair/rejoin | pocket-api |
| Prepared read, health, readiness, diagnostics, and evidence APIs | Lite API | FastAPI | Prepared SQLite projections | Projection scheduler and owning workers | pocket-api |
| App Catalog | Apps domain | React / FastAPI | SQLite app state | App worker | Lite UI / Lite API |
| App lifecycle worker | Apps execution | pocket-worker | App lifecycle SQLite state | Worker retry / repair | PM2 |
| App backup, restore preview, and update lifecycle | Apps and Recovery | app/recovery services | SQLite and backup manifests | Checkpoint / rollback | pocket-worker |
| App, command, and workflow state | Apps and workflows | app/workflow services | SQLite | Reconciliation | workers |
| Atomic PWA promotion | Release runtime | release apply stage | Active and staged PWA directories | Rollback | release subprocess |
| Backup and verification engine | Recovery execution | backup services | Backup repository and manifest index | Recovery worker | pocket-worker |
| Bounded queues and reconciliation | Schedulers and stores | queue owners | SQLite lifecycle state | Reconciliation loops | pocket-api / pocket-worker |
| Browser | Browser | Browser | None | Browser reload / service-worker update | Browser |
| Caddy same-origin proxy | Same-origin access | caddy-proxy | None | Startup scripts / PM2 | PM2 |
| Checkpoints and retention policy | Recovery maintenance | maintenance services | Recovery state | Recovery worker | pocket-worker |
| Command admission and lifecycle | Command lifecycle | FastAPI and worker | SQLite command_lifecycle | Reconciliation | pocket-api / pocket-worker |
| Completion and audit evidence | Evidence services | domain owners | SQLite evidence index and sanitized files | Owning domain | worker / FastAPI |
| Enrollment and device lifecycle state | Fleet domain | FastAPI / worker | SQLite | Explicit retirement / repair | lite_control_plane_store |
| Frontend state ownership | Lite UI | React | FastAPI; Dexie is safe read-only fallback | TanStack revalidation and UI workflows | Browser |
| GitHub Release | Release workflow | release-dist workflow | Release assets | Release workflow rerun/fix | GitHub Actions |
| GitHub repository | Repository maintainers | GitHub Actions | Git repository | Repository maintainers | GitHub |
| Invite and identity lifecycle | Fleet onboarding | FastAPI | SQLite | Explicit repair/rejoin | Lite API |
| Local LAN | Private network | Network stack | None | Network owner | Network |
| Last-known-good state and rollback | Release recovery | rollback stage | Release SQLite state and prior PWA | Self | release subprocess |
| FastAPI /api/lite/* | Lite API | pocket-api | SQLite prepared reads | PM2 after NATS/SQLite verification | PM2 |
| Media readiness and app health probes | Apps domain | app services | Sanitized app projection | App repair | Lite API / worker |
| NATS / JetStream | Messaging backbone | pocket-nats | JetStream storage | Startup scripts / PM2 | PM2 |
| Primary and secondary NATS listeners | NATS runtime | NATS server | NATS configuration | startup scripts | pocket-nats |
| Lite node agent | Device runtime | pocketlab-agent-<node_id> | Local identity environment; server SQLite is canonical | Reconnect watchdog and supervisor | PM2 |
| PhotoPrism | Managed application | pocketlab-app-photoprism | PhotoPrism application data | App lifecycle worker | PM2 / PROot Ubuntu |
| PM2 process manager | Runtime process management | PM2 daemon | None | PM2 plus supervisors | PM2 |
| Post-switch health validation | Release validation | release validation stage | Release runtime state | Rollback | release subprocess |
| Audit index, projection refresh, prepared projections, and domain revisions | Projection subsystem | projection services | SQLite | Projection reconciliation | scheduler / subprocesses |
| Projection subprocesses | Prepared projections | projection scheduler | SQLite prepared projections | Projection scheduler | pocket-api and subprocesses |
| PROot Ubuntu application container | Application runtime | PM2-launched PROot process | Application-owned state | App lifecycle worker | proot-distro |
| React / Vite PWA | Lite UI | React | FastAPI source of truth | Error boundaries and browser reload | Browser |
| Backup, restore, and checkpoint state | Recovery domain | recovery services | SQLite / backup repository | Recovery worker | Recovery worker |
| Date-based Lite tag, dist.zip, checksums, and release manifest | Release engineering | GitHub Actions | Release assets | Release workflow | Release workflow |
| Download staging and release verification | Release runtime | release subprocess | Staging directory and release SQLite state | Discard staging / backoff | pocket-worker |
| Installed release and runtime state | Release system | release services | SQLite | Rollback | Release subprocess |
| Release subprocess | Release runtime | release subprocess | SQLite release state and staging area | Last-known-good rollback | pocket-worker |
| Remote-access readiness checks | Lite API | FastAPI | Prepared status | startup scripts / user guidance | pocket-api |
| Restore preview and confirmed restore | Recovery execution | restore services | Recovery operations and backup repository | Checkpoint rollback | pocket-worker |
| Explicit retirement and database recovery | Fleet and Recovery | domain services | SQLite | Explicit repair/rejoin or database restore | pocket-api / pocket-worker |
| Lynis and Trivy scanner adapters | Security execution | scanner subprocess group | Sanitized Security evidence | Worker cleanup / retry | pocket-worker |
| Security scan coordinator | Security domain | security services | SQLite Security state | Security maintenance / worker recovery | pocket-api / pocket-worker |
| Quick, Full, and App safety checks | Security policy | Security coordinator | Security state | Explicit retry | pocket-worker |
| Security findings and run state | Security domain | security services | SQLite | Security maintenance / retry | Security worker |
| SQLite control-plane store | Lite control plane store | SQLite clients | Pocket Lab Lite | Database backup/restore | FastAPI and workers |
| Tailscale remote access | Remote access | tailscaled | Tailscale local state | Startup scripts | tailscaled |
| tailscaled daemon | Remote access runtime | tailscaled | Local Tailscale state | startup scripts | startup scripts |
| User | User | Browser | None | User | Browser |
| Worker process | Execution plane | pocket-worker | Domain state via services | Durable-consumer watchdog / PM2 | PM2 |
| Workflow execution | Workflow engine | worker and workflow projection subprocess | SQLite workflow tables | Workflow reconciliation | pocket-worker |

## Reverse owner lookup

| Owner role | Resources |
| --- | --- |
| data_owner:Active and staged PWA directories | component:atomic-promotion |
| data_owner:App lifecycle SQLite state | component:app-lifecycle-worker |
| data_owner:Application-owned state | component:proot-ubuntu |
| data_owner:Backup repository and manifest index | component:backup-engine |
| data_owner:Command lifecycle in server SQLite | component:agent-command-executor |
| data_owner:Domain SQLite state | component:api-domain-surfaces |
| data_owner:Domain state via services | component:worker |
| data_owner:FastAPI source of truth | component:pwa |
| data_owner:FastAPI; Dexie is safe read-only fallback | component:frontend-state |
| data_owner:Git repository | component:github-repository |
| data_owner:JetStream storage | component:nats-jetstream |
| data_owner:Local Tailscale state | component:tailscaled |
| data_owner:Local identity environment; server SQLite is canonical | component:node-agent |
| data_owner:NATS configuration | component:nats-listeners |
| data_owner:No canonical state | component:agent-supervisor |
| data_owner:None | component:browser, component:caddy, component:lan, component:pm2, component:user |
| data_owner:PhotoPrism application data | component:photoprism |
| data_owner:Pocket Lab Lite | component:sqlite |
| data_owner:Prepared SQLite projections | component:api-read-surfaces |
| data_owner:Prepared status | component:remote-readiness |
| data_owner:Recovery operations and backup repository | component:restore-preview |
| data_owner:Recovery state | component:checkpoints-retention |
| data_owner:Release SQLite state and prior PWA | component:last-known-good |
| data_owner:Release assets | component:github-release, component:release-artifacts |
| data_owner:Release runtime state | component:post-switch-health |
| data_owner:SQLite | component:app-workflow-state, component:device-state, component:invite-state, component:prepared-state, component:release-state, component:retirement-database-recovery, component:security-state |
| data_owner:SQLite / backup repository | component:recovery-state |
| data_owner:SQLite Security state | component:security-coordinator |
| data_owner:SQLite and backup manifests | component:app-recovery-update |
| data_owner:SQLite app state | component:app-catalog |
| data_owner:SQLite command_lifecycle | component:command-lifecycle |
| data_owner:SQLite evidence index and sanitized files | component:completion-evidence |
| data_owner:SQLite identity and invite state | component:api-guards |
| data_owner:SQLite lifecycle state | component:bounded-reconciliation |
| data_owner:SQLite prepared projections | component:projection-subprocesses |
| data_owner:SQLite prepared reads | component:lite-api |
| data_owner:SQLite release state and staging area | component:release-subprocess |
| data_owner:SQLite workflow tables | component:workflow-execution |
| data_owner:Sanitized Security evidence | component:scanner-adapters |
| data_owner:Sanitized app projection | component:media-app-health |
| data_owner:Security state | component:security-profiles |
| data_owner:Server SQLite projections | component:agent-signals |
| data_owner:Server lifecycle state | component:agent-recovery |
| data_owner:Staging directory and release SQLite state | component:release-staging |
| data_owner:Tailscale local state | component:tailscale |
| execution_owner:Browser | component:browser, component:user |
| execution_owner:FastAPI | component:api-domain-surfaces, component:api-guards, component:api-read-surfaces, component:invite-state, component:remote-readiness |
| execution_owner:FastAPI / worker | component:device-state |
| execution_owner:FastAPI and worker | component:command-lifecycle |
| execution_owner:GitHub Actions | component:github-repository, component:release-artifacts |
| execution_owner:NATS server | component:nats-listeners |
| execution_owner:Network stack | component:lan |
| execution_owner:PM2 daemon | component:pm2 |
| execution_owner:PM2-launched PROot process | component:proot-ubuntu |
| execution_owner:React | component:frontend-state, component:pwa |
| execution_owner:React / FastAPI | component:app-catalog |
| execution_owner:SQLite clients | component:sqlite |
| execution_owner:Security coordinator | component:security-profiles |
| execution_owner:app services | component:media-app-health |
| execution_owner:app/recovery services | component:app-recovery-update |
| execution_owner:app/workflow services | component:app-workflow-state |
| execution_owner:backup services | component:backup-engine |
| execution_owner:caddy-proxy | component:caddy |
| execution_owner:domain owners | component:completion-evidence |
| execution_owner:domain services | component:retirement-database-recovery |
| execution_owner:maintenance services | component:checkpoints-retention |
| execution_owner:node agent | component:agent-command-executor, component:agent-signals |
| execution_owner:pocket-api | component:lite-api |
| execution_owner:pocket-nats | component:nats-jetstream |
| execution_owner:pocket-worker | component:app-lifecycle-worker, component:worker |
| execution_owner:pocketlab-agent-<node_id> | component:node-agent |
| execution_owner:pocketlab-agent-supervisor-<node_id> | component:agent-supervisor |
| execution_owner:pocketlab-app-photoprism | component:photoprism |
| execution_owner:projection scheduler | component:projection-subprocesses |
| execution_owner:projection services | component:prepared-state |
| execution_owner:queue owners | component:bounded-reconciliation |
| execution_owner:recovery services | component:recovery-state |
| execution_owner:release apply stage | component:atomic-promotion |
| execution_owner:release services | component:release-state |
| execution_owner:release subprocess | component:release-staging, component:release-subprocess |
| execution_owner:release validation stage | component:post-switch-health |
| execution_owner:release-dist workflow | component:github-release |
| execution_owner:restore services | component:restore-preview |
| execution_owner:rollback stage | component:last-known-good |
| execution_owner:scanner subprocess group | component:scanner-adapters |
| execution_owner:security services | component:security-coordinator, component:security-state |
| execution_owner:separate processes | component:agent-recovery |
| execution_owner:tailscaled | component:tailscale, component:tailscaled |
| execution_owner:worker and workflow projection subprocess | component:workflow-execution |
| owner:Application runtime | component:proot-ubuntu |
| owner:Apps and Recovery | component:app-recovery-update |
| owner:Apps and workflows | component:app-workflow-state |
| owner:Apps domain | component:app-catalog, component:media-app-health |
| owner:Apps execution | component:app-lifecycle-worker |
| owner:Browser | component:browser |
| owner:Command lifecycle | component:command-lifecycle |
| owner:Device execution | component:agent-command-executor |
| owner:Device recovery | component:agent-recovery, component:agent-supervisor |
| owner:Device runtime | component:agent-signals, component:node-agent |
| owner:Evidence services | component:completion-evidence |
| owner:Execution plane | component:worker |
| owner:Fleet and Recovery | component:retirement-database-recovery |
| owner:Fleet domain | component:device-state |
| owner:Fleet onboarding | component:invite-state |
| owner:Lite API | component:api-guards, component:api-read-surfaces, component:lite-api, component:remote-readiness |
| owner:Lite API domains | component:api-domain-surfaces |
| owner:Lite UI | component:frontend-state, component:pwa |
| owner:Lite control plane store | component:sqlite |
| owner:Managed application | component:photoprism |
| owner:Messaging backbone | component:nats-jetstream |
| owner:NATS runtime | component:nats-listeners |
| owner:Prepared projections | component:projection-subprocesses |
| owner:Private network | component:lan |
| owner:Projection subsystem | component:prepared-state |
| owner:Recovery domain | component:recovery-state |
| owner:Recovery execution | component:backup-engine, component:restore-preview |
| owner:Recovery maintenance | component:checkpoints-retention |
| owner:Release engineering | component:release-artifacts |
| owner:Release recovery | component:last-known-good |
| owner:Release runtime | component:atomic-promotion, component:release-staging, component:release-subprocess |
| owner:Release system | component:release-state |
| owner:Release validation | component:post-switch-health |
| owner:Release workflow | component:github-release |
| owner:Remote access | component:tailscale |
| owner:Remote access runtime | component:tailscaled |
| owner:Repository maintainers | component:github-repository |
| owner:Runtime process management | component:pm2 |
| owner:Same-origin access | component:caddy |
| owner:Schedulers and stores | component:bounded-reconciliation |
| owner:Security domain | component:security-coordinator, component:security-state |
| owner:Security execution | component:scanner-adapters |
| owner:Security policy | component:security-profiles |
| owner:User | component:user |
| owner:Workflow engine | component:workflow-execution |
| recovery_owner:App lifecycle worker | component:photoprism, component:proot-ubuntu |
| recovery_owner:App repair | component:media-app-health |
| recovery_owner:App worker | component:app-catalog |
| recovery_owner:Browser reload / service-worker update | component:browser |
| recovery_owner:Checkpoint / rollback | component:app-recovery-update |
| recovery_owner:Checkpoint rollback | component:restore-preview |
| recovery_owner:Command reconciliation | component:agent-command-executor |
| recovery_owner:Database backup/restore | component:sqlite |
| recovery_owner:Discard staging / backoff | component:release-staging |
| recovery_owner:Domain worker / supervisor | component:api-domain-surfaces |
| recovery_owner:Durable-consumer watchdog / PM2 | component:worker |
| recovery_owner:Error boundaries and browser reload | component:pwa |
| recovery_owner:Explicit repair/rejoin | component:api-guards, component:invite-state |
| recovery_owner:Explicit repair/rejoin or database restore | component:retirement-database-recovery |
| recovery_owner:Explicit retirement / repair | component:device-state |
| recovery_owner:Explicit retry | component:security-profiles |
| recovery_owner:Last-known-good rollback | component:release-subprocess |
| recovery_owner:Network owner | component:lan |
| recovery_owner:Owning domain | component:completion-evidence |
| recovery_owner:PM2 after NATS/SQLite verification | component:lite-api |
| recovery_owner:PM2 plus supervisors | component:pm2 |
| recovery_owner:Projection reconciliation | component:prepared-state |
| recovery_owner:Projection scheduler | component:projection-subprocesses |
| recovery_owner:Projection scheduler and owning workers | component:api-read-surfaces |
| recovery_owner:Reconciliation | component:app-workflow-state, component:command-lifecycle |
| recovery_owner:Reconciliation loops | component:bounded-reconciliation |
| recovery_owner:Reconnect watchdog | component:agent-signals |
| recovery_owner:Reconnect watchdog and supervisor | component:node-agent |
| recovery_owner:Recovery worker | component:backup-engine, component:checkpoints-retention, component:recovery-state |
| recovery_owner:Release workflow | component:release-artifacts |
| recovery_owner:Release workflow rerun/fix | component:github-release |
| recovery_owner:Repository maintainers | component:github-repository |
| recovery_owner:Rollback | component:atomic-promotion, component:post-switch-health, component:release-state |
| recovery_owner:Security maintenance / retry | component:security-state |
| recovery_owner:Security maintenance / worker recovery | component:security-coordinator |
| recovery_owner:Self | component:last-known-good |
| recovery_owner:Self / PM2 | component:agent-supervisor |
| recovery_owner:Startup scripts | component:tailscale |
| recovery_owner:Startup scripts / PM2 | component:caddy, component:nats-jetstream |
| recovery_owner:TanStack revalidation and UI workflows | component:frontend-state |
| recovery_owner:User | component:user |
| recovery_owner:Worker cleanup / retry | component:scanner-adapters |
| recovery_owner:Worker retry / repair | component:app-lifecycle-worker |
| recovery_owner:Workflow reconciliation | component:workflow-execution |
| recovery_owner:agent/supervisor | component:agent-recovery |
| recovery_owner:startup scripts | component:nats-listeners, component:tailscaled |
| recovery_owner:startup scripts / user guidance | component:remote-readiness |
| runtime_owner:Browser | component:browser, component:frontend-state, component:pwa, component:user |
| runtime_owner:FastAPI and workers | component:sqlite |
| runtime_owner:GitHub | component:github-repository |
| runtime_owner:GitHub Actions | component:github-release |
| runtime_owner:Lite API | component:invite-state |
| runtime_owner:Lite API / worker | component:media-app-health |
| runtime_owner:Lite UI / Lite API | component:app-catalog |
| runtime_owner:Network | component:lan |
| runtime_owner:PM2 | component:agent-supervisor, component:app-lifecycle-worker, component:caddy, component:lite-api, component:nats-jetstream, component:node-agent, component:pm2, component:worker |
| runtime_owner:PM2 / PROot Ubuntu | component:photoprism |
| runtime_owner:Recovery worker | component:recovery-state |
| runtime_owner:Release subprocess | component:release-state |
| runtime_owner:Release workflow | component:release-artifacts |
| runtime_owner:Security worker | component:security-state |
| runtime_owner:agent and supervisor | component:agent-recovery |
| runtime_owner:lite_control_plane_store | component:device-state |
| runtime_owner:node agent | component:agent-command-executor, component:agent-signals |
| runtime_owner:pocket-api | component:api-domain-surfaces, component:api-guards, component:api-read-surfaces, component:remote-readiness |
| runtime_owner:pocket-api / pocket-worker | component:bounded-reconciliation, component:command-lifecycle, component:retirement-database-recovery, component:security-coordinator |
| runtime_owner:pocket-api and subprocesses | component:projection-subprocesses |
| runtime_owner:pocket-nats | component:nats-listeners |
| runtime_owner:pocket-worker | component:app-recovery-update, component:backup-engine, component:checkpoints-retention, component:release-staging, component:release-subprocess, component:restore-preview, component:scanner-adapters, component:security-profiles, component:workflow-execution |
| runtime_owner:proot-distro | component:proot-ubuntu |
| runtime_owner:release subprocess | component:atomic-promotion, component:last-known-good, component:post-switch-health |
| runtime_owner:scheduler / subprocesses | component:prepared-state |
| runtime_owner:startup scripts | component:tailscaled |
| runtime_owner:tailscaled | component:tailscale |
| runtime_owner:worker / FastAPI | component:completion-evidence |
| runtime_owner:workers | component:app-workflow-state |
