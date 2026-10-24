# Azure Horizon Apps — Premium UI/UX P0–P1 Refinement

> **QUALIFICATION ADDENDUM APPLIED — SOURCE, MOCKED, VISUAL AND DEVICE EVIDENCE RECORDED.**
> Original source baseline: `1fd4058b5fa29d5f7a30908c6bb8410ddf2fabb0`.
> Final candidate at the end of qualification: see the exact-head evidence below.
> Feature branch: `feat/azure-horizon-apps-ux-polish`.
> PR #629 remains **OPEN — DRAFT**. Merge, release and production deployment remain unauthorized.
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

The entries above describe the original source-authoring state. The qualification addendum below records the later execution evidence and its explicit limits.

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
No new dependencies, backend queries or polling channels. Status selectors are pure local functions, details remain lazy, and existing PR #588 frame/bundle/render budgets remain authoritative. New performance specifications sample frame intervals and Manage opening; they do not relax existing acceptance gates. Qualification measurements and attribution are recorded in the addendum below.

## 22. Unit/component tests authored and subsequently executed
- `src/lite/catalog/appsOperationalView.test.js` — readiness/live/unknown/saved/zero items, non-fabricated destination, notices dedup and backend reasons.
- `src/lite/catalog/AppActionDetailsLazy.test.jsx` — blocked/queued/unknown statuses never promoted by saved record, terminal-only readiness.
- `src/lite/catalog/useDesktopManageGeometry.test.jsx` — shared pointer capture/cancel/resize/bounds and keyboard cases for Apps/Devices.

## 23. Playwright and accessibility authored and subsequently executed
- `tests/e2e/lite-apps-azure-premium-polish.spec.ts` — Daylight/Black/System, narrow/desktop viewports, nested Details, tab semantics, storage/backup notices, generic app and Axe AA.
- Existing `tests/e2e/lite-azure-horizon-apps.spec.ts` — baseline shared Devices regression and broader gestures/zoom remain available.

## 24. Storybook and visual snapshots authored and subsequently executed
- Extended `src/lite/LiteCatalog.stories.jsx` with Daylight/Black Manage, mobile, photo readiness (ready/review/unknown), explanation, storage, notices, multi-app, 200% zoom and saved/offline states. Fixtures come from MSW; no Server Phone data used.
- `tests/e2e/lite-apps-azure-premium-polish-visual.spec.ts` defines light/dark catalog/Manage/Details, storage/guide, moved/resized, zoom and media state screenshot expectations. The reviewed baseline set is recorded below.

## 25. Commands used by the qualification session
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
Existing Taskfile counterparts are `task lite:test:apps:premium:{unit,mocked,theme,a11y,geometry,devices-regression,storybook,performance,visual}`. The final results and residual limits are recorded below.

## 26. Risks
- Existing `src/index.css` has a long legacy cascade: some unrelated selectors may still take precedence at specific breakpoints or dynamic classes.
- Pointer events, capture loss, browser zoom, nested dialogs, touchscreen scroll and release will require real device/browser interaction testing.
- MSW media-backup fixture state may differ from production projections; unknown and malformed data must remain harmless.
- Contrast in Daylight/Black, 200% zoom, disabled controls and installed PWA safe areas is source-intended, not measured.
- Visual expectations now have reviewed Daylight/Black baselines; physical screenshots remain qualification evidence rather than committed Playwright baselines.
- The source-authored tests were corrected where their setup/fixture assumptions were wrong; results and remaining environment failures are listed below.
- The P2 gesture is deliberately bounded to a small touch affordance; real touch usability requires observation.

## 27. Rollback
Before qualification/merge, close the draft PR or abandon the feature branch without touching `main`. If later merged, revert the PR through a dedicated review, not history rewrite. No backend state, device identity, app data, or credentials are migrated by this frontend patch.

## 28. Follow-up qualification
The qualification session executed the scoped Chromium and Android checks described below. Remaining work is limited to external/runtime blockers and any future review of the retained physical performance target misses; it is not a reason to broaden PR #629 into unrelated optimization.

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

