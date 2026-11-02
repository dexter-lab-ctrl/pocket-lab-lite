# Azure Horizon Command Home — implementation provenance and qualification

> **Status: VALIDATED / PARTIAL.** This addendum records the exact-head DEV-PC, mocked browser, accessibility, visual-reference and physical Android Home-only qualification performed on `feat/azure-horizon-home-native-revamp`. The absolute Android frame budget remains a truthful gate miss with mixed baseline attribution. The PR remains **OPEN — DRAFT — NOT MERGED**.

## Objective and exact baseline

- Repository: `dexter-lab-ctrl/pocket-lab-lite`
- Resolved authoritative `main`: `821ad56f83b2af9cf1fd59001364daf3545cc408`, after merged PR #637.
- Feature branch: `feat/azure-horizon-home-native-revamp`; draft PR targets `main`.
- Initial PR head observed: `c0a1aabc7f905d37216254e2dae9074e61dd0211`.
- Exact qualified candidate before this documentation update: `a1bb1dc84eb17b5a2b792efd00759147c8f07359`.
- Target: responsive desktop browsers, mobile browsers and installed Android PWA.
- Scope: Home screen composition, Home-only grouped navigation, shared `LiteFreshness` reuse, source tests, Storybook, mocked browser and visual/performance candidates.
- Exclusions: backend schema, authorization, NATS/JetStream, Devices/Apps/Rules/Security/Recovery screens, production Server Phone, release and deployment.

## P0–P3 authored source map

| Requirement | Authored implementation | Qualification |
|---|---|---|
| P0: Native header, hero, four destinations | `src/lite/LiteHome.jsx` `HomeHealthHero`, `homeCommandHeroPresentation`, `HomeOverviewGrid` | **VERIFIED** — focused unit, mocked browser, geometry and reviewed visual references |
| P0: Status truthfulness | Prepared `buildLiteHomeOverview` unchanged; saved/reachability, stale projection, unknown and running signals drive explicit states; the hero now uses the shared `LiteFreshness` primitive | **VERIFIED** — state matrix, shared UX contract and mocked browser coverage |
| P0: Attention and recent activity | Existing `prioritizeWorkspaceAttention`, `selectHomeActivityEvidence` and FastAPI-backed activity query | **VERIFIED** — activity/attention browser and unit coverage |
| P1: Native grouped settings | `src/lite/components/HomeGroupedSections.jsx` reused by both Home panels | **VALIDATED** — desktop/mobile flow, Back, Escape, focus return and physical Home interaction sequence |
| P1: Mobile and desktop | `src/lite/components/homeCommand.css` two-column cards on narrow mobile, four on desktop; `@container home-panel` changes details from mobile index/nested to two-column desktop | **VALIDATED** — 320/360/375/390/430/768/1024/1280/1440 mocked geometry and reviewed references |
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

> Shared component changes: **None** outside Home-specific `HomeActivityDetails.jsx`. Existing token, API, query, geometry, portal and common screen code has not been rewritten. A wider shared-settings extraction could be considered only after targeted qualification demonstrates identical needs.

## Qualification inventory — executed

- Unit/component: `src/lite/LiteHomeScreen.test.jsx` (hero/four destinations, conditional attention, grouped section/Back, saved/offline/unknown/partial/running). Existing `LiteHomeAzure.test.jsx` and `HomeActivityDetails*.test.jsx` remain part of the candidate suite.
- Storybook: `src/lite/LiteHome.stories.jsx`, with Command variants for healthy/attention/offline/unavailable/loading/partial/running/refresh, both themes/System, large text, grouped index and nested sections, desktop panels, mobile widths and reduced motion.
- Mocked Playwright: `tests/e2e/lite-home-command.spec.ts`, responsive 320–1600, destination navigation, grouped nested/back/close/focus, activity review, 200% type, semantic Axe, stale/offline state handling.
- Visual references: `tests/e2e/lite-home-command-visual.spec.ts` and `tests/e2e/lite-home-panel-premium-visual.spec.ts`. The reviewed PNG references are committed under their existing snapshot directories: 54 Home command PNGs plus 40 canonical grouped-panel PNGs cover approved desktop/mobile, Daylight/Dark, healthy/attention/saved/unavailable states and nested-panel references. They are deterministic mocked references, not physical-device proof.
- Geometry parity: Light/Dark bounding boxes for hero, header, four cards, recent-activity region and panel navigation; maximum intended difference 1.5 CSS px in the authored mock assertion; resized desktop container fallback.
- Performance: `tests/e2e/lite-home-command-performance.spec.ts` plus the adapted `tests/e2e/lite-home-panel-premium-performance.spec.ts`; existing `expectLitePerformanceBudget` from PR #588 is unchanged. The focused mocked panel suite remains **PARTIAL** because host-side frame/LoAF/React-profiler samples were intermittent; no threshold or assertion was weakened.
- Existing Home E2E candidates: `lite-home-panel-flow-scroll.spec.ts`, `lite-home-panel-premium.spec.ts`, and `lite-azure-horizon*.spec.ts` adapted where relevant to grouped navigation and the new explicit activity action. The adapted flow suite completed 40/40.

