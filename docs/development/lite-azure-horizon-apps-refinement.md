# Azure Horizon Apps — implementation and deferred qualification

> [!IMPORTANT]
> **IMPLEMENTED SOURCE · UNVALIDATED.** The branch `feat/azure-horizon-apps-ui` was authored as an implementation-only change. Tests, builds, checks, screenshots, accessibility measurement, CI investigation, runtime and Android qualification were **NOT RUN**. Approval to merge or deploy has not been given. The current GitHub repository, not this document, is source of truth.

## 1. Objective
Refine the existing Universal App Platform's Apps catalog and Manage experience to match the Azure Horizon Home visual language from PR #622, reuse shared PR #606 UI semantics, and preserve PR #588 low-power performance contract. One generic Apps UI must support Azure Black, Daylight and System preference without a second design system or a PhotoPrism-only rewrite.

## 2. Current implementation baseline
The authoritative base when the branch was created was `main` at `693c41559e326ab369f2bf3c6af61da6056d8e40`. Apps ownership is primarily `src/lite/catalog/AppCatalogScreen.jsx`; small wrappers under `src/lite/catalog/` are not themselves the lifecycle implementation. Backend contracts continue to be projected via FastAPI and consumed through TanStack Query, offline safe snapshots and existing governed mutation functions.

## 3. Azure palette authority
`src/lite/theme/azureHorizonTokens.css` is the sole palette authority. Black uses canvas `#050607`, surface `#0B0F14`, raised `#121822`, text `#E6EDF7`, and accent `#4AA8FF`. Daylight uses canvas `#F4F9FF`, surface `#FFFFFF`, raised `#E7F2FF`, text `#142841`. Importantly, contrast-corrected foreground and focus tokens remain authoritative instead of older mockup hex values. `LiteThemeProvider` and `liteThemeRuntime` continue to resolve Light/Dark/System; no new preference is introduced.

## 4. Shared component ownership
`PageHeader`, `GlassCard`, `LiteButton`, `StatusBadge`, `StateSurface`, `LiteFreshness`, `LiteNextSteps`, `LiteDetailsPanel` and safe confirmation forms continue to own their semantic functions. `AppSummaryCard` wraps shared GlassCard. AppActionRow and AppActionProgressSlot present backend-projected capability, readiness and progress. The desktop geometry controller lives in `src/lite/components/useDesktopManageGeometry.js`, shared by Apps and Devices.

## 5. Apps catalog architecture
The existing `selectCatalogSummaryView` projection, `liteQueryKeys.catalog()`, safe snapshots, `liteApi.catalog` and live/saved handling remain unchanged. Search and status filtering are local read-only projections through `catalogPresentation.js`. No new API endpoint, command, queue or arbitrary app ordering is introduced.

## 6. Desktop layout
The catalog retains the global navigation and shared page header. Its content uses responsive CSS Grid with a minimum card width and allows a variable number of columns. The first app retains the current featured ordering. Search, counts, safe readiness guidance and backend-derived notices remain visible.

## 7. Mobile layout
At narrow widths, the catalog is one column and primary actions remain accessible. Search and filter controls wrap, button touch targets are at least 44 CSS px where controlled by the new styles, and Manage remains a scrollable bottom sheet. The shared app navigation is not replaced. 320, 360, 375, 390, 430 and tablet widths are authored browser scenarios.

## 8. App card structure
The card uses shared GlassCard presentation, app icon with built-in generic fallback, accessible app title, short summary/description, backend-derived status, concise readiness, and Open/Manage. Install remains shown where currently supported. Long names wrap; descriptions clamp visually to three lines with original content preserved in the title attribute.

## 9. Search and filter behavior
The labelled searchbox has a Search icon, keyboard-clearing action, theme-aware input, visible focus and no new server traffic. Filters use `aria-pressed` and real catalog-derived counts for All, Ready, Installing/working, Needs attention and Not installed. Buckets classify unknown separately and only consider Ready after actual backend-projected route readiness. Unavailable buckets are hidden unless selected.

