---
title: "Apps Feature Journey"
description: "Source-derived orchestration journey for apps."
generated: true
audience: production
page_type: journey
confidence: generated
---

# Apps Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Apps guide](../../production/apps.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: App installation, PhotoPrism operation.

## User-oriented sequence

<ol class="pl-journey-stepper" aria-label="User-oriented sequence"><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">01</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Start</span><p>A supported catalog app.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">02</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Request</span><p>A supported app action.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">03</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Check</span><p>The action prerequisites and current state.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">04</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Execute</span><p>FastAPI and backend-owned services.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">05</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Evidence</span><p>Bounded progress and evidence.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">06</span><div class="pl-journey-step-content"><span class="pl-journey-stage">See</span><p>An updated app state.</p></div></li></ol>

## Typical user journey

- `journey:app-installation`
- `journey:photoprism-operation`

## Architecture

Primary architecture: [open architecture](../../production/architecture/apps.md).

### Components

- `component:app-catalog`
- `component:app-lifecycle-worker`
- `component:app-recovery-update`
- `component:app-workflow-state`
- `component:caddy`
- `component:completion-evidence`
- `component:media-app-health`
- `component:photoprism`
- `component:proot-ubuntu`
- `component:pwa`
- `component:workflow-execution`

## Frontend and FastAPI ownership

### Source ownership

- `src/lite/LiteCatalog.jsx`

### API relationships

- `api:get:/api/lite/apps/{app_id}/actions`
- `api:get:/api/lite/catalog`
- `api:post:/api/lite/catalog/install`

## Events and execution

- `pocketlab.commands.catalog.refresh`
- `pocketlab.commands.lite.app.safety`
- `pocketlab.commands.lite.catalog.install`
- `pocketlab.events.catalog.refresh_started`
- `pocketlab.events.catalog.refreshed`
- `pocketlab.events.lite.catalog.install_completed`
- `pocketlab.events.lite.catalog.install_failed`
- `pocketlab.events.lite.catalog.install_started`

Execution ownership: FastAPI → NATS/JetStream → worker; FastAPI/Caddy read path.

## SQLite / data ownership

- `table:app_action_lifecycle`
- `table:app_current_state`

## Evidence and audit projection

- No feature-specific evidence entity was emitted; evidence remains backend-owned and is reached through the canonical linked projections.

## Security controls and threat boundaries

### Boundaries

- `control-api`
- `messaging-execution`

### Controls

- `CTRL-API-CONTROL`
- `CTRL-BROWSER-NATS`
- `CTRL-ENTERPRISE-ROLE-FINAL-OWNER`
- `CTRL-EXECUTION-OWNERS`
- `CTRL-HUMAN-SESSION-CSRF`
- `CTRL-INDEPENDENT-APPROVAL-CONTINUATION`
- `CTRL-OPA-FAIL-CLOSED`
- `CTRL-POLICY-REVISION-LIFECYCLE`
- `CTRL-TEMPORARY-EXCEPTION-SCOPE`
- `CTRL-WEBAUTHN-ASSURANCE`

## Tests and validation

- `test:tests/backend/test_lite_api.py`
- `test:tests/backend/test_lite_app_runtime_reconciliation.py`
- `test:tests/backend/test_lite_control_plane_sqlite_p3.py`
- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_projection_semantic_hardening.py`
- `test:tests/backend/test_lite_security_s8_recovery.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/backend/test_lite_worker_recovery.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/e2e/lite-mocked.spec.ts`
- `test:tests/e2e/lite-test-helpers.ts`
- `test:tests/parity/test_api_contract_fences.py`

## Failure modes and recovery

- `troubleshooting:app-install-failure`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
