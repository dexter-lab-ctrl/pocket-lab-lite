---
title: "Passkey, step-up, and Enterprise identity controls"
description: "Verifies passkeys, records purpose-bound session assurance, and resolves server-owned Enterprise memberships and final-Owner protection; it does not create a browser-held authority."
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

# Passkey, step-up, and Enterprise identity controls

Verifies passkeys, records purpose-bound session assurance, and resolves server-owned Enterprise memberships and final-Owner protection; it does not create a browser-held authority.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/api-guard.svg" alt="" loading="lazy" decoding="async" /><span>API guard</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--brand"><img src="../../../../../assets/diagrams/production/icons/python.svg" alt="" loading="lazy" decoding="async" /><span>Python</span></span><span class="pl-architecture-icon pl-architecture-icon--small pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/api-guard.svg" alt="" loading="lazy" decoding="async" /><span>API guard</span></span></div>

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/identity-access-controls.light.svg" aria-label="Open full-size Passkey, step-up, and Enterprise identity controls mini architecture">
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="../../../../../assets/diagrams/production/components/identity-access-controls.light.svg" alt="Passkey, step-up, and Enterprise identity controls mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="../../../../../assets/diagrams/production/components/identity-access-controls.dark.svg" alt="Passkey, step-up, and Enterprise identity controls mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>Passkey, step-up, and Enterprise identity controls mini architecture. <a href="../../../../../assets/diagrams/production/components/identity-access-controls.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Verifies passkeys, records purpose-bound session assurance, and resolves server-owned Enterprise memberships and final-Owner protection; it does not create a browser-held authority. |
| Primary inputs | authenticated human context, WebAuthn assertion, membership update request |
| Primary outputs | purpose-bound assurance, authoritative membership context, sanitized identity projection |
| Protocols / uses | HTTP JSON, WebAuthn |
| Evidence | identity audit events |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | FastAPI process |
| Started / runtime owner | pocket-api |
| Process owner | FastAPI |
| Execution owner | Lite API Identity |
| Data owner | SQLite passkey, session-assurance, Enterprise configuration, and membership state |
| Recovery owner | FastAPI Identity |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |
| Architecture icon | semantic-api-guard |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | brand-python, semantic-api-guard |

## Inputs

- authenticated human context
- WebAuthn assertion
- membership update request

## Outputs

- purpose-bound assurance
- authoritative membership context
- sanitized identity projection

## Protocols

- HTTP JSON
- WebAuthn

## Durable state

- webauthn_credentials
- auth_session_assurance
- enterprise_configuration
- enterprise_memberships
- identity_audit_events

## Health and readiness

- authenticated human context
- Enterprise Mode state

## Evidence

- identity audit events

## Failure behavior

- passkey verification refused
- step-up expired
- final Owner protection

## Recovery behavior

- fail closed
- explicit recovery

## Connections

### Incoming

- Identity, authentication, and invite guards — applies passkey, step-up, and membership controls

### Outgoing

- stores assurance, membership, and audit state — SQLite control-plane store

## Source verification

- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_webauthn.py`
- `path` — `pocket-lab-final-structure/runtime/api_fastapi/services/lite_enterprise_identity.py`
- `route` — `POST /api/lite/identity/step-up/verify`
- `sqlite_table` — `enterprise_memberships`

## Existing documentation

- [identity.md](../../identity.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Request and control flow](../request-control.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
