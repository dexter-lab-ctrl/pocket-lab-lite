# Azure Horizon Recovery — P0–P4 engineering record

> **Status: [IMPLEMENTED] source committed / [UNVALIDATED] behavior / [NOT RUN] every check, test, build, screenshot, benchmark and runtime qualification.**
>
> **Important:** This is the implementation-only handoff for the dedicated Codex stabilization session. GitHub commits demonstrate source delivery, not a functioning or qualified recovery product. No Android/Termux recovery operation was performed.

## 1. Objective

Present Pocket Lab Lite Recovery as an understandable, accessible and protected Azure Horizon workspace in Black, Daylight and System appearance. The product questions are: Do I have a verified backup? Is its selected destination ready? Does the same backup have a current matching restore preview? What would restore change? Can the server authorize restoration now? Did the backend report success, rollback or an unknown outcome? The UI must never turn attractive colors or an accepted command into recovery authority.

## 2. Existing Recovery architecture

```text
React/Vite PWA (read-only projections, user intent, confirmation)
  → Caddy same-origin proxy
  → FastAPI /api/lite/* (authorization, validation, authoritative recovery state)
  → NATS/JetStream
  → worker/agent/supervisor (restic, checkpoint, database staging, restore, rollback)
  → sanitized events, evidence and backend-owned status
  → FastAPI
  → TanStack Query / safe read-only snapshot fallback / Recovery UI
```

No new backend contract or execution engine was introduced. The frontend does not run shell, access NATS directly, keep backend credentials, queue offline privileged writes or claim an operation succeeded before authoritative evidence exists. `src/hooks/useLiteRecoveryActions.js` and `useLiteRecoveryFlow.js` preserve mutation, invalidation, single-flight and XState reconciliation.

## 3–8. Shared implementation evidence and predecessor PRs

Only actual imports or directly used styles/mechanisms count as reuse; historical PR membership is not proof of current behavior.

| Reference | Verified current source | Recovery reuse | Qualification |
|---|---|---|---|
| #606 shared controls | `src/lite/LiteUi.jsx`, `src/lite/LiteUx.jsx`, `src/lite/LiteOverlay.jsx` | `PageHeader`, `GlassCard`, `LiteButton`, `StatusBadge`, `StateSurface`, `LiteRefreshButton`, `LiteFreshness`, `LiteFlowStatusPanel`, `LiteSheet`, `LiteConsequenceSummary` | [UNVALIDATED] layout and keyboard |
| #622 semantic Azure theme | `src/lite/theme/azureHorizonTokens.css`, `azureHorizon.css` | CSS `--azure-*` semantic surfaces, `html[data-lite-theme]` and portal inheritance, no duplicate provider | [UNVALIDATED] computed contrast |
| #623 shared geometry | `src/lite/components/useDesktopManageGeometry.js`, `src/lite/LiteIdentity.jsx`, `src/lite/LiteOverlay.jsx` | Primary Recovery `LiteSheet` consumes `useDesktopManageGeometry`, `surfaceRef`, `surfaceStyle`, move/resize/reset tools; 701px breakpoint | [UNVALIDATED] pointer, keyboard, visual viewport |
| #624 protected interaction | `src/lite/LiteOverlay.jsx`, `src/lite/LiteUx.jsx` | Existing focus management, nested `LiteSheet`, `LiteConsequenceSummary`, non-draggable `RecoveryConfirmSheetLazy` | [UNVALIDATED] nested focus/authorization |
| #630 operational truth | `src/lite/LiteUi.jsx`, `src/lite/LiteDevices.jsx`, `src/lite/recovery/recoveryPremiumView.js` | Explicit saved/stale/not-confirmed/blocked statuses and backend-derived facts | [UNVALIDATED] live consistency |
| #588 performance contract | `src/lite/liteNavigationRuntime.js`, existing performance scripts and `src/lite/theme/azureHorizon.css` | Reuse conditional/low-motion shared overlays and existing lazy details; no threshold changes | [NOT RUN] instrumentation |
| #589 Android baseline | existing `scripts/dev/lite/run-ui-performance-android-cdp.sh`, Android candidate/baseline scripts | Preserve physical-device measurement and stop conditions; no device access in this PR | [DEFERRED] Android qualification |

