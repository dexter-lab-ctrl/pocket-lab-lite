---
title: "GitHub repository"
description: "Hosts source and release workflow definitions; it is not a Lite runtime apply owner."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# GitHub repository

Hosts source and release workflow definitions; it is not a Lite runtime apply owner.

## Why it exists

Hosts source and release workflow definitions; it is not a Lite runtime apply owner.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:github-repository` |
| Owner | Repository maintainers |
| Execution owner | GitHub Actions |
| Data owner | Git repository |
| Recovery owner | Repository maintainers |
| Runtime owner | GitHub |
| Runtime process | GitHub Actions |
| Runtime platform | External source hosting |
| Security boundary | external-release |
| Confidence | verified |

## Responsibilities

- Hosts source and release workflow definitions; it is not a Lite runtime apply owner.

## Inputs

- Merged source

## Outputs

- Tagged workflow

## Health signals

- workflow status

## Failure modes

- workflow failure

## Recovery behavior

- fix via PR

## Supported platforms

- External service

## Depends on / uses

- depends_on: `GitHub Release`
- protected_by: `External release boundary`
- protected_by: `External release boundary`
- recovers_with: `Release tag missing locally`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

No verified backlinks.

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/github-repository.md)

## Canonical sources

- `.github/workflows/release-dist.yml`
- `architecture/metadata/pocket-lab-architecture.json`
