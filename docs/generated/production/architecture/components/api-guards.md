---
title: "Identity, authentication, and invite guards"
description: "Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance."
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

# Identity, authentication, and invite guards

Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/api-guards.light.svg" aria-label="Open full-size Identity, authentication, and invite guards mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/api-guards.light.svg#only-light" alt="Identity, authentication, and invite guards mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/api-guards.dark.svg#only-dark" alt="Identity, authentication, and invite guards mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Identity, authentication, and invite guards mini architecture. <a href="../../../../../assets/diagrams/production/components/api-guards.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance. |
| Primary inputs | Device invite request, identity claim |
| Primary outputs | Accepted bootstrap artifact, blocked evidence |
| Protocols / uses | HTTP JSON |
| Evidence | invite lifecycle, bootstrap blocked |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | FastAPI process |
| Started / runtime owner | pocket-api |
| Process owner | FastAPI |
| Execution owner | Lite API |
| Data owner | SQLite identity and invite state |
| Recovery owner | Explicit repair/rejoin |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | infra-decision |

## Inputs

- Device invite request
- identity claim

## Outputs

- Accepted bootstrap artifact
- blocked evidence

## Protocols

- HTTP JSON

## Durable state

- device_identity_guards
- device_invite_lifecycle

## Health and readiness

- invite status

## Evidence

- invite lifecycle
- bootstrap blocked

## Failure behavior

- identity mismatch
- duplicate device

## Recovery behavior

- fail closed
- explicit repair/rejoin

## Connections

### Incoming

- FastAPI /api/lite/* — validates identity and intent

### Outgoing

- backend-generated bootstrap — Lite node agent
- stores invite/identity state — Invite and identity lifecycle

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_awareness.py`
- `route` — `POST /api/lite/fleet/add-device`
- `sqlite_table` — `device_identity_guards`

## Existing documentation

- [devices.md](../../devices.md)

## Related architecture views

- [Device onboarding](../device-onboarding.md)
- [Request and control flow](../request-control.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
