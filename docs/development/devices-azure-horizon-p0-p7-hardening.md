# Azure Horizon Devices · Native Manage Hardening (P0–P7)

> **IMPLEMENTATION AUTHORED — VALIDATION NOT EXECUTED.** This document describes source changes on `feat/azure-horizon-devices-experience-hardening`, not observed browser or Android outcomes. Do not promote to verified/production-ready until a separate qualification session.

## P0 — Source audit and authority

- **Repository:** `dexter-lab-ctrl/pocket-lab-lite`
- **Authoritative `main` at branch creation:** `c85bdfbae9991262ee34430a1daf0b8a6a361197`.
- **PR #643:** existing Device Library, cards, summary, search/filter, deferred topology, protected-host logic, rich detail sections and device operation guards. Preserved.
- **Shared infrastructure present at source:** `GlassCard`, `PageHeader`, `LiteButton`, `StateSurface`, `LiteHistoryTimeline`, `LiteProgressiveDetails`, `useDesktopManageGeometry`, `useMobileSheetSnap`, `triggerLiteHaptic`, `azureHorizonTokens.css`, `DeviceFactsPrimitives`.
- **Reference status:** PRs #606, #622, #623, #629, #634, #635, #636, #637, #638, #640–#647 are merged at inspection time. None is a prerequisite outside `main`.
- **Verification scope:** source inspection, branch creation, source/asset authoring. No build, tests, linter, formatting, browser, CSS-computed style, CI investigation or runtime/Android checks.

### P0 findings and classification

| Category | Source evidence / observed concern | Change |
|---|---|---|
| VERIFIED FROM SOURCE | `DeviceDetailsLazy.jsx` rendered a horizontal, scrollable row of operational section buttons | Replace with grouped Devices-specific navigation over the existing sections |
| VERIFIED FROM SOURCE | `azureDevices.css` explicitly applied `overflow-x:auto` to `.lite-device-manage-navigation` | Remove the tab-strip layout and scope desktop/mobile index/detail styles |
| VERIFIED FROM SOURCE | `DeviceDetailsPortal` already called the shared geometry and mobile-snap hooks | Reuse unchanged; adjust default desktop panel width and toolbar presentation |
| VERIFIED FROM SOURCE | `DeviceModelPickerLazy` directly called `navigator.vibrate` | Route user-triggered tactile feedback through shared `triggerLiteHaptic` |
| VERIFIED FROM SOURCE | A frontend temperature utility assigned health tones using fixed 45/60°C thresholds, regardless of backend semantics | Remove synthetic temperature-health classifications; show reported measurement and authoritative reported health |
| VERIFIED FROM SOURCE | Service list repeated state text per item and did not group reports | Group by safe service-identity mappings; unknown services remain under Other services |
| VERIFIED FROM SOURCE | Remote Access summary could label a cached command path Reachable when in saved-only mode | Give saved mode precedence; keep Tailnet address hidden unless backend readiness is confirmed |
| VERIFIED FROM SOURCE | History used the shared `LiteHistoryTimeline`, but all events shared the same visual marker | Extend shared timeline via opt-in Devices variant, date grouping and event-specific icons |
| VERIFIED FROM SOURCE | `src/index.css` has historical Daylight-scoped Devices selectors, while `azureDevices.css` overlays Azure theme rules | Devices-scoped token-backed styles replace conflicting local Manage presentation; computed cascade still needs qualification |
| OBSERVED IN SCREENSHOT (brief) | Low-contrast values, concatenated connection labels, uneven density and mismatched Light/Dark spacing were reported | Target token-backed styles and explicit fact label/value groups; reproduction **not browser-verified** |
| INFERRED | Legacy CSS selector ordering and panel-container width likely contribute to some visual defects | Source-level containment/refinement; actual browser root cause remains unvalidated |
| PATCH-PROVIDED | Native Manage navigation, service grouping, timeline variant, new scoped CSS, haptics and qualification assets | Implemented on feature branch |
| NOT VALIDATED | 320px, high zoom, screen reader, physical touch/haptics, Caddy/PWA, running Device agent, CI and visual parity | Future qualification gates |

### Before/after component map

```text
BEFORE (PR #643)
LiteDevices → DeviceCard → DeviceDetailsPortal
  → useDesktopManageGeometry / useMobileSheetSnap
  → DeviceDetailsLazy → horizontal navigation tabs → section content
  → LiteHistoryTimeline (undifferentiated nodes)

AFTER (this branch; source-authored)
LiteDevices → DeviceCard (unchanged) → DeviceDetailsPortal
  → shared geometry/snap hooks (unchanged)
  → DeviceActionPortal (scroll containment, optional Manage backdrop)
  → DeviceDetailsLazy
      ├── DeviceManageNavigation → deviceManageSections (protected-host filter)
      ├── desktop: persistent grouped index + selected details
      ├── mobile: settings index → focused details → Back → index → Close
      ├── DeviceFactsPrimitives / LiteProgressiveDetails (reused)
      ├── grouped backend-reported runtime services
      └── LiteHistoryTimeline variant="devices" (safe shared extension)
```

