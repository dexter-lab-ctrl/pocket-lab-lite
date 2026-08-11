---
title: "Release subprocess"
description: "Owns network, download, verification, staging, apply, and rollback work outside the FastAPI event loop."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Release subprocess

Owns network, download, verification, staging, apply, and rollback work outside the FastAPI event loop.

## Why it exists

Owns network, download, verification, staging, apply, and rollback work outside the FastAPI event loop.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:release-subprocess` |
| Owner | Release runtime |
| Execution owner | release subprocess |
| Data owner | SQLite release state and staging area |
| Recovery owner | Last-known-good rollback |
| Runtime owner | pocket-worker |
| Runtime process | release subprocess |
| Runtime platform | Dedicated subprocess |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Owns network, download, verification, staging, apply, and rollback work outside the FastAPI event loop.

## Inputs

- Release check/apply command

## Outputs

- Verified staged release
- release evidence

## Health signals

- subprocess generation
- deadline counters

## Failure modes

- download failure
- verification failure
- post-switch health failure

## Recovery behavior

- bounded backoff
- atomic rollback

## Evidence

- release stage results

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Atomic PWA promotion`
- depends_on: `Completion and audit evidence`
- depends_on: `Installed release and runtime state`
- depends_on: `release_runtime_projection`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Download staging and release verification`
- depends_on: `Worker process`
- uses: `Release and update flow`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/release-subprocess.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/release_update_process.py`