## 10. Lifecycle status truthfulness
Installing/queued/starting/updating/removing are working, while blocked/unhealthy/failed/stopped, route unavailability or reported HTTPS failure indicate attention. An installed-but-unverified app is not automatically categorised as route-ready. Saved/degraded state remains read-only. No successful action is synthesized from a request acceptance.

## 11. Manage panel structure
`CatalogManagePortal` remains the owner of Manage's lifecycle and existing nested overlays. It keeps lazy action-model building, app-resource/governance information, capability-derived sections, PhotoPrism extensions and protected confirm flows. The header presents app name, concise explanation, current status/freshness and a close action. Existing section tabs and action rows are retained.

## 12. Desktop drag/resize reuse from Devices
The old DeviceDetailsPortal-specific pointer/keyboard geometry logic has been extracted to `useDesktopManageGeometry`. Both DeviceDetailsPortal and CatalogManagePortal call it. It uses the existing `(min-width: 701px)` contract, separate move and resize handles, transient React state, requestAnimationFrame coalescing, window pointer listeners with cleanup, geometry clamping and a reset button. No dependency or geometry persistence is introduced.

## 13. Accessible resize/move behavior
Both surfaces provide dedicated labelled move/resize buttons. While a handle has focus, arrows move or resize by 16 px, Shift+arrows by 64 px, Home resets, and a visible Reset button restores position and size. Live status announces keyboard changes; ordinary buttons, tabs and text are not draggable. Normal Escape behaviour remains with overlay ownership.

## 14. Mobile bottom sheet behavior
The Apps portal preserves its existing bottom-sheet grip, safe-area padding, body-scroll containment, close control, performance-mode behavior and nested Details. Below 701 px geometry and desktop handles disappear; a return to desktop creates or clamps a safe position. Touch scrolling does not start window dragging.

## 15. Photos and storage
PhotoPrism media flow, connected source and storage mapping summaries, phone/joined storage choices, backend-derived readiness, storage preview and import progress remain in their existing lifecycle implementation. Media UI remains capability-gated. Private paths and credentials must not be introduced into the frontend.

## 16. Backup and restore presentation
The protected records-only app backup and separate device photo backup retain their distinction. The existing source → transfer/destination → verification summaries remain backend-driven; conceptual paths are labelled conceptual. Restore preview is read-only and does not confer apply permission. Destinations and backup verification remain server-owned.

## 17. Updates and repair
Update readiness stays distinct from applying a newer app version. Check/Repair/Update buttons remain enabled or blocked by existing FastAPI projections, risk gates and backend authorization. The UI does not start PM2, Caddy, workers, scanners or arbitrary app commands.

## 18. Destructive safeguards
Removing an app still requires the existing review and protected confirmation. Default media and backup protections remain stated. Personal Mode and Enterprise Mode authorization, OPA/Rules decisions and backend audit evidence are not bypassed.

## 19. Portal and theme handling
The Apps portal no longer hardcodes a Daylight class or color. It uses inherited CSS custom properties from the resolved root theme, including `--azure-surface`, `--azure-muted`, `--azure-border`, `--azure-backdrop`, and `--azure-panel-shadow`. Nested Action Details continue to use shared LiteDetailsPanel; no second modal framework was added.

## 20. Accessibility
The catalogue has a programmatic search label, clear action, accessible filter group, text statuses independent from color, labelled move/resize/reset handles, responsive controls, visible focus and responsive wrapping. Shared FocusReturn and FocusTrap are reused by Apps Manage; existing nested overlay close behavior is retained. New Axe scenarios target WCAG A/AA including Light/Dark, mobile and 200% text. **Contrast, keyboard trapping and screen reader behaviour are unmeasured until qualification.**

