# Pocket Lab Lite — Azure Horizon Home Premium Refinement (P0–P6)

> **Status: PARTIALLY QUALIFIED.** DEV-PC functional, accessibility, visual and build gates pass on the final application commit. Strict Home performance remains `PARTIAL`. The standard-user Windows-local Android CDP transport and the exact-SHA physical Home-only run are now verified without UAC. The physical functional/visual evidence is approved; the absolute Android frame/performance gate remains an explicit failure. Documentation generation is run after this application qualification record.

## 1. Objective and exact provenance

- Repository: `dexter-lab-ctrl/pocket-lab-lite`
- Authoritative starting branch: `main`
- Resolved baseline SHA: `1b249be9fbb2f3bf7a1d898d8c8f282c4bfbe25a`
- Implementation branch: `feat/azure-horizon-home-premium-refinement`
- Initial PR #646 HEAD: `f36cda18d96c5b49df239e6f1dfdf8cd835bd542`
- Qualified application commit: `b9398be4d11b9f1a9bb1781a5a0b0e78c188eb12` (`fix(lite-home): align settings rows with recovery tabs`)
- Physical candidate / PR HEAD before this documentation refresh: `e10a36d74aeb2ad1e2b21fee46e51ea7d6c22172`
- Main SHA observed during qualification: `1b249be9fbb2f3bf7a1d898d8c8f282c4bfbe25a`
- Scope: P0–P6, desktop, mobile, installed-PWA-compatible layout.
- Qualification environment: native WSL2 Ubuntu on the Windows DEV-PC, Node `24.16.0`, Chromium/Playwright mocked desktop and mobile projects, Storybook production build, standard-user Windows PowerShell/ADB preflight.
- PR status: open, draft and unmerged; no Ready-for-Review transition is made while mandatory Android and strict performance gates remain incomplete.
- PR #645: **merged into main before this branch was created**. Its shared controls are on the authoritative baseline.
- The qualified application commit was pushed to GitHub. No merge, release, `dist.zip` publication, production deployment or runtime mutation was authorized.

This is a refinement of PR #638's Command Home, not an information-architecture redesign. The landing view still has one health hero, four destinations (Apps, Devices, Safety, Backups), conditional attention and one recent activity preview. Workspace details and Recent Activity remain separate `LiteDetailsPanel` portals with native grouped navigation.

## 2. Architecture and state-authority boundary

The read/control path remains React/Vite PWA → Caddy same-origin → FastAPI `/api/lite/*` → NATS/JetStream → worker/agent/supervisor → sanitized projection/evidence → FastAPI → UI.

- `buildLiteHomeOverview` and `prioritizeWorkspaceAttention` remain Home status and attention authorities.
- `useLiteQuery` / TanStack Query read the activity projection; safe read-only snapshot and Dexie semantics remain unchanged.
- The backend activity review cursor remains the only authority for marking an item reviewed. The browser does **not** mark review optimistically.
- Home only navigates to Devices for device-related attention; Devices handles identity, device selection and authorized actions. Home has no restart, repair, Tailscale, removal or shell action.
- Zustand, XState, FastAPI, worker execution, NATS, Caddy, scanner, backup, updater and bootstrap contracts are unchanged.
- No secrets, credentials, raw log records, private paths or privileged command payloads are introduced.

## 3. Before → after

