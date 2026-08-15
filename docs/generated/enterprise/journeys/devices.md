---
title: "Devices Feature Journey"
description: "Source-derived orchestration journey for devices."
generated: true
audience: production
page_type: journey
confidence: generated
---

# Devices Feature Journey

<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>

## What the feature does

Canonical user guide: [Devices guide](../../production/devices.md).

## What the user sees

Source-derived journeys in the canonical Knowledge Graph: Add Device, Device bootstrap and enrollment, Device offline and reconnect recovery, Remove Old Device, Restart Agent.

## Typical user journey

- `journey:add-device`
- `journey:device-enrollment`
- `journey:device-reconnect`
- `journey:remove-old-device`
- `journey:restart-agent`

## Architecture

Primary architecture: [open architecture](../../production/architecture/device-onboarding.md).

### Components

- `component:agent-command-executor`
- `component:agent-recovery`
- `component:agent-signals`
- `component:agent-supervisor`
- `component:api-guards`
- `component:device-state`
- `component:invite-state`
- `component:nats-jetstream`
- `component:node-agent`
- `component:retirement-database-recovery`

## Frontend and FastAPI ownership

### Source ownership

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py`
- `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_invites.py`
- `src/lite/LiteDevices.jsx`

### API relationships

- `api:get:/api/lite/fleet`
- `api:post:/api/lite/fleet/add-device`
- `api:post:/api/lite/fleet/devices/{node_id}/restart-agent`
- `api:post:/api/lite/fleet/remove-device`

## Events and execution

- `pocketlab.commands.lite.device.restart`
- `pocketlab.commands.node.{normalized_node_id}.agent.restart`
- `pocketlab.events.fleet.bootstrap_blocked`
- `pocketlab.events.fleet.device_removed`
- `pocketlab.events.fleet.invite_accepted`
- `pocketlab.events.fleet.invite_created`
- `pocketlab.events.fleet.invite_revoked`
- `pocketlab.events.fleet.invite_started`
- `pocketlab.events.lite.database.restore.started`
- `pocketlab.events.lite.restore.service_restart_checked`
- `pocketlab.events.lite.restore.started`

Execution ownership: FastAPI → NATS/JetStream → node agent/supervisor.

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

- `managed-device`

### Controls

- `CTRL-EXECUTION-OWNERS`

## Tests and validation

- `test:src/__tests__/enterpriseLabels.test.js`
- `test:tests/backend/test_lite_api.py`
- `test:tests/backend/test_lite_control_plane_sqlite_p3.py`
- `test:tests/backend/test_lite_development_documentation_platform.py`
- `test:tests/backend/test_lite_device_system_profile.py`
- `test:tests/backend/test_lite_devices_d2_d3.py`
- `test:tests/backend/test_lite_devices_durable_enrollment.py`
- `test:tests/backend/test_lite_devices_production_readiness.py`
- `test:tests/backend/test_lite_termux_runtime_documentation.py`
- `test:tests/docs/test_documentation_presentation_polish.py`
- `test:tests/docs/test_enterprise_completion.py`
- `test:tests/docs/test_living_knowledgebase.py`
- `test:tests/parity/test_api_contract_fences.py`

## Failure modes and recovery

- `troubleshooting:agent-stopped`
- `troubleshooting:supervisor-stopped`

## Source and bounded expansion

Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.
