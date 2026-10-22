# Azure Horizon — Lite appearance and premium Home

> **IMPLEMENTATION PROVIDED — QUALIFICATION STATUS RECORDED IN THE CURRENT PR #626 ADDENDUM.**
>
> This document retains the design-system source contract. Current PR #626 evidence is split into verified mocked/accessibility/build results, pending visual approval, performance attribution and an Android CDP attach blocker. **DRAFT — DO NOT MERGE.**

## 1. Design goals and scope

Azure Horizon makes Pocket Lab Lite a quiet, premium, small-device-friendly self-hosted control plane, rather than an operations-heavy visual dashboard. Home is the first comprehensively rearranged tab; other tabs inherit shared semantic styling without replacing their screen composition.

The application retains the **React/Vite PWA → Caddy same origin → FastAPI `/api/lite/*` → NATS/JetStream → worker/agent/supervisor → sanitized events → FastAPI → UI** boundary. No browser-side execution, NATS connection, scanner, backup, PM2, enrollment or credential handling has been added.

## 2. Two appearances, one component tree

`data-lite-theme="light"` is **Azure Horizon Daylight** and `data-lite-theme="dark"` is **Azure Horizon Black**. System is a preference, **not a third CSS appearance**; it resolves using `prefers-color-scheme`. The same DOM and responsive CSS govern both.

| Semantic role | Black | Daylight |
|---|---|---|
| Canvas | `#050607` | `#F4F9FF` |
| Main surface | `#0B0F14` | `#FFFFFF` |
| Raised surface | `#121822` | `#E7F2FF` |
| Border | `#1F2A36` | `#D5E5F8` |
| Primary text | `#E6EDF7` | `#142841` |
| Secondary text | `#A4B3C4` | `#60768F` |
| Azure accent | `#4AA8FF` | `#087DEB` |
| Primary button | `#248EF1` | `#087DEB` |
| Button foreground | `#FFFFFF` | `#FFFFFF` |
| Success | `#62D6A8` | `#087E68` |
| Warning | `#F1C47A` | `#9A640D` |
| Danger | `#FF8794` | `#BF4756` |

Expanded roles include focus, pressed/hover/selected, informational/neutral, disabled, form fields, error/warning/success surfaces, backdrop, skeleton, high-contrast border, selection, and elevation. **These palette choices are starting points, not WCAG certification.**

## 3. Canonical token ownership

- `src/lite/theme/azureHorizonTokens.css`: sole semantic palette authority, rooted at `:root[data-lite-theme]`. Backward-compatibility mappings include `--pocket-*`, `--lite-*` and the P0 focus token.
- `src/lite/theme/azureHorizon.css`: shared shell, navigation, button, card, badge, status, loading, form, overlay and typography **application** of tokens. It must not contain backend assumptions.
- `src/lite/components/azureHome.css`: Home-specific **geometry**, reusing color tokens.
- `src/lite/liteDesignSystemP0.css`: PR #606 shared touch, focus, sizing and overlay baseline; preserved.
- `src/index.css`: historic cascade; intentionally retained and *not* regenerated wholesale.

Do not copy palette literals into new tab JSX. Adjust semantic tokens if future accessibility evidence requires a contrast correction. Avoid creating theme-specific React components.

## 4. Preference and startup ownership

| Element | Responsibility |
|---|---|
| `public/lite-theme-bootstrap.js` | Synchronous, same-origin pre-paint resolution in `index.html`; no API calls |
| `liteThemeRuntime.js` | Normalization, safe read/write, System resolution, root attributes, native `color-scheme`, browser theme color |
| `LiteThemeProvider.jsx` | Subscribe to harmless Zustand UI preference and live OS media changes |
| `liteUiStore.js` | Stores only `appearancePreference` and its setter; **never operational state** |
| `LiteThemeControl` | Shared accessible native Light/Dark/System select in the existing header |

Canonical local storage key: `pocketlab:appearance` with `light|dark|system`. Legacy `POCKETLAB_LITE_THEME` (`daylight|dark`) can be read on first use but new writes use only the canonical key. Invalid/unavailable storage falls back to System. System remains the persisted preference even when the resolved OS appearance changes. Nothing is sent to FastAPI, Dexie or NATS. Private browsing storage failure is nonfatal.

The pre-paint script is same-origin to preserve CSP compatibility with the existing self-hosted PWA. Offline caching behavior of this **new** resource still requires qualification.

## 5. Portal propagation

PR #606's `LiteOverlayRoot` and `LiteSheet` originally included `theme-pocket-lite-daylight` class names inside `document.body` portals, independently of the app shell. These hardcoded portal classes are removed. The authoritative `html[data-lite-theme]` attribute and semantic CSS now style modal, backdrop, sheet, Details panel, fields and focus rings through normal ancestry, including nested overlays. Portal ownership, Escape stack, focus trap, focus return, backdrop, body lock, safe-grip and reduced-motion behavior are otherwise retained.

## 6. Typography and density

Theme-independent scale: page heading 24–30px; hero 20–28px; section 17–20px; card 15–16px; body 14px; supporting 13px; controls 14px; line heights typically 1.4–1.5. Use `font-weight:600–650` for headings, with tabular numerals in counters. System monospace remains the appropriate technical font.