| Surface | Before / retained foundation | Authored refinement |
|---|---|---|
| Header and Refresh | One `PageHeader` and `LiteRefreshButton` | Scoped font/spacing, native focus/press tokens; same truthful Refresh callback |
| Hero | Backend-derived `HomeHealthHero` | Semantic status announcement, density/font balance, quiet footer and retained saved/offline messaging |
| Destination cards | Four full-card `GlassCard as="button"` destinations | Uniform Azure density, consistent icon geometry, source-state attributes and 2×2 at 320/390px |
| Attention | Existing `LiteNextSteps`, backend prioritization and navigation | Home-only divided row styling, opt-in shared chevron disclosure with `aria-controls` |
| Recent Activity preview | Latest backend-reported event | Quieter semantic surface and typography; same bounded source |
| Workspace details | Shared `LiteDetailsPanel`, grouped index/details | Focus returns to the last section selected; content exposed as a labelled region |
| Service health | Device → Services → Apps → Safety diagram | Per-node tone only from explicit matching projected area facts; unknown stays unknown; neutral connectors |
| Updates | Existing `LiteReleaseUpdateCard` | Preserved update/check/confirmation ownership; inherits refined panel presentation |
| Diagnostics | Existing `LiteTechnicalFacts` | Group/row density via Home-scoped CSS; no private value expansion |
| Activity details | Existing Attention/Running/Recent/History groups | Contextual domain icons and backend-timestamp-confirmed personal review label |
| Shared panels | PRs #623/#634/#635/#645 geometry | Reuses existing Desktop Move/Resize/Reset, mobile snap and portal controls |
| Light/Dark/System | PR #622 semantic themes and #636 parity | One geometry contract; no theme-dependent Home dimensions |

## 4. P0 — audited component and CSS ownership inventory

The following provenance matrix is source-inspected; runtime results are recorded in §11:

| Element | Source owner | Status / decision |
|---|---|---|
| `PageHeader`, `LiteRefreshButton`, `LiteButton`, `LiteActionRow` | `src/lite/LiteUi.jsx` | Reused unchanged |
| `GlassCard`, `StatusBadge`, `StateSurface` | `src/components/ui.jsx`, exported via `LiteUi.jsx` | Reused unchanged |
| `LiteFreshness`, `LiteTechnicalFacts` | `src/lite/LiteUx.jsx` | Reused unchanged |
| Home hero, destinations, activity preview, workspace sections | `src/lite/LiteHome.jsx` | Existing Home components refined |
| `HomeWorkspaceFlow` | `src/lite/LiteHome.jsx` | Refined with per-domain projected facts |
| `HomeGroupedSections` | `src/lite/components/HomeGroupedSections.jsx` | Refined focus and accessible region |
| `HomeActivityDetails` | `src/lite/components/HomeActivityDetails.jsx` | Refined timeline icons and confirmed review |
| `LiteNextSteps` | `src/lite/components/LiteNextSteps.jsx` | Backward-compatible optional chevron |
| `LiteDetailsPanel`, `LiteSheet`, `LiteDesktopPanelControls` | `src/lite/LiteOverlay.jsx` | Reused; shared mobile snap control wiring was corrected to use the existing incremental contract |
| `useMobileSheetSnap` | `src/lite/components/useMobileSheetSnap.js` | Reused unchanged |
| `useDesktopManageGeometry` | `src/lite/components/useDesktopManageGeometry.js` | Reused unchanged |
| `useLitePanelSectionNavigation` | `src/lite/hooks/useLitePanelSectionNavigation.js` | Reused unchanged |
| `LiteTechnicalDetails`, `LiteHistorySection` | `src/lite/components/` | Reviewed/shared reference, not newly mounted in Home |
| `triggerLiteHaptic`, global delegated handler | `src/lib/liteNativeFeedback.js`, `src/lib/liteGlobalHaptics.js`; `src/main.jsx` | Reused unchanged; native Home controls already participate |
| `LiteThemeProvider` | `src/lite/theme/LiteThemeProvider.jsx` | Preserved; no duplicate provider |
| Azure tokens | `src/lite/theme/azureHorizonTokens.css` | Retained sole palette authority |
| Historic Home styles | `src/index.css` | Preserved because some older selectors are shared/legacy |
| Home import order | `homePremium.css` → `azureHome.css` → `homeActivityEvidence.css` → `homePanelRefinement.css` → `homeCommand.css` → **`homePremiumRefinement.css`** | New final scoped ownership for active Home refinements |
| Shared overlay and Apps premium CSS | Existing imports outside Home | No wholesale copy or change to Apps |

**CSS cascade decision:** old Home CSS contains legacy palette fallbacks and presentation rules. Deleting those wholesale could break other screens or historical variants. The new `homePremiumRefinement.css` is imported last and targets `.lite-home-refined` and `.lite-home-panel-layer` only. No broad theme-specific padding, new hardcoded color, new global `!important` or duplicate theme provider was added. Consolidation of proven-dead legacy selectors remains deferred because the current qualification proves the scoped behavior, not the safety of deleting shared historical rules.