**Not consumed:** `LiteProtectedConfirmation` is not claimed as directly reused; Recovery uses its existing separate `LiteSheet` plus `LiteConsequenceSummary`. Shared design *patterns* do not imply importing unrelated Identity authentication components.

## 9. Desktop layout

The existing page shell owns global navigation. Recovery has its existing `PageHeader` with a single Refresh action, followed by one protection hero containing the status, verification time, **Latest backup / Selected destination / Restore preview** facts, and `Back Up Now` / one `Manage Recovery` entry. `RecoveryJourney` and `RecoveryPremiumTimeline` share an aligned two-column grid on wide viewports. A real active operation keeps the existing `LiteFlowStatusPanel`. No Restore landing-page shortcut exists.

## 10. Mobile layout

One-column hero, responsive facts (two columns where readable, otherwise stacked), full-width actions, vertical explanatory Journey, activity and progress. The application shell provides mobile navigation; Recovery does not invent a second bar. `LiteSheet` maintains mobile bottom-sheet behavior below 701px and safe-area spacing. Widths 320/360/375/390/430px, tablets and landscape are authored as future browser cases.

## 11. Azure Black

`src/lite/recovery/recoveryPremium.css` adds narrow scoped `html[data-lite-theme]` semantic declarations for the hero, timeline, journey, Manage, nested confirmation, database details, backup history, location picker and progressive details. The existing token palette is authoritative over historical mockup hex values.

## 12. Azure Daylight

Uses the same selectors and token roles under `html[data-lite-theme="light"]`. Hardcoded Daylight Recovery declarations in `src/index.css` remain as legacy compatibility, but the new Recovery-scoped semantic overrides take priority. Do not duplicate this CSS into another Recovery theme file.

## 13. Portal and System-theme inheritance

`LiteOverlayRoot` renders under `document.body`. `LiteSheet` already syncs its portal compatibility class with `document.documentElement.dataset.liteTheme` by `MutationObserver`; semantic `--azure-*` properties are rooted on `:root`. This retains dynamic System resolution and foreground/background symmetry. Nested confirmations are separate `LiteSheet` instances, not children of the draggable main Manage surface.

## 14. Protection hero

`recoveryPremiumHero()` remains the authority-neutral presentation of reported status. Its verified state label says **Verified backup**, not full Recovery Ready. `recoveryOverviewFacts()` projects three facts without generating backend authorization, fabricated timestamps, verification evidence or a completed restore.

## 15. Backup readiness

No backup → **No backup**; present but not verified → **Needs verification**; verified → **Verified**. Saved, stale or backend unreachable → **Not confirmed**. Verified means integrity was reported, not restoration was authorized.

## 16. Destination readiness

`RecoveryBackupLocation` displays exact known Ready/Available/Low space/Read-only/Missing/Unavailable/Unknown distinctions. **Available is not Ready.** `isRecoveryLocationReady()` explicitly rejects `available` alongside blocked states for restore-impact purposes. Destination changes remain backend-approved; no raw browser filesystem path picker is added.

## 17. Preview readiness

The preview must have its own `preview_id`, a `backup_id` identical to the selected verified backup and a ready/allowed server state. Mismatch, absent, expired, blocked or saved data cannot grant restore eligibility. Preview represents proposed impact only.

## 18. Recovery Journey

`RecoveryJourney` retains the four distinct stages **Back Up → Verify → Preview → Restore**, accessible native buttons and state selectors from `recoveryJourneyStatus`. This is educational status, not an always-running progress bar or new state machine.

## 19. Recent Activity

`RecoveryPremiumTimeline` continues reading `recoveryPremiumActivity`: sanitized backend events; if none, clearly marked current-record fallback instead of invented historic events. Timestamps appear only when reported. `View Activity` opens the existing History section.

