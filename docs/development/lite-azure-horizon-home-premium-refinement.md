# Pocket Lab Lite — Azure Horizon Home Premium Refinement (P0–P6)

> **Status: SOURCE AUTHORED — NOT QUALIFIED.** Tests, builds, linters, accessibility scans, visual snapshots, performance runs, documentation gates, CI repair and physical Android checks were **not** executed in this source-only session.

## 1. Objective and exact provenance

- Repository: `dexter-lab-ctrl/pocket-lab-lite`
- Authoritative starting branch: `main`
- Resolved baseline SHA: `1b249be9fbb2f3bf7a1d898d8c8f282c4bfbe25a`
- Implementation branch: `feat/azure-horizon-home-premium-refinement`
- Scope: P0–P6, desktop, mobile, installed-PWA-compatible layout.
- PR status: draft and unmerged until a separate qualification/finalization session.
- PR #645: **merged into main before this branch was created**. Its shared controls are on the authoritative baseline.
- No merge, release, `dist.zip` creation, production deployment or runtime mutation was authorized.

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

The following are source-inspected, not runtime-validated:

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
| `LiteDetailsPanel`, `LiteSheet`, `LiteDesktopPanelControls` | `src/lite/LiteOverlay.jsx` | Reused unchanged |
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

**CSS cascade decision:** old Home CSS contains legacy palette fallbacks and presentation rules. Deleting those wholesale could break other screens or historical variants. The new `homePremiumRefinement.css` is imported last and targets `.lite-home-refined` and `.lite-home-panel-layer` only. No broad theme-specific padding, new hardcoded color, new global `!important` or duplicate theme provider was added. Consolidation of proven-dead legacy selectors is deferred until source and screenshot qualification.

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
| #645 | `LiteDesktopPanelControls`, `LiteSheet` mobile controls; shared `LiteTechnicalDetails` / `LiteHistorySection` chevrons | Direct shared overlay; disclosure reference | Home already inherits desktop/snap controls; Home attention now uses matching chevron | Small compatible Home disclosure extension |

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
- Responsive layout and accessibility compliance are **not yet validated**.

## 11. P6 — authored qualification assets (NONE EXECUTED)

| Asset | File | Coverage | Status |
|---|---|---|---|
| Flow node authority unit tests | `src/lite/components/HomeWorkspaceFlow.test.jsx` | Node truth, unknown, saved, checking | AUTHORED — NOT EXECUTED |
| New component contracts | `src/lite/LiteHomePremiumRefinement.test.jsx` | Destinations, attention, chevron, focus return, review, haptic delegation | AUTHORED — NOT EXECUTED |
| Mocked Playwright | `tests/e2e/lite-home-premium-refinement.spec.ts` | 320/390/768/1280/1440, themes, overlays, keyboard, Axe, stale/offline | AUTHORED — NOT EXECUTED |
| Performance interaction | `tests/e2e/lite-home-command-performance.spec.ts` | Mobile snap against **existing** budget helper | AUTHORED — NOT EXECUTED |
| Storybook state fixtures | `src/lite/LiteHome.stories.jsx` | Ready, attention, critical, running, partial, offline/saved, unknown, loading, nested panels, large text | AUTHORED — NOT EXECUTED |
| Visual baseline candidates | Playwright `test.skip` placeholder | Light/Dark Home candidate screenshots | **NOT CAPTURED — NOT VALIDATED** |
| Physical Android/PWA | Separate planned operator session | Frame smoothness, safe areas, IME, battery/RAM, haptic capability | NOT QUALIFIED |

**No builds, tests, syntax checks, lint, accessibility scans, visual checks, performance measurements, contract checks, docs gates or physical device qualification commands were executed.** GitHub Actions may run naturally after push/PR; no manual reruns or CI repairs are authorized here.

## 12. Later qualification: commands (NOT RUN IN THIS SESSION)

From a **separate** developer-PC session, with the branch checked out and dependencies installed:

```bash
git status --short
git diff --check origin/main...HEAD
npx vitest run src/lite/components/HomeWorkspaceFlow.test.jsx src/lite/LiteHomePremiumRefinement.test.jsx
npx vitest run src/lite/LiteHomeScreen.test.jsx src/lite/LiteHomeAzure.test.jsx
npm run build
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-premium-refinement.spec.ts --project=mocked-desktop --project=mocked-mobile
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command.spec.ts tests/e2e/lite-home-panel-flow-scroll.spec.ts --project=mocked-desktop --project=mocked-mobile
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-home-command-performance.spec.ts --project=mocked-mobile
```

Storybook manual scenario review must examine the new Premium stories under both themes; inspect panel width at 380px and 660px, Compact/Medium/Expanded, touch targets at 320px, keyboard/focus on nested Back and close, safe-area/keyboard/IME, history and empty states. Take separate **candidate** screenshots only in qualification; compare and explicitly approve baselines, not blindly promote them.

Performance work must separately capture cold/warm Home first paint, Refresh, opening workspace/activity panels, section switch, moving/resizing a desktop panel, Compact/Expand, bounded activity rendering, memory and low-power Android frame times. Retain PR #588/#589 thresholds and environmental assumptions. Real Android/Termux validation and source provenance must be separately authorized, safe and non-destructive.

## 13. Risks, intentionally preserved behavior and deferred work

- **Unvalidated CSS specificity:** Legacy `src/index.css` and historical Home layers remain. Source inspection identifies the new final scoped layer as owner, but visual geometry needs real browser review before it can be considered proven.
- **Shared component regression risk:** The optional chevron extends a shared component backward compatibly; qualification must confirm other tabs' behavior is unchanged.
- **Panel focus/scroll:** New focus-to-last-selected behavior requires mobile browser and screen-reader testing; portal scroll locks and IME are not runtime-qualified.
- **Source truth:** The generic Services diagram node is deliberately unknown. If future backend models publish an authoritative aggregate service health record, it can be wired in a separate contract-backed change.
- **Haptic capability:** Delegated haptics are optional and browser dependent. No vibration was tested on a real device.
- **Storybook and tests:** All are authored fixtures, not evidence of passing.
- **Visual baselines:** None generated, accepted or updated; skipped placeholder remains pending.
- **Generated documentation and CI:** No docs generation, CI correction or green status asserted.
- **Performance:** No before/after measurement and no Android profile; reported benefit is an expected design outcome, not a verified improvement.
- **PWA offline:** Home remains read-only on saved/offline states; no browser write queue is added.

**Final disposition: SOURCE IMPLEMENTATION AUTHORED — QUALIFICATION DEFERRED — DRAFT PR OPEN — NO MERGE OR RELEASE AUTHORIZED.**
