---
title: "Backup and verification engine"
description: "Creates and verifies local encrypted backups through backend/worker-owned operations."
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

# Backup and verification engine

Creates and verifies local encrypted backups through backend/worker-owned operations.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/backup.svg" alt="" loading="lazy" decoding="async" /><span>Backup</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/backup-engine.light.svg" aria-label="Open full-size Backup and verification engine mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/backup-engine.light.svg" alt="Backup and verification engine mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/backup-engine.dark.svg" alt="Backup and verification engine mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Backup and verification engine mini architecture. <a href="../../../../../assets/diagrams/production/components/backup-engine.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Creates and verifies local encrypted backups through backend/worker-owned operations. |
| Primary inputs | Backup command |
| Primary outputs | verified backup manifest |
| Protocols / uses | NATS, restic, SQLite |
| Evidence | backup receipt |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Recovery worker |
| Started / runtime owner | pocket-worker |
| Process owner | backup services |
| Execution owner | Recovery execution |
| Data owner | Backup repository and manifest index |
| Recovery owner | Recovery worker |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-backup |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python |

## Inputs

- Backup command

## Outputs

- verified backup manifest

## Protocols

- NATS
- restic
- SQLite

## Durable state

- backup_manifest_index

## Health and readiness

- repository readiness
- verification status

## Evidence

- backup receipt

## Failure behavior

- repository unavailable
- verification failed

## Recovery behavior

- retry
- repair repository

## Connections

### Incoming

- Worker process — runs backup work

### Outgoing

- verified backup input — Restore preview and confirmed restore
- updates backup state — Backup, restore, and checkpoint state
- records sanitized lifecycle — Completion and audit evidence

## Source verification

- `route` — `POST /api/lite/recovery/backup`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup.py`
- `nats_subject` — `pocketlab.commands.lite.backup.create`

## Existing documentation

- [recovery.md](../../recovery.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Backup and restore](../backup-recovery.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