## 21. Performance
The existing PR #588 performance budget and default low-power mode are not edited. Panel pointer updates are coalesced via requestAnimationFrame. No new npm dependencies, decorative animation loops, backend polling, or eager details data were added. Supplemental performance scenarios sample catalog, filtering, Manage and geometry interactions but do not invent new acceptance thresholds.

## 22. CSS migration
`appsPremiumRefinement.css` consolidates selectors into theme-neutral Apps ownership, adds a small Azure-specific semantic surface layer and avoids the old Daylight-only portal class. Pre-Azure styles in `src/index.css` continue to exist for compatibility; their cascade and older accents require visual qualification. The code does **not** claim all legacy CSS debt has been removed.

## 23. Authored tests, tasks and Storybook
Unit: `catalogPresentationAzure.test.js`, `useDesktopManageGeometry.test.jsx`. Mocked browser: `lite-azure-horizon-apps.spec.ts`; visual definitions: `lite-azure-horizon-apps-visual.spec.ts`; perf samples: `lite-azure-horizon-apps-performance.spec.ts`. `LiteCatalog.stories.jsx` contains Light/Dark, mobile/desktop, capability, saved, stale, media, failure, and Manage states. npm and `tasks/Taskfile.ui.yml` add targeted tasks.

## 24. Future validation commands — ALL NOT RUN
The following commands are **instructions for a separate stabilization session**, not evidence of a successful run.

```bash
npm run test:apps:azure:unit
npm run test:apps:azure:mocked
npm run test:apps:azure:a11y
npm run test:apps:azure:geometry
npm run test:apps:azure:perf
npm run test:apps:azure:visual
npm run test:azure:qualification
npm run test:apps:azure:qualification
npm run build
npm run test:mock-regression
npm run test:a11y:states
npm run test:perf
task lite:check
```

Run baseline screenshot capture and **human review** before invoking the visual comparison task. Do not auto-approve new snapshots. Add a separate mobile Android/Termux runtime session only after development-PC source and browser stabilization.

## 25. Known limitations and risks
All new code is **UNVALIDATED**. Risks include CSS specificity against long-standing Daylight rules, focus-trap interactions with nested overlays, state sorting assumptions, pointer handling under browser zoom, resizing in short viewports, scroll containment on physical Android, accessibility contrasts, unknown/long app text, low-power layout cost and older Devices behaviour after shared extraction. The mocked test scenarios also need stabilization against current fixture timing and semantics.

## 26. Follow-ups
Separate qualification should inspect real rendered screenshots for Black/Daylight; measure color contrast, high text zoom, mixed focus handling and low-power frame budgets; verify DeviceDetailsPortal regression, Azure dark portal inheritance, authorization-negative results, storage/PhotoPrism no-media-scan boundaries and compatibility with generic example-app fixture. Fix defects as targeted commits without loosening PR #588 budgets.

## 27. Rollback
No changes to production, backend, workflows or release artifacts were made. Before merging, revert feature branch commits or close the draft PR; `main` is unchanged. After an authorized merge, revert the merge commit using the usual PR governance procedure rather than manipulating deployed runtime state. Do not deploy unqualified source.

## Qualification inventory

| Workstream | Source disposition | Qualification |
|---|---|---|
| P0 semantic Azure Apps surface | Implemented | NOT RUN |
| P1 catalog/grid/search/filters | Implemented | NOT RUN |
| P2 Manage + shared geometry | Implemented | NOT RUN |
| P3 media/storage/lifecycle presentation | Existing semantics retained; presentation updated | NOT RUN |
| P4 units/Stories/Playwright/tasks | Authored | NOT RUN |
| Desktop/mobile screenshot baselines | DEFINED — CAPTURE AND HUMAN REVIEW DEFERRED | NOT RUN |
| Contrast, Axe, keyboard, zoom, physical Android | DEFERRED to stabilization | NOT RUN |
| CI investigation, release, merge | Explicitly forbidden in this session | NOT RUN |

**Required disposition: DRAFT — IMPLEMENTED — UNVALIDATED — DO NOT MERGE.**
