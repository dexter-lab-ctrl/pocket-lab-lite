---
title: "App Catalog"
description: "Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details."
audience: production
status: verified
generated: true
generated_at: uncommitted
generator: scripts/docs/graphviz/generate_lite_architecture.py
source_fingerprint: 13dae80367ddf3ba183f4f77c57075516b1e463d27336c7aa834c23b5cce75a2
source_commit: uncommitted
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span><span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>

# App Catalog

Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details.

<figure class="pl-architecture-diagram pl-architecture-diagram--component">
  <div class="pl-architecture-diagram__viewport">
    <a class="pl-architecture-diagram__link" href="../../../../../assets/diagrams/production/components/app-catalog.light.svg" aria-label="Open full-size App Catalog mini architecture">
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/app-catalog.light.svg#only-light" alt="App Catalog mini architecture" loading="lazy" decoding="async" />
      <img class="pl-architecture-diagram__image" src="../../../../../assets/diagrams/production/components/app-catalog.dark.svg#only-dark" alt="App Catalog mini architecture" loading="lazy" decoding="async" />
    </a>
  </div>
  <figcaption>App Catalog mini architecture. <a href="../../../../../assets/diagrams/production/components/app-catalog.light.svg">View full-size diagram</a></figcaption>
</figure>


## Function and use

| Field | Value |
| --- | --- |
| Function | Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details. |
| Primary inputs | App catalog projection |
| Primary outputs | Open route, validated action requests |
| Protocols / uses | HTTPS JSON |
| Evidence | action details/troubleshooting |

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
| Architecture icon | infra-app |

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
