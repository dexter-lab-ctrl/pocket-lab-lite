---
title: "Post-switch health validation"
description: "Validates Caddy/FastAPI/PWA health after promotion before declaring the release current."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Post-switch health validation

Validates Caddy/FastAPI/PWA health after promotion before declaring the release current.

## Why it exists

Validates Caddy/FastAPI/PWA health after promotion before declaring the release current.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:post-switch-health` |
| Owner | Release validation |
| Execution owner | release validation stage |
| Data owner | Release runtime state |
| Recovery owner | Rollback |
| Runtime owner | release subprocess |
| Runtime process | release validation stage |
| Runtime platform | Release subprocess against local services |
| Security boundary | server-host |
| Confidence | verified |

## Responsibilities

- Validates Caddy/FastAPI/PWA health after promotion before declaring the release current.

## Inputs

- Promoted release

## Outputs

- healthy/current or rollback trigger

## Health signals

- /health
- /ready

## Failure modes

- health gate fails

## Recovery behavior

- rollback immediately

## Evidence

- post-switch health

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Last-known-good state and rollback`
- depends_on: `Installed release and runtime state`
- depends_on: `release_runtime_projection`
- protected_by: `Server-host boundary`
- protected_by: `Server-host boundary`
- recovers_with: `Release or rollback issue`
- uses: `GET /health`
- uses: `GET /ready`
- verified_by: `tests/backend/test_lite_native_release.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Atomic PWA promotion`
- uses: `Release and update flow`
- uses: `Rollback`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/post-switch-health.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`