## 5. Shared-component / reference PR provenance

All reference PRs were confirmed **merged** on 2026-11-06 before branch creation. The `main` source, not PR prose alone, was inspected for the named integrations.

| Source PR | Actual component/path or pattern | Reuse type | Home integration | Changed? |
|---|---|---|---|---|
| #606 | `LiteUi.jsx`: `PageHeader`, `LiteRefreshButton`, `LiteActionRow`; `components/ui.jsx`: `GlassCard`, `StateSurface`, `StatusBadge`; `homeAttentionPriority.js`, `homeActivityEvidence.js` | Direct | Existing hero, navigation, attention, activity | Preserved |
| #622 | `theme/azureHorizonTokens.css`, `LiteThemeProvider.jsx`, `components/azureHome.css` | Direct theme authority | Semantic Home surfaces, focus, typography | New Home-only CSS references existing tokens |
| #623 | `LiteOverlay.jsx`, `useDesktopManageGeometry.js` | Direct | Portal focus/scroll/geometry | Preserved |
| #629 | Apps premium alignment/interaction philosophy | Pattern reference | Buttons/card geometry; **no Apps CSS copied** | Home CSS only |
| #634 | `useMobileSheetSnap.js`, `LiteSheet` snap buttons | Direct | Workspace and Activity Compact/Medium/Expanded | Preserved |
| #635 | `useDesktopManageGeometry.js` | Direct | Move/Resize/Reset/clamp | Preserved |
| #636 | Shared Azure spacing tokens and Apps theme-independent density pattern | Pattern + token reuse | Identical Light/Dark/System geometry | New Home density contract |
| #637 | `HomeGroupedSections.jsx`, `useLitePanelSectionNavigation.js` | Direct native navigation reuse | Mobile index→detail→Back, desktop navigation+content | Small Home focus extension |
| #638 | `LiteHome.jsx`, `HomeHealthHero`, `HomeWorkspaceFlow`, grouped Activity and cards | Direct baseline | Exact Command Home IA | Targeted presentation refinement |
| #640 | `liteNativeFeedback.js`, `liteGlobalHaptics.js`, `main.jsx` | Direct existing global delegated haptic support | Native click/keyboard/touch Home buttons, navigation, overlays, review and disclosure | No new engine; preserved |
| #641 | Theme hardening and safe nested-surface presentation | Pattern reference | Final scoped semantic styling | Home CSS only |
| #642 | Rules `LiteDetailsPanel` interaction precedent | Existing shared primitive already consumed | No Rules-specific module imported | No direct Rules code change |
| #643 | Devices authoritative state/navigation boundary | Existing handoff | Home navigates to `devices`; no Home-only device action | Preserved, no Devices module imported |
| #644 | Recovery native panel interaction precedent | Existing shared primitive already consumed | Home navigates to `recovery`; no Recovery workflow duplicated | Preserved |
| #645 | `LiteDesktopPanelControls`, `LiteSheet` mobile controls; shared `LiteTechnicalDetails` / `LiteHistorySection` chevrons | Direct shared overlay; disclosure reference | Home inherits desktop/snap controls; Home attention uses matching chevron; shared Expand now advances Compact → Medium → Expanded | Small compatible Home disclosure extension plus shared snap wiring correction |

**No direct imported reuse is claimed** for unrelated Rules/Devices/Recovery-specific presentation modules, or for `LiteTechnicalDetails` and `LiteHistorySection` in Home's current composition. They were inspected as compatibility and disclosure references.

## 6. P1 — visual, color, density and interactions

`homePremiumRefinement.css` owns final, Home-only geometry and colors under existing `html[data-lite-theme]` ancestry. Semantic tokens used include `--azure-surface`, `--azure-raised`, `--azure-border`, `--azure-strong-border`, `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-selected`, `--azure-focus`, `--azure-hover`, `--azure-pressed`, `--azure-success`, `--azure-warning`, `--azure-danger`, `--azure-neutral`, relevant subtle fills, `--azure-shadow`, `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card` and `--azure-font-ui`.

