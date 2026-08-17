---
title: "API ↔ UI reverse index"
description: "Cross-reference from FastAPI contracts to frontend consumers and back."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# API ↔ UI reverse index

## API → UI

| API | Domain | UI consumers | Operation | Confidence |
| --- | --- | --- | --- | --- |
| `DELETE /api/lite/apps/photoprism/storage-mappings/{mapping_id}` | apps | — | delete_photoprism_storage_mapping_api_lite_apps_photoprism_storage_mappings__mapping_id__delete | contract-derived |
| `DELETE /api/lite/identity/sessions/{session_id}` | identity | — | revoke_lite_identity_session_api_lite_identity_sessions__session_id__delete | contract-derived |
| `GET /api/lite/apps/lifecycle` | apps | — | get_lite_app_lifecycle_profiles_api_lite_apps_lifecycle_get | contract-derived |
| `GET /api/lite/apps/lifecycle/{app_id}` | apps | — | get_lite_app_lifecycle_profile_api_lite_apps_lifecycle__app_id__get | contract-derived |
| `GET /api/lite/apps/photoprism/storage-mappings` | apps | — | get_photoprism_storage_mappings_api_lite_apps_photoprism_storage_mappings_get | contract-derived |
| `GET /api/lite/apps/photoprism/storage-preview` | apps | — | get_photoprism_storage_preview_api_lite_apps_photoprism_storage_preview_get | contract-derived |
| `GET /api/lite/apps/{app_id}/action-history` | apps | — | get_lite_app_action_history_api_lite_apps__app_id__action_history_get | contract-derived |
| `GET /api/lite/apps/{app_id}/actions` | apps | — | get_lite_app_actions_api_lite_apps__app_id__actions_get | contract-derived |
| `GET /api/lite/apps/{app_id}/backup` | apps | — | get_lite_app_backup_status_api_lite_apps__app_id__backup_get | contract-derived |
| `GET /api/lite/apps/{app_id}/backups` | apps | — | list_lite_app_backups_api_lite_apps__app_id__backups_get | contract-derived |
| `GET /api/lite/apps/{app_id}/backups/{backup_id}/receipt` | apps | — | get_lite_app_backup_receipt_api_lite_apps__app_id__backups__backup_id__receipt_get | contract-derived |
| `GET /api/lite/apps/{app_id}/evidence` | apps | — | get_lite_app_evidence_api_lite_apps__app_id__evidence_get | contract-derived |
| `GET /api/lite/apps/{app_id}/restore/previews/{preview_id}` | apps | — | get_lite_app_restore_preview_api_lite_apps__app_id__restore_previews__preview_id__get | contract-derived |
| `GET /api/lite/apps/{app_id}/update` | apps | — | get_lite_app_update_status_api_lite_apps__app_id__update_get | contract-derived |
| `GET /api/lite/apps/{app_id}/update/receipts/{operation_id}` | apps | — | get_lite_app_update_receipt_api_lite_apps__app_id__update_receipts__operation_id__get | contract-derived |
| `GET /api/lite/catalog` | apps | LiteApp | get_lite_catalog_api_lite_catalog_get | contract-derived |
| `GET /api/lite/commands/history` | commands | — | get_lite_command_history_api_lite_commands_history_get | contract-derived |
| `GET /api/lite/devices/{device_id}` | devices | — | get_lite_device_details_api_lite_devices__device_id__get | contract-derived |
| `GET /api/lite/devices/{device_id}/health` | devices | — | get_lite_device_health_api_lite_devices__device_id__health_get | contract-derived |
| `GET /api/lite/devices/{device_id}/health/history` | devices | — | get_lite_device_health_history_api_lite_devices__device_id__health_history_get | contract-derived |
| `GET /api/lite/devices/{device_id}/history` | devices | — | get_lite_device_lifecycle_history_api_lite_devices__device_id__history_get | contract-derived |
| `GET /api/lite/devices/{device_id}/removal-assessment` | devices | LiteDevices | get_lite_device_removal_assessment_api_lite_devices__device_id__removal_assessment_get | contract-derived |
| `GET /api/lite/diagnostics/frontend-lifecycle/challenge` | diagnostics | — | get_frontend_lifecycle_diagnostics_challenge_api_lite_diagnostics_frontend_lifecycle_challenge_get | contract-derived |
| `GET /api/lite/diagnostics/runtime` | diagnostics | — | get_lite_runtime_diagnostics_api_lite_diagnostics_runtime_get | contract-derived |
| `GET /api/lite/diagnostics/runtime/full` | diagnostics | — | get_lite_runtime_diagnostics_full_api_lite_diagnostics_runtime_full_get | contract-derived |
| `GET /api/lite/events` | events | — | get_lite_revision_events_api_lite_events_get | contract-derived |
| `GET /api/lite/fleet` | devices | LiteDevices | get_lite_fleet_api_lite_fleet_get | contract-derived |
| `GET /api/lite/fleet/agent/bootstrap.sh` | devices | — | lite_fleet_agent_bootstrap_script_api_lite_fleet_agent_bootstrap_sh_get | contract-derived |
| `GET /api/lite/fleet/devices/{device_id}/recovery-history` | devices | — | get_lite_device_recovery_history_api_lite_fleet_devices__device_id__recovery_history_get | contract-derived |
| `GET /api/lite/fleet/devices/{node_id}/restart-agent/status` | devices | LiteDevices | lite_fleet_agent_restart_status_api_lite_fleet_devices__node_id__restart_agent_status_get | contract-derived |
| `GET /api/lite/fleet/health-summary` | devices | — | get_lite_fleet_health_summary_api_lite_fleet_health_summary_get | contract-derived |
| `GET /api/lite/fleet/invites/latest` | devices | — | get_latest_lite_fleet_invite_api_lite_fleet_invites_latest_get | contract-derived |
| `GET /api/lite/identity` | identity | LiteIdentity | get_lite_identity_api_lite_identity_get | contract-derived |
| `GET /api/lite/policy` | rules | LiteRules | get_lite_policy_api_lite_policy_get | contract-derived |
| `GET /api/lite/recovery` | recovery | — | get_lite_recovery_api_lite_recovery_get | contract-derived |
| `GET /api/lite/recovery/apps` | recovery | — | get_lite_recovery_apps_api_lite_recovery_apps_get | contract-derived |
| `GET /api/lite/recovery/apps/{app_id}` | recovery | — | get_lite_recovery_app_api_lite_recovery_apps__app_id__get | contract-derived |
| `GET /api/lite/recovery/apps/{app_id}/backup-targets` | recovery | — | get_lite_recovery_app_backup_targets_api_lite_recovery_apps__app_id__backup_targets_get | contract-derived |
| `GET /api/lite/recovery/backup-targets` | recovery | — | get_lite_backup_targets_api_lite_recovery_backup_targets_get | contract-derived |
| `GET /api/lite/recovery/backups` | recovery | — | list_lite_backups_api_lite_recovery_backups_get | contract-derived |
| `GET /api/lite/recovery/backups/{backup_id}` | recovery | — | get_lite_backup_api_lite_recovery_backups__backup_id__get | contract-derived |
| `GET /api/lite/recovery/database` | recovery | LiteRecovery | get_lite_database_recovery_api_lite_recovery_database_get | contract-derived |
| `GET /api/lite/recovery/database/backups` | recovery | — | list_lite_database_backups_api_lite_recovery_database_backups_get | contract-derived |
| `GET /api/lite/recovery/database/backups/{backup_id}` | recovery | — | get_lite_database_backup_api_lite_recovery_database_backups__backup_id__get | contract-derived |
| `GET /api/lite/recovery/database/restore/previews/{preview_id}` | recovery | — | get_lite_database_restore_preview_api_lite_recovery_database_restore_previews__preview_id__get | contract-derived |
| `GET /api/lite/recovery/database/restore/{restore_id}` | recovery | — | get_lite_database_restore_run_api_lite_recovery_database_restore__restore_id__get | contract-derived |
| `GET /api/lite/recovery/details` | recovery | LiteRecovery | get_lite_recovery_details_api_lite_recovery_details_get | contract-derived |
| `GET /api/lite/recovery/maintenance` | recovery | — | get_lite_recovery_maintenance_api_lite_recovery_maintenance_get | contract-derived |
| `GET /api/lite/recovery/operations` | recovery | — | get_lite_recovery_operation_history_api_lite_recovery_operations_get | contract-derived |
| `GET /api/lite/recovery/receipts/{backup_id}` | recovery | — | get_lite_backup_receipt_api_lite_recovery_receipts__backup_id__get | contract-derived |
| `GET /api/lite/recovery/restore/checkpoints/{checkpoint_id}` | recovery | — | get_lite_restore_checkpoint_api_lite_recovery_restore_checkpoints__checkpoint_id__get | contract-derived |
| `GET /api/lite/recovery/restore/previews/{preview_id}` | recovery | — | get_lite_restore_preview_api_lite_recovery_restore_previews__preview_id__get | contract-derived |
| `GET /api/lite/recovery/restore/runs/{restore_id}` | recovery | — | get_lite_restore_run_api_lite_recovery_restore_runs__restore_id__get | contract-derived |
| `GET /api/lite/recovery/summary` | recovery | LiteRecovery | get_lite_recovery_summary_api_lite_recovery_summary_get | contract-derived |
| `GET /api/lite/release` | release | LiteReleaseUpdateCard | release_status_api_lite_release_get | contract-derived |
| `GET /api/lite/remote-access/readiness` | remote-access | — | get_lite_remote_access_readiness_api_lite_remote_access_readiness_get | contract-derived |
| `GET /api/lite/revisions` | home | LiteRevisionSyncBridge | get_lite_domain_revisions_api_lite_revisions_get | contract-derived |
| `GET /api/lite/security` | security | — | get_lite_security_api_lite_security_get | contract-derived |
| `GET /api/lite/security/apps` | security | — | get_lite_security_apps_api_lite_security_apps_get | contract-derived |
| `GET /api/lite/security/apps/{app_id}` | security | — | get_lite_security_app_api_lite_security_apps__app_id__get | contract-derived |
| `GET /api/lite/security/details/{run_id}` | security | — | get_lite_security_details_api_lite_security_details__run_id__get | contract-derived |
| `GET /api/lite/security/events` | security | — | get_lite_security_events_api_lite_security_events_get | contract-derived |
| `GET /api/lite/security/evidence/{run_id}` | security | — | get_lite_security_evidence_api_lite_security_evidence__run_id__get | contract-derived |
| `GET /api/lite/security/evidence/{run_id}/summary` | security | LiteSecurity | get_lite_security_evidence_summary_api_lite_security_evidence__run_id__summary_get | contract-derived |
| `GET /api/lite/security/freshness` | security | LiteSecurity | get_lite_security_freshness_api_lite_security_freshness_get | contract-derived |
| `GET /api/lite/security/history` | security | LiteSecurity | get_lite_security_history_api_lite_security_history_get | contract-derived |
| `GET /api/lite/security/profiles/{profile}` | security | LiteSecurity | get_lite_security_profile_api_lite_security_profiles__profile__get | contract-derived |
| `GET /api/lite/security/progress` | security | LiteSecurity | get_lite_security_progress_api_lite_security_progress_get | contract-derived |
| `GET /api/lite/security/runs/{run_id}` | security | — | get_lite_security_run_api_lite_security_runs__run_id__get | contract-derived |
| `GET /api/lite/security/summary` | security | LiteSecurity | get_lite_security_summary_api_lite_security_summary_get | contract-derived |
| `GET /api/lite/status` | home | — | get_lite_status_api_lite_status_get | contract-derived |
| `GET /api/lite/system/activity-summary` | system | — | get_lite_activity_summary_api_lite_system_activity_summary_get | contract-derived |
| `GET /api/lite/system/agent` | system | — | get_lite_system_agent_api_lite_system_agent_get | contract-derived |
| `GET /api/lite/system/health` | system | — | get_lite_system_health_api_lite_system_health_get | contract-derived |
| `GET /api/lite/system/nats-readiness` | system | — | get_lite_nats_readiness_api_lite_system_nats_readiness_get | contract-derived |
| `GET /api/lite/system/processes` | system | — | get_lite_system_processes_api_lite_system_processes_get | contract-derived |
| `GET /api/lite/system/sqlite-health` | system | — | get_lite_sqlite_health_api_lite_system_sqlite_health_get | contract-derived |
| `GET /api/lite/system/storage-pressure` | system | — | get_lite_storage_pressure_api_lite_system_storage_pressure_get | contract-derived |
| `GET /api/lite/system/supervisor` | system | — | get_lite_system_supervisor_api_lite_system_supervisor_get | contract-derived |
| `GET /api/lite/system/telemetry-thresholds` | system | — | get_lite_telemetry_thresholds_api_lite_system_telemetry_thresholds_get | contract-derived |
| `GET /health` | platform | — | health_health_get | contract-derived |
| `GET /ready` | platform | — | ready_ready_get | contract-derived |
| `POST /api/lite/apps/photoprism/storage-mappings` | apps | — | create_photoprism_storage_mapping_api_lite_apps_photoprism_storage_mappings_post | contract-derived |
| `POST /api/lite/apps/{app_id}/actions/{action_id}` | apps | — | run_lite_app_action_api_lite_apps__app_id__actions__action_id__post | contract-derived |
| `POST /api/lite/apps/{app_id}/backup` | apps | LiteRecovery | start_lite_app_backup_api_lite_apps__app_id__backup_post | contract-derived |
| `POST /api/lite/apps/{app_id}/backup/storage-device` | apps | — | start_lite_app_backup_to_storage_device_api_lite_apps__app_id__backup_storage_device_post | contract-derived |
| `POST /api/lite/apps/{app_id}/restore/preview` | apps | LiteRecovery | start_lite_app_restore_preview_api_lite_apps__app_id__restore_preview_post | contract-derived |
| `POST /api/lite/apps/{app_id}/update/apply` | apps | — | apply_lite_app_update_api_lite_apps__app_id__update_apply_post | contract-derived |
| `POST /api/lite/catalog/install` | apps | — | install_lite_catalog_item_api_lite_catalog_install_post | contract-derived |
| `POST /api/lite/catalog/remove` | apps | — | remove_lite_catalog_item_api_lite_catalog_remove_post | contract-derived |
| `POST /api/lite/diagnostics/frontend-lifecycle` | diagnostics | — | record_frontend_lifecycle_diagnostics_api_lite_diagnostics_frontend_lifecycle_post | contract-derived |
| `POST /api/lite/fleet/add-device` | devices | LiteDevices | add_lite_device_api_lite_fleet_add_device_post | contract-derived |
| `POST /api/lite/fleet/agent/bootstrap-blocked` | devices | — | lite_fleet_agent_bootstrap_blocked_api_lite_fleet_agent_bootstrap_blocked_post | contract-derived |
| `POST /api/lite/fleet/agent/bootstrap.env` | devices | — | lite_fleet_agent_bootstrap_env_api_lite_fleet_agent_bootstrap_env_post | contract-derived |
| `POST /api/lite/fleet/devices/{node_id}/restart-agent` | devices | LiteDevices | restart_lite_fleet_agent_api_lite_fleet_devices__node_id__restart_agent_post | contract-derived |
| `POST /api/lite/fleet/invites/{invite_id}/revoke` | devices | — | revoke_lite_fleet_invite_api_lite_fleet_invites__invite_id__revoke_post | contract-derived |
| `POST /api/lite/fleet/remove-device` | devices | LiteDevices | remove_lite_device_api_lite_fleet_remove_device_post | contract-derived |
| `POST /api/lite/identity/login` | identity | LiteIdentity | login_lite_identity_api_lite_identity_login_post | contract-derived |
| `POST /api/lite/identity/logout` | identity | LiteIdentity | logout_lite_identity_api_lite_identity_logout_post | contract-derived |
| `POST /api/lite/identity/password` | identity | LiteIdentity | change_lite_identity_password_api_lite_identity_password_post | contract-derived |
| `POST /api/lite/identity/recover` | identity | LiteIdentity | recover_lite_identity_api_lite_identity_recover_post | contract-derived |
| `POST /api/lite/identity/recovery/regenerate` | identity | LiteIdentity | regenerate_lite_identity_recovery_api_lite_identity_recovery_regenerate_post | contract-derived |
| `POST /api/lite/identity/rotate` | identity | — | rotate_lite_identity_api_lite_identity_rotate_post | contract-derived |
| `POST /api/lite/identity/sessions/revoke-others` | identity | LiteIdentity | revoke_other_lite_identity_sessions_api_lite_identity_sessions_revoke_others_post | contract-derived |
| `POST /api/lite/identity/setup` | identity | LiteIdentity | setup_lite_identity_api_lite_identity_setup_post | contract-derived |
| `POST /api/lite/policy/apply` | rules | — | apply_lite_policy_api_lite_policy_apply_post | contract-derived |
| `POST /api/lite/recovery/apps/{app_id}/backup` | recovery | — | backup_lite_app_api_lite_recovery_apps__app_id__backup_post | contract-derived |
| `POST /api/lite/recovery/apps/{app_id}/backup-to-target` | recovery | — | backup_lite_app_to_target_api_lite_recovery_apps__app_id__backup_to_target_post | contract-derived |
| `POST /api/lite/recovery/apps/{app_id}/restore` | recovery | — | restore_lite_app_api_lite_recovery_apps__app_id__restore_post | contract-derived |
| `POST /api/lite/recovery/apps/{app_id}/restore/preview` | recovery | — | preview_lite_app_restore_api_lite_recovery_apps__app_id__restore_preview_post | contract-derived |
| `POST /api/lite/recovery/backup` | recovery | LiteRecovery | backup_lite_api_lite_recovery_backup_post | contract-derived |
| `POST /api/lite/recovery/backups/{backup_id}/verify` | recovery | LiteRecovery | verify_lite_backup_api_lite_recovery_backups__backup_id__verify_post | contract-derived |
| `POST /api/lite/recovery/database/backup` | recovery | LiteRecovery | backup_lite_database_api_lite_recovery_database_backup_post | contract-derived |
| `POST /api/lite/recovery/database/backups/{backup_id}/preview` | recovery | LiteRecovery | preview_lite_database_restore_api_lite_recovery_database_backups__backup_id__preview_post | contract-derived |
| `POST /api/lite/recovery/database/backups/{backup_id}/restore` | recovery | LiteRecovery | restore_lite_database_api_lite_recovery_database_backups__backup_id__restore_post | contract-derived |
| `POST /api/lite/recovery/database/backups/{backup_id}/verify` | recovery | LiteRecovery | verify_lite_database_backup_api_lite_recovery_database_backups__backup_id__verify_post | contract-derived |
| `POST /api/lite/recovery/maintenance/checkpoint` | recovery | — | run_lite_recovery_checkpoint_api_lite_recovery_maintenance_checkpoint_post | contract-derived |
| `POST /api/lite/recovery/maintenance/retention` | recovery | — | run_lite_recovery_retention_api_lite_recovery_maintenance_retention_post | contract-derived |
| `POST /api/lite/recovery/restore` | recovery | LiteRecovery | restore_lite_api_lite_recovery_restore_post | contract-derived |
| `POST /api/lite/recovery/restore/preview` | recovery | LiteRecovery | preview_lite_restore_api_lite_recovery_restore_preview_post | contract-derived |
| `POST /api/lite/release/apply` | release | LiteReleaseUpdateCard | release_apply_api_lite_release_apply_post | contract-derived |
| `POST /api/lite/release/check` | release | LiteReleaseUpdateCard | release_check_api_lite_release_check_post | contract-derived |
| `POST /api/lite/security/apps/{app_id}/check` | security | LiteSecurity | check_lite_security_app_api_lite_security_apps__app_id__check_post | contract-derived |
| `POST /api/lite/security/check` | security | LiteSecurity | check_lite_security_api_lite_security_check_post | contract-derived |
| `POST /api/lite/security/scan` | security | — | scan_lite_security_api_lite_security_scan_post | contract-derived |
| `PUT /api/lite/fleet/devices/{device_id}/display-model` | devices | — | update_lite_device_display_model_api_lite_fleet_devices__device_id__display_model_put | contract-derived |

