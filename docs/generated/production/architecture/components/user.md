---
title: "User"
description: "Uses Pocket Lab Lite through the browser."
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

# User

Uses Pocket Lab Lite through the browser.

> This component is represented in domain diagrams; a dedicated mini diagram is intentionally omitted.


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