## 20. Manage Recovery sections

Canonical `Backup | Restore | Protection | History`, with native tablist/tab/tabpanel, `aria-selected`, `aria-controls`, Home/End and arrow navigation. No unsupported sections or duplicate actions.

## 21. Desktop geometry

`useDesktopManageGeometry({ open, defaultWidth:720, minWidth:400, minHeight:380 })` supplies `panelRef`, `panelStyle`, `desktopPanel`, `startPanelInteraction`, `adjustPanelWithKeyboard`, `reset` and polite status. Pointer gestures are bound **only** to labelled controls, not backup rows or a destructive action; geometry is RAF-clamped and transient. The shared hook owns viewport clamping, keyboard arrows, larger Shift increments, Home reset and responsive reentry. No new window-management dependency.

## 22. Mobile Manage

For widths below 701px, the shared geometry reports `desktopPanel=false`, supplies no desktop coordinates and hides desktop controls. The original `LiteSheet` retains its bottom sheet, focus, Escape behavior, scroll and safe area. Destructive confirmation is always a separate non-movable sheet.

## 23. Backup locations

`RecoveryBackupLocation` retains discovery, selection, forget and safe candidate presentation. A displayed `repository_present` does not independently claim write readiness. Forget means unregistering the location, **not** deletion of files. No new backend endpoint or privileged path selection.

## 24. History

`RecoveryBackupHistory` retains existing cursor/paged loading and `LiteHistorySection`, with explicit selected indicators and readable sizes/times. `recoveryHistoryEligibility` requires selected ID, verification, matching preview, destination availability and live state for Recover. An unrelated backup's preview cannot enable a row.

## 25. Verification

Verification request accepted is not the same as backup verified. The frontend does not synthesize success; status/last-known-safe views stay distinct. Writes are still routed through `useLiteRecoveryActions` and `useLiteRecoveryFlow`.

## 26. Restore impact

`recoveryRestoreImpact` supplies the current matching count, backup identity, inclusion, exclusion and location state. Missing `change_count` means **not reported**, never zero. No broad default promise of PhotoPrism media/device photos is made.

## 27. Protected restore

Restore confirmation presents selected backup identity, verification, matching preview, impact and `LiteConsequenceSummary`. The final button is disabled if impact is not ready. `LiteRecovery.jsx` also rechecks live write, selected backup, verification, matching preview and location before submitting `liteApi.restoreBackup({backup_id,preview_id,confirm:true})`. Cancel never dispatches restore. Backend authorization and confirmation remain mandatory.

## 28. Database recovery

The existing database details component retains backup, verification, preview and restore actions. Its preview is now explicitly bound to the selected database backup ID. `DatabaseRestoreTimeline` displays only known backend `stage_history`, `timeline` or current phase. It does not extrapolate completed phases or invent progress percentages.

## 29. Rollback

Database `committed` displays **Restore committed**. `rolled_back` displays **Rolled back — restore not committed** and `rollback_failed` is an attention-required failure. Never report rollback as a successful restore. Backend controls actual checkpointing, promotion and rollback.

## 30. Evidence and technical details

`RecoveryActionDetailsLazy` continues using `LiteProgressiveDetails`; `RecoveryDatabaseDetailsLazy` holds sanitized technical facts, while `LiteRecovery.jsx` retains reference-value evidence handling. No raw secrets, command payloads, Android private paths or backend logs are newly exposed; hidden history is not eagerly mounted.

## 31. Authorization and protected UX

The frontend cannot mint restore rights. Owner/Enterprise permissions, approval rules, protected confirmations, write blockers and underlying API guards are unchanged. A visually enabled control is not proof of authorization; FastAPI must independently enforce every write. Offline, stale, invalid preview or database maintenance is not converted into live permission.

## 32. Saved-state and stale-state rules