## P1 — Theme/density and readability

**Token authority:** `src/lite/theme/azureHorizonTokens.css` (unchanged). Devices styles use `--azure-canvas`, `--azure-surface`, `--azure-raised`, `--azure-input`, `--azure-border`, `--azure-strong-border`, `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-selected`, `--azure-hover`, `--azure-pressed`, `--azure-focus`, `--azure-success`, `--azure-warning`, `--azure-danger`, `--azure-neutral`, `--azure-panel-shadow`, `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card`.

**Geometry authority:** one theme-independent spacing/grid rule set in `azureDevices.css`, using established `--azure-spacing-card`, container-width behavior, fixed accessible target sizes and CSS grid. No theme-specific hardcoded geometry or new theme provider. State accents are localized; overall success does not recolor the entire panel.

**Readability:** explicitly scoped text versus muted facts, resource values, health and recovery cards, nested controls, service group and timeline labels. Removed panel-wide button color/background overrides so individually themed semantic buttons can remain authoritative. Device-specific CSS replaces only the local old horizontal navigation; avoids modifying other tabs' CSS.

## P2 — Native Manage workspace

### Desktop

```text
┌────────────────────────────────────────────────────────────────┐
│ [Move] Device workspace · Move/resize          [Reset] [Resize]│
│ Server or device · projected connection / freshness       [×]  │
├────────────────────┬───────────────────────────────────────────┤
│ DEVICE             │ HEALTH / CONNECTION / SERVICES / ...      │
│ Overview           │ Grouped backend-reported facts            │
│ Connection         │ Safe recommendations / details            │
│ Health             │                                           │
│ Roles (peer only)  │                                           │
│ Services           │                                           │
│ Backup (peer only) │                                           │
│ ACTIVITY & DETAILS │                                           │
│ History            │                                           │
│ Technical          │                                           │
└────────────────────┴───────────────────────────────────────────┘
```

- `useDesktopManageGeometry` still owns movement, resizing, reset, keyboard arrows and viewport clamping. Only the initial width changes to 820px subject to shared viewport limits.
- CSS container queries stack navigation and content inside a **narrow resized panel**, regardless of viewport width. No new geometry engine.
- Manage toolbar retains the exact accessible Move, Resize and Reset labels for existing source consumers.

### Mobile

```text
Manage index                              Focused detail
┌───────────────────────────┐             ┌────────────────────────────┐
│ Device name            ×  │             │ Device name             ×  │
│ DEVICE                    │             │ ‹ All device settings       │
│ Overview              ›   │  tap row    │ HEALTH                     │
│ Connection            ›   │ ──────────► │ Reported status, freshness │
│ Health                ›   │             │ Resources / recovery       │
│ Services              ›   │ ◄────────── │                            │
│ ACTIVITY & DETAILS        │    Back     │                            │
│ History               ›   │             │                            │
│ Technical             ›   │             │                            │
└───────────────────────────┘             └────────────────────────────┘
```

- Back changes harmless UI navigation; Close dismisses the whole modal and restores focus to the device's Manage button. Escape from a focused detail returns to index before Escape on index closes.
- Selecting a different device remounts details via the pre-existing per-device key, preventing stale local tab selection.
- The shared snap controller still owns Compact / Medium / Expanded, grip-only gesture semantics, keyboard snap and visual viewport height. No dragging on action buttons/forms.
- Modal backdrop is clickable only for Manage; body scroll is locked while a Devices action portal is mounted.

## P3 — Component unification and disposition

