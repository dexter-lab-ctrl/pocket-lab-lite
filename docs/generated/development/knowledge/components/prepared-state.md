---
title: "Audit index, projection refresh, prepared projections, and domain revisions"
description: "Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Audit index, projection refresh, prepared projections, and domain revisions

Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions.

## Why it exists

Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:prepared-state` |
| Owner | Projection subsystem |
| Execution owner | projection services |
| Data owner | SQLite |
| Recovery owner | Projection reconciliation |
| Runtime owner | scheduler / subprocesses |
| Runtime process | projection services |
| Runtime platform | SQLite |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Indexes audit evidence and tracks dirty signals, generations, committed projections, current-state summaries, and semantic revisions.

## Inputs

- domain revisions
- evidence

## Outputs

- prepared API reads

## Health signals

- dirty
- committed_generation

## Failure modes

- stale generation

## Recovery behavior

- rebuild affected domain
- serve last valid

## Evidence

- generation diagnostics

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `SQLite is durable authority for control-plane state`
- depends_on: `Prepared read, health, readiness, diagnostics, and evidence APIs`
- depends_on: `SQLite control-plane store`
- depends_on: `domain_revisions`
- depends_on: `projection_refresh_state`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- recovers_with: `Recovery projection stale`
- recovers_with: `Restore blocked or preview stale`
- recovers_with: `Stale runtime evidence`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Completion and audit evidence`
- depends_on: `Projection subprocesses`
- uses: `Recovery reconciliation`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/prepared-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