Home shell and separate portal layer define matching geometry-only density variables; portal descendants do not rely on inheriting a value from the React application tree. Focus styling is token-based and visible. Pointer states are restrained. Reduced motion turns off new transitions. No independent palette or heavy runtime animations are introduced.

All Home controls remain actual semantic buttons. `main.jsx` already installs `installLiteGlobalHaptics()` globally, including portal buttons. Its existing capability detection, reduced-motion behavior, click filtering and 65ms deduplication apply. Home does **not** call `triggerLiteHaptic` again, preventing double feedback. Grip gestures stay owned by shared `LiteSheet` and opt out of global click haptics during drag.

## 7. P2 — Home landing and authoritative handoff

- `HomeHealthHero` continues to distinguish ready, attention, critical, running, checking, saved, offline, partial, loading and unknown.
- Its status eyebrow is a polite status region; neither animation nor presence of a saved record is treated as backend confirmation.
- The four destination cards have explicit source-state attributes for authored tests, but their labels and counts remain derived from `buildLiteHomeOverview` and bounded `status.summary` fields.
- Attention uses the existing priority selector, first three items and optional expanded list. A chevron and `aria-controls` are available **only** through an opt-in backward-compatible `LiteNextSteps` prop.
- For Devices attention: the UI navigates to the authoritative Devices tab. No attempt is made to repair, restart or remove from Home, and no device ID is guessed when the existing navigation contract does not provide focused selection.
- Recent Activity remains a **single** latest event on the landing surface.

## 8. P3 — Workspace details, geometry and service flow

- Existing sections remain Workspace (Overview, Service health) and Maintenance (Updates, Diagnostics).
- Desktop uses actual panel-container queries for the two-column navigation/detail layout; narrow panels fall back to stacked presentation.
- Mobile retains grouped index → focused detail → explicit Back. The prior selected index row is focused when Back is activated instead of always jumping to the first row.
- Each detail content surface has an associated labelled region; rows carry stable `aria-controls` and existing `aria-current="page"`.
- `LiteDetailsPanel` continues to own Escape, focus return, backdrop, body scroll and portal behavior. Shared PR #645 Move/Resize/Reset, Close, Compact/Expand and snap grip are not reimplemented.
- `HomeWorkspaceFlow` retains the Device → Services → Apps → Safety educational sequence. Individual **Device**, **Apps** and **Safety** nodes are now colored only when their matching domain has an explicit projected `tone`. The generic **Services** node remains unknown without an authoritative matching source. Connectors are always neutral, do not animate traffic and never assert network connectivity.
- Saved/checking state intentionally suppresses node-level `ready` presentation. Unknown, offline or absent data is never converted to healthy.
- `LiteReleaseUpdateCard` and `LiteTechnicalFacts` retain existing backend-owned update/readiness and sanitized diagnostics behaviors.

## 9. P4 — Recent Activity and private review

- The four grouped sections (Attention, Running, Recent, History) and bounded data source stay unchanged.
- Timeline rows use Lucide icons mapped only from reported domain names; unknown events get a neutral Activity icon.
- Status labels and timestamps remain source-derived. No inferred percentages, synthetic events or "resolved" claims are added.
- When the backend review cursor returns `last_reviewed_at`, the UI may announce "Review confirmed at". No optimistic review state is added. Saved/offline state and busy state continue to disable write access.
- The same shared overlay navigation, scroll containment and haptic layer applies.

## 10. P5 — responsive, accessibility and low-power controls

- Source contract: 320/390 mobile two-column destination cards; adaptive tablet and wide four-column desktop layout.
- Desktop panels retain their bounded Move/Resize/Reset geometry.
- Mobile uses shared 35%/72%/94% Compact/Medium/Expanded ratios, dedicated grip interaction, visual viewport and safe areas.
- Semantic buttons, visible focus, detail regions, disclosure associations, reduced motion and CSS-only transitions are retained/extended.
- On-demand activity history and nested content remain lazy or panel-gated; no new polling or heavy dependency is added.
- DEV-PC responsive and accessibility qualification passed: the final mocked matrix covered 320, 360, 390, 430, 768, 1024, 1280, 1440 and 1600px representative widths, 200% text, reduced motion, keyboard/focus, mobile scroll containment, System theme resolution and serious/critical Axe checks. The standard-user Windows-local Android CDP endpoint and bounded WSL localhost relay were verified without UAC. The user unlocked the dedicated test phone; the exact candidate then passed the physical Home smoke, foreground-frame prerequisite, Home-only interaction matrix, and screenshot capture. Real haptic output and installed-PWA behavior were not independently instrumented.

