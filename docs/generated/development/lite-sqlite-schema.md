---
title: "Lite SQLite schema"
description: "Data-free migration-derived SQLite tables, views, columns, relationships, owners and classifications."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: e1295d7d81ac8527f7d9268063a4a783d84f2165bcfc3ebc4c033ff85f42ef7b
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Lite SQLite schema

The generator applies migrations to a temporary database, deletes all seed rows, verifies every table has zero rows, introspects the schema, then securely removes the database. It never opens a live Pocket Lab database.

[Open the normalized SchemaSpy HTML reference](../schemaspy/index.html).

Semantic rows marked **inferred** are conservative source-derived ownership hints and are not promoted to verified runtime truth.

| Object | Type | Columns | FKs | Indexes | Domain | Writer | Classification | Semantic status | Migration source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `app_action_lifecycle` | table | 10 | 0 | 4 | apps | App Catalog lifecycle and action services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0016_phase3c_system_aggregates.sql |
| `app_current_state` | table | 20 | 0 | 3 | apps | App Catalog lifecycle and action services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0007_app_current_subprojections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0008_app_current_hot_subprojections.sql |
| `audit_evidence_index` | table | 10 | 0 | 4 | audit | audit evidence indexing services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0016_phase3c_system_aggregates.sql |
| `auth_session_assurance` | table | 7 | 2 | 2 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `auth_sessions` | table | 12 | 1 | 3 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0024_identity_rules_authorization.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `backup_manifest_index` | table | 11 | 0 | 2 | recovery | Recovery services and worker completion handlers | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql |
| `command_lifecycle` | table | 19 | 0 | 8 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0009_lite_revision_events.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0017_command_lifecycle_reconciliation.sql |
| `device_awareness_state` | table | 33 | 1 | 4 | devices | device lifecycle and projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0011_device_trust_capability_awareness.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0022_device_durable_enrollment.sql |
| `device_current_state` | table | 20 | 0 | 4 | devices | fleet/device projection writer | restricted operational metadata | verified | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0010_device_system_profiles.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0011_device_trust_capability_awareness.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0012_device_proactive_health.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0014_transactional_lifecycle_projection_scheduler.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0022_device_durable_enrollment.sql |
| `device_enrollment_registry` | table | 22 | 0 | 4 | devices | device lifecycle and projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0022_device_durable_enrollment.sql |
| `device_health_attention` | table | 16 | 1 | 4 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0012_device_proactive_health.sql |
| `device_health_current` | table | 27 | 1 | 3 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0012_device_proactive_health.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0023_device_runtime_truth.sql |
| `device_health_transitions` | table | 11 | 1 | 2 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0012_device_proactive_health.sql |
| `device_heartbeats` | table | 13 | 0 | 3 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql |
| `device_identity_guards` | table | 6 | 0 | 1 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql |
| `device_invite_lifecycle` | table | 11 | 0 | 4 | devices | device lifecycle and projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql |
| `device_lifecycle_events` | table | 16 | 1 | 5 | devices | device lifecycle and projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0011_device_trust_capability_awareness.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0013_device_lifecycle_idempotency.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0014_transactional_lifecycle_projection_scheduler.sql |
| `device_lifecycle_transactions` | table | 16 | 2 | 5 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0014_transactional_lifecycle_projection_scheduler.sql |
| `device_recovery_history` | table | 9 | 0 | 2 | devices | device lifecycle and projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql |
| `device_removal_receipts` | table | 12 | 1 | 2 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0022_device_durable_enrollment.sql |
| `device_supervisor_state` | table | 15 | 0 | 2 | devices | device lifecycle and projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0023_device_runtime_truth.sql |
| `device_system_profiles` | table | 36 | 1 | 2 | devices | device lifecycle and projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0010_device_system_profiles.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0023_device_runtime_truth.sql |
| `domain_revisions` | table | 3 | 0 | 1 | projections | prepared projection scheduler | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0015_phase3b_system_current_state.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0016_phase3c_system_aggregates.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0018_projection_semantic_hardening.sql |
| `enterprise_configuration` | table | 8 | 1 | 0 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0026_enterprise_identity_p2.sql |
| `enterprise_memberships` | table | 8 | 3 | 2 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0026_enterprise_identity_p2.sql |
| `human_credentials` | table | 10 | 1 | 2 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0024_identity_rules_authorization.sql |
| `human_identities` | table | 8 | 0 | 2 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0024_identity_rules_authorization.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0026_enterprise_identity_p2.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0027_policy_revision_activation_p2.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0028_policy_approvals_exceptions_p3.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0029_policy_uncertain_resolution_p2.sql |
| `identity_audit_events` | table | 8 | 0 | 1 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0024_identity_rules_authorization.sql |
| `lite_installed_release_identity` | table | 18 | 0 | 2 | release | release runtime and identity services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0021_lite_native_release.sql |
| `lite_revision_events` | table | 10 | 0 | 3 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0009_lite_revision_events.sql |
| `owner_claims` | table | 12 | 0 | 4 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `phase3b_current_state` | table | 12 | 0 | 3 | prepared_state | prepared state projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0015_phase3b_system_current_state.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0018_projection_semantic_hardening.sql |
| `phase3b_revision_events` | table | 16 | 0 | 4 | prepared_state | prepared state projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0015_phase3b_system_current_state.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0018_projection_semantic_hardening.sql |
| `policy_activation_operations` | table | 12 | 3 | 3 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0027_policy_revision_activation_p2.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0029_policy_uncertain_resolution_p2.sql |
| `policy_approvals` | table | 23 | 2 | 4 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0028_policy_approvals_exceptions_p3.sql |
| `policy_continuation_events` | table | 9 | 0 | 1 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0028_policy_approvals_exceptions_p3.sql |
| `policy_decision_details` | table | 3 | 1 | 1 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `policy_decisions` | table | 14 | 0 | 3 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0024_identity_rules_authorization.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `policy_recovery_resolutions` | table | 10 | 2 | 3 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0029_policy_uncertain_resolution_p2.sql |
| `policy_revisions` | table | 15 | 2 | 3 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0027_policy_revision_activation_p2.sql |
| `policy_runtime_state` | table | 5 | 2 | 0 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0027_policy_revision_activation_p2.sql |
| `policy_temporary_exceptions` | table | 13 | 2 | 2 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0028_policy_approvals_exceptions_p3.sql |
| `projection_dirty_signals` | table | 7 | 0 | 2 | projections | prepared projection scheduler | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0018_projection_semantic_hardening.sql |
| `projection_refresh_state` | table | 30 | 0 | 2 | projections | projection scheduler | internal metadata | verified | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0014_transactional_lifecycle_projection_scheduler.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0018_projection_semantic_hardening.sql |
| `recovery_code_batches` | table | 5 | 1 | 2 | recovery | Recovery services and worker completion handlers | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0024_identity_rules_authorization.sql |
| `recovery_codes` | table | 5 | 1 | 3 | recovery | Recovery services and worker completion handlers | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0024_identity_rules_authorization.sql |
| `recovery_current_state` | table | 11 | 0 | 0 | recovery | Recovery services and worker completion handlers | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql |
| `recovery_operations` | table | 11 | 0 | 4 | recovery | Recovery services and worker completion handlers | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0006_control_plane_projections.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0016_phase3c_system_aggregates.sql |
| `release_runtime_projection` | table | 64 | 0 | 3 | release | release runtime and identity services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0020_release_runtime_process.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0021_lite_native_release.sql |
| `schema_migrations` | table | 4 | 0 | 0 | database | SQLite migration runner | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql |
| `security_database_backups` | table | 11 | 0 | 2 | security | Security store and scanner completion services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0004_security_maintenance.sql |
| `security_database_restores` | table | 10 | 1 | 2 | security | Security store and scanner completion services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0004_security_maintenance.sql |
| `security_maintenance_runs` | table | 9 | 0 | 3 | security | Security store and scanner completion services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0004_security_maintenance.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0016_phase3c_system_aggregates.sql |
| `security_profile_snapshots` | table | 10 | 1 | 1 | security | Security store and scanner completion services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql |
| `security_scan_evidence_refs` | table | 8 | 1 | 2 | security | Security store and scanner completion services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql |
| `security_scan_findings` | table | 15 | 1 | 3 | security | Security store and scanner completion services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql |
| `security_scan_progress_events` | table | 12 | 1 | 4 | security | Security store and scanner completion services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql |
| `security_scan_runs` | table | 47 | 0 | 10 | security | Security API/worker store | sanitized operational metadata | verified | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0002_security_delivery_lifecycle.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0003_security_progress_lookup.sql, pocket-lab-final-structure/runtime/api_fastapi/db/schema/0005_security_read_performance.sql |
| `security_scan_tool_runs` | table | 11 | 1 | 2 | security | Security store and scanner completion services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql |
| `security_store_metadata` | table | 3 | 0 | 1 | security | Security store and scanner completion services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0001_security_store.sql |
| `webauthn_challenges` | table | 11 | 3 | 3 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `webauthn_credentials` | table | 12 | 1 | 2 | control_plane | source-defined control-plane service | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `webauthn_users` | table | 3 | 1 | 2 | control_plane | source-defined control-plane service | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0025_identity_passkeys_rules_p1.sql |
| `workflow_command_state` | table | 10 | 0 | 2 | workflow | workflow projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0019_workflow_projection_process.sql |
| `workflow_current_state` | table | 11 | 0 | 3 | workflow | workflow projection services | restricted operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0019_workflow_projection_process.sql |
| `workflow_event_index` | table | 9 | 0 | 2 | workflow | workflow projection services | internal operational metadata | inferred | pocket-lab-final-structure/runtime/api_fastapi/db/schema/0019_workflow_projection_process.sql |

