# Azure Horizon Safety Center — P0–P3 implementation and deferred qualification

> **Status:** [IMPLEMENTED — SOURCE ONLY], [UNVALIDATED]. This document does not assert that tests, builds, screenshots, scanner runs, CI, or Android qualification passed. **No validation execution was authorized or performed in this session.**

## 1. Objective and provenance

Azure Horizon Safety Center gives Pocket Lab Lite's **Safety** screen a calm, backend-truthful desktop and mobile interface. It retains the existing Security domain and action contracts, and teaches the user: **outcome → coverage → findings → next safe action → sanitized evidence**.

- Repository: `dexter-lab-ctrl/pocket-lab-lite`
- Authoritative source base: remote `main` at `b685d2ce3c19f11d590932d7fd37f6e3ad3dc470`
- Working branch: `feat/azure-horizon-safety-ui`
- Implementation: P0 Foundation; P1 Safety overview; P2 Manage Safety; P3 protected scan paths and **unexecuted** test infrastructure.
- Public UI label: **Safety Center**. Existing `LiteSecurity.jsx`, Security API paths, state identifiers, evidence and event schema are not renamed.

This source-first phase deliberately does **not** mutate FastAPI, SQLite, JetStream, the worker, server phone, scanners, or release artifacts.

## 2. Architecture and ownership

```text
React/Vite PWA
  → same-origin Caddy
  → FastAPI /api/lite/security/* (authority for acceptance/results)
  → NATS/JetStream
  → worker/agent/supervisor
  → Lynis / Trivy / sanitized evidence / SQLite
  → FastAPI prepared summary + profile + progress + history
  → TanStack Query and saved safe-read snapshots
  → Safety Center display
```

The frontend must **not** execute commands, contact NATS, hold scanner secrets, expose raw evidence, or manufacture success. Scan admission and acceptance remain FastAPI/backend-owned. Existing `useLiteSecurityCheckFlow`, `useLiteSecurityEvents`, replay cursor handling, bounded fallback polling, the Service Worker update blocker, and action status reconciliation remain in place.

**State boundaries:** TanStack Query owns live prepared FastAPI server-state; Dexie/snapshot APIs provide sanitized *read-only* offline fallbacks; Zustand stores harmless selected profile, Manage section and overlay state; XState-guided workflow reflects user interactions but is not execution authority. No new backend truth cache or browser command queue is introduced.

## 3. Actual reuse matrix

| Foundation | Existing source re-used | This increment |
|---|---|---|
| PR #606 — shared Lite UI | `src/lite/LiteUi.jsx`: `PageHeader`, `LiteButton`, `LiteOperationalStory`, `LiteActionRow`, `LiteFlowStatusPanel`, `LiteOutcomeNotice`, `GlassCard` | Reuses existing components for hero, summary, actions, facts, and check states; no new component framework |
| PR #606 — overlays | `src/lite/LiteOverlay.jsx`: `LiteSheet` | Retains portal, focus trap, backdrop, Escape, nested sheets and safe motion |
| PR #622 — Azure system | `src/lite/theme/azureHorizonTokens.css`, `src/lite/theme/azureHorizon.css`, `LiteThemeProvider.jsx` | Adds scoped token-based styling for Black, Daylight, System, including mobile and portal surfaces |
| PR #623 — desktop Manage geometry | `src/lite/components/useDesktopManageGeometry.js` | Reuses viewport-clamped pointer move, keyboard move/resize, reset and mobile breakpoint; geometry transient, never persisted |
| PR #624 — protected interaction | Existing `LiteSheet`, `LiteConsequenceSummary` and confirmation functions in `LiteSecurity.jsx` | Reconnects Full/App profile dispatch to **existing** confirmation sheets before execution |
| PR #630 — operational truth | Existing `selectSecuritySafetyStoryView`, `selectSecurityScreenView`, `LiteFreshness`, `LiteEvidenceGuide` | Shows reported state, scope and stale/offline meaning; no fabricated clean outcomes |
| PR #588/#589 — performance | Existing performance primitive attributes, playwright perf components, `check:render-budgets` and Android qualification scripts | Keeps thresholds unchanged; adds supplemental synthetic interaction samples only |

