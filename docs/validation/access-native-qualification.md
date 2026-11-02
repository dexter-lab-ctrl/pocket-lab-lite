# Azure Horizon Access Center — P1–P6 qualification record

> [!IMPORTANT]
> **IMPLEMENTED · MOCKED QUALIFICATION PASS · PHYSICAL ACCESS QUALIFICATION WITH DOCUMENTED PERFORMANCE RESIDUALS · DRAFT PR ONLY.**
> This is a qualification record, not a release certificate. The physical Android Access runner completed its complete scoped matrix, but the device did not meet the existing absolute render gates; baseline attribution found no isolated `APP_INCREMENTAL_COST` classification.

## Authority and provenance

| Field | Recorded value |
|---|---|
| Repository | `dexter-lab-ctrl/pocket-lab-lite` |
| Base branch | `main` |
| Initial worktree | Clean `main` at `0fa114f89243334ffa4db084810c34f4c97995b7` |
| Initial feature SHA | `41b8819525a5e0f23a2da9197ec9669215b38585` |
| Feature branch | `feat/azure-horizon-access-native-revamp` |
| Destination | `main` (Draft PR only) |
| Qualified source SHA | `3d0b954f9fb0051869fc2456c2b376309929a405` |
| Candidate manifest / response / page metadata | Exact qualified source SHA above |
| Qualification status | Mocked/browser and source gates passed; physical Access target/gate residual documented below |
| Final Server Phone checkout | `main` at `0fa114f89243334ffa4db084810c34f4c97995b7`; clean; production runtime restored separately |
| Merge / release / deployment | Not authorized; not performed |

The final branch SHA includes the reviewed visual-test tolerance, canonical snapshots, this record, generated documentation and the final qualification commit. It is reconciled in the PR and final engineering report; the physical candidate evidence remains bound to the exact qualified source SHA above.

## Architecture and non-goals

React/Vite PWA → Caddy → authenticated FastAPI `/api/lite/*` → backend authorization and NATS/JetStream → workers/agents/supervisors → sanitized state and audit → FastAPI projections → UI.

The Access Center is presentation-only. It reuses `liteEnterpriseApi.identitySelf`, the current `identityPremiumProjection`, existing mutation functions, platform WebAuthn ceremonies, Identity/Rules authority, owner step-up, confirmation sheets, and Enterprise governance. It introduces **no API contract**, new authorization policy, new data persistence, offline mutation queue, browser-held recovery-code store, frontend NATS access, or shell command execution.

All recovery-code disclosure continues through the existing ephemeral `recoveryCodes` component state and its existing authorized generation and copy flow. Recovery codes must never appear in Storybook/Playwright fixtures, screenshots, activity projections, Zustand, Dexie, or other snapshots. Protected destructive actions remain behind existing confirmation and backend step-up logic. Authenticated stale/saved views remain read-only.

## P1–P6 source map

| Phase | Authored source | Expected behavior |
|---|---|---|
| P1 | `LiteIdentity.jsx`, `identity/AccessCenterSummary.jsx`, `identity/accessCenterPresentation.js` | One backend-derived identity hero, grouped Passkeys/Sessions/Recovery rows, compact sanitized latest activity, conditional Owner attention |
| P2 | `IdentityManageContent.jsx`, `IdentityDetailsContent.jsx` | Focused lists, existing WebAuthn, session/recovery confirmation paths, password management under Recovery |
| P3 | `identity/AccessManageNavigation.jsx`, `LiteOverlay.jsx`, `LiteIdentity.jsx` | Narrow-panel grouped index/section/Back and wide panel navigation/detail; distinct Escape and Close, shared portal geometry and sheet snaps |
| P4 | Existing `LiteIdentityEnterprise.jsx` nested in Manage; Access-specific CSS | Personal Mode avoids directory; Enterprise Owner/Admin/Operator/Auditor/Viewer remain server-owned; role and people details continue through existing functions |
| P5 | `identity/accessCenter.css` | Existing Azure semantic colors, token-driven radius/insets, common geometry across themes, reduced motion, 44px controls |
| P6 | Stories, unit/component tests, Playwright suites, this document | Qualification executed; final results are recorded below |

## Exact reuse and source inspection inventory

