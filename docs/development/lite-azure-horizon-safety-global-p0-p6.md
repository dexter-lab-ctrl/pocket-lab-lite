# Pocket Lab Lite — Azure Horizon Safety Center Global UI Hardening (P0–P6)

**Status:** SOURCE-AUTHORED / QUALIFICATION DEFERRED  
**Repository:** `dexter-lab-ctrl/pocket-lab-lite`  
**Source base:** `main` at `3b0d8ecfd92f65f2ed81569e1dc1a974017736cb`  
**Branch:** `feat/azure-horizon-safety-global-ui-hardening`

> This document records source inspection and targeted implementation, **not** an executed validation report. No tests, builds, Storybook, Playwright, snapshots, accessibility scans, docs generation, runtime checks, physical-device qualification or CI remediation were performed during this implementation session. Preserve the draft PR until separately qualified.

## Objective and non-goals

Unify the existing native Safety screen with mature Azure Horizon Apps presentation and the shared Lite overlay primitives, while preserving every FastAPI-owned Safety status, saved history, scanner lifecycle, protected evidence flow and user permission boundary. This is **not** a scan-engine refactor or an Apps/Devices/Recovery redesign.

## P0: source-backed problem map

| Confirmed source | Observed defect / technical cause | Targeted correction |
|---|---|---|
| `src/index.css`, legacy Security premium portal skin around the `.lite-security-overlay-surface` and `.lite-security-phase3-panel` rules | Fixed light gradient, light header/grip, `#0f172a` text and panel-specific `!important` compete with live portal tokens | Replace the legacy owning declarations with `var(--azure-*)` colors/surfaces and remove the decorative gradient strip |
| `src/index.css`, `.lite-progressive-detail-section::before` and `.is-saved::before` | Decorative circles and checkmark drawn before the semantic Lucide title icon | Remove pseudo-indicators; retain existing named Lucide section icon |
| `src/lite/LiteOverlay.jsx` `LiteSheet` | Safety header rendered a developer-facing “Drag handle to resize” instruction; snap actions step between adjacent states rather than directly selecting the user-facing Compact/Expand mode | Remove instruction; expose explicit `aria-pressed` Compact and Expand selection via the existing `useMobileSheetSnap` state machine |
| `src/lite/LiteSecurity.jsx` `headerActions` | Safety duplicated desktop Move/Reset/Resize UI already owned by `LiteDetailsPanel` | Extract `LiteDesktopPanelControls` in `LiteOverlay.jsx`, reuse for both consumers with `useDesktopManageGeometry` |
| `src/lite/LiteSecurity.jsx` `securityToolChip` and `safetyCenterChips` | Terminal run status could imply individual scanner completion; zero critical findings advertised when scanner output was pending | Use `deriveSafetyStatusPresentation` with explicit run, profile, scanner and coverage authority; render one primary status + scanner group + findings + subordinate safeguard |
| `src/lite/components/LiteHistorySection.jsx` and `LiteTechnicalDetails.jsx` | Show/Hide/extra text controls diverged from established Apps chevron disclosure pattern | One accessible right-side chevron, explicit expanded state, lazily mounted associated region |
| `src/lite/security/SecurityProgressiveDetailsLazy.jsx` coverage branch | UI supplied fabricated fallback coverage categories and repeated “skipped by ... profile” on every exclusion | Render only reported exclusion records, one explanatory parent, grouped separators |
| `src/lite/security/SecurityHistoryLazy.jsx`, legacy `.lite-security-s7-history-row` | History rows lacked a clear status hierarchy and muted text inherited daylight-only style | Persisted status label, recorded summary and timestamp with a responsive Azure-token activity timeline |
| `src/lib/liteGlobalHaptics.js` / `src/lite/LiteUi.jsx` | Delegation and explicit per-button haptics already coexist | Keep documented delegation + manual ownership and remove redundant snap-specific triggering; no haptic on grip movement |

**Important limitations:** The root-cause claims above are grounded in source declarations, not browser measurements; the screenshot-observed appearance has not been re-created or qualified here. Source edit review does not establish contrast compliance or theme correctness on a live display. Existing historical selectors outside this bounded Safety scope remain potential regression sources.

## Exact shared-component and PR provenance

Modes: **unchanged** means consumed as already available; **adapted/extracted** means behavior was factored into a shared source primitive; **visual reference** means no code was copied. PR attribution is based on inspected changed-file inventories and current source rather than descriptions alone.