<a id="app-action-lifecycle"></a>
## `app_action_lifecycle`

Source-derived apps persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `operation_id` | TEXT | yes | — | 1 |
| `app_id` | TEXT | no | — | 0 |
| `action_id` | TEXT | no | — | 0 |
| `status` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `source_ref` | TEXT | no | '' | 0 |
| `summary` | TEXT | no | '' | 0 |
| `metadata_json` | TEXT | no | '{}' | 0 |

<a id="app-current-state"></a>
## `app_current_state`

Source-derived apps persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `app_id` | TEXT | yes | — | 1 |
| `app_name` | TEXT | no | — | 0 |
| `status` | TEXT | no | 'unknown' | 0 |
| `installed` | INTEGER | no | 0 | 0 |
| `health_state` | TEXT | no | 'unknown' | 0 |
| `latest_action_id` | TEXT | yes | — | 0 |
| `latest_action_status` | TEXT | yes | — | 0 |
| `latest_backup_id` | TEXT | yes | — | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |
| `catalog_state_json` | TEXT | no | '{}' | 0 |
| `media_state_json` | TEXT | no | '{}' | 0 |
| `operation_state_json` | TEXT | no | '{}' | 0 |
| `update_state_json` | TEXT | no | '{}' | 0 |
| `backup_profile_json` | TEXT | no | '{}' | 0 |
| `projection_version` | INTEGER | no | 1 | 0 |
| `security_profile_json` | TEXT | no | '{}' | 0 |
| `backup_targets_json` | TEXT | no | '{}' | 0 |

<a id="audit-evidence-index"></a>
## `audit_evidence_index`

Source-derived audit persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `evidence_index_id` | INTEGER | yes | — | 1 |
| `event_type` | TEXT | no | — | 0 |
| `entity_type` | TEXT | no | — | 0 |
| `entity_id` | TEXT | no | — | 0 |
| `operation_id` | TEXT | no | '' | 0 |
| `status` | TEXT | no | 'unknown' | 0 |
| `evidence_ref` | TEXT | no | '' | 0 |
| `created_at` | TEXT | no | — | 0 |
| `created_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="auth-session-assurance"></a>
## `auth_session_assurance`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `assurance_id` | TEXT | yes | — | 1 |
| `session_id` | TEXT | no | — | 0 |
| `credential_id` | TEXT | no | — | 0 |
| `purpose` | TEXT | no | — | 0 |
| `satisfied_at` | TEXT | no | — | 0 |
| `expires_at` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |

<a id="auth-sessions"></a>
## `auth_sessions`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `session_id` | TEXT | yes | — | 1 |
| `token_hash` | TEXT | no | — | 0 |
| `csrf_hash` | TEXT | no | — | 0 |
| `human_id` | TEXT | no | — | 0 |
| `auth_version` | INTEGER | no | — | 0 |
| `auth_method` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `last_seen_at` | TEXT | no | — | 0 |
| `idle_expires_at` | TEXT | no | — | 0 |
| `absolute_expires_at` | TEXT | no | — | 0 |
| `revoked_at` | TEXT | yes | — | 0 |
| `revoke_reason` | TEXT | yes | — | 0 |

<a id="backup-manifest-index"></a>
## `backup_manifest_index`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `backup_id` | TEXT | yes | — | 1 |
| `backup_type` | TEXT | no | 'lite' | 0 |
| `status` | TEXT | no | 'unknown' | 0 |
| `verification_status` | TEXT | no | 'unknown' | 0 |
| `created_at` | TEXT | yes | — | 0 |
| `verified_at` | TEXT | yes | — | 0 |
| `size_bytes` | INTEGER | no | 0 | 0 |
| `source_ref` | TEXT | no | '' | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="command-lifecycle"></a>
## `command_lifecycle`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `command_id` | TEXT | yes | — | 1 |
| `entity_type` | TEXT | no | — | 0 |
| `entity_id` | TEXT | no | — | 0 |
| `operation_type` | TEXT | no | '' | 0 |
| `status` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `deadline_at` | TEXT | yes | — | 0 |
| `source_ref` | TEXT | no | '' | 0 |
| `summary` | TEXT | no | '' | 0 |
| `metadata_json` | TEXT | no | '{}' | 0 |
| `lifecycle_stage` | TEXT | no | 'accepted' | 0 |
| `terminal_at` | TEXT | yes | — | 0 |
| `ignored_redelivery` | INTEGER | no | 0 | 0 |
| `recovery_action` | TEXT | no | '' | 0 |
| `attention_status` | TEXT | no | 'none' | 0 |
| `attention_updated_at` | TEXT | yes | — | 0 |
| `attention_updated_at_epoch_ms` | INTEGER | no | 0 | 0 |

<a id="device-awareness-state"></a>
## `device_awareness_state`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `device_id` | TEXT | yes | — | 1 |
| `enrollment_status` | TEXT | no | 'not_enrolled' | 0 |
| `identity_status` | TEXT | no | 'pending' | 0 |
| `identity_verified_at` | TEXT | yes | — | 0 |
| `identity_verified_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `identity_mismatch_count` | INTEGER | no | 0 | 0 |
| `last_identity_mismatch_at` | TEXT | yes | — | 0 |
| `last_identity_mismatch_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `blocked_join_count` | INTEGER | no | 0 | 0 |
| `last_blocked_join_at` | TEXT | yes | — | 0 |
| `repair_required` | INTEGER | no | 0 | 0 |
| `last_seen_at` | TEXT | yes | — | 0 |
| `last_seen_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `last_seen_source` | TEXT | no | 'unknown' | 0 |
| `staleness_state` | TEXT | no | 'unknown' | 0 |
| `command_delivery_status` | TEXT | no | 'unknown' | 0 |
| `supervisor_status` | TEXT | no | 'unknown' | 0 |
| `recovery_status` | TEXT | no | 'unknown' | 0 |
| `hosted_app_count` | INTEGER | no | 0 | 0 |
| `backup_dependency_count` | INTEGER | no | 0 | 0 |
| `storage_dependency_count` | INTEGER | no | 0 | 0 |
| `capability_revision` | TEXT | no | '' | 0 |
| `capabilities_json` | TEXT | no | '[]' | 0 |
| `dependencies_json` | TEXT | no | '{}' | 0 |
| `removal_safe` | INTEGER | no | 0 | 0 |
| `removal_assessment_revision` | TEXT | no | '' | 0 |
| `removal_assessment_json` | TEXT | no | '{}' | 0 |
| `trust_json` | TEXT | no | '{}' | 0 |
| `enrollment_json` | TEXT | no | '{}' | 0 |
| `last_seen_json` | TEXT | no | '{}' | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `revision` | INTEGER | no | 0 | 0 |

