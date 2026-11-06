# Pocket Lab Lite — Azure Horizon Safety Center Global UI Hardening (P0–P6)

**Status:** VALIDATED WHERE EVIDENCE PERMITS / PHYSICAL ANDROID BLOCKED
**Repository:** `dexter-lab-ctrl/pocket-lab-lite`  
**Source base:** `main` at `3b0d8ecfd92f65f2ed81569e1dc1a974017736cb`  
**Branch:** `feat/azure-horizon-safety-global-ui-hardening`
**Candidate:** `94cd16356c33fddc20362945588045d7d1dceb37`

> This document is the qualification record for the exact candidate above. Dev-PC source, mocked UI, Storybook, visual review and shared consumer checks were executed. The Safety-only Android workflow reached the repository candidate foreground gate but remained blocked because Android Chrome's `NotificationShade` stayed foreground after the bounded collapse path. No physical Safety UI, haptic or performance result is claimed. The PR remains open and draft.

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

## Qualification evidence — exact candidate

The following results were executed from `94cd16356c33fddc20362945588045d7d1dceb37` on the native WSL Dev-PC checkout. Frontend commands used Node `24.16.0`.

| Area | Command / evidence | Result |
|---|---|---|
| Build | `npm run build` | **PASS** — Vite production build completed; only existing browser-support and chunk-size warnings were emitted. |
| Focused source tests | `npx vitest run src/lib/liteViewModels.test.js` plus the authored Safety/overlay/disclosure/haptics and relevant Safety component files | **PASS** — 13 files, 75 tests; the authored five-file set was 28/28 and the existing relevant set was 45/45. |
| Storybook | `npm run build-storybook` | **PASS** — Storybook 8.6.18 built `storybook-static`; no tracked output was left behind. |
| Safety mocked visual matrix | `npx playwright test tests/e2e/lite-azure-horizon-safety-visual.spec.ts --project=mocked-desktop --project=mocked-mobile --workers=2` | **PASS** — 278/278. |
| Safety unification | `tests/e2e/lite-azure-horizon-safety-unification.spec.ts` targeted functional/accessibility run | **PASS** — 66/66; exact desktop geometry repair rerun was 2/2. |
| Safety unification visual capture | targeted `--update-snapshots` run for shared and nested states | **PASS** — 84/84; reviewed 78 new unification images plus the corrected existing Safety baselines. |
| Accessibility and responsive states | `tests/e2e/lite-accessibility-states.spec.ts` and the Safety combined mocked state suite | **PASS** — 36/36 independent accessibility-state checks; no color rule was disabled. Contrast was checked through the mocked token/computed-style assertions, not a physical screen reader session. |
| Apps shared regression | `npm run test:apps:azure:unit`; `npm run test:apps:azure:mocked` | **PASS** — 19/19 unit and 64/64 mocked checks. |
| Recovery shared regression | `npm run test:recovery:azure:unit`; `npm run test:recovery:azure:mocked` | **PASS** — 52/52 unit and 90/90 mocked checks. |
| Visual review | `tests/e2e/lite-azure-horizon-safety-visual.spec.ts-snapshots/` and `tests/e2e/lite-azure-horizon-safety-unification.spec.ts-snapshots/` | **VALIDATED** — Light, Dark and System representative images were inspected; 54 corrected Safety Manage images, 2 full-scan confirmation images and 78 new unification images are scoped to Safety. |
| Canonical documentation | `task lite:docs:generate`; `task lite:docs:check` | **PASS** — deterministic contracts, Codebase Map, architecture, enterprise/development/production pages, strict MkDocs, backend documentation tests and runtime-network fencing passed; browser projection is 9,951,690 bytes. |
| Repository gate | `task lite:check` | **PASS** — full checked-in gate completed after the late source-contract test repair; 416 backend tests, 590 Vitest tests, mocked E2E, Axe, docs browser tests, build, Storybook, redaction and architecture checks passed. |
| Static tooling | `npm run typecheck`; `npx eslint ...` | **UNVALIDATED / BLOCKED** — the repository typecheck script only prints TypeScript help and exits successfully without a project; ESLint has no discoverable configuration. No threshold or configuration was weakened. |
| Windows Android CDP | `Invoke-RestMethod http://127.0.0.1:9222/json/version`; standard-user `adb devices -l`; `adb forward` | **VERIFIED transport only** — device `RZCW71C09GX`, model `SM-S911B`, Chrome package `com.android.chrome`, Chrome `156.0.8078.79`, protocol `1.3`; the forward was session-owned and removed. |
| Candidate identity | `prepare-ui-performance-android-candidate.ps1` manifest and candidate server | **VERIFIED before navigation** — source SHA, sanitized manifest `source_commit` and candidate server were `94cd16356c33fddc20362945588045d7d1dceb37`; rendered-page identity was not reached. |
| Physical Safety-only UI/performance | `run-ui-performance-android-safety.sh` prerequisite/candidate path | **BLOCKED** — the helper reported `android_notification_shade_open`; `mCurrentFocus` and `mFocusedWindow` remained `NotificationShade` after the bounded collapse attempt. No UI, haptic or frame-budget PASS is claimed. |
| Synthetic Owner | repository qualification harness | **NOT USED** — mocked fixtures were sufficient for the Dev-PC suites; the physical candidate did not reach an authenticated UI. |
| Server phone | read-only SSH Git and PM2 diagnostics | **VERIFIED unchanged for this session** — checkout clean on `main` at `3b0d8ecfd92f65f2ed81569e1dc1a974017736cb`; no source, runtime, PM2 or production data mutation was performed. |

