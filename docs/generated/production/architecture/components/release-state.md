---
title: "Installed release and runtime state"
description: "Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state."
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

# Installed release and runtime state

Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/durable-state.svg" alt="" loading="lazy" decoding="async" /><span>Durable state</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/release-state.light.svg" aria-label="Open full-size Installed release and runtime state mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/release-state.light.svg" alt="Installed release and runtime state mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/release-state.dark.svg" alt="Installed release and runtime state mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Installed release and runtime state mini architecture. <a href="../../../../../assets/diagrams/production/components/release-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state. |
| Primary inputs | verified release lifecycle |
| Primary outputs | release summary |
| Protocols / uses | SQLite |
| Evidence | release stage evidence |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite |
| Started / runtime owner | Release subprocess |
| Process owner | release services |
| Execution owner | Release system |
| Data owner | SQLite |
| Recovery owner | Rollback |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-durable-state |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- verified release lifecycle

## Outputs

- release summary

## Protocols

- SQLite

## Durable state

- lite_installed_release_identity
- release_runtime_projection

## Health and readiness

- comparison
- artifact verification

## Evidence

- release stage evidence

## Failure behavior

- identity mismatch
- health validation failure

## Recovery behavior

- last-known-good rollback

## Connections

### Incoming

- Post-switch health validation — mark current/failed
- Release subprocess — updates release state

### Outgoing

- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `lite_installed_release_identity`
- `sqlite_table` — `release_runtime_projection`

## Existing documentation

- [release.md](../../release.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Release subprocess and atomic rollback](../release-rollback.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
