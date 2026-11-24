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


## Continuation of PR #658 — source-only implementation

This section supersedes the earlier partial disposition where applicable. The earlier implementation is retained as provenance. **SOURCE AUTHORED — NOT QUALIFIED.** No production operation is promoted and the source-qualified production allowlist remains empty. The entire P5–P12 scope is still partial.

| Phase | Additional source delivered | Residual implementation |
|---|---|---|
| P5 | Revisioned Owner preferences; durable actor/session/role binding; execution-time session, approval, policy and capability revalidation; confirmation and expiry guards; isolated qualification identity distinct from human Owner | Broader operation authorization coverage, approval UI continuation, durable production automatic policy |
| P6 | Existing supervisor restart evidence correlated with later same-process stable reconciler readiness; runtime desired-state and restart-budget signals | New directly admitted service-specific repair contracts, additional remote/guardian evidence and end-to-end local/TLS readiness |
| P7 | Measured filesystem and WAL capacity, managed log policy observations; fixed NATS maintenance preview/apply and passive checkpoint adapters with fresh evidence, Owner, policy, exact candidate, expiry, and single-flight guards | Physical reclaimable-byte attribution; protected log/temp/cache/raw-evidence cleanup contracts; uncertain maintenance resolution and additional maintenance window operations |
| P8 | Owner cancellation before first execution; persisted request attempts; maintenance delivery/expiry reconciliation and no replay of uncertain outcomes | Generic workflow-specific cancellation/retry and reconciliation across app, backup, agent and other command owners |
| P9 | Durable balanced/low-power/maintenance preferences; gated existing adaptive scheduler extension for stable history reconciliation only; return to balanced shortens next eligible history interval | Battery/charging collection, broader resource admission and hysteresis, verified effective policy projection |
| P10 | Runtime desired-state comparison fields, managed log constraints, durable active/known-good policy pointer agreement distinct from loaded integrity | Certificate/time/scanner freshness, approved configuration restoration, verified backup rehearsal compatibility and owner reconciliation adapters |
| P11 | Scoped Owner-confirmed audited no-store diagnostic export; verified request elapsed-time statistic distinct from incident MTTR; separate automatic supervisor evidence | Coverage-aware uptime, incident MTTR and broader recurrence presentation |
| P12 | Layered assisted activation gate with empty production qualification allowlist; new qualification-only maintenance/resource candidates; existing guardians unchanged as execution owners | New selective automatic admission/activation rules and full cross-owner resource/maintenance conflict contract |

### New source boundaries

- Additive schemas 0049, 0050 and 0051 cover recovery authority, preferences/control audit, maintenance admissions, and core-service recovery evidence. No migration has been executed during this continuation.
- Existing FastAPI auth and OPA are retained. New protected action `system_health.maintenance` is source-defined; deployed OPA source synchronization and generated policy metadata are deliberately deferred. Owner preference and export/cancellation endpoints re-check current human authority and audit the change. The browser does not supply actor identity, a command subject or a filesystem path.
- Maintenance is restricted to `storage.evidence.preview`, `storage.evidence.retention`, `sqlite.checkpoint.passive`. Preview reports bounded candidates, not reclaimable bytes. Apply rechecks the exact eligible set and deletes only eligible historical Security scan database rows, never raw evidence files. SQLite physical free-space recovery is not asserted. A checkpoint is not verified while busy or when full completion cannot be established. Uncertain admissions block additional maintenance rather than being replayed; explicit resolution remains outstanding.
- The existing worker owns execution through the canonical domain-command dispatcher or existing consumer watchdog. Core supervisor and runtime reconciler remain independent owners. No additional PM2 controller, NATS browser connection or arbitrary shell bridge.
- Resource preferences affect only stable optional historical reconciliation when the source/environment gate allows it. Production is default-off. No battery readings or essential-service interruption are invented. The recorded preference is not evidence that a worker has applied it.
- New UI controls reuse the existing Manage panel, LiteButton haptics, LiteActionRow and confirmation states. Owner eligibility is server-derived. No independent overlay or theme palette. 
- Backend fixture/authority/maintenance/owner evidence regression and frontend owner confirmation cases authored — NOT RUN. Additional per-operation concurrency, policy, migration, UI, accessibility and runtime qualification cases remain outstanding.

**Continuation status: partial source implementation, not ready for qualification or merge as the full P5–P12 delivery.** No tests, builds, checks, CI investigation, qualification, generated contracts/docs, runtime deployment, production activation, merge, release or tagging were performed.


## Residual source implementation continuation — 2026-11-25

Scope: source implementation only, continuing draft PR #658 on the existing branch from `0a5686b33f211bc82f7c77d37d2c1dec8e61a8ed`. Last implementation commit before this documentation update: `6935759bd115844d43aff9756a46db2aa5d60875`.

All new implementation in this section is **source-authored / unqualified**. GitHub commit/ref results establish that the source was written, not that it compiles, migrates, executes or passes qualification. No production activation, deployment, server-phone operation, test/build/check execution, CI investigation, release or merge was performed.