<a id="device-current-state"></a>
## `device_current_state`

Durable current enrolled-device projection

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `device_id` | TEXT | yes | — | 1 |
| `device_name` | TEXT | no | — | 0 |
| `role` | TEXT | no | 'compute' | 0 |
| `ui_state` | TEXT | no | 'Waiting' | 0 |
| `connection_state` | TEXT | no | 'unknown' | 0 |
| `agent_status` | TEXT | no | 'unknown' | 0 |
| `supervisor_status` | TEXT | no | 'unknown' | 0 |
| `pm2_status` | TEXT | no | 'unknown' | 0 |
| `remote_access_ready` | INTEGER | no | 0 | 0 |
| `protected_server_host` | INTEGER | no | 0 | 0 |
| `source_heartbeat_id` | TEXT | yes | — | 0 |
| `latest_command_id` | TEXT | yes | — | 0 |
| `latest_invite_id` | TEXT | yes | — | 0 |
| `latest_recovery_id` | TEXT | yes | — | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `last_seen_at` | TEXT | yes | — | 0 |
| `last_seen_epoch_ms` | INTEGER | no | 0 | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="device-enrollment-registry"></a>
## `device_enrollment_registry`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `device_id` | TEXT | yes | — | 1 |
| `device_name` | TEXT | no | — | 0 |
| `normalized_name` | TEXT | no | '' | 0 |
| `role` | TEXT | no | 'compute' | 0 |
| `enrollment_status` | TEXT | no | 'enrolled' | 0 |
| `identity_status` | TEXT | no | 'pending' | 0 |
| `enrolled_at` | TEXT | no | — | 0 |
| `enrolled_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `last_known_state` | TEXT | no | 'offline' | 0 |
| `last_seen_at` | TEXT | yes | — | 0 |
| `last_seen_epoch_ms` | INTEGER | no | 0 | 0 |
| `retired_at` | TEXT | yes | — | 0 |
| `retired_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `removal_status` | TEXT | no | 'active' | 0 |
| `removal_reason` | TEXT | no | '' | 0 |
| `protected_server_host` | INTEGER | no | 0 | 0 |
| `canonical_identity_json` | TEXT | no | '{}' | 0 |
| `last_valid_state_json` | TEXT | no | '{}' | 0 |
| `registry_revision` | INTEGER | no | 1 | 0 |
| `canonical_hash` | TEXT | no | '' | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | 0 | 0 |

<a id="device-health-attention"></a>
## `device_health_attention`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `attention_id` | TEXT | yes | — | 1 |
| `device_id` | TEXT | no | — | 0 |
| `reason_code` | TEXT | no | — | 0 |
| `category` | TEXT | no | — | 0 |
| `severity` | TEXT | no | — | 0 |
| `status` | TEXT | no | 'active' | 0 |
| `summary` | TEXT | no | '' | 0 |
| `recommendation` | TEXT | no | '' | 0 |
| `recommendation_code` | TEXT | no | 'review_device' | 0 |
| `created_at` | TEXT | no | — | 0 |
| `created_at_epoch_ms` | INTEGER | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `resolved_at` | TEXT | yes | — | 0 |
| `resolved_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |

<a id="device-health-current"></a>
## `device_health_current`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `device_id` | TEXT | yes | — | 1 |
| `health_status` | TEXT | no | 'unknown' | 0 |
| `health_severity` | TEXT | no | 'none' | 0 |
| `resource_status` | TEXT | no | 'unknown' | 0 |
| `connection_status` | TEXT | no | 'unknown' | 0 |
| `recovery_status` | TEXT | no | 'unknown' | 0 |
| `version_status` | TEXT | no | 'unknown' | 0 |
| `dependency_impact_status` | TEXT | no | 'unknown' | 0 |
| `reason_codes_json` | TEXT | no | '[]' | 0 |
| `recommendation_code` | TEXT | no | 'review_device' | 0 |
| `recommendation_target` | TEXT | yes | — | 0 |
| `attention_count` | INTEGER | no | 0 | 0 |
| `health_revision` | TEXT | no | '' | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `source_freshness_json` | TEXT | no | '{}' | 0 |
| `resources_json` | TEXT | no | '{}' | 0 |
| `connection_json` | TEXT | no | '{}' | 0 |
| `recovery_json` | TEXT | no | '{}' | 0 |
| `versions_json` | TEXT | no | '{}' | 0 |
| `dependency_impact_json` | TEXT | no | '{}' | 0 |
| `summary` | TEXT | no | '' | 0 |
| `last_evaluated_at` | TEXT | no | — | 0 |
| `last_evaluated_at_epoch_ms` | INTEGER | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `revision` | INTEGER | no | 0 | 0 |
| `dimensions_json` | TEXT | no | '{}' | 0 |

<a id="device-health-transitions"></a>
## `device_health_transitions`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `transition_row_id` | INTEGER | yes | — | 1 |
| `event_id` | TEXT | no | — | 0 |
| `device_id` | TEXT | no | — | 0 |
| `previous_state` | TEXT | no | — | 0 |
| `new_state` | TEXT | no | — | 0 |
| `reason_codes_json` | TEXT | no | '[]' | 0 |
| `summary` | TEXT | no | '' | 0 |
| `occurred_at` | TEXT | no | — | 0 |
| `occurred_at_epoch_ms` | INTEGER | no | — | 0 |
| `resolved_at` | TEXT | yes | — | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |

<a id="device-heartbeats"></a>
## `device_heartbeats`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `heartbeat_row_id` | INTEGER | yes | — | 1 |
| `device_id` | TEXT | no | — | 0 |
| `heartbeat_id` | TEXT | no | — | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `connection_state` | TEXT | no | 'unknown' | 0 |
| `agent_status` | TEXT | no | 'unknown' | 0 |
| `supervisor_status` | TEXT | no | 'unknown' | 0 |
| `pm2_status` | TEXT | no | 'unknown' | 0 |
| `remote_access_ready` | INTEGER | no | 0 | 0 |
| `protected_server_host` | INTEGER | no | 0 | 0 |
| `observed_at` | TEXT | no | — | 0 |
| `observed_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="device-identity-guards"></a>
## `device_identity_guards`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `identity_key` | TEXT | yes | — | 1 |
| `device_id` | TEXT | no | — | 0 |
| `normalized_name` | TEXT | no | '' | 0 |
| `protected_server_host` | INTEGER | no | 0 | 0 |
| `source` | TEXT | no | 'fleet-projection' | 0 |
| `updated_at` | TEXT | no | — | 0 |

