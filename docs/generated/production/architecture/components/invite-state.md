---
title: "Invite and identity lifecycle"
description: "Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards."
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

# Invite and identity lifecycle

Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/durable-state.svg" alt="" loading="lazy" decoding="async" /><span>Durable state</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/invite-state.light.svg" aria-label="Open full-size Invite and identity lifecycle mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/invite-state.light.svg" alt="Invite and identity lifecycle mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/invite-state.dark.svg" alt="Invite and identity lifecycle mini architecture" loading="lazy" decoding="async" />
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
| Architecture icon | semantic-durable-state |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

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

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [SQLite and projection architecture](../data-projections.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
