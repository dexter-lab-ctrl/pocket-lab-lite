---
title: "Security scan coordinator"
description: "Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Security scan coordinator

Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries.

## Why it exists

Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:security-coordinator` |
| Owner | Security domain |
| Execution owner | security services |
| Data owner | SQLite Security state |
| Recovery owner | Security maintenance / worker recovery |
| Runtime owner | pocket-api / pocket-worker |
| Runtime process | security services |
| Runtime platform | FastAPI and worker |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Validates Quick, Full, and App Check requests, tracks active runs, and exposes compact split-read summaries.

## Inputs

- Scan request

## Outputs

- run state
- compact summary

## Health signals

- progress
- freshness

## Failure modes

- worker start timeout
- scanner timeout

## Recovery behavior

- consumer recovery
- terminal recovery

## Evidence

- scan lifecycle

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Completion and audit evidence`
- depends_on: `Lynis and Trivy scanner adapters`
- depends_on: `Quick, Full, and App safety checks`
- depends_on: `Security findings and run state`
- depends_on: `security_scan_runs`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- recovers_with: `Security scan failure`
- uses: `POST /api/lite/security/check`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_security_f11_events_contract.py`
- verified_by: `tests/backend/test_lite_security_f3_summary_contract.py`
- verified_by: `tests/backend/test_lite_security_f7_split_read_contract.py`
- verified_by: `tests/backend/test_lite_security_f9_etag_contract.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/backend/test_lite_workload_admission.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Worker process`
- uses: `Security finding review`
- uses: `Security scan`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/security-coordinator.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py`
