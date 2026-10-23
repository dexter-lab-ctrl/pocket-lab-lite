# Home panel flow and scroll stabilization (P0/P1)

> [!IMPORTANT]
> **SOURCE IMPLEMENTED — UNVALIDATED.** Feature: `fix/home-panel-flow-scroll-stabilization`; base `main` at `3cf451f29e93277083d2f6e197a54fcbf8639b2d`. The session was implementation-only: **no tests, builds, screenshots, visual approvals, performance measurements, Android CDP, CI investigation or generated-documentation commands were executed**. Preserve this qualification boundary in any release or PR summary.

## Scope and original defects

The Workspace Details / Recent Activity dialogs retained several issues after #626: the Workspace Status Flow was mostly unstyled in Black mode; scroll-direction navigation sometimes remained visible while a touched tab retained focus; translated sticky bars left unused layout space; narrow desktop and mobile panels showed inconsistent spacing and alignment. This change is focused on Home panel source and automated qualification definitions, not a redesign or a change to backend truth.

### Source-level causes

1. The workflow styling in `src/index.css` (legacy Home premium section) is scoped to `.theme-pocket-lite-daylight .lite-home-workflow*`, including node icons, connectors and the mobile vertical layout. Its dark portal has `.theme-pocket-lite-dark`, so the corresponding rules do not apply there. The prior light-specific selectors also used hardcoded light colors.
2. `src/lite/components/homePanelRefinement.css` had `:focus-within` overriding `data-tabs-hidden`; Android can retain focus after a touch tap, making CSS disagree with JavaScript's scroll-direction decision.
3. `transform:translate3d(...-100%...)` hid the sticky strip visually while preserving its occupied layout height. The visible content and sticky offset could consequently disagree with the actual scroll owner.
4. The existing scroll hook used a single panel-body listener (good), but had no explicit distinction between keyboard focus, incidental pointer focus, and wheel/touch intent.

## Implementation

### P0-A — shared semantic workflow appearance

`HomeWorkspaceFlow` preserves the backend-derived Ready/Review/Saved/Checking presentation. `homePanelRefinement.css` now applies the flow visual hierarchy inside the existing `.lite-home-panel-layer` for both `html[data-lite-theme="light"]` and `html[data-lite-theme="dark"]`, using `--azure-surface`, `--azure-raised`, `--azure-border`, `--azure-strong-border`, `--azure-text`, `--azure-neutral`, `--azure-accent`, `--azure-success`, `--azure-warning` and their established subtle/selected variants. The dark mode does not inherit a light-only workflow background.

The four real product areas retain their existing order: Device → Services → Apps → Safety. The connector spans are visual only and are hidden from assistive technology; the four steps are exposed as a labelled list. No step-level health is invented. The card header, one semantic status badge and a horizontal four-card flow use scoped styling; the existing named `home-panel` container query switches to a vertical connected step list for narrow panel widths. Icons and labels have minimum readable sizes, and motion is restrained, including reduced-motion support.

The legacy Daylight CSS block in `src/index.css` remains present for other historical Home contexts; the targeted overlay rules have greater scope-specific selector priority. It should only be retired in a separate, validated CSS ownership cleanup, rather than replacing an unrelated 26k-line global stylesheet in this PR.

### P0-B/C — single scroll owner, direction and focus modality

Both dialogs pass their own `bodyRef` to `LiteDetailsPanel → LiteSheet`, where `.lite-home-panel-scroll` is the single vertical scroll owner. The shared `useLitePanelSectionNavigation` hook listens only to that mounted body, using passive scroll, wheel, touchstart and pointerdown listeners (plus local keyboard/focus events). No window scroll listeners or Activity-specific algorithm were added.

The navigation has independent states for selected section (`aria-current="page"`), keyboard-focused controls (`data-tabs-keyboard-focused`), hidden status (`data-tabs-hidden`) and meaningful scroll direction. Pointer/touch/wheel intent releases the keyboard lock; a keyboard-focused tab remains visible. `:focus-visible` provides keyboard outlines, while a pointer-focused control is not mistaken for a keyboard-locked strip. The existing 14px hysteresis and 8px top zone are preserved. State setters avoid unnecessary updates when visibility does not change.

