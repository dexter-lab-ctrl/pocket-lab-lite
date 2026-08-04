---
title: "Remote-access readiness checks"
description: "Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance."
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

# Remote-access readiness checks

Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/health.svg" alt="" loading="lazy" decoding="async" /><span>Health and readiness</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/remote-readiness.light.svg" aria-label="Open full-size Remote-access readiness checks mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/remote-readiness.light.svg" alt="Remote-access readiness checks mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/remote-readiness.dark.svg" alt="Remote-access readiness checks mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Remote-access readiness checks mini architecture. <a href="../../../../../assets/diagrams/production/components/remote-readiness.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance. |
| Primary inputs | Tailscale and NATS posture |
| Primary outputs | Ready or Remote access not ready |
| Protocols / uses | HTTP JSON |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | decision |
| Runs on | FastAPI read surface |
| Started / runtime owner | pocket-api |
| Process owner | FastAPI |
| Execution owner | Lite API |
| Data owner | Prepared status |
| Recovery owner | startup scripts / user guidance |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-health |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- Tailscale and NATS posture

## Outputs

- Ready or Remote access not ready

## Protocols

- HTTP JSON

## Durable state

- None declared

## Health and readiness

- readiness reasons

## Evidence

- None declared

## Failure behavior

- remote unavailable

## Recovery behavior

- truthful guidance
- safe startup side effects outside reads

## Connections

### Incoming

- Primary and secondary NATS listeners — listener reachability
- tailscaled daemon — daemon status

### Outgoing

- readiness summary — Prepared read, health, readiness, diagnostics, and evidence APIs

## Source verification

- `route` — `GET /api/lite/remote-access/readiness`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_status.py`

## Existing documentation

- [remote-access.md](../../remote-access.md)

## Related architecture views

- [Network and trust boundaries](../network-boundaries.md)
- [Tailscale readiness](../remote-access.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
