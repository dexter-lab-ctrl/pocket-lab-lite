# Pocket Lab Lite — Azure Horizon Native Safety Center (P0–P7)

**Status: SOURCE AUTHORED — NOT QUALIFIED.** This change set was intentionally prepared without running builds, tests, Playwright, Storybook, accessibility, snapshots, generators, static checks, benchmarks, scanner processes, CI workflows, or physical-device validation. Keep the PR **DRAFT** until an independent qualification session.

**Repository:** dexter-lab-ctrl/pocket-lab-lite
**Source base:** main at SHA ec03d7cfc9c7891043ef2617f15663bd8be1e98b (resolved through GitHub before creating branch)
**Feature branch:** feat/azure-horizon-safety-native-revamp
**Final source SHA:** The branch HEAD on the Draft PR after the final commit (the PR is the authoritative GitHub commit index).
**Scope:** Frontend presentation, Safety-specific styling, Storybook, Playwright, source tests and this handoff.
**Backend, API, scanner, worker, NATS, state schema:** unchanged.

## P0 — Repo-based source and reuse inventory

| Capability | Repo source | Disposition |
|---|---|---|
| Safety view, actions and API hook | src/lite/LiteSecurity.jsx; src/lib/liteApi.js; src/lib/liteViewModels.js | Preserve all backend state and action guards |
| Score/progress/coverage/history comparability | src/lite/security/safetyAzurePresentation.js | Preserve selectors and provenance rules |
| Overlay, focus, Escape, portal theme | src/lite/LiteOverlay.jsx | Reuse LiteSheet |
| Desktop Move/Reset/Resize | src/lite/components/useDesktopManageGeometry.js | Reuse existing pointer and keyboard geometry authority |
| Mobile Compact/Medium/Expanded | src/lite/components/useMobileSheetSnap.js; mobileSheetSnap.css | Reuse LiteSheet mobileSnap; never fork gestures |
| Azure semantic colors and System resolution | src/lite/theme/azureHorizonTokens.css; LiteThemeProvider.jsx | Preserve root-token authority |
| Apps density | src/lite/catalog/appsPremiumRefinement.css | Adapt bounded, token-driven layout |
| Recovery-selected controls | src/lite/recovery/recoveryPremium.css, lite-recovery-manage-tabs | Adapt selected/hover/pressed/focus styling |
| Access grouped index/detail pattern | src/lite/identity/AccessManageNavigation.jsx | Adapt index, Back and persistent desktop navigation |
| Original tests | src/lite/LiteSecurity.stories.jsx; tests/e2e/lite-azure-horizon-safety*.spec.ts | Update expectations to new IA |

### PR reference decisions

- PR #606 — retain shared LiteButton, PageHeader, status, overlay and accessibility foundations.
- PR #622 — retain Azure Horizon theme and semantic tokens.
- PR #623 — retain desktop panel move/reset/resize controller.
- PR #629 — adapt Apps progressive-disclosure and premium density.
- PR #634 — opt into shared three-position mobile snap controller.
- PR #635 — adapt toolbar separation and operational control styling.
- PR #636 — preserve identical cross-theme spacing, geometry and font metrics; no theme-specific layout declarations.
- PR #637 — use native Apps library and progressive-disclosure pattern as reference.
- PR #638 — use native Home summary and action destinations as reference.
- PR #639 — adapt native Access grouping, mobile Back vs Close semantics.
- Recovery — translate segmented selected-state appearance into Safety navigation without converting navigation buttons to ARIA tabs.
- PR #588/#589 — preserve their existing qualification budgets; this PR cannot claim 60 FPS.

## P1 — Before and after

**Before:** overlapping Safety overview, large score, three scan actions, operational story, freshness card, evidence guide, latest check row, outcome, attention/coverage/recent dashboard cards and technical details.

**After — desktop and mobile:**

~~~text
Safety                      Refresh   Manage Safety
Your workspace protection

SAFETY OVERVIEW
Backend-reported state       Reported score (if any)
Selected profile · timestamp · saved/offline
Review items · Coverage · Evidence
[Run Quick Scan] Other checks in Manage Safety

Needs Attention                                        >
Coverage & Checks                                     >
Recent Activity                                       >
~~~

