---
title: "Identity, authentication, and invite guards"
description: "Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance."
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

# Identity, authentication, and invite guards

Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance.

![Identity, authentication, and invite guards mini architecture](../../../../assets/diagrams/production/components/api-guards.light.svg#only-light)
![Identity, authentication, and invite guards mini architecture](../../../../assets/diagrams/production/components/api-guards.dark.svg#only-dark)


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
