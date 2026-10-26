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
