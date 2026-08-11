---
title: "Security findings and run state"
description: "Stores scan runs, tools, progress, findings, profile snapshots, and sanitized evidence references."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Security findings and run state

Stores scan runs, tools, progress, findings, profile snapshots, and sanitized evidence references.

## Why it exists

Stores scan runs, tools, progress, findings, profile snapshots, and sanitized evidence references.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:security-state` |
| Owner | Security domain |
| Execution owner | security services |
| Data owner | SQLite |
| Recovery owner | Security maintenance / retry |
| Runtime owner | Security worker |
| Runtime process | security services |
| Runtime platform | SQLite and compact sanitized files |
| Security boundary | durable-state |
| Confidence | verified |

## Responsibilities

- Stores scan runs, tools, progress, findings, profile snapshots, and sanitized evidence references.

## Inputs

- scanner results

## Outputs

- compact Security reads

## Health signals

- active key
- progress freshness

## Failure modes

- stale accepted run
- scanner timeout

## Recovery behavior

- terminal recovery
- maintenance

## Evidence

- sanitized evidence refs

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `SQLite control-plane store`
- depends_on: `security_scan_findings`
- depends_on: `security_scan_runs`
- protected_by: `Durable-state boundary`
- protected_by: `Durable-state boundary`
- recovers_with: `Security scan failure`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Lynis and Trivy scanner adapters`
- depends_on: `Security scan coordinator`
- uses: `Security finding review`
- uses: `Security scan`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/security-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
