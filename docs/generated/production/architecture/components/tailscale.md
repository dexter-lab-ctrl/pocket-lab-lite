---
title: "Tailscale remote access"
description: "Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner."
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

# Tailscale remote access

Provides private Tailnet connectivity and HTTPS identity without becoming a browser-held secret or control owner.

![Tailscale remote access mini architecture](../../../../assets/diagrams/production/components/tailscale.light.svg#only-light)
![Tailscale remote access mini architecture](../../../../assets/diagrams/production/components/tailscale.dark.svg#only-dark)


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