The authored component is src/lite/security/SafetyNativeCenter.jsx, composed by src/lite/LiteSecurity.jsx. Backend-projected facts only. Missing score is shown as unreported, never zero. Missing coverage is unreported, never silently complete. Saved/offline truth remains visible. The Quick action uses the original guarded runSecurityProfile('quick') pathway. Full and App actions are in Manage → Run Checks with their existing confirmations. Existing backend-truthful running timeline and measured/indeterminate progress remain mounted when applicable.

## P2 — Manage navigation, responsiveness, overlays

All nine existing Manage section IDs are retained, with new user-facing labels:

| Group | Visible | Existing ID |
|---|---|---|
| Review | Overview | overview |
| Review | Findings | issues |
| Review | Coverage | coverage |
| Operations | Run Checks | checks |
| Operations | Changes | changes |
| Operations | History | history |
| Operations | Evidence | evidence |
| Operations | Check path | check_path |
| Operations | Technical details | technical_details |

Desktop: left persistent navigation and right selected content when the **panel container** is at least 620px. For smaller containers, index-to-detail navigation. Existing shared desktop handles still own Move, Reset, Resize and keyboard operations. Panel title/controls use independent wrap-safe regions.

Mobile: Manage opens to the grouped index. Selecting a destination opens one detail. **Back** returns to index without closing. **Close** dismisses the entire sheet. Focus follows index/detail transitions; the shared overlay handles modal focus, Escape, portal layering and return.

Original content, API hooks, selected profile, sanitized evidence, coverage and history remain in the original Security component, selected by Zustand UI-only section state. The former horizontally scrolling navigation tablist is replaced with a semantic navigation element and buttons; nested real profile tabs keep tab semantics.

## P3–P4 — Daylight/Dark/System, spacing, icon, panel treatment

The new src/lite/security/safetyCenter.css keeps dimensions identical across appearances: Azure spacing-card, card and control radii, fixed minimum touch targets, typography hierarchy, row gaps, responsive grid and safe-area treatment. Color derives exclusively from the existing --azure-* semantic tokens. Icons reuse installed lucide-react, rendered 18–20px, with decorative icons hidden from assistive technology.

Selected states reuse the Recovery design roles: --azure-selected, --azure-strong-border and inset --azure-accent. Hover/pressed/focus follow --azure-hover, --azure-pressed and --azure-focus. Nested portal content inherits the root resolved theme.

Previously, existing Safety-focused detail styling in src/index.css used hardcoded white gradients, dark text and !important declarations. That source block has been edited in place to use the Azure semantic palette, avoiding a growing stack of overriding patches and leaving other tabs unchanged. Exact visual appearance and contrast still require a browser qualification pass.

Shared LiteSheet.mobileSnap is enabled on compatible Safety modal owners only on mobile: Manage, focused progressive details, findings, remediation, Full Local confirmation and App Check confirmation. The same shared controller supplies ~35% Compact, ~72% Medium and ~94% Expanded; grip drag changes snap state rather than dismissing. Nested content uses modal scrolling, and Close remains independent. No new gesture library/controller introduced.

## P5 — Preserved execution and safety invariants

- Existing Quick, Full Local and PhotoPrism App profiles; current FastAPI/NATS/worker execution; unchanged scanner policies and media exclusions.
- Existing write authorization, duplicate-run concurrency prevention, disabled/offline behavior, confirmations and cancellation eligibility.
- Existing backend-reported stage labels, SSE reconnect/replay, measured progress and indeterminate fallback. No invented completion or percentage.
- Reported score provenance, checked/partial/missing/timed-out/skipped coverage, Lynis/Trivy tool status, saved/offline freshness.
- Finding details and safe remediation guidance, sanitized evidence receipts, profile/app-scoped histories and same-profile comparison guards.
- No frontend shell execution, NATS access, raw logs, secrets, private paths, browser-side queue or fake backend success.

## P6 — Authored regression source inventory

