# Pocket Lab Lite — System Health implementation and source reuse

**State:** IMPLEMENTED — DEV-PC AND ISOLATED PHYSICAL ANDROID/TERMUX BACKEND-PROMOTION WORKFLOW QUALIFIED WITH BOUNDARIES. **Qualification:** PASS for exact-SHA artifact verification, isolated promotion, schema-42→44 backup/restore/migration rehearsal and the inactive phone-side candidate; production backend activation remains intentionally unperformed on `main` because the live admission gate requires the missing external guardian.

**Provenance:** dexter-lab-ctrl/pocket-lab-lite; main base SHA `cfd4194fd338aeae07580fa7f227d118bebdd907`; prior System Health UI candidate SHA `8c21a4ff729f89064aa794c65bf8795beeef4ed4`; backend-promotion candidate SHA `0b767dc662c8f7c37accb4bc5fbad71a5f31564f`; feature `feat/azure-horizon-system-health-intelligence`. The repository is authoritative; historical PRs are context, not proof of runtime readiness. Documentation synchronization may produce a later feature SHA without changing the qualified backend candidate.

## Architecture and ownership

React/Vite PWA → Caddy same origin → FastAPI /api/lite/system-health/* → SQLite incident projections. Worker-owned committed Phase 3B/3C observations are the inputs. NATS/JetStream, supervisors, agents, existing app actions and Recovery remain execution owners.

The new System Health service does not execute shell commands, start PM2, connect a browser to NATS, manipulate Tailscale, perform a database restore, change credentials or overwrite configuration.

## Phase P0–P6 matrix

| Phase | Source authored | Gaps and qualification |
|---|---|---|
| P0 | Reviewed live navigation, overlay, SQLite, projection and app registry source; canonical contracts below | VERIFIED by source audit; Server Phone does not contain the PR #649 route |
| P1 | 0043 SQLite schema, stable incident identity, deduplication, recurrence, reopen, freshness, bounded reads and history | VERIFIED by focused backend tests and isolated route qualification; NATS-lifespan integration remains separately limited by local tool availability |
| P2 | 0044 diagnostic/denial audit, risk A/B/C policy registry, authenticated fail-closed preflight, incident-generation guard, idempotency digest | VERIFIED: diagnosis persists, preflight is blocked, repair returns audited denial, no new executor is enabled |
| P3 | Existing watchdog/supervisor ownership preserved; worker-owned NATS/process/agent, storage/SQLite/telemetry signals; registered app-process detection | Source and exact-SHA isolated ARM64/Termux candidate qualified; no destructive fault injection or production-phone service changes performed |
| P4 | Lazy System Health tab, Home summary, Apps/Devices/Safety/Recovery links, native Manage, diagnosis, safe guidance, history, policy and dependency views | Mocked desktop/mobile and exact-SHA physical Android Chrome-to-candidate UI qualified; hardware haptics and production API remain separately limited |
| P5 | Dependency authority labels, inferred upstream diagnosis, safe configuration mismatch reporting, recurrence, resource bands and disabled AI state | Truthful unknown/stale/unavailable semantics qualified; predictive forecast remains intentionally unavailable without evidence |
| P6 | Authored pytest, Vitest, Storybook and Playwright, mock API states and handoff | DEV-PC tests/builds pass; Home-only Android performance is baseline-attributed with no `APP_INCREMENTAL_COST`; exact-SHA phone-side backend candidate and isolated migration proof pass; broader legacy visual loop retains unrelated Catalog drift |

## Architectural recommendations 1–12

1. Incident detection, canonical history, reopen: implemented from supported signals; unvalidated.
2. A/B/C remediation policy: allowlist and admission/denial authored; new executors blocked. Existing Class A guardians unchanged.
3. Diagnose & Fix: evidence-backed diagnosis and guidance; Fix unavailable until qualification.
4. Root-cause graph: inferred symptoms and verified-contract edges, not proof of live connectivity.
5. Independent guardian/PM2/supervisor: reused unchanged, avoiding a second process manager.
6. NATS/worker lifecycle: existing durable-consumer watchdog reused, no new destructive replay.
7. App-specific: registered process mapping and safe read-only app diagnostics, existing App actions own actual repairs.
8. Resource pressure: existing thresholds reused, forecast honestly unavailable.
9. Rollback: existing preview/checkpoint/restore gates remain exclusively authoritative.
10. Configuration: reported observed process mismatch; intentional/approved drift cannot be decided from an old snapshot.
11. Knowledge: recorded recurrence and diagnostics; no invented success rates.
12. Optional AI: explicitly disabled; no cloud requirement or AI repair authority.

## Exact backend files

- pocket-lab-final-structure/runtime/api_fastapi/db/schema/0043_system_health_intelligence.sql — incident, observation, repair-attempt and event tables.
- pocket-lab-final-structure/runtime/api_fastapi/db/schema/0044_system_health_audit.sql — immutable sanitized diagnostic and repair-denial decisions.
- pocket-lab-final-structure/runtime/api_fastapi/services/lite_system_health.py — event-driven ingress, incident lifecycle, graph, diagnosed/blocked states, preflight and history.
- pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3b_projections.py and lite_phase3c_projections.py — forward only committed worker-owned projection data.
- pocket-lab-final-structure/runtime/api_fastapi/routers/lite_system_health.py and main.py — authenticated FastAPI control endpoints.

GET paths: /summary, /incidents, /incidents/{id}, /incidents/{id}/decisions, /history, /dependencies, /resources, /intelligence, /configuration-drift, /apps/{app_id}, /policies, /repairs.
POST paths: /incidents/{id}/diagnose (persist diagnosis), /incidents/{id}/preflight (always blocked), /incidents/{id}/repair (always 409 with audited denial). All paths share /api/lite/system-health base.

**No new repair is executed by these paths.** A healthy observation can resolve a detection but cannot count as a verified repair. Unknown and stale never imply healthy.

## Qualification record

- Focused Android qualifier tests: 8 passed; the combined qualifier/System Health regression run passed 15; the full backend gate passed 171 with 165 unrelated tests deselected. SQLite/authorization/security/harness/tooling suites passed in the recorded DEV-PC runs. An isolated exact-head route probe verified anonymous rejection, service/Owner reads, diagnosis persistence, CSRF, session expiry, generation fencing, idempotent repair denial and evidence sanitization.
- Frontend: System Health unit 6 passed; System Health mocked desktop/mobile Playwright 10 passed; full unit run 625 passed; Storybook and production build passed. Canonical Home desktop/mobile snapshots were regenerated after physical validation and then Home comparison passed.
- Physical Android/Termux backend candidate: exact SHA `8c21a4ff729f89064aa794c65bf8795beeef4ed4`, ARM64/aarch64, Python `3.14.6`, read-only snapshot manifest `c0271831a23a7e867bae238cc09b287783b6ada8603d13f6d3473d287bc980d1`, schema 42→44 isolated migration and rollback proof passed. Real candidate API routes and blocked-repair/security contracts passed; production PM2/Caddy/NATS/SQLite were not used.
- Android Chrome-to-candidate UI: exact candidate manifest and response headers matched `8c21a4ff729f89064aa794c65bf8795beeef4ed4`; Chrome `157.0.8103.50`, CDP Protocol `1.3`, package `com.android.chrome`, loopback websocket and explicit standard-user ADB selection passed. Summary, incidents and diagnosis were consumed from the candidate; Manage opened, diagnosis returned `200`, Fix was disabled, no repair/preflight write occurred and Home navigation returned.
- Home-only performance: 18 candidate reports and 3×18 baseline-normalized reports. Absolute production gates remained red; final normalized attribution was `MIXED=18`, `APP_INCREMENTAL_COST=0`, with no actionable PR-specific regression established. The seven-screen workflow was not run.
- Server Phone production runtime: clean `main` at base SHA `cfd4194…`; all 10 observed PM2 services were online and bounded health observation remained non-disruptive. Its installed backend remains separately identified because production activation was not performed. Candidate processes and temporary qualification material were removed; the production database was not touched.

## Backend promotion and activation contract

The repository-owned `scripts/dev/lite/backend_runtime_promotion.py` is the bootstrap-side promotion controller for the backend runtime. It is separate from the PWA `dist.zip` release flow and does not replace the existing release controller. `scripts/dev/lite/run-backend-runtime-promotion-android-qualification.py` performs the bounded physical qualifier; it stages only an exact-SHA artifact and controller in a unique inactive phone cache directory, uses disposable SQLite state for lifecycle tests, records a read-only live admission snapshot and removes its temporary directory.

The artifact is schema `pocketlab.backend-runtime-artifact/v1`: exact Git SHA, deterministic 284-file inventory, SHA256 checksums, Android/Termux aarch64 + PRoot Ubuntu target, required service ownership, complete migration checksums through schema 44, forbidden-path/secret/symlink checks and no environment or credential material. Admission binds candidate SHA, artifact digest, current production SHA, protected database device identity, schema, storage/memory/battery/thermal, SQLite integrity, Caddy/FastAPI readiness, all required PM2 services, worker-owned runtime-contract heartbeat and the external guardian.

Backup assurance uses SQLite online backup with WAL included, receipt hashes and an independent restore target. The actual production snapshot remained schema 42, integrity/quick-check passed and the isolated rehearsal applied migrations 0043 and 0044 exactly once to schema 44 with data, foreign-key and checksum validation. The old `main` runtime does not know migrations 0043/0044, so code-only rollback is not admitted. The controller uses consistent code-and-database restore, disables automatic rollback after newer writes, records a durable journal and fails closed with `manual_recovery_required` when a write boundary is uncertain.

Promotion authorization and recovery authorization are separate Ed25519, short-lived, single-use contracts. They bind exact candidate/current revisions, target identity, artifact and receipt digests, preflight evidence, checkpoint and audit identity. A durable lock, atomic pointer/database transition, controlled writer quiescence, consecutive health observations and restart reconciliation protect the cutover. No final production authorization was issued or consumed.

**Physical result at `0b767dc6`:** artifact verification PASS; isolated candidate promotion PASS; schema 42→44 migration PASS; phone checkout before/after `main` + clean at `cfd4194…`; temporary candidate removed; production preflight `BLOCKED` only by `external_guardian=false`. Worker heartbeat is `PASS` from the existing sanitized `/api/lite/runtime` runtime contract (`state=stable`, `stable=true`, `pocket-worker` stable). Other admission checks—device identity, schema 42/integrity, Caddy/FastAPI readiness, required PM2 services, storage, memory, battery and thermal—passed. This is candidate qualification plus admission evidence, not production activation.

## Source reuse matrix — verified repository paths

| Reference PR | Existing path and component/service | Where reused, adaptation and reason for new code |
|---|---|---|
| #606 | src/lite/LiteUi.jsx — PageHeader, GlassCard, LiteButton, LiteRefreshButton, LiteActionRow, StateSurface | System Health/Home use shared buttons, states, layout; only new health composition added |
| #622, #636 | Existing Azure semantic token contract and src/lite/components/azureHome.css | src/lite/systemHealth.css uses Azure CSS variables and theme-neutral spacing; no hardcoded colors or theme-dependent geometry |
| #623, #635, #648 | src/lite/components/useDesktopManageGeometry.js | System Health Manage reuses bounded move/resize/reset and keyboard support |
| #629, #634, #637 | src/lite/LiteOverlay.jsx — LiteDetailsPanel/LiteSheet | Existing modal portal, mobile snap/expand, focus, Close and backdrop; no duplicated drag logic |
| #637, #638, #645, #646 | src/lite/components/HomeGroupedSections.jsx and src/lite/hooks/useLitePanelSectionNavigation.js | Group rows, chevrons, Back, focus and scroll ownership |
| #640 | Existing liteNativeFeedback.js and global button haptic behavior | Shared LiteButton haptic used for contextual action; no second vibration implementation |
| #643, #648 | src/lite/LiteDevices.jsx | Adds a navigation-only System Health diagnosis entry |
| #644 | src/lite/LiteRecovery.jsx | Adds contextual entry without changing protected restore policy |
| #638, #646 | src/lite/LiteHome.jsx | Adds a compact health count/attention summary and navigation |
| Current main | src/lite/liteNavigationMetadata.js, liteNavigationConfig.js, liteScreenRegistry.js | Registers one lazy tab and deep-link support in existing routing |
| Current main | src/lib/liteApi.js, liteQueryClient.js, liteSafeSnapshots.js | FastAPI reads and safe compact summary; no offline cache of command payloads or sensitive evidence |
| Existing runtime | lite_phase3b_projections.py, lite_phase3c_projections.py, lite_app_registry.py | No new subprocess, network collector or app execution loop |

## Interface and security guarantees

Desktop uses the shared Manage drag/resize/reposition and focus controls; mobile uses shared bottom-sheet Compact/Expand. Daylight, Black and System have identical CSS geometry and colors from --azure-* tokens. The dashboard displays only sanitized summaries. Raw logs, evidence, private Android paths, secrets, hashes and actual command payloads stay backend-only.

The Home card shows recent observed services and counts without upgrading cached or incomplete state to healthy. The new contextual links in Apps, Devices, Safety and Recovery navigate to the same System Health workspace rather than invoking independent repair operations.

## Low-power and rollout constraints

No new background polling thread, heavyweight ML library, continuous process sampler, cloud dependency or automatic restart loop is added. Incident processing is invoked only after committed projection changes; read paths are SQLite-based with bounded pagination, bounded in-memory lists and retention. Candidate-only CPU/RSS/WAL/battery observations were collected on ARM64/Termux; they are not production performance claims.

## Important deferred work

- Enable a reviewed Class A/B executor only after runtime authorization, lease/cooldown/retry, resource policy, audit and fresh verification are proven.
- Attribute verified repairs from existing guardian/worker lifecycle events, rather than equating healthy observations with repairs.
- Extend app-adapter-specific route, database and backup diagnosis using source facts.
- Add actual historic metric trends/hysteresis before presenting a forecast.
- Map an Apps/Devices contextual entry directly to a canonical incident ID when available.
- Keep the repository-owned standard-user candidate proxy/CDP bridge as the narrow Android qualification path; no browser fixture or production route is substituted for candidate identity.
- Start and verify the existing external Termux runtime guardian through its supported boot/recovery ownership path, then repeat the read-only admission and obtain a separate explicit production-promotion authorization. Do not bypass the guardian check or treat PM2 online as a substitute.
- Qualify remaining deferred fault scenarios and independently measure hardware haptics.

**Final state: SOURCE IMPLEMENTATION AND GUARDED PROMOTION WORKFLOW PROVIDED — EXACT-SHA ARM64/TERMUX CANDIDATE, ISOLATED MIGRATIONS, MOCKED UI AND ANDROID CHROME-TO-CANDIDATE UI QUALIFIED — PRODUCTION ACTIVATION NOT PERFORMED; LIVE ADMISSION BLOCKED BY THE MISSING EXTERNAL GUARDIAN — DRAFT PR REQUIRED.**
