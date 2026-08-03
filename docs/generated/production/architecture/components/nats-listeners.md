---
title: "Primary and secondary NATS listeners"
description: "Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses."
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

# Primary and secondary NATS listeners

Exposes local and verified Tailnet-reachable NATS listeners for agents without hardcoding credentials or addresses.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/nats-listeners.light.svg" aria-label="Open full-size Primary and secondary NATS listeners mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/nats-listeners.light.svg#only-light" alt="Primary and secondary NATS listeners mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/nats-listeners.dark.svg#only-dark" alt="Primary and secondary NATS listeners mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Primary and secondary NATS listeners mini architecture. <a href="../../../../../assets/diagrams/production/components/nats-listeners.light.svg">View full-size diagram</a></figcaption>
</figure>


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
