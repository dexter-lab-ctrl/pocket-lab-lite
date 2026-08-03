---
title: "Last-known-good state and rollback"
description: "Records the verified prior release and restores it atomically when post-switch validation fails."
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

# Last-known-good state and rollback

Records the verified prior release and restores it atomically when post-switch validation fails.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/last-known-good.light.svg" aria-label="Open full-size Last-known-good state and rollback mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/last-known-good.light.svg#only-light" alt="Last-known-good state and rollback mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/last-known-good.dark.svg#only-dark" alt="Last-known-good state and rollback mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Last-known-good state and rollback mini architecture. <a href="../../../../../assets/diagrams/production/components/last-known-good.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Records the verified prior release and restores it atomically when post-switch validation fails. |
| Primary inputs | Rollback trigger |
| Primary outputs | Restored prior release |
| Protocols / uses | Filesystem atomic switch, SQLite |
| Evidence | rollback status |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Server host / release subprocess |
| Started / runtime owner | release subprocess |
| Process owner | rollback stage |
| Execution owner | Release recovery |
| Data owner | Release SQLite state and prior PWA |
| Recovery owner | Self |
| Security boundary | Server-host boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-release |

## Inputs

- Rollback trigger

## Outputs

- Restored prior release

## Protocols

- Filesystem atomic switch
- SQLite

## Durable state

- lite_installed_release_identity
- release_runtime_projection

## Health and readiness

- last_known_good

## Evidence

- rollback status

## Failure behavior

- rollback failure

## Recovery behavior

- manual recovery guidance

## Connections

### Incoming

- Post-switch health validation — failure trigger

### Outgoing

- restore prior PWA — Atomic PWA promotion

## Source verification

- `route` — `GET /api/lite/release`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`

## Existing documentation

- [rollback.md](../../rollback.md)

## Related architecture views

- [Release subprocess and atomic rollback](../release-rollback.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