<a id="device-invite-lifecycle"></a>
## `device_invite_lifecycle`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `invite_id` | TEXT | yes | — | 1 |
| `device_id` | TEXT | no | '' | 0 |
| `device_name` | TEXT | no | '' | 0 |
| `role` | TEXT | no | '' | 0 |
| `status` | TEXT | no | — | 0 |
| `created_at` | TEXT | yes | — | 0 |
| `expires_at` | TEXT | yes | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="device-lifecycle-events"></a>
## `device_lifecycle_events`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `event_row_id` | INTEGER | yes | — | 1 |
| `event_id` | TEXT | no | — | 0 |
| `device_id` | TEXT | no | — | 0 |
| `event_type` | TEXT | no | — | 0 |
| `reason_code` | TEXT | no | '' | 0 |
| `status` | TEXT | no | 'recorded' | 0 |
| `occurred_at` | TEXT | no | — | 0 |
| `occurred_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `dedupe_key` | TEXT | yes | — | 0 |
| `generation_key` | TEXT | yes | — | 0 |
| `state_revision` | INTEGER | no | 0 | 0 |
| `database_instance` | TEXT | no | '' | 0 |
| `payload_checksum` | TEXT | no | '' | 0 |

<a id="device-lifecycle-transactions"></a>
## `device_lifecycle_transactions`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `transaction_id` | TEXT | yes | — | 1 |
| `device_id` | TEXT | no | — | 0 |
| `event_id` | TEXT | no | — | 0 |
| `event_type` | TEXT | no | — | 0 |
| `dedupe_key` | TEXT | yes | — | 0 |
| `generation_key` | TEXT | yes | — | 0 |
| `state_revision` | INTEGER | no | 0 | 0 |
| `database_instance` | TEXT | no | — | 0 |
| `status` | TEXT | no | 'committed' | 0 |
| `export_status` | TEXT | no | 'pending' | 0 |
| `export_attempts` | INTEGER | no | 0 | 0 |
| `occurred_at` | TEXT | no | — | 0 |
| `occurred_at_epoch_ms` | INTEGER | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="device-recovery-history"></a>
## `device_recovery_history`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `recovery_id` | TEXT | yes | — | 1 |
| `device_id` | TEXT | no | — | 0 |
| `action` | TEXT | no | '' | 0 |
| `status` | TEXT | no | 'unknown' | 0 |
| `command_id` | TEXT | yes | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `created_at_epoch_ms` | INTEGER | no | — | 0 |
| `source_ref` | TEXT | no | '' | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="device-removal-receipts"></a>
## `device_removal_receipts`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `receipt_id` | TEXT | yes | — | 1 |
| `device_id` | TEXT | no | — | 0 |
| `device_name` | TEXT | no | '' | 0 |
| `removal_status` | TEXT | no | — | 0 |
| `reason_code` | TEXT | no | 'explicit_operator_removal' | 0 |
| `assessment_revision` | TEXT | no | '' | 0 |
| `awareness_revision` | INTEGER | no | 0 | 0 |
| `requested_by` | TEXT | no | 'authenticated_operator' | 0 |
| `created_at` | TEXT | no | — | 0 |
| `created_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |

<a id="device-supervisor-state"></a>
## `device_supervisor_state`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `device_id` | TEXT | yes | — | 1 |
| `evidence_schema_version` | INTEGER | no | 1 | 0 |
| `supervisor_status` | TEXT | no | 'unknown' | 0 |
| `supervisor_version` | TEXT | no | '' | 0 |
| `supervisor_process_status` | TEXT | no | 'unknown' | 0 |
| `agent_process_status` | TEXT | no | 'unknown' | 0 |
| `nats_reachable` | INTEGER | no | 0 | 0 |
| `repair_status` | TEXT | no | 'not_needed' | 0 |
| `repair_reason_code` | TEXT | no | '' | 0 |
| `repair_count` | INTEGER | no | 0 | 0 |
| `checked_at` | TEXT | yes | — | 0 |
| `checked_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `canonical_hash` | TEXT | no | '' | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | 0 | 0 |

<a id="device-system-profiles"></a>
## `device_system_profiles`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `node_id` | TEXT | yes | — | 1 |
| `profile_schema_version` | INTEGER | no | 1 | 0 |
| `os_family` | TEXT | no | '' | 0 |
| `os_name` | TEXT | no | '' | 0 |
| `os_version` | TEXT | no | '' | 0 |
| `android_api_level` | INTEGER | yes | — | 0 |
| `security_patch` | TEXT | no | '' | 0 |
| `manufacturer` | TEXT | no | '' | 0 |
| `technical_model` | TEXT | no | '' | 0 |
| `device_codename` | TEXT | no | '' | 0 |
| `consumer_model_name` | TEXT | no | '' | 0 |
| `architecture` | TEXT | no | '' | 0 |
| `android_abi` | TEXT | no | '' | 0 |
| `kernel` | TEXT | no | '' | 0 |
| `runtime_type` | TEXT | no | 'unknown' | 0 |
| `termux_version` | TEXT | no | '' | 0 |
| `python_version` | TEXT | no | '' | 0 |
| `agent_version` | TEXT | no | '' | 0 |
| `supervisor_version` | TEXT | no | '' | 0 |
| `profile_fingerprint` | TEXT | no | '' | 0 |
| `profile_status` | TEXT | no | 'unavailable' | 0 |
| `uptime_seconds` | INTEGER | yes | — | 0 |
| `load_average_1m` | REAL | yes | — | 0 |
| `load_average_5m` | REAL | yes | — | 0 |
| `load_average_15m` | REAL | yes | — | 0 |
| `load_status` | TEXT | no | 'unavailable' | 0 |
| `uptime_status` | TEXT | no | 'unavailable' | 0 |
| `profile_collected_at` | TEXT | yes | — | 0 |
| `profile_collected_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `health_collected_at` | TEXT | yes | — | 0 |
| `health_collected_at_epoch_ms` | INTEGER | no | 0 | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `revision` | INTEGER | no | 0 | 0 |
| `architecture_raw` | TEXT | no | '' | 0 |
| `architecture_family` | TEXT | no | '' | 0 |

<a id="domain-revisions"></a>
## `domain_revisions`

Source-derived projections persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `domain` | TEXT | yes | — | 1 |
| `revision` | INTEGER | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |

