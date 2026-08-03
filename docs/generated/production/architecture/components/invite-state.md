---
title: "Invite and identity lifecycle"
description: "Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards."
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

# Invite and identity lifecycle

Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/invite-state.light.svg" aria-label="Open full-size Invite and identity lifecycle mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/invite-state.light.svg#only-light" alt="Invite and identity lifecycle mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/invite-state.dark.svg#only-dark" alt="Invite and identity lifecycle mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Invite and identity lifecycle mini architecture. <a href="../../../../../assets/diagrams/production/components/invite-state.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards. |
| Primary inputs | invite creation, bootstrap acceptance |
| Primary outputs | safe onboarding state |
| Protocols / uses | SQLite |
| Evidence | blocked consumption, invite state |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | database |
| Runs on | SQLite |
| Started / runtime owner | Lite API |
| Process owner | FastAPI |
| Execution owner | Fleet onboarding |
| Data owner | SQLite |
| Recovery owner | Explicit repair/rejoin |
| Security boundary | Durable-state boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-state |

## Inputs

- invite creation
- bootstrap acceptance

## Outputs

- safe onboarding state

## Protocols

- SQLite

## Durable state

- device_invite_lifecycle
- device_identity_guards

## Health and readiness

- pending invite age

## Evidence

- blocked consumption
- invite state

## Failure behavior

- duplicate
- mismatch

## Recovery behavior

- revoke
- explicit repair

## Connections

### Incoming

- Identity, authentication, and invite guards — stores invite/identity state

### Outgoing

- accepted enrollment — Enrollment and device lifecycle state
- stored in — SQLite control-plane store

## Source verification

- `sqlite_table` — `device_invite_lifecycle`
- `sqlite_table` — `device_identity_guards`

## Existing documentation

- [devices.md](../../devices.md)

## Related architecture views

- [Device onboarding](../device-onboarding.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
