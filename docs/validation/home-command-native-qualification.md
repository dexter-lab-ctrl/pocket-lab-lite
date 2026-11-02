# Azure Horizon Command Home — implementation provenance and deferred qualification

> **Status: AUTHORED / UNVALIDATED.** This document describes source changes on `feat/azure-horizon-home-native-revamp`. No local, browser, Storybook, performance, GitHub CI, or physical Android validation was executed by the implementation session. Do not treat source authoring as qualification.

## Objective and exact baseline

- Repository: `dexter-lab-ctrl/pocket-lab-lite`
- Resolved authoritative `main`: `821ad56f83b2af9cf1fd59001364daf3545cc408`, after merged PR #637.
- Feature branch: `feat/azure-horizon-home-native-revamp`; draft PR targets `main`.
- Target: responsive desktop browsers, mobile browsers and installed Android PWA.
- Scope: Home screen composition, Home-only grouped navigation, source tests, Storybook, mocked browser and visual/performance candidates.
- Exclusions: backend schema, authorization, NATS/JetStream, Devices/Apps/Rules/Security/Recovery screens, production Server Phone, release and deployment.

## P0–P3 authored source map

| Requirement | Authored implementation | Qualification |
|---|---|---|
| P0: Native header, hero, four destinations | `src/lite/LiteHome.jsx` `HomeHealthHero`, `homeCommandHeroPresentation`, `HomeOverviewGrid` | NOT RUN — DEFERRED |
| P0: Status truthfulness | Prepared `buildLiteHomeOverview` unchanged; saved/reachability, stale projection, unknown and running signals drive explicit states | NOT RUN — DEFERRED |
| P0: Attention and recent activity | Existing `prioritizeWorkspaceAttention`, `selectHomeActivityEvidence` and FastAPI-backed activity query | NOT RUN — DEFERRED |
| P1: Native grouped settings | `src/lite/components/HomeGroupedSections.jsx` reused by both Home panels | NOT RUN — DEFERRED |
| P1: Mobile and desktop | `src/lite/components/homeCommand.css` two-column cards on narrow mobile, four on desktop; `@container home-panel` changes details from mobile index/nested to two-column desktop | NOT RUN — DEFERRED |
| P1: Focus, Back, Escape, panel geometry | Grouped navigation focus handoff; existing `LiteDetailsPanel`, `useDesktopManageGeometry`, `useLitePanelSectionNavigation` and portal lifecycle preserved | NOT RUN — DEFERRED |
| P2: Workspace flow | Existing `HomeWorkspaceFlow` retained inside Workspace details → Service health; no new graphing library or dashboard visual | NOT RUN — DEFERRED |
| P3: Restrained polish | Semantic status icons, tone border, Azure-surface cards, touch/focus states and reduced-motion guard; no continuous animation, illustration, or new package | NOT RUN — DEFERRED |

### State authority

The hero differentiates **ready, attention, critical, running, refreshing/checking, saved, offline, partial/stale, initial loading, and unknown/error**. It may not claim ready when the backend reports unknown or the effective status comes from an offline snapshot. The four destination cards use current, named service records for tone, only expose bounded read-only counts from `status.summary` under the ready service state, and retain existing `onNavigate` destinations.

The attention list is conditional and keeps the existing risk priority model, bounded first view and domain routes. Activity uses only `selectHomeActivityEvidence`-approved event labels, status and timestamps. Running and stale records remain distinct. Review history is a separately confirmed, backend-owned operation; changing the personal review cursor never resolves an issue.

## Design-System Reuse and Provenance

