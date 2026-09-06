---
title: Device Facts contract
description: Generated resource, capability, runtime-service, software, and API projection contract for Pocket Lab Lite.
status: verified
generated: true
audience: development
generator: scripts/docs/lite/generate_device_facts_contract.py
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Device Facts contract

This page is generated from backend-owned resource-provider and capability registries.

## Resource observations

States: `available`, `verification_pending`, `stale`, `missing`, `unsupported`, `permission_denied`, `unavailable`, `transient_failure`, `blocked`, `not_applicable`.

Metrics: `memory`, `storage`, `cpu_usage`, `load_average`, `uptime`, `temperature`.

Every observation is sanitized and carries source, observed time, freshness, reason, support state, schema version, revision, and a bounded value when available. Unsupported or failed collection never becomes a fabricated numeric zero.

## Capability lifecycle

States: `not_advertised`, `advertised`, `verification_pending`, `verified`, `unavailable`, `unsupported`, `stale`, `blocked`, `not_applicable`.

- `host_apps` — Can host apps (`hosted_app_runtime`)
- `store_backups` — Can store backups (`storage_readiness`)
- `run_safety_checks` — Runs safety checks (`security_execution`)
- `receive_commands` — Receives commands (`command_delivery`)
- `supervisor_recovery` — Supervisor recovery (`supervisor_evidence`)
- `remote_access` — Remote access (`remote_access_health`)
- `serve_control_plane` — Serves Pocket Lab (`control_plane_runtime`)
- `access_phone_media` — Can access phone media (`media_access_readiness`)
- `provide_storage` — Provides storage (`storage_readiness`)
- `restore_target` — Restore target (`restore_target_readiness`)
- `backup_target` — Backup target (`backup_target_readiness`)

Advertisement alone does not verify a capability. `verified_at` is present only when authoritative runtime evidence verifies the capability.

## Runtime services

Runtime services are backend-owned, dynamic, device-specific, and sanitized. Process environment values, command arguments, credentials, and private paths are excluded. Secondary devices show only services they actually report.

## API parity

The same canonical facts are projected through:

- `/api/lite/status`
- `/api/lite/fleet`
- `/api/lite/devices/{device_id}`
- `/api/lite/devices/{device_id}/health`

Legacy telemetry fields remain compatibility aliases during migration; canonical `device_facts` is authoritative.

## Regression scenarios

The generated scenario manifest is `src/test/fixtures/generated/device-facts/manifest.json`. Runtime fixture payloads are owned by `src/mocks/deviceFactsScenarios.js` so Storybook and Playwright use the same deterministic states.