## UI → API

| UI | APIs |
| --- | --- |
| LiteApp | GET /api/lite/catalog |
| LiteDevices | GET /api/lite/devices/{device_id}/removal-assessment, GET /api/lite/fleet, GET /api/lite/fleet/devices/{node_id}/restart-agent/status, POST /api/lite/fleet/add-device, POST /api/lite/fleet/devices/{node_id}/restart-agent, POST /api/lite/fleet/remove-device |
| LiteIdentity | GET /api/lite/identity, POST /api/lite/identity/login, POST /api/lite/identity/logout, POST /api/lite/identity/password, POST /api/lite/identity/recover, POST /api/lite/identity/recovery/regenerate, POST /api/lite/identity/sessions/revoke-others, POST /api/lite/identity/setup |
| LiteRecovery | GET /api/lite/recovery/database, GET /api/lite/recovery/details, GET /api/lite/recovery/summary, POST /api/lite/apps/{app_id}/backup, POST /api/lite/apps/{app_id}/restore/preview, POST /api/lite/recovery/backup, POST /api/lite/recovery/backups/{backup_id}/verify, POST /api/lite/recovery/database/backup, POST /api/lite/recovery/database/backups/{backup_id}/preview, POST /api/lite/recovery/database/backups/{backup_id}/restore, POST /api/lite/recovery/database/backups/{backup_id}/verify, POST /api/lite/recovery/restore, POST /api/lite/recovery/restore/preview |
| LiteReleaseUpdateCard | GET /api/lite/release, POST /api/lite/release/apply, POST /api/lite/release/check |
| LiteRevisionSyncBridge | GET /api/lite/revisions |
| LiteRules | GET /api/lite/policy |
| LiteSecurity | GET /api/lite/security/evidence/{run_id}/summary, GET /api/lite/security/freshness, GET /api/lite/security/history, GET /api/lite/security/profiles/{profile}, GET /api/lite/security/progress, GET /api/lite/security/summary, POST /api/lite/security/apps/{app_id}/check, POST /api/lite/security/check |
