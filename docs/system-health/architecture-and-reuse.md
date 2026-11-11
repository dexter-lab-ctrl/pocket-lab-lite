# Pocket Lab Lite — System Health implementation and source reuse

**State:** IMPLEMENTED — DEV-PC AND PHYSICAL ANDROID UI QUALIFIED WITH BOUNDARIES. **Qualification:** PASS for isolated candidate/API and mocked UI; PASS for the narrow physical Android UI scope; PARTIAL for the installed Server Phone backend, which remains on `main` before PR #649.

**Provenance:** dexter-lab-ctrl/pocket-lab-lite; main base SHA `cfd4194fd338aeae07580fa7f227d118bebdd907`; starting feature SHA `37cb4d0597d3f35dbf536f86c5bb21478674d782`; final qualifying feature SHA `fce2c643eff02fab996a8583f3a6ac74541d80d5`; feature `feat/azure-horizon-system-health-intelligence`. The repository is authoritative; historical PRs are context, not proof of runtime readiness.

## Architecture and ownership

React/Vite PWA → Caddy same origin → FastAPI /api/lite/system-health/* → SQLite incident projections. Worker-owned committed Phase 3B/3C observations are the inputs. NATS/JetStream, supervisors, agents, existing app actions and Recovery remain execution owners.

The new System Health service does not execute shell commands, start PM2, connect a browser to NATS, manipulate Tailscale, perform a database restore, change credentials or overwrite configuration.

## Phase P0–P6 matrix

| Phase | Source authored | Gaps and qualification |
|---|---|---|
| P0 | Reviewed live navigation, overlay, SQLite, projection and app registry source; canonical contracts below | VERIFIED by source audit; Server Phone does not contain the PR #649 route |
| P1 | 0043 SQLite schema, stable incident identity, deduplication, recurrence, reopen, freshness, bounded reads and history | VERIFIED by focused backend tests and isolated route qualification; NATS-lifespan integration remains separately limited by local tool availability |
| P2 | 0044 diagnostic/denial audit, risk A/B/C policy registry, authenticated fail-closed preflight, incident-generation guard, idempotency digest | VERIFIED: diagnosis persists, preflight is blocked, repair returns audited denial, no new executor is enabled |
| P3 | Existing watchdog/supervisor ownership preserved; worker-owned NATS/process/agent, storage/SQLite/telemetry signals; registered app-process detection | Source and isolated fixtures qualified; no destructive fault injection or production-phone service changes performed |
| P4 | Lazy System Health tab, Home summary, Apps/Devices/Safety/Recovery links, native Manage, diagnosis, safe guidance, history, policy and dependency views | Mocked desktop/mobile and exact-SHA physical Android UI qualified; haptic actuation and installed-phone System Health API remain separately limited |
| P5 | Dependency authority labels, inferred upstream diagnosis, safe configuration mismatch reporting, recurrence, resource bands and disabled AI state | Truthful unknown/stale/unavailable semantics qualified; predictive forecast remains intentionally unavailable without evidence |
| P6 | Authored pytest, Vitest, Storybook and Playwright, mock API states and handoff | DEV-PC tests/builds pass; Home-only Android performance is baseline-attributed with no `APP_INCREMENTAL_COST`; broader legacy visual loop retains unrelated Catalog drift |

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

- Focused backend System Health tests: 9 passed; related Lite API tests: 336 passed; SQLite/authorization/security/harness/tooling suites passed in the recorded DEV-PC runs. An isolated exact-head route probe verified anonymous rejection, service/Owner reads, diagnosis persistence, CSRF, session expiry, generation fencing, idempotent repair denial and evidence sanitization.
- Frontend: System Health unit 6 passed; System Health mocked desktop/mobile Playwright 10 passed; full unit run 625 passed; Storybook and production build passed. Canonical Home desktop/mobile snapshots were regenerated after physical validation and then Home comparison passed.
- Physical Android candidate: exact SHA `fce2c643eff02fab996a8583f3a6ac74541d80d5`, Chrome `156.0.8078.79`, CDP protocol `1.3`, Android Chrome package verified, 360×691 viewport, 10/10 scoped System Health checks passed, zero repair POSTs, no page errors. API responses in this UI run were repository MSW fixtures, not the installed phone backend.
- Home-only performance: 18 candidate reports and 3×18 baseline-normalized reports. Absolute production gates remained red; final normalized attribution was `MIXED=18`, `APP_INCREMENTAL_COST=0`, with no actionable PR-specific regression established. The seven-screen workflow was not run.
- Server Phone: runtime remained on clean `main` at base SHA `cfd4194…`; core PM2 services and bounded health endpoints were healthy. Its installed backend returned 404 for `/api/lite/system-health/`, so new backend behavior was not represented as phone-runtime validation.

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

No new background polling thread, heavyweight ML library, continuous process sampler, cloud dependency or automatic restart loop is added. Incident processing is invoked only after committed projection changes; read paths are SQLite-based with bounded pagination, bounded in-memory lists and retention. CPU/RSS/WAL/battery impact on Termux/ARM64 must be measured in the qualification phase. No performance claim is made before testing.

## Important deferred work

- Enable a reviewed Class A/B executor only after runtime authorization, lease/cooldown/retry, resource policy, audit and fresh verification are proven.
- Attribute verified repairs from existing guardian/worker lifecycle events, rather than equating healthy observations with repairs.
- Extend app-adapter-specific route, database and backup diagnosis using source facts.
- Add actual historic metric trends/hysteresis before presenting a forecast.
- Map an Apps/Devices contextual entry directly to a canonical incident ID when available.
- Qualify migrations, latency, a11y/haptics and mobile/desktop theme parity.

**Final state: SOURCE IMPLEMENTATION PROVIDED — ISOLATED BACKEND, MOCKED UI AND NARROW PHYSICAL ANDROID UI QUALIFIED — INSTALLED PHONE BACKEND AND FULL PRODUCTION RUNTIME DEFERRED — DRAFT PR REQUIRED.**
