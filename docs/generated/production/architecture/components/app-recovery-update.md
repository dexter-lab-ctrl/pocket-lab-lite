---
title: "App backup, restore preview, and update lifecycle"
description: "Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution."
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

# App backup, restore preview, and update lifecycle

Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/recovery.svg" alt="" loading="lazy" decoding="async" /><span>Recovery</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/app-recovery-update.light.svg" aria-label="Open full-size App backup, restore preview, and update lifecycle mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/app-recovery-update.light.svg" alt="App backup, restore preview, and update lifecycle mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/app-recovery-update.dark.svg" alt="App backup, restore preview, and update lifecycle mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>App backup, restore preview, and update lifecycle mini architecture. <a href="../../../../../assets/diagrams/production/components/app-recovery-update.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Coordinates app backup, safe restore preview, update readiness/apply, verification, and rollback gates without browser-owned execution. |
| Primary inputs | Confirmed action |
| Primary outputs | backup, preview, verified update result |
| Protocols / uses | NATS, SQLite |
| Evidence | app backup/update receipts |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Worker / release subprocess |
| Started / runtime owner | pocket-worker |
| Process owner | app/recovery services |
| Execution owner | Apps and Recovery |
| Data owner | SQLite and backup manifests |
| Recovery owner | Checkpoint / rollback |
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

- Confirmed action

## Outputs

- backup
- preview
- verified update result

## Protocols

- NATS
- SQLite

## Durable state

- backup_manifest_index
- app_action_lifecycle

## Health and readiness

- backup verified
- rollback ready

## Evidence

- app backup/update receipts

## Failure behavior

- verification blocked

## Recovery behavior

- preview first
- rollback

## Connections

### Incoming

- App lifecycle worker — runs backup/update paths

### Outgoing

- stores manifests/operations — Backup, restore, and checkpoint state

## Source verification

- `route` — `POST /api/lite/apps/{app_id}/backup`
- `route` — `POST /api/lite/apps/{app_id}/restore/preview`
- `route` — `POST /api/lite/apps/{app_id}/update/apply`

## Existing documentation

- [apps.md](../../apps.md)
- [recovery.md](../../recovery.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
