---
title: "Fleet, Apps, Security, Recovery, and Release APIs"
description: "Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Fleet, Apps, Security, Recovery, and Release APIs

Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution.

## Why it exists

Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:api-domain-surfaces` |
| Owner | Lite API domains |
| Execution owner | FastAPI |
| Data owner | Domain SQLite state |
| Recovery owner | Domain worker / supervisor |
| Runtime owner | pocket-api |
| Runtime process | FastAPI |
| Runtime platform | FastAPI process |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Exposes domain-specific read and command endpoints while preserving backend-owned lifecycle execution.

## Inputs

- User intent
- domain state

## Outputs

- Domain summaries
- accepted commands

## Health signals

- domain revisions
- projection freshness

## Failure modes

- command undeliverable
- domain stale

## Recovery behavior

- explicit retry
- reconciliation

## Evidence

- domain lifecycle evidence

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `NATS / JetStream`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- uses: `GET /api/lite/catalog`
- uses: `GET /api/lite/fleet`
- uses: `GET /api/lite/recovery/summary`
- uses: `GET /api/lite/release`
- uses: `GET /api/lite/security/summary`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `FastAPI /api/lite/*`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/api-domain-surfaces.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