| PR | Actual file / component or token | Mode | Consumer and rationale | Intentional deviation / risk |
|---|---|---|---|---|
| [#606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606) | `src/lite/LiteUi.jsx` `LiteButton`; `src/lite/LiteUx.jsx`; `src/index.css` shared presentation; Safety shared flows | Unchanged | Existing action/readiness and result presentation preserved inside Safety | Explicit `LiteButton haptic` remains manually owned; delegated haptic must ignore it |
| [#622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622) | `src/lite/theme/azureHorizonTokens.css`, `azureHorizon.css`; `src/lite/LiteOverlay.jsx` | Unchanged token authority, adapted portal presentation | All Safety surfaces, scroll wrappers, nested content, focus, contrast and status color | Color tokens are authoritative; no Safety palette. Source-only contrast requires future measurement |
| [#623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623) | `src/lite/components/useDesktopManageGeometry.js`; `src/lite/catalog/appsPremiumRefinement.css` | Unchanged geometry engine, extracted control markup | Safety Manage + existing `LiteDetailsPanel` share Move/Reset/Resize button implementation | Desktop dimensions remain consumer-specific (`defaultWidth:720,minWidth:420,minHeight:420` for Safety) |
| [#629](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/629) | `src/lite/catalog/appsPremiumRefinement.css` Apps premium refinement | Visual reference | Calm action hierarchy, usable nested details and restrained surfaces | No wholesale Apps CSS migration |
| [#634](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/634) | `src/lite/catalog/appsPremiumRefinement.css` portal/mobile styling | Visual reference | Shared header and modal proportions | Keep Safety navigation/selection and safe-area owners |
| [#635](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/635) | `src/lite/catalog/appsPremiumRefinement.css` Apps geometry polish | Visual reference | Compact row density and responsive geometry | Do not copy Apps-only CSS custom properties into Safety |
| [#636](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/636) | `src/lite/catalog/appsPremiumRefinement.css`; `docs/development/lite-azure-horizon-apps-theme-layout-parity.md` | Unchanged reference contract | Theme-independent width, padding, line-height and control height; Safety uses shared spacing semantics | A later real-browser comparison must still prove parity |
| [#637](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/637) | `src/lite/catalog/appsPremiumRefinement.css` native App Library / Manage | Visual reference | Native-feeling progressive navigation and detail emphasis | App-specific operations untouched |
| [#638](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/638) | `src/lite/LiteAzureHorizon.stories.jsx`, Home native presentation | Visual reference | Home/Safety shared vocabulary and native settings-like groups | Home interaction untouched |
| [#640](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/640) | `src/lite/security/SafetyNativeCenter.jsx`, `LiteSecurity.jsx`, `safetyCenter.css`; `src/lib/liteGlobalHaptics.js` | Extended Safety presentation, delegated haptics reused unchanged | Status hierarchy, nav, dialogs, scan states, sanitization preserved | Haptics never represent backend success; no duplicate explicit snap haptic |
| [#641](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/641) | `src/lite/LiteOverlay.jsx`, `src/lite/components/LiteHistorySection.jsx`, `src/lite/security/safetyCenter.css` | Extended | Preserve resolved-theme portal handling, native mobile header and progressively loaded detail | Replaced developer resize text; changes require requalification of old PR #641 snapshots |
| [#642](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/642) | Rules native UI/UX and overlay composition, `src/lite/LiteOverlay.jsx` rules variant in current source | Shared primitive unchanged | `LiteSheet` still supports Rules variant without Safety-specific fork | Shared snap mode markup affects mobile opt-in consumers |
| [#643](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/643) | `src/lite/devices/azureDevices.css`, Devices native stories | Visual reference | Calm status and information hierarchy | Devices state/runtime ownership untouched |
| [#644](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/644) | `src/lite/LiteOverlay.jsx` and `src/lite/components/LiteHistorySection.jsx`, Recovery consumers | Shared primitive reused/extended in current merged main | Reuse across Recovery and Safety follows current main state | At source inspection #644 is merged; its Recovery behavior remains out of this implementation scope |

**Other existing primitives preserved:** `LiteOverlayRoot`, `LiteBackdrop`, `useFocusTrap`, `useFocusReturn`, `useBodyScrollLock`, `useVisualViewportHeight`, `useEscapeToClose`; `useMobileSheetSnap` (`compact/medium/expanded`, ratios `0.35/0.72/0.94`); `LiteProgressiveDetails`, `LiteTechnicalDetails`, `LiteHistorySection`, `LiteVirtualList`. Desktop keyboard adjustment, mobile grip gestures, stored Safety Manage selection and TanStack/Dexie split reads remain in their existing owners.

## P1–P5 source implementation map

| Phase | Implementation | Files | Behavior to qualify later |
|---|---|---|---|
| P1 | Shared `LiteDesktopPanelControls`, direct Compact/Expand buttons, existing mobile snap hooks, no redundant visible resize instruction | `LiteOverlay.jsx`, `LiteSecurity.jsx` | Focus trap/return; Escape; nested stacking; desktop move/resize bounds; 320px and installed PWA mobile snaps |
| P2 | Original Security legacy portal skin switched to semantic Azure surfaces; additional scoped Safety token treatment of actual scroll/content descendants | `src/index.css`, `security/safetyCenter.css` | Computed Light/Dark/System styles, focus, contrast and layout parity; no intermediate gray canvas |
| P3 | Removed decorative pseudocircles, unified chevron disclosure, semantic section icons retained, restrained nested borders | `src/index.css`, `LiteTechnicalDetails.jsx`, `LiteHistorySection.jsx` | Screen reader labels, one icon per section, keyboard association, reduced motion |
| P4 | Derived scanner/state/finding/safeguard hierarchy using authoritative backend-run metadata; no incomplete green outcome | `safetyStatusPresentation.js`, `SafetyNativeCenter.jsx`, `LiteSecurity.jsx` | Pending, partial, completed, failed, cancelled, stale/offline, profile-scoped tool statuses |
| P5 | Readable persisted activity timeline, grouped quick-profile exclusion list, protected metadata, lazy cursor retained | `SecurityHistoryLazy.jsx`, `SecurityProgressiveDetailsLazy.jsx`, `LiteHistorySection.jsx`, `LiteSecurity.jsx` | Cursor loading, chronological order, long history, safe redaction, no invented coverage |

## Haptic ownership matrix

| Interaction | Owner | Treatment |
|---|---|---|
| Safety native destination, Manage section, profile tabs, secondary links, history/details nav, close button | `installLiteGlobalHaptics` delegated document event | One supported touch/keyboard tap; disabled and busy controls skipped |
| `LiteButton haptic` explicit actions (e.g. native Quick Scan) | `LiteButton` and `data-lite-haptic="manual"` | No delegated duplicate; successful scan is never inferred from a tap |
| Compact / Expand mode | Same delegated button handling | Remove per-snap explicit trigger; one click = at most one haptic |
| Grip drag / continuous resize | `useMobileSheetSnap` / geometry engine | `data-lite-haptic="off"`; no repeated vibration |
| Passive scan progress, read-only status, refresh/polling | No haptics | Non-interactive updates must not vibrate |
| Unsupported browser/device | Existing `liteNativeFeedback` capability guard | No throwing, blocking or artificial fallback |

## Azure Horizon resolved theme / density contract

Colors: `--azure-canvas`, `--azure-surface`, `--azure-raised`, `--azure-border`, `--azure-strong-border`, `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-info`, `--azure-success`, `--azure-warning`, `--azure-danger`, `--azure-neutral`, `--azure-backdrop`, `--azure-focus`, `--azure-hover`, `--azure-selected`, `--azure-panel-shadow`. Sizing: `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card`.

The shared `LiteSheet` layer resolves `html[data-lite-theme]` dynamically, even when open under `document.body`. Surface hierarchy: backdrop → primary overlay → raised rows → semantic status. CSS lengths and responsive grid are the same under Light, Dark and System. No colors or success states are fabricated by theme changes.

## P6 authored qualification assets

- `src/lite/security/safetyStatusPresentation.test.js` — pending/terminal/partial and scanner authority.
- `src/lite/security/SafetyStatusHierarchy.test.jsx` — status structure, scanner grouping, privacy subordination.
- `src/lite/LiteOverlayUnified.test.jsx` — shared desktop toolbar, mobile snap modes and dialog.
- `src/lite/components/LiteDisclosureAzure.test.jsx` — chevron association, lazy content, grouped coverage, protected metadata.
- `src/lib/liteGlobalHaptics.test.js` — delegated portal buttons, dedup, passive/disabled/grip no-op.
- `src/lite/LiteSecurity.stories.jsx` — deterministic Light/Dark/System, pending, complete, unavailable, review, history, technical, 320px, Compact and Expanded variants.
- `tests/e2e/lite-azure-horizon-safety-unification.spec.ts` — mocked-only matrix 320/360/375/390/430/768/1280/1440, portal token binding, responsive containment, scanner truth, keyboard, focus, history/coverage, reduced motion and deferred visual scenarios.
- Existing `tests/e2e/lite-azure-horizon-safety-visual.spec.ts` and its previous baselines are preserved, not regenerated.
- Existing `src/lite/security/SafetyNativeCenter.test.jsx` and `src/lite/components/LiteProgressiveDetails.safety.test.jsx` remain available to future qualification.

## Follow-up qualification — instructions only, not executed

| Target | Qualification scope | Evidence to capture |
|---|---|---|
| Dev-PC mocked | Focused Vitest component/state tests, React Testing Library, Storybook controls, existing Safety/Apps/Recovery regression suites | Test output at exact candidate SHA; no fabricated passes |
| Desktop browsers (1280/1440) | Light/Dark/System open theme switch, CSS computed surfaces, drag/resize/keyboard, focus restore, nested overlays, history cursor | Playwright traces + reviewed visual diffs |
| Responsive tablet (768) | Drawer width, header composition, group density, token parity | Screenshot review and no overflow |
| Mobile 320/360/375/390/430 | 44px touch targets, orientation, virtual keyboard, safe areas, snap states, text zoom, reduced motion | Mocked screenshots and accessibility checks |
| Android Chrome | Physical tap/drag/snap, visual viewport changes, no unexpected haptics | Device screenshots, interaction notes, measured Safety-only render profile |
| Installed Android PWA | Resumed saved/offline state, system theme change in open portal, haptics capability | Installed PWA observation and sanitized evidence |
| Accessibility | WCAG AA contrast, role/name/state, keyboard, live region, focus trap/return, screen-reader check | Axe/Playwright and manual screen-reader evidence |
| Performance | Safety-only open/close/scroll/drag budget on low-power ARM64; compare to preserved product thresholds | Repeatable measurements; do not weaken prior gates |

**For a separate, authorized qualification session only**, typical commands from an isolated Dev-PC checkout might include:

```bash
npm run build
npx vitest run src/lite/security/safetyStatusPresentation.test.js src/lite/security/SafetyStatusHierarchy.test.jsx src/lite/LiteOverlayUnified.test.jsx src/lite/components/LiteDisclosureAzure.test.jsx src/lib/liteGlobalHaptics.test.js
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-azure-horizon-safety-unification.spec.ts --project=mocked-desktop --project=mocked-mobile
```

These commands are **not** executed by this implementation session. Before approving screenshots, manually compare new expected baselines against existing PR #640/#641 Safety and PR #636 Apps parity examples; do not update snapshots automatically. Maintain all quality gates and inspect any later CI failures in their own qualification session.

## Risks and boundaries

1. **Shared overlay scope:** `LiteSheet` is used beyond Safety; replacing snap button semantics impacts other opt-in mobile consumers. Do not qualify only Safety.
2. **CSS precedence:** historical rules and `!important` ownership remain extensive. This targeted patch updates confirmed legacy owners and token-backed Safety descendants, not a wholesale index.css rewrite.
3. **Tool-state authority:** a terminal run status does not mean Lynis/Trivy completed. New display intentionally marks missing per-tool results as unreported until evidence is present.
4. **Coverage truth:** only reported skipped lists appear; some profiles may have zero reported scope and must say coverage not reported.
5. **Source-only state:** tests, Storybook, Playwright, a11y, visual snapshots, performance, production-device behavior and CI are **UNVALIDATED**. Shared focus/gesture/viewport changes warrant explicit manual review.
6. **Backend invariant:** unchanged scanner execution, FastAPI contracts, authorization, NATS/JetStream, SQLite retention, evidence redaction, Tailscale, agent/supervisor and ARM64/Termux runtime.

**Handoff state:** IMPLEMENTATION SOURCE AUTHORED / QUALIFICATION DEFERRED. The draft PR is the review entry point. Do not merge, release or deploy before an independent qualification decision.
