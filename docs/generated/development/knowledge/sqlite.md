---
title: "SQLite knowledgebase"
description: "Semantic SQLite metadata linked to SchemaSpy and API consumers."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# SQLite knowledgebase

SchemaSpy remains the structural authority; this page adds semantic ownership.

## `app_action_lifecycle`

Source-derived apps persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | apps |
| Owner | not a prepared projection |
| Writer | App Catalog lifecycle and action services |
| Readers | /api/lite/catalog, /api/lite/apps/{app_id}/actions |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_phase3c_app_actions_status_latest, idx_app_actions_active, idx_app_actions_history, sqlite_autoindex_app_action_lifecycle_1 |
| Confidence | inferred |

## `app_current_state`

Source-derived apps persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | apps |
| Owner | apps |
| Writer | App Catalog lifecycle and action services |
| Readers | /api/lite/catalog, /api/lite/apps/{app_id}/actions |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_app_current_updated, idx_app_current_order, sqlite_autoindex_app_current_state_1 |
| Confidence | inferred |

## `audit_evidence_index`

Source-derived audit persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | audit |
| Owner | audit |
| Writer | audit evidence indexing services |
| Readers | — |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_phase3c_audit_latest, idx_audit_operation_created, idx_audit_entity_created, sqlite_autoindex_audit_evidence_index_1 |
| Confidence | inferred |

## `backup_manifest_index`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | recovery |
| Owner | recovery |
| Writer | Recovery services and worker completion handlers |
| Readers | /api/lite/recovery, /api/lite/recovery/details |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_backup_manifest_created, sqlite_autoindex_backup_manifest_index_1 |
| Confidence | inferred |

## `command_lifecycle`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | control_plane |
| Owner | not a prepared projection |
| Writer | source-defined control-plane service |
| Readers | — |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_commands_nonterminal_age, idx_commands_attention_latest, idx_commands_lifecycle_stage, idx_commands_entity_history, idx_commands_status_updated, idx_commands_entity_active_latest, idx_commands_entity_active, sqlite_autoindex_command_lifecycle_1 |
| Confidence | inferred |

## `device_awareness_state`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | devices |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_device_awareness_identity, idx_device_awareness_removal, idx_device_awareness_staleness, sqlite_autoindex_device_awareness_state_1 |
| Confidence | inferred |

## `device_current_state`

Durable current enrolled-device projection

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | fleet |
| Writer | fleet/device projection writer |
| Readers | GET /api/lite/fleet |
| Retention | until explicit retirement |
| Classification | restricted operational metadata |
| Indexes | idx_device_current_stale_order, idx_device_current_stale, idx_device_current_fleet_order, sqlite_autoindex_device_current_state_1 |
| Confidence | source-derived |

## `device_enrollment_registry`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_device_enrollment_last_seen, idx_device_enrollment_name, idx_device_enrollment_active_order, sqlite_autoindex_device_enrollment_registry_1 |
| Confidence | inferred |

## `device_health_attention`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_device_health_attention_active_time, idx_device_health_attention_device_status, idx_device_health_attention_active_reason, sqlite_autoindex_device_health_attention_1 |
| Confidence | inferred |

## `device_health_current`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | devices |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_device_health_attention, idx_device_health_status, sqlite_autoindex_device_health_current_1 |
| Confidence | inferred |

## `device_health_transitions`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_device_health_transitions_device_time, sqlite_autoindex_device_health_transitions_1 |
| Confidence | inferred |

## `device_heartbeats`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_device_heartbeats_stale, idx_device_heartbeats_latest, sqlite_autoindex_device_heartbeats_1 |
| Confidence | inferred |

## `device_identity_guards`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | sqlite_autoindex_device_identity_guards_1 |
| Confidence | inferred |

## `device_invite_lifecycle`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_device_invites_status, idx_device_invites_active_latest, idx_device_invites_identity, sqlite_autoindex_device_invite_lifecycle_1 |
| Confidence | inferred |

