---
title: "How Pocket Lab works"
description: "Generated end-to-end journey knowledge from verified repository sources."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# How Pocket Lab works

| Journey | Domain | Components | APIs | Confidence |
| --- | --- | --- | --- | --- |
| Add Device | devices | 5 | 2 | source-derived |
| App installation | apps | 5 | 2 | source-derived |
| Backup creation and verification | recovery | 3 | 2 | source-derived |
| Change Password / identity rotation | identity | 3 | 1 | partial |
| Device bootstrap and enrollment | devices | 6 | 1 | source-derived |
| Device offline and reconnect recovery | devices | 5 | 1 | source-derived |
| Documentation generation | documentation | 0 | 0 | source-derived |
| Backend-to-Frontend parity capture and verification | validation | 3 | 0 | source-derived |
| PhotoPrism operation | apps | 5 | 2 | source-derived |
| Recovery reconciliation | recovery | 3 | 1 | source-derived |
| Release and update flow | release | 5 | 1 | source-derived |
| Tailscale and remote access readiness | devices | 4 | 1 | source-derived |
| Remove Old Device | devices | 2 | 2 | source-derived |
| Restart Agent | devices | 4 | 2 | source-derived |
| Confirmed restore | recovery | 4 | 2 | source-derived |
| Restore preview | recovery | 2 | 2 | source-derived |
| Rollback | release | 3 | 1 | source-derived |
| Sanitized Termux runtime capture | validation | 3 | 0 | source-derived |
| Runtime evidence promotion | validation | 2 | 0 | source-derived |
| Security finding review | security | 2 | 2 | source-derived |
| Security scan | security | 5 | 3 | source-derived |
| Pocket Lab Lite startup | platform | 7 | 0 | source-derived |

## Add Device

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `api-guards`, `invite-state`, `device-state`, `node-agent`, `agent-supervisor`

**Verified API routes:** `POST /api/lite/fleet/add-device`, `GET /api/lite/fleet`

**Graph links:** calls: `GET /api/lite/fleet`, calls: `POST /api/lite/fleet/add-device`, uses: `Lite agent supervisor`, uses: `Identity, authentication, and invite guards`, uses: `Enrollment and device lifecycle state`, uses: `Invite and identity lifecycle`, uses: `Lite node agent`, verified_by: `src/__tests__/enterpriseLabels.test.js`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_device_system_profile.py`, verified_by: `tests/backend/test_lite_devices_d2_d3.py`, verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`

**Sources:** `pocket-lab-final-structure/runtime/api_fastapi/services/lite_invites.py`, `src/lite/LiteDevices.jsx`

## App installation

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `app-catalog`, `app-lifecycle-worker`, `workflow-execution`, `photoprism`, `caddy`

**Verified API routes:** `POST /api/lite/catalog/install`, `GET /api/lite/catalog`

**Graph links:** calls: `GET /api/lite/catalog`, calls: `POST /api/lite/catalog/install`, uses: `App Catalog`, uses: `App lifecycle worker`, uses: `Caddy same-origin proxy`, uses: `PhotoPrism`, uses: `Workflow execution`, verified_by: `tests/backend/test_lite_api.py`

**Sources:** `src/lite/LiteCatalog.jsx`

## Backup creation and verification

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `backup-engine`, `recovery-state`, `worker`

**Verified API routes:** `POST /api/lite/recovery/backup`, `GET /api/lite/recovery/summary`

