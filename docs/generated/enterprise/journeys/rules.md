---
title: "Rules Feature Journey"
description: "Source-derived orchestration journey for rules."
generated: true
audience: production
page_type: journey
confidence: generated
---

# Rules Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Rules guide](../../production/rules.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: Typed Safety Rules authorization, lifecycle, simulation, and continuations.

## Typical user journey

- `journey:rules-authorization`

## Architecture

Primary architecture: [open architecture](../../production/architecture/components/opa-policy-engine.md).

### Components

- `component:api-domain-surfaces`
- `component:api-guards`
- `component:identity-access-controls`
- `component:invite-state`
- `component:lite-api`
- `component:nats-jetstream`
- `component:node-agent`
- `component:opa-policy-engine`
- `component:sqlite`

## Frontend and FastAPI ownership

### Source ownership

- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_analysis.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_approvals.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_lifecycle.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_opa.py`
- `security/policies/opa/pocketlab/pocketlab.rego`
- `src/lite/LiteRules.jsx`

### API relationships

- `api:get:/api/lite/catalog`
- `api:get:/api/lite/enterprise/rules/analysis`
- `api:get:/api/lite/enterprise/rules/approvals`
- `api:get:/api/lite/enterprise/rules/health`
- `api:get:/api/lite/enterprise/rules/revisions`
- `api:get:/api/lite/fleet`
- `api:get:/api/lite/policy`
- `api:get:/api/lite/recovery/summary`
- `api:get:/api/lite/release`
- `api:get:/api/lite/security/summary`
- `api:post:/api/lite/catalog/install`
- `api:post:/api/lite/enterprise/rules/activations`
- `api:post:/api/lite/enterprise/rules/activations/{operation_id}/resolve`
- `api:post:/api/lite/enterprise/rules/approvals/{approval_id}`
- `api:post:/api/lite/enterprise/rules/exceptions`
- `api:post:/api/lite/enterprise/rules/revisions`
- `api:post:/api/lite/enterprise/rules/rollbacks`
- `api:post:/api/lite/enterprise/rules/simulations`
- `api:post:/api/lite/fleet/remove-device`

## Events and execution

- No exact event subject relationship was proven by both API-to-UI trace and event encyclopedia, so none is emitted.

Execution ownership: use the component/API ownership links above; no additional execution owner was inferred.

## SQLite / data ownership

- `table:app_action_lifecycle`
- `table:app_current_state`
- `table:device_awareness_state`
- `table:device_enrollment_registry`
- `table:device_health_attention`
- `table:device_health_current`
- `table:device_health_transitions`
- `table:device_heartbeats`
- `table:device_identity_guards`
- `table:device_invite_lifecycle`
- `table:device_lifecycle_events`
- `table:device_lifecycle_transactions`
- `table:device_recovery_history`
- `table:device_removal_receipts`
- `table:device_supervisor_state`
- `table:device_system_profiles`
- `table:lite_installed_release_identity`
- `table:release_runtime_projection`
- `table:security_database_backups`
- `table:security_database_restores`
- `table:security_maintenance_runs`
- `table:security_profile_snapshots`
- `table:security_scan_evidence_refs`
- `table:security_scan_findings`
- `table:security_scan_progress_events`
- `table:security_scan_tool_runs`
- `table:security_store_metadata`

## Evidence and audit projection

- No feature-specific evidence entity was emitted; evidence remains backend-owned and is reached through the canonical linked projections.

## Security controls and threat boundaries

### Boundaries

- `control-api`

### Controls

- `CTRL-API-CONTROL`
- `CTRL-HUMAN-SESSION-CSRF`
- `CTRL-OPA-FAIL-CLOSED`

## Tests and validation

- `test:tests/backend/test_lite_api.py`
- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_identity_passkeys_rules_p1.py`
- `test:tests/backend/test_lite_identity_rules_authorization.py`
- `test:tests/backend/test_lite_identity_rules_ui_projection.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/parity/test_api_contract_fences.py`

## Failure modes and recovery

- `troubleshooting:rules-policy-readiness-failed`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