<a id="enterprise-configuration"></a>
## `enterprise_configuration`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `configuration_id` | INTEGER | yes | — | 1 |
| `enabled` | INTEGER | no | 0 | 0 |
| `authorization_version` | INTEGER | no | 1 | 0 |
| `enabled_at` | TEXT | yes | — | 0 |
| `disabled_at` | TEXT | yes | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_by_human_id` | TEXT | yes | — | 0 |

<a id="enterprise-memberships"></a>
## `enterprise_memberships`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `human_id` | TEXT | yes | — | 1 |
| `role` | TEXT | no | — | 0 |
| `status` | TEXT | no | 'active' | 0 |
| `authorization_version` | INTEGER | no | 1 | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `created_by_human_id` | TEXT | yes | — | 0 |
| `updated_by_human_id` | TEXT | yes | — | 0 |

<a id="human-credentials"></a>
## `human_credentials`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `credential_id` | TEXT | yes | — | 1 |
| `human_id` | TEXT | no | — | 0 |
| `kind` | TEXT | no | — | 0 |
| `verifier` | TEXT | no | — | 0 |
| `salt` | TEXT | no | — | 0 |
| `algorithm` | TEXT | no | — | 0 |
| `parameters_json` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `rotated_at` | TEXT | yes | — | 0 |
| `disabled_at` | TEXT | yes | — | 0 |

<a id="human-identities"></a>
## `human_identities`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `human_id` | TEXT | yes | — | 1 |
| `username_normalized` | TEXT | no | — | 0 |
| `display_name` | TEXT | no | — | 0 |
| `status` | TEXT | no | 'active' | 0 |
| `auth_version` | INTEGER | no | 1 | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `last_authenticated_at` | TEXT | yes | — | 0 |

<a id="identity-audit-events"></a>
## `identity_audit_events`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `event_id` | INTEGER | yes | — | 1 |
| `occurred_at` | TEXT | no | — | 0 |
| `human_id` | TEXT | yes | — | 0 |
| `session_id` | TEXT | yes | — | 0 |
| `event_type` | TEXT | no | — | 0 |
| `reason_code` | TEXT | no | — | 0 |
| `summary` | TEXT | no | — | 0 |
| `correlation_id` | TEXT | no | — | 0 |

<a id="lite-installed-release-identity"></a>
## `lite_installed_release_identity`

Source-derived release persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `owner` | TEXT | yes | — | 1 |
| `schema_version` | INTEGER | no | 1 | 0 |
| `identity_revision` | INTEGER | no | 0 | 0 |
| `product` | TEXT | no | 'pocket-lab-lite' | 0 |
| `install_mode` | TEXT | no | 'unknown' | 0 |
| `source_repository` | TEXT | no | '' | 0 |
| `source_commit` | TEXT | no | '' | 0 |
| `release_tag` | TEXT | no | '' | 0 |
| `artifact_name` | TEXT | no | '' | 0 |
| `artifact_sha256` | TEXT | no | '' | 0 |
| `installed_at` | TEXT | yes | — | 0 |
| `installer_schema` | INTEGER | no | 1 | 0 |
| `verified` | INTEGER | no | 0 | 0 |
| `migration_status` | TEXT | no | '' | 0 |
| `canonical_hash` | TEXT | no | '' | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |

<a id="lite-revision-events"></a>
## `lite_revision_events`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `event_id` | INTEGER | yes | — | 1 |
| `database_instance` | TEXT | no | — | 0 |
| `domain` | TEXT | no | — | 0 |
| `revision` | INTEGER | no | — | 0 |
| `changed_ids_json` | TEXT | no | '[]' | 0 |
| `reason` | TEXT | no | 'domain_state_changed' | 0 |
| `projection_version` | INTEGER | no | 1 | 0 |
| `occurred_at` | TEXT | no | — | 0 |
| `occurred_at_epoch_ms` | INTEGER | no | — | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |

<a id="owner-claims"></a>
## `owner_claims`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `claim_id` | TEXT | yes | — | 1 |
| `claim_hash` | TEXT | no | — | 0 |
| `installation_id` | TEXT | no | — | 0 |
| `rp_id` | TEXT | no | — | 0 |
| `origin` | TEXT | no | — | 0 |
| `webauthn_user_handle` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `expires_at` | TEXT | no | — | 0 |
| `consumed_at` | TEXT | yes | — | 0 |
| `authority_hash` | TEXT | yes | — | 0 |
| `authority_expires_at` | TEXT | yes | — | 0 |
| `completed_at` | TEXT | yes | — | 0 |

<a id="phase3b-current-state"></a>
## `phase3b_current_state`

Source-derived prepared state persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `domain` | TEXT | yes | — | 1 |
| `status` | TEXT | no | 'unknown' | 0 |
| `generation` | INTEGER | no | 0 | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `projection_revision` | INTEGER | no | 0 | 0 |
| `payload_json` | TEXT | no | '{}' | 0 |
| `item_count` | INTEGER | no | 0 | 0 |
| `collector_duration_ms` | REAL | no | 0 | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |
| `canonical_hash` | TEXT | no | '' | 0 |

<a id="phase3b-revision-events"></a>
## `phase3b_revision_events`

Source-derived prepared state persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `event_id` | INTEGER | yes | — | 1 |
| `database_instance` | TEXT | no | — | 0 |
| `domain` | TEXT | no | — | 0 |
| `projection_revision` | INTEGER | no | — | 0 |
| `source_revision` | INTEGER | no | — | 0 |
| `reason` | TEXT | no | 'semantic_state_changed' | 0 |
| `occurred_at` | TEXT | no | — | 0 |
| `occurred_at_epoch_ms` | INTEGER | no | — | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |
| `previous_semantic_hash` | TEXT | no | '' | 0 |
| `new_semantic_hash` | TEXT | no | '' | 0 |
| `changed_paths_json` | TEXT | no | '[]' | 0 |
| `source_revision_before` | INTEGER | no | 0 | 0 |
| `source_revision_after` | INTEGER | no | 0 | 0 |
| `scheduler_generation` | INTEGER | no | 0 | 0 |
| `execution_owner` | TEXT | no | 'unknown' | 0 |

<a id="policy-activation-operations"></a>
## `policy_activation_operations`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `operation_id` | TEXT | yes | — | 1 |
| `requested_by_human_id` | TEXT | no | — | 0 |
| `correlation_id` | TEXT | no | — | 0 |
| `candidate_revision_id` | TEXT | no | — | 0 |
| `prior_known_good_revision_id` | TEXT | yes | — | 0 |
| `state` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `reason_code` | TEXT | no | '' | 0 |
| `observed_filesystem_revision` | TEXT | yes | — | 0 |
| `observed_opa_revision` | TEXT | yes | — | 0 |
| `evidence_ref` | TEXT | yes | — | 0 |

<a id="policy-approvals"></a>
## `policy_approvals`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `approval_id` | TEXT | yes | — | 1 |
| `originating_decision_id` | TEXT | no | — | 0 |
| `correlation_id` | TEXT | no | — | 0 |
| `action_id` | TEXT | no | — | 0 |
| `target_type` | TEXT | no | — | 0 |
| `target_id` | TEXT | no | — | 0 |
| `initiating_human_id` | TEXT | no | — | 0 |
| `initiating_role` | TEXT | no | — | 0 |
| `required_approver_roles_json` | TEXT | no | — | 0 |
| `required_assurance` | TEXT | no | — | 0 |
| `policy_revision` | TEXT | no | — | 0 |
| `status` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `expires_at` | TEXT | no | — | 0 |
| `approved_at` | TEXT | yes | — | 0 |
| `approved_by_human_id` | TEXT | yes | — | 0 |
| `rejected_at` | TEXT | yes | — | 0 |
| `rejected_by_human_id` | TEXT | yes | — | 0 |
| `cancelled_at` | TEXT | yes | — | 0 |
| `cancelled_by_human_id` | TEXT | yes | — | 0 |
| `consumed_at` | TEXT | yes | — | 0 |
| `reason_code` | TEXT | no | '' | 0 |
| `evidence_ref` | TEXT | no | '' | 0 |

<a id="policy-continuation-events"></a>
## `policy_continuation_events`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `event_id` | INTEGER | yes | — | 1 |
| `occurred_at` | TEXT | no | — | 0 |
| `kind` | TEXT | no | — | 0 |
| `subject_id` | TEXT | no | — | 0 |
| `actor_human_id` | TEXT | yes | — | 0 |
| `event_type` | TEXT | no | — | 0 |
| `reason_code` | TEXT | no | — | 0 |
| `summary` | TEXT | no | — | 0 |
| `correlation_id` | TEXT | no | — | 0 |

<a id="policy-decision-details"></a>
## `policy_decision_details`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `decision_id` | TEXT | yes | — | 1 |
| `constraints_json` | TEXT | no | '[]' | 0 |
| `evidence_ref` | TEXT | yes | — | 0 |

<a id="policy-decisions"></a>
## `policy_decisions`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `decision_row_id` | INTEGER | yes | — | 1 |
| `occurred_at` | TEXT | no | — | 0 |
| `decision_id` | TEXT | no | — | 0 |
| `correlation_id` | TEXT | no | — | 0 |
| `actor_type` | TEXT | no | — | 0 |
| `actor_id` | TEXT | no | — | 0 |
| `action_id` | TEXT | no | — | 0 |
| `target_type` | TEXT | no | — | 0 |
| `target_id` | TEXT | no | — | 0 |
| `target_revision` | TEXT | no | — | 0 |
| `allow` | INTEGER | no | — | 0 |
| `reason_code` | TEXT | no | — | 0 |
| `policy_revision` | TEXT | no | — | 0 |
| `evaluation_ms` | REAL | no | 0 | 0 |

<a id="policy-recovery-resolutions"></a>
## `policy_recovery_resolutions`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `resolution_id` | TEXT | yes | — | 1 |
| `operation_id` | TEXT | no | — | 0 |
| `requested_by_human_id` | TEXT | no | — | 0 |
| `requested_at` | TEXT | no | — | 0 |
| `resolved_at` | TEXT | no | — | 0 |
| `original_reason_code` | TEXT | no | — | 0 |
| `recovered_revision_id` | TEXT | no | — | 0 |
| `status` | TEXT | no | — | 0 |
| `evidence_ref` | TEXT | no | — | 0 |
| `summary` | TEXT | no | — | 0 |

<a id="policy-revisions"></a>
## `policy_revisions`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `revision_id` | TEXT | yes | — | 1 |
| `parent_revision_id` | TEXT | yes | — | 0 |
| `template_id` | TEXT | no | — | 0 |
| `template_version` | TEXT | no | — | 0 |
| `canonical_parameters_json` | TEXT | no | — | 0 |
| `manifest_json` | TEXT | no | — | 0 |
| `content_hash` | TEXT | no | — | 0 |
| `created_by_human_id` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `validation_status` | TEXT | no | — | 0 |
| `validated_at` | TEXT | yes | — | 0 |
| `validation_reason_code` | TEXT | no | '' | 0 |
| `lifecycle_status` | TEXT | no | — | 0 |
| `activated_at` | TEXT | yes | — | 0 |
| `change_summary` | TEXT | no | — | 0 |

<a id="policy-runtime-state"></a>
## `policy_runtime_state`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `state_id` | INTEGER | yes | — | 1 |
| `active_revision_id` | TEXT | yes | — | 0 |
| `known_good_revision_id` | TEXT | yes | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_by_operation_id` | TEXT | yes | — | 0 |