**Graph links:** calls: `GET /api/lite/recovery/summary`, calls: `POST /api/lite/recovery/backup`, uses: `Backup and verification engine`, uses: `Backup, restore, and checkpoint state`, uses: `Worker process`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_database_restore_reconciliation.py`, verified_by: `tests/backend/test_lite_premium_tab_polish.py`, verified_by: `tests/backend/test_lite_security_s8_recovery.py`

**Sources:** `src/lite/LiteRecovery.jsx`

## Change Password / identity rotation

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `api-guards`, `lite-api`, `sqlite`

**Verified API routes:** `POST /api/lite/identity/rotate`

**Graph links:** calls: `POST /api/lite/identity/rotate`, uses: `Identity, authentication, and invite guards`, uses: `FastAPI /api/lite/*`, uses: `SQLite control-plane store`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_development_documentation_platform.py`, verified_by: `tests/parity/test_api_contract_fences.py`

**Sources:** `contracts/generated/lite-openapi.json`, `contracts/parity/parity-model.json`, `src/lite/LiteIdentity.jsx`

## Device bootstrap and enrollment

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `api-guards`, `invite-state`, `device-state`, `node-agent`, `agent-supervisor`, `agent-signals`

**Verified API routes:** `GET /api/lite/fleet`

**Graph links:** calls: `GET /api/lite/fleet`, uses: `Heartbeat, telemetry, and health publishers`, uses: `Lite agent supervisor`, uses: `Identity, authentication, and invite guards`, uses: `Enrollment and device lifecycle state`, uses: `Invite and identity lifecycle`, uses: `Lite node agent`, verified_by: `tests/backend/test_lite_device_system_profile.py`, verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`, verified_by: `tests/backend/test_lite_devices_production_readiness.py`

**Sources:** `pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py`, `pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py`

## Device offline and reconnect recovery

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `agent-signals`, `agent-recovery`, `node-agent`, `agent-supervisor`, `nats-jetstream`

**Verified API routes:** `GET /api/lite/fleet`

**Graph links:** calls: `GET /api/lite/fleet`, uses: `Reconnect watchdog and supervisor recovery`, uses: `Heartbeat, telemetry, and health publishers`, uses: `Lite agent supervisor`, uses: `NATS / JetStream`, uses: `Lite node agent`, verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`, verified_by: `tests/docs/test_living_knowledgebase.py`

**Sources:** `architecture/metadata/pocket-lab-architecture.json`

## Documentation generation

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** none declared

**Verified API routes:** none

**Graph links:** verified_by: `tests/backend/test_lite_complete_documentation_platform.py`, verified_by: `tests/backend/test_lite_development_documentation_platform.py`, verified_by: `tests/backend/test_lite_production_architecture_platform.py`, verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`

**Sources:** `scripts/docs/lite/generate_docs.py`, `scripts/docs/lite/generate_platform_catalogs.py`, `tasks/Taskfile.docs.yml`

## Backend-to-Frontend parity capture and verification

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `lite-api`, `pwa`, `sqlite`

**Verified API routes:** none

**Graph links:** uses: `FastAPI /api/lite/*`, uses: `React / Vite PWA`, uses: `SQLite control-plane store`

**Sources:** `contracts/parity/parity-model.json`, `scripts/docs/parity/generate_parity.py`

## PhotoPrism operation

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `app-catalog`, `photoprism`, `proot-ubuntu`, `media-app-health`, `caddy`

**Verified API routes:** `GET /api/lite/catalog`, `GET /api/lite/apps/{app_id}/actions`

**Graph links:** calls: `GET /api/lite/apps/{app_id}/actions`, calls: `GET /api/lite/catalog`, uses: `App Catalog`, uses: `Caddy same-origin proxy`, uses: `Media readiness and app health probes`, uses: `PhotoPrism`, uses: `PROot Ubuntu application container`, verified_by: `tests/backend/test_lite_api.py`

**Sources:** `src/lite/LiteCatalog.jsx`

## Recovery reconciliation

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `prepared-state`, `recovery-state`, `sqlite`

**Verified API routes:** `GET /api/lite/recovery/summary`

**Graph links:** calls: `GET /api/lite/recovery/summary`, uses: `Audit index, projection refresh, prepared projections, and domain revisions`, uses: `Backup, restore, and checkpoint state`, uses: `SQLite control-plane store`

**Sources:** `contracts/parity/parity-model.json`

## Release and update flow

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `release-artifacts`, `release-staging`, `release-subprocess`, `post-switch-health`, `release-state`

**Verified API routes:** `GET /api/lite/release`

**Graph links:** calls: `GET /api/lite/release`, uses: `Post-switch health validation`, uses: `Date-based Lite tag, dist.zip, checksums, and release manifest`, uses: `Download staging and release verification`, uses: `Installed release and runtime state`, uses: `Release subprocess`

**Sources:** `docs/generated/production/release.md`

## Tailscale and remote access readiness

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `tailscale`, `tailscaled`, `remote-readiness`, `nats-listeners`

**Verified API routes:** `GET /api/lite/fleet`

**Graph links:** calls: `GET /api/lite/fleet`, uses: `Primary and secondary NATS listeners`, uses: `Remote-access readiness checks`, uses: `Tailscale remote access`, uses: `tailscaled daemon`

**Sources:** `docs/generated/production/remote-access.md`

## Remove Old Device

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `device-state`, `retirement-database-recovery`

**Verified API routes:** `POST /api/lite/fleet/remove-device`, `GET /api/lite/fleet`

**Graph links:** calls: `GET /api/lite/fleet`, calls: `POST /api/lite/fleet/remove-device`, uses: `Enrollment and device lifecycle state`, uses: `Explicit retirement and database recovery`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_device_system_profile.py`, verified_by: `tests/backend/test_lite_devices_d2_d3.py`, verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`

**Sources:** `src/lite/LiteDevices.jsx`

## Restart Agent

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `agent-command-executor`, `agent-recovery`, `node-agent`, `agent-supervisor`

**Verified API routes:** `POST /api/lite/fleet/devices/{node_id}/restart-agent`, `GET /api/lite/fleet`

**Graph links:** calls: `GET /api/lite/fleet`, calls: `POST /api/lite/fleet/devices/{node_id}/restart-agent`, uses: `Device command executor`, uses: `Reconnect watchdog and supervisor recovery`, uses: `Lite agent supervisor`, uses: `Lite node agent`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`, verified_by: `tests/backend/test_lite_device_system_profile.py`, verified_by: `tests/backend/test_lite_devices_d2_d3.py`, verified_by: `tests/backend/test_lite_devices_durable_enrollment.py`, verified_by: `tests/docs/test_living_knowledgebase.py`

**Sources:** `src/lite/LiteDevices.jsx`

## Confirmed restore

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `restore-preview`, `backup-engine`, `recovery-state`, `workflow-execution`

**Verified API routes:** `POST /api/lite/recovery/restore`, `GET /api/lite/recovery/summary`

**Graph links:** calls: `GET /api/lite/recovery/summary`, calls: `POST /api/lite/recovery/restore`, uses: `Backup and verification engine`, uses: `Backup, restore, and checkpoint state`, uses: `Restore preview and confirmed restore`, uses: `Workflow execution`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_database_restore_reconciliation.py`, verified_by: `tests/backend/test_lite_premium_tab_polish.py`, verified_by: `tests/backend/test_lite_security_s8_recovery.py`

**Sources:** `runbooks/backup_restore_verify.yaml`, `src/lite/LiteRecovery.jsx`

## Restore preview

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `restore-preview`, `recovery-state`

**Verified API routes:** `POST /api/lite/recovery/restore/preview`, `GET /api/lite/recovery/summary`

**Graph links:** calls: `GET /api/lite/recovery/summary`, calls: `POST /api/lite/recovery/restore/preview`, uses: `Backup, restore, and checkpoint state`, uses: `Restore preview and confirmed restore`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_database_restore_reconciliation.py`, verified_by: `tests/backend/test_lite_premium_tab_polish.py`, verified_by: `tests/backend/test_lite_security_s8_recovery.py`, verified_by: `tests/parity/test_backup_recovery_parity.py`

**Sources:** `src/lite/LiteRecovery.jsx`

## Rollback

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `last-known-good`, `release-state`, `post-switch-health`

**Verified API routes:** `GET /api/lite/release`

**Graph links:** calls: `GET /api/lite/release`, uses: `Last-known-good state and rollback`, uses: `Post-switch health validation`, uses: `Installed release and runtime state`

**Sources:** `runbooks/release_rollback.yaml`

## Sanitized Termux runtime capture

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `node-agent`, `agent-supervisor`, `nats-jetstream`

**Verified API routes:** none

**Graph links:** uses: `Lite agent supervisor`, uses: `NATS / JetStream`, uses: `Lite node agent`

**Sources:** `scripts/docs/runtime/capture_termux_runtime.sh`, `scripts/docs/runtime/promote_termux_runtime.py`

## Runtime evidence promotion

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `runtime-evidence`, `release-state`

**Verified API routes:** none

**Graph links:** uses: `Installed release and runtime state`, verified_by: `tests/parity/test_runtime_promotion_preflight.py`

**Sources:** `scripts/test/parity/preflight_runtime_promotion.py`, `scripts/test/parity/promote_runtime_verification.py`

## Security finding review

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `security-state`, `security-coordinator`

**Verified API routes:** `GET /api/lite/security/summary`, `GET /api/lite/security/details/{run_id}`

**Graph links:** calls: `GET /api/lite/security/details/{run_id}`, calls: `GET /api/lite/security/summary`, uses: `Security scan coordinator`, uses: `Security findings and run state`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_complete_documentation_platform.py`, verified_by: `tests/backend/test_lite_premium_tab_polish.py`, verified_by: `tests/backend/test_lite_security_f11_events_contract.py`, verified_by: `tests/backend/test_lite_security_f12_f14_stability_contract.py`, verified_by: `tests/backend/test_lite_security_f3_summary_contract.py`, verified_by: `tests/backend/test_lite_security_f7_split_read_contract.py`, verified_by: `tests/backend/test_lite_security_f9_etag_contract.py`, verified_by: `tests/backend/test_lite_security_s6_frontend_contract.py`, verified_by: `tests/backend/test_lite_security_s7_saved_state_history.py`

**Sources:** `src/lite/LiteSecurity.jsx`

## Security scan

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `security-profiles`, `security-coordinator`, `scanner-adapters`, `security-state`, `worker`

**Verified API routes:** `POST /api/lite/security/check`, `GET /api/lite/security/summary`, `GET /api/lite/security/progress`

**Graph links:** calls: `GET /api/lite/security/progress`, calls: `GET /api/lite/security/summary`, calls: `POST /api/lite/security/check`, uses: `Lynis and Trivy scanner adapters`, uses: `Security scan coordinator`, uses: `Quick, Full, and App safety checks`, uses: `Security findings and run state`, uses: `Worker process`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_complete_documentation_platform.py`, verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`, verified_by: `tests/backend/test_lite_premium_tab_polish.py`, verified_by: `tests/backend/test_lite_security_f11_events_contract.py`, verified_by: `tests/backend/test_lite_security_f12_f14_stability_contract.py`, verified_by: `tests/backend/test_lite_security_f3_summary_contract.py`, verified_by: `tests/backend/test_lite_security_f7_split_read_contract.py`, verified_by: `tests/backend/test_lite_security_f9_etag_contract.py`, verified_by: `tests/backend/test_lite_security_s6_frontend_contract.py`, verified_by: `tests/backend/test_lite_security_s7_saved_state_history.py`, verified_by: `tests/backend/test_lite_security_s8_gate_submission_recovery.py`, verified_by: `tests/backend/test_lite_security_s8_idle_reconciliation.py`, verified_by: `tests/backend/test_lite_workload_admission.py`

**Sources:** `pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py`, `src/lite/LiteSecurity.jsx`

## Pocket Lab Lite startup

**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.

**Verified components:** `pm2`, `caddy`, `lite-api`, `nats-jetstream`, `worker`, `node-agent`, `agent-supervisor`

**Verified API routes:** none

**Graph links:** uses: `Lite agent supervisor`, uses: `Caddy same-origin proxy`, uses: `FastAPI /api/lite/*`, uses: `NATS / JetStream`, uses: `Lite node agent`, uses: `PM2 process manager`, uses: `Worker process`, verified_by: `tests/backend/test_lite_api.py`, verified_by: `tests/backend/test_lite_device_system_profile.py`, verified_by: `tests/backend/test_lite_security_s6_frontend_contract.py`, verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`, verified_by: `tests/docs/test_living_knowledgebase.py`

**Sources:** `architecture/metadata/pocket-lab-architecture.json`, `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh`
