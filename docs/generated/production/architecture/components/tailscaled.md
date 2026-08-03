---
title: "tailscaled daemon"
description: "Owns Tailscale networking; startup scripts may detect/start it safely while read APIs remain side-effect-free."
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

# tailscaled daemon

Owns Tailscale networking; startup scripts may detect/start it safely while read APIs remain side-effect-free.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/tailscaled.light.svg" aria-label="Open full-size tailscaled daemon mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/tailscaled.light.svg#only-light" alt="tailscaled daemon mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/tailscaled.dark.svg#only-dark" alt="tailscaled daemon mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>tailscaled daemon mini architecture. <a href="../../../../../assets/diagrams/production/components/tailscaled.light.svg">View full-size diagram</a></figcaption>
</figure>


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Android/Termux server host |
| Started / runtime owner | startup scripts |
| Process owner | tailscaled |
| Execution owner | Remote access runtime |
| Data owner | Local Tailscale state |
| Recovery owner | startup scripts |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- Tailscale configuration

## Outputs

- Tailnet interface/IP

## Protocols

- Tailscale

## Durable state

- None declared

## Health and readiness

- daemon state

## Evidence

- None declared

## Failure behavior

- daemon unavailable

## Recovery behavior

- start when safe

## Connections

### Incoming

- None declared

### Outgoing

- daemon status — Remote-access readiness checks
- provides interface — Tailscale remote access

## Source verification

- `path` — `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-tailscale.sh`

## Existing documentation

- [remote-access.md](../../remote-access.md)

## Related architecture views

- [Network and trust boundaries](../network-boundaries.md)
- [Runtime and PM2 process topology](../runtime-topology.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