**Other existing source reused without rewriting:** `src/lite/security/SecurityFindingDetailsLazy.jsx`, `SecurityHistoryLazy.jsx`, `SecurityProgressiveDetailsLazy.jsx`, `securityPreload.js`, `src/hooks/useLiteSecurityEvents.js`, `src/lib/securityProgressEvents.js`, `src/lib/liteSecurityProgressPolicy.js`, `src/lib/liteViewModels.js`, `src/stores/liteUiStore.js`, `src/lite/LiteUx.jsx`.

## 4. P0 — theme and surface foundation

The existing source-of-truth palette in `azureHorizonTokens.css` continues to define `--azure-canvas`, `--azure-surface`, `--azure-raised`, `--azure-border`, `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-focus`, semantic warning/danger/success, and button tokens. This work extends `src/lite/theme/azureHorizon.css`; it does **not** introduce a competing palette.

**Black** inherits the dark tokens (`#050607` canvas, `#0B0F14` main surface, `#121822` raised surface, `#1F2A36` border). **Daylight** inherits the light tokens (`#F4F9FF`, `#FFFFFF`, `#E7F2FF`, `#D5E5F8`). **System** follows `data-lite-theme` resolution in the existing theme provider. Portal overlays are already attached to the document and synchronize light/dark theme classes in `LiteSheet`. The Safety extension styles main hero, findings, coverage, tabs, frame, progress-adjacent content, desktop geometry controls, and focus with shared tokens.

All theme, contrast, full nested-overlay, and screenshot claims remain **UNVALIDATED** until future browser/a11y/visual qualification. Do not claim dark-mode bleed is eliminated simply because token CSS was authored.

## 5. P1 — outcome-first Safety overview

The default screen preserves the established PageHeader and Safety components and now puts the visible **Safety overview** `GlassCard` first, rather than relying on a hidden legacy hero.

It presents:
- **Reported score** only when the existing safety story marks score provenance as `backend_reported`; otherwise an accessible dash communicates **not reported**.
- **Profile** (Quick/Full/App), **last check/freshness**, **saved-result state**, an evidence status and a statement that the score applies only to the selected profile and its coverage.
- Three compact facts: Items to review, Check coverage, Evidence. Missing checks/evidence are **not** turned into clean/pass claims.
- **Needs attention**: a bounded preview of the latest profile's findings and a Manage Issues action.
- **Coverage & checks**: checked/partial/timed-out/skipped summary and scanner status, including an explicit absence state when coverage metadata is missing.
- **Recent checks & changes**: saved completion information and strictly same-profile, same-app scored history comparability; latest comparison details remain in Manage.

This is a UI presentation refinement, not a change in score computation, scanner grading, or backend projections. A safety score is **not a guarantee** that all apps/devices were inspected or that no vulnerability exists. Partial, missing, skipped, failed or timed-out targets must be reviewed in Coverage before relying on conclusions.

## 6. P2 — Manage Safety

The same `LiteSheet` remains the primary management surface. Its navigation exposes the nine already-developed content sections:

| Section | User intent | Deeper existing surface |
|---|---|---|
| Overview | Saved status, profile, assessment, evidence, next steps | Open Checks |
| Checks | Select Quick/Full/App; review latest profile state | Coverage / check record |
| Changes | New/resolved/ongoing differences | Lazy Changes details |
| Issues | Findings, severity and safe next steps | Existing finding details and remediation overlay |
| Coverage | Checked, skipped, partial, missing, timed out | Lazy Coverage details |
| Check path | Backend-reported request/tool/evidence stages | Lazy execution timeline |
| Evidence | Sanitized metadata, evidence saved/unknown | Existing sanitized summary |
| History | Profile-specific history, saved/stale record | Lazy History details |
| Technical details | Non-sensitive operational facts | Lazy technical details |

Tabs use explicit accessible names, `role="tablist"`, `role="tab"`, one active `role="tabpanel"`, `aria-selected`, `aria-controls`, roving tab index, and Home/End/arrow keys. Heavy detail content remains lazy and hydrated **only** after explicit navigation. Nested detail sheets remain on existing portals and keep focus management.

