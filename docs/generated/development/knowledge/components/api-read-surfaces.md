---
title: "Prepared read, health, readiness, diagnostics, and evidence APIs"
description: "Serves side-effect-free prepared projections, health/readiness, compact diagnostics, and sanitized evidence lookups."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Prepared read, health, readiness, diagnostics, and evidence APIs

Serves side-effect-free prepared projections, health/readiness, compact diagnostics, and sanitized evidence lookups.

## Why it exists

Serves side-effect-free prepared projections, health/readiness, compact diagnostics, and sanitized evidence lookups.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:api-read-surfaces` |
| Owner | Lite API |
| Execution owner | FastAPI |
| Data owner | Prepared SQLite projections |
| Recovery owner | Projection scheduler and owning workers |
| Runtime owner | pocket-api |
| Runtime process | FastAPI |
| Runtime platform | FastAPI process |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Serves side-effect-free prepared projections, health/readiness, compact diagnostics, and sanitized evidence lookups.

## Inputs

- Prepared projections
- compact evidence indexes

## Outputs

- Safe GET responses

## Health signals

- revision
- freshness
- ETag

## Failure modes

- stale projection

## Recovery behavior

- serve last committed generation
- focused invalidation

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Frontend state ownership`
- depends_on: `audit_evidence_index`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- uses: `GET /api/lite/diagnostics/runtime`
- uses: `GET /api/lite/events`
- uses: `GET /api/lite/system/health`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Completion and audit evidence`
- depends_on: `FastAPI /api/lite/*`
- depends_on: `Audit index, projection refresh, prepared projections, and domain revisions`
- depends_on: `Remote-access readiness checks`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/api-read-surfaces.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