### Scanner truth matrix

The UI now distinguishes not checked, pending, in progress, incomplete, completed, needs review, unavailable/not reported, failed, cancelled, saved/offline and stale states. A partial or unreported result cannot fall through to a fabricated clean conclusion. Coverage is rendered only when the backend projection reports coverage arrays; otherwise the UI states that coverage was not reported.

### Defects found and exact fixes

- `src/lite/LiteSecurity.jsx` now separates backend-reported coverage from profile fallback labels and only renders checked targets from authoritative coverage. `src/lib/liteViewModels.js` exposes explicit `coverage_reported` authority, with regression tests in `src/lib/liteViewModels.test.js`.
- `src/lite/LiteOverlay.jsx` now shares desktop controls while preserving existing consumers' compact reset contract; Safety receives the panel-specific reset name required by its geometry qualification.
- `src/lite/security/safetyCenter.css` scopes the nested dark technical-details surface over the legacy light `!important` declaration.
- `tests/e2e/lite-azure-horizon-safety-unification.spec.ts` is included by the repository Playwright projects, waits for lazy nested content before capture, and uses semantic Compact/Expand controls. The intended Safety baselines were reviewed and updated; unrelated snapshots were not regenerated.

### Physical qualification and performance disposition

The CDP endpoint proves only transport. The candidate server and manifest proved the exact source SHA, but the physical browser could not pass the foreground gate. Therefore:

1. Safety functional qualification: **BLOCKED** for physical Android; Dev-PC mocked functional qualification is **PASS**.
2. Safety physical performance contract: **BLOCKED / NO MEASUREMENT**; no target or hard-gate metric was collected.
3. PR #645 performance regression attribution: **INSUFFICIENT EVIDENCE**; no PR-vs-baseline comparison is claimed.

The notification-shade blocker is an external Android foreground condition, not a source failure demonstrated by the mocked or desktop evidence. It remains a **RESIDUAL / BLOCKER** for full physical qualification. Existing PR #588/#589 thresholds were preserved.

## Risks and boundaries

1. **Shared overlay scope:** `LiteSheet` is used beyond Safety; replacing snap button semantics impacts other opt-in mobile consumers. Do not qualify only Safety.
2. **CSS precedence:** historical rules and `!important` ownership remain extensive. This targeted patch updates confirmed legacy owners and token-backed Safety descendants, not a wholesale index.css rewrite.
3. **Tool-state authority:** a terminal run status does not mean Lynis/Trivy completed. New display intentionally marks missing per-tool results as unreported until evidence is present.
4. **Coverage truth:** only reported skipped lists appear; some profiles may have zero reported scope and must say coverage not reported.
5. **Qualification boundary:** mocked source, Storybook, Playwright, accessibility-state checks, visual baselines and shared consumers are **VALIDATED**; physical Android rendering, haptic behavior, performance metrics, installed-PWA resume behavior and any missing static-tool configuration remain **BLOCKED** or **UNVALIDATED** as stated above.
6. **Backend invariant:** unchanged scanner execution, FastAPI contracts, authorization, NATS/JetStream, SQLite retention, evidence redaction, Tailscale, agent/supervisor and ARM64/Termux runtime.

**Handoff state:** EXACT-HEAD DEV-PC QUALIFICATION COMPLETE WHERE EVIDENCE PERMITS / PHYSICAL ANDROID BLOCKED. PR #645 remains open and draft. No merge, release, deployment, server-phone source change or server-phone runtime change occurred.