<a id="policy-temporary-exceptions"></a>
## `policy_temporary_exceptions`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `exception_id` | TEXT | yes | — | 1 |
| `action_id` | TEXT | no | — | 0 |
| `app_id` | TEXT | no | — | 0 |
| `device_id` | TEXT | no | — | 0 |
| `human_id` | TEXT | no | — | 0 |
| `policy_revision` | TEXT | no | — | 0 |
| `reason` | TEXT | no | — | 0 |
| `created_by_human_id` | TEXT | no | — | 0 |
| `status` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `expires_at` | TEXT | no | — | 0 |
| `revoked_at` | TEXT | yes | — | 0 |
| `revoked_by_human_id` | TEXT | yes | — | 0 |

<a id="projection-dirty-signals"></a>
## `projection_dirty_signals`

Source-derived projections persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `domain` | TEXT | yes | — | 1 |
| `signal_generation` | INTEGER | no | 0 | 0 |
| `claimed_generation` | INTEGER | no | 0 | 0 |
| `trigger_reason` | TEXT | no | 'event' | 0 |
| `requested_by` | TEXT | no | 'unknown' | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |

<a id="projection-refresh-state"></a>
## `projection_refresh_state`

Bounded projection scheduler state

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `domain` | TEXT | yes | — | 1 |
| `generation` | INTEGER | no | 0 | 0 |
| `committed_generation` | INTEGER | no | 0 | 0 |
| `dirty` | INTEGER | no | 0 | 0 |
| `active` | INTEGER | no | 0 | 0 |
| `priority` | INTEGER | no | 50 | 0 |
| `work_class` | TEXT | no | 'io' | 0 |
| `failure_count` | INTEGER | no | 0 | 0 |
| `next_retry_epoch_ms` | INTEGER | no | 0 | 0 |
| `coalesced_count` | INTEGER | no | 0 | 0 |
| `late_result_count` | INTEGER | no | 0 | 0 |
| `stale_generation_count` | INTEGER | no | 0 | 0 |
| `last_started_at` | TEXT | yes | — | 0 |
| `last_completed_at` | TEXT | yes | — | 0 |
| `last_error_type` | TEXT | no | '' | 0 |
| `last_pressure_reason` | TEXT | no | '' | 0 |
| `database_instance` | TEXT | no | '' | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `source_revision` | INTEGER | no | -1 | 0 |
| `last_duration_ms` | REAL | no | 0 | 0 |
| `execution_count` | INTEGER | no | 0 | 0 |
| `committed_count` | INTEGER | no | 0 | 0 |
| `unchanged_count` | INTEGER | no | 0 | 0 |
| `dirty_mark_count` | INTEGER | no | 0 | 0 |
| `followup_requested` | INTEGER | no | 0 | 0 |
| `trigger_reason` | TEXT | no | 'event' | 0 |
| `last_trigger_reason` | TEXT | no | '' | 0 |
| `execution_owner` | TEXT | no | 'unknown' | 0 |
| `executor_build_version` | TEXT | no | 'unavailable' | 0 |
| `executor_process_generation` | TEXT | no | 'unknown' | 0 |

<a id="recovery-code-batches"></a>
## `recovery_code_batches`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `batch_id` | TEXT | yes | — | 1 |
| `human_id` | TEXT | no | — | 0 |
| `generation` | INTEGER | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `invalidated_at` | TEXT | yes | — | 0 |

<a id="recovery-codes"></a>
## `recovery_codes`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `code_id` | TEXT | yes | — | 1 |
| `batch_id` | TEXT | no | — | 0 |
| `code_hash` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `consumed_at` | TEXT | yes | — | 0 |

<a id="recovery-current-state"></a>
## `recovery_current_state`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `singleton_id` | INTEGER | yes | — | 1 |
| `status` | TEXT | no | 'unknown' | 0 |
| `active_operation_id` | TEXT | yes | — | 0 |
| `latest_backup_id` | TEXT | yes | — | 0 |
| `latest_preview_id` | TEXT | yes | — | 0 |
| `latest_restore_id` | TEXT | yes | — | 0 |
| `maintenance_status` | TEXT | no | 'idle' | 0 |
| `source_revision` | INTEGER | no | 0 | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |

<a id="recovery-operations"></a>
## `recovery_operations`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `operation_id` | TEXT | yes | — | 1 |
| `operation_type` | TEXT | no | — | 0 |
| `status` | TEXT | no | — | 0 |
| `backup_id` | TEXT | yes | — | 0 |
| `preview_id` | TEXT | yes | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `source_ref` | TEXT | no | '' | 0 |
| `summary` | TEXT | no | '' | 0 |
| `metadata_json` | TEXT | no | '{}' | 0 |

<a id="release-runtime-projection"></a>
## `release_runtime_projection`

