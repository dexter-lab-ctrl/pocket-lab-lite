---
title: "Passkey, step-up, and Enterprise identity controls"
description: "Verifies passkeys, records purpose-bound session assurance, and resolves server-owned Enterprise memberships and final-Owner protection; it does not create a browser-held authority."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Passkey, step-up, and Enterprise identity controls

Verifies passkeys, records purpose-bound session assurance, and resolves server-owned Enterprise memberships and final-Owner protection; it does not create a browser-held authority.

## Why it exists

Verifies passkeys, records purpose-bound session assurance, and resolves server-owned Enterprise memberships and final-Owner protection; it does not create a browser-held authority.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:identity-access-controls` |
| Owner | Lite API Identity |
| Execution owner | FastAPI |
| Data owner | SQLite passkey, session-assurance, Enterprise configuration, and membership state |
| Recovery owner | FastAPI Identity |
| Runtime owner | pocket-api |
| Runtime process | FastAPI |
| Runtime platform | FastAPI process |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Verifies passkeys, records purpose-bound session assurance, and resolves server-owned Enterprise memberships and final-Owner protection; it does not create a browser-held authority.

## Inputs

- authenticated human context
- WebAuthn assertion
- membership update request

## Outputs

- purpose-bound assurance
- authoritative membership context
- sanitized identity projection

## Health signals

- authenticated human context
- Enterprise Mode state

## Failure modes

- passkey verification refused
- step-up expired
- final Owner protection

## Recovery behavior

- fail closed
- explicit recovery

## Evidence

- identity audit events

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `SQLite control-plane store`
- depends_on: `auth_session_assurance`
- depends_on: `enterprise_configuration`
- depends_on: `enterprise_memberships`
- depends_on: `identity_audit_events`
- depends_on: `webauthn_credentials`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- recovers_with: `Enterprise membership change protected`
- recovers_with: `Passkey or step-up refused`
- recovers_with: `Rules approval, continuation, or exception refused`
- uses: `POST /api/lite/identity/step-up/verify`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Identity, authentication, and invite guards`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/identity-access-controls.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_enterprise_identity.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_webauthn.py`
