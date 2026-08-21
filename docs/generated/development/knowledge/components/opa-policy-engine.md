---
title: "OPA Safety Rules policy engine"
description: "Evaluates only registered protected actions after FastAPI hard invariants and before existing NATS/worker execution; it never owns command execution."
generated: true
audience: knowledgebase
confidence: source-derived
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# OPA Safety Rules policy engine

Evaluates only registered protected actions after FastAPI hard invariants and before existing NATS/worker execution; it never owns command execution.

## Why it exists

Evaluates only registered protected actions after FastAPI hard invariants and before existing NATS/worker execution; it never owns command execution.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:opa-policy-engine` |
| Owner | Rules authorization |
| Execution owner | pocket-opa |
| Data owner | Repository Rego source and bounded SQLite policy decision metadata |
| Recovery owner | Startup validation and PM2 core supervisor |
| Runtime owner | PM2 |
| Runtime process | pocket-opa |
| Runtime platform | Server host loopback |
| Security boundary | control-api |
| Confidence | source-derived |

## Responsibilities

- Evaluates only registered protected actions after FastAPI hard invariants and before existing NATS/worker execution; it never owns command execution.

## Inputs

- bounded FastAPI authorization input

## Outputs

- allow/deny/constraints/reason code/policy revision

## Health signals

- loopback /health
- engine version
- active policy revision
- last decision

## Failure modes

- OPA unavailable
- OPA timeout
- invalid decision
- policy activation validation failure

## Recovery behavior

- fail closed
- preserve last-known-good policy
- restart only after validated activation

## Evidence

- bounded authorization decision metadata

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Fleet, Apps, Security, Recovery, and Release APIs`
- depends_on: `policy_decisions`
- protected_by: `Control API boundary`
- protected_by: `Control API boundary`
- uses: `GET /api/lite/policy`
- verified_by: `tests/backend/test_lite_identity_passkeys_rules_p1.py`
- verified_by: `tests/backend/test_lite_identity_rules_authorization.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Fleet, Apps, Security, Recovery, and Release APIs`
- uses: `Safety Rules authorization decision`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/opa-policy-engine.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/prepare-opa-policy.sh`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_opa.py`
- `security/policies/opa/pocketlab/pocketlab.rego`