Safe snapshots may provide nonprivileged visibility. `LiteFreshness`, `StateSurface` and disabled-action reasons distinguish last-known-state from current authority. No browser-side recovery queue, background mutation replay or optimistic restore completion.

## 33. Accessibility

Semantic headings, native buttons, 44px minimum shared controls, named Move/Reset/Resize controls, labelled portal dialogs, focus restoration, WCAG-aware semantic colors, keyboard tabs, selected-backup text as well as border, 200% text candidates and reduced-motion rules. **Contrast ratios are NOT CERTIFIED**; Axe, computed contrast and physical zoom are future qualification.

## 34. Performance

A two-column/one-column CSS layout and semantic colors add no new animation dependency. Manage/history/details retain lazy mounting and calm query policies. Geometry uses the existing RAF-throttled hook. No 60 FPS claim; PR #588 budget/stop rules and PR #589 Android baseline attribution remain unchanged and must be applied in the next qualification.

## 35. Unit and component tests authored

- `src/lite/recovery/recoveryAzureHorizon.test.js`: 3 facts; empty/unverified/verified; destination enumerations; preview identity/expiry; saved; impact; journey; event provenance; history permissions.
- `src/lite/recovery/RecoveryAzureHorizon.test.jsx`: Journey, activity, destination selection, protected confirmation/cancel, database preview identity and backend-sourced rollback.
- Existing `recoveryPremiumView.test.js`, `RecoveryJourney.test.jsx` and `RecoveryConfirmSheetLazy.test.jsx` remain in focused task.
- Existing `tests/e2e/lite-recovery-premium-refinement.spec.ts` updated only for revised Restore selected backup wording.

## 36. Storybook and visual scenarios

`src/lite/LiteRecovery.stories.jsx` adds Black/Daylight/System, desktop/mobile, no backup, unverified, destination unavailable, stale, running, rollback, enlarged text and each Manage section via existing MSW stories. `tests/e2e/lite-azure-horizon-recovery-visual.spec.ts` defines 320/360/375/390/430/768/1024/1440px overview, semantic states, all Manage tabs, confirmation, desktop movement/resize and 200% text. **DEFINED — BASELINE CAPTURE AND APPROVAL DEFERRED.** Visual cases cannot be treated as passing or approved.

## 37. Focused qualification tasks

All commands below are **NOT RUN — DEFERRED TO CODEX STABILIZATION**:

```bash
npm run test:recovery:azure:unit
npm run test:recovery:azure:mocked
npm run test:recovery:azure:a11y
npm run test:recovery:azure:geometry
npm run test:recovery:azure:visual
npm run test:recovery:azure:perf
npm run test:recovery:azure:storybook
npm run test:recovery:azure:qualification
task lite:test:recovery:azure:unit
task lite:test:recovery:azure:mocked
task lite:test:recovery:azure:visual
npm run build
npm run test:a11y:states
npm run test:mock-regression
npm run test:perf
task lite:check
```

Visual baseline creation and approval must be a separate deliberate owner-reviewed process. CI runs may start automatically; this implementation session did not inspect their results or remediate failures.

## 38. Deferred qualification

Codex must execute targeted and cross-tab suites, inspect CSS inheritance in Black, Daylight and System, verify protected confirmation focus, history identities, saved and partial states, keyboard and pointer drag, viewport clamps, 320px and 200% zoom, reduced motion, Axe/contrast and nested portal inheritance. Then qualify physical Android rendering, frame time, low-power and baseline-normalized attribution per #589, and backend-authoritative restore/rollback in a controlled disposable test environment. No production restore may be implied from mocks.

## 39. Known risks and incompleteness

- [UNVALIDATED] No tests, builds, lint, formatting, screenshots, performance or runtime results exist for this branch's changes.
- [UNVALIDATED] Legacy `src/index.css` Recovery rules are Daylight-specific; the semantic overrides require rendered computed-style qualification.
- [UNVALIDATED] Pointer/keyboard geometry, focus stacking and restore dialogs may exhibit browser-specific regressions.
- [UNVALIDATED] Backend projection and mock fixture differences may expose edge cases in live location/preview identity.
- [DEFERRED] Actual contrast certification, approved snapshots, Android PWA verification, database rollback and real recovery qualification.
- [DEFERRED] CI remediation; do not diagnose CI in this implementation session.
- [MISSING] New approved visual baseline images (deliberately not generated).