| File | Intended qualification | Current result |
|---|---|---|
| src/lite/security/SafetyNativeCenter.test.jsx | Component truth/disabled/Back/grouping | NOT RUN |
| src/lite/security/safetyAzurePresentation.test.js | Existing provenance/coverage/progress guards | NOT RUN |
| src/lite/LiteSecurity.stories.jsx | Healthy, attention, first run, offline, dark/daylight/system, Manage states | NOT RUN |
| tests/e2e/lite-azure-horizon-safety.spec.ts | Semantic IA, nine sections, keyboard, confirmations, Axe | NOT RUN |
| tests/e2e/lite-safety-native-geometry.spec.ts | Computed-style parity, System light/dark, widths, mobile snap, 200% text, Axe | NOT RUN |
| tests/e2e/lite-azure-horizon-safety-visual.spec.ts | New native visual candidates, state and panel layouts | NOT RUN, NO PNG GENERATED |
| tests/e2e/lite-azure-horizon-safety-performance.spec.ts | Supplemental synthetic first view/panel switch/geometry timing | NOT RUN |

The existing mocked scenarios drive healthy, action-needed, urgent, first-run, scanner unavailable, running Full, App healthy, stale and offline cases. Additional missing fixture-based qualifications to author/extend later: cancelled/failed Quick/App checks, timed-out target, missing evidence receipt, role-denied action, SSE reconnect, nested overlay focus, touch gesture cancellation, non-comparable history and real-device viewports. Do **not** invent a positive capability fixture. Mark unsupported cases as missing until grounded.

### Commands for a future, separate qualification session — DEFERRED, DO NOT RUN NOW

~~~bash
git fetch origin
git switch feat/azure-horizon-safety-native-revamp
npm run build
npx vitest run src/lite/security/SafetyNativeCenter.test.jsx src/lite/security/safetyAzurePresentation.test.js
npx playwright test tests/e2e/lite-azure-horizon-safety.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-safety-native-geometry.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-azure-horizon-safety-visual.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-azure-horizon-safety-performance.spec.ts --project=mocked-desktop --project=mocked-mobile
task lite:docs:generate
task lite:docs:check
task lite:check
~~~

Do not automatically generate/approve baseline PNGs in this source-authoring session. New visual snapshot filenames are future **candidate baselines**, never approved results. Canonical docs or contracts requiring generators remain unrefreshed.

### P7 — Qualification acceptance

1. **Responsive:** 320, 360, 375, 390, 430, 768, 1280 and 1440px. No clipped content, horizontal overflow or toolbar collisions. Resize desktop panel narrower than the 620px container boundary.
2. **Themes:** compare Daylight, Dark, System-light and System-dark computed geometry (padding, margins, gap, typography, border dimensions) plus color/contrast. Dark portal nested details must not display light gradients/dark-on-dark text.
3. **Inputs and overlays:** keyboard/SR focus and Escape; Back vs Close; desktop Move/Reset/Resize; mobile grip/Compact/Medium/Expanded; drag cancellation; screen rotation and keyboard/viewport.
4. **Accessibility:** automated Axe WCAG 2.1 AA, manual focus trap, heading order, 44px targets, no duplicate main landmarks, 200% text, reduced-motion.
5. **Backend truth:** no scores if not reported, no fabricated status/coverage/evidence, no Full/App scan writes before confirmation, offline writes blocked, sanitized outputs.
6. **Performance:** follow PR #588/#589 performance budget/attribution evidence including physical Android/Termux ARM64; supplemental synthetic timings do not prove 60 FPS.
7. **Runtime:** future owner-approved, bounded live qualification on Android PWA over same-origin Caddy and private Tailscale. Avoid heavy scans on live phones.
8. **CI:** GitHub Actions may run automatically after push/PR. This authoring session must not trigger, rerun, investigate, fix or suppress CI.

## Risks, rollback and release disposition

Unvalidated: source integration and build could fail, legacy CSS tokenization may change deep detail icon/border appearance, shared snap and nested portal focus could need refinement, visual baseline composition and text wrapping could differ, static tests may need correction. No production qualification claim.

**Rollback:** leave Draft PR unmerged; closing it leaves main unchanged. For a local preview, switch back to main. After a future merge, revert the focused Safety changes by PR without resetting main, deleting runtime state or changing the backend. Never interpret a screenshot or successful button click as backend execution proof.

**Disposition:** Feature branch and Draft PR only. No merge, release, device deployment, generated artifact promotion, snapshot baseline approval, CI review or validation execution authorized. A future qualification owner must capture actual passing outputs, screenshots, Axe evidence, geometry results and physical Android evidence before promotion.
