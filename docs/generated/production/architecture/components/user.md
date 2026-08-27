---
title: "User"
description: "Uses Pocket Lab Lite through the browser."
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

# User

Uses Pocket Lab Lite through the browser.

<div class="pl-architecture-component-icons"><span class="pl-architecture-icon pl-architecture-icon--component pl-architecture-icon--semantic"><img src="../../../../../assets/diagrams/production/icons/user.svg" alt="" loading="lazy" decoding="async" /><span>User</span></span></div>

> This component is represented in domain diagrams; a dedicated mini diagram is intentionally omitted.


## Function and use

| Field | Value |
| --- | --- |
| Function | Uses Pocket Lab Lite through the browser. |
| Primary inputs | Pocket Lab Lite status and actions |
| Primary outputs | Intent and confirmation |
| Protocols / uses | HTTPS |
| Evidence | None |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | actor |
| Runs on | Human user device |
| Started / runtime owner | Browser |
| Process owner | Browser |
| Execution owner | User |
| Data owner | None |
| Recovery owner | User |
| Security boundary | Browser trust boundary |
| Supported platforms | Browser |
| Verification | verified |
| Architecture icon | semantic-user |
| Icon class | semantic |
| Icon upstream | Pocket Lab Lite |
| Icon source revision | semantic-family-2 |
| Icon license | CC0-1.0 |
| Icon trademark note | No third-party trademark; locally generated semantic symbol. |
| Technology markers | None |

## Inputs

- Pocket Lab Lite status and actions

## Outputs

- Intent and confirmation

## Protocols

- HTTPS

## Durable state

- None declared

## Health and readiness

- None declared

## Evidence

- None declared

## Failure behavior

- None declared

## Recovery behavior

- None declared

## Connections

### Incoming

- None declared

### Outgoing

- uses — Browser

## Source verification

- `path` — `src/lite/LiteApp.jsx`

## Existing documentation

- [index.md](../../index.md)

## Related architecture views

- [Complete Pocket Lab Lite system map](../complete-system.md)
- [Request and control flow](../request-control.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
