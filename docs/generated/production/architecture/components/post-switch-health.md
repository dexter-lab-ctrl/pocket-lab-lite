---
title: "Post-switch health validation"
description: "Validates Caddy/FastAPI/PWA health after promotion before declaring the release current."
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

# Post-switch health validation

Validates Caddy/FastAPI/PWA health after promotion before declaring the release current.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/health.svg" alt="" loading="lazy" decoding="async" /><span>Health and readiness</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/post-switch-health.light.svg" aria-label="Open full-size Post-switch health validation mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/post-switch-health.light.svg" alt="Post-switch health validation mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/post-switch-health.dark.svg" alt="Post-switch health validation mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Post-switch health validation mini architecture. <a href="../../../../../assets/diagrams/production/components/post-switch-health.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Validates Caddy/FastAPI/PWA health after promotion before declaring the release current. |
| Primary inputs | Promoted release |
| Primary outputs | healthy/current or rollback trigger |
| Protocols / uses | HTTP |
| Evidence | post-switch health |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | decision |
| Runs on | Release subprocess against local services |
| Started / runtime owner | release subprocess |
| Process owner | release validation stage |
| Execution owner | Release validation |
| Data owner | Release runtime state |
| Recovery owner | Rollback |
| Security boundary | Server-host boundary |
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

- Promoted release

## Outputs

- healthy/current or rollback trigger

## Protocols

- HTTP

## Durable state

- release_runtime_projection

## Health and readiness

- /health
- /ready

## Evidence

- post-switch health

## Failure behavior

- health gate fails

## Recovery behavior

- rollback immediately

## Connections

### Incoming

- Atomic PWA promotion — validate switched release

### Outgoing

- mark current/failed — Installed release and runtime state
- failure trigger — Last-known-good state and rollback

## Source verification

- `route` — `GET /health`
- `route` — `GET /ready`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
