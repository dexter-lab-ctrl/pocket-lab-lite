# Azure Horizon Command Home — implementation provenance and qualification

> **Status: VALIDATED / PARTIAL / BLOCKED.** This addendum records the exact-head DEV-PC, mocked browser, accessibility and reviewed visual-reference qualification for the PR #634 mobile snap integration on `feat/azure-horizon-home-native-revamp`. The current physical Android snap run is blocked at the established Windows CDP/UAC bridge prerequisite; the prior PR #638 Android evidence remains separately classified as an absolute frame-budget miss with mixed baseline attribution. The PR remains **OPEN — DRAFT — NOT MERGED**.

## Objective and exact baseline

- Repository: `dexter-lab-ctrl/pocket-lab-lite`
- Resolved authoritative `main`: `821ad56f83b2af9cf1fd59001364daf3545cc408`, after merged PR #637.
- Feature branch: `feat/azure-horizon-home-native-revamp`; draft PR targets `main`.
- Initial PR head observed: `c0a1aabc7f905d37216254e2dae9074e61dd0211`.
- Prior PR #638 runtime-qualified candidate: `a1bb1dc84eb17b5a2b792efd00759147c8f07359`.
- Exact candidate for this PR #634 mobile snap integration: `a1827836a63f45884398f32bb002af2017d2445f`.
- Target: responsive desktop browsers, mobile browsers and installed Android PWA.
- Scope: Home screen composition, Home-only grouped navigation, direct reuse of the PR #634 mobile snap controller on Home detail sheets, source tests, Storybook, mocked browser and narrowly scoped physical qualification infrastructure.
- Exclusions: backend schema, authorization, NATS/JetStream, Devices/Apps/Rules/Security/Recovery screens, production Server Phone, release and deployment.

## P0–P3 authored source map

