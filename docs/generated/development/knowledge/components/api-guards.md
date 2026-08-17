---
title: "Identity, authentication, and invite guards"
description: "Applies human authentication/session/CSRF guards plus device identity, duplicate, protected-host, and fail-closed invite/bootstrap acceptance guards."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Identity, authentication, and invite guards

Applies human authentication/session/CSRF guards plus device identity, duplicate, protected-host, and fail-closed invite/bootstrap acceptance guards.

## Why it exists

Applies human authentication/session/CSRF guards plus device identity, duplicate, protected-host, and fail-closed invite/bootstrap acceptance guards.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:api-guards` |
| Owner | Lite API |
| Execution owner | FastAPI |
| Data owner | SQLite human identity/session state plus device identity and invite state |
| Recovery owner | Explicit repair/rejoin |
| Runtime owner | pocket-api |
| Runtime process | FastAPI |
| Runtime platform | FastAPI process |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Applies human authentication/session/CSRF guards plus device identity, duplicate, protected-host, and fail-closed invite/bootstrap acceptance guards.

## Inputs

- CSRF token
- Device invite request
- Owner login/session credential
- identity claim

## Outputs

- Accepted bootstrap artifact
- Authenticated human context
- blocked evidence
- safe identity projection

## Health signals

- authenticated session state
- invite status
- owner configured

## Failure modes

- CSRF rejected
- authentication required
- duplicate device
- identity mismatch
- session expired

## Recovery behavior

- fail closed
- explicit repair/rejoin

## Evidence

- bootstrap blocked
- identity audit reason codes
- invite lifecycle

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Bootstrap artifacts are backend-generated and identity-guarded`
- depends_on: `Invite and identity lifecycle`
- depends_on: `Lite node agent`
- depends_on: `auth_sessions`
- depends_on: `device_identity_guards`
- depends_on: `device_invite_lifecycle`
- depends_on: `human_credentials`
- depends_on: `human_identities`
- depends_on: `identity_audit_events`
- depends_on: `recovery_code_batches`
- depends_on: `recovery_codes`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- publishes: `pocketlab.events.fleet.invite_created`
- related_to: `pocketlab.events.fleet.bootstrap_blocked`
- related_to: `pocketlab.events.fleet.invite_accepted`
- uses: `POST /api/lite/fleet/add-device`
- uses: `POST /api/lite/identity/login`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `FastAPI /api/lite/*`
- uses: `Add Device`
- uses: `Local owner password and session lifecycle`
- uses: `Device bootstrap and enrollment`
- uses: `Safety Rules authorization decision`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/api-guards.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_awareness.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_identity_auth.py`