## 40. Rollback

The feature branch is isolated from `main`. Before merge, close the draft PR and leave main unchanged if qualification identifies blockers; no feature-branch deletion or force push is necessary. After any future merge, use a targeted revert PR of the Recovery-related commits instead of rewriting history, and preserve backend recovery state, backup repositories and audit evidence. Never restore/overwrite live user data to roll back CSS.

## 41. Cross-tab compatibility

No Apps/Devices/Identity/Rules/Security API or styling implementation was changed by this Recovery initiative. The PR reuses the same shared desktop geometry as Apps/Devices/Identity rather than duplicating it. Future qualification should rerun their Manage geometry and focus/portal regressions to detect global CSS or overlay interactions.

---

## Implementation and qualification disposition

**[IMPLEMENTED]** Recovery-specific presentation/stylesheet/source tests/Storybook/Playwright/npm/Taskfile definitions are committed to `feat/azure-horizon-recovery-ui`.

**[UNVALIDATED]** No functional, accessibility, visual, performance, database, Android or production-readiness assertion is authorized.

**[NOT RUN]** Every validation/check/build/benchmark command above.

**[DEFERRED]** Codex stabilization; owner review of visual baselines; physical Android baseline attribution; backend-authoritative controlled restore tests.

**MERGE: NOT AUTHORIZED. DRAFT PR MUST REMAIN OPEN.**

---

## 42. Final Narrow Qualification Closure — 2026-10-27

This section is the later stabilization record. Sections 1–41 above remain the historical implementation-only handoff and are intentionally not rewritten.

### Provenance

