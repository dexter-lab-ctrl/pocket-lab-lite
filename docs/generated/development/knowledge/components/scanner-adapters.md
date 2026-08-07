---
title: "Lynis and Trivy scanner adapters"
description: "Run bounded backend-owned scanners with target-aware exclusions and sanitized evidence; the browser never executes scanners."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Lynis and Trivy scanner adapters

Run bounded backend-owned scanners with target-aware exclusions and sanitized evidence; the browser never executes scanners.

## Why it exists

Run bounded backend-owned scanners with target-aware exclusions and sanitized evidence; the browser never executes scanners.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:scanner-adapters` |
| Owner | Security execution |
| Execution owner | scanner subprocess group |
| Data owner | Sanitized Security evidence |
| Recovery owner | Worker cleanup / retry |
| Runtime owner | pocket-worker |
| Runtime process | scanner subprocess group |
| Runtime platform | Security worker subprocesses |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Run bounded backend-owned scanners with target-aware exclusions and sanitized evidence; the browser never executes scanners.

## Inputs

- Verified scan plan

## Outputs

- normalized findings
- coverage summary

## Health signals

- tool status
- timeout status

## Failure modes

- tool unavailable
- timeout

## Recovery behavior

- kill process group
- record partial state

## Evidence

- sanitized scanner evidence

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Security findings and run state`
- depends_on: `security_scan_evidence_refs`
- depends_on: `security_scan_tool_runs`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- publishes: `pocketlab.commands.lite.security.scan`
- recovers_with: `Security scan failure`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_security_f7_split_read_contract.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Security scan coordinator`
- depends_on: `Quick, Full, and App safety checks`
- uses: `Security scan`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/scanner-adapters.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_evidence.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_policy.py`
