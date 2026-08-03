---
title: "Caddy same-origin proxy"
description: "Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 13dae80367ddf3ba183f4f77c57075516b1e463d27336c7aa834c23b5cce75a2
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Caddy same-origin proxy

Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/caddy.light.svg" aria-label="Open full-size Caddy same-origin proxy mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/caddy.light.svg#only-light" alt="Caddy same-origin proxy mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/caddy.dark.svg#only-dark" alt="Caddy same-origin proxy mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Caddy same-origin proxy mini architecture. <a href="../../../../../assets/diagrams/production/components/caddy.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **1** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Serves the PWA and routes /api/lite/* and managed app paths without exposing backend secrets. |
| Primary inputs | HTTPS requests |
| Primary outputs | Static PWA, FastAPI requests, managed app routes |
| Protocols / uses | HTTPS, HTTP reverse proxy |
| Evidence | None |

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
| Architecture icon | infra-caddy |

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
