# Azure Horizon Access Center — P1–P6 source qualification handoff

> [!IMPORTANT]
> **SOURCE AUTHORED · NOT EXECUTED · RUNTIME UNVALIDATED · VISUAL BASELINES NOT PROMOTED.**
> This is an implementation-session handoff, not a test or release certificate. No validation tasks, builds, checks, screenshots, CI actions, or runtime operations were executed intentionally.

## Authority and provenance

| Field | Recorded value |
|---|---|
| Repository | `dexter-lab-ctrl/pocket-lab-lite` |
| Base branch | `main` |
| Source-authoring base SHA | `0fa114f89243334ffa4db084810c34f4c97995b7` |
| Feature branch | `feat/azure-horizon-access-native-revamp` |
| Destination | `main` (Draft PR only) |
| Qualification | Deferred; no evidence of passing execution |
| Merge / release / deployment | Not authorized; not performed |

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
| P6 | Stories, unit/component tests, Playwright source candidates, this document | Qualification authored, NOT executed |

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

## Native Manage, overlay, and mobile sheet contract

Mobile Manage begins at the grouped index. Selecting a row opens a focused section and moves focus to its heading. **Back** restores the index; **Close** dismisses the overlay. Escape performs narrow-panel Back before Close, while nested Details and confirmations retain top-of-stack Escape behavior. A desktop Manage panel uses the existing `useDesktopManageGeometry` and a container query (not merely viewport width). The existing Move/Resize/Reset controls, clamping and keyboard handling remain in their original controller.

| State | Approximate visual viewport height | Existing controller authority |
|---|---:|---|
| Compact | 35% | `MOBILE_SHEET_RATIOS.compact` |
| Medium | 72% | `MOBILE_SHEET_RATIOS.medium` |
| Expanded | 94% | `MOBILE_SHEET_RATIOS.expanded` |

`LiteSheet` opts `mobileSnap` into **Manage Access**; `LiteDetailsPanel` opts it into selected passkey, session, recovery, access activity, person, role, authorization, mode and explanation Details. These share the same nested Details portal and controller. No gestures attach to rows, input fields, actions or destructive buttons. Grip, snap size buttons and keyboard Arrow/Page/Home/End handling are owned by the shared controller.

**Intentional exceptions:** Passkey rename form, confirmation sheets, Enterprise destructive confirmation and platform WebAuthn dialogs **do not opt into snaps**. They keep their established focus, confirmation, security and browser ceremony behaviors.

## Qualification matrix — all UNEXECUTED

| Candidate | Location | Scenarios | Status |
|---|---|---|---|
| Pure presentation | `src/lite/identity/accessCenterPresentation.test.js` | ready/attention/saved/unavailable, missing counts, payload redaction, mode grouping | SOURCE AUTHORED / NOT EXECUTED |
| Component and navigation | `src/lite/identity/AccessCenterSummary.test.jsx` | grouped rows, one hero, empty activity, Back and Enterprise section control | SOURCE AUTHORED / NOT EXECUTED |
| Existing Access unit tests | `src/lite/identity/identityHorizon.test.jsx`, `identityPremiumView.test.js` | authority, stale operation restrictions, sanitized projections | Existing and adapted / NOT EXECUTED |
| Storybook | `src/lite/LiteIdentity.stories.jsx` | theme, responsive, recovery, password, sign-in, Enterprise, nested details, confirmations | SOURCE AUTHORED / NOT EXECUTED |
| Mocked browser | `tests/e2e/lite-access-native.spec.ts` | navigation, touch, Escape, focus, role gates, stale, responsive, axe, text scaling | SOURCE AUTHORED / NOT EXECUTED |
| Theme geometry | `tests/e2e/lite-access-native.spec.ts` | light/dark bounding-box comparison with 2px tolerance | SOURCE AUTHORED / NOT EXECUTED |
| Visual candidates | `tests/e2e/lite-access-native-visual.spec.ts` | mobile/tablet/desktop, theme/state/index/nested/snap screenshots | SOURCE AUTHORED / NOT EXECUTED; NO BASELINES PROMOTED |
| Performance | `tests/e2e/lite-access-native-performance.spec.ts` | first paint, Manage, nested, mobile snap | SOURCE AUTHORED / NOT EXECUTED |
| Existing Access browser contracts | `tests/e2e/lite-azure-horizon-identity.spec.ts`, `lite-identity-premium-refinement.spec.ts` | migrated structure assumptions | SOURCE ADAPTED / NOT EXECUTED |
| Physical runtime | Server Phone / Android browser / installed PWA | real WebAuthn, focus, gestures, low-power cost, session impact | NOT EXECUTED / RUNTIME UNVALIDATED |

Tests are source candidates, not observed results. Existing approved Azure Identity screenshots represent the **old** layout and must not be silently promoted or auto-updated. New screenshot assertions require separately reviewed baseline creation in a later approved qualification session.

## Deferred risks and security review

1. Mobile nested overlay Escape / Back / focus return and iOS PWA keyboard opening must be exercised on real browsers.
2. Browser viewport and resized desktop panel can differ; verify container width switching, toolbar reachability, and minimum geometry.
3. Long language, 200–400% zoom, 320px and tablet landscape need real layout, clipping, safe-area and horizontal overflow checks.
4. Current-session identification, password-change requirements, Enterprise role-specific actions and missing backend fields require independent fixture/API verification. No frontend role check substitutes for backend authorization.
5. Existing screenshot baselines are expected to differ after this intentional redesign; review before any promotion.
6. Unverified latency/frame-time, theme cascade and low-power Android resource overhead must be measured under PR #588 policy.
7. No destructive operation must be submitted during mock/physical qualification unless the existing safety harness expressly supports a harmless synthetic case.

## Suggested future qualification commands — DO NOT RUN IN THIS SESSION

From a clean DEV-PC checkout of the exact PR head (after source review and authorization):

```bash
npm run build
npx vitest run src/lite/identity/accessCenterPresentation.test.js src/lite/identity/AccessCenterSummary.test.jsx src/lite/identity/identityHorizon.test.jsx src/lite/identity/identityPremiumView.test.js
npx playwright test tests/e2e/lite-access-native.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-access-native-performance.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-access-native-visual.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-azure-horizon-identity.spec.ts tests/e2e/lite-identity-premium-refinement.spec.ts --project=mocked-desktop --project=mocked-mobile
npm run test:a11y:states
npm run test:perf:components
task lite:docs:check
```

Do not pass `--update-snapshots` without separate human visual review and approval. After Dev-PC mocking, qualify installed PWA and physical Android at an authorized candidate SHA with exact-commit proof and controlled non-destructive harness. Confirm the real backend authorization and step-up rules, all themes, navigation, 35/72/94% grip snapping, nested focus, virtual keyboard, safe areas, session highlights, no synthetic success and PR #588 performance targets. Do not deploy to production during qualification by default.

> [!CAUTION]
> **Draft PR only.** Do not squash, merge, release, tag or deploy until separate qualification and review explicitly authorize it. CI and failure remediation are outside this authoring session. Any automatically triggered workflow outcome is not evidence claimed by this document.