On each section change, the real scroll element returns to top and the navigation state resets. Close/reopen initializes the scroll state. Legitimate nested scrolling does not bubble into the body's non-bubbling scroll listener.

### P0-D — collapsed sticky geometry

Navigation remains sticky only while visible. Its hidden state collapses its own block-size, padding and border, rather than translating a layout-bearing bar out of view. This removes the stranded sticky-strip footprint and does not require negative margins or an arbitrary offset. Section changes reset scroll before displaying their new content. The tab buttons remain in DOM so keyboard focus can reveal the strip; an input-modality-aware hook coordinates the reveal. Qualification must inspect the visual transition for layout shifts and keyboard reachability.

### P1-A/B/C — theme, desktop and mobile fit

Azure semantic tokens cover dark/light panel surfaces, cards, warning badges, typography, separators, hover, focus, controls and scrollbars. Flow cards have consistent icon width; Activity counts wrap, and card actions stay aligned or stack with container width. The overlay continues to use CSS container queries, desktop geometry clamping, normal mobile bottom-sheet safe areas and native momentum scrolling. System theme still flows through the existing `LiteSheet` portal class synchronization, not a new theme state. Scrolling cannot escape into the page body during a normal open sheet.

### P1-D — Move / Resize / Reset

Both dialogs already consume `useDesktopManageGeometry` from `src/lite/components/useDesktopManageGeometry.js` through `LiteDetailsPanel`. That hook remains unchanged: desktop-only controls, RAF-coalesced pointer adjustment, Arrow keys, Shift stepping, Home/reset, viewport clamp and resize listeners remain shared. This PR only refines scoped cursor affordances and responsive content. Touch-only mobile keeps the bottom sheet and no desktop geometry controls.

### P1-E/F — accessibility and truthful Activity

Preserved dialog semantics, Escape/focus return, focus trap, keyboard move/resize/reset and minimum 44px controls. Activity counts retain backend-defined time windows and the distinction between active needs-review flags and historical failures. Existing per-person review cursor and permissions remain unchanged; marking reviewed is not represented as resolving an issue.

## Exact component/reference ownership matrix

| Reference | Actual source primitive | Usage here | Modified? | Other consumers / risk |
|---|---|---|---|---|
| #606 | `LiteSheet` / `LiteDetailsPanel` — `src/lite/LiteOverlay.jsx` | Existing portal, focus return/trap, Escape and scroll-body ref | No | All Lite sheet consumers; avoid shared overlay regression |
| #606 | `LiteActionRow`, `LiteOperationalStory` — `src/lite/LiteUi.jsx` | Existing Home service rows and operational story | No | Apps/Devices/other Lite screens |
| #606 | `StateSurface` — `src/components/ui.jsx` | Existing Activity empty/error/unavailable cases | No | Cross-tab state surfaces |
| #622 | Azure semantic tokens defined in `src/index.css`; Home rules in `src/lite/components/azureHome.css` | Daylight/Black/System surfaces and Home hierarchy | Consumed, not changed | Shared theme consumers |
| #623 | `useDesktopManageGeometry` — `src/lite/components/useDesktopManageGeometry.js` | Existing desktop pointer/keyboard move/resize/reset | No | Apps/Devices/Identity/Rules |
| #626 | `useLitePanelSectionNavigation` — `src/lite/hooks/useLitePanelSectionNavigation.js` | Shared Home scroll direction and modality | **Yes**, Home-only hook | Workspace and Activity |
| #626 | `HomeWorkspaceFlow` — `src/lite/LiteHome.jsx` | Semantic state list and node presentation | **Yes**, exported for unit coverage | Workspace Details |
| #588 | `tests/e2e/lite-performance-helpers.ts` and `tests/e2e/lite-home-panel-premium-performance.spec.ts` | Existing UI performance budgets and evidence format | Test extended only | Performance gate unchanged |
| #589 | Physical Android baseline-normalized attribution | Qualification/handoff requirements; do not label platform cost as an app regression | No | Android qualification, not executed |