## 30. Qualification addendum — PR #629 stabilization

### Provenance and disposition

| Item | Verified value |
|---|---|
| Repository | `dexter-lab-ctrl/pocket-lab-lite` |
| Base | `main` at `bf48bfcaa660fc5fd7f5e6d34cf4f6f63601e425` |
| Original feature head | `1fd4058b5fa29d5f7a30908c6bb8410ddf2fabb0` |
| Final candidate during this qualification | `803c6ae1fbc9bcfec60a3e255a4f7e3c57d0a517` before the documentation-only follow-up commit |
| Branch | `feat/azure-horizon-apps-ux-polish` |
| PR | [#629](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/629), OPEN, DRAFT |
| Merge/release/deployment | NOT AUTHORIZED; none performed |

### Stabilization changes

The exact source/test fixes were committed to the feature branch. The changes fixed: Playwright `testMatch` registration for the new premium suites; legacy global `!important` geometry leaking into movable Apps/Devices panels; missing `jest-dom` and async assertions in the Action Details unit test; pointer-cancel animation cleanup coverage; the small-pull `touchend` readiness lifecycle; fixture readiness needed to open read-only Manage states; Black Manage and nested Action Details token/surface leakage; visual settling around lazy Details and stale loading opacity; source-contract assertions that confused `aria-hidden` with a standalone `hidden` prop, used the old Storage label, or rejected the scoped touch-zone binding; and stale qualification comments/Taskfile descriptions. The late documentation pass also fixed the source-owned Graphviz cleanup routine so it preserves the committed `docs/assets/diagrams/readme-control-flow.svg` while still removing generated stale diagrams.

### Dev PC test evidence

| Qualification | Result |
|---|---|
| `npm run test:apps:premium:unit` | PASS — 3 files, 35 tests |
| `npm run test:apps:azure:unit` | PASS — 3 files, 19 tests |
| `npm run test:azure:unit` | PASS — 2 files, 7 tests |
| `npm run test:apps:premium:mocked` | PASS — 61 passed, 3 intentional desktop touch skips |
| Premium theme/geometry/Devices/a11y | PASS — 10 / 44 (43 plus one expected touch skip) / 2 / 4 |
| Existing Azure mocked/a11y/geometry | PASS — 64 / 4 / 40 |
| `npm run build` | PASS — Vite build, 2243 modules; existing large-chunk warnings retained |
| `npm run lint` | BLOCKED — repository has no ESLint configuration; no unrelated config was introduced |
| `npm run typecheck` | UNVALIDATED — repository script invokes `tsc ... || true` without a project config and returned TypeScript help |
| `npm run test:apps:premium:storybook` | PASS — Storybook build, 2335 modules; existing chunk/evaluation warnings retained |
| `npm run test:apps:premium:visual` | PASS — 68 comparisons, 72 accepted PNG baselines, no-update stability rerun |

Mocked coverage exercised Daylight, Black and System themes; desktop, tablet and mobile layouts; 320/360/375/390/430px mobile widths; 701px geometry boundary; wide/standard/narrow desktop; long names; generic apps; storage, notices, Photo Backup truth states; nested Action Details; keyboard and Axe cases; responsive reflow and 200% text. The shared Devices geometry regression remained passing.

### Visual acceptance

The accepted Playwright baseline set is committed under `tests/e2e/lite-apps-azure-premium-polish-visual.spec.ts-snapshots/`. The reviewed matrix covers Daylight/Black catalog and Manage, mobile reflow, nested Action Details, ready/attention/unknown Photo Backup, storage and notice disclosures, moved/resized panels, narrow layout, 200% text and long names. Physical Android screenshots were inspected separately and were not mixed into the deterministic browser baseline set.

### Live backend and authentication boundaries

The Server Phone was inspected read-only at runtime SHA `a53939e2d9e3bfb0cdae819479ba422c082b0a76`, on clean `main`. PM2 and the initial health/readiness/NATS/resilience checks passed. Later bounded reads observed a transient/restarting API and the runtime contract reported `stable=false`, `state=restart_budget_exhausted`; this is an external runtime residual, not an Apps source change. The live candidate served the exact feature SHA and the live read-only suite passed 6/8 tests; the two failures were Recovery projection/502 observations during that runtime instability, outside the Apps refinement.

The production harness remained disabled (`enabled=false`, `destructive_gate=false`, `qualification_owner=false`, zero sessions/principals). No human Owner credentials, test-auth bypass, persistent keys or production configuration were used. Authenticated synthetic-owner qualification is therefore **BLOCKED by the currently disabled production harness**; it was not enabled or bypassed.

### Physical Android and CDP

The repository-established Windows ADB/WSL2 bridge was recreated with the authorized elevated PowerShell helper. Device `RZCW71C09GX` (`SM_S911B`) was authorized; Windows platform-tools reported `37.0.1-15733141`; Chrome was `156.0.8078.47`; CDP attach and the Android Home smoke passed. The candidate manifest, response header and page meta all identified `803c6ae1fbc9bcfec60a3e255a4f7e3c57d0a517`.

Exact-SHA physical Apps UI qualification passed for portrait 360×691: Daylight/Black catalog, Manage, nested Action Details, truthful read-only attention/not-ready rendering, no horizontal overflow and safe close/navigation behavior. The broader Android performance matrix retained platform/renderer misses around 41.7–42.1ms p95; the Apps Manage section-switch sample was 16.8ms and passed the gate, and nested Action Details was 16.8ms with one target miss but no hard-gate violation. The run also stopped at the existing refresh-indicator interaction boundary. The three-run baseline-normalized attempt was **BLOCKED** when the Server Phone restart budget prevented candidate tunnel readiness; no baseline was fabricated. The PR #588/#589 stop decision is to retain the absolute target misses transparently and stop Apps optimization because no stable, attributable PR #629 application regression was established.

### Accessibility and interaction outcomes

Axe and mocked accessibility suites passed in the relevant Daylight/Black matrix. Manual review covered visible focus, tab/panel relationships, arrows/Home/End, move/resize/reset semantics, nested Details Escape/focus return, status/alert/disclosure semantics, reduced motion, 44px practical targets, 200% reflow and Black contrast/surface parity. The physical Android UI pass confirmed touch layout and no horizontal overflow. Screen-reader certification and an independent human assistive-technology audit were not claimed.

### Documentation and residual quality gates

After source, mocked/browser, visual, live read-only and physical qualification, `task lite:docs:generate` completed successfully, including contracts, platform/runtime projections, parity, architecture, knowledge and Codebase Map generation. The Graphviz preservation correction was part of the late source-owned fix. `task lite:docs:check` and `task lite:check` remain the final commands to run after this addendum/Taskfile edit and are recorded in the final PR evidence.

The historical exact-head CI run `40100729814` tested `803c6ae1fbc9bcfec60a3e255a4f7e3c57d0a517`: isolated Dev PC and UI performance jobs passed, while `quick-and-docs` exposed the README SVG deletion defect. A new exact-head CI run is required after the final documentation/generator commit; no older run is presented as final green CI.

### Rollback and restoration

Rollback is a reviewed revert of the final feature-branch commits; `main`, production data, device identity and credentials were not changed. The Server Phone remained on clean `main`; final checks must confirm that state, PM2/API/NATS health, disabled harness, no candidate tunnel and no disposable authority. PocketLab-owned Android/CDP resources created for qualification must be removed by their established cleanup helpers while unrelated ADB mappings remain untouched.

### Final status ledger

**QUALIFIED:** source/unit, mocked Apps/Azure, shared geometry/Devices, Storybook, reviewed visual baselines, exact-SHA physical Apps UI and documentation generation (subject to the final checks below).

**BLOCKED/PARTIAL:** repository lint configuration, permissive typecheck script, authenticated synthetic-owner live reads, three-run normalized Android baseline, broader Android absolute frame target and transient Server Phone runtime stability. These limitations do not authorize merge, release or deployment.
