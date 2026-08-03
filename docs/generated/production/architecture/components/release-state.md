---
title: "Installed release and runtime state"
description: "Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state."
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

# Installed release and runtime state

Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/release-state.light.svg" aria-label="Open full-size Installed release and runtime state mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/release-state.light.svg#only-light" alt="Installed release and runtime state mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/release-state.dark.svg#only-dark" alt="Installed release and runtime state mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Installed release and runtime state mini architecture. <a href="../../../../../assets/diagrams/production/components/release-state.light.svg">View full-size diagram</a></figcaption>
</figure>


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

- [Release subprocess and atomic rollback](../release-rollback.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