| Source PR | Component/file | Existing responsibility | Devices usage | Disposition | Why |
|---|---|---|---|---|---|
| #606 | `LiteUi.jsx` `PageHeader`, `LiteButton`, `GlassCard`, `StateSurface`, `StatusBadge` | Shared page/actions/state surfaces | Existing library/card/onboarding/details | Reused unchanged | Preserve common UI semantics |
| #606 | `LiteProgressiveDetails.jsx` | Protected action/technical details | Nested Technical detail | Reused unchanged | No raw evidence exposure |
| #606 | `LiteUx.jsx` `LiteHistoryTimeline` | Event timeline normalization/rendering | New opt-in Devices dated/icon variant | Reused with safe shared extension | Keep one common timeline implementation |
| #622 | `azureHorizonTokens.css` | Light/Dark semantic token authority | All Devices surfaces and portals | Reused unchanged | Theme-dependent colors, independent geometry |
| #623 | `useDesktopManageGeometry.js` | Move/resize/reset/keyboard and clamping | Device Manage portal | Reused unchanged | No alternate geometry engine |
| #629 | Apps progressive disclosure patterns | Calm summary-first app operations | Considered for Devices progressive details | Considered, not imported | Domain-specific interaction remains Devices-owned |
| #634 | `useMobileSheetSnap.js` | Three-state mobile sheet and safe grip | Device Manage portal | Reused unchanged | Avoid gesture duplication |
| #635 | Apps Azure presentation patterns | Token-backed cards/panels | Design reference, no direct import | Considered, not used directly | Avoid cross-domain CSS coupling |
| #636 | Apps theme-density parity specification | Geometry/typography parity across themes | Devices CSS and deferred Playwright computed-style test | Adapted locally | Same principle; Devices-only selectors |
| #637 | Native Apps Library/Manage | Summary-first inventory and Manage | Existing PR #643 library + new native settings index | Pattern adaptation | Device operations remain distinct |
| #638 | Native Home hierarchy | Summary and progressive content | Existing PageHeader/freshness patterns | Existing shared usage | Avoid unrelated Home changes |
| #640 | `liteNativeFeedback.js` | Native haptic patterns/feature gating | Manage, Back, nav, disclosure, sheet, model, backup/onboarding | Reused unchanged | No direct `navigator.vibrate` duplication |
| #641 | Safety shared disclosure styling | Icon orientation and tokens | Devices chevrons scoped to `lite-shared-disclosure-chevron` | Reused class/contract | Consistent disclosure semantics |
| #642 | Rules grouped settings interactions | Navigation grouping/design reference | New Devices-specific grouped navigation | Pattern only | No Rules dependency |
| #643 | `LiteDevices.jsx`, `DeviceCard.jsx`, Devices projections | Authoritative Devices Library | Kept, targeted modifications | DeviceCard reused unchanged; others adapted | Preserve library IA and backend boundaries |
| #644 | Recovery index/detail patterns | Task-grouped navigation | Mobile settings index concept | Pattern only | No cross-screen orchestration |
| #645 | Overlay hardening patterns | Managed focus/scroll/semantic actions | Devices portal updated locally | Adapted locally | Preserve existing Devices surface geometry |
| #646 | PR formatting and shared interaction guidance | Professional reuse and provenance | PR description pattern; no copied UI dependency | Considered | Metadata/documentation reference |
| #647 | Access native interaction design | Access-specific detail and overlay flow | Inspected, no direct component imported | Considered, not used | Do not couple device and identity UI internals |

**New Devices-only components:** `DeviceManageNavigation.jsx` for grouped mobile/desktop settings index; `deviceManagePresentation.js` for peer-only section filtering, service grouping, event-date/icon classification.

**Legacy duplicate removed:** old Devices horizontal tab-strip markup and its scrolling CSS. No backend/device domain component was deleted.

## P4 — Truthful content and data lineage

| View | Source of truth | UI posture |
|---|---|---|
| Overview | Fleet/device profile, system model and `canonicalDevicePresentation` | Identity and system separate; Choose Model remains display-only |
| Connection | Last heartbeat/last seen, supervisor, identity, remote-access and command delivery projections | Independent facts; no forced agreement between Online and Repairing |
| Health | Prepared device health projection and `DeviceFactsPrimitives` | Reported readings and health status; stale/saved not described as current |
| Resources | Backend metrics via `normalizeDeviceFacts` | Storage/memory/CPU display meters are neutral; no client-derived health thresholds; temperature is a reading only |
| Services | `deviceRuntimeServices` | Safe identity groupings preserve all reported service rows, freshness and last-reported time if supplied; unknown IDs are Other services |
| Responsibilities | Backend dependency/hosted-app projection | Hosted apps remain separate from core services; stale is last reported, not Running |
| History | `liteApi.deviceHistory` / existing saved recent lifecycle | Shared timeline with date groups and source-derived icons; no fabricated events/timestamps |
| Remote Access | FastAPI prepared `remote_access` | Tailscale status, last checked, device address and control path separated; saved state never proves current reachability |
| Technical | Existing sanitized technical rows and `LiteProgressiveDetails` | Progressive disclosure; no raw evidence or secrets |

**Distinct states:** Online, Joining, Waiting, Offline, Agent stopped, Repairing, Remote access not ready, Protected server host, saved and unknown remain separate. One projected connection state does not imply healthy software, a working command path or successful recovery.

## P5 — Overlay, containment and responsiveness

