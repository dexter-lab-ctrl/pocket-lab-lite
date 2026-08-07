---
title: "Installed release and runtime state"
description: "Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Installed release and runtime state

Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state.

## Why it exists

Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:release-state` |
| Owner | Release system |
| Execution owner | release services |
| Data owner | SQLite |
| Recovery owner | Rollback |
| Runtime owner | Release subprocess |
| Runtime process | release services |
| Runtime platform | SQLite |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Stores installed-release identity and release-runtime projection for truthful comparison, staging, apply, rollback, and last-known-good state.

## Inputs

- verified release lifecycle

## Outputs

- release summary

## Health signals

- comparison
- artifact verification

## Failure modes

- identity mismatch
- health validation failure

## Recovery behavior

- last-known-good rollback

## Evidence

- release stage evidence

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Runtime evidence is explicitly promoted`
- depends_on: `SQLite control-plane store`
- depends_on: `lite_installed_release_identity`
- depends_on: `release_runtime_projection`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- recovers_with: `Release tag missing locally`
- recovers_with: `Release or rollback issue`
- recovers_with: `Runtime evidence or release binding mismatch`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Post-switch health validation`
- depends_on: `Release subprocess`
- uses: `Release and update flow`
- uses: `Rollback`
- uses: `Runtime evidence promotion`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/release-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
