---
title: "Backup, restore, and checkpoint state"
description: "Stores backup manifests, recovery operations, current state, database backups/restores, and restore checkpoints."
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

# Backup, restore, and checkpoint state

Stores backup manifests, recovery operations, current state, database backups/restores, and restore checkpoints.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/durable-state.svg" alt="" loading="lazy" decoding="async" /><span>Durable state</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/recovery-state.light.svg" aria-label="Open full-size Backup, restore, and checkpoint state mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/recovery-state.light.svg" alt="Backup, restore, and checkpoint state mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/recovery-state.dark.svg" alt="Backup, restore, and checkpoint state mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Backup, restore, and checkpoint state mini architecture. <a href="../../../../../assets/diagrams/production/components/recovery-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Stores backup manifests, recovery operations, current state, database backups/restores, and restore checkpoints. |
| Primary inputs | backup/verify/preview/restore lifecycle |
| Primary outputs | recovery projection |
| Protocols / uses | SQLite, restic metadata |
| Evidence | backup and restore receipts |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite and repository-owned manifests |
| Started / runtime owner | Recovery worker |
| Process owner | recovery services |
| Execution owner | Recovery domain |
| Data owner | SQLite / backup repository |
| Recovery owner | Recovery worker |
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

- backup/verify/preview/restore lifecycle

## Outputs

- recovery projection

## Protocols

- SQLite
- restic metadata

## Durable state

- backup_manifest_index
- recovery_operations

## Health and readiness

- repository readiness
- verification state

## Evidence

- backup and restore receipts

## Failure behavior

- verification failed
- restore blocked

## Recovery behavior

- checkpoint
- preview
- explicit confirmation

## Connections

### Incoming

- App backup, restore preview, and update lifecycle — stores manifests/operations
- Backup and verification engine — updates backup state
- Restore preview and confirmed restore — updates restore state

### Outgoing

- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `backup_manifest_index`
- `sqlite_table` — `recovery_current_state`
- `sqlite_table` — `recovery_operations`

## Existing documentation

- [recovery.md](../../recovery.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Backup and restore](../backup-recovery.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
