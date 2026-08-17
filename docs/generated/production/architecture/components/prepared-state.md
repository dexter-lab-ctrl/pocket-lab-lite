---
title: "Audit index, projection refresh, prepared projections, and domain revisions"
description: "Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 765d187cae484a494c7f2602216f3c7ab49cafc2bdffd1ea1b8900f7d1e8e672
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Audit index, projection refresh, prepared projections, and domain revisions

Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/projection.svg" alt="" loading="lazy" decoding="async" /><span>Projection</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/prepared-state.light.svg" aria-label="Open full-size Audit index, projection refresh, prepared projections, and domain revisions mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/prepared-state.light.svg" alt="Audit index, projection refresh, prepared projections, and domain revisions mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/prepared-state.dark.svg" alt="Audit index, projection refresh, prepared projections, and domain revisions mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Audit index, projection refresh, prepared projections, and domain revisions mini architecture. <a href="../../../../../assets/diagrams/production/components/prepared-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions. |
| Primary inputs | domain revisions, evidence |
| Primary outputs | prepared API reads |
| Protocols / uses | SQLite |
| Evidence | generation diagnostics |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite |
| Started / runtime owner | scheduler / subprocesses |
| Process owner | projection services |
| Execution owner | Projection subsystem |
| Data owner | SQLite |
| Recovery owner | Projection reconciliation |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-projection |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- domain revisions
- evidence

## Outputs

- prepared API reads

## Protocols

- SQLite

## Durable state

- projection_refresh_state
- domain_revisions

## Health and readiness

- dirty
- committed_generation

## Evidence

- generation diagnostics

## Failure behavior

- stale generation

## Recovery behavior

- rebuild affected domain
- serve last valid

## Connections

### Incoming

- Completion and audit evidence — indexes evidence
- Projection subprocesses — commits generation

### Outgoing

- prepared read — Prepared read, health, readiness, diagnostics, and evidence APIs
- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `audit_evidence_index`
- `sqlite_table` — `projection_refresh_state`
- `sqlite_table` — `domain_revisions`
- `sqlite_table` — `phase3b_current_state`

## Existing documentation

- [projection-catalog.md](../../../development/projection-catalog.md)

## Related architecture views

- [Audit and evidence flow](../audit-evidence.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Frontend state ownership](../frontend-state.md)
- [Request and control flow](../request-control.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
