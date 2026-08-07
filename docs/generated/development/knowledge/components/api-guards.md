---
title: "Identity, authentication, and invite guards"
description: "Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Identity, authentication, and invite guards

Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance.

## Why it exists

Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:api-guards` |
| Owner | Lite API |
| Execution owner | FastAPI |
| Data owner | SQLite identity and invite state |
| Recovery owner | Explicit repair/rejoin |
| Runtime owner | pocket-api |
| Runtime process | FastAPI |
| Runtime platform | FastAPI process |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Applies identity guards, duplicate checks, protected-host checks, and fail-closed invite/bootstrap acceptance.

## Inputs

- Device invite request
- identity claim

## Outputs

- Accepted bootstrap artifact
- blocked evidence

## Health signals

- invite status

## Failure modes

- identity mismatch
- duplicate device

## Recovery behavior

- fail closed
- explicit repair/rejoin

## Evidence

- invite lifecycle
- bootstrap blocked

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Bootstrap artifacts are backend-generated and identity-guarded`
- depends_on: `Invite and identity lifecycle`
- depends_on: `Lite node agent`
- depends_on: `device_identity_guards`
- depends_on: `device_invite_lifecycle`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- publishes: `pocketlab.events.fleet.invite_created`
- related_to: `pocketlab.events.fleet.bootstrap_blocked`
- related_to: `pocketlab.events.fleet.invite_accepted`
- uses: `POST /api/lite/fleet/add-device`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `FastAPI /api/lite/*`
- uses: `Add Device`
- uses: `Change Password / identity rotation`
- uses: `Device bootstrap and enrollment`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/api-guards.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_awareness.py`