| Requirement | Authored implementation | Qualification |
|---|---|---|
| P0: Native header, hero, four destinations | `src/lite/LiteHome.jsx` `HomeHealthHero`, `homeCommandHeroPresentation`, `HomeOverviewGrid` | **VERIFIED** — focused unit, mocked browser, geometry and reviewed visual references |
| P0: Status truthfulness | Prepared `buildLiteHomeOverview` unchanged; saved/reachability, stale projection, unknown and running signals drive explicit states; the hero now uses the shared `LiteFreshness` primitive | **VERIFIED** — state matrix, shared UX contract and mocked browser coverage |
| P0: Attention and recent activity | Existing `prioritizeWorkspaceAttention`, `selectHomeActivityEvidence` and FastAPI-backed activity query | **VERIFIED** — activity/attention browser and unit coverage |
| P1: Native grouped settings | `src/lite/components/HomeGroupedSections.jsx` reused by both Home panels | **VALIDATED** — desktop/mobile flow, Back, Escape, focus return and physical Home interaction sequence |
| P1: Mobile and desktop | `src/lite/components/homeCommand.css` two-column cards on narrow mobile, four on desktop; `@container home-panel` changes details from mobile index/nested to two-column desktop; Home details opt into shared `mobileSnap` | **VALIDATED** — 320/360/375/390/430/768/1024/1280/1440 mocked geometry and reviewed references |
| P1: Focus, Back, Escape, panel geometry | Grouped navigation focus handoff; existing `LiteDetailsPanel`, `useDesktopManageGeometry`, `useLitePanelSectionNavigation` and portal lifecycle preserved | **VALIDATED** — focused flow, accessibility and geometry suites |
| P2: Workspace flow | Existing `HomeWorkspaceFlow` retained inside Workspace details → Service health; no new graphing library or dashboard visual | **VERIFIED** — unit, browser and physical Home-only interaction evidence |
| P3: Restrained polish | Semantic status icons, tone border, Azure-surface cards, touch/focus states and reduced-motion guard; no continuous animation, illustration, or new package | **VERIFIED** — build, Storybook, accessibility and visual inspection |

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
| [#634](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/634) | `src/lite/components/useMobileSheetSnap.js`, `src/lite/components/mobileSheetSnap.css`, `LiteSheet` and `LiteDetailsPanel` in `src/lite/LiteOverlay.jsx` | **Direct shared-component reuse.** Home Workspace Details and Recent Activity pass `mobileSnap`; the existing Compact/Medium/Expanded controller, grip pointer handling, keyboard equivalents, visual-viewport safeguards and internal scrolling remain authoritative. This is not a new Home snap engine. | Home-only opt-in in `src/lite/LiteHome.jsx`; focused Home tests, stories, visual references and Android qualifier assertions added. Shared controller/CSS/overlay implementation unchanged. |

> Shared component changes: **None** to `useMobileSheetSnap.js`, `mobileSheetSnap.css`, `LiteSheet`, `LiteDetailsPanel`, tokens, API, query, geometry or portal code. Home-specific `LiteHome.jsx` now opts both applicable details panels into the PR #634 shared controller; `scripts/dev/lite/qualify-ui-performance-android-cdp.mjs` adds narrow Home snap assertions to the existing Home-only runner. A wider shared-settings extraction was not introduced.

## Qualification inventory — executed

- Unit/component: `src/lite/LiteHomeScreen.test.jsx` (hero/four destinations, conditional attention, grouped section/Back, saved/offline/unknown/partial/running). Existing `LiteHomeAzure.test.jsx` and `HomeActivityDetails*.test.jsx` remain part of the candidate suite.
- Storybook: `src/lite/LiteHome.stories.jsx`, with Command variants for healthy/attention/offline/unavailable/loading/partial/running/refresh, both themes/System, large text, grouped index and nested sections, desktop panels, mobile widths, reduced motion, and Workspace Details/Recent Activity Compact, Medium and Expanded snap states.
- Mocked Playwright: `tests/e2e/lite-home-command.spec.ts`, responsive 320–1600, destination navigation, grouped nested/back/close/focus, activity review, 200% type, semantic Axe, stale/offline state handling.
- Snap behavior: `tests/e2e/lite-home-panel-snap.spec.ts` covers both Home detail panels, Medium initial state, Compact/Medium/Expanded transitions, grip drag, keyboard Home/End/PageDown, nested navigation, internal scroll, Back, close/reopen reset and desktop non-activation.
- Visual references: `tests/e2e/lite-home-command-visual.spec.ts` and `tests/e2e/lite-home-panel-premium-visual.spec.ts`. The reviewed PNG references are committed under their existing snapshot directories: 78 Home command PNGs plus 40 canonical grouped-panel PNGs cover approved desktop/mobile, Daylight/Dark, healthy/attention/saved/unavailable states, nested-panel references and the 24 new Home snap-state references. They are deterministic mocked references, not physical-device proof.
- Geometry parity: Light/Dark bounding boxes for hero, header, four cards, recent-activity region and panel navigation; maximum intended difference 1.5 CSS px in the authored mock assertion; resized desktop container fallback.
- Performance: `tests/e2e/lite-home-command-performance.spec.ts` plus the adapted `tests/e2e/lite-home-panel-premium-performance.spec.ts`; existing `expectLitePerformanceBudget` from PR #588 is unchanged. The focused mocked panel suite remains **PARTIAL** because host-side frame/LoAF/React-profiler samples were intermittent; no threshold or assertion was weakened.
- Existing Home E2E candidates: `lite-home-panel-flow-scroll.spec.ts`, `lite-home-panel-premium.spec.ts`, and `lite-azure-horizon*.spec.ts` adapted where relevant to grouped navigation and the new explicit activity action. The adapted flow suite completed 40/40.

## DEV-PC qualification evidence

The focused checks ran on Node `24.16.0` against the application source now committed at `a1827836a63f45884398f32bb002af2017d2445f`; the Android qualifier-only assertions were added in that same commit.

| Command | Result |
|---|---|
| `npm run test:azure:home` | **PASS — 11 tests** |
| `npm run test:azure:home:premium:unit` | **PASS — 45 tests** |
| `npx vitest run src/lib/liteUxPresentation.test.js src/performance/litePerformancePolicy.test.js` | **PASS — 19 tests** |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_ux_maturity_contract.py` | **PASS — 9 tests** |
| `npm run build` | **PASS** — existing large-chunk warnings only |
| `npm run build-storybook` | **PASS** — existing bundle/eval warnings only |
| `npx vitest run src/lite/LiteHomeAzure.test.jsx src/lite/LiteHomeScreen.test.jsx src/lite/components/useMobileSheetSnap.test.jsx` | **PASS — 16 tests**; shared PR #634 controller regression remains covered by 7 existing tests |
| `VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command.spec.ts --project=mocked-desktop --project=mocked-mobile` | **PASS — 36 tests** |
| `VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-panel-snap.spec.ts --project=mocked-desktop --project=mocked-mobile` | **PASS — 8 tests**; all Home snap and desktop opt-out cases passed |
| `VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command-visual.spec.ts --grep 'mobile .*snap reference' --project=mocked-desktop --project=mocked-mobile` | **PASS — 24 tests**, canonical comparison without update flags after visual inspection |
| `VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command-visual.spec.ts --project=mocked-desktop --project=mocked-mobile` | **PARTIAL — 60/62 in the final full run**; two 1%-pixel light mocked-mobile anti-aliasing diffs were isolated and passed three repetitions each; no geometry/content defect found |
| `npm run test:azure:home:premium:mocked` | **PASS — 56 tests** |
| `npm run test:azure:home:flow:mocked` | **PASS — 40 tests** |
| combined Home WCAG/Axe/grouped-panel accessibility command | **PASS — 16 tests**, no serious/critical violations |
| `npm run test:azure:home:premium:visual` | **PASS — 40 tests**, canonical comparison without update flags after reviewed promotion |
| `npm run test:azure:home:premium:perf` | **PARTIAL — 12 interaction tests per run; intermittent host frame/LoAF/React-profiler hard-gate samples; no policy change** |
| `git diff --check` | **PASS** |

One attempted parallel browser launch encountered the repository's shared Vite port contention; the isolated rerun passed and no product failure was attributed to that tooling collision.

## Qualification commands and physical Android evidence

```bash
# Exact-head Home-only physical qualifier; the broad seven-screen matrix was not run.
source /home/dj/.nvm/nvm.sh && nvm use 24.16.0
bash scripts/dev/lite/run-ui-performance-android-candidate.sh --home-only
bash scripts/dev/lite/run-ui-performance-android-candidate.sh --baseline --home-only
```

The current snap candidate `a1827836a63f45884398f32bb002af2017d2445f` built successfully on DEV-PC with the repository candidate identity set to that exact SHA. The local candidate manifest was ready on loopback port `18765`, the repository-owned ADB reverse was created, and the runner began the Home-only path. The established Windows CDP bridge then reset the connection at its recorded bridge port before CDP preflight could attach to Android Chrome. The preflight correctly stopped and required an elevated PowerShell bridge setup; no UAC bypass or repeated consent loop was attempted. No Android page manifest/header/meta proof, browser target proof, Home snap measurement or physical screenshot was recorded for `a1827836`.

The runner cleanup completed: the candidate process and candidate reverse were removed, ADB forward/reverse mappings were zero, and the local CDP listener was unreachable. A pre-existing elevated bridge state/portproxy record remains outside the non-elevated cleanup boundary and was not force-removed. This current PR #634 snap qualification is **BLOCKED** by the external Windows CDP/UAC prerequisite, not reported as Android PASS.

For historical attribution only, the prior PR #638 Home-only run at `a1bb1dc84eb17b5a2b792efd00759147c8f07359` completed 18 safe interaction reports: cold/steady Home, four destination cards, Workspace Details open/sections/technical details/Back/Close, Recent Activity open/sections/Back/Close, and refresh feedback. All 18 missed the unchanged PR #588/#589 absolute target and hard render gate. Its three-repetition normalized result was `MIXED=18`, `APP_INCREMENTAL_COST=0`, `PLATFORM_DOMINATED=0`, `WITHIN_BASELINE=0`, `INCONCLUSIVE=0`, with all 18 absolute target misses. That evidence remains **PARTIAL / MIXED** and is not reused as proof of the new Home snap interactions. The recorded current-main control SHA was `821ad56f83b2af9cf1fd59001364daf3545cc408`; no clean current-main application A/B entry point exists in the established runner.

**Physical Android and protected consumer:** no production PWA was installed, no Caddy/API/NATS/PM2 service was restarted, and the Server Phone checkout remained read-only on `main` at `821ad56f83b2af9cf1fd59001364daf3545cc408`. Android snap behavior is **BLOCKED**, while DEV-PC snap behavior is **VALIDATED** below.

### Acceptance criteria

- Every intended responsive size works without horizontal overflow or clipped controls, including 320px, 200% text and a 380px resized desktop panel.
- Daylight/Dark/System retain identical geometry with expected semantic color differences.
- State facts are backend-truthful; no live ready or running claims from stale/unknown source.
- Compact/Medium/Expanded, grip drag, keyboard resize, Escape/Backdrop/Back and focus restores work in both panels in the mocked mobile browser; current physical Android snap behavior remains **BLOCKED** by the external CDP/UAC bridge prerequisite.
- Grouped-settings navigation, nested history, internal scrolling and server-confirmed mark-reviewed action remain intact.
- Accessibility has zero serious/critical violations in Home and both panels.
- Existing PR #588 performance thresholds remain unchanged; report actual measured results and relative attribution.
- Current source and generated docs/contracts gates were evaluated after the Home source, visual references and Android bridge attempt were evidence-classified.
- No unauthorized runtime, API, backend, app, security, device or release change.

## Gate register

| Gate | Status | Explanation |
|---|---|---|
| Unit / component tests | **VERIFIED** | 16 focused Home/snap tests and 45 premium unit tests passed |
| Storybook build, interactions | **VALIDATED** | Production Storybook build passed; source stories cover Home states and panels |
| Playwright mocked | **VALIDATED** | Command, flow and premium mocked suites passed |
| Visual regression / screenshot comparison | **PARTIAL** | 24 new snap-state comparisons passed and 78 Home command PNGs plus 40 premium PNGs were reviewed/committed; one full 62-case run had two isolated 1%-pixel anti-aliasing residuals that passed three repetitions each |
| Accessibility / 200% text | **VALIDATED** | Focused Home premium mocked suite passed serious/critical Axe, focus, 200% and reduced-motion checks |
| Light / Dark geometry parity | **VALIDATED** | Reviewed Daylight/Dark geometry across desktop/mobile references |
| Performance / PR #588 hard gates | **PARTIAL** | Physical Home reports missed the absolute target; 3-run attribution is MIXED=18. Mocked panel performance also has intermittent host-side hard-gate samples; thresholds remain unchanged. |
| DEV-PC build / lint / git checks | **VALIDATED** | Build, Storybook, focused checks and `git diff --check` passed; no repo ESLint gate was claimed |
| Physical Android / Server Phone | **BLOCKED / PARTIAL** | Current `a1827836` Home snap run stopped before CDP attachment at the Windows bridge/UAC prerequisite; historical `a1bb1dc8` physical Home evidence remains PARTIAL/MIXED; Server Phone read-only integrity preserved |
| GitHub Actions | **VALIDATED** | PR #638 checks `isolated-devpc-qualification`, `ui-performance-qualification` and `quick-and-docs` are successful at `a1827836`; no merge or deployment action was taken |
| Release / deploy / merge | **PROHIBITED** | No merge or production changes |

## Final canonical documentation and repository gates

These late-phase gates are run only after the Home source and reviewed visual references are stable, and after the physical Android attempt is either complete or evidence-classified. The current Android attempt is explicitly **BLOCKED** at the external bridge prerequisite. Generated outputs are regenerated from their canonical sources; no generated file is manually edited.

| Command | Result | Evidence / limitation |
|---|---|---|
| `task lite:docs:generate` | **PASS** | Completed at `a1827836`; canonical contracts, platform/runtime projections, architecture, enterprise/intelligence, development/production docs and Codebase Map projections were regenerated. |
| `task lite:docs:check` | **PASS** | Completed at the generated final head; contract/docs/platform/runtime/parity/knowledge/intelligence/enterprise/architecture/SchemaSpy/backend-doc/MkDocs checks passed. Redocly reported 90 existing warnings and no validation errors. |
| `task lite:check` | **PASS** | Completed at `a1827836`; all 20/20 recorded full-gate commands passed, including backend, frontend unit, build, Storybook, mocked E2E, accessibility, docs browser, redaction and strict docs. |
| `npm run check:render-budgets` | **PARTIAL** | The repository evidence checker preserves the physical Android absolute frame-budget miss: 18 reports, 17 hard-gate failures and 18 target misses in the retained Home-only baseline evidence. No threshold or evidence was weakened. |

The prior PR #638 broad gate at `a1bb1dc8` completed 20/20 recorded gates with zero failures after grouped-settings contract corrections. The current snap-integration head `a1827836` independently completed the same 20/20 full gate after final documentation regeneration.

## Risks, reviewer work and rollback

1. The current Android snap qualification is **BLOCKED** by the Windows CDP/UAC bridge prerequisite; no physical Android snap result is claimed.
2. Historical Android evidence at `a1bb1dc8` remains **PARTIAL / MIXED** because its physical control and Home interactions missed the absolute PR #588/#589 frame budget; no clean main application A/B result is available.
3. The reviewed PNG references are deterministic mocked showcase/reference images. They are not physical-device screenshot evidence.
4. The pre-existing elevated bridge state was not force-removed after the non-elevated attempt; the precise cleanup boundary is recorded in the session report.
5. The generated-doc and broad repository gates passed at the final documented head; their evidence does not override the separately blocked physical Android snap run.
6. The design has no new browser authority; panel navigation and animation do not alter the FastAPI/NATS/worker trust boundary.

**Rollback:** As this is an unmerged draft branch, close the PR or revert only the feature commits after review. Do not reset `main`, force-push shared branches, change production services, or remove existing server state as a UI rollback.

**Merge restriction:** **DRAFT PR — DEV-PC snap behavior and reviewed mocked visual references validated; physical Android snap qualification is BLOCKED at the external bridge prerequisite; historical Android performance remains PARTIAL / MIXED. NOT APPROVED FOR MERGE, SQUASH, RELEASE, OR DEPLOYMENT.**
