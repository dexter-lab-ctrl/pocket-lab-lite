# Azure Horizon Recovery Center — source implementation and qualification handoff

> **AUTHORED — NOT RUN.** Implementation-only session, 2026-11-05. No source check, test, build, lint, browser run, screenshot, CI re-run, runtime check, deployment, merge or release was performed. This document records source edits and planned verification, **not** a passed qualification.

## Provenance

- Repository: `dexter-lab-ctrl/pocket-lab-lite`
- Starting `main`: `a734c8dc78c20ca489b4ce28cc64191742bc729f`
- Target: `feat/azure-horizon-recovery-center-revamp` → Draft PR → `main`
- Implementation: targeted Recovery presentation, one optional shared history-open prop and one optional shared snap-haptic prop. No backend API, worker, restore executor or authorization rewrite.
- Source authority: current GitHub `main` and the actual PR branch. Historic handovers are context only.

## Source-backed P0 audit and CSS ownership

The prior Recovery implementation already provided `LiteRecovery.jsx`, `RecoveryManageSheetLazy.jsx`, `RecoveryBackupHistory.jsx`, `RecoveryJourney.jsx`, `RecoveryPremiumTimeline.jsx`, `recoveryPremiumView.js`, `recoveryPremium.css`, `RecoveryConfirmSheetLazy.jsx`, FastAPI summary/details separation, XState `useLiteRecoveryFlow`, the shared `LiteSheet` portal and desktop geometry. P0 retained these. The default Journey had a four-by-large educational grid and Recent Activity could show three events. Restore placed Verify/Preview/Restore together before a guided selection. These were presentation gaps rather than proof of a backend capability gap.

Recovery-only new surface styling lives in `src/lite/recovery/recoveryPremium.css`, using `--azure-surface`, `--azure-raised`, `--azure-text`, `--azure-muted`, `--azure-border`, `--azure-strong-border`, `--azure-accent`, `--azure-info`, `--azure-success`, `--azure-warning`, `--azure-danger`, `--azure-focus`, `--azure-selected`, `--azure-shadow`, `--azure-radius-card`, `--azure-radius-control` and `--azure-spacing-card`. Daylight/Dark/System change token values, not geometry. Legacy Recovery styles remain for pre-existing details and require computed-style review; they were not broadly rewritten. Older fallback colors and `!important` declarations outside these new components were not comprehensively deleted. **CSS ownership is refined, not proven conflict-free.**

## P0–P7 implementation ledger

| Phase | Source-authored work | Qualification |
|---|---|---|
| P0 | Read Recovery, shared overlay/snap/geometry/haptic source and relevant Azure Horizon PR descriptions; identified high-density overview and restore navigation gaps | NOT RUN |
| P1 | Centered Recovery Center hierarchy, Apps-aligned `--azure-spacing-card` and semantic-token hero/grid | NOT RUN |
| P2 | Compact four-stage readiness and one-record recent activity; focused stage explanation via `LiteSheet`; no fabricated history or completion | NOT RUN |
| P3 | Manage Backup/Restore/Protection/History retained; Backup Locations and Apps progressively exposed; native Restore Assistant steps | NOT RUN |
| P4 | Presentation-only Choose → Preview → Safety → Confirm; existing XState/FastAPI dispatch, restore-point ID and matching-preview checks preserved | NOT RUN |
| P5 | Timestamp-sorted Recovery Point Library, intent-open selection in Assistant, selected-only actions in History, existing database/app protection and location surfaces retained | NOT RUN |
| P6 | Recovery-only theme styles, 320px stacking, reduced motion; shared `useMobileSheetSnap` 35/72/94 ratios; desktop Manage Move/Resize/Reset; optional haptics | NOT RUN |
| P7 | Authored Vitest, Storybook states, Playwright theme/geometry/snap, WCAG AA/contrast and restore-request guards. Existing visual spec navigation updated; screenshots untouched | NOT RUN |

## Reuse and provenance (actual source)

| Earlier PR | Existing source | Recovery integration | Classification |
|---|---|---|---|
| #606 | `src/lite/LiteUi.jsx`, `src/lite/LiteOverlay.jsx` | `LiteButton`, `GlassCard`, `StateSurface`, `LiteSheet`, focus/escape portal | REUSED |
| #622 | `src/lite/theme/azureHorizonTokens.css` | Daylight/Dark/System semantic colors and spacing | REUSED |
| #623 | `src/lite/components/useDesktopManageGeometry.js` | Existing Recovery Manage Move/Resize/Reset and clamping | REUSED |
| #629 | Shared Azure Horizon Apps UX conventions | Limited geometry/feedback alignment, no Apps code copied | PATTERN REFINED |
| #634 | `src/lite/components/useMobileSheetSnap.js`, `mobileSheetSnap.css` | Existing `LiteSheet mobileSnap`, responsive Recovery opt-in and optional control haptics | REUSED |
| #635 | Existing Apps management visual geometry | Recovery-only row, grouped navigation and details composition | PATTERN REFINED |
| #636 | `--azure-spacing-card`, `--azure-radius-card` in shared tokens; Apps theme parity convention | Same Recovery spacing across themes | REUSED |
| #637 | Native App Library / management workspace pattern | Progressive Backup Locations and Apps details | PATTERN REFINED |
| #638 | Home summary-first native composition | Protection hero → two secondary sections | PATTERN REFINED |
| #639 | Access Center focused details pattern | Managed navigation → on-demand recovery details | PATTERN REFINED |
| #640 | `src/lib/liteNativeFeedback.js`, `LiteButton` | Existing manual haptics retained; Recovery navigation and snap controls opt in | REUSED |
| #641 | Shared overlay theme and detail layout refinements in `LiteOverlay`/Azure styles | Recovery panels continue to use theme-bearing portal; mobile header layout scoped | REUSED |
| #642 | Native Rules Center information hierarchy and PR presentation | Source-story organization; professional Draft PR structure only | PATTERN REFINED |