| Reference | Existing code / authority | Access integration |
|---|---|---|
| #588 | `tests/e2e/lite-performance-helpers.ts`, `lite-performance-contract.ts`, `docs/validation/ui-performance-qualification.md` | `tests/e2e/lite-access-native-performance.spec.ts`; no threshold changes |
| #606 | `src/lite/LiteUi.jsx` (`PageHeader`, `LiteButton`, `GlassCard`, `StateSurface`, `LiteRefreshButton`); `src/lite/LiteOverlay.jsx` (`LiteSheet`, `LiteDetailsPanel`, focus, portal, scroll lock); `src/lite/components/LiteSafeForms.jsx` | Direct reuse of presentation, accessibility and sensitive confirmations |
| #622 | `src/lite/theme/azureHorizonTokens.css`, `azureHorizon.css`, `LiteThemeProvider.jsx` | Direct reuse of light/dark/system appearance and semantic color contract |
| #623 | `src/lite/components/useDesktopManageGeometry.js` | Existing Access Manage controller preserved; separate instance for nested Details; move/reset/resize/keyboard/clamp |
| #629 | `src/lite/catalog/appsPremiumRefinement.css`, `AppCatalogScreen.jsx` | Summary-first, whitespace, focusable operational details adapted—not PhotoPrism logic |
| #634 | `src/lite/components/useMobileSheetSnap.js`, `mobileSheetSnap.css`, `LiteOverlay.jsx` | `mobileSnap` for Manage Access and nested Access Details only; grip drag, keyboard and sizing controls are shared |
| #635 | `LiteOverlay.jsx`, `AppCatalogScreen.jsx` nested details | Independent Details geometry and toolbar-fenced composition; protected confirmations remain separate |
| #636 | `src/lite/catalog/appsPremiumRefinement.css`, `src/lite/theme/azureHorizonTokens.css` | Shared token insets/radius and theme-independent density; Access-scoped variables only |
| #637 | `src/lite/catalog/AppCatalogScreen.jsx`, `AppManageSections.jsx` | Grouped native index, nested details on small panels, persistent navigation on wide panels; Access-specific composition rather than copying Apps |
| #638 | `src/lite/components/HomeGroupedSections.jsx`, `homeCommand.css`, `LiteHome.jsx` | Small-panel navigation semantics, focusable heading on entry, Back to root, container-query content responsiveness |

No new theme provider, geometry engine, sheet engine, global component library or state framework is added.

### Azure Horizon token usage

| Source token | Access use | Contract |
|---|---|---|
| `--azure-canvas` | inherited page canvas from shared shell | semantic appearance only |
| `--azure-surface` / `--azure-raised` | hero, groups, inputs, directory | colors only |
| `--azure-border` / `--azure-strong-border` | dividers, card outlines, current-session border | colors only |
| `--azure-text` / `--azure-muted` | identity and supporting content | colors only |
| `--azure-accent` / `--azure-accent-subtle` / `--azure-selected` | navigation, icons, selection | colors only |
| `--azure-success` / `--azure-warning` / `--azure-neutral` | backend-derived readiness | never color-only |
| `--azure-focus` | focus indicators | accessibility |
| `--azure-hover` | hover and press affordances | semantic appearance |
| `--azure-shadow` | hero elevation | semantic appearance |
| `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card` | common size/shape/insets | **same across all appearances** |

`accessCenter.css` adds only three **theme-independent spacing aliases** (`--access-gap-sm/md/lg`). No new palette or Dark-only geometry override is introduced. System preference resolves via the existing theme runtime; at identical resolved appearance, density rules remain unchanged.

### Recovery-inspired Access navigation

The visual reference is the existing `RecoveryManageSheetLazy.jsx` tablist (`.lite-recovery-manage-tabs`) and its Azure Horizon ownership in `src/lite/theme/azureHorizon.css`. Access does not import Recovery or make Recovery depend on Access. Instead, `identity/accessCenter.css` applies the same semantic raised surface, border, radius, gap, active/hover treatment, muted supporting text and 44px interaction target to the native grouped Access index. The Access information architecture remains its own grouped index → section flow with a separate Back action, rather than restoring Recovery's horizontal tab strip. The mocked visual matrix covered desktop, narrow panels, mobile grouped settings, Daylight, Black and System appearances.

### Shared mobile dock correction

`LiteApp.jsx` now owns the mobile dock at the shared shell layer: the dock is portaled to `document.body`, measured with `ResizeObserver`, and publishes its actual height through `--pocket-nav-dock-height`. Azure Horizon shell CSS anchors it to the visible bottom safe area and uses the measured height for `pocket-main`'s bottom inset. Workspace docks remain hidden through the existing workspace-specific selector. This avoids per-tab padding workarounds and preserves desktop side navigation. Mocked geometry and Access physical checks verified a stationary bottom dock, safe-area spacing, scroll reachability and overlay coexistence; focused smoke checks covered Home, Apps, Devices, Access, Security, Rules and Recovery.

