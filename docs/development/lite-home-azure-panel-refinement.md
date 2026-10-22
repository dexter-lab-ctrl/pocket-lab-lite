# Azure Horizon — Home Workspace and Recent Activity panel refinement

> **IMPLEMENTATION PROVIDED — VALIDATION DEFERRED BY USER INSTRUCTION.**
>
> Source branch: `fix/azure-home-panel-premium-refinement`  
> Exact source base: `0ee498bd8f9f22ca7d670bcefa7a814e683cf02a` on `main`  
> Implementation scope: P0 theme/layout/scroll navigation and P1 Activity presentation, responsive geometry, accessibility and authored regression coverage.  
> **No tests, builds, browser exercises, visual baselines, accessibility tools, performance samplers, documentation generators, CI investigations or Server Phone qualification were executed.**
>
> This is a source implementation record, not proof that any behavior passes qualification. The PR remains **DRAFT / NOT MERGED** pending a separate exact-head qualification session.

## 1. Design objective and baseline defects

The Azure Horizon Home page's Workspace details and Recent activity overlays reused the shared Lite overlay but did not receive complete scoped information design. The pre-existing Home-specific CSS used negative margins on Workspace navigation, while only Workspace implemented scroll-direction hiding. Recent activity had raw explanatory paragraphs, unthemed timeline structures, less differentiated absent/error/review states, and fixed-time wording inconsistent with backend-reported values. Legacy portal-theme compatibility classes required observation of a live System-mode appearance change while a panel stayed open.

The refinement changes **presentation and UI-only interaction**. It does not alter operational execution, approvals, health projections, cached authoritative state, event retention, lifecycle classification or security boundaries.

## 2. Exact component ownership and reuse

