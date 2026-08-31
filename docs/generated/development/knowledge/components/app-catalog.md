---
title: "App Catalog"
description: "Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# App Catalog

Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details.

## Why it exists

Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:app-catalog` |
| Owner | Apps domain |
| Execution owner | React / FastAPI |
| Data owner | SQLite app state |
| Recovery owner | App worker |
| Runtime owner | Lite UI / Lite API |
| Runtime process | React / FastAPI |
| Runtime platform | PWA plus FastAPI prepared reads |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Presents backend-owned app lifecycle and safe action readiness, including same-origin Open routes and Manage details.

## Inputs

- App catalog projection

## Outputs

- Open route
- validated action requests

## Health signals

- route_ready
- lifecycle status

## Failure modes

- route unavailable
- action blocked

## Recovery behavior

- repair/check
- safe disabled reason

## Evidence

- action details/troubleshooting

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `React / Vite PWA`
- depends_on: `app_action_lifecycle`
- depends_on: `app_current_state`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- recovers_with: `App installation failure`
- uses: `GET /api/lite/apps/{app_id}/actions`
- uses: `GET /api/lite/catalog`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_app_runtime_reconciliation.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`
- verified_by: `tests/e2e/lite-mocked.spec.ts`
- verified_by: `tests/e2e/lite-test-helpers.ts`

## Used by / backlinks

- depends_on: `App, command, and workflow state`
- uses: `App installation`
- uses: `PhotoPrism operation`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/app-catalog.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `src/lite/LiteCatalog.jsx`