## `device_lifecycle_events`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_device_lifecycle_generation, idx_device_lifecycle_events_dedupe, idx_device_lifecycle_type_time, idx_device_lifecycle_device_time, sqlite_autoindex_device_lifecycle_events_1 |
| Confidence | inferred |

## `device_lifecycle_transactions`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_device_lifecycle_transactions_export, idx_device_lifecycle_transactions_device, sqlite_autoindex_device_lifecycle_transactions_3, sqlite_autoindex_device_lifecycle_transactions_2, sqlite_autoindex_device_lifecycle_transactions_1 |
| Confidence | inferred |

## `device_recovery_history`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_device_recovery_history, sqlite_autoindex_device_recovery_history_1 |
| Confidence | inferred |

## `device_removal_receipts`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_device_removal_receipts_device_time, sqlite_autoindex_device_removal_receipts_1 |
| Confidence | inferred |

## `device_supervisor_state`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | devices |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_device_supervisor_freshness, sqlite_autoindex_device_supervisor_state_1 |
| Confidence | inferred |

## `device_system_profiles`

Source-derived devices persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | devices |
| Owner | not a prepared projection |
| Writer | device lifecycle and projection services |
| Readers | /api/lite/fleet, /api/lite/devices/{device_id} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_device_system_profiles_updated, sqlite_autoindex_device_system_profiles_1 |
| Confidence | inferred |

## `domain_revisions`

Source-derived projections persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | projections |
| Owner | projections |
| Writer | prepared projection scheduler |
| Readers | /api/lite/diagnostics/runtime, /api/lite/revisions |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | sqlite_autoindex_domain_revisions_1 |
| Confidence | inferred |

## `lite_installed_release_identity`

Source-derived release persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | release |
| Owner | not a prepared projection |
| Writer | release runtime and identity services |
| Readers | /api/lite/release |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_lite_installed_release_identity_mode, sqlite_autoindex_lite_installed_release_identity_1 |
| Confidence | inferred |

## `lite_revision_events`

Source-derived control plane persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | control_plane |
| Owner | control_plane |
| Writer | source-defined control-plane service |
| Readers | — |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_lite_revision_events_retention, idx_lite_revision_events_replay, idx_lite_revision_events_domain_revision |
| Confidence | inferred |

## `phase3b_current_state`

Source-derived prepared state persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | prepared_state |
| Owner | prepared_state |
| Writer | prepared state projection services |
| Readers | /api/lite/status |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_phase3b_current_state_revision, idx_phase3b_current_state_status, sqlite_autoindex_phase3b_current_state_1 |
| Confidence | inferred |

## `phase3b_revision_events`

Source-derived prepared state persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | prepared_state |
| Owner | prepared_state |
| Writer | prepared state projection services |
| Readers | /api/lite/status |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_phase3b_revision_events_domain_recent, idx_phase3b_revision_events_retention, idx_phase3b_revision_events_replay, sqlite_autoindex_phase3b_revision_events_1 |
| Confidence | inferred |

## `projection_dirty_signals`

Source-derived projections persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | projections |
| Owner | projections |
| Writer | prepared projection scheduler |
| Readers | /api/lite/diagnostics/runtime, /api/lite/revisions |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_projection_dirty_signals_pending, sqlite_autoindex_projection_dirty_signals_1 |
| Confidence | inferred |

## `projection_refresh_state`

Bounded projection scheduler state

| Field | Value |
| --- | --- |
| Domain | projections |
| Owner | projection scheduler |
| Writer | projection scheduler |
| Readers | diagnostics endpoints |
| Retention | current state |
| Classification | internal metadata |
| Indexes | idx_projection_refresh_ready, sqlite_autoindex_projection_refresh_state_1 |
| Confidence | source-derived |

## `recovery_current_state`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | recovery |
| Owner | recovery |
| Writer | Recovery services and worker completion handlers |
| Readers | /api/lite/recovery, /api/lite/recovery/details |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | — |
| Confidence | inferred |

## `recovery_operations`

Source-derived recovery persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | recovery |
| Owner | not a prepared projection |
| Writer | Recovery services and worker completion handlers |
| Readers | /api/lite/recovery, /api/lite/recovery/details |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_phase3c_recovery_status_latest, idx_recovery_operations_updated, idx_recovery_operations_history, sqlite_autoindex_recovery_operations_1 |
| Confidence | inferred |

