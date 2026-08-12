---
title: "Completion and audit evidence"
description: "Records sanitized lifecycle and completion evidence for commands, devices, apps, security, recovery, and releases."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Completion and audit evidence

Records sanitized lifecycle and completion evidence for commands, devices, apps, security, recovery, and releases.

## Why it exists

Records sanitized lifecycle and completion evidence for commands, devices, apps, security, recovery, and releases.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:completion-evidence` |
| Owner | Evidence services |
| Execution owner | domain owners |
| Data owner | SQLite evidence index and sanitized files |
| Recovery owner | Owning domain |
| Runtime owner | worker / FastAPI |
| Runtime process | domain owners |
| Runtime platform | Worker and FastAPI |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Records sanitized lifecycle and completion evidence for commands, devices, apps, security, recovery, and releases.

## Inputs

- Lifecycle results

## Outputs

- Sanitized evidence summaries

## Health signals

- evidence index consistency

## Failure modes

- evidence write failure

## Recovery behavior

- fail action truthfully
- retry bounded write

## Evidence

- self-describing evidence

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Prepared read, health, readiness, diagnostics, and evidence APIs`
- depends_on: `Audit index, projection refresh, prepared projections, and domain revisions`
- depends_on: `audit_evidence_index`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- recovers_with: `Stale runtime evidence`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Device command executor`
- depends_on: `App lifecycle worker`
- depends_on: `Backup and verification engine`
- depends_on: `Command admission and lifecycle`
- depends_on: `Release subprocess`
- depends_on: `Security scan coordinator`
- depends_on: `Workflow execution`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/completion-evidence.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_evidence_receipts.py`
