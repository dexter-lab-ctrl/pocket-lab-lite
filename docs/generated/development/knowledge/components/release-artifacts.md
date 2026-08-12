---
title: "Date-based Lite tag, dist.zip, checksums, and release manifest"
description: "Defines immutable release identity and the exact assets required for a Lite installation."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Date-based Lite tag, dist.zip, checksums, and release manifest

Defines immutable release identity and the exact assets required for a Lite installation.

## Why it exists

Defines immutable release identity and the exact assets required for a Lite installation.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:release-artifacts` |
| Owner | Release engineering |
| Execution owner | GitHub Actions |
| Data owner | Release assets |
| Recovery owner | Release workflow |
| Runtime owner | Release workflow |
| Runtime process | GitHub Actions |
| Runtime platform | GitHub Release / staging |
| Security boundary | external-release |
| Confidence | verified |

## Responsibilities

- Defines immutable release identity and the exact assets required for a Lite installation.

## Inputs

- Source commit

## Outputs

- verified release identity

## Health signals

- checksums match

## Failure modes

- tag or manifest mismatch

## Recovery behavior

- reject release

## Evidence

- release manifest

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Download staging and release verification`
- protected_by: `External release boundary`
- protected_by: `External release boundary`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `GitHub Release`
- uses: `Release and update flow`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/release-artifacts.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
