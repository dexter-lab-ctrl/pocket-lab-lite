---
title: "Restore preview and confirmed restore"
description: "Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health."
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

# Restore preview and confirmed restore

Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/recovery.svg" alt="" loading="lazy" decoding="async" /><span>Recovery</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/backup.svg" alt="" loading="lazy" decoding="async" /><span>Backup</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/restore-preview.light.svg" aria-label="Open full-size Restore preview and confirmed restore mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/restore-preview.light.svg" alt="Restore preview and confirmed restore mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/restore-preview.dark.svg" alt="Restore preview and confirmed restore mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Restore preview and confirmed restore mini architecture. <a href="../../../../../assets/diagrams/production/components/restore-preview.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Builds a non-destructive preview, requires explicit confirmation, creates a checkpoint, applies restore, and validates health. |
| Primary inputs | Backup selection, confirmation |
| Primary outputs | preview, restore result |
| Protocols / uses | NATS, SQLite, filesystem |
| Evidence | preview and restore receipt |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Recovery worker |
| Started / runtime owner | pocket-worker |
| Process owner | restore services |
| Execution owner | Recovery execution |
| Data owner | Recovery operations and backup repository |
| Recovery owner | Checkpoint rollback |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-recovery |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | semantic-backup |

## Inputs

- Backup selection
- confirmation

## Outputs

- preview
- restore result

## Protocols

- NATS
- SQLite
- filesystem

## Durable state

- recovery_operations

## Health and readiness

- post-restore API health

## Evidence

- preview and restore receipt

## Failure behavior

- preview unsafe
- health failed

## Recovery behavior

- checkpoint rollback

## Connections

### Incoming

- Backup and verification engine — verified backup input

### Outgoing

- updates restore state — Backup, restore, and checkpoint state
- creates checkpoint before apply — Checkpoints and retention policy

## Source verification

- `route` — `POST /api/lite/recovery/restore/preview`
- `route` — `POST /api/lite/recovery/restore`
- `contract` — `contracts/generated/recovery-contract.json`

## Existing documentation

- [recovery.md](../../recovery.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
