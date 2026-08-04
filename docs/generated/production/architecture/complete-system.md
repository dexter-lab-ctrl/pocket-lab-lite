---
title: "Complete Pocket Lab Lite system map"
description: "Executive poster of the verified experience, control plane, event execution, durable state, device runtime, remote access, apps, and release flow."
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

# Complete Pocket Lab Lite system map

Executive poster of the verified experience, control plane, event execution, durable state, device runtime, remote access, apps, and release flow.

## Executive summary

<div class="pl-architecture-summary-grid"><article class="pl-architecture-summary-card"><span class="pl-architecture-icon pl-architecture-icon--summary pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/react.svg" alt="" loading="lazy" decoding="async" /><span>React</span></span><h3>Self-hosted workspace</h3><p>React/Vite PWA with safe saved summaries</p></article><article class="pl-architecture-summary-card"><span class="pl-architecture-icon pl-architecture-icon--summary pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/fastapi.svg" alt="" loading="lazy" decoding="async" /><span>FastAPI</span></span><h3>FastAPI control plane</h3><p>Validated reads, guards, and command admission</p></article><article class="pl-architecture-summary-card"><span class="pl-architecture-icon pl-architecture-icon--summary pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/nats.svg" alt="" loading="lazy" decoding="async" /><span>NATS</span></span><h3>NATS event backbone</h3><p>Durable command, event, and heartbeat transport</p></article><article class="pl-architecture-summary-card"><span class="pl-architecture-icon pl-architecture-icon--summary pl-architecture-icon--semantic"><img src="../../../../assets/diagrams/production/icons/evidence.svg" alt="" loading="lazy" decoding="async" /><span>Evidence</span></span><h3>Auditable evidence</h3><p>Sanitized lifecycle evidence and prepared projections</p></article><article class="pl-architecture-summary-card"><span class="pl-architecture-icon pl-architecture-icon--summary pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/android.svg" alt="" loading="lazy" decoding="async" /><span>Android</span></span><h3>Android/Termux edge</h3><p>PM2-managed agents and supervisor recovery</p></article><article class="pl-architecture-summary-card"><span class="pl-architecture-icon pl-architecture-icon--summary pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/tailscale.svg" alt="" loading="lazy" decoding="async" /><span>Tailscale</span></span><h3>Private remote access</h3><p>Tailscale and same-origin Caddy routes</p></article></div>

## Six architecture zones