## 11. P6 — qualification assets and results

The following results are from the final application commit `b9398be4d11b9f1a9bb1781a5a0b0e78c188eb12` unless noted otherwise. A green result means the command actually completed; authored comments and source inspection are not treated as execution evidence.

| Gate | File / command | Result | Evidence |
|---|---|---|---|
| Focused Vitest | `HomeWorkspaceFlow`, `LiteHomePremiumRefinement`, `LiteHomeScreen`, `LiteHomeAzure`, `LiteHome`, `LiteOverlayUnified`, `useMobileSheetSnap` | **PASS — 7 files / 35 tests** | DEV-PC Vitest output |
| Home functional mocked E2E | `lite-home-premium-refinement`, `lite-home-command`, `lite-home-panel-flow-scroll`, `lite-home-panel-snap` | **PASS — 106 / 106** | `tests/e2e/*.spec.ts` |
| Premium Home mocked E2E | `npm run test:azure:home:premium:mocked` | **PASS — 56 / 56** | `tests/e2e/lite-home-panel-premium.spec.ts` |
| Flow accessibility | `npm run test:azure:home:flow:a11y` | **PASS — 4 / 4** | Black-panel Axe cases in `lite-home-panel-flow-scroll.spec.ts` |
| Shared overlay/haptics and snap | `lite-native-dock-and-haptics.spec.ts` plus `lite-home-panel-snap.spec.ts` | **PASS — 32 / 32** | Shared regression output |
| Premium visual baselines | `npm run test:azure:home:premium:visual` | **PASS — 40 / 40** | `tests/e2e/lite-home-panel-premium-visual.spec.ts-snapshots/` |
| Command visual baselines | `lite-home-command-visual.spec.ts` | **PASS after isolated retry** — initial 61 / 62, exact mobile offline-saved retry 1 / 1 | `tests/e2e/lite-home-command-visual.spec.ts-snapshots/` |
| Production application build | `npm run build` | **PASS — 2,262 modules** | Vite output; existing chunk-size warnings only |
| Storybook production build | `npm run build-storybook` | **PASS** | `storybook-static/` build output (ignored artifact) |
| Strict Home performance | `lite-home-panel-premium-performance.spec.ts`, `lite-home-command-performance.spec.ts` | **PARTIAL** — premium 10 / 12 and command 5 / 6; workspace open/switch cases recorded `long_animation_frame_ms` misses | `.pocketlab-dev/test-results/` and performance evidence output |
| Physical Android Chrome | Home-only candidate runner | **PASS** for exact-source Home functional/visual qualification; **FAIL** for the absolute frame/performance gate (18 / 18 evidence samples missed the 60 FPS target) | Standard-user PowerShell/ADB preflight, candidate manifest and retained screenshot bundle below |
| Documentation and contracts | `task lite:docs:generate`, `task lite:docs:check`, `task lite:check` | **PASS** — generation completed; docs check passed with existing Redocly warnings; full Lite check passed | Generated contracts/docs plus Taskfile output |

The original stale Home unit expectation, an unregistered PR-authored Playwright file, an Axe grep that matched no tests, invalid broad region assertions, the shared snap button's direct Compact/Expanded jump, a Light-theme contrast miss, pointer/legacy-typography visual drift and Home/Recovery settings-row styling divergence were corrected and covered by the gates above.

## 12. Qualification detail, performance attribution and Android boundary

### DEV-PC commands actually executed

The final application commit was checked with Node `24.16.0` and the following commands:

```bash
npx vitest run src/lite/components/HomeWorkspaceFlow.test.jsx src/lite/LiteHomePremiumRefinement.test.jsx src/lite/LiteHomeScreen.test.jsx src/lite/LiteHomeAzure.test.jsx src/lite/LiteHome.test.jsx src/lite/LiteOverlayUnified.test.jsx src/lite/components/useMobileSheetSnap.test.jsx
npm run build
npm run build-storybook
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-premium-refinement.spec.ts tests/e2e/lite-home-command.spec.ts tests/e2e/lite-home-panel-flow-scroll.spec.ts tests/e2e/lite-home-panel-snap.spec.ts --project=mocked-desktop --project=mocked-mobile --workers=2
npm run test:azure:home:premium:mocked
npm run test:azure:home:flow:a11y
npm run test:azure:home:premium:visual
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command-visual.spec.ts --project=mocked-desktop --project=mocked-mobile --workers=2
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-native-dock-and-haptics.spec.ts tests/e2e/lite-home-panel-snap.spec.ts --project=mocked-desktop --project=mocked-mobile --workers=2
VITE_POCKETLAB_PERF_TEST=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-panel-premium-performance.spec.ts --project=mocked-desktop --project=mocked-mobile --workers=1
VITE_POCKETLAB_PERF_TEST=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command-performance.spec.ts --project=mocked-desktop --project=mocked-mobile --workers=1
npm run check:render-budgets
```

All required performance thresholds from PRs #588/#589 remain unchanged. The direct final premium run was `10 / 12`: both workspace grouped open/switch/close cases failed the absolute `long_animation_frame_ms` gate, while activity, move/resize, native scroll and the remaining Home interactions passed. The direct command run was `5 / 6`: only the mocked-desktop workspace grouped interaction failed. Representative failures were `p95=16.8ms`, `gate_smooth=0.9623`, `long_task=0ms`, `loaf=104.3ms` for premium desktop and `p95=16.8ms`, `gate_smooth=0.9683`, `long_task=0ms`, `loaf=98.7ms` for command desktop. A 3-repeat targeted run remained variable (`2 / 3` pass), so this is not a stable green result.

The aggregate `npm run check:render-budgets` result was **FAIL** (`evidence=131`, `gate_failures=7`, `target_misses=41`). It includes pre-existing records for Recovery, Identity, Security and other screens, so it is not used as a Home-only verdict. Current relevant Home records include `mocked-desktop azure-home-workspace-section-switch`, `mocked-desktop command-workspace-open` and `mocked-mobile azure-home-workspace-close` failures or target misses. No performance budget, minimum sample count or suppression rule was changed.

For attribution, clean detached runs of the original PR head `f36cda18d96c5b49df239e6f1dfdf8cd835bd542` and `origin/main` passed the focused workspace interaction and repeated clean runs, while the current WSL candidate is variable across first/cold invocations. This supports an **INFERRED measurement/environment contribution**, but it does not remove the absolute gate failure. The completed Android A/B/A evidence classified one sample as `PLATFORM_DOMINATED`, seventeen as `MIXED`, and zero as `APP_INCREMENTAL_COST`; the baseline itself also missed the absolute target. No PR-specific optimization is claimed and no unrelated screen was changed.

### Standard-user Android CDP preflight

- One authorized device was verified: serial `RZCW71C09GX`, model `SM-S911B`, ADB state `device`; Chrome package `com.android.chrome` was foregrounded and the test screen was woken with the permitted non-privileged ADB key event.
- Repository-supported ADB was `/mnt/c/Android/platform-tools/adb.exe`, version `1.0.41` / `37.0.1-15733141`.
- The required initial `http://127.0.0.1:9222/json/version` check was verified from standard-user Windows PowerShell: Chrome `156.0.8078.79`, CDP Protocol `1.3`, Android package `com.android.chrome` and a localhost WebSocket endpoint were returned. The bounded repository relay exposed that endpoint to WSL on `127.0.0.1:19222` without a Windows listener, firewall rule or portproxy.
- Playwright attached through the relay and the exact final candidate at `e10a36d74aeb2ad1e2b21fee46e51ea7d6c22172` passed the physical Home smoke and candidate identity checks. Before the successful rerun, the user removed the dedicated test phone from secure keyguard; ADB then verified `isKeyguardShowing=false`, Chrome foreground, `mWakefulness=Awake` and `mIsInteractive=true`. The bounded qualifier collected foreground animation frames and completed the Home-only matrix without changing Android security policy or using credentials.
- The repository helper `scripts/dev/lite/prepare-ui-performance-android-cdp.ps1` was inspected and not invoked because its setup path requires Administrator privileges and privileged `netsh`/firewall operations. No UAC escalation occurred.
- The temporary candidate reverse, relay, candidate server and runner were cleaned up. The pre-existing `tcp:9222 localabstract:chrome_devtools_remote` ADB forward was preserved and no reverse mapping remained. No synthetic harness session, phone source edit or physical Home matrix was left running.

