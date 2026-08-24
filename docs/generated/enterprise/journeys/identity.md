---
title: "Identity Feature Journey"
description: "Source-derived orchestration journey for identity."
generated: true
audience: production
page_type: journey
confidence: generated
---

# Identity Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Identity guide](../../production/identity.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: Local owner, passkey, recovery, and session lifecycle.

## Typical user journey

- `journey:change-password`

## Architecture

Primary architecture: [open architecture](../../production/architecture/components/api-guards.md).

### Components

- `component:api-domain-surfaces`
- `component:api-guards`
- `component:api-read-surfaces`
- `component:invite-state`
- `component:lite-api`
- `component:node-agent`
- `component:sqlite`

## Frontend and FastAPI ownership

### Source ownership

- `pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_identity_auth.py`
- `src/lite/LiteIdentity.jsx`

### API relationships

- `api:get:/api/lite/status`
- `api:post:/api/lite/fleet/add-device`
- `api:post:/api/lite/identity/login`
- `api:post:/api/lite/identity/logout`
- `api:post:/api/lite/identity/password`
- `api:post:/api/lite/identity/recover`
- `api:post:/api/lite/identity/recovery/regenerate`
- `api:post:/api/lite/identity/setup`

## Events and execution

- No exact event subject relationship was proven by both API-to-UI trace and event encyclopedia, so none is emitted.

Execution ownership: use the component/API ownership links above; no additional execution owner was inferred.

## SQLite / data ownership

- No SQLite relation was emitted for the journey APIs.

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
- `test:tests/backend/test_lite_control_plane_sqlite_p3.py`
- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_device_health_d4.py`
- `test:tests/backend/test_lite_identity_passkeys_rules_p1.py`
- `test:tests/backend/test_lite_identity_rules_authorization.py`
- `test:tests/backend/test_lite_identity_rules_ui_projection.py`
- `test:tests/backend/test_lite_long_gate_submission_recovery.py`
- `test:tests/backend/test_lite_phase3b_security_system_probe_revisions.py`
- `test:tests/backend/test_lite_phase3c_system_aggregates.py`
- `test:tests/backend/test_lite_revision_sync_n4_n5.py`
- `test:tests/backend/test_lite_security_f11_events_contract.py`
- `test:tests/backend/test_lite_security_f3_summary_contract.py`
- `test:tests/backend/test_lite_security_f7_split_read_contract.py`
- `test:tests/backend/test_lite_security_f9_etag_contract.py`
- `test:tests/backend/test_lite_security_p2b_reboot_generation.py`
- `test:tests/backend/test_lite_security_s6_retention.py`
- `test:tests/backend/test_lite_security_s8_recovery.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/parity/test_api_contract_fences.py`

## Failure modes and recovery

- `troubleshooting:api-unavailable`
- `troubleshooting:caddy-unavailable`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