| Residual capability | Source delivered | Remaining boundary / qualification requirement |
|---|---|---|
| Governed service-specific recovery | Fixed stopped telemetry and server-agent recovery through existing core supervisor, current authority and process generation, restart budget and independent readiness evidence | Other service owners retain existing paths; no arbitrary NATS/API/worker/OPA/remote restart interface |
| Safe cleanup | Exact reviewed preview/apply for aged rotated PM2 archives and marked abandoned database-rehearsal directories, bounded selection, inode and link exclusions, existing owner locks | Cache removal remains with app-specific owner; raw evidence and personal data protected; concurrency and filesystem race qualification required |
| Reclaimable storage | Allocated bytes for exact candidate set and observed before/after available-space delta | Observed delta is not exclusive physical attribution; no guaranteed reclaim amount |
| Uncertain maintenance | Separate durable closed-unverified resolution, explicit current Owner and policy, shared execution fence, no rewriting success or replay | Live owner contention, expiry and closure races require local qualification |
| Workflow retry/cancel | Queued maintenance cancellation and owner navigation for apps/devices/recovery/Safety; fresh optional activity-history reconciliation request | No generic replay/cancel of other owners' accepted or uncertain work; additional per-owner mutation contracts remain source work |
| Battery / charging | Bounded local sysfs observation, explicit unsupported/unknown, thermal and charging-aware evidence | Android permissions and host variants need device proof; remote device battery not newly collected |
| Resource admission | Effective preference and pressure hysteresis for optional stable activity-history cadence; essential services excluded | Not general app/backup/scan workload admission; broader owner contracts remain source work |
| Certificate / clock / scanner DB | Local certificate expiry, local HTTPS trust and hostname plus certificate fingerprint check; systemd synchronization indication where supported; clock-step observation; existing scanner database freshness; durable and loaded policy consistency | No claim of remote end-to-end TLS, synchronized Android clock, or scanner currency without observations |
| Approved configuration recovery | Narrow Caddy desired-state repair candidate through existing runtime reconciler, later approved/observed fingerprints and functional readiness | Other configuration owners remain authoritative; review admission/claim race and exact scope on DEV-PC |
| Restore rehearsal | Bounded isolated verified database copy; exact backup identity/hash/schema, migration rehearsal, integrity and foreign-key checks; no live promotion | Not a full workspace/app restore rehearsal; actual compatibility and resource cost untested |
| Availability / incident timing | 24-hour per-service minute samples, explicit observed coverage, generation-specific observed incident-resolution duration | Not continuous uptime or universal MTTR; missing samples excluded, coverage must accompany interpretation |
| Selective automatic recovery | Fixed Risk A optional activity-history reconciliation via existing scheduler, durable attempts, cooldown, single flight and escalation | Later successful refresh establishes observed completion, not exclusive causality; no automatic cleanup or restart |
| Automatic production policy | Revisioned Owner preference, durable authority and policy binding, exact internal service actor, emergency disable, explicit future runtime gates and separate empty qualification allowlist | No qualified production operation; no actual preference activation or policy promotion |

### Source migrations and authorization

New draft migrations: 0052 (uncertain resolution and availability samples), 0053 (host protection), 0054 (selective automation policy and attempts). The **unreleased draft migration 0050** was extended to enumerate additional fixed operations. This session did not execute any migration. If any external DEV-PC or device already applied the earlier draft 0050, do not overwrite its migration checksum or bypass migration validation: reconcile with a reviewed forward-only migration, or use a fresh disposable candidate database. Do not assume earlier draft migrations have never been applied elsewhere.

Existing OPA source was extended for fixed operations, closure, cancellation and the narrow automatic service actor. Deployed policy, runtime configuration and production qualification allowlists were not activated or promoted. Runtime actor authority, fail-closed behavior, idempotency, stale revisions, replay, leases and owner coordination require actual qualification.

### DEV-PC / Codex handoff (deferred, not executed)

1. Fetch the existing feature branch and confirm exact GitHub head. Read the complete PR and this ledger before editing.
2. Perform a single-agent source integration review of migrations, command/owner contracts, OPA source and synchronization, API schemas, owner lock ordering, scheduler refresh semantics, PM2 state and generation comparisons, protected filesystem manifests, platform capability handling, and frontend query/confirmation state.
3. Resolve the remaining source gaps above against the existing owner contracts; do not introduce a competing executor or generic retry, unrestricted cleanup, or unsafe restart capability.
4. Only in a separately authorized qualification session, use disposable state for schema migration and backend/frontend regression runs, then scoped mocked/live DEV-PC and server-phone qualification using the established project harness. Verify actual Android permissions, TLS listener configuration, pressure/idle overhead and owner failure scenarios. Do not modify production state or promote the empty qualification allowlists merely to obtain passing results.
5. Preserve the draft PR, no merge/release/activation until explicitly authorized after evidence review.

Regression test source was extended for power observation, pressure dwell/recovery, sampled availability, disabled automation, cleanup links, stopped-service generation and configuration mismatch eligibility, and the frontend preference boundary. These are authored tests, not results; they are not a complete qualification matrix.

