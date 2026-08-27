---
title: "Primary and secondary NATS listeners"
description: "Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: f82d3e269a91212087e920fb458fe3869473b363b8e0a4874489074018141ec5
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Primary and secondary NATS listeners

Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/network.svg" alt="" loading="lazy" decoding="async" /><span>Network</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/nats.svg" alt="" loading="lazy" decoding="async" /><span>NATS</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/nats-listeners.light.svg" aria-label="Open full-size Primary and secondary NATS listeners mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/nats-listeners.light.svg" alt="Primary and secondary NATS listeners mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/nats-listeners.dark.svg" alt="Primary and secondary NATS listeners mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Primary and secondary NATS listeners mini architecture. <a href="../../../../../assets/diagrams/production/components/nats-listeners.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses. |
| Primary inputs | Generated listener config |
| Primary outputs | Primary and secondary agent connectivity |
| Protocols / uses | NATS/TCP |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | network |
| Runs on | Server host |
| Started / runtime owner | pocket-nats |
| Process owner | NATS server |
| Execution owner | NATS runtime |
| Data owner | NATS configuration |
| Recovery owner | startup scripts |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-network |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-nats |

## Inputs

- Generated listener config

## Outputs

- Primary and secondary agent connectivity

## Protocols

- NATS/TCP

## Durable state

- None declared

## Health and readiness

- local listener
- Tailnet listener reachability

## Evidence

- None declared

## Failure behavior

- listener bound incorrectly

## Recovery behavior

- regenerate config
- verify connectivity

## Connections

### Incoming

- Tailscale remote access — Tailnet reachability

### Outgoing

- listener endpoints — NATS / JetStream
- listener reachability — Remote-access readiness checks

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh`

## Existing documentation

- [remote-access.md](../../remote-access.md)

## Related architecture views

- [Network and trust boundaries](../network-boundaries.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
