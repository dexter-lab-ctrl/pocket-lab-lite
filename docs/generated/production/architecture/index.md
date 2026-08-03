---
title: "Pocket Lab Lite Architecture"
description: "Generated Production architecture from one canonical, source-verified model."
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

# Pocket Lab Lite Architecture

## Pocket Lab Lite in one view

![Complete Pocket Lab Lite system map](../../../assets/diagrams/production/views/complete-system.light.svg#only-light)
![Complete Pocket Lab Lite system map](../../../assets/diagrams/production/views/complete-system.dark.svg#only-dark)


```text
React/Vite PWA
→ Caddy
→ FastAPI /api/lite/*
→ NATS/JetStream
→ worker / agent / supervisor
→ lifecycle events / evidence / heartbeats
→ FastAPI prepared projections
→ PWA
```

## Generated architecture facts

| Measure | Count |
| --- | ---: |
| Components | 56 |
| Connections | 93 |
| Trust boundaries | 9 |
| Domain views | 15 |
| Component mini diagrams | 52 |
| Verified source references | 136 |

**Architecture source fingerprint:** `70e1e3dd1be588ab4eada0a05875282ebd5daa117f0b647e4f50d7977fccef16`

**Repository source inventory fingerprint:** `f7a48d8d77f5c8bdd87b998647924c5f09f66c7825c02d23807fa673c9f705e3`

## Operational guarantees

- Frontend never talks directly to NATS.
- Frontend never executes shell commands.
- FastAPI remains the control API.
- Agents and supervisors own execution and recovery.
- Bootstrap scripts are backend-generated.
- Secrets are not exposed.
- Offline enrolled devices remain represented.
- Lifecycle changes produce audit evidence.
- Read APIs remain side-effect-free.
- Startup scripts own safe startup side effects.

## Trust-boundary summary

- **Application-container boundary** — PROot Ubuntu and managed application runtime.
- **Browser trust boundary** — User device, browser, PWA, and safe local frontend state.
- **Control API boundary** — FastAPI validation, side-effect-free reads, and command admission.
- **Durable-state boundary** — SQLite canonical state, indexes, revisions, and prepared projections.
- **External release boundary** — GitHub source and immutable release assets.
- **Managed-device boundary** — Joined-device PM2 agent/supervisor runtime.
- **Messaging and execution boundary** — NATS/JetStream, workers, subprocesses, queues, and lifecycle execution.
- **Server-host boundary** — Android/Termux or Ubuntu host processes and local networking.
- **Private network and Tailnet boundary** — LAN and Tailscale private connectivity.

## Architecture views

- [Complete Pocket Lab Lite system map](complete-system.md)
- [App Catalog lifecycle](apps.md)
- [Audit and evidence flow](audit-evidence.md)
- [Backup and restore](backup-recovery.md)
- [Command acknowledgement and reconciliation](command-reconciliation.md)
- [Device onboarding](device-onboarding.md)
- [Devices and offline recovery](device-recovery.md)
- [Frontend state ownership](frontend-state.md)
- [Network and trust boundaries](network-boundaries.md)
- [Release subprocess and atomic rollback](release-rollback.md)
- [Request and control flow](request-control.md)
- [Runtime and PM2 process topology](runtime-topology.md)
- [SQLite and projection architecture](data-projections.md)
- [Security and safety](security.md)
- [Tailscale readiness](remote-access.md)

## Component catalog

Open the [generated component catalog](component-catalog.md) for ownership, runtime placement, health signals, evidence, source verification, and per-component mini diagrams.
