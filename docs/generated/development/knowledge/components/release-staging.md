---
title: "Download staging and release verification"
description: "Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Download staging and release verification

Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA.

## Why it exists

Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:release-staging` |
| Owner | Release runtime |
| Execution owner | release subprocess |
| Data owner | Staging directory and release SQLite state |
| Recovery owner | Discard staging / backoff |
| Runtime owner | pocket-worker |
| Runtime process | release subprocess |
| Runtime platform | Release subprocess |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Downloads on explicit/manual or stable cadence, verifies repository/tag/manifest/assets/checksums, and stages without touching the active PWA.

## Inputs

- GitHub release metadata

## Outputs

- verified staged release

## Health signals

- artifact_verified

## Failure modes

- network/checksum/identity failure

## Recovery behavior

- preserve active release
- bounded backoff

## Evidence

- download/verification stages

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Release subprocess`
- depends_on: `release_runtime_projection`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- publishes: `pocketlab.events.release.applied`
- publishes: `pocketlab.events.release.available`
- publishes: `pocketlab.events.release.current`
- publishes: `pocketlab.events.release.stage.completed`
- publishes: `pocketlab.events.release.stage.failed`
- publishes: `pocketlab.events.release.stage.started`
- publishes: `pocketlab.events.release.workflow.completed`
- publishes: `pocketlab.events.release.workflow.failed`
- publishes: `pocketlab.events.release.workflow.started`
- recovers_with: `Release tag missing locally`
- recovers_with: `Release or rollback issue`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Date-based Lite tag, dist.zip, checksums, and release manifest`
- uses: `Release and update flow`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/release-staging.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_release_contract.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/release_orchestrator.py`