<div class="pl-architecture-zone-grid"><article class="pl-architecture-zone-card"><h3>Zone A — Experience</h3><p>User interaction, safe read-state presentation, offline-safe summaries, UI-only coordination, and guided workflow presentation.</p><p class="pl-architecture-zone-card__members"><strong>Includes:</strong> User, Browser, React / Vite PWA, Frontend state ownership</p></article><article class="pl-architecture-zone-card"><h3>Zone B — Control plane</h3><p>Caddy and FastAPI validate, guard, route, admit commands, and serve prepared reads.</p><p class="pl-architecture-zone-card__members"><strong>Includes:</strong> Caddy same-origin proxy, FastAPI /api/lite/*, Fleet, Apps, Security, Recovery, and Release APIs, Prepared read, health, readiness, diagnostics, and evidence APIs, Identity, authentication, and invite guards, App Catalog, Security scan coordinator</p></article><article class="pl-architecture-zone-card"><h3>Zone C — Event and execution</h3><p>NATS/JetStream transports bounded work; workers and executors own lifecycle execution and evidence.</p><p class="pl-architecture-zone-card__members"><strong>Includes:</strong> NATS / JetStream, Worker process, Command admission and lifecycle, Device command executor, Backup and verification engine, Release subprocess, Completion and audit evidence</p></article><article class="pl-architecture-zone-card"><h3>Zone D — Durable state</h3><p>SQLite and prepared projections preserve canonical device, invite, workflow, security, recovery, release, and app state.</p><p class="pl-architecture-zone-card__members"><strong>Includes:</strong> SQLite control-plane store, Audit index, projection refresh, prepared projections, and domain revisions, Invite and identity lifecycle, Enrollment and device lifecycle state, Backup, restore, and checkpoint state, Security findings and run state, Installed release and runtime state, App, command, and workflow state</p></article><article class="pl-architecture-zone-card"><h3>Zone E — Device runtime</h3><p>PM2, the node agent, supervisor, heartbeats, and recovery watchdog run on low-power Android/Termux or Ubuntu devices.</p><p class="pl-architecture-zone-card__members"><strong>Includes:</strong> PM2 process manager, Lite node agent, Lite agent supervisor, Heartbeat, telemetry, and health publishers, Reconnect watchdog and supervisor recovery</p></article><article class="pl-architecture-zone-card"><h3>Zone F — Remote access and apps</h3><p>Tailscale private access, PROot Ubuntu, PhotoPrism, and immutable GitHub release assets.</p><p class="pl-architecture-zone-card__members"><strong>Includes:</strong> Tailscale remote access, PROot Ubuntu application container, PhotoPrism, GitHub repository, GitHub Release, Date-based Lite tag, dist.zip, checksums, and release manifest</p></article></div>

## Legend and icon key

<ul class="pl-architecture-legend"><li><span class="pl-architecture-legend__mark pl-architecture-legend__mark--brand" aria-hidden="true"></span><span>Brand icon — verified external technology or product</span></li><li><span class="pl-architecture-legend__mark pl-architecture-legend__mark--semantic" aria-hidden="true"></span><span>Semantic icon — internal Pocket Lab Lite role or lifecycle</span></li><li><span class="pl-architecture-legend__mark pl-architecture-legend__mark--solid" aria-hidden="true"></span><span>Solid arrow — request, command, or primary control</span></li><li><span class="pl-architecture-legend__mark pl-architecture-legend__mark--dashed" aria-hidden="true"></span><span>Dashed arrow — health, readiness, or recovery</span></li><li><span class="pl-architecture-legend__mark pl-architecture-legend__mark--dotted" aria-hidden="true"></span><span>Dotted arrow — asynchronous evidence or lifecycle</span></li><li><span class="pl-architecture-legend__mark pl-architecture-legend__mark--boundary" aria-hidden="true"></span><span>Nested band — verified trust boundary</span></li></ul>

The SVG also includes a generated legend. Brand icons identify verified external products; semantic icons identify Pocket Lab Lite roles, state, guards, evidence, recovery, and workflows. Text labels remain authoritative when an icon is unfamiliar or unavailable.

## Primary flows

| Primary flow | Canonical relationships |
| --- | --- |
| 1. User/API request | uses → loads and hosts → same-origin request → routes /api/lite/* → dispatches domain request → publishes validated command → durable delivery |
| 2. Device onboarding | validates identity and intent → stores invite/identity state → backend-generated bootstrap → starts/supervises → starts/supervises |
| 3. Command execution | publishes validated command → durable delivery → claims and updates → delivers device command |
| 4. Evidence and heartbeat return | publishes → heartbeat/telemetry/health → fleet events projected → records sanitized lifecycle → indexes evidence → prepared read → safe summary |
| 5. Supervisor recovery | starts/supervises → stopped-agent recovery → reconnect/restart |
| 6. Release/update | annotated tag workflow → publishes assets → admits release work → records sanitized lifecycle |
| 7. App access | Tailnet HTTPS → app cards and actions → same-origin /apps path → hosts process |
| 8. Safe frontend state | selects and renders → prepared read → safe summary |

## Trust boundaries

- **Browser trust boundary** — User device, browser, PWA, and safe local frontend state.
- **Server-host boundary** — Android/Termux or Ubuntu host processes and local networking.
- **Control API boundary** — FastAPI validation, side-effect-free reads, and command admission.
- **Messaging and execution boundary** — NATS/JetStream, workers, subprocesses, queues, and lifecycle execution.
- **Durable-state boundary** — SQLite canonical state, indexes, revisions, and prepared projections.
- **Managed-device boundary** — Joined-device PM2 agent/supervisor runtime.
- **Private network and Tailnet boundary** — LAN and Tailscale private connectivity.
- **Application-container boundary** — PROot Ubuntu and managed application runtime.
- **External release boundary** — GitHub source and immutable release assets.

## Runtime technology stack

<div class="pl-architecture-icon-key"><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/react.svg" alt="" loading="lazy" decoding="async" /><span>React</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/vite.svg" alt="" loading="lazy" decoding="async" /><span>Vite</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/tanstack.svg" alt="" loading="lazy" decoding="async" /><span>TanStack</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/xstate.svg" alt="" loading="lazy" decoding="async" /><span>XState</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/caddy.svg" alt="" loading="lazy" decoding="async" /><span>Caddy</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/fastapi.svg" alt="" loading="lazy" decoding="async" /><span>FastAPI</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/nats.svg" alt="" loading="lazy" decoding="async" /><span>NATS</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/android.svg" alt="" loading="lazy" decoding="async" /><span>Android</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/pm2.svg" alt="" loading="lazy" decoding="async" /><span>PM2</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/sqlite.svg" alt="" loading="lazy" decoding="async" /><span>SQLite</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/nodejs.svg" alt="" loading="lazy" decoding="async" /><span>Node.js</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/npm.svg" alt="" loading="lazy" decoding="async" /><span>npm</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/tailscale.svg" alt="" loading="lazy" decoding="async" /><span>Tailscale</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/ubuntu.svg" alt="" loading="lazy" decoding="async" /><span>Ubuntu</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/photoprism.svg" alt="" loading="lazy" decoding="async" /><span>PhotoPrism</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/github.svg" alt="" loading="lazy" decoding="async" /><span>GitHub</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../assets/diagrams/production/icons/git.svg" alt="" loading="lazy" decoding="async" /><span>Git</span></span></div>

## Architecture callouts

<div class="pl-architecture-callout-grid"><article class="pl-architecture-callout"><h3>What Pocket Lab Lite guarantees</h3><ul><li>Frontend never talks directly to NATS.</li><li>Frontend never executes shell commands.</li><li>FastAPI remains the control API.</li><li>Agents and supervisors own execution and recovery.</li><li>Bootstrap scripts are backend-generated.</li></ul></article><article class="pl-architecture-callout"><h3>Execution ownership</h3><ul><li>UI presents</li><li>FastAPI validates</li><li>NATS transports</li><li>Workers execute</li><li>Agents act on devices</li><li>Supervisors recover</li><li>SQLite preserves truth</li></ul></article><article class="pl-architecture-callout"><h3>Operational highlights</h3><ul><li>Self-hosted</li><li>Edge-first</li><li>ARM64 friendly</li><li>Private by default</li><li>Recovery-aware</li><li>Evidence-backed</li><li>Offline-safe read summaries</li></ul></article></div>


## Complete-system hero poster

<figure class="pl-architecture-diagram pl-architecture-diagram--system pl-architecture-diagram--wide pl-architecture-diagram--poster">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../assets/diagrams/production/views/complete-system.light.svg" aria-label="Open full-size Complete Pocket Lab Lite system map">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../assets/diagrams/production/views/complete-system.light.svg" alt="Complete Pocket Lab Lite system map" loading="eager" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../assets/diagrams/production/views/complete-system.dark.svg" alt="Complete Pocket Lab Lite system map" loading="eager" decoding="async" />
    </a>
  </div>
  <figcaption>Complete Pocket Lab Lite system map. <a href="../../../../assets/diagrams/production/views/complete-system.light.svg">View full-size diagram</a></figcaption>
</figure>


## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
| [User](components/user.md) | actor | Human user device | Browser | Browser trust boundary |
| [Browser](components/browser.md) | ui | User device | Browser | Browser trust boundary |
| [React / Vite PWA](components/pwa.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Frontend state ownership](components/frontend-state.md) | ui | Browser / installed PWA | Browser | Browser trust boundary |
| [Caddy same-origin proxy](components/caddy.md) | proxy | Server host | PM2 | Server-host boundary |
| [FastAPI /api/lite/*](components/lite-api.md) | service | Server host | PM2 | Control API boundary |
| [Fleet, Apps, Security, Recovery, and Release APIs](components/api-domain-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Prepared read, health, readiness, diagnostics, and evidence APIs](components/api-read-surfaces.md) | service | FastAPI process | pocket-api | Control API boundary |
| [Identity, authentication, and invite guards](components/api-guards.md) | service | FastAPI process | pocket-api | Control API boundary |
| [App Catalog](components/app-catalog.md) | service | PWA plus FastAPI prepared reads | Lite UI / Lite API | Control API boundary |
| [Security scan coordinator](components/security-coordinator.md) | service | FastAPI and worker | pocket-api / pocket-worker | Control API boundary |
| [NATS / JetStream](components/nats-jetstream.md) | event | Server host | PM2 | Messaging and execution boundary |
| [Worker process](components/worker.md) | process | Server host | PM2 | Messaging and execution boundary |
| [Command admission and lifecycle](components/command-lifecycle.md) | process | FastAPI and worker | pocket-api / pocket-worker | Messaging and execution boundary |
| [Device command executor](components/agent-command-executor.md) | process | Node agent | node agent | Managed-device boundary |
| [Backup and verification engine](components/backup-engine.md) | process | Recovery worker | pocket-worker | Messaging and execution boundary |
| [Release subprocess](components/release-subprocess.md) | process | Dedicated subprocess | pocket-worker | Messaging and execution boundary |
| [Completion and audit evidence](components/completion-evidence.md) | event | Worker and FastAPI | worker / FastAPI | Messaging and execution boundary |
| [SQLite control-plane store](components/sqlite.md) | database | Server host | FastAPI and workers | Durable-state boundary |
| [Audit index, projection refresh, prepared projections, and domain revisions](components/prepared-state.md) | database | SQLite | scheduler / subprocesses | Durable-state boundary |
| [Invite and identity lifecycle](components/invite-state.md) | database | SQLite | Lite API | Durable-state boundary |
| [Enrollment and device lifecycle state](components/device-state.md) | database | SQLite | lite_control_plane_store | Durable-state boundary |
| [Backup, restore, and checkpoint state](components/recovery-state.md) | database | SQLite and repository-owned manifests | Recovery worker | Durable-state boundary |
| [Security findings and run state](components/security-state.md) | database | SQLite and compact sanitized files | Security worker | Durable-state boundary |
| [Installed release and runtime state](components/release-state.md) | database | SQLite | Release subprocess | Durable-state boundary |
| [App, command, and workflow state](components/app-workflow-state.md) | database | SQLite | workers | Durable-state boundary |
| [PM2 process manager](components/pm2.md) | process | Server host and joined devices | PM2 | Server-host boundary |
| [Lite node agent](components/node-agent.md) | process | Server host or joined device | PM2 | Managed-device boundary |
| [Lite agent supervisor](components/agent-supervisor.md) | process | Joined device | PM2 | Managed-device boundary |
| [Heartbeat, telemetry, and health publishers](components/agent-signals.md) | event | Node agent | node agent | Managed-device boundary |
| [Reconnect watchdog and supervisor recovery](components/agent-recovery.md) | process | Joined device | agent and supervisor | Managed-device boundary |
| [Tailscale remote access](components/tailscale.md) | network | Server host and joined devices | tailscaled | Private network and Tailnet boundary |
| [PROot Ubuntu application container](components/proot-ubuntu.md) | process | Android/Termux server host | proot-distro | Application-container boundary |
| [PhotoPrism](components/photoprism.md) | external-app | PROot Ubuntu on server host | PM2 / PROot Ubuntu | Application-container boundary |
| [GitHub repository](components/github-repository.md) | external | External source hosting | GitHub | External release boundary |
| [GitHub Release](components/github-release.md) | external | GitHub | GitHub Actions | External release boundary |
| [Date-based Lite tag, dist.zip, checksums, and release manifest](components/release-artifacts.md) | artifact | GitHub Release / staging | Release workflow | External release boundary |

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
| NATS / JetStream | delivers device command | Device command executor | control | NATS |
| Lite node agent | publishes | Heartbeat, telemetry, and health publishers | health | NATS |
| Lite node agent | connection state | Reconnect watchdog and supervisor recovery | health | NATS |
| FastAPI /api/lite/* | dispatches domain request | Fleet, Apps, Security, Recovery, and Release APIs | control | Python |
| FastAPI /api/lite/* | validates identity and intent | Identity, authentication, and invite guards | control | Python |
| Fleet, Apps, Security, Recovery, and Release APIs | publishes validated command | NATS / JetStream | control | NATS |
| FastAPI /api/lite/* | serves safe reads | Prepared read, health, readiness, diagnostics, and evidence APIs | data | Python |
| FastAPI /api/lite/* | transactional read/write | SQLite control-plane store | data | SQLite |
| Browser | loads and hosts | React / Vite PWA | control | Browser runtime |
| Caddy same-origin proxy | routes /api/lite/* | FastAPI /api/lite/* | control | HTTP |
| Caddy same-origin proxy | same-origin /apps path | PhotoPrism | control | HTTP |
| App Catalog | app cards and actions | React / Vite PWA | data | HTTPS |
| App, command, and workflow state | catalog/action projection | App Catalog | data | SQLite |
| Command admission and lifecycle | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Release subprocess | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Security scan coordinator | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Backup and verification engine | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Device command executor | records sanitized lifecycle | Completion and audit evidence | evidence | SQLite/NATS |
| Completion and audit evidence | indexes evidence | Audit index, projection refresh, prepared projections, and domain revisions | data | SQLite |
| Completion and audit evidence | sanitized lookup | Prepared read, health, readiness, diagnostics, and evidence APIs | evidence | HTTP |
| Device command executor | executes within | Lite node agent | control | Python |
| Identity, authentication, and invite guards | backend-generated bootstrap | Lite node agent | control | Shell artifact |
| Invite and identity lifecycle | accepted enrollment | Enrollment and device lifecycle state | data | SQLite |
| NATS / JetStream | fleet events projected | Enrollment and device lifecycle state | data | NATS/SQLite |
| NATS / JetStream | durable delivery | Worker process | control | JetStream |
| PM2 process manager | starts/supervises | Lite node agent | recovery | Local process |
| PM2 process manager | starts app process | PROot Ubuntu application container | recovery | Local process |
| PM2 process manager | starts/supervises | Lite agent supervisor | recovery | Local process |
| PROot Ubuntu application container | hosts process | PhotoPrism | control | Local process |
| React / Vite PWA | same-origin request | Caddy same-origin proxy | control | HTTPS |
| React / Vite PWA | selects and renders | Frontend state ownership | data | React |
| Prepared read, health, readiness, diagnostics, and evidence APIs | safe summary | Frontend state ownership | data | HTTPS |
| Reconnect watchdog and supervisor recovery | reconnect/restart | Lite node agent | recovery | NATS/process |
| GitHub Release | publishes assets | Date-based Lite tag, dist.zip, checksums, and release manifest | data | HTTPS |
| GitHub repository | annotated tag workflow | GitHub Release | control | GitHub Actions |
| Heartbeat, telemetry, and health publishers | heartbeat/telemetry/health | NATS / JetStream | health | NATS |
| Enrollment and device lifecycle state | stored in | SQLite control-plane store | data | SQLite |
| Invite and identity lifecycle | stored in | SQLite control-plane store | data | SQLite |
| App, command, and workflow state | stored in | SQLite control-plane store | data | SQLite |
| Security findings and run state | stored in | SQLite control-plane store | data | SQLite |
| Backup, restore, and checkpoint state | stored in | SQLite control-plane store | data | SQLite |
| Installed release and runtime state | stored in | SQLite control-plane store | data | SQLite |
| Audit index, projection refresh, prepared projections, and domain revisions | stored in | SQLite control-plane store | data | SQLite |
| Identity, authentication, and invite guards | stores invite/identity state | Invite and identity lifecycle | data | SQLite |
| Heartbeat, telemetry, and health publishers | updates device truth | Enrollment and device lifecycle state | data | SQLite |
| Security scan coordinator | updates scan state | Security findings and run state | data | SQLite |
| Backup and verification engine | updates backup state | Backup, restore, and checkpoint state | data | SQLite |
| Release subprocess | updates release state | Installed release and runtime state | data | SQLite |
| Audit index, projection refresh, prepared projections, and domain revisions | prepared read | Prepared read, health, readiness, diagnostics, and evidence APIs | data | SQLite |
| Lite agent supervisor | stopped-agent recovery | Reconnect watchdog and supervisor recovery | recovery | Local process |
| Tailscale remote access | Tailnet HTTPS | Caddy same-origin proxy | control | HTTPS |
| User | uses | Browser | control | HTTPS |
| Worker process | runs backup work | Backup and verification engine | control | Python |
| Worker process | claims and updates | Command admission and lifecycle | control | SQLite/NATS |
| Worker process | admits release work | Release subprocess | control | IPC |
| Worker process | runs security work | Security scan coordinator | control | Python |

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
