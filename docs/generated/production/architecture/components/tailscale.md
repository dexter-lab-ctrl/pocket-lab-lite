---
title: "Tailscale remote access"
description: "Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner."
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

# Tailscale remote access

Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/tailscale.svg" alt="" loading="lazy" decoding="async" /><span>Tailscale</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/tailscale.light.svg" aria-label="Open full-size Tailscale remote access mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/tailscale.light.svg" alt="Tailscale remote access mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/tailscale.dark.svg" alt="Tailscale remote access mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Tailscale remote access mini architecture. <a href="../../../../../assets/diagrams/production/components/tailscale.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner. |
| Primary inputs | Tailnet identity |
| Primary outputs | Tailnet IPv4, private reachability |
| Protocols / uses | WireGuard/Tailscale |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | network |
| Runs on | Server host and joined devices |
| Started / runtime owner | tailscaled |
| Process owner | tailscaled |
| Execution owner | Remote access |
| Data owner | Tailscale local state |
| Recovery owner | Startup scripts |
| Security boundary | Private network and Tailnet boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | brand-tailscale |
| Icon class | brand |
| Icon upstream | Tailscale |
| Icon source revision | simple-icons-16.28.0 |
| Icon license | Simple-Icons-CC0 |
| Icon trademark note | Tailscale and its logo may be trademarks of Tailscale; descriptive use only and no endorsement implied. |
| Technology markers | None |

## Inputs

- Tailnet identity

## Outputs

- Tailnet IPv4
- private reachability

## Protocols

- WireGuard/Tailscale

## Durable state

- None declared

## Health and readiness

- Tailnet IPv4
- peer reachability

## Evidence

- None declared

## Failure behavior

- tailscaled stopped
- no Tailnet IP

## Recovery behavior

- safe startup
- readiness guidance

## Connections

### Incoming

- tailscaled daemon — provides interface

### Outgoing

- Tailnet HTTPS — Caddy same-origin proxy
- Tailnet reachability — Primary and secondary NATS listeners

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-tailscale.sh`
- `route` — `GET /api/lite/remote-access/readiness`

## Existing documentation

- [remote-access.md](../../remote-access.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Network and trust boundaries](../network-boundaries.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
