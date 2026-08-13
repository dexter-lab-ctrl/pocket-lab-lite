---
title: "Remote-access readiness checks"
description: "Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Remote-access readiness checks

Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance.

## Why it exists

Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:remote-readiness` |
| Owner | Lite API |
| Execution owner | FastAPI |
| Data owner | Prepared status |
| Recovery owner | startup scripts / user guidance |
| Runtime owner | pocket-api |
| Runtime process | FastAPI |
| Runtime platform | FastAPI read surface |
| Security boundary | control-api |
| Confidence | verified |

## Responsibilities

- Combines tailscaled state, Tailnet IPv4, NATS listener reachability, agent/supervisor status, and safe guidance.

## Inputs

- Tailscale and NATS posture

## Outputs

- Ready or Remote access not ready

## Health signals

- readiness reasons

## Failure modes

- remote unavailable

## Recovery behavior

- truthful guidance
- safe startup side effects outside reads

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Prepared read, health, readiness, diagnostics, and evidence APIs`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- recovers_with: `Remote access not ready`
- recovers_with: `Tailscale unavailable`
- uses: `GET /api/lite/remote-access/readiness`
- verified_by: `tests/backend/test_lite_phase3b_security_system_probe_revisions.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Primary and secondary NATS listeners`
- depends_on: `tailscaled daemon`
- uses: `Tailscale and remote access readiness`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/remote-readiness.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_status.py`
