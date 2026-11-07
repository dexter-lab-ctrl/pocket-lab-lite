# Pocket Lab Lite — Azure Horizon Access Center UI/UX Hardening

> **Implementation:** Source authored on `feat/azure-horizon-access-center-hardening`.  
> **Qualification:** **AUTHORED — NOT EXECUTED**. No build, tests, lint, visual review, performance benchmark, runtime check, or physical Android qualification was executed in this session.  
> **Authoritative base:** `main` at `b51a3e4abe2861459f1d542d159fd5c77af10027`.  
> **Safety:** Existing Identity API and server-owned authorization, confirmations and step-up requirements remain unchanged.

## 1. Objective and scope

Refine the already merged Azure Horizon Access Center from [PR #639](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/639), without redesigning the Identity API or introducing another overlay, typography, theme, haptic or authorization system. The scope is the Access UI for signed-out and signed-in states, Personal and Enterprise Mode, desktop and mobile, and safe education about authorization.

Runtime boundary, intentionally unchanged:

```text
React / Vite PWA
  → Caddy same-origin
  → FastAPI /api/lite/* (identity and authorization authority)
  → backend-owned command / audit paths
  → authorized execution and sanitized server facts
  → FastAPI → UI
```

The browser cannot grant permission, generate credentials, access NATS directly, execute shell commands, or persist private auth materials as UI state.

## 2. P0 — Source-level CSS ownership and reconciliation

The pre-existing overlap was discovered by reading source definitions, **not verified by computed browser styling**. In particular, historical Daylight selectors in `src/index.css` imposed Access card typography and layout, `identityPremium.css` defined a narrower Manage width, and `accessCenter.css` defined a wider Manage width. This branch removes targeted conflicting declarations instead of adding new theme-specific overrides.

| Component | Previously overlapping sources | Final authoritative source | Implementation |
|---|---|---|---|
| Semantic colors, backgrounds, controls and focus | Daylight rules, multiple theme declarations | `src/lite/theme/azureHorizonTokens.css` | Source uses existing `--azure-*` tokens for both Light and Dark |
| Access page shell and spacing | `src/index.css`, `identityPremium.css`, `accessCenter.css` | `src/lite/identity/accessCenter.css` | Scoped `.lite-access-page` page shell, constrained width and theme-independent gaps |
| Signed-out setup, sign-in and recovery cards | Legacy Daylight `.lite-identity-grid`, `.lite-identity-card`, local styles | `src/lite/identity/accessCenter.css` | Grid, cards, form controls and responsive spacing shared across themes |
| Access hero and grouped protection/activity rows | `src/lite/identity/accessCenter.css` | Same stylesheet | Existing summary-first group model retained |
| Manage navigation and responsive columns | `identityPremium.css` and `accessCenter.css` | `accessCenter.css` | Existing `@container 620px` layout retained; duplicated grid rules removed |
| Manage sheet width and mobile geometry | `identityPremium.css`, `accessCenter.css`, shared overlay | `accessCenter.css` for width, `LiteOverlay.jsx` for behavior | Removed conflicting 46rem width, reused existing shared snap and portal |
| Nested Details layout | `identityPremium.css`, `accessCenter.css`, shared overlay | `accessCenter.css` for inner layout, `LiteOverlay.jsx` for mechanics | Unified heading, status, explanatory card and scroll containment |
| Technical facts disclosure | `LiteUx.jsx`, legacy `src/index.css` pseudo +/− | `LiteUx.jsx` + existing `lite-shared-disclosure-chevron` | Native `<details>` with down/up chevron; removed pseudo +/− |
| Haptic interaction | Local button callbacks, global haptics | `src/lib/liteGlobalHaptics.js` and `src/lib/liteNativeFeedback.js` | Delegated haptics reused; native `<summary>` adds targeted haptic |
| Focus and keyboard behavior | Existing `LiteOverlay.jsx` + geometry hooks | Same shared infrastructure | No new event interception, fake focus state or gesture engine |

**Unvalidated:** Exact computed geometry and CSS cascade results, including media queries inherited from other stylesheets, require the authored Playwright theme and layout qualification.

## 3. P1 — Account composition and theme parity

The Access page now uses the hierarchy:

```text
Account & Access
Your access — Your identity and protection

[Existing authenticated account hero]
  Server-reported identity, role and workspace mode
  Sign-in method + readiness
  Manage Access

Sign-in & protection
  Passkeys → Sessions → Account recovery

Recent activity [View history]

How Access works →
```

Signed-out states keep the established trusted Owner setup, passkey sign-in, optional advanced sign-in and recovery paths. The same `--azure-surface`, `--azure-raised`, `--azure-input`, typography and geometry now decorate these cards under both Light and Dark. Unknown or saved Identity facts stay explicitly unavailable; no readiness is inferred from the browser.

Geometry properties are theme-independent: width constraints, form min-height, padding, gaps, radii, breakpoints, card structure and touch targets. Only semantic appearance tokens resolve differently between themes. This follows [PR #636](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/636).

## 4. P2 — Chevron and disclosure unification

`LiteTechnicalFacts` retains native `<details><summary>` and now renders `ChevronDown` with `lite-shared-disclosure-chevron`, matching the current `LiteTechnicalDetails.jsx` and `LiteHistorySection.jsx` convention. Existing title/facts behavior and native keyboard toggling remain. Open state rotates the chevron through the existing CSS convention. Navigation rows use `ChevronRight`; Back uses the existing `ArrowLeft`. A manual `tap` haptic is attached only to the native summary because the shared delegated click handler covers button-like controls but not `<summary>`.

**Important:** `LiteDisclosureAzure.jsx` is not present in the inspected repository; only `LiteDisclosureAzure.test.jsx` exists. No non-existent component is imported or falsely credited. The existing visual/semantic convention was reused directly without adding a competing library.

## 5. P3 — Reusable Access Details

Added `src/lite/identity/AccessDetailPresentation.jsx`, a presentation-only icon/title/status/explanation header. Integrated in `IdentityDetailsContent.jsx` for Identity, Passkeys, Sessions, Recovery, People, Roles, Authorization, Activity, Workspace Mode and explanations. Grouped server facts, relevant actions, existing protected confirmation path and optional technical details remain with their prior handlers.

`formatAccessTimestamp` converts valid server timestamps into readable locale-aware date/time displays without changing the underlying meaning. Missing and invalid date values render `Not reported`; unknown credential states do not become `Revoked` or `Active`. Names and long facts wrap; no secrets or credential IDs are deliberately added to the presentation.

**Server ownership:** Revocation, sign-out, recovery-code regeneration, passkey registration, Owner/Enterprise policy and step-up are unchanged and remain API-owned.

## 6. P4 — How Access works

Added a compact row at the end of the signed-in Access summary, plus an available signed-out entry. Both open existing shared Identity overlay infrastructure. The educational content has four conceptual stages, not a fake operational progress bar:

1. **Sign in:** Identify yourself using a supported sign-in method.
2. **Protect your access:** Review passkeys, active sessions and recovery.
3. **Make protected changes:** Server authorization and applicable confirmation/approval policy govern action.
4. **Review activity:** Examine only recorded access events.

`accessEducationContext(view,signedIn)` explains signed-out, Personal, Enterprise, stale and unknown states conservatively. It never infers that Enterprise Owner or Admin has unrestricted authority; Personal Mode does not invent an Enterprise approval requirement. No new API is needed.

## 7. P5 — Responsive Manage and nested overlays

**Reused:** `LiteSheet`, `LiteDetailsPanel`, `LiteDesktopPanelControls`, `useMobileSheetSnap`, `useDesktopManageGeometry`.

The Access Manage panel continues to be movable and resizable on desktop, and now renders the *shared* `LiteDesktopPanelControls` presentation rather than an Access-only copy. It retains keyboard geometry, default clamps, reset, focus and close semantics from existing code.

On mobile, shared sheet state is `compact` (35%), `medium` (72%) and `expanded` (94%); the grip is the only swipe surface. Compact and Expand buttons remain alternate controls. The existing portal, focus trap, Escape/Close handling, scroll containment and nested Details stay in place. Access-specific CSS only styles the internal content and never implements a second sheet engine.

**Unvalidated:** Android Chromium/PWA visual viewport behavior, nested stacking during keyboard invocation, focus restoration on particular mobile builds and visual result of PR #646's performance mode require later qualification.

## 8. P6 — Haptics and accessible interactions

- [PR #640](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/640) established `liteGlobalHaptics.js` for delegated button, navigation, input-submit and dialog controls. It already covers dynamically mounted Access buttons and portal controls.
- `triggerLiteHaptic` respects unavailable `navigator.vibrate`, hidden documents and `prefers-reduced-motion` and never gates the underlying action.
- Existing successful/blocked/confirmed Identity operation feedback is preserved; the added `<summary>` feedback does not duplicate delegated button feedback.
- Managed buttons retain min 44px interaction height where appropriate; labels, focus-visible token, native semantic forms, screen-reader names and real confirmation surfaces are preserved.
- New decorative icons are `aria-hidden`; no auto-haptics run on rendering, polling, navigation effects or state hydration.

## 9. Mandatory reuse trace

| Source | Actual inspected implementation | Reuse in this branch |
|---|---|---|
| [#606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606) | `GlassCard`, `StatusBadge`, `StateSurface`, `LiteButton`, `LiteConsequenceSummary`/protected forms | Existing Access cards, safe notices, forms, confirmation, reusable explanatory card |
| [#622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622) | `azureHorizonTokens.css`, `azureHorizon.css`, theme runtime/provider | All new Access CSS resolves semantic tokens rather than hardcoded Light/Dark colors |
| [#623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623) | Apps portal and responsive Manage geometry | Existing `LiteSheet` + `useDesktopManageGeometry`; no new implementation |
| [#636](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/636) | Apps Light/Dark layout parity and density | Unified geometry, shared `accessCenter.css` ownership, authored computed-style parity check |
| [#639](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/639) | Current Access Center, grouped navigation, backend-truthful Identity projection | Entire existing product/workflow architecture preserved and extended |
| [#640](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/640) | `liteGlobalHaptics.js`, `liteNativeFeedback.js` | Reused delegated haptic mechanism; no alternate vibration library |
| [#645](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/645) | Shared overlay and `lite-shared-disclosure-chevron` convention | Retained native details + shared chevron styling and shared overlay engine |
| [#646](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/646) | `LiteDesktopPanelControls`, shared `useMobileSheetSnap` | Desktop controls unified; mobile Compact/Expand maintained |

### Exact Azure Horizon token reuse

| Role | Existing semantic variables |
|---|---|
| Page and raised surfaces | `--azure-canvas`, `--azure-surface`, `--azure-raised` |
| Inputs | `--azure-input`, `--azure-strong-border` |
| Foreground and secondary information | `--azure-text`, `--azure-muted` |
| Interactive and selected | `--azure-accent`, `--azure-accent-subtle`, `--azure-hover`, `--azure-selected` |
| Borders, focus and danger | `--azure-border`, `--azure-focus`, `--azure-warning`, `--azure-danger` |
| Shape and geometry | `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card`, `--azure-font-ui` |
| Surface depth | `--azure-shadow`, `--azure-panel-shadow` |

### Other reference PRs

[#629](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/629), [#634](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/634), [#635](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/635), [#637](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/637), [#638](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/638), [#641](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/641), [#642](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/642), [#643](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/643) and [#644](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/644) were reviewed for source patterns, responsive sheets, safety styling, grouping, progressive disclosure and existing interaction boundaries. No new dependency or duplicative global library was added based solely on their PR descriptions.

## 10. P7 — Authored qualification: **NOT EXECUTED**

| Asset | Status | Future checks |
|---|---|---|
| `src/lite/identity/accessCenterHardening.test.jsx` | **AUTHORED — NOT EXECUTED** | Truthful readiness, icon/data presentation, disclosure, localized timestamps, unknown states, education and protected-action disabled state |
| `src/lite/LiteIdentity.stories.jsx` | **EXTENDED — NOT EXECUTED** | Signed-out Light/Dark, education, sessions, recovery, technical chevron |
| `tests/e2e/lite-access-azure-hardening.spec.ts` | **AUTHORED — NOT EXECUTED** | Mocked 320/360/390/430/768/1024/1440, Light/Dark geometry, signed-in/out, System, keyboard/Escape, native summary, mobile snap, desktop nested, Enterprise, axe and zoom |
| Existing Access/Overlay/Global Haptic stories and tests | **REUSED — NOT EXECUTED HERE** | Existing baseline tests from prior PRs still require a fresh qualification run |
| Physical Android / Termux qualification plan below | **DOCUMENTED — NOT EXECUTED** | Real runtime and platform checks |

No snapshots were generated, approved or changed. No CI run was examined or initiated intentionally. CI may trigger automatically when the draft PR is opened; results are intentionally not investigated in this implementation-only session.

### Dedicated future Dev-PC qualification session (commands **not run** here)

From a clean development checkout of this branch, the *future qualification engineer* can execute targeted checks in order:

```bash
npm run build
npx vitest run src/lite/identity/accessCenterHardening.test.jsx src/lite/identity/AccessCenterSummary.test.jsx
npx playwright test tests/e2e/lite-access-azure-hardening.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-access-native-visual.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-access-native-performance.spec.ts --project=mocked-mobile
```

Compare prior golden images intentionally; **do not automatically update snapshots** until a human has reviewed the changed geometry. Capture theme parity, focus, reduced motion, long text and 200% zoom evidence. Follow the repository's existing docs and quality gates when permitted by the future session's execution policy.

### Physical Android / installed PWA qualification (not run)

1. Use approved synthetic or existing authorized identities in a controlled test environment. Never log credentials, recovery codes, raw WebAuthn challenges, tokens, secrets or session identifiers.
2. Review Android/Termux server readiness **separately from this implementation session**, using safe existing operational health procedures; leave production auth configuration unchanged.
3. In mobile Chromium and installed PWA, exercise first-load, sign-in/out, Personal Owner, Enterprise restricted viewer, saved/offline read-only, light/dark/system changes.
4. Exercise nested Manage→Passkeys/Sessions/Recovery→Details; Compact→Medium→Expanded; keyboard appearance, focus restoration, Back versus Close, Escape on desktop; ensure scroll and input are never mistaken for drag commands.
5. On devices that support vibration, verify supported haptics, reduced-motion and silent fallback where no vibration API exists.
6. Capture first interaction latency, frame stability, CPU/memory impact, layout shifts, text zoom and no horizontal overflow at representative mobile sizes. Compare with the existing performance budget without claiming that it passed.
7. Reconfirm real Owner passkey enrollment, step-up, session management and recovery flow integrity only in authorized, safe scenarios, without destructive action on production accounts.

**Historical residuals:** PR #639 documented physical Android performance limitations. They are **not resolved or re-qualified by this source-only session** and remain in scope for the next qualification session.

## 11. Risks, rollback and enterprise value

**Risks:** Complex legacy CSS remains in the broader `src/index.css`; this change consolidates only identifiable Access rules. Native `<details>` chevron style must be compared against global disclosure appearance in real browsers. Cross-tab visual regressions from shared `LiteUx.jsx` and `src/index.css` warrant targeted tests. New educational copy must not be mistaken for an authorization decision. Mobile keyboard/viewport changes and PWA haptics can differ by device. No test or CI outcome is known for this branch.

**Rollback:** This branch targets `main` and has not been merged or deployed. To roll back before merge, close the draft PR and leave `main` unchanged. For selective rollback later, revert the scoped Access commits rather than changing backend Identity authorization. Avoid reverting global shared components without examining unrelated consumers.

**Enterprise value:** Consistent semantics and geometry reduce cognitive load, improve the auditability of status versus action authority, and limit future CSS drift. Component reuse reduces the number of unique overlay and feedback implementations that require review. High-value UX changes remain isolated from the security control plane.

**Final status:** Access P0–P6 source enhancements committed; P7 coverage and documentation authored. **QUALIFICATION NOT EXECUTED**. No merge, release, deployment or runtime state change.
