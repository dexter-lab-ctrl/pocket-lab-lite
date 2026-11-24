# P5–P12 infrastructure operations implementation ledger

Base: `bb98e6c04c657154ce19675d9d96dc693995ac22` (PR #657). Implementation only; no qualification or production activation authorized. This ledger begins with source inspection; subsequent commits must reconcile each entry with actual implementation.

## Source reuse and initial boundaries

| Phase | Verified source / existing owner | Initial gap and intended treatment |
|---|---|---|
| P5 | `services/lite_system_health.py`: REPAIR_CATALOG, controlled_recovery_enabled, repair_preflight, admit_controlled_recovery, process_controlled_recovery_requests; migrations 0043–0047; `routers/lite_system_health.py`: OPA/approval integration | Extend catalog, separate qualification and production authority; production remains blocked until exact operation is qualified and explicitly authorized. No competing executor. Existing owner evidence is not automatically a verified repair. |
| P6 | `lite_phase3b_projections.py`: collect_process_state, collect_nats_remote_state, collect_agent_state, collect_supervisor_state, collect_remote_access_state; `lite_device_recovery.py`: guarded_recovery_contract | Prepared views and guided existing workflows; no arbitrary PM2 or Tailnet operations. |
| P7 | `lite_phase3c_projections.py`: collect_storage_pressure, collect_sqlite_health; `lite_storage_guard.py`: storage_readiness; `lite_security_maintenance.py`: run_retention, run_wal_checkpoint, maintenance_state | Prepared state and guarded operator guidance. No arbitrary paths, deletion, VACUUM or restore. Requestable adapters require separately established admission/verification. |
| P8 | `lite_control_plane_store.py`: ControlPlaneProjectionStore; `lite_phase3c_projections.py`: collect_activity_current/history | Reuse durable command evidence; no blind replay, no fabricated cancellation. |
| P9 | `lite_phase3c_projections.py`: collect_telemetry_thresholds; `lite_device_resource_health.py`: assess_resource_observations; projection_scheduler.py | Resource decisions require reliable observations, bounded scheduling and approved policy. No essential-service interruption. |
| P10 | `lite_system_health.py`: configuration_drift; `lite_policy_lifecycle.py`: consistency_projection, request_activation, request_rollback; `lite_database_recovery.py`: create_database_backup, verify_database_backup, create_database_restore_preview | Guided existing Recovery/Rules/Safety flows; no unauthorized configuration replacement or database restoration. |
| P11 | `lite_system_health.py`: dependency_graph, knowledge, history | Bounded evidence correlation and recurrence; no inferred root cause presented as verified. Export requires explicit safe scope and authorization. |
| P12 | Existing worker watchdog, core supervisor, runtime guardian and node supervisor | Existing execution remains authoritative; new candidates fail closed without qualification, policy actor, durable admission and verification. |

Backend paths above are relative to `pocket-lab-final-structure/runtime/api_fastapi/` unless otherwise stated. Source inspection is not qualification.

## Frontend baseline

`src/lite/LiteSystemHealth.jsx` already reuses GlassCard, LiteButton, LiteActionRow, PageHeader and StateSurface (LiteUi.jsx), LiteDetailsPanel (LiteOverlay.jsx), useDesktopManageGeometry, useLitePanelSectionNavigation and HomeGroupedSections. Preserve the four areas, haptic props, existing geometry and theme-independent spacing. References: #606, #622, #623, #636, #640, #648, #649, #656, #657. Performance contract #588/#589; PM2 ownership #653; command state #654; OPA #655.

## Qualification

All new qualification is ADDED — NOT RUN or EXTENDED — NOT RUN. Canonical generated outputs must be regenerated in a later session; no generated evidence is edited here.
