---
title: "Last-known-good state and rollback"
description: "Records the verified prior release and restores it atomically when post-switch validation fails."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Last-known-good state and rollback

Records the verified prior release and restores it atomically when post-switch validation fails.

## Why it exists

Records the verified prior release and restores it atomically when post-switch validation fails.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:last-known-good` |
| Owner | Release recovery |
| Execution owner | rollback stage |
| Data owner | Release SQLite state and prior PWA |
| Recovery owner | Self |
| Runtime owner | release subprocess |
| Runtime process | rollback stage |
| Runtime platform | Server host / release subprocess |
| Security boundary | server-host |
| Confidence | verified |

## Responsibilities

- Records the verified prior release and restores it atomically when post-switch validation fails.

## Inputs

- Rollback trigger

## Outputs

- Restored prior release

## Health signals

- last_known_good

## Failure modes

- rollback failure

## Recovery behavior

- manual recovery guidance

## Evidence

- rollback status

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Atomic PWA promotion`
- depends_on: `lite_installed_release_identity`
- depends_on: `release_runtime_projection`
- protected_by: `Server-host boundary`
- protected_by: `Server-host boundary`
- recovers_with: `Release or rollback issue`
- uses: `GET /api/lite/release`
- verified_by: `tests/backend/test_lite_native_release.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Post-switch health validation`
- uses: `Rollback`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/last-known-good.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/release_runtime.py`
