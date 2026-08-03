---
title: "Checkpoints and retention policy"
description: "Creates pre-change checkpoints and applies explicit bounded retention without silently deleting current state."
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

# Checkpoints and retention policy

Creates pre-change checkpoints and applies explicit bounded retention without silently deleting current state.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/checkpoints-retention.light.svg" aria-label="Open full-size Checkpoints and retention policy mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/checkpoints-retention.light.svg#only-light" alt="Checkpoints and retention policy mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/checkpoints-retention.dark.svg#only-dark" alt="Checkpoints and retention policy mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Checkpoints and retention policy mini architecture. <a href="../../../../../assets/diagrams/production/components/checkpoints-retention.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Creates pre-change checkpoints and applies explicit bounded retention without silently deleting current state. |
| Primary inputs | Maintenance command |
| Primary outputs | checkpoint, retention receipt |
| Protocols / uses | NATS, SQLite |
| Evidence | maintenance receipt |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | process |
| Runs on | Recovery worker |
| Started / runtime owner | pocket-worker |
| Process owner | maintenance services |
| Execution owner | Recovery maintenance |
| Data owner | Recovery state |
| Recovery owner | Recovery worker |
| Security boundary | Messaging and execution boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-backup |

## Inputs

- Maintenance command

## Outputs

- checkpoint
- retention receipt

## Protocols

- NATS
- SQLite

## Durable state

- recovery_operations

## Health and readiness

- retention status

## Evidence

- maintenance receipt

## Failure behavior

- checkpoint failure

## Recovery behavior

- abort destructive operation

## Connections

### Incoming

- Restore preview and confirmed restore — creates checkpoint before apply

### Outgoing

- provides recovery point — Explicit retirement and database recovery

## Source verification

- `route` — `POST /api/lite/recovery/maintenance/checkpoint`
- `route` — `POST /api/lite/recovery/maintenance/retention`

## Existing documentation

- [recovery.md](../../recovery.md)
- [data-retention.md](../../data-retention.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
