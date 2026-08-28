---
title: "Backup & Restore Feature Journey"
description: "Source-derived orchestration journey for recovery."
generated: true
audience: production
page_type: journey
confidence: generated
---

# Backup & Restore Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Recovery guide](../../production/recovery.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: Backup creation and verification, Recovery reconciliation, Restore preview, Confirmed restore.

## User-oriented sequence

<ol class="pl-journey-stepper" aria-label="User-oriented sequence"><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">01</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Start</span><p>Data to protect or a restore point.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">02</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Request</span><p>Backup, verify, preview, then confirmed restore.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">03</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Check</span><p>Freshness, locks, confirmation, and restore guards.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">04</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Execute</span><p>Backend/worker recovery services.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">05</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Evidence</span><p>Verification and health evidence.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">06</span><div class="pl-journey-step-content"><span class="pl-journey-stage">See</span><p>A truthful recovery status.</p></div></li></ol>

## Typical user journey

- `journey:backup-create`
- `journey:recovery-reconciliation`
- `journey:restore-preview`
- `journey:restore-execution`

## Architecture

Primary architecture: [open architecture](../../production/architecture/backup-recovery.md).

### Components

- `component:app-lifecycle-worker`
- `component:backup-engine`
- `component:command-lifecycle`
- `component:completion-evidence`
- `component:prepared-state`
- `component:recovery-state`
- `component:release-subprocess`
- `component:restore-preview`
- `component:security-coordinator`
- `component:sqlite`
- `component:worker`
- `component:workflow-execution`

## Frontend and FastAPI ownership

### Source ownership

- `contracts/parity/parity-model.json`
- `runbooks/backup_restore_verify.yaml`
- `src/lite/LiteRecovery.jsx`

### API relationships

- `api:get:/api/lite/recovery/summary`
- `api:post:/api/lite/recovery/backup`
- `api:post:/api/lite/recovery/restore`
- `api:post:/api/lite/recovery/restore/preview`

## Events and execution

- `pocketlab.commands.drift.preview`
- `pocketlab.commands.lite.app.restore.preview`
- `pocketlab.commands.lite.database.restore`
- `pocketlab.commands.lite.database.restore.preview`
- `pocketlab.commands.lite.restore.apply`
- `pocketlab.commands.lite.restore.preview`
- `pocketlab.events.drift.previewed`
- `pocketlab.events.lite.app.restore.preview_created`
- `pocketlab.events.lite.app.restore.preview_failed`
- `pocketlab.events.lite.app.restore.preview_started`
- `pocketlab.events.lite.database.restore.preview_ready`
- `pocketlab.events.lite.database.restore.started`
- `pocketlab.events.lite.restore.preview_created`

Execution ownership: FastAPI → NATS/JetStream → worker.

## SQLite / data ownership

- No SQLite relation was emitted for the journey APIs.

## Evidence and audit projection

- No feature-specific evidence entity was emitted; evidence remains backend-owned and is reached through the canonical linked projections.

## Security controls and threat boundaries

### Boundaries

- `durable-state`
- `messaging-execution`

### Controls

- `CTRL-API-CONTROL`
- `CTRL-BROWSER-NATS`
- `CTRL-ENTERPRISE-ROLE-FINAL-OWNER`
- `CTRL-EVIDENCE-SANITIZE`
- `CTRL-EXECUTION-OWNERS`
- `CTRL-EXPLICIT-PROMOTION`
- `CTRL-HUMAN-SESSION-CSRF`
- `CTRL-INDEPENDENT-APPROVAL-CONTINUATION`
- `CTRL-OPA-FAIL-CLOSED`
- `CTRL-POLICY-REVISION-LIFECYCLE`
- `CTRL-TEMPORARY-EXCEPTION-SCOPE`
- `CTRL-WEBAUTHN-ASSURANCE`

## Tests and validation

- `test:tests/backend/test_lite_api.py`
- `test:tests/backend/test_lite_database_restore_reconciliation.py`
- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_premium_tab_polish.py`
- `test:tests/backend/test_lite_security_s8_recovery.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/docs/test_operational_health_bridge.py`
- `test:tests/parity/test_api_contract_fences.py`
- `test:tests/parity/test_backup_recovery_parity.py`

## Failure modes and recovery

- `troubleshooting:backup-failure`
- `troubleshooting:recovery-projection-stale`
- `troubleshooting:restore-blocked`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