| Original owner/source | Existing capability | Home integration in this branch |
|---|---|---|
| PR [#606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606): `src/lite/LiteOverlay.jsx` | `LiteSheet`, `LiteDetailsPanel`, portal, backdrop, Escape stack, focus trap/return and scroll locking | Home-specific `variant="home"` is a small extension; the same dialog primitive remains authoritative |
| PR #606: `src/lite/LiteUi.jsx` | `LiteActionRow`, `LiteOperationalStory`, `LiteRefreshButton` | Workspace cards, status/health context and Home first paint remain on these primitives |
| PR #606: `src/components/ui.jsx` | `GlassCard`, `StateSurface` | Unchanged overview tiles and semantic Activity missing/empty/error UI |
| PR [#622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622): `src/lite/theme/azureHorizonTokens.css` | `--azure-*` semantic Light/Black palette | Home panel backgrounds, surfaces, focus, text, border, disabled, warning and activity controls |
| PR #622: `LiteThemeProvider.jsx` and `liteThemeRuntime.js` | `light`, `dark`, `system` preference and root `html[data-lite-theme]` | No new theme engine or browser-held operational data; Home portal compatibility classes now track the resolved root |
| PR [#623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623): `src/lite/components/useDesktopManageGeometry.js` | Transient move/resize, viewport clamp, keyboard arrows, Shift increments and Home reset | Both Home panels call the hook directly; `LiteDetailsPanel` accepts an optional `desktopGeometry` |
| PR [#624](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/624) | Accessible panel toolbar, focus, escape and responsive interaction patterns | Home uses explicit Move/Resize/Reset controls and retains the shared dialog focus boundary |
| PR [#625](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/625) | Premium Rules panel's scoped dark-theme/desktop geometry treatment | Home CSS is separate, semantic and does not modify Rules, Identity or the Apps panel presentation |
| PR [#588](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/588) and [#589](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/589) | Existing UI timing budget and physical Android performance qualification guidance | Authored `measureLiteInteraction` cases with unmodified PR #588 checks; no measured performance is claimed |

**No copy of the geometry hook, new overlay engine or duplicate theme system has been added.** The only shared-geometry edit is a harmless media-query fallback in environments without `window.matchMedia`. Shared `LiteDetailsPanel` only shows the move/resize toolbar when an optional geometry adapter is passed **and** the viewport qualifies as desktop.

## 3. Authoritative Home data path

```text
React/Vite Home
  -> Caddy same-origin
  -> FastAPI /api/lite/status and prepared activity summaries
     -> /api/lite/system/activity-summary (safe bounded first-paint read)
     -> /api/lite/home/activity-history (lazy, when Activity opens)
     -> /api/lite/home/activity-cursor (read) and /api/lite/home/activity-cursor/review (explicit backend-owned review action)
  -> TanStack Query / safe read-only snapshots where applicable
  -> sanitized presenter only
```

All action execution continues to flow through FastAPI → NATS/JetStream → worker/agent/supervisor → sanitized events/audit → FastAPI → UI.

Home never executes shell commands, connects to NATS, stores server secrets, creates server history or clears audit records. Its Personal activity review does not approve work, acknowledge an incident or fix failed actions. Activity label/domain/status and count allowlists remain in `src/lite/homeActivityEvidence.js`. Failed historical events are explicitly not automatically classified as active unresolved incidents. An unavailable value is not zero; stale operations are not confirmed running.

## 4. Home component tree

```text
HomeScreen (src/lite/LiteHome.jsx)
 ├─ LiteOperationalStory / LiteFreshness / HomeOverviewGrid / HomeActivityPreview
 ├─ Workspace details — LiteDetailsPanel variant="home"
 │    ├─ useDesktopManageGeometry(open, defaultWidth 660, minWidth 380)
 │    ├─ useLitePanelSectionNavigation(open)
 │    ├─ Overview -> LiteActionRow
 │    ├─ Service health -> HomeWorkspaceFlow / LiteActionRow
 │    ├─ Updates -> LiteReleaseUpdateCard
 │    └─ Diagnostics -> LiteTechnicalFacts
 └─ Recent activity — LiteDetailsPanel variant="home"
      ├─ independent useDesktopManageGeometry / useLitePanelSectionNavigation
      └─ HomeActivityDetails
           ├─ Attention | Running | Recent | History
           ├─ 2x2 KPI cards
           ├─ ActivityNotice (time window, attention classification, stale, history)
           ├─ ActivityEvents timeline / StateSurface empty
           └─ Personal activity review / StateSurface error-unavailable
```

Home-specific styling is centralized in `src/lite/components/homePanelRefinement.css` imported **after** the existing `homePremium.css`, `azureHome.css` and `homeActivityEvidence.css`. Tokens are owned by `azureHorizonTokens.css`, and generic overlay positioning remains with `azureHorizon.css`. Existing history projection ownership is unchanged.

## 5. P0-A — Daylight, Black and System appearance contract

| Role | Daylight | Black | Token |
|---|---|---|---|
| Canvas | #F4F9FF | #050607 | `--azure-canvas` |
| Panel surface | #FFFFFF | #0B0F14 | `--azure-surface` |
| Raised card | #E7F2FF | #121822 | `--azure-raised` |
| Border | #D5E5F8 | #1F2A36 | `--azure-border` |
| Heading/body | #142841 | #E6EDF7 | `--azure-text` |
| Supporting copy | #5B7088 | #A4B3C4 | `--azure-muted` |
| Active blue | #006BC7 | #4AA8FF | `--azure-accent` |

Scoped selectors begin with `html[data-lite-theme] .lite-home-panel-layer`. Both panels explicitly style their surface, heading, scroll background, navigation, active/inactive tabs, data cards, informative and warning cards, timeline, events, empty/error states, personal review, buttons, disabled states, scrollbar, grip, focus and shadows using these tokens. No fixed white background or broad global `!important` rule was introduced.

The existing `LiteSheet` portal's legacy compatibility class now listens to the resolved `html[data-lite-theme]` with a `MutationObserver`. This allows a System OS dark/light preference change to update an **already open** panel without remounting content or changing selected tabs. A following session must confirm that all inherited legacy rules resolve as intended in the browser.

## 6. P0-B — Explicit tab and card separation

Existing `homePremium.css` and `azureHome.css` Workspace tabs formerly used negative top/horizontal margins. The Home branch removes those negative margins and provides explicit panel scroll padding, `gap`, a container-bound navigation border and `lite-home-workspace-section` card separation. The first Workspace card follows the navigation in the normal grid flow. Status/action areas wrap when constrained.

At 320–430px, two-column tab layout and stacked card/row actions are governed by a **panel container query**, not a false full-window width assumption.

## 7. P0-C — Unified Workspace and Activity scroll navigation

The independent UI-only `useLitePanelSectionNavigation` hook binds passive scroll + focus listeners to the actual panel scroll element. It avoids global window scroll listeners and never reads backend state. Model:

| Condition | Expected UI-only outcome |
|---|---|
| At top (<= 8px) | Tabs revealed; scrolled styling cleared |
| Scrolling down after accumulated 14px | Tabs retract |
| Scrolling up after accumulated 14px | Tabs reveal |
| Subthreshold jitter | Maintain current state |
| Focus inside navigation | Tabs reveal; keyboard users keep access |
| Tab selected | Keep tabs visible; reset that panel body's scroll to top |
| Overlay closed/unmounted | Listener cleanup and UI state reset |

The two panels have separate hook instances and independent scroll refs. `prefers-reduced-motion: reduce` disables the tab motion. During qualification, observe retraction, sticky-content occupation and focus across real touch and keyboard devices.

## 8. P1 — Activity semantic surfaces and timeline

The new `HomeActivityDetails` uses semantic explanatory cards rather than loose paragraphs: bounded running/waiting window, historical window, old unfinished records, backend-specific attention classification, historical failure explanation and personal review. `running_window_minutes` and `history_window_days` are rendered only as safe positive integers reported by FastAPI; missing fields show 'not reported', never an invented interval.

Counters display `Not available` for absent values, preserve exact large integers with tabular numerals, and retain backend classification. Ordered event rows show safe allowlisted labels/statuses, formatted timestamps, and explicit destination buttons. Invalid timestamps receive a visible fallback. An empty list uses the shared `StateSurface` with bounded-sample wording; unavailable activity and review errors use explicit unavailable/error `StateSurface` blocks. A personal review action is disabled for saved/offline/busy state and invokes the existing explicit FastAPI request handler only.

## 9. P1 — Geometry, mobile responsiveness, accessibility and performance

At width >=701px, both Home dialogs reuse `useDesktopManageGeometry` for ephemeral panel position/size (default 660px), bounded to the viewport and recalculated on resize. The existing pointer implementation supports drag/resize; keyboard arrow keys move/resize by 16px, Shift+arrow by 64px and Home/reset restores defaults. Explicit labelled 44px controls are supplied only on desktop. No geometry is persisted to Dexie/localStorage.

Under 701px, no desktop move/resize toolbar is rendered. The shared `LiteSheet` stays a bottom sheet with safe-area bottom padding, touch-usable buttons and bounded body scrolling. Container-query breakpoints adapt the tab grid, timeline and action rows **to panel width**. Tested width **definitions only**: 320/360/375/390/430/768/1024/1440, 200% font scale, reduced motion and resized window. No verified outcome is claimed.

Inherited `LiteSheet` semantics: `role="dialog"`, `aria-modal`, title label, Escape stack, focus trap, focus return, backdrop close and body scroll locking. Home adds focus-visible outlines, semantic notices, explicit button names, `aria-current="page"` for section selection and keyboard panel-tool handlers.

No performance contract changes were made. Tests are designed to use PR #588's existing sampler, budget assertion and report writer, and still need real device measurements for CPU/thermal/memory/smoothness.

## 10. Authored-only regression inventory

| Category | Repository source | Intention — NOT EXECUTED |
|---|---|---|
| UI navigation state/hook | `src/lite/hooks/useLitePanelSectionNavigation.test.jsx` | Threshold, direction, focus, scroll cleanup |
| Activity component | `src/lite/components/HomeActivityDetailsPremium.test.jsx` | KPIs, window, timeline, errors, empty, private review |
| Activity sanitization | `src/lite/homeActivityEvidence.test.js` | Authority, large numbers, malformed input, dynamic safe time windows |
| Existing Home unit/component | `src/lite/LiteHomeScreen.test.jsx`, `src/lite/LiteHomeAzure.test.jsx` | Existing backward compatibility gates |
| Shared desktop geometry | `src/lite/catalog/useDesktopManageGeometry.test.jsx` | Existing move/resize/clamp/keyboard hook regressions |
| Storybook | `src/lite/LiteHome.stories.jsx` | Daylight/Black/System, desktop/mobile, Activity sections, empty/saved/unavailable, long text, motion, moved/resized |
| Playwright mocked/Axe | `tests/e2e/lite-home-panel-premium.spec.ts` | Responsive themes, 320–1440 widths, 200% text, keyboard, bounds, focus, semantic dark styling |
| Visual definitions | `tests/e2e/lite-home-panel-premium-visual.spec.ts` | New screenshot names for panel/theme/state/width; **NO PNG generated** |
| Performance definitions | `tests/e2e/lite-home-panel-premium-performance.spec.ts` | Home open/close, tabs, scroll, theme/geometry with unchanged PR #588 thresholds |
| Qualification task integration | `package.json`, `tasks/Taskfile.ui.yml` | Four Home-specific unit/mock/visual/performance entry points |

No new backend endpoints, NATS subjects, operations, authz policies, manifest entries or dependencies were added.

## 11. Follow-on Dev-PC qualification — commands to EXECUTE LATER, not now

Resolve the future PR's exact HEAD and run these on a properly provisioned Windows/WSL2 or Linux development environment, with expected build dependencies and isolated mocks. Inspect current task names before execution.

```bash
git fetch origin
git switch --track origin/fix/azure-home-panel-premium-refinement
npm run test:azure:home:premium:unit
npm run test:azure:home:premium:mocked
npm run test:azure:home:premium:perf
npm run test:azure:storybook
npm run test:azure:home
npm run test:azure:a11y
npm run test:a11y:states
npm run test:e2e:mocked
npm run test:perf:components
npm run test:perf:mocked
npm run build
npm run build:budget
task lite:docs:generate
task lite:docs:check
task lite:check
```

After **explicit owner approval of newly captured images**, run `npm run test:azure:home:premium:visual` and compare baseline changes to the merged PR #622/Home canonical snapshots. Do not silently update existing visuals. Review genuine contrast ratios and AXE WCAG A/AA violations for Light/Black/System, narrow devices and PWA. Independently review System open-panel theme changes and focus-return.

For Android CDP, use the existing PR #588/#589 local candidate workflow: exact HEAD, loopback-only Vite and same-origin safe API, ADB reverse/forward, transport gates, permissioned synthetic-owner harness only if read access needs it, candidate identification evidence, CPU/long task/LoAF/frame sampling, capture/readability and reset/cleanup. Do not deploy candidate to production Phone or submit destructive operations merely to qualify Home.

Only after the Dev-PC build/tests/visual approvals/docs and isolated Android qualification should an operator investigate automatically triggered exact-head CI, record its provenance, assess residual performance target misses, and decide whether the PR is mergeable.

## 12. Known unvalidated risks and recovery

- Complex legacy `index.css` selectors may still override a Home descendant despite the scoped tokens. Inspect computed styles and screenshots; do not globally suppress selectors with `!important`.
- `LiteSheet`'s legacy portal theme class observation is shared and must be smoke-tested in existing Apps/Devices/Identity/Security/Rules/Recovery overlays during System appearance changes.
- Desktop CSS absolute positioning and `useDesktopManageGeometry` width clamp need direct testing at the 701px threshold, 200% text, viewport resize and reduced-height mobile keyboards.
- The new scroll nav uses transform/opacity while retaining sticky layout context; visually qualify tab-card spacing, click/focus reachability and nested scroll.
- New snapshot names require approved baseline capture and cannot be interpreted as passing.
- Storybook fixture availability for specific unavailable/empty cases must be verified; no mocked backend behavior is invented by the component.
- Unit/component, lint/typecheck, Playwright, Axe, performance and docs source compilation remain **unvalidated**.
- Physical Android Termux/ARM64, installed PWA/Safari, remote Tailnet, server phone processes and real per-user history are not tested in this implementation session.

Rollback is a feature-branch revert of the affected commits (never force-reset `main`); the existing merged Home panels remain available in `main` until explicit authorization and qualification. Do not strip safe state or audit evidence to restore a display.

**Merge disposition: OPEN — DRAFT — NOT MERGED — NOT AUTHORIZED FOR MERGE.**
