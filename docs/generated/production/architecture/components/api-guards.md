---
title: "Identity, authentication, and invite guards"
description: "Applies human authentication/session/CSRF guards plus device identity, duplicate, protected-host, and fail-closed invite/bootstrap acceptance guards."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: f82d3e269a91212087e920fb458fe3869473b363b8e0a4874489074018141ec5
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# Identity, authentication, and invite guards

Applies human authentication/session/CSRF guards plus device identity, duplicate, protected-host, and fail-closed invite/bootstrap acceptance guards.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/api-guard.svg" alt="" loading="lazy" decoding="async" /><span>API guard</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/api-guards.light.svg" aria-label="Open full-size Identity, authentication, and invite guards mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/api-guards.light.svg" alt="Identity, authentication, and invite guards mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/api-guards.dark.svg" alt="Identity, authentication, and invite guards mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Identity, authentication, and invite guards mini architecture. <a href="../../../../../assets/diagrams/production/components/api-guards.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Applies human authentication/session/CSRF guards plus device identity, duplicate, protected-host, and fail-closed invite/bootstrap acceptance guards. |
| Primary inputs | CSRF token, Device invite request, Owner login/session credential |
| Primary outputs | Accepted bootstrap artifact, Authenticated human context, blocked evidence |
| Protocols / uses | HTTP JSON |
| Evidence | bootstrap blocked, identity audit reason codes, invite lifecycle |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | FastAPI process |
| Started / runtime owner | pocket-api |
| Process owner | FastAPI |
| Execution owner | Lite API |
| Data owner | SQLite human identity/session state plus device identity and invite state |
| Recovery owner | Explicit repair/rejoin |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-api-guard |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python |

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

## Protocols

- HTTP JSON

## Durable state

- auth_sessions
- auth_session_assurance
- device_identity_guards
- device_invite_lifecycle
- human_credentials
- human_identities
- identity_audit_events
- recovery_code_batches
- recovery_codes

## Health and readiness

- authenticated session state
- invite status
- owner configured

## Evidence

- bootstrap blocked
- identity audit reason codes
- invite lifecycle

## Failure behavior

- CSRF rejected
- authentication required
- duplicate device
- identity mismatch
- session expired

## Recovery behavior

- fail closed
- explicit repair/rejoin

## Connections

### Incoming

- FastAPI /api/lite/* — validates identity and intent

### Outgoing

- applies passkey, step-up, and membership controls — Passkey, step-up, and Enterprise identity controls
- backend-generated bootstrap — Lite node agent
- stores invite/identity state — Invite and identity lifecycle

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_awareness.py`
- `route` — `POST /api/lite/fleet/add-device`
- `sqlite_table` — `device_identity_guards`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_identity_auth.py`
- `route` — `POST /api/lite/identity/login`
- `sqlite_table` — `human_identities`
- `sqlite_table` — `auth_sessions`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_webauthn.py`
- `sqlite_table` — `webauthn_credentials`
- `sqlite_table` — `auth_session_assurance`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_enterprise_identity.py`
- `sqlite_table` — `enterprise_memberships`

## Existing documentation

- [devices.md](../../devices.md)
- [identity.md](../../identity.md)
- [rules.md](../../rules.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Device onboarding](../device-onboarding.md)
- [Request and control flow](../request-control.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
