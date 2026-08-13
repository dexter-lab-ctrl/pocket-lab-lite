---
title: "GitHub Release"
description: "Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# GitHub Release

Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess.

## Why it exists

Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:github-release` |
| Owner | Release workflow |
| Execution owner | release-dist workflow |
| Data owner | Release assets |
| Recovery owner | Release workflow rerun/fix |
| Runtime owner | GitHub Actions |
| Runtime process | release-dist workflow |
| Runtime platform | GitHub |
| Security boundary | external-release |
| Confidence | verified |

## Responsibilities

- Publishes the verified Lite release manifest, checksums, and dist.zip assets for the release subprocess.

## Inputs

- Annotated Lite tag

## Outputs

- Release assets

## Health signals

- asset manifest validation

## Failure modes

- missing asset

## Recovery behavior

- do not apply; publish corrected release

## Supported platforms

- External service

## Depends on / uses

- depends_on: `Date-based Lite tag, dist.zip, checksums, and release manifest`
- protected_by: `External release boundary`
- protected_by: `External release boundary`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `GitHub repository`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/github-release.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
