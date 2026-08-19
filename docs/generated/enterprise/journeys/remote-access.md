---
title: "Remote Access Feature Journey"
description: "Source-derived orchestration journey for remote-access."
generated: true
audience: production
page_type: journey
confidence: generated
---

# Remote Access Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Remote Access guide](../../production/remote-access.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: Tailscale and remote access readiness.

## Typical user journey

- `journey:remote-access-readiness`

## Architecture

Primary architecture: [open architecture](../../production/architecture/remote-access.md).

### Components

- `component:api-read-surfaces`
- `component:caddy`
- `component:nats-jetstream`
- `component:nats-listeners`
- `component:remote-readiness`
- `component:tailscale`
- `component:tailscaled`

## Frontend and FastAPI ownership

### Source ownership

- `docs/generated/production/remote-access.md`

### API relationships

- `api:get:/api/lite/fleet`
- `api:get:/api/lite/remote-access/readiness`

## Events and execution

- No exact event subject relationship was proven by both API-to-UI trace and event encyclopedia, so none is emitted.

Execution ownership: use the component/API ownership links above; no additional execution owner was inferred.

## SQLite / data ownership

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

## Evidence and audit projection

- No feature-specific evidence entity was emitted; evidence remains backend-owned and is reached through the canonical linked projections.

## Security controls and threat boundaries

### Boundaries

- `control-api`
- `server-host`
- `tailnet`

### Controls

- `CTRL-API-CONTROL`
- `CTRL-EVIDENCE-SANITIZE`
- `CTRL-EXECUTION-OWNERS`
- `CTRL-EXPLICIT-PROMOTION`
- `CTRL-HUMAN-SESSION-CSRF`
- `CTRL-OPA-FAIL-CLOSED`

## Tests and validation

- `test:tests/backend/test_lite_api.py`
- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_device_system_profile.py`
- `test:tests/backend/test_lite_identity_rules_authorization.py`
- `test:tests/backend/test_lite_opa_bootstrap_reconciliation.py`
- `test:tests/backend/test_lite_phase3b_security_system_probe_revisions.py`
- `test:tests/backend/test_lite_security_s6_frontend_contract.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/parity/test_api_contract_fences.py`

## Failure modes and recovery

- `troubleshooting:device-offline`
- `troubleshooting:nats-unavailable`
- `troubleshooting:remote-access-not-ready`
- `troubleshooting:tailscale-unavailable`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
