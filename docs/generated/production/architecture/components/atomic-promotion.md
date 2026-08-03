---
title: "Atomic PWA promotion"
description: "Promotes a verified staged PWA atomically and keeps the previous release available for rollback."
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

# Atomic PWA promotion

Promotes a verified staged PWA atomically and keeps the previous release available for rollback.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/atomic-promotion.light.svg" aria-label="Open full-size Atomic PWA promotion mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/atomic-promotion.light.svg#only-light" alt="Atomic PWA promotion mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/atomic-promotion.dark.svg#only-dark" alt="Atomic PWA promotion mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Atomic PWA promotion mini architecture. <a href="../../../../../assets/diagrams/production/components/atomic-promotion.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Promotes a verified staged PWA atomically and keeps the previous release available for rollback. |
| Primary inputs | Verified stage |
| Primary outputs | New active PWA |
| Protocols / uses | Filesystem atomic rename |
| Evidence | promotion result |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Server host |
| Started / runtime owner | release subprocess |
| Process owner | release apply stage |
| Execution owner | Release runtime |
| Data owner | Active and staged PWA directories |
| Recovery owner | Rollback |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-release |

## Inputs

- Verified stage

## Outputs

- New active PWA

## Protocols

- Filesystem atomic rename

## Durable state

- lite_installed_release_identity

## Health and readiness

- active release identity

## Evidence

- promotion result

## Failure behavior

- promotion failure

## Recovery behavior

- retain previous active release

## Connections

### Incoming

- Release subprocess — apply
- Last-known-good state and rollback — restore prior PWA

### Outgoing

- serves active PWA — Caddy same-origin proxy
- validate switched release — Post-switch health validation

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
