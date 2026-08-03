---
title: "Caddy same-origin proxy"
description: "Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets."
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

# Caddy same-origin proxy

Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets.

![Caddy same-origin proxy mini architecture](../../../../assets/diagrams/production/components/caddy.light.svg#only-light)
![Caddy same-origin proxy mini architecture](../../../../assets/diagrams/production/components/caddy.dark.svg#only-dark)

The mini diagram deterministically collapses **1** additional connections.


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | proxy |
| Runs on | Server host |
| Started / runtime owner | PM2 |
| Process owner | caddy-proxy |
| Execution owner | Same-origin access |
| Data owner | None |
| Recovery owner | Startup scripts / PM2 |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- HTTPS requests

## Outputs

- Static PWA
- FastAPI requests
- managed app routes

## Protocols

- HTTPS
- HTTP reverse proxy

## Durable state

- None declared

## Health and readiness

- Caddy validation
- route probes

## Evidence

- None declared

## Failure behavior

- route unavailable
- certificate unavailable

## Recovery behavior

- regenerate validated config
- bounded PM2 restart

## Connections

### Incoming

- Atomic PWA promotion — serves active PWA
- Local LAN — local HTTPS
- React / Vite PWA — same-origin request
- Tailscale remote access — Tailnet HTTPS

### Outgoing

- routes /api/lite/* — FastAPI /api/lite/*
- same-origin /apps path — PhotoPrism

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh`
- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/restart-caddy-proxy.sh`

## Existing documentation

- [caddy-access.md](../../caddy-access.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Frontend state ownership](../frontend-state.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Release subprocess and atomic rollback](../release-rollback.md)
- [Request and control flow](../request-control.md)
- [Runtime and PM2 process topology](../runtime-topology.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