## Authored coverage (NOT EXECUTED)

| File / task | Authored scope |
|---|---|
| `src/lite/hooks/useLitePanelSectionNavigation.test.jsx` | Direction, jitter, top, keyboard/touch, wheel intent, nested scroll, reopen, passive listener cleanup |
| `src/lite/components/HomeWorkspaceFlow.test.jsx` | All four view states, four semantic steps/three connectors, saved-state truth |
| `tests/e2e/lite-home-panel-flow-scroll.spec.ts` | Actual browser scroll geometry (no synthesized scroll events), immediate after-section touch/wheel path, 390/1280px, light/dark, System changes, keyboard, Axe, Black flow widths 320–430px |
| `tests/e2e/lite-home-panel-flow-visual-candidates.spec.ts` | Candidate states and visible/hidden navigation; **disabled unless explicitly enabled**, no PNG promoted |
| `tests/e2e/lite-home-panel-premium-performance.spec.ts` | Native scroll/theme cost under unchanged budget helper |
| `src/lite/LiteHome.stories.jsx` | Service Health flow across Ready/Review/Saved, mobile, desktop, System, long/text-scale/reduced motion, Activity variants |
| `package.json`; `tasks/Taskfile.lite.yml` | Focused unit, mocked, Axe, visual-candidate and existing performance runners |

The initial #626 screenshot baselines remain untouched. Any unavoidable visual drift is **PENDING HUMAN APPROVAL**, not silently promoted. Storybook also renders an isolated, explicitly simulated Checking presentation contract; it does not start an API refresh or assert that backend work occurred. The unit test instantiates the Checking state directly. A real pending-refresh interaction remains for later qualification.

## Subsequent Dev-PC qualification commands — do not execute in this implementation session

```bash
git fetch origin
git switch fix/home-panel-flow-scroll-stabilization
npm run test:azure:home:flow:unit
npm run test:azure:home:flow:mocked
npm run test:azure:home:flow:a11y
npm run test:azure:home:premium:mocked
npm run test:azure:home:premium:perf
npm run build
npm run test:azure:storybook
# Review old Home canonical diffs; do not blindly overwrite reference images.
npm run test:azure:home:premium:visual
# Only after explicit visual approval, opt into NEW candidate baseline work:
LITE_HOME_VISUAL_CANDIDATES=1 npm run test:azure:home:flow:visual:candidates
# Existing full gates, after focused qualification:
task lite:check
task lite:docs:generate
task lite:docs:check
```

Review desktop widths including resized 380–560px panels, mobile 320/360/375/390/430px on both appearance schemes, System changes with the sheet open, scroll/hysteresis, tab focus, 200% text, RTL/wrapped labels, nested scrolling and visual baselines. Qualify the exact feature SHA on a physical Android Chrome/CDP candidate using the existing PR #589 baseline-normalized approach, never by mutating the Server Phone production instance. Confirm output, commit counts and any CI state only **in the future qualification session**.

## Risks and disposition

- **UNVALIDATED:** collapsing sticky navigation can alter scroll anchoring and produce a small layout shift; test with wheel, touch, inertia, scrollbar and section switching.
- **UNVALIDATED:** pixel-perfect Black contrast, edge padding and narrow desktop reflow require visual and Axe measurements.
- **UNVALIDATED:** the existing and newly authored visual screenshots need deliberate review; current PNGs were not regenerated.
- **UNVALIDATED:** Storybook checking fixture and performance results need real execution before claiming parity.
- **DEFERRED:** generated documentation/contracts, exact-head CI investigation, Android CDP and Server Phone qualification.
- **PRESERVED:** backend truth, API paths, permissions, activity cursor, Caddy/NATS/worker separation, offline read-only behavior and PR #588/#589 performance thresholds.

**Merge readiness: BLOCKED — DRAFT SOURCE IMPLEMENTATION / QUALIFICATION REQUIRED.**
