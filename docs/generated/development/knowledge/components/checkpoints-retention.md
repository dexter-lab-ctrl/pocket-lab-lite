---
title: "Checkpoints and retention policy"
description: "Creates pre-change checkpoints and applies explicit bounded retention without silently deleting current state."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Checkpoints and retention policy

Creates pre-change checkpoints and applies explicit bounded retention without silently deleting current state.

## Why it exists

Creates pre-change checkpoints and applies explicit bounded retention without silently deleting current state.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:checkpoints-retention` |
| Owner | Recovery maintenance |
| Execution owner | maintenance services |
| Data owner | Recovery state |
| Recovery owner | Recovery worker |
| Runtime owner | pocket-worker |
| Runtime process | maintenance services |
| Runtime platform | Recovery worker |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Creates pre-change checkpoints and applies explicit bounded retention without silently deleting current state.

## Inputs

- Maintenance command

## Outputs

- checkpoint
- retention receipt

## Health signals

- retention status

## Failure modes

- checkpoint failure

## Recovery behavior

- abort destructive operation

## Evidence

- maintenance receipt

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Explicit retirement and database recovery`
- depends_on: `recovery_operations`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- uses: `POST /api/lite/recovery/maintenance/checkpoint`
- uses: `POST /api/lite/recovery/maintenance/retention`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Restore preview and confirmed restore`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/checkpoints-retention.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
