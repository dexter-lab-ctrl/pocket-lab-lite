# Azure Horizon Apps — Premium UI/UX P0–P1 Refinement

> **SOURCE IMPLEMENTATION ONLY — AUTHORED · NOT EXECUTED · UNVALIDATED.**
> Authoritative starting main: `bf48bfcaa660fc5fd7f5e6d34cf4f6f63601e425`.
> Feature branch: `feat/azure-horizon-apps-ux-polish`.
> No automated checks, screenshots, performance, CI investigation or device qualification were performed in this source-authoring session.
> Base PRs: [#606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606), [#622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622), [#623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623), [#588](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/588).

## 1. Objective
Refine the existing registry-driven Apps surface without redesigning other tabs. Implement theme integrity, Manage tabs and Details, clear action hierarchies, evidence-backed Photo Backup, structured storage/notices, smooth desktop geometry, mobile bottom-sheet continuity and bounded pull-to-refresh.

## 2. PR #623 baseline
PR #623 established Azure Apps catalog/search/filters, a shared desktop Manage geometry hook and generic app cards. This work refines those exact contracts rather than replacing them. Source of truth is the current repository; historic summaries are not qualification.

## 3. Screenshot defect inventory / resolution
| Defect | Source cause identified | Corrected owner | Intended behavior | Regression source |
|---|---|---|---|---|
| White bleeding in Black Manage | Legacy `#f8fafc !important` in Apps portal and scroll | `src/index.css` | Azure token-backed nested surfaces | Premium mocked/visual |
| Manage tabs unreadable | Daylight-only selected chip and fixed five-column geometry | `src/index.css`, `appsPremiumRefinement.css` | Scrollable, selected, focusable semantic tabs | Keyboard, theme, visual |
| Nested Details white backdrop | Daylight-scoped Details CSS and portal cascade | `appsPremiumRefinement.css` | Dark/Daylight/OS parity | Details theme tests |
| Daylight Details flat | All cards flattened by legacy Daylight-only rule | `appsPremiumRefinement.css` | Raised evidence sections in both themes | Details visual |
| Buttons touching | Inconsistent group gaps | `appsPremiumRefinement.css` | 44px targets, 14px gaps | Mobile responsive |
| Storage facts dark slab | Ungrouped icon/spans | `AppCatalogScreen.jsx` | Semantic definition-list rows | Storage expanded |
| Photo Backup guide plain | Paragraph-only explanation | `AppCatalogScreen.jsx` | Three educational step cards | Disclosure visual |
| Action Notices plain | Colon-joined strings | `AppCatalogScreen.jsx`, `appsOperationalView.js` | Deduped source-derived cards | Selector and browser tests |
| Conceptual path | Connectivity displayed alongside transfer concept | `appsOperationalView.js`, `AppCatalogScreen.jsx` | Device/Transfer/Destination per-step evidence | Ready/unknown/attention |
| Vague destination warning | No reason/action hierarchy | `PhotoBackupTruthCard` | Reason, current state and Devices next action | Scenario fixtures |
| Idle pull indicator | Indicator present without a bound touch zone | `AppCatalogScreen.jsx`, CSS | Hidden idle and desktop; valid touch zone | Gesture/presentation |
| Desktop move jumping | CSS important geometry overrides | `src/index.css`, shared hook | Fixed transient geometry with pointer capture | Geometry unit/browser |
| Desktop resize | Existing top control, rigid width rules | `AppCatalogScreen.jsx`, shared hook | Bottom-right grip, clamp, reset | Geometry tests |
| Mobile sheet | Desktop rules bleeding at breakpoint | CSS + existing portal | No move/resize, scroll & safe area | Mobile mocked |
| Generic app cards | Risk of PhotoPrism-only styling | Existing generic catalog + CSS | Capability-driven card, equal hierarchy | Multi-app mock |
| Action outcome | Evidence saved could promote status | `AppActionDetailsLazy.jsx` | Terminal-only success style | Contradictory status unit |

All entries are **SOURCE-IMPLEMENTED / UNVALIDATED**; screenshots have not been captured in this session.

## 4. Component ownership
- `src/lite/catalog/AppCatalogScreen.jsx` retains screen, header/search/filter, capability-derived sections, overlay, read-only projections, safe actions and photo-specific presentation.
- `src/lite/catalog/appsOperationalView.js` owns *pure presentation selectors* for Photo Backup facts and nonduplicated action notices.
- `src/lite/catalog/AppActionDetailsLazy.jsx` retains lazy, source-derived operation results and shared progressive Details.
- `src/lite/catalog/appsPremiumRefinement.css` owns Apps-specific geometry and semantic surface layering.
- `src/index.css` is changed only where old Apps important rules caused the observed defects.
- `src/lite/components/useDesktopManageGeometry.js` remains shared by Apps/Devices and owns transient geometry.
- Azure tokens and the existing backend are intentionally unchanged.

## 5. Theme-leakage root cause
The pre-Azure `.lite-catalog-manage-sheet` and portal rules used `#f8fafc !important` (including scroll container) and selected tabs used a Daylight blue-gradient literal. An Apps Details rule applied only to `.theme-pocket-lite-daylight.lite-details-overlay-layer` and flattened explanatory cards. Breakpoint grid/position important rules intercepted the shared movable panel. Refactoring *those owners* fixes the cascade without adding a second palette. Existing global aliases are preserved for compatibility.

## 6. Token inheritance
The root theme `html[data-lite-theme="light"|"dark"]` resolves PR #622 semantic tokens. System is the stored preference, not a third palette; the provider resolves OS appearance. Portals under document body inherit the root values.

| Semantic role | Token | Daylight source | Black source |
|---|---|---|---|
| Main card / Manage / Details | `--azure-surface` | `#FFFFFF` | `#0B0F14` |
| Raised facts / disclosures | `--azure-raised` | `#E7F2FF` | `#121822` |
| Border | `--azure-border` | `#D5E5F8` | `#1F2A36` |
| Foreground | `--azure-text` | `#142841` | `#E6EDF7` |
| Muted | `--azure-muted` | `#5B7088` | `#A4B3C4` |
| Accent | `--azure-accent` | `#006BC7` | `#4AA8FF` |
| Selected | `--azure-selected` | `#DFEEFF` | `#142941` |
| Focus | `--azure-focus` | `#075FAF` | `#79C5FF` |
| Inputs | `--azure-input` | `#FFFFFF` | `#0F1620` |
| Notices/warnings | `--azure-warning-subtle` | `#FFF1D7` | `#352B1B` |
| Backdrop | `--azure-backdrop` | light resolved overlay | dark resolved overlay |
| Elevation | `--azure-shadow` / `--azure-panel-shadow` | theme shadow | theme shadow |

All values above are from the repository's `src/lite/theme/azureHorizonTokens.css`, not local Apps palettes.

## 7. Surface hierarchy
Catalog page → shared GlassCard → Manage dialog → raised group/row → operational fact → supporting explanation → next safe action. Details uses shared portal and raised outcome sections. Data/status wording never depends solely on color.

## 8. Responsive layout
Catalog cards use the existing fluid grid. Manage fixed geometry only above the preexisting 701px breakpoint. Mobile remains bottom sheet with safe-area padding; information cards and guides stack at 700px or narrower. At 320–375px avoid shrinking labels to illegibility. 200% text, landscape, tablet, installed PWA and long names require later browser/physical-device qualification.

## 9. Manage geometry
Reuse `useDesktopManageGeometry` unchanged as shared *architecture*, extended with pointer-capture lifecycle, cancel/lost-capture cleanup, resize clamps, reset and announcements. The Apps panel uses a bottom-right resize control and existing move/reset buttons. Updates are requestAnimationFrame-coalesced, no new drag dependency or backend state/persistence. Source CSS fixed old `!important` width, left/right and max-height rules blocking controlled geometry.

## 10. Button groups
Retain `LiteButton` and Azure shared primary/secondary semantics. Scoped Apps action groups use a 0.875rem rhythm, 44px practical minimum controls and wrapping/stacking. Focus should not be clipped by action-row overflow; this requires manual review at 200% zoom.

## 11. Photo Backup readiness
`selectPhotoBackupFacts` reads the existing `/api/lite/media-backup` device projection. A device `ready` flag is readiness, not evidence of a transfer; `photo_storage_access` and `destination_ready` are separately reported. `latest_backup.status` classifies actual running/completion/review, `items_transferred=0` differs from null, timestamps derive from the recorded transfer/device, and missing evidence reads **Not reported**. No percentages, source media paths, credentials or private URLs are created.

## 12. Storage/device facts
Definition rows show host, media source, connected mappings/mode, storage-device availability, app-record backup readiness and protections. Backend-approved mappings stay unchanged. The user can navigate to Devices when storage readiness is missing.

## 13. Other action notices
`selectSupplementalActionNotices` filters only disabled backend-projected actions with concrete reasons, removes terminal/duplicate/no-reason entries and excludes active visible rows. Each notice has action, state, reason and optional backend-provided next step. No unconditional PhotoPrism warnings are synthesized.

## 14. Photo backup explanation
Native `details/summary` expands Step 1 source connection, Step 2 readiness, Step 3 protected PhotoPrism WebDAV delivery. Explicitly distinguishes media transfer from app-record backup and read-only restore preview. Education does not assert a live status.

## 15. Action Details
`LiteDetailsPanel` plus `LiteProgressiveDetails` retain What happened, What changed, What did not happen, Saved for troubleshooting, Technical details and Run history. Styling uses shared Azure surfaces in both resolved themes. `actionDetailsTone` is now driven by explicit status, not the presence of a saved record or positive wording. Unknown, queued, blocked and partial cannot appear as completed.

## 16. Universal App Platform
Search/filters/render cards remain registry/capability-based. PhotoPrism-specific Photo Backup and WebDAV explanation only appear behind the existing `isPhotoPrismApp` capability branch; synthetic Example App never gets Photo Backup. No frontend direct NATS, shell, lifecycle dispatch or backend-secret storage.

## 17. Accessibility
New tab `aria-selected`, roving `tabIndex`, arrows/Home/End and linked `tabpanel` IDs, labelled move/resize/reset controls, native disclosures, `role=status/alert` for backend facts and structured definition lists. Existing `useFocusTrap`, `useFocusReturn`, escape ownership and modal relationship remain. Axe specifications target WCAG AA; Axe cannot certify focus order, actual contrast at runtime, screen readers, vestibular safety or 200% zoom.

## 18. Keyboard
Tabs: Left/Right wrap, Home first, End last. Move/resize handles: arrows 16px; Shift+arrows 64px; Home resets; Reset button. Nested Action Details Escape returns to Manage and Manage close returns to its opener subject to existing focus helpers.

## 19. Touch/gestures
Desktop pointer captures move/resize with cancellation. No card or action-row dragging is added. Pull-to-refresh binds to a small, touch-only top zone; normal desktop and idle are hidden, and interaction is gated on scroll-top, reachability, saved state and in-flight refresh. Explicit Refresh remains authoritative. Manual touch-device testing remains mandatory.

## 20. Reduced motion
No decorative flow animation or fake transfer spinner is introduced. The touch status is static under reduced-motion, and the overlay/card CSS retains the existing low-power preference behavior.

## 21. Performance
No new dependencies, backend queries or polling channels. Status selectors are pure local functions, details remain lazy, and existing PR #588 frame/bundle/render budgets remain authoritative. New performance specifications sample frame intervals and Manage opening; they do not relax existing acceptance gates. **No timing measurements were taken.**

## 22. Unit/component tests authored (NOT RUN)
- `src/lite/catalog/appsOperationalView.test.js` — readiness/live/unknown/saved/zero items, non-fabricated destination, notices dedup and backend reasons.
- `src/lite/catalog/AppActionDetailsLazy.test.jsx` — blocked/queued/unknown statuses never promoted by saved record, terminal-only readiness.
- `src/lite/catalog/useDesktopManageGeometry.test.jsx` — shared pointer capture/cancel/resize/bounds and keyboard cases for Apps/Devices.

## 23. Playwright and accessibility authored (NOT RUN)
- `tests/e2e/lite-apps-azure-premium-polish.spec.ts` — Daylight/Black/System, narrow/desktop viewports, nested Details, tab semantics, storage/backup notices, generic app and Axe AA.
- Existing `tests/e2e/lite-azure-horizon-apps.spec.ts` — baseline shared Devices regression and broader gestures/zoom remain available.

## 24. Storybook and visual snapshots authored (NOT RUN)
- Extended `src/lite/LiteCatalog.stories.jsx` with Daylight/Black Manage, mobile, photo readiness (ready/review/unknown), explanation, storage, notices, multi-app, 200% zoom and saved/offline states. Fixtures come from MSW; no Server Phone data used.
- `tests/e2e/lite-apps-azure-premium-polish-visual.spec.ts` defines light/dark catalog/Manage/Details, storage/guide, moved/resized, zoom and media state screenshot expectations. **No baselines were captured or promoted; comparisons must not be treated as PASS.**

## 25. Commands for a SEPARATE qualification session (DO NOT RUN HERE)
```bash
npm run test:apps:premium:unit
npm run test:apps:premium:mocked
npm run test:apps:premium:theme
npm run test:apps:premium:a11y
npm run test:apps:premium:geometry
npm run test:apps:premium:devices-regression
npm run test:apps:premium:storybook
npm run test:apps:premium:performance
# After explicit owner approval and screenshot baseline creation:
npm run test:apps:premium:visual
npm run build
task lite:check
```
Existing Taskfile counterparts are `task lite:test:apps:premium:{unit,mocked,theme,a11y,geometry,devices-regression,storybook,performance,visual}`. Next session should first triage source/test regressions, run mocked and live read-only checks where authorized, review contrast and focus manually, collect owner-approved visual baselines, inspect PR #588 budget evidence, and only then judge readiness.

## 26. Risks
- Existing `src/index.css` has a long legacy cascade: some unrelated selectors may still take precedence at specific breakpoints or dynamic classes.
- Pointer events, capture loss, browser zoom, nested dialogs, touchscreen scroll and release will require real device/browser interaction testing.
- MSW media-backup fixture state may differ from production projections; unknown and malformed data must remain harmless.
- Contrast in Daylight/Black, 200% zoom, disabled controls and installed PWA safe areas is source-intended, not measured.
- Visual expectations have no reviewed baselines.
- The source-authored tests could themselves contain integration mistakes; no PASS is claimed.
- The P2 gesture is deliberately bounded to a small touch affordance; real touch usability requires observation.

## 27. Rollback
Before qualification/merge, close the draft PR or abandon the feature branch without touching `main`. If later merged, revert the PR through a dedicated review, not history rewrite. No backend state, device identity, app data, or credentials are migrated by this frontend patch.

## 28. Follow-up qualification
Run authored source checks and test suites *in a future authorized session*. Then inspect mobile portrait/landscape (320–430px), 701–900px transition, desktop zoom, keyboard/screen reader, Safari/Chromium PWA, Android touch pull, photo readiness contradictory cases, shared Devices geometry, and nested overlays. Resolve any CI failures only in the later stabilization session. Document exact result timestamps, SHA, command output, screenshot acceptance and signed off run summary.

## 29. Enterprise value
A trustworthy app-operations interface matters because ambiguous statuses, hidden warnings, inaccessible actions and contradictory theme cues can cause unsafe operator decisions. This refinement improves comprehension and reuse without broadening frontend authority or abandoning low-power self-hosting.

## Reuse provenance matrix
| Behavior | Original | Exact existing symbol/owner | Retained behavior | Focused refinement |
|---|---|---|---|---|
| Button | #606 | `LiteButton` in `src/lite/LiteUi.jsx` | Accessible tone/disabled semantics | Apps-only group gaps |
| Cards | #606 | `GlassCard` / `AppSummaryCard` | Semantic shared surfaces | Operational fact cards |
| Status | #606 | `StatusBadge`, `StateSurface` | Backend-linked status | Legible layered status |
| Dialog/focus | #606 | `LiteDetailsPanel`, `useFocusTrap`, `useFocusReturn` in `LiteOverlay.jsx` | Escape/return/trap | Token-correct nested Details |
| Progressive detail | shared platform | `LiteProgressiveDetails` | Lightweight evidence details | Truthful outcome tone |
| Azure themes | #622 | `LiteThemeProvider`, `azureHorizonTokens.css` | Daylight/Black/System | Inherited nested surfaces |
| Desktop geometry | #623 | `useDesktopManageGeometry` | Clamp/keyboard/reset | Pointer capture, grip, CSS ownership |
| Catalog | #623 | `AppCatalogScreen`, `catalogPresentation` | Generic registry/app cards | Hierarchy/filter continuity |
| Photo workflows | existing platform | FastAPI media-backup projection via `liteApi.mediaBackup` | Backend-owned execution | Evidence-led readiness-only view |

## Status ledger
**Source-authored and committed** is not **working or passed**. All new tests, Storybook states, visuals, performance sampling, contrast targets, browser interaction, physical Android qualification and runtime readiness remain **AUTHORED — NOT EXECUTED — UNVALIDATED**.

**Merge forbidden in this session; deployment and release forbidden. CI failures were not investigated or remediated.**