| Source PR | Exact existing source or symbols inspected | Classification and Command Home usage | Changes required |
|---|---|---|---|
| [#606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606) | `src/lite/LiteUi.jsx`: `PageHeader`, `GlassCard`, `LiteRefreshButton`, `LiteActionRow`; `src/lite/homeActivityEvidence.js`: `selectHomeActivityEvidence`; `src/lite/homeAttentionPriority.js`: `prioritizeWorkspaceAttention`; `src/lite/components/HomeActivityDetails.jsx` | **Components and selectors reused.** Existing FastAPI status, activity history and private review cursor are retained. | Home composition changed; the activity detail component is wrapped in grouped navigation, while its backend-derived history semantics remain. |
| [#622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622) | `src/lite/theme/azureHorizonTokens.css`, `LiteThemeProvider.jsx`, `src/lite/components/azureHome.css`, `HomeWorkspaceFlow` | **Tokens/theme and flow component reused.** Home-only CSS consumes `--azure-surface`, `--azure-border`, `--azure-text`, `--azure-muted`, `--azure-success`, `--azure-warning`, `--azure-danger`, `--azure-focus`, and related existing variables. | No global theme change; new Home scoped rules and hero only. |
| [#623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623) | `src/lite/components/useDesktopManageGeometry.js` → `useDesktopManageGeometry`; `src/lite/LiteOverlay.jsx` → `LiteDetailsPanel`, `LiteSheet` | **Utilities/components reused.** Desktop Move/Resize/Reset, mobile sheet, Escape, focus return and portal remain shared. | No shared overlay rewrite. |
| [#629](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/629) | `src/lite/catalog/appsPremiumRefinement.css` and existing premium Action/Manage visual density | **Pattern adopted**, not a shared Apps component. Home cards adopt calm spacing, 44px controls, small elevation and bounded copy. | Scoped Home CSS; Apps unchanged. |
| [#634](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/634) | Shared `src/lite/LiteOverlay.jsx`; refined Apps details panel behavior | **Shared overlay reused** and accessible geometry/focus **pattern adopted**. | None to shared overlay. |
| [#635](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/635) | Existing `LiteDetailsPanel` Move/Resize/Reset controls and `useDesktopManageGeometry` | **Components reused.** Desktop panel controls and geometry stay authoritative. | No duplicate Home-specific geometry engine. |
| [#636](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/636) | `src/lite/catalog/appsPremiumRefinement.css` density contract; central `src/lite/theme/azureHorizonTokens.css` | **Theme-independent geometry pattern adopted.** All Command Home dimensions/layout are shared across light/dark/system while existing semantic tokens vary surface colors. | Home-only CSS; no semantic token override or parallel theme engine. |
| [#637](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/637) | `src/lite/catalog/AppCatalogScreen.jsx`: `lite-app-manage-workspace`, `lite-catalog-manage-section-viewport`, `lite-app-manage-back`, sections; corresponding CSS | **Native grouped-settings pattern adopted**, **not** literal Apps component reuse. Home uses one local `HomeGroupedSections` for both panels so Apps UX is unaffected. | Single Home-only component, no general Apps/Manage refactor. |

> Shared component changes: **None** outside Home-specific `HomeActivityDetails.jsx`. Existing token, API, query, geometry, portal and common screen code has not been rewritten. A wider shared-settings extraction could be considered only after targeted qualification demonstrates identical needs.

## Authored qualification inventory — NOT EXECUTED

- Unit/component: `src/lite/LiteHomeScreen.test.jsx` (hero/four destinations, conditional attention, grouped section/Back, saved/offline/unknown/partial/running). Existing `LiteHomeAzure.test.jsx` and `HomeActivityDetails*.test.jsx` remain part of the candidate suite.
- Storybook: `src/lite/LiteHome.stories.jsx`, with Command variants for healthy/attention/offline/unavailable/loading/partial/running/refresh, both themes/System, large text, grouped index and nested sections, desktop panels, mobile widths and reduced motion.
- Mocked Playwright: `tests/e2e/lite-home-command.spec.ts`, responsive 320–1600, destination navigation, grouped nested/back/close/focus, activity review, 200% type, semantic Axe, stale/offline state handling.
- Visual candidates: `tests/e2e/lite-home-command-visual.spec.ts`. PNG references are **not created**. Run, review and explicitly approve a baseline in a separate qualification session.
- Geometry parity: Light/Dark bounding boxes for hero, header, four cards, recent-activity region and panel navigation; maximum intended difference 1.5 CSS px in the authored mock assertion; resized desktop container fallback.
- Performance: `tests/e2e/lite-home-command-performance.spec.ts` plus the adapted `tests/e2e/lite-home-panel-premium-performance.spec.ts`; existing `expectLitePerformanceBudget` from PR #588 is unchanged.
- Existing Home E2E candidates: `lite-home-panel-flow-scroll.spec.ts`, `lite-home-panel-premium.spec.ts`, and `lite-azure-horizon*.spec.ts` adapted where relevant to grouped navigation and the new explicit activity action.

## Deferred qualification commands

These commands are **documentation only**. They were not executed, and are not authorization to run on the Server Phone.

```bash
# Later authorized, isolated DEV-PC working tree; not this implementation session
git fetch origin
git switch feat/azure-horizon-home-native-revamp
npm run build
npm run build-storybook
npm run test:azure:home
npm run test:azure:home:premium:unit
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test \
  tests/e2e/lite-home-command.spec.ts \
  tests/e2e/lite-home-panel-flow-scroll.spec.ts \
  tests/e2e/lite-home-panel-premium.spec.ts \
  --project=mocked-desktop --project=mocked-mobile
VITE_POCKETLAB_PERF_TEST=1 LITE_E2E_MODE=mocked npx playwright test \
  tests/e2e/lite-home-command-performance.spec.ts \
  tests/e2e/lite-home-panel-premium-performance.spec.ts \
  --project=mocked-desktop --project=mocked-mobile
npm run check:render-budgets
npm run test:a11y:states
git diff --check
```

**Visual snapshots:** run the two Home visual specs only after an explicit visual qualification approval; generate baseline images in that future session, inspect every actual PNG in both theme/device variants, then promote reviewed references. Existing pre-revamp Home references are not valid proof of the changed UI.

**Physical Android:** exact-head candidate and baseline-normalized PR #588 performance/thermal tests should be separately authorized and performed without touching an installed production release; preserve the existing baseline absolute-budget misses rather than relabeling them PASS.

### Acceptance criteria

- Every intended responsive size works without horizontal overflow or clipped controls, including 320px, 200% text and a 380px resized desktop panel.
- Daylight/Dark/System retain identical geometry with expected semantic color differences.
- State facts are backend-truthful; no live ready or running claims from stale/unknown source.
- Keyboard/Touch/Escape/Backdrop/Back/focus restores work in both panels, including nested history and server-confirmed mark-reviewed action.
- Accessibility has zero serious/critical violations in Home and both panels.
- Existing PR #588 performance thresholds remain unchanged; report actual measured results and relative attribution.
- Current source and generated docs/contracts gates are evaluated only after authorization.
- No unauthorized runtime, API, backend, app, security, device or release change.

## Gate register

| Gate | Status | Explanation |
|---|---|---|
| Unit / component tests | **NOT RUN — DEFERRED** | Authored source only |
| Storybook build, interactions | **NOT RUN — DEFERRED** | Source stories created; browser review pending |
| Playwright mocked | **NOT RUN — DEFERRED** | Authored only |
| Visual regression / screenshot comparison | **NOT RUN — DEFERRED** | Candidate baselines not generated nor approved |
| Accessibility / 200% text | **NOT RUN — DEFERRED** | Authored Axe and responsive assertions |
| Light / Dark geometry parity | **NOT RUN — DEFERRED** | Geometry assertion authored, not measured |
| Performance / PR #588 hard gates | **NOT RUN — DEFERRED** | Budget helpers and thresholds unchanged |
| DEV-PC build / lint / git checks | **NOT RUN — DEFERRED** | Explicitly excluded |
| Physical Android / Server Phone | **NOT RUN — DEFERRED** | No device contact |
| GitHub Actions | **NOT EVALUATED** | Jobs may trigger automatically, without this session interacting with them |
| Release / deploy / merge | **PROHIBITED** | No merge or production changes |

## Risks, reviewer work and rollback

1. React/JSX/CSS, accessibility, geometry and Storybook compatibility remain **unvalidated**. If tests fail, handle through later authorized review, not an assertion of success here.
2. Existing Home visual references intentionally reflect the old design; newly authored screenshot-candidate specs have no PNG references and require human qualification/promotion.
3. Narrow desktop panel and 200% text, especially with fixed header and portal scroll, need genuine browser validation. CSS container queries follow `home-panel` from the current shared overlay, not viewport heuristics.
4. Baseline low-power Android performance residuals from PRs #588/#636/#637 must be independently attributed; source changes provide no evidence of 60 FPS or hardware qualification.
5. Deferred full repository generated-doc/CI gates might detect source/fixture drift. This authoring session does not repair or re-run CI.
6. The design has no new browser authority; panel navigation and animation do not alter the FastAPI/NATS/worker trust boundary.

**Rollback:** As this is an unmerged draft branch, close the PR or revert only the feature commits after review. Do not reset `main`, force-push shared branches, change production services, or remove existing server state as a UI rollback.

**Merge restriction:** **DRAFT PR — IMPLEMENTATION COMPLETE TO THE EXTENT AUTHORED; NO VALIDATION EXECUTED. NOT APPROVED FOR MERGE, SQUASH, RELEASE, OR DEPLOYMENT.**
