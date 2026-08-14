---
title: "Media readiness and app health probes"
description: "Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Media readiness and app health probes

Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation.

## Why it exists

Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:media-app-health` |
| Owner | Apps domain |
| Execution owner | app services |
| Data owner | Sanitized app projection |
| Recovery owner | App repair |
| Runtime owner | Lite API / worker |
| Runtime process | app services |
| Runtime platform | FastAPI / worker |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Verifies approved media mapping, base-path route health, and app readiness without scanning or exposing user media in documentation.

## Inputs

- Route/runtime/storage posture

## Outputs

- route_ready
- media readiness

## Health signals

- operational status

## Failure modes

- media not connected
- route not ready

## Recovery behavior

- connect media safely
- repair

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `PhotoPrism`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- recovers_with: `PhotoPrism unavailable`
- uses: `GET /api/lite/apps/photoprism/storage-preview`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `App lifecycle worker`
- uses: `PhotoPrism operation`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/media-app-health.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_catalog_live.py`