- Reuse the portal host to retain theme context; improve backdrop/scroll behavior without altering the FastAPI/agent operation path.
- Device details, nested health history, service lists, remote facts and technical disclosure use token-backed visuals and safe wrapping.
- Container-width layout responds to resizing; mobile retains safe area, grip-only dragging and internal scroll containment.
- Device deletion still requires the existing server-owned assessment and confirmation; no browser-owned remove authority.

## P6 — Native haptics and accessibility

The existing `triggerLiteHaptic` utility owns browser support, visibility and reduced-motion suppression. Newly wired controls include mobile Back, grouped section selection, model picker selection/back/reset, backup refresh/start/repair/cancel, onboarding options and submission, invite copy, removal review, confirmation step and dismissals, shared details/health disclosure, panel size/reset/move/resize and routed next steps. Success/warning feedback remains event-directed; no passive polling/render haptics.

Accessibility contract: labelled modal, Close versus Back, semantic navigation groups, icon-plus-text status, focus-visible rings, focus restoration, Escape behavior, text wrapping, keyboard panel geometry, touch targets, reduced motion and explicit stale/unconfirmed labels. Physical vibration, screen-reader traversal, contrast and 200% zoom **not validated**.

## P7 — Qualification authored; NOT EXECUTED

| Asset | Coverage | Status |
|---|---|---|
| `deviceManagePresentation.test.js` | Protected-host sections, grouped service preservation, event mapping | AUTHORED · NOT RUN |
| `DeviceManageNavigation.test.jsx` | Desktop navigation selection, mobile/protected index, shared history variant | AUTHORED · NOT RUN |
| `tests/e2e/lite-devices-manage-hardening.spec.ts` | Desktop/mobile navigation, Back/Close, geometry, snap, remote saved state, connection/health distinction, Axe | AUTHORED · NOT RUN |
| `tests/e2e/lite-devices-theme-density-hardening.spec.ts` | Geometry comparison at 320/360/430/768/1024/1440; visual candidate snapshots | AUTHORED · NOT RUN |
| `AzureDevices.stories.jsx` | Light/Dark/System and targeted sections, mobile index/details, stale/repairing/long-name | EXTENDED · NOT RENDERED |
| Existing Devices tests/stories | Library, a11y, device action regressions, multiple backend-truth states | RETAINED · NOT RUN |
| Storybook/Playwright baseline approval | Exact screenshot candidates | PENDING; NO BASELINES CAPTURED |
| Android CDP, live PWA, Tailscale, service health | Live behavior and haptic/touch verification | NOT EXECUTED |

### Future qualification commands (do not run in implementation session)

```bash
npm run build
npx vitest run src/lite/devices/deviceManagePresentation.test.js src/lite/devices/DeviceManageNavigation.test.jsx
npx playwright test tests/e2e/lite-devices-manage-hardening.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-devices-theme-density-hardening.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-devices-native-workspace-qualification.spec.ts --project=mocked-desktop --project=mocked-mobile
npm run build-storybook
task lite:check
```

The separate qualification session must approve visual baselines intentionally, exercise real Android Chrome/CDP and installed PWA, test focus and touch haptics (subject to platform support), inspect computed Light/Dark/System CSS, and diagnose real CI failures before considering merge.

## Known limitations and risks

1. **Unvalidated browser rendering:** CSS cascade, PWA, portal layering, container queries, typography and body scroll locking require desktop/mobile qualification.
2. **No physical haptic verification:** shared utility is wired in source; actual Android/browser capability remains unknown.
3. **No production status change:** feature branch is unmerged; no Android runtime or backend execution was performed.
4. **Service categorization:** conservative service-ID mapping is presentation-only, and unknown names remain Other services. It does not redefine service ownership or health.
5. **Source timestamps:** no invented timestamps; missing reported times display as unavailable. Date grouping depends on parseable API timestamps.
6. **Unknown health thresholds:** client does not classify thermal or resource readings; backend may provide a separate authoritative assessment.
7. **Visual snapshots:** screenshot assertions are candidate specifications only; expected image files deliberately not generated.
8. **Legacy styling:** the repository retains historical style rules; further cascade consolidation may be necessary based on computed CSS findings.

## Rollback

No direct changes to `main`, release artifacts, server phone, API or worker were made. To roll back this proposal, close the Draft PR or revert feature-branch commits, retaining the original PR #643 Devices Library. Do not rewrite the authoritative `main` or deploy an unqualified build.

## Enterprise value

The implementation separates connectivity from recovery/health facts, makes protected identities and guardrails easier to understand, reduces duplicated presentation logic, and centralizes accessible settings navigation around existing backend-owned operations. The impact is intended; it must be measured and qualified before a production-readiness claim.