The configured stack *prefers* Inter if already available locally, then falls back to platform sans-serif. **No Inter WOFF2 binary was added**: the licensing/subsetting/bundling and low-power size review are deferred, rather than introducing a remote Google Fonts dependency or a large unreviewed asset.

## 7. Desktop application shell

The preexisting header continues to own Pocket Lab identity, installed-PWA affordances and Quick Find. The seven-tab PR #606 navigation configuration remains canonical. Its existing icon rail gains text labels at desktop widths, with Azure selected state and no duplicate navigation or fictional notification/account widgets. The existing workspace app-switcher and URL handling remain unchanged.

At desktop widths (approximately 1024px and above), Home uses a workspace heading, bounded LiteOperationalStory hero, four source-derived tiles, recent activity and attention sections. The main column accommodates the labeled sidebar. The existing Home layout remains the only screen-specific redesign.

## 8. Mobile and adaptive geometry

Below tablet widths, the existing mobile bottom navigation and More sheet remain canonical; they expose all seven tabs without a second router. Home's four tiles form a 2×2 grid when the available width supports it. Below about 355px the tiles stack to avoid overflow, especially with enlarged text. The 850px breakpoint stacks the activity/attention area. CSS handles layout; no JavaScript resize listeners or new component trees.

Safe-area padding, minimum 44px controls, keyboard navigation, existing responsive overlays and no body horizontal overflow are required behaviors **to qualify** at 320, 360, 375, 390, 430, tablet and desktop widths.

## 9. Home operational-state contract

Home continues to receive the existing prepared FastAPI status and safe read-only snapshots. `buildLiteHomeOverview` remains the source for the overview, `workspaceStory`, service labels, overall tone and detail sections. The main hero is the existing `LiteOperationalStory`; no fabricated device count, app, CPU, RAM, uptime, safety score, release, or successful operation is added.

States requiring visual qualification: ready, attention, degraded, checking, loading, saved, stale, API unavailable, partial and unknown. Green/amber/red/blue/neutral are **presentation**, not a replacement for backend status. The decorative hero halo conveys no health or connectivity assertion. Refresh and `LiteFreshness` remain visible.

## 10. Workspace overview

The four summary destinations are Apps, Devices, Safety and Backups/Recovery. Each clickable tile reuses the PR #606 `GlassCard` primitive as a semantic button with text/icon and authoritative per-service status. The existing `onNavigate` callback owns navigation. Additional backend-provided areas remain reachable through the existing More areas disclosure. No numeric metrics are displayed unless the existing projection actually supplies them.

## 11. Activity and personal review

The lightweight `/api/lite/system/activity-summary` read still supports first Home paint. `/api/lite/home/activity-history` remains lazy and is requested only when Activity Details opens. `HomeActivityDetails` retains bounded sanitized events, grouping, timestamps and explicit empty/unavailable states.

The per-human SQLite review cursor remains FastAPI-owned. `Mark activity reviewed` still uses `liteApi.reviewHomeActivityCursor()` with the existing authorization and disabled/saved controls. A review never resolves a backend issue, approves action, or deletes audit records.

## 12. Attention prioritization

The same `prioritizeWorkspaceAttention` selector and `LiteNextSteps` guidance remain. Attention is displayed after the overview/activity area to produce a calmer first scan; it is **not discarded** for aesthetic purposes. Saved information continues to warn about uncertainty and must not be treated as live execution authorization.

## 13. Workspace Details and Activity Details

Both preserve PR #606 `LiteDetailsPanel`/portal/scroll/focus semantics. Desktop: right-side details panel. Mobile: bottom sheet. Workspace sections are Overview, Service health, Updates, Diagnostics, with retained scroll-aware section tabs and `LiteReleaseUpdateCard`. Activity Details maintains Attention/Running/Recent/History, including personal review position. Styling is semantic; the backend content and write workflow are unchanged.

## 14. Shared component reuse matrix

| Surface | Existing primitive | Azure adjustment |
|---|---|---|
| App/header | `LiteApp`, existing `NAV_ITEMS` | top bar, labeled desktop rail, shared theme selector |
| Page heading | `PageHeader` | tokenized typography and spacing |
| Hero | `LiteOperationalStory` | Home layout, semantic status stripe |
| Overview | `GlassCard` | existing navigation button semantics |
| Buttons | `LiteButton` | semantic hover, disabled, focus, emphasis |
| Other cards | `GlassCard` | border, radius, surface, elevation |
| Badges | `StatusBadge` | success/warning/danger/info/neutral tokens |
| Loading/empty/error | `StateSurface` and `LoadingCard` | token surfaces and skeleton |
| Actions | `LiteActionRow` | shared density/foreground |
| Manage/details | `LiteSheet` and `LiteDetailsPanel` | root theme propagation |
| Confirmations/forms | PR #606 shared safe forms | inherits shared surface/control styles |
| Guidance | `LiteNextSteps` | maintained priority and saved-state semantics |

Do not fork these components for future Apps, Devices, Security, Identity, Rules or Recovery migrations.

