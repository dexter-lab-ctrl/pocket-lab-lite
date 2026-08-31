---
title: "Security & Safety Feature Journey"
description: "Source-derived orchestration journey for security."
generated: true
audience: production
page_type: journey
confidence: generated
---

# Security & Safety Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Security guide](../../production/security.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: Security finding review, Security scan.

## User-oriented sequence

<ol class="pl-journey-stepper" aria-label="User-oriented sequence"><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">01</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Start</span><p>A safety question.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">02</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Request</span><p>A scan profile.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">03</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Check</span><p>Profile scope and availability.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">04</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Execute</span><p>FastAPI, NATS/JetStream, and the worker.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">05</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Evidence</span><p>Normalized, sanitized findings.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">06</span><div class="pl-journey-step-content"><span class="pl-journey-stage">See</span><p>A Security &amp; Safety result or truthful failure state.</p></div></li></ol>

## Typical user journey

- `journey:security-review`
- `journey:security-scan`

## Architecture

Primary architecture: [open architecture](../../production/architecture/security.md).

### Components

- `component:completion-evidence`
- `component:scanner-adapters`
- `component:security-coordinator`
- `component:security-profiles`
- `component:security-state`
- `component:sqlite`
- `component:worker`

## Frontend and FastAPI ownership

### Source ownership

- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py`
- `src/lite/LiteSecurity.jsx`

### API relationships

- `api:get:/api/lite/security/details/{run_id}`
- `api:get:/api/lite/security/progress`
- `api:get:/api/lite/security/summary`
- `api:post:/api/lite/security/check`

## Events and execution

- No exact event subject relationship was proven by both API-to-UI trace and event encyclopedia, so none is emitted.

Execution ownership: FastAPI → NATS/JetStream → worker.

## SQLite / data ownership

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
- `durable-state`

### Controls

- `CTRL-API-CONTROL`
- `CTRL-ENTERPRISE-ROLE-FINAL-OWNER`
- `CTRL-EVIDENCE-SANITIZE`
- `CTRL-EXPLICIT-PROMOTION`
- `CTRL-HUMAN-SESSION-CSRF`
- `CTRL-INDEPENDENT-APPROVAL-CONTINUATION`
- `CTRL-OPA-FAIL-CLOSED`
- `CTRL-POLICY-REVISION-LIFECYCLE`
- `CTRL-TEMPORARY-EXCEPTION-SCOPE`
- `CTRL-WEBAUTHN-ASSURANCE`

## Tests and validation

- `test:tests/backend/test_lite_api.py`
- `test:tests/backend/test_lite_complete_documentation_platform.py`
- `test:tests/backend/test_lite_control_plane_sqlite_p3.py`
- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_premium_tab_polish.py`
- `test:tests/backend/test_lite_security_f11_events_contract.py`
- `test:tests/backend/test_lite_security_f12_f14_stability_contract.py`
- `test:tests/backend/test_lite_security_f3_summary_contract.py`
- `test:tests/backend/test_lite_security_f7_split_read_contract.py`
- `test:tests/backend/test_lite_security_f9_etag_contract.py`
- `test:tests/backend/test_lite_security_s6_frontend_contract.py`
- `test:tests/backend/test_lite_security_s7_saved_state_history.py`
- `test:tests/backend/test_lite_security_s8_gate_submission_recovery.py`
- `test:tests/backend/test_lite_security_s8_idle_reconciliation.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/backend/test_lite_workload_admission.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/e2e/lite-mocked.spec.ts`
- `test:tests/parity/test_api_contract_fences.py`

## Failure modes and recovery

- `troubleshooting:security-scan-failure`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