Therefore the exact final candidate SHA was served and identity-verified, foreground requestAnimationFrame evidence was collected, and the final Home-only matrix completed. The qualifier retained 11 sanitized physical screenshots covering Home landing, Workspace details, Service Health, Diagnostics, Recent Activity, History and Compact/Medium/Expanded snap states. The broad seven-screen matrix was not run.

The retained manifest is `.pocketlab-dev/performance/android-home-visual-evidence.json`, and the screenshot directory is `.pocketlab-dev/performance/physical-home-screenshots-e10a36d74aeb2ad1e2b21fee46e51ea7d6c22172/`. It records `qualification_scope=home`, `source_commit=e10a36d74aeb2ad1e2b21fee46e51ea7d6c22172`, candidate origin `http://127.0.0.1:18765`, Chrome `156.0.8078.79`, CDP `1.3`, sanitized output, and successful candidate manifest/header/meta identity checks.

## 13. Risks, intentionally preserved behavior and deferred work

- **Android physical performance:** the Windows-local CDP transport, bounded WSL relay, exact candidate identity, foreground frame prerequisite and Home-only interactions are healthy without UAC. The absolute frame/performance gate remains red: 18 evidence samples exceeded the hard render gate and all 18 missed the 60 FPS target. The baseline/A-B/A attribution does not establish a clean PR-specific incremental cost, but it does not justify a green production performance claim.
- **Strict performance:** Home workspace grouped open/switch interactions fail the absolute long-animation-frame gate on this WSL/Chromium run. Main and the clean original PR head passed focused comparison runs, so the observed cause is currently an `INFERRED` environment/cold-start contribution, not a proven PR-only regression; the gate remains unresolved and is not downgraded.
- **Visual retry:** The command visual suite had one first-run 298-pixel mobile offline-saved mismatch; the exact case passed on isolated retry. Premium canonical visual coverage is stable at 40 / 40. This is recorded as a retry-qualified visual result, not a blanket update of unrelated snapshots.
- **Bounded physical scope:** Android Home touch/navigation, safe-area presentation, IME-related snap resizing, grouped navigation, close/reopen, long-history presentation and physical screenshots are approved for the retained run. Real haptic output, installed-PWA behavior and a green thermal/power performance result were not independently established.
- **Server Phone:** Read-only SSH verification found the phone on clean `main` at `1b249be9fbb2f3bf7a1d898d8c8f282c4bfbe25a`, with existing services unchanged. It was not used as a development workspace.
- **Source truth:** The generic Services diagram node remains deliberately unknown without an authoritative aggregate service-health projection. Home does not invent connectivity, repair, restart, recovery, uptime, scan or review success.
- **PWA offline:** Home remains read-only on saved/offline states; no browser write queue or secret storage was added.
- **Documentation/CI:** Canonical docs generation, `task lite:docs:check` and full `task lite:check` passed after the application commit. GitHub checks remain external CI evidence and the PR remains Draft while Android and strict performance are incomplete.

**Final disposition at this document revision: DEV-PC APPLICATION QUALIFIED — STRICT ANDROID PERFORMANCE PARTIAL/FAIL — ANDROID CDP TRANSPORT VERIFIED — PHYSICAL HOME-ONLY FUNCTIONAL/VISUAL PASS — DRAFT PR OPEN — NO MERGE, RELEASE OR DEPLOYMENT.**