**Desktop (≥701px):** `useDesktopManageGeometry({ open, defaultWidth:720, minWidth:420, minHeight:420 })` supplies `surfaceRef`, `surfaceStyle`, and viewport-clamped geometry. Only the dedicated **Move**, **Resize**, and **Reset** header buttons own panel manipulation. Keyboard Arrow keys adjust position/size; Home resets. The panel's coordinates are transient React state and are discarded upon close. No broad card dragging or browser-side state persistence.

**Mobile (≤700px):** existing bottom-sheet LiteSheet behavior is retained; desktop handles are absent. Cards stack into one column, profile controls into touch-friendly rows, tabs scroll horizontally, and narrow 320–390px facts reflow. This is implemented CSS/source behavior, **not yet measured** for overflow, zoom, or mobile accessibility.

## 7. P3 — scan profiles, confirmation and progress

| Profile | Request and boundaries | UI |
|---|---|---|
| Quick | Existing `liteApi.runSecurityScan('local', {profile:'quick', ...})` through FastAPI and worker | Existing Quick action (safe admission rules unchanged) |
| Full | Existing `liteApi.runSecurityScan('local', {profile:'full', ...})`, potentially slower/heavier, no user media | **Existing** Full Local Check `LiteSheet` now opens before dispatch. Explicit confirm required |
| App | Existing `liteApi.checkSecurityApp(app_id, ...)`, PhotoPrism target guarded by backend, media excluded | **Existing** Check PhotoPrism `LiteSheet` now opens before dispatch. Explicit confirm required |

**Source defect corrected:** the pre-existing `runSecurityProfile` dispatcher directly called `startFullLocalCheck()` and `startAppCheck()` instead of the already-implemented `openFullLocalConfirm()` and `openAppCheckConfirm()`. The targeted change restores the existing protected UI review step. This is **UNVALIDATED** until interactions and network absence-before-confirmation are checked.

**Truthful optimistic start:** the frontend no longer seeds synthetic `4%` and `8%` on queuing/acceptance. Pending states show request preparation with `percent:null`, and numeric progress is rendered only if received from backend projection/accepted progress. `aria-valuenow` is omitted if no measured progress is present. It does **not** claim a scan finished merely because the request was accepted. Existing SSE replay, reconnect, bounded polling, lifecycle reconciliation and evidence-saving signals remain untouched.

**Finding details, remediation and evidence:** existing action indicators, safe remediation UI, detail sheets, sanitized evidence summary and technical metadata remain available. The browser does not acquire raw Lynis/Trivy output, secret values, protected paths, bootstrap payloads, or backend-only full receipts.

**Saved/offline:** prior safe read-only snapshots can be displayed with explicit stale/offline language, but cannot be used as authority to initiate a new scan. Current backend reachability, existing state machine guards, and backend admission remain required.

## 8. Accessibility and responsiveness implementation

Source defines: one visible reported/unreported score; meaningful score caveat; accessible progress value text; keyboard tab navigation; dedicated pointer/keyboard geometry controls; shared LiteSheet focus trap/return/Escape/backdrop; 44px+ tab and geometry controls; semantic colors and focus outlines; max-width constraints; 320px layout; 200% text enlargement scenarios; and `prefers-reduced-motion` CSS.

**Unvalidated concerns:** exact contrast ratios, screen reader announcements, gesture conflicts, focus restore from header action, 200% enlargement clipping, viewport-change recalculation, Android performance, and inherited older CSS precedence must be assessed by later automated and manual qualification.

## 9. Source files and regression infrastructure

| Type | Sources |
|---|---|
| Safety UI | `src/lite/LiteSecurity.jsx` |
| Shared theme | `src/lite/theme/azureHorizon.css` |
| Pure view guards | `src/lite/security/safetyAzurePresentation.js` |
| Unit tests | `src/lite/security/safetyAzurePresentation.test.js` |
| Storybook | `src/lite/LiteSecurity.stories.jsx` |
| Playwright behavior/Axe/geometry | `tests/e2e/lite-azure-horizon-safety.spec.ts` |
| Playwright visual definitions | `tests/e2e/lite-azure-horizon-safety-visual.spec.ts` |
| Playwright perf samples | `tests/e2e/lite-azure-horizon-safety-performance.spec.ts` |
| Future npm commands | `package.json` `test:safety:azure:*` |
| Future Taskfile commands | `tasks/Taskfile.ui.yml` `lite:test:safety:azure:*` |
| This documentation | `docs/development/lite-azure-horizon-safety-refinement.md` |

