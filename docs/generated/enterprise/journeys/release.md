---
title: "Release Feature Journey"
description: "Source-derived orchestration journey for release."
generated: true
audience: development
page_type: journey
confidence: generated
---

# Release Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Release guide](../../production/release.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: Release and update flow, Rollback.

## User-oriented sequence

<ol class="pl-journey-stepper" aria-label="User-oriented sequence"><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">01</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Start</span><p>What you start with.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">02</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Request</span><p>What you click.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">03</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Check</span><p>What Pocket Lab checks.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">04</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Execute</span><p>Where execution happens.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">05</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Evidence</span><p>What comes back.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">06</span><div class="pl-journey-step-content"><span class="pl-journey-stage">See</span><p>What you see when complete. This sequence is limited to linked source-derived relationships.</p></div></li></ol>

## Typical user journey

- `journey:release-update`
- `journey:rollback`

## Architecture

Primary architecture: [open architecture](../../production/architecture/release-rollback.md).

### Components

- `component:atomic-promotion`
- `component:completion-evidence`
- `component:last-known-good`
- `component:post-switch-health`
- `component:release-artifacts`
- `component:release-staging`
- `component:release-state`
- `component:release-subprocess`
- `component:sqlite`

## Frontend and FastAPI ownership

### Source ownership

- `docs/generated/production/release.md`
- `runbooks/release_rollback.yaml`

### API relationships

- `api:get:/api/lite/release`
- `api:get:/health`
- `api:get:/ready`

## Events and execution

- No exact event subject relationship was proven by both API-to-UI trace and event encyclopedia, so none is emitted.

Execution ownership: use the component/API ownership links above; no additional execution owner was inferred.

## SQLite / data ownership

- `table:lite_installed_release_identity`
- `table:release_runtime_projection`

## Evidence and audit projection

- No feature-specific evidence entity was emitted; evidence remains backend-owned and is reached through the canonical linked projections.

## Security controls and threat boundaries

### Boundaries

- `durable-state`
- `external-release`
- `messaging-execution`
- `server-host`

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
- `CTRL-SUPPLY-CHAIN`
- `CTRL-TEMPORARY-EXCEPTION-SCOPE`
- `CTRL-WEBAUTHN-ASSURANCE`

## Tests and validation

- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_native_release.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/parity/test_api_contract_fences.py`

## Failure modes and recovery

- `troubleshooting:missing-release-tag`
- `troubleshooting:release-failure`
- `troubleshooting:runtime-evidence-mismatch`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
