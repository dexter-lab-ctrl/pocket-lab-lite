---
title: "App Catalog"
description: "Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details."
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

# App Catalog

Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details.

![App Catalog mini architecture](../../../../assets/diagrams/production/components/app-catalog.light.svg#only-light)
![App Catalog mini architecture](../../../../assets/diagrams/production/components/app-catalog.dark.svg#only-dark)


## Ownership and placement

| Field | Value |
| --- | --- |
| Category | service |
| Runs on | PWA plus FastAPI prepared reads |
| Started / runtime owner | Lite UI / Lite API |
| Process owner | React / FastAPI |
| Execution owner | Apps domain |
| Data owner | SQLite app state |
| Recovery owner | App worker |
| Security boundary | Control API boundary |
| Supported platforms | Android/Termux, ARM64, Ubuntu, WSL2 development |
| Verification | verified |

## Inputs

- App catalog projection

## Outputs

- Open route
- validated action requests

## Protocols

- HTTPS JSON

## Durable state

- app_current_state
- app_action_lifecycle

## Health and readiness

- route_ready
- lifecycle status

## Evidence

- action details/troubleshooting

## Failure behavior

- route unavailable
- action blocked

## Recovery behavior

- repair/check
- safe disabled reason

## Connections

### Incoming

- App, command, and workflow state — catalog/action projection

### Outgoing

- app cards and actions — React / Vite PWA

## Source verification

- `route` — `GET /api/lite/catalog`
- `route` — `GET /api/lite/apps/{app_id}/actions`
- `path` — `src/lite/LiteCatalog.jsx`

## Existing documentation

- [apps.md](../../apps.md)

## Related architecture views

- [App Catalog lifecycle](../apps.md)
- [Complete Pocket Lab Lite system map](../complete-system.md)

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
