---
title: "Atomic PWA promotion"
description: "Promotes a verified staged PWA atomically and keeps the previous release available for rollback."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Atomic PWA promotion

Promotes a verified staged PWA atomically and keeps the previous release available for rollback.

## Why it exists

Promotes a verified staged PWA atomically and keeps the previous release available for rollback.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:atomic-promotion` |
| Owner | Release runtime |
| Execution owner | release apply stage |
| Data owner | Active and staged PWA directories |
| Recovery owner | Rollback |
| Runtime owner | release subprocess |
| Runtime process | release apply stage |
| Runtime platform | Server host |
| Security boundary | server-host |
| Confidence | verified |

## Responsibilities

- Promotes a verified staged PWA atomically and keeps the previous release available for rollback.

## Inputs

- Verified stage

## Outputs

- New active PWA

## Health signals

- active release identity

## Failure modes

- promotion failure

## Recovery behavior

- retain previous active release

## Evidence

- promotion result

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Caddy same-origin proxy`
- depends_on: `Post-switch health validation`
- depends_on: `lite_installed_release_identity`
- protected_by: `Server-host boundary`
- protected_by: `Server-host boundary`
- verified_by: `tests/backend/test_lite_native_release.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Last-known-good state and rollback`
- depends_on: `Release subprocess`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/atomic-promotion.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`