## Native Manage, overlay, and mobile sheet contract

Mobile Manage begins at the grouped index. Selecting a row opens a focused section and moves focus to its heading. **Back** restores the index; **Close** dismisses the overlay. Escape performs narrow-panel Back before Close, while nested Details and confirmations retain top-of-stack Escape behavior. A desktop Manage panel uses the existing `useDesktopManageGeometry` and a container query (not merely viewport width). The existing Move/Resize/Reset controls, clamping and keyboard handling remain in their original controller.

| State | Approximate visual viewport height | Existing controller authority |
|---|---:|---|
| Compact | 35% | `MOBILE_SHEET_RATIOS.compact` |
| Medium | 72% | `MOBILE_SHEET_RATIOS.medium` |
| Expanded | 94% | `MOBILE_SHEET_RATIOS.expanded` |

`LiteSheet` opts `mobileSnap` into **Manage Access**; `LiteDetailsPanel` opts it into selected passkey, session, recovery, access activity, person, role, authorization, mode and explanation Details. These share the same nested Details portal and controller. No gestures attach to rows, input fields, actions or destructive buttons. Grip, snap size buttons and keyboard Arrow/Page/Home/End handling are owned by the shared controller.

**Intentional exceptions:** Passkey rename form, confirmation sheets, Enterprise destructive confirmation and platform WebAuthn dialogs **do not opt into snaps**. They keep their established focus, confirmation, security and browser ceremony behaviors.

## Qualification matrix — observed results

| Candidate | Command / location | Result | Evidence and qualification boundary |
|---|---|---|---|
| Pure presentation and Access components | `npx vitest run` over presentation, summary, Horizon, premium-view and mobile-snap tests | **PASS — 33 passed** | Current source contracts, redaction, grouping, stale/offline truthfulness and snap controller behavior |
| Vite build | `npm run build` with Node 24.16.0 | **PASS** | Candidate build embedded `3d0b954f9fb0051869fc2456c2b376309929a405` in the build metadata; only existing Browserslist/chunk-size warnings remained |
| Authored Access browser qualification | `lite-access-native.spec.ts` plus `lite-azure-horizon-identity.spec.ts` and `lite-identity-premium-refinement.spec.ts`, mocked desktop/mobile | **PASS — 158/158** | Navigation, role visibility, saved/offline read-only behavior, focus, Back/Close, nested Details, snaps and regression contracts |
| Access visual qualification | `lite-access-native-visual.spec.ts`, mocked desktop/mobile | **PASS — 174/174** | Reviewed Daylight/Black/System, 320/360/390/430/768/1024/1440 widths, states, Manage geometry, nested Details, confirmation and snaps; 198 reviewed PNG artifacts are retained in the repository snapshot directory |
| Component performance lane | `npm run test:perf:components` | **PASS — 27 passed** | Mocked component render contract; thresholds unchanged |
| Mocked Access performance lane | Access performance spec with the performance-enabled Vite server | **PASS — 6/6** | Mocked/browser result only; does not substitute for physical Android evidence |
| ADB qualification helper tests | `tests/backend/test_lite_windows_adb_qualification_tools.py` | **PASS — 5 passed** | Notification-shade guard and bounded wake/collapse behavior |
| Physical Android Access interaction/performance | `run-ui-performance-qualified.py --mode android-cdp --candidate-ui --access-only --baseline` | **15/15 Access reports per run; 3 baseline repetitions** | Exact candidate/header/meta SHA proof, Chrome `156.0.8078.75`, Access-only scope; no broad seven-screen matrix was run |
| Physical performance gates | `npm run check:render-budgets` against the physical Access evidence | **TARGET MISS / GATE MISS** | 15 reports; 12 target misses and 11 hard-gate misses. Thresholds and evidence schema were not weakened |
| Baseline attribution | Android baseline summary for the same exact source SHA | **DOCUMENTED RESIDUAL** | 6 `PLATFORM_DOMINATED`, 9 `MIXED`, 0 `APP_INCREMENTAL_COST`, 0 inconclusive; no isolated Access application regression was established, so no unrelated optimization campaign was started |
| Accessibility and responsive behavior | Access interaction/browser suites, keyboard/focus checks, theme geometry and visual review | **PASS for exercised mocked coverage** | Physical keyboard/assistive-technology coverage remains bounded by the available harness; no destructive protected action was submitted |
| Server Phone runtime | Read-only diagnostics plus temporary approved qualification harness | **RESTORED — `main` / `0fa114f`** | Clean checkout, production profile, all ten PM2 services online, HTTP health/readiness and NATS health 200; no source edits or deployment |