| Item | Evidence |
|---|---|
| Base | `origin/main` `1b951448f86a0b76fefc2ebeb7c4229090f63fff` |
| Starting feature HEAD | `1a8d40e5d2bf70af5d4577ec158d3b74c245ca5a` |
| Validated functional/UI candidate | `032126e880d6462fec901dc567ef423be7377284` |
| Branch | `feat/azure-horizon-recovery-ui` |
| PR | [#631](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/631), open and draft |

### Dev-PC qualification

- Recovery Azure unit: **52/52 PASS**.
- Premium Recovery unit: **11/11 PASS**.
- Recovery mocked semantic/protected/responsive suite: **90/90 PASS**.
- Premium Recovery mocked suite: **28/28 PASS**.
- Recovery accessibility and enlarged-text suite: **8/8 PASS**.
- Shared geometry/protected-confirmation suite: **24/24 PASS**.
- Recovery interaction performance: **8/8 PASS**.
- Recovery canonical visual suite: **180/180 PASS** across Black/Daylight/System, 320–1440px, Manage tabs, rollback, protected confirmation, moved/resized desktop and 200% text.
- Storybook build, production build and bundle-budget gate: **PASS**. Bundle warnings remain warnings; thresholds were not changed.
- Cross-state accessibility: **36/36 PASS**.
- Recovery legacy visual reconciliation: **12/12 Recovery snapshots reviewed, regenerated and passing**. Apps/Catalog legacy failures were not changed.

### Physical Android and CDP

The repository-owned bridge was refreshed with normal elevated Windows PowerShell/UAC, using Windows `adb.exe` and the persisted CDP bridge state. The authorized device was `SM-S911B`; Chrome was `156.0.8078.47`; the qualified bridge used ADB Chrome port `9222` and the WSL CDP bridge on `19223`. The candidate server used the documented Dev-PC loopback plus read-only SSH transport to the existing Server Phone runtime.

The exact candidate manifest, response provenance, page metadata and CDP target all reported `032126e880d6462fec901dc567ef423be7377284`. Three Android repetitions collected foreground animation frames with the screen awake, battery saver off, battery at 94% and thermal status 0. Recovery overview, scrolling, Manage, History, backup details and safe cancellation interactions rendered on physical Chrome. No restore or production mutation was attempted.

The Android qualifier returned its true absolute-gate miss: 28 reports, 1 absolute target pass, 2 absolute gate passes, 1 `PLATFORM_DOMINATED`, 27 `MIXED`, 0 `APP_INCREMENTAL_COST`, 0 `WITHIN_BASELINE`, and 0 `INCONCLUSIVE`. The Recovery rows were mixed/target-miss evidence only; no Recovery-attributable incremental cost was found against the immutable main comparison. The Owner-gated Identity confirmation surface was not exposed by the authorized runtime and remains unqualified.

### Performance and CI attribution

- The exact candidate Android run preserved the PR #588/#589 thresholds and stop conditions. Absolute frame/commit misses remain a **GATE MISS**, not a pass; the evidence does not justify a Recovery performance rewrite.
- The aggregate mocked performance suite remains **54/56** because the two Devices nested-detail React commit hard gates remain above 28 ms desktop / 25.5 ms mobile. They are outside this PR and were not changed.
- The isolated runtime budget root cause was candidate source and reviewed visual-baseline bytes being included in the disposable runtime tree measurement. The unchanged 256 MiB cap was retained. Old feature accounting observed 287,160,685 bytes versus 268,435,456; patched exact feature accounting measured 6,468,229 runtime-root bytes, while patched main measured 6,450,779. Cleanup and synthetic-principal revocation passed in both lanes.

### Visual, accessibility and safety disposition

The approved Recovery visual changes are limited to the 12 legacy Recovery snapshots listed by the targeted state and overlay tests. Apps/Catalog visual baselines remain an explicit separate maintenance item: the final aggregate results are six Apps state failures and two Apps Manage overlay failures, with Recovery passing. Axe/WCAG checks, focus restoration, keyboard tabs, protected confirmation cancellation, reduced motion, touch targets, mobile overflow and 200% text checks passed for the Recovery coverage. The fixed mobile navigation overlay remains shared-shell behavior; Recovery content remains scrollable and its active tab is discoverable.

The existing synthetic qualification mechanism was used only within the isolated disposable lane. Synthetic principal creation, scoped access and revocation passed; `owner_equivalent: false` remains truthful, so this is not Owner-equivalent live authorization evidence. No real credentials, secrets, production backup, restore, database mutation, service restart or deployment was used.

### Documentation and remaining gates

`task lite:docs:generate` completed and regenerated deterministic contracts and documentation projections. `task lite:docs:check` completed **PASS** with the repository Node 24.16.0 toolchain; the initial no-Node invocation was an environment-only failure and was not treated as a repository failure. `task lite:check` completed **PASS** (exit 0), including 52/62 mocked E2E tests with 10 repository-defined skips, 2/2 accessibility tests, 74/74 documentation browser tests, generated-artifact redaction, contract/platform/runtime/parity/knowledge/enterprise checks and the runtime-network safety gate. The exact post-documentation Git HEAD and exact-head CI run are recorded in the PR qualification update after the normal push of the completed candidate.

The Server Phone remained a read-only runtime consumer on clean `main`; its existing health/readiness and NATS evidence were inspected without mutation. The pre-existing Recovery database projection GET timeout remains documented separately and was not attributed to this UI branch. PR #631 must remain **OPEN — DRAFT — NOT MERGED** pending review of the remaining Android absolute gate, Owner-gated coverage limitation, external CI result and unrelated Apps/Devices findings.


---

## 2026-10-28 — source-only readiness and accessibility refinement

> **[IMPLEMENTED]** Additional targeted source commits authored on `feat/azure-horizon-recovery-ui` from GitHub `main` `b685d2ce3c19f11d590932d7fd37f6e3ad3dc470`.
> **[NOT RUN / UNVALIDATED]** No tests, checks, builds, linting, formatting, static validation, screenshots, baseline updates, CI log investigations, runtime probes, Android/CDP qualification, backup or restore operation were executed **in this session**.
> Earlier qualification and performance observations recorded above are historical records from other commits and must not be applied to this head.

### Scope and implementation inventory

The current `main` already carried the P0–P4 Azure Recovery overview, four Manage sections, shared geometry, three facts, theme styling, source tests, Storybook, Playwright and performance scripts. This increment **does not rebuild or claim authorship of those existing capabilities**. It addresses specific remaining source gaps:

| Scope | Source change | Rationale | Qualification |
|---|---|---|---|
| P0 theme and text | `src/lite/recovery/recoveryPremium.css` | Semantic `--azure-*` for prerequisite messaging, focus-visible inheritance, technical wrapping, portal-safe confirmation, readable 320px typography | [NOT RUN] rendered light/dark/System, 200% text, actual AA contrast |
| P1 overview | `src/lite/LiteRecovery.jsx` | Verification timestamp only if backend `verified_at` exists, is verified and state is fresh/live; no fabricated timestamps | [NOT RUN] mocked and backend parity |
| P2 Manage | `src/lite/recovery/RecoveryManageSheetLazy.jsx` | Explicit per-row action blockers; persistent `aria-controls` targets for inactive tabpanels without eagerly mounting their heavy content | [NOT RUN] keyboard, screen reader, focus, portal |
| P3 destination | `recoveryPremiumView.js`, `RecoveryBackupLocation.jsx` | Only backend `status: ready` with no explicit negative flags counts as ready; `repository_present` no longer implies write readiness | [NOT RUN] real candidates and historical backup data |
| P3 history | `RecoveryBackupHistory.jsx` | A recoverable row must have an explicit ready backup location, matching selected backup, verified state, matching preview and current reads; blocked reasons remain text-visible | [NOT RUN] cursor/history selection and accessibility |
| P3 protected restore | `LiteRecovery.jsx`, `RecoveryConfirmSheetLazy.jsx` | Missing workspace location fails closed; database confirmation independently checks its own backup/preview identity because database recovery does not use a workspace backup location | [NOT RUN] nested modal and server authorization |
| P4 tests | `recoveryAzureHorizon.test.js`, `RecoveryAzureHorizon.test.jsx`, `RecoveryConfirmSheetLazy.test.jsx`, `lite-azure-horizon-recovery.spec.ts` | Explicit ready/available/unknown/missing, database mismatch, disabled explanation and live tabpanel target cases | [DEFINED / NOT RUN] |
| P4 visual/story/performance | `LiteRecovery.stories.jsx`, `lite-azure-horizon-recovery-visual.spec.ts`, `lite-azure-horizon-recovery-performance.spec.ts` | Adds blocked history/restore stories, Black/Daylight mobile blocked-state candidates, synthetic preview/history sampling | [DEFINED / NOT RUN] new baselines unapproved |
| P4 tasks | `package.json`, `tasks/Taskfile.lite.yml` | Bounded readiness/reflow commands plus Taskfile aliases for the current Recovery Azure suites, not a new runner | [DEFINED / NOT RUN] |

### Exact reuse evidence for this increment

| Merged PR | Source of truth in current repository | Reused by Recovery |
|---|---|---|
| #606 | `src/lite/LiteUi.jsx`, `src/lite/LiteUx.jsx`, `src/lite/LiteOverlay.jsx` | `PageHeader`, `GlassCard`, `LiteButton`, `StatusBadge`, `StateSurface`, `LiteRefreshButton`, `LiteFreshness`, `LiteSheet`, `LiteFlowStatusPanel`, `LiteConsequenceSummary` |
| #622 | `src/lite/theme/azureHorizon.css` and `azureHorizonTokens.css` | Existing semantic `--azure-*` token ownership and `html[data-lite-theme]` cascade; no Recovery provider |
| #623 | `src/lite/components/useDesktopManageGeometry.js` | `useDesktopManageGeometry` return values `panelRef`, `desktopPanel`, `panelStyle`, `reset`, `startPanelInteraction`, `adjustPanelWithKeyboard`; no independent geometry engine |
| #624 | `src/lite/LiteOverlay.jsx` and `src/lite/LiteUx.jsx` | Non-draggable nested `LiteSheet` confirmation, protected focus/close, `LiteConsequenceSummary`; not Identity authentication |
| #630 | `src/lite/LiteUi.jsx`, `src/lite/recovery/recoveryPremiumView.js` | Backend-derived `StateSurface`/badges, current vs saved/unknown distinction, explicit disabled reasons |
| #588 and #589 | Existing `tests/e2e/lite-performance-contract.ts`, `lite-performance-helpers.ts`, Android scripts and immutable performance budgets | Existing measurement framework, cheap static paint, lazy panels, RAF-throttled geometry; no rewritten threshold or new dependency |

### Safety distinctions to qualify

1. **Verified backup is not recovery ready.** Backup verification and readiness of the destination, same-backup preview, freshness, owner/Enterprise authorization, server-side guards and protected confirmation remain distinct. On unknown destination `RecoveryBackupHistory` and the workspace Restore controls now fail closed. Backend remains final authority.
2. **Workspace and database restores are different scopes.** Workspace confirmation demands an explicitly ready workspace destination; database confirmation demands its own verified database backup and matching ready preview, subject to existing database guard, maintenance block and FastAPI authorization.
3. **Accepted is not committed.** `useLiteRecoveryFlow` must reconcile backend results. Rollback, rollback_failed, committed and validating_active stages remain distinct and should not be inferred from button clicks.
4. **Empty or outdated data is not a write permit.** No Dexie/local snapshot, expired projection, unrelated backup preview or stale destination should activate a destructive action.
5. **Cross-tab behavior stays untouched.** Neither `useDesktopManageGeometry.js`, `LiteOverlay.jsx`, shared token definitions nor the backend/worker/agent were changed in this increment.

### Deferred qualification — executable only in the future Codex session

Every command below is **NOT RUN — DEFERRED TO CODEX STABILIZATION**:

```bash
npm run test:recovery:azure:readiness
npm run test:recovery:azure:reflow
npm run test:recovery:azure:unit
npm run test:recovery:azure:mocked
npm run test:recovery:azure:a11y
npm run test:recovery:azure:geometry
npm run test:recovery:azure:visual
npm run test:recovery:azure:perf
npm run test:recovery:azure:qualification
task lite:ui:recovery:azure:readiness
task lite:ui:recovery:azure:reflow
npm run test:mock-regression
npm run test:a11y:states
npm run test:perf
npm run build
task lite:check
```

**DEFINED — BASELINE CAPTURE AND APPROVAL DEFERRED:** `recovery-{light,dark}-mobile-blocked-prerequisites-candidate.png` and all new/changed screenshots. Stabilization must review the visual diff intentionally, not update or bless snapshots to silence failures. Check 320/360/375/390/430 px, tablet, 701 px breakpoint, landscape, nested portal theme inheritance, 200% text, keyboard movement/resize/reset and protected modal focus. Measure non-text and normal-text contrast; no WCAG certification exists for this increment. Verify backend contract projections against a disposable authorized environment only after explicit risk review, not production backup repositories.

**Risks [UNVALIDATED]:** Some older backend backup records may lack explicit destination status and will now show blocked instead of presumed ready. Real destination `ready` semantics, history paging, layout overflow, CSS specificity, focus on nested dialogs, Storybook stories, incidental tests and baseline candidates all require future examination. The change intentionally favors refusing a destructive workflow over making a false recovery-readiness claim. The rollback strategy is a targeted revert of these commits before merge; do not manipulate live backup files.

**CI disposition:** CI may start by GitHub automation; no job logs were examined, no workflow reruns or fixes were attempted, no merge authorization is implied. Feature branch and draft PR are reserved for a dedicated Codex qualification session.