## DEV-PC qualification evidence

The focused checks ran on Node `24.16.0` at the exact committed application source `a1bb1dc84eb17b5a2b792efd00759147c8f07359`.

| Command | Result |
|---|---|
| `npm run test:azure:home` | **PASS — 11 tests** |
| `npm run test:azure:home:premium:unit` | **PASS — 45 tests** |
| `npx vitest run src/lib/liteUxPresentation.test.js src/performance/litePerformancePolicy.test.js` | **PASS — 19 tests** |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_ux_maturity_contract.py` | **PASS — 9 tests** |
| `npm run build` | **PASS** — existing large-chunk warnings only |
| `npm run build-storybook` | **PASS** — existing bundle/eval warnings only |
| `VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command.spec.ts --project=mocked-desktop --project=mocked-mobile` | **PASS — 36 tests** |
| `VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command-visual.spec.ts --project=mocked-desktop --project=mocked-mobile` | **PASS — 38 tests**, canonical comparison without update flags after reviewed promotion |
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

The repository-owned bridge selected Windows `C:\Android\platform-tools\adb.exe` version `37.0.1-15733141`, attached Android Chrome `156.0.8078.75` via CDP `1.3`, served the exact candidate on DEV-PC loopback port `18765`, and verified candidate manifest, response header and page metadata against `a1bb1dc84eb17b5a2b792efd00759147c8f07359`. The physical Home smoke and foreground animation-frame preflight passed. The sanitized Android state samples reported Android 16, screen on, battery saver off, thermal status 0 and battery 94–95%; the focus parser did not expose a foreground package, so this is retained as sanitized runtime context rather than foreground identity proof.

The Home-only qualifier completed all 18 safe interaction reports: cold/steady Home, four destination cards, Workspace Details open/sections/technical details/Back/Close, Recent Activity open/sections/Back/Close, and refresh feedback. All 18 missed the unchanged PR #588/#589 absolute target and hard render gate. The exact report set is under `.pocketlab-dev/performance/` locally and is not a tracked secret-bearing artifact.

The three-repetition baseline-normalized run completed all 18 reports per repetition on the same device, browser and transport. The static control itself missed the absolute target (`p50` about 41.7 ms, `p95` about 41.8 ms, smooth ratio 0.14, severe ratio 0.86). Normalized results were `MIXED=18`, `APP_INCREMENTAL_COST=0`, `PLATFORM_DOMINATED=0`, `WITHIN_BASELINE=0`, `INCONCLUSIVE=0`; all 18 missed the production target, with one normalized report meeting the hard gate. This is **PARTIAL / MIXED**, not a performance PASS and not proof of a clean Home-only no-regression result. No threshold, stop condition or baseline policy was changed, and no unrelated screen was optimized.

The corresponding current-main source control recorded for this qualification is `821ad56f83b2af9cf1fd59001364daf3545cc408`. The repository-supported PR #588/#589 runner uses the contemporaneous exact-SHA static control page for normalized attribution; no separate main application A/B build was introduced because that entry point is not part of the established Home-only runner. A clean current-main application A/B comparison is therefore **UNVALIDATED**, while the approved platform-control comparison above remains the executed attribution evidence.

**Physical Android:** candidate qualification was performed without installing a production PWA, changing production Caddy, restarting the Server Phone or mutating the protected runtime. The absolute misses and mixed attribution remain visible.

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
| Unit / component tests | **VERIFIED** | 11 focused Home tests and 45 premium unit tests passed |
| Storybook build, interactions | **VALIDATED** | Production Storybook build passed; source stories cover Home states and panels |
| Playwright mocked | **VALIDATED** | Command, flow and premium mocked suites passed |
| Visual regression / screenshot comparison | **VALIDATED** | 38 Home command and 40 premium panel canonical visual tests passed; 94 PNG references reviewed and committed |
| Accessibility / 200% text | **VALIDATED** | Focused Home premium mocked suite passed serious/critical Axe, focus, 200% and reduced-motion checks |
| Light / Dark geometry parity | **VALIDATED** | Reviewed Daylight/Dark geometry across desktop/mobile references |
| Performance / PR #588 hard gates | **PARTIAL** | Physical Home reports missed the absolute target; 3-run attribution is MIXED=18. Mocked panel performance also has intermittent host-side hard-gate samples; thresholds remain unchanged. |
| DEV-PC build / lint / git checks | **VALIDATED** | Build, Storybook, focused checks and `git diff --check` passed; no repo ESLint gate was claimed |
| Physical Android / Server Phone | **PARTIAL** | Exact candidate and Home interactions reached; physical absolute performance remains a gate miss; Server Phone read-only integrity preserved |
| GitHub Actions | **UNVALIDATED** | Fresh checks are recorded after the feature branch is pushed; old remote-head checks are not reused as final proof |
| Release / deploy / merge | **PROHIBITED** | No merge or production changes |

## Final canonical documentation and repository gates

These late-phase gates were run only after the Home source, reviewed visual references and physical Home-only Android qualification were stable. Generated outputs were regenerated from their canonical sources; no generated file was manually edited.

| Command | Result | Evidence / limitation |
|---|---|---|
| `task lite:docs:generate` | **PASS** | Deterministic generation completed: Lite contracts/fixtures, platform/runtime projections, architecture, enterprise, intelligence, development/production docs, diagrams and final Codebase Map projections were regenerated. |
| `task lite:docs:check` | **PASS** | OpenAPI/Redocly validation and all documentation, contract, architecture, knowledge, diagram, backend-doc and runtime-network checks passed. Redocly reported 90 pre-existing warnings; no validation errors. |
| `task lite:check` | **PASS** | Final broad gate completed with 20/20 recorded gates passed and zero failures after the Home mocked-contract selectors were updated for the grouped-settings implementation and safe-read nonce. |
| `npm run check:render-budgets` | **PARTIAL** | The repository evidence checker preserves the physical Android absolute frame-budget miss: 18 reports, 17 hard-gate failures and 18 target misses in the retained Home-only baseline evidence. No threshold or evidence was weakened. |

The broad gate's first post-generation pass exposed stale tests that still expected the pre-revamp floating tab strip, the old `View activity` label and the removed operational-story wrapper. Those expectations were corrected to the current grouped-settings/navigation and guidance contracts; the affected desktop/mobile scenarios then passed 6/6 and the complete mocked contract path passed 52 tests with 10 intentional skips.

## Risks, reviewer work and rollback

1. The Android absolute render budget remains **PARTIAL / FAIL**: the physical control was already below budget and Home interactions added variable deltas. No clean main application A/B result is available from the established Home-only runner.
2. The reviewed PNG references are deterministic mocked showcase/reference images. They are not physical-device screenshot evidence.
3. The physical Android state parser did not expose a foreground package even though Chrome activity was foreground during bounded diagnostics; this is retained as a provenance limitation rather than silently promoted.
4. The generated-doc and broad repository gates are intentionally late-phase tasks and are recorded at the final documentation head below.
5. The design has no new browser authority; panel navigation and animation do not alter the FastAPI/NATS/worker trust boundary.

**Rollback:** As this is an unmerged draft branch, close the PR or revert only the feature commits after review. Do not reset `main`, force-push shared branches, change production services, or remove existing server state as a UI rollback.

**Merge restriction:** **DRAFT PR — DEV-PC and visual evidence validated; physical Android performance remains PARTIAL / MIXED. NOT APPROVED FOR MERGE, SQUASH, RELEASE, OR DEPLOYMENT.**