Unit fixtures cover reported/unreported score, 0 as legitimate reported score, invalid/optimistic progress, incomplete/missing coverage and strict same-target historical comparison. Stories cover Black/Daylight/System, desktop/mobile, first-run, urgency, unavailable scanners, stale state, active scan, nine Manage areas and 200% text cases. Playwright cases define mocked theme and width matrix, three scan profiles, confirmation-before-request, keyboard/geometry, saved/offline, Axe WCAG AA, zoom, reduced motion, and screenshot candidates.

**Visual screenshots and baselines:** No new screenshots were captured, evaluated, committed or approved. Snapshot test definitions will need baseline capture and independent review before visual tests can pass. The supplemental performance test measures synthetic browser interactions; it is *not* the PR #588/#589 Android or 60 FPS gate. Existing render budgets and physical qualification stop conditions remain unchanged.

## 10. Future Codex stabilization runbook — all commands NOT RUN

**Every command below is NOT RUN — DEFERRED TO CODEX STABILIZATION.** They are documentation only, not execution instructions for the current session.

```bash
# Focused unit and UI qualification
npm run test:safety:azure:unit
npm run test:safety:azure:mocked
npm run test:safety:azure:a11y
npm run test:safety:azure:geometry
npm run test:safety:azure:storybook
npm run test:safety:azure:visual       # only after candidate baselines approved
npm run test:safety:azure:perf
npm run test:safety:azure:qualification

# Existing broader authority
npm run build
npm run test:a11y:states
npm run test:mock-regression
npm run test:perf
task lite:check
```

Future isolated stabilization must qualify exact-head source/tests and Storybook; Black/Daylight/System and nested portals; screenshots and contrast; ARIA and keyboard/focus; mobile 320px/200%; movement/resizing at 701px breakpoint; SSE reconnect and persisted replay; bounded freshness and lazy hydration; Quick/Full/App acceptance, unauthorized/duplicate/blocked paths and no request before protected confirmation; scanner coverage, evidence redaction and prior-run comparability; PR #588/#589 budgets and physical Android CDP where supported. If a physical device cannot be placed in foreground, report **BLOCKED**, never a fabricated PASS. Live Server Phone verification must remain read-only unless separately authorized.

## 11. Risks, compatibility, rollback and disposition

**Known unvalidated risks:**
1. Existing source-assertion tests or visual snapshots may encode the five-tab Security panel or hidden legacy hero.
2. Existing legacy `src/index.css` rules may override semantic tokens, cause dark-mode visual bleed or hide the new card; actual computed CSS remains unmeasured.
3. Some mocks may not populate authoritative coverage or profile latest runs; the UI must retain **Not reported** in that case.
4. Existing SSE stream/progress fallback may present different shapes than the synthetic fixtures; no live run was performed.
5. Scrolling, keyboard focus, 200% text or nested overlay interactions may require CSS/focus refinements.
6. Shared geometry minimum width and large viewport reductions require actual browser qualification.
7. New screenshot assertions intentionally lack approved candidate baselines.
8. Android CPU, rendering and input latency are unmeasured; no 60 FPS qualification claim is permitted.
9. The confirmation-source fix must be tested against real API request dispatch in isolated authenticated mocks.
10. Existing source-level backend assertions and fixed test selectors may need follow-up reconciliation; CI issues, if any, belong to a separate stabilization session.

No main-branch changes, release tags, scanner execution, migrations, or deployment were authorized. To roll back without disturbing main, revert individual feature-branch commits or close the draft PR and remove its feature branch after explicit review. Avoid rewriting shared geometry or altering backend scan admission for a visual rollback.

**Enterprise value:** a clear safety narrative, source-labeled coverage uncertainty, worker-truthful progress, protected app/deep checks, disciplined evidence privacy, documented accessibility/performance qualification and shared system-wide UI consistency.

**Current disposition: [IMPLEMENTED — SOURCE], [UNVALIDATED], DRAFT PR, MERGE BLOCKED.**
