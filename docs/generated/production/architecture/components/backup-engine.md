---
title: "Backup and verification engine"
description: "Creates and verifies local encrypted backups through backend/worker-owned operations."
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

# Backup and verification engine

Creates and verifies local encrypted backups through backend/worker-owned operations.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/backup-engine.light.svg" aria-label="Open full-size Backup and verification engine mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/backup-engine.light.svg#only-light" alt="Backup and verification engine mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/backup-engine.dark.svg#only-dark" alt="Backup and verification engine mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Backup and verification engine mini architecture. <a href="../../../../../assets/diagrams/production/components/backup-engine.light.svg">View full-size diagram</a></figcaption>
</figure>


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