## `release_runtime_projection`

Source-derived release persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | release |
| Owner | release |
| Writer | release runtime and identity services |
| Readers | /api/lite/release |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_release_runtime_active_lease, idx_release_runtime_status_updated, sqlite_autoindex_release_runtime_projection_1 |
| Confidence | inferred |

## `schema_migrations`

Source-derived database persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | database |
| Owner | not a prepared projection |
| Writer | SQLite migration runner |
| Readers | — |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | — |
| Confidence | inferred |

## `security_database_backups`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_security_database_backups_created, sqlite_autoindex_security_database_backups_1 |
| Confidence | inferred |

## `security_database_restores`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_security_database_restores_requested, sqlite_autoindex_security_database_restores_1 |
| Confidence | inferred |

## `security_maintenance_runs`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_phase3c_maintenance_status_latest, idx_security_maintenance_kind_requested, sqlite_autoindex_security_maintenance_runs_1 |
| Confidence | inferred |

## `security_profile_snapshots`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | security |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | sqlite_autoindex_security_profile_snapshots_1 |
| Confidence | inferred |

## `security_scan_evidence_refs`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_security_evidence_run_kind, sqlite_autoindex_security_scan_evidence_refs_1 |
| Confidence | inferred |

## `security_scan_findings`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_security_findings_fingerprint, idx_security_findings_run_severity, sqlite_autoindex_security_scan_findings_1 |
| Confidence | inferred |

## `security_scan_progress_events`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_security_progress_created, idx_security_progress_run_event, sqlite_autoindex_security_scan_progress_events_2, sqlite_autoindex_security_scan_progress_events_1 |
| Confidence | inferred |

## `security_scan_runs`

Canonical Security scan lifecycle

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | security |
| Writer | Security API/worker store |
| Readers | Security summary/profile/progress endpoints |
| Retention | bounded by Security retention policy |
| Classification | sanitized operational metadata |
| Indexes | idx_security_runs_app_updated_latest, idx_security_runs_profile_updated_latest, idx_security_runs_profile_history_cursor, idx_security_runs_history_cursor, idx_security_runs_progress_latest, idx_security_runs_delivery_state, idx_security_runs_status_updated, idx_security_runs_profile_completed, sqlite_autoindex_security_scan_runs_2, sqlite_autoindex_security_scan_runs_1 |
| Confidence | source-derived |

## `security_scan_tool_runs`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_security_tool_runs_run, sqlite_autoindex_security_scan_tool_runs_1 |
| Confidence | inferred |

## `security_store_metadata`

Source-derived security persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | security |
| Owner | not a prepared projection |
| Writer | Security store and scanner completion services |
| Readers | /api/lite/security/summary, /api/lite/security/profiles/{profile} |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | sqlite_autoindex_security_store_metadata_1 |
| Confidence | inferred |

## `workflow_command_state`

Source-derived workflow persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | workflow |
| Owner | workflow |
| Writer | workflow projection services |
| Readers | — |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_workflow_command_workflow, sqlite_autoindex_workflow_command_state_1 |
| Confidence | inferred |

## `workflow_current_state`

Source-derived workflow persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | workflow |
| Owner | workflow |
| Writer | workflow projection services |
| Readers | — |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | restricted operational metadata |
| Indexes | idx_workflow_current_terminal_updated, idx_workflow_current_status_updated, sqlite_autoindex_workflow_current_state_1 |
| Confidence | inferred |

## `workflow_event_index`

Source-derived workflow persistence object; detailed ownership is conservatively inferred from its migration-defined name.

| Field | Value |
| --- | --- |
| Domain | workflow |
| Owner | workflow |
| Writer | workflow projection services |
| Readers | — |
| Retention | domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance |
| Classification | internal operational metadata |
| Indexes | idx_workflow_event_workflow_time, sqlite_autoindex_workflow_event_index_1 |
| Confidence | inferred |