Source-derived release persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `owner` | TEXT | yes | — | 1 |
| `schema_version` | INTEGER | no | 1 | 0 |
| `projection_revision` | INTEGER | no | 0 | 0 |
| `operation_generation` | INTEGER | no | 0 | 0 |
| `active_generation` | INTEGER | no | 0 | 0 |
| `active_operation` | TEXT | no | '' | 0 |
| `active_command_id` | TEXT | no | '' | 0 |
| `lease_expires_epoch_ms` | INTEGER | no | 0 | 0 |
| `worker_generation` | TEXT | no | '' | 0 |
| `phase` | TEXT | no | 'unknown' | 0 |
| `status` | TEXT | no | 'degraded' | 0 |
| `current_tag` | TEXT | no | 'unknown' | 0 |
| `latest_tag` | TEXT | no | 'unknown' | 0 |
| `update_available` | INTEGER | no | 0 | 0 |
| `canonical_hash` | TEXT | no | '' | 0 |
| `payload_json` | TEXT | no | '{}' | 0 |
| `payload_bytes` | INTEGER | no | 2 | 0 |
| `last_checked_at` | TEXT | yes | — | 0 |
| `last_success_at` | TEXT | yes | — | 0 |
| `last_failure_at` | TEXT | yes | — | 0 |
| `last_failure_code` | TEXT | no | '' | 0 |
| `last_terminal_command_id` | TEXT | no | '' | 0 |
| `last_terminal_status` | TEXT | no | '' | 0 |
| `last_terminal_generation` | INTEGER | no | 0 | 0 |
| `checks_started` | INTEGER | no | 0 | 0 |
| `checks_completed` | INTEGER | no | 0 | 0 |
| `applies_started` | INTEGER | no | 0 | 0 |
| `applies_completed` | INTEGER | no | 0 | 0 |
| `unchanged_results` | INTEGER | no | 0 | 0 |
| `writes_skipped` | INTEGER | no | 0 | 0 |
| `writes_committed` | INTEGER | no | 0 | 0 |
| `coalesced_requests` | INTEGER | no | 0 | 0 |
| `deduplicated_requests` | INTEGER | no | 0 | 0 |
| `pressure_deferred` | INTEGER | no | 0 | 0 |
| `deadline_exceeded` | INTEGER | no | 0 | 0 |
| `stale_results_rejected` | INTEGER | no | 0 | 0 |
| `subprocess_restarts` | INTEGER | no | 0 | 0 |
| `subprocess_recycles` | INTEGER | no | 0 | 0 |
| `last_subprocess_pid` | INTEGER | no | 0 | 0 |
| `last_subprocess_exit_code` | INTEGER | yes | — | 0 |
| `last_cpu_ms` | REAL | no | 0 | 0 |
| `last_wall_ms` | REAL | no | 0 | 0 |
| `last_peak_rss_bytes` | INTEGER | no | 0 | 0 |
| `last_bytes_read` | INTEGER | no | 0 | 0 |
| `last_files_examined` | INTEGER | no | 0 | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `configured_repository` | TEXT | no | '' | 0 |
| `verified_repository` | TEXT | no | '' | 0 |
| `repository_match` | INTEGER | no | 0 | 0 |
| `install_mode` | TEXT | no | 'unknown' | 0 |
| `installed_release_tag` | TEXT | no | '' | 0 |
| `installed_source_commit` | TEXT | no | '' | 0 |
| `comparison` | TEXT | no | 'unknown_installed_identity' | 0 |
| `manifest_verified` | INTEGER | no | 0 | 0 |
| `artifact_verified` | INTEGER | no | 0 | 0 |
| `staging_status` | TEXT | no | 'idle' | 0 |
| `promotion_status` | TEXT | no | 'idle' | 0 |
| `rollback_available` | INTEGER | no | 0 | 0 |
| `last_failure_stage` | TEXT | no | '' | 0 |
| `last_rollback_status` | TEXT | no | '' | 0 |
| `next_check_epoch_ms` | INTEGER | no | 0 | 0 |
| `stable_interval_seconds` | INTEGER | no | 43200 | 0 |

<a id="schema-migrations"></a>
## `schema_migrations`

Source-derived database persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `version` | INTEGER | yes | — | 1 |
| `name` | TEXT | no | — | 0 |
| `applied_at` | TEXT | no | — | 0 |
| `checksum` | TEXT | no | — | 0 |

<a id="security-database-backups"></a>
## `security_database_backups`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `backup_id` | TEXT | yes | — | 1 |
| `status` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `verified_at` | TEXT | yes | — | 0 |
| `file_name` | TEXT | no | — | 0 |
| `size_bytes` | INTEGER | no | 0 | 0 |
| `sha256` | TEXT | no | '' | 0 |
| `schema_version` | INTEGER | no | 0 | 0 |
| `sqlite_version` | TEXT | no | '' | 0 |
| `manifest_json` | TEXT | no | '{}' | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |

<a id="security-database-restores"></a>
## `security_database_restores`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `restore_id` | TEXT | yes | — | 1 |
| `backup_id` | TEXT | no | — | 0 |
| `preview_id` | TEXT | no | — | 0 |
| `state` | TEXT | no | — | 0 |
| `requested_at` | TEXT | no | — | 0 |
| `completed_at` | TEXT | yes | — | 0 |
| `rollback_file_name` | TEXT | yes | — | 0 |
| `summary` | TEXT | no | '' | 0 |
| `metadata_json` | TEXT | no | '{}' | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |

<a id="security-maintenance-runs"></a>
## `security_maintenance_runs`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `maintenance_id` | TEXT | yes | — | 1 |
| `kind` | TEXT | no | — | 0 |
| `mode` | TEXT | no | 'apply' | 0 |
| `status` | TEXT | no | — | 0 |
| `requested_at` | TEXT | no | — | 0 |
| `completed_at` | TEXT | yes | — | 0 |
| `summary` | TEXT | no | '' | 0 |
| `metadata_json` | TEXT | yes | — | 0 |
| `sanitized` | INTEGER | no | 1 | 0 |

<a id="security-profile-snapshots"></a>
## `security_profile_snapshots`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `profile` | TEXT | no | — | 1 |
| `app_id` | TEXT | no | '' | 2 |
| `latest_run_id` | TEXT | no | — | 0 |
| `latest_status` | TEXT | no | — | 0 |
| `latest_score` | INTEGER | yes | — | 0 |
| `latest_summary` | TEXT | no | '' | 0 |
| `latest_completed_at` | TEXT | yes | — | 0 |
| `latest_evidence_at` | TEXT | yes | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `revision` | INTEGER | no | 1 | 0 |

<a id="security-scan-evidence-refs"></a>
## `security_scan_evidence_refs`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `evidence_ref_id` | INTEGER | yes | — | 1 |
| `run_id` | TEXT | no | — | 0 |
| `kind` | TEXT | no | — | 0 |
| `relative_path` | TEXT | no | — | 0 |
| `sha256` | TEXT | yes | — | 0 |
| `size_bytes` | INTEGER | yes | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `metadata_json` | TEXT | yes | — | 0 |

<a id="security-scan-findings"></a>
## `security_scan_findings`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `finding_row_id` | INTEGER | yes | — | 1 |
| `run_id` | TEXT | no | — | 0 |
| `finding_key` | TEXT | no | — | 0 |
| `fingerprint` | TEXT | no | — | 0 |
| `source` | TEXT | no | — | 0 |
| `severity` | TEXT | no | — | 0 |
| `title` | TEXT | no | — | 0 |
| `summary` | TEXT | no | '' | 0 |
| `component` | TEXT | no | '' | 0 |
| `status` | TEXT | no | 'present' | 0 |
| `first_seen_at` | TEXT | yes | — | 0 |
| `last_seen_at` | TEXT | yes | — | 0 |
| `resolved_at` | TEXT | yes | — | 0 |
| `remediation_json` | TEXT | yes | — | 0 |
| `technical_json` | TEXT | yes | — | 0 |

