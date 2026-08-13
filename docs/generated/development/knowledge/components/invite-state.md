---
title: "Invite and identity lifecycle"
description: "Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Invite and identity lifecycle

Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards.

## Why it exists

Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:invite-state` |
| Owner | Fleet onboarding |
| Execution owner | FastAPI |
| Data owner | SQLite |
| Recovery owner | Explicit repair/rejoin |
| Runtime owner | Lite API |
| Runtime process | FastAPI |
| Runtime platform | SQLite |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Tracks pending, accepted, revoked, blocked, and consumed invite/identity state with duplicate and mismatch guards.

## Inputs

- invite creation
- bootstrap acceptance

## Outputs

- safe onboarding state

## Health signals

- pending invite age

## Failure modes

- duplicate
- mismatch

## Recovery behavior

- revoke
- explicit repair

## Evidence

- blocked consumption
- invite state

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Bootstrap artifacts are backend-generated and identity-guarded`
- depends_on: `Enrollment and device lifecycle state`
- depends_on: `SQLite control-plane store`
- depends_on: `device_identity_guards`
- depends_on: `device_invite_lifecycle`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- recovers_with: `Device joining, waiting, or repairing`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Identity, authentication, and invite guards`
- uses: `Add Device`
- uses: `Device bootstrap and enrollment`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/invite-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
