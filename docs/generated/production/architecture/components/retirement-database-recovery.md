---
title: "Explicit retirement and database recovery"
description: "Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion."
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

# Explicit retirement and database recovery

Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/recovery.svg" alt="" loading="lazy" decoding="async" /><span>Recovery</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/retirement-database-recovery.light.svg" aria-label="Open full-size Explicit retirement and database recovery mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/retirement-database-recovery.light.svg" alt="Explicit retirement and database recovery mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/retirement-database-recovery.dark.svg" alt="Explicit retirement and database recovery mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Explicit retirement and database recovery mini architecture. <a href="../../../../../assets/diagrams/production/components/retirement-database-recovery.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Requires assessment and confirmation for device retirement and provides verified database backup/preview/restore without coupling command cleanup to device deletion. |
| Primary inputs | Confirmed retirement/restore |
| Primary outputs | retirement receipt, database restore |
| Protocols / uses | HTTP JSON, NATS, SQLite |
| Evidence | retirement/restore evidence |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | FastAPI / worker |
| Started / runtime owner | pocket-api / pocket-worker |
| Process owner | domain services |
| Execution owner | Fleet and Recovery |
| Data owner | SQLite |
| Recovery owner | Explicit repair/rejoin or database restore |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-recovery |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- Confirmed retirement/restore

## Outputs

- retirement receipt
- database restore

## Protocols

- HTTP JSON
- NATS
- SQLite

## Durable state

- device_removal_receipts
- security_database_backups

## Health and readiness

- dependency assessment
- database verification

## Evidence

- retirement/restore evidence

## Failure behavior

- healthy device removal blocked
- restore verification failed

## Recovery behavior

- cancel
- use verified backup

## Connections

### Incoming

- Checkpoints and retention policy — provides recovery point

### Outgoing

- verified backup/restore — SQLite control-plane store

## Source verification

- `route` — `GET /api/lite/devices/{device_id}/removal-assessment`
- `route` — `POST /api/lite/fleet/remove-device`
- `route` — `POST /api/lite/recovery/database/backup`
- `route` — `POST /api/lite/recovery/database/backups/{backup_id}/restore`

## Existing documentation

- [devices.md](../../devices.md)
- [recovery.md](../../recovery.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)
- [Devices and offline recovery](../device-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