<a id="security-scan-progress-events"></a>
## `security_scan_progress_events`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `event_id` | INTEGER | yes | — | 1 |
| `run_id` | TEXT | no | — | 0 |
| `sequence_no` | INTEGER | no | — | 0 |
| `status` | TEXT | no | — | 0 |
| `stage` | TEXT | yes | — | 0 |
| `percent` | INTEGER | yes | — | 0 |
| `message` | TEXT | yes | — | 0 |
| `tool` | TEXT | yes | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `created_at_epoch_ms` | INTEGER | no | — | 0 |
| `payload_json` | TEXT | yes | — | 0 |
| `fingerprint` | TEXT | no | — | 0 |

<a id="security-scan-runs"></a>
## `security_scan_runs`

Canonical Security scan lifecycle

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `run_id` | TEXT | yes | — | 1 |
| `profile` | TEXT | no | — | 0 |
| `app_id` | TEXT | no | '' | 0 |
| `app_label` | TEXT | no | '' | 0 |
| `status` | TEXT | no | — | 0 |
| `active_key` | TEXT | yes | — | 0 |
| `summary` | TEXT | no | '' | 0 |
| `score` | INTEGER | yes | — | 0 |
| `partial_results` | INTEGER | no | 0 | 0 |
| `requested_at` | TEXT | no | — | 0 |
| `accepted_at` | TEXT | yes | — | 0 |
| `started_at` | TEXT | yes | — | 0 |
| `completed_at` | TEXT | yes | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `requested_at_epoch_ms` | INTEGER | no | — | 0 |
| `started_at_epoch_ms` | INTEGER | yes | — | 0 |
| `completed_at_epoch_ms` | INTEGER | yes | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `current_stage` | TEXT | yes | — | 0 |
| `current_percent` | INTEGER | yes | — | 0 |
| `current_message` | TEXT | yes | — | 0 |
| `current_tool` | TEXT | yes | — | 0 |
| `checks_reviewed` | INTEGER | no | 0 | 0 |
| `items_to_review` | INTEGER | no | 0 | 0 |
| `critical_count` | INTEGER | no | 0 | 0 |
| `high_count` | INTEGER | no | 0 | 0 |
| `medium_count` | INTEGER | no | 0 | 0 |
| `low_count` | INTEGER | no | 0 | 0 |
| `info_count` | INTEGER | no | 0 | 0 |
| `timeout_reason` | TEXT | yes | — | 0 |
| `failure_code` | TEXT | yes | — | 0 |
| `failure_message` | TEXT | yes | — | 0 |
| `command_id` | TEXT | yes | — | 0 |
| `correlation_id` | TEXT | yes | — | 0 |
| `source` | TEXT | no | 'security-worker' | 0 |
| `revision` | INTEGER | no | 1 | 0 |
| `evidence_saved` | INTEGER | no | 0 | 0 |
| `metadata_json` | TEXT | yes | — | 0 |
| `command_published_at` | TEXT | yes | — | 0 |
| `command_published_at_epoch_ms` | INTEGER | yes | — | 0 |
| `command_received_at` | TEXT | yes | — | 0 |
| `command_received_at_epoch_ms` | INTEGER | yes | — | 0 |
| `execution_started_at` | TEXT | yes | — | 0 |
| `execution_started_at_epoch_ms` | INTEGER | yes | — | 0 |
| `last_progress_at` | TEXT | yes | — | 0 |
| `last_progress_at_epoch_ms` | INTEGER | yes | — | 0 |
| `delivery_attempt` | INTEGER | no | 0 | 0 |

<a id="security-scan-tool-runs"></a>
## `security_scan_tool_runs`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `tool_run_id` | INTEGER | yes | — | 1 |
| `run_id` | TEXT | no | — | 0 |
| `tool_name` | TEXT | no | — | 0 |
| `status` | TEXT | no | — | 0 |
| `started_at` | TEXT | yes | — | 0 |
| `completed_at` | TEXT | yes | — | 0 |
| `duration_ms` | INTEGER | yes | — | 0 |
| `finding_count` | INTEGER | no | 0 | 0 |
| `timed_out` | INTEGER | no | 0 | 0 |
| `timeout_reason` | TEXT | yes | — | 0 |
| `metadata_json` | TEXT | yes | — | 0 |

<a id="security-store-metadata"></a>
## `security_store_metadata`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `metadata_key` | TEXT | yes | — | 1 |
| `value_json` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |

<a id="webauthn-challenges"></a>
## `webauthn_challenges`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `challenge_id` | TEXT | yes | — | 1 |
| `challenge_hash` | TEXT | no | — | 0 |
| `purpose` | TEXT | no | — | 0 |
| `human_id` | TEXT | yes | — | 0 |
| `session_id` | TEXT | yes | — | 0 |
| `owner_claim_id` | TEXT | yes | — | 0 |
| `rp_id` | TEXT | no | — | 0 |
| `origin` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `expires_at` | TEXT | no | — | 0 |
| `consumed_at` | TEXT | yes | — | 0 |

<a id="webauthn-credentials"></a>
## `webauthn_credentials`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `credential_id` | TEXT | yes | — | 1 |
| `human_id` | TEXT | no | — | 0 |
| `friendly_name` | TEXT | no | — | 0 |
| `public_key_x` | TEXT | no | — | 0 |
| `public_key_y` | TEXT | no | — | 0 |
| `algorithm` | INTEGER | no | — | 0 |
| `sign_count` | INTEGER | no | 0 | 0 |
| `transports_json` | TEXT | no | '[]' | 0 |
| `authenticator_attachment` | TEXT | yes | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `last_used_at` | TEXT | yes | — | 0 |
| `revoked_at` | TEXT | yes | — | 0 |

<a id="webauthn-users"></a>
## `webauthn_users`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `human_id` | TEXT | yes | — | 1 |
| `user_handle` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |

<a id="workflow-command-state"></a>
## `workflow_command_state`

Source-derived workflow persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `command_id` | TEXT | yes | — | 1 |
| `workflow_id` | TEXT | no | — | 0 |
| `subject` | TEXT | no | '' | 0 |
| `event_type` | TEXT | no | '' | 0 |
| `command_json` | TEXT | no | — | 0 |
| `created_at` | TEXT | no | — | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `process_generation` | INTEGER | no | 0 | 0 |
| `database_instance` | TEXT | no | '' | 0 |

<a id="workflow-current-state"></a>
## `workflow_current_state`

Source-derived workflow persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `workflow_id` | TEXT | yes | — | 1 |
| `projection_json` | TEXT | no | — | 0 |
| `canonical_hash` | TEXT | no | — | 0 |
| `status` | TEXT | no | 'unknown' | 0 |
| `terminal` | INTEGER | no | 0 | 0 |
| `revision` | INTEGER | no | 1 | 0 |
| `semantic_event_count` | INTEGER | no | 0 | 0 |
| `updated_at` | TEXT | no | — | 0 |
| `updated_at_epoch_ms` | INTEGER | no | — | 0 |
| `process_generation` | INTEGER | no | 0 | 0 |
| `database_instance` | TEXT | no | '' | 0 |

<a id="workflow-event-index"></a>
## `workflow_event_index`

Source-derived workflow persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Column | Type | Nullable | Default | Primary key |
| --- | --- | --- | --- | --- |
| `event_id` | TEXT | yes | — | 1 |
| `workflow_id` | TEXT | no | — | 0 |
| `event_type` | TEXT | no | '' | 0 |
| `subject` | TEXT | no | '' | 0 |
| `event_json` | TEXT | no | — | 0 |
| `observed_at` | TEXT | no | — | 0 |
| `observed_at_epoch_ms` | INTEGER | no | — | 0 |
| `process_generation` | INTEGER | no | 0 | 0 |
| `database_instance` | TEXT | no | '' | 0 |
