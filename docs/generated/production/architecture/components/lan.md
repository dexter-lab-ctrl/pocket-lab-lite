---
title: "Local LAN"
description: "Provides local-device access to the same-origin Caddy endpoint without hardcoded addresses."
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

# Local LAN

Provides local-device access to the same-origin Caddy endpoint without hardcoded addresses.

> This component is represented in domain diagrams; a dedicated mini diagram is intentionally omitted.


## Function and use

| Field | Value |
| --- | --- |
| Function | Provides local-device access to the same-origin Caddy endpoint without hardcoded addresses. |
| Primary inputs | Browser traffic |
| Primary outputs | Caddy connectivity |
| Protocols / uses | TCP/IP, HTTPS |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | network |
| Runs on | Private local network |
| Started / runtime owner | Network |
| Process owner | Network stack |
| Execution owner | Private network |
| Data owner | None |
| Recovery owner | Network owner |
| Security boundary | Private network and Tailnet boundary |
| Supported platforms | Private LAN |
| Verification | verified |
| Architecture icon | infra-network |

## Inputs

- Browser traffic

## Outputs

- Caddy connectivity

## Protocols

- TCP/IP
- HTTPS

## Durable state

- None declared

## Health and readiness

- route reachability

## Evidence

- None declared

## Failure behavior

- None declared

## Recovery behavior

- None declared

## Connections

### Incoming

- None declared

### Outgoing

- local HTTPS — Caddy same-origin proxy

## Source verification

- `path` — `docs/generated/production/caddy-access.md`

## Existing documentation

- [caddy-access.md](../../caddy-access.md)

## Related architecture views

- [Network and trust boundaries](../network-boundaries.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
