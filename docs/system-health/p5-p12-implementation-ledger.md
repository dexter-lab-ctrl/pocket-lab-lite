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


## Source implementation disposition

**PARTIAL — SOURCE AUTHORED — QUALIFICATION NOT RUN.** This is not the completed end-to-end P5–P12 platform. Production activation, newly executable owner adapters, cleanup and resource controls are not delivered by this increment.

| Phase | Source delivered | Outstanding |
|---|---|---|
| P5 | Typed descriptive registry; isolated P4 reconnect gate; emergency disable; exact target and freshness checks; shared single-flight and cooldown; bounded abandoned-request reconciliation; operator review and confirmation; existing consumer watchdog recovery evidence and later-fetch verification | Durable production activation and preferences, execution-time actor/policy revalidation, approval expiry and revocation qualification, additional guardian evidence adapters |
| P6 | Prepared core service/process/readiness, remote connectivity fields and guided existing controls | New guarded service operation adapters, end-to-end local network/TLS and guardian readiness coverage; no arbitrary process restart |
| P7 | Storage and SQLite observations, explicit unknown capacity, protected cleanup classes and Recovery guidance | Measured capacity attribution, bounded owner manifests, cleanup preview/execution, WAL/maintenance admission and verification |
| P8 | Prepared workflow counts and controlled recovery expiry/uncertainty handling | Generic operation details, owner-bound cancellation/retry, durable delivery reconciliation beyond existing P4 |
| P9 | Prepared resource signals and explicit unsupported/unknown policy states | Durable resource preferences, hysteresis/deferral/resumption, charging/battery telemetry and qualification |
| P10 | Security and backup readiness projection fields, existing drift view, guided Rules/Safety/Recovery controls | Approved configuration comparison, policy integrity, certificate/time/scanner freshness, backup rehearsal compatibility and executable reconciliation adapters |
| P11 | Current-only inferred dependency correlation and bounded governed request verification rate | Coverage-aware uptime, comparable timing/MTTR, recurrence UX expansion, scoped audited diagnostic export |
| P12 | Existing watchdog evidence; descriptive candidate catalog with new automatic admission always false | Selective new automatic adapters, graduated activation, resource and maintenance conflict proof, safe cleanup automation |

Registry entries for unsupported operations describe proposed owner boundaries, not independently proven execution contracts. Existing guarded flows remain authoritative. No OPA rule, supervisor executor, arbitrary shell or browser command dispatch was added. Existing production watchdog behavior remains unchanged apart from evidence capture and bounded reconciliation. Production System Health assisted/automatic admission is still blocked; an environment switch alone is not qualification.

## Source files and data contracts

- Backend: services/lite_infrastructure_operations.py, services/lite_infrastructure_read_model.py, services/lite_infrastructure_owner_evidence.py, services/lite_system_health.py, routers/lite_system_health.py.
- Execution owner: runtime/workers/pocketlab_worker.py; existing durable consumer watchdog, no new recovery engine.
- SQLite: db/schema/0048_system_health_owner_recovery_evidence.sql, additive evidence table. Migration and legacy schema compatibility not executed.
- API: authenticated GET /api/lite/system-health/infrastructure, additions to existing summary, history, policy and intelligence reads. Only existing prepared fields; no live collector on read. New response is not added to offline persistent cache allowlist.
- UI: src/lite/LiteSystemHealth.jsx and src/lib/liteApi.js. Four existing Manage groups retained, seven focused on-demand detail views; reuse existing theme spacing, haptic LiteButton and LiteActionRow, StateSurface and shared panel navigation. No new CSS/theme tokens or independent overlay. Confirmation is local UI state only.
- Coverage: tests/backend/test_lite_system_health.py, src/lite/LiteSystemHealth.test.jsx, tests/e2e/lite-system-health.spec.ts, src/mocks/handlers.js, src/lite/LiteSystemHealth.stories.jsx. Tests and stories authored or extended; none executed. Additional per-operation cases, visual baselines, stress, authorization and performance matrices remain to be authored.

## Deferred qualification commands

Run only in a subsequent authorized DEV-PC qualification session after checking exact candidate SHA and reviewing source gaps:

```bash
.venv/bin/python -m pytest -q tests/backend/test_lite_system_health.py
npm run test:unit -- src/lite/LiteSystemHealth.test.jsx
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
npm run build-storybook
npm run test:a11y:states
npm run test:visual:states
npm run test:visual:overlays
npm run test:perf:mocked
npm run build:budget
task lite:check
task lite:docs:generate
task lite:docs:check
```

Do not blindly accept generated visual differences. Review light/dark and 360px/390px geometry, text scaling, keyboard navigation, focus return, saved/offline behavior, confirmation cancellation, no duplicate admission and redaction. Isolate migration 0048 with backup/restore on a disposable DB, then test concurrency, worker restart, expiry, stale policy/actor and verification windows. Measure idle overhead and SQLite read/write cost on exact candidate; compare against main. Only separately authorized physical qualification can use the existing task lite:system-health:candidate:android:qualify with its documented exact-SHA, standard-user Windows/Termux, non-production safeguards. No physical run performed.

## Qualification verdict

All execution and qualification: NOT RUN. No CI inspected or remediated. Canonical documentation/contract generation and repository gate checks: NOT RUN. No production configuration, phone, release, tag or main changes. Review the source risks and implement the outstanding scope before requesting production activation or merge.