## 15. Accessibility behavior and qualifications

The design retains semantic buttons, labeled native theme selector, focus outlines, ARIA dialog semantics, existing overlay Escape stack, focus return and keyboard nav. It supports `prefers-reduced-motion` and text enlargement through CSS. Color-coded state must retain text labels. Automated Axe WCAG AA checks are defined for light/dark Home, shell and Details. **No contrast or accessibility PASS is claimed**; visual and browser checks remain pending.

## 16. Edge-first performance design

No new animation library, runtime polling, backend fetch, heavy blur, remote font or large image has been introduced. The hero accent is static CSS. Shared cards avoid continuous effects. Heavy Details and activity history remain on demand. Existing PR #588 frame budget and `expectLitePerformanceBudget` are reused without relaxed thresholds.

## 17. CSS migration and follow-up tabs

Historical CSS remains large. Later increments should remove legacy overrides only where superseded and qualified; do not bulk-delete or regenerate. Use `html[data-lite-theme]` for theme-dependent rules, `--azure-*` for colors and shared primitives for interaction semantics. Cross-tab priority: Apps → Devices → Security → Identity & Access → Rules → Recovery, each as separate reviewed UI work, without disturbing their existing operational workflows.

## 18. Authored coverage and current execution

| Source | Intended coverage |
|---|---|
| `liteThemeRuntime.test.js` | preference resolution, invalid storage, no operational keys, color-scheme/meta |
| `LiteThemeProvider.test.jsx` | System changes, theme picker and portal inheritance |
| `LiteHomeAzure.test.jsx` and existing Home tests | four tiles, on-demand activity, Details sections, saved-state honesty |
| `LiteAzureHorizon.stories.jsx` | Daylight/Black, desktop/mobile, attention/saved/offline, Details, long text |
| `lite-azure-horizon.spec.ts` | responsive widths, theme persistence, OS changes, Axe, focus, activity, overflow, 200% text |
| `lite-azure-horizon-visual.spec.ts` | canonical visual contracts; 14 existing cases pass and 8 detail baselines mismatch the current panel geometry |
| `lite-azure-horizon-performance.spec.ts` | PR #588 instrumented theme-switch and Details-open interactions |

## 19. Qualification command reference

The PR #626 session inspected exact branch provenance and ran the focused and shared mocked/accessibility suites, Storybook, build and performance commands. Keep this list as the repeatable command reference for future exact-head checks:

```bash
npm run test:azure:unit
npm run test:azure:home
npm run test:azure:storybook
npm run test:azure:mocked
npm run test:azure:a11y
npm run build:budget
npm run test:azure:perf
npm run test:a11y:states
npm run test:mock-regression
task lite:check
```

The new premium visual suite intentionally remains baseline-pending. Existing canonical visual mismatches and the physical Android CDP blocker are recorded in the Home panel refinement addendum; neither is silently converted to a pass.

## 20. Screenshot baseline disposition

**BASELINES DEFINED — APPROVAL PENDING.** The new visual spec defines Daylight/Black Home on mobile and desktop, attention, saved, unavailable and light/dark Workspace/Activity Details. Candidate images were captured during PR #626 qualification but are not canonical until owner review. PR #606/#622 reference images remain untouched.

## 21. Current risks and unvalidated areas

- CSS specificity/cascade conflicts with the very large historical `src/index.css`, especially cross-tab Daylight selectors.
- Root and control contrast is covered by the mocked Axe suites for the qualified Home and shared tabs; visual approval and physical safe-area evidence remain pending.
- Inter is not locally bundled; actual font differs across Android/desktop and could change metrics.
- Overlay focus/return and nested scroll behavior pass mocked keyboard/state coverage; physical Android rendering remains blocked by CDP attach.
- Mobile 320px–1440px and 200% text have mocked evidence; installed PWA, safe areas and offline bootstrap asset caching remain unvalidated.
- Screenshot references are missing by design; visual gate must not pass without approval.
- Newly authored unit/mocked/performance commands execute on the feature branch; premium screenshot approval remains pending.
- PR #588 performance budgets remain unchanged; residual target/hard-gate outcomes are classified in the qualification addendum.
- Exact-head GitHub Actions still require inspection after the final docs commit and push.

## 22. Release/merge disposition

**IMPLEMENTATION PROVIDED — QUALIFICATION PARTIAL / DRAFT.**

Dev-PC tests, a11y, Storybook, build, performance and read-only Server Phone checks were executed. Lint/typecheck are repository configuration limitations, new visual baselines await owner approval, physical Android CDP attach is blocked, and exact-head CI completed with one documented pre-existing Devices performance residual. The PR stays **OPEN — DRAFT — NOT MERGED**.


## Home Workspace and Activity panel refinement (PR #626 qualification)

The later Home-only refinement adds the shared section-scroll hook, Home-specific `LiteSheet` variant, Azure token-scoped panel content, backend-truthful Activity presentation, reusable desktop geometry and authored regression definitions. See [Azure Home panel refinement qualification addendum](lite-home-azure-panel-refinement.md) for exact source changes, verified results, pending baselines and blocked Android evidence.