**Important:** A design *pattern* reference is not a claim that code was copied from that PR. The source paths above are authoritative for actual reused components. Reuse is still unqualified on physical devices.

## Protection and safety boundaries

- The PWA does not run restic, shell, NATS, PM2, restores or database operations.
- All writes still use `liteApi` → FastAPI → backend workers and existing authorization/guard logic.
- `useLiteRecoveryFlow` remains the only guided recovery state machine; new Assistant controls are presentation state only.
- Clicking readiness or an Assistant step never dispatches work.
- A restore requires a selected backup ID, verification, a current **matching** preview, available destination, explicit confirmation, live/backend-safe state and backend execution/checkpoint/health validation.
- Unknown, stale, saved and unavailable data never authorizes a restore.
- Readable history is distinct from snapshot fallback records; absent counts never imply zero.
- No raw secrets, credentials, paths, command payloads or evidence are newly exposed.

## Interaction and geometry

The shared `LiteSheet` controller owns mobile drag/keyboard size transitions (`compact=.35`, `medium=.72`, `expanded=.94`); the Recovery-only media query switches the opt-in at 700px. The mobile grip resizes, never dismisses. All existing close/escape/focus restoration are retained. Recovery Manage remains the sole panel with existing desktop draggable/resizable geometry; extending those controls to every nested detail is **not claimed**. Shared `LiteSheet` gained opt-in `snapHaptic` defaulting to false, so other tabs do not change.

## Authored qualification (DO NOT EXECUTE IN THIS SESSION)

- `src/lite/recovery/RecoveryRestoreAssistant.test.jsx`: presentation-only navigation, preview identity, stale/unknown guards, activity limit.
- `src/lite/recovery/RecoveryAzureHorizon.test.jsx`: existing component assumptions adjusted for compact activity.
- `src/lite/recovery/RecoveryCenter.stories.jsx`: verified, no backup, unverified, preview, unavailable, active, failed, completed, offline, stale, partial, guard, empty/populated history, confirmation, responsive and reduced-motion fixtures.
- `tests/e2e/lite-recovery-native-center.spec.ts`: 320–1440px, Daylight/Dark/System, mobile snap keyboard/buttons, desktop geometry, no accidental POST restore, WCAG AA including contrast.
- `tests/e2e/lite-azure-horizon-recovery-visual.spec.ts`: source navigation update for the new guided confirmation stage. **Historical visual baselines are expected to need later review. No screenshot generation or approval occurred here.**

### Later qualification order (not run)

1. Inspect the branch diff/source and run `npm run build` and focused Vitest in a Dev-PC qualification session.
2. Run mocked desktop/mobile Playwright, Axe/contrast, theme parity and keyboard/focus tests. Confirm 200% scaling, narrow-width containment and snap/desktop geometry.
3. Inspect visual diffs and deliberately approve or reject new deterministic MSW baselines; do not auto-accept.
4. Run permitted focused CI, then bounded read-only device/PWA observation if approved; exercise protected writes only with a separate authorized safe test plan.
5. Check Android/Termux memory/CPU and real Tailscale/saved-state behavior; do not infer it from mocks.

## Risks and limitations — pending

- **UNVALIDATED** source code, JSX composition, semantic CSS contrast, snapshots and theme parity; no build or test was executed.
- Existing legacy Recovery CSS selectors and background/fallback declarations still require a computed-style cascade audit and cleanup after visual review.
- Existing visual snapshots target the old Recovery layout and may fail until reviewed and updated in an authorized qualification session.
- Overlay focus, 320px + 200% text scaling, mobile keyboard safe area, nested sheet stacking and desktop clamp must be checked in browser/device.
- Selected non-latest backup reconciliation with latest summary and preview state must be specifically exercised under mocked/live-safe records; do not assume a selected historical backup is verified solely by the latest summary.
- Service-worker update blocker remains active during pending writes; confirm behavior during interrupted refreshes.
- The default Manage shell has native navigation but some operational Backup/Protection subsections retain established inline actions. No claim of wholesale control redesign.
- Physical Android performance and external storage/unavailable location behavior were not measured.

**Final status:** Source-authored on feature branch; Draft PR intended; qualification pending; no merge, deployment, release or tag.
