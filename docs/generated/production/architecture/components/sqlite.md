---
title: "SQLite control-plane store"
description: "Stores canonical Lite lifecycle state and prepared projections; the frontend never accesses it directly."
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

# SQLite control-plane store

Stores canonical Lite lifecycle state and prepared projections; the frontend never accesses it directly.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/sqlite.light.svg" aria-label="Open full-size SQLite control-plane store mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/sqlite.light.svg#only-light" alt="SQLite control-plane store mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/sqlite.dark.svg#only-dark" alt="SQLite control-plane store mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>SQLite control-plane store mini architecture. <a href="../../../../../assets/diagrams/production/components/sqlite.light.svg">View full-size diagram</a></figcaption>
</figure>

The mini diagram deterministically collapses **6** additional connections.


## Function and use

| Field | Value |
| --- | --- |
| Function | Stores canonical Lite lifecycle state and prepared projections; the frontend never accesses it directly. |
| Primary inputs | Transactional lifecycle writes |
| Primary outputs | Canonical state, prepared reads |
| Protocols / uses | SQLite |
| Evidence | schema migrations, quick_check |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | Server host |
| Started / runtime owner | FastAPI and workers |
| Process owner | SQLite clients |
| Execution owner | Lite control plane store |
| Data owner | Pocket Lab Lite |
| Recovery owner | Database backup/restore |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-sqlite |

## Inputs

- Transactional lifecycle writes

## Outputs

- Canonical state
- prepared reads

## Protocols

- SQLite

## Durable state

- all Lite tables

## Health and readiness

- PRAGMA quick_check
- WAL pressure

## Evidence

- schema migrations
- quick_check

## Failure behavior

- corruption
- write contention

## Recovery behavior

- checkpoint
- verified database restore

## Connections

### Incoming

- App, command, and workflow state — stored in
- Enrollment and device lifecycle state — stored in
- Invite and identity lifecycle — stored in
- FastAPI /api/lite/* — transactional read/write
- Audit index, projection refresh, prepared projections, and domain revisions — stored in
- Backup, restore, and checkpoint state — stored in
- Installed release and runtime state — stored in
- Security findings and run state — stored in
- Explicit retirement and database recovery — verified backup/restore

### Outgoing

- None declared

## Source verification

- `contract` — `contracts/generated/lite-sqlite-schema.json`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py`

## Existing documentation

- [lite-sqlite-schema.md](../../../development/lite-sqlite-schema.md)

## Related architecture views

- [Backup and restore](../backup-recovery.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Request and control flow](../request-control.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