Canonical snapshots were promoted only after rendering and inspecting the actual PNGs. Seven mobile light-theme files were refreshed after review; the test retains strict screenshot comparison with narrowly scoped mocked-mobile text-rasterization tolerance for recurring Chromium anti-aliasing noise, not layout drift.

### Physical Android evidence and identity boundaries

The repository-owned Windows ADB/CDP topology was cleaned and recreated with one authorized Android target. The verified topology used Android CDP `9222`, Windows bridge `19222`, and the candidate origin `127.0.0.1:18765`, as defined by the current scripts. The elevated PowerShell helper was granted through normal UAC consent for the session; no UAC policy, credential cache, scheduled-task bypass or permanent elevation was created. The exact candidate manifest, response header, rendered page metadata and source commit all resolved to `3d0b954f9fb0051869fc2456c2b376309929a405`.

Final cleanup removed the candidate reverse, Android CDP forward, WSL relay, temporary elevated helper and transcript, and verified the repository firewall rule absent. The Windows `172.19.0.1:19222` portproxy could not be removed because two subsequent normal UAC prompts were cancelled by the host; its recorded state was intentionally retained for a future approved cleanup, and this is a qualification-environment residual rather than a product or release claim.

The physical qualifier covered only Access: initial paint/hero/protection, Manage/index, Passkeys, Sessions and nested Details, Recovery, protected-confirmation cancellation, Activity, Settings, compact/medium/expanded snapping, theme, repetition, scrolling, saved/unavailable presentation and dock visibility. The global dock received focused cross-tab smoke checks; the seven-screen physical performance matrix was not invoked.

The approved synthetic profile was the backend-owned `qualification-owner` profile with short-lived, key-bound sessions and bounded browser access. The principal was revoked during controller cleanup. No real Owner credential, WebAuthn private material, test-auth bypass, persistent browser credential, destructive mutation or production audit mutation was used.

### Test and screenshot inventory

The canonical Access visual inventory is the PNG set under `tests/e2e/lite-access-native-visual.spec.ts-snapshots/`, with scenario names for overview, missing passkeys/recovery, signed-out, pending/offline, Enterprise roles, Manage sections, nested session Details, protected confirmation and Compact/Medium/Expanded sheet states. These are mocked desktop/mobile renders, not physical-device captures. Physical Android evidence is stored in the ignored qualification evidence directory and is reported separately from mocked snapshots.

## Residual risks and security review

1. The physical Android renderer missed existing absolute frame gates. Three same-device baselines classified six interactions as `PLATFORM_DOMINATED` and nine as `MIXED`; the evidence did not isolate an Access application incremental-cost finding, but this is not a physical performance PASS.
2. Mocked keyboard/focus, safe-area and responsive coverage passed; installed-PWA and physical assistive-technology coverage remains limited to the available Android CDP/harness path.
3. Long-language and 200–400% text-scaling coverage is represented by the responsive/text-stress contracts but was not promoted to a separate physical gate.
4. Current-session identification, Enterprise roles, protected confirmations and recovery handling remain backend-authoritative. No frontend role check or mocked readiness state is treated as live authorization.
5. The shared dock was verified through mocked cross-tab geometry and focused physical Access visibility checks. A full physical cross-tab performance matrix was intentionally out of scope.
6. No destructive operation was submitted. The synthetic principal was short-lived and revoked; no real Owner session or WebAuthn private material was used.

## Reproduction commands and evidence paths

The final source and mocked checks were run with Node 24.16.0. The Access-only physical pathway was invoked through the repository controller, with `--access-only` and `--baseline`; the pre-existing broad runner remains unchanged and was not used for a seven-screen run. Physical summaries and normalized reports are retained under the ignored `.pocketlab-dev/performance/` qualification directory. The final documentation tasks are run after this source/visual/device record is updated:

```bash
task lite:docs:generate
task lite:docs:check
task lite:check
```

The final output of those commands, generated-file review, PR SHA reconciliation, Server Phone restoration and CDP cleanup is recorded in the session completion report and PR #639.

> [!CAUTION]
> **Draft PR only.** Do not squash, merge, release, tag or deploy until separate qualification and review explicitly authorize it. CI and failure remediation are outside this authoring session. Any automatically triggered workflow outcome is not evidence claimed by this document.
