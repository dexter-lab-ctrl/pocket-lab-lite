# Azure Horizon Apps — Light / Dark Layout and Density Parity

> **Source authored; qualification NOT RUN.** This implementation targets the Apps presentation layer only. No screenshot, computed-style capture, browser session, local test, build, documentation generator, CI rerun, or Android runtime qualification was executed when this document was authored. This is a Draft PR handoff, not merge approval.

## 1. Problem and user impact

Following [#629](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/629), [#634](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/634), and [#635](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/635), Apps retains the expected Open/Manage flow, section tabs, desktop move/resize, mobile snaps, nested Action Details, and the PhotoPrism workflow. The residual problem is that Azure Black feels visually tighter than Azure Daylight. Both need one calm, legible density contract while retaining the current Light layout as the geometric design reference.

The intended result is a premium catalog, not a redesigned catalog: app cards remain in the existing grid; the action footer still exposes Open/Manage; Manage and Details remain progressive disclosure surfaces; backend-owned statuses remain unchanged.

## 2. Source-only root-cause assessment

**Confirmed from current `main` source (base `07559c0cf97ba2037d3205044af05129c4462841`):**

- `src/lite/theme/azureHorizonTokens.css:1–76` gives Daylight/Black different semantic colors and shadows while defining common `--azure-radius-*`, `--azure-spacing-card`, and `--azure-font-ui` outside the theme branches. There is **no Light/Dark-specific Azure spacing scale**.
- `src/index.css:8592–8620` still carries legacy Daylight selectors, including a `1rem !important` category-top margin and `line-height:1 !important`; `src/lite/catalog/appsPremiumRefinement.css:643–685` already supplies shared Azure overrides, grid constraints and touch targets. Some legacy selectors are therefore source-order/specificity-sensitive; whether any creates a *computed* Light/Dark difference remains unmeasured.
- `appsPremiumRefinement.css:1010–1112` includes `.16rem` header/action-copy gaps and `.7–.72rem` labels. `appsPremiumRefinement.css:1411–1428` previously further reduced narrow workflow labels. These compact values were visible in source; their perceptual impact is **inferred**.
- The Apps Manage portal is mounted under `document.body` (`AppCatalogScreen.jsx:2231–2293`), not inside the catalog card; nested details also use an overlay. Apps-only styles must therefore include those distinct scopes.
- `src/lite/components/useDesktopManageGeometry.js` and `useMobileSheetSnap.js` already implement shared geometry and three mobile snap states. Their operation is outside the CSS density problem.

**Unmeasured:** actual cross-theme computed styles, bounding boxes, contrast outcomes, font rasterization, 200%-zoom placement, and perceived quality on a phone. The authored tests are intended to establish those facts in the next session. No user-visible improvement is asserted as empirically qualified here.

## 3. Light-reference shared spacing contract

The Apps stylesheet defines one **theme-independent** local scale for catalog, Manage and Action Details; it does not add globals or a new design system:

| Property | Value / authority | Intent |
|---|---|---|
| `--apps-space-xs` | `.375rem` | title/subtitle, labels |
| `--apps-space-sm` | `.625rem` | badges, buttons, small groups |
| `--apps-space-md` | `.875rem` | row and section grouping |
| `--apps-space-lg` | `1rem` | panel/body spacing |
| `--apps-space-xl` | `1.25rem` | reserved for larger separation |
| `--apps-card-inset` | `var(--azure-spacing-card)` | canonical card padding |
| `--apps-body-leading` | `1.5` | support-text legibility |

These custom properties are declared for `.lite-catalog-screen`, `.lite-catalog-manage-layer.lite-catalog-app-premium-layer`, and `.lite-details-overlay-layer .lite-app-premium-details`. All are in `appsPremiumRefinement.css`, no theme-specific geometry selector was added. Portal scopes are deliberate.

## 4. Typography and status

- App name uses the existing Azure font and responsive size with a shared `1.35` line-height.
- Category is token-backed, with one shared top-margin correction and `1.4` line-height, preventing a legacy Daylight-only offset from determining card hierarchy.
- Descriptions, operational summaries and disabled reasons use at least `1.5` body leading, preserving wrap and three-line card description clamp.
- Manage eyebrow, title, subtitle and state gain breathing room; action eyebrows remain distinct from labels and supporting prose.
- Status badges/chips wrap instead of forcing horizontal width; their status labels and colors are not fabricated.
- Narrow PhotoPrism workflow labels are not shrunk to `.68rem`; stage semantics, symbols and connectors remain source-derived.

## 5. Dark treatment and Azure semantic authority

No new hex palette. The visual hierarchy continues to use the **currently present** token families from `azureHorizonTokens.css`:

- Surfaces: `--azure-canvas`, `--azure-surface`, `--azure-raised`, `--azure-input`
- Separation: `--azure-border`, `--azure-strong-border`, `--azure-shadow`, `--azure-panel-shadow`, `--azure-backdrop`
- Copy and emphasis: `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-font-ui`
- Controls: `--azure-button`, `--azure-button-text`, `--azure-hover`, `--azure-pressed`, `--azure-selected`, `--azure-focus`
- Status: `--azure-success`, `--azure-success-subtle`, `--azure-warning`, `--azure-warning-subtle`, `--azure-danger`, `--azure-danger-subtle`, `--azure-neutral`, `--azure-neutral-subtle`
- Shape/space: `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card`

Existing semantic backgrounds, disabled colors, focus rings, and hover states continue to resolve through the theme provider and `liteThemeRuntime.js`. The CSS adds no Dark-only padding scale. **Perceptual visual balance is pending human review.**

## 6. Desktop layout

The page keeps `PageHeader`, `LiteRefreshButton`, search/filter toolbar, featured card, multi-app grid and empty states. Cards use consistent inset, section gaps and action-footer spacing without widening grid columns.

The Manage sheet keeps the actual existing `desktop-movable` marker, useDesktopManageGeometry's viewport clamp, keyboard move/reset/resize, pointer capture and current close handling. This change adjusts only interior padding, heading rhythm, action-row copy, tabs, workflow and storage/backup group spacing. The nested Details overlay keeps its own toolbar and viewport geometry.

## 7. Mobile layout

At 320/360/375/390/430/768px, the original responsive breakpoints and grid/sheet rules remain. Mobile cards and the status filters may wrap; buttons keep a 44px minimum target. Manage's `compact`, `medium`, and `expanded` states remain owned by `useMobileSheetSnap`; only interior padding changes. The preexisting portal scroll containment and safe-area padding in `src/index.css:13937–14041` remain authoritative. Workflow steps remain three-across where supported, with the existing stacked 320–360px fallback. Avoid clipping sticky controls and scroll content during future qualification.

## 8. Component coverage and reuse

| Surface | Reused implementation | This PR's scoped treatment |
|---|---|---|
| Catalog/toolbar | `AppCatalogScreen`, `PageHeader`, `LiteRefreshButton`, search/filter | consistent fields/gutters and button spacing |
| App cards | `AppSummaryCard` → `GlassCard`, `StatusBadge`, `LiteButton` | shared inset, headings, description, status/footer |
| Status chips | `AppStatusChips` | wrapping and line-height; no new status logic |
| Manage | existing portal, sheet, section tablist and overlays | scroll-column and header/content rhythm only |
| Action rows | `AppActionRow` with shared badge/button/elevation | row inset, icon/copy, disabled reason, control gaps |
| Photo workflow | existing three-stage rail and state indicators | label legibility, step spacing, preserved connectors |
| Photos/storage/backup | `PhotoPrismMediaSummary`, existing disclosure, backup metrics | panel/guidance padding and wrapped text |
| Nested Action Details | `AppActionDetailsLazy` and `LiteProgressiveDetails` | section gap, disclosure/technical-row legibility |
| Loading, offline, errors | `LoadingCard`, `LiteFreshness`, `LiteEmptyState`, `StateSurface` | no backend facts or loading semantics changed |

## 9. Exact upstream traceability

These refer to **existing current-main files**, not to new code in this branch.

| PR | Existing file / symbol (base line range) | Existing behavior | Reuse or change here |
|---|---|---|---|
| [#606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606) | `src/components/ui.jsx:131–148` `GlassCard`, `StatusBadge`; `src/lite/LiteUi.jsx:815–850` `PageHeader`, `LiteButton` | accessible shared card, status, header, control primitives | **Unchanged**, used via existing catalog components |
| #606 | `src/lite/LiteUx.jsx:12–55` `LiteFreshness`, `LiteEmptyState` | saved and unavailable surfaces | **Unchanged** |
| #606 | `src/lite/liteDesignSystemP0.css` | shared initial CSS foundation | **Unchanged**, no competing global density layer |
| [#622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622) | `src/lite/theme/azureHorizonTokens.css:1–76` | Light/Dark semantic surface, text, border, status, interaction, shape and common spacing tokens | **Unchanged**, consumed by Apps-scoped declarations |
| #622 | `src/lite/theme/LiteThemeProvider.jsx`; `src/lite/theme/liteThemeRuntime.js` | Light/Dark/System preference resolves to document-level data attribute | **Unchanged** |
| [#623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623) | `src/lite/components/useDesktopManageGeometry.js:1–186` | desktop move/resize/viewport clamp shared with Devices | **Unchanged**, no dimension or gesture policy change |
| #623 | `src/lite/catalog/AppCatalogScreen.jsx:2231–2375`; `src/lite/components/useMobileSheetSnap.js:5–25` | portal Manage, named panel state and mobile snaps | **Unchanged** |
| #623 | `src/lite/catalog/AppActionRow.jsx:1–75` | action semantics, shared controls, disabled reasons | **Unchanged component**, Apps-only CSS updated |
| [#629](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/629) | `AppCatalogScreen.jsx`, `appsPremiumRefinement.css` | premium cards, filter/refresh and scroll presentation | **Preserved**, shared-density CSS layered onto existing implementation |
| [#634](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/634) | `AppCatalogScreen.jsx`, `src/lite/LiteCatalog.stories.jsx`, `tests/e2e/lite-apps-azure-final-polish.spec.ts` | tablist, disclosures, snap controls, authored visual matrix | **Preserved**, additional paired story and parity coverage |
| [#635](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/635) | `appsPremiumRefinement.css:1010–1468`, `AppCatalogScreen.jsx:1511–1532` | header/tool separation and PhotoPrism three-stage rail | **Targeted typography/spacing edits**, no workflow or movement rewrite |

Original PR history may have further subsequent changes; the actual modified source was read at the recorded `main` SHA.

## 10. Changes and new qualification source

| File | Change |
|---|---|
| `src/lite/catalog/appsPremiumRefinement.css` | Apps-scoped density variables and consistent shared layout; narrow workflow font protection; no new palette |
| `src/lite/LiteCatalog.stories.jsx` | paired Light/Dark desktop/mobile, System, Manage, Details, long-text and status cases |
| `src/lite/catalog/AppBalancedDensity.test.jsx` | lightweight card, chip, enabled and disabled action render/dispatch contracts |
| `tests/e2e/lite-apps-theme-density-parity.spec.ts` | computed-style and box comparisons, System resolution, viewport/overflow, scenarios, mobile snaps, reflow, keyboard and Axe |
| `tests/e2e/lite-apps-theme-density-visual.spec.ts` | candidate screenshots **without any PNG baselines** |
| This document | scope, authority, unmeasured assumptions, handoff, rollback |

No backend, API, SQLite, worker, agent, NATS, auth, policy, or release files were changed.

## 11. Qualification design — not executed

The parity suite compares corresponding DOM selectors at fixed viewports with identical mocked data, reduced motion and font loading completed. It compares padding/margin/gap, font and border values, min-height, alignment and rect x/y/width/height. Computed style values should be equal. Bounding-box comparison allows **2px** for fractional rounding. Legitimate wrapping may change box heights when content or viewport differs, so comparisons use identical fixtures; any cross-theme difference requires investigation, not tolerance expansion by default.

The separate visual suite uses named, unbaselined screenshot candidates. **A first run may report missing snapshots by design.** Review the rendered result visually *before* approving new PNG references. Existing canonical approved screenshots must not be overwritten without review. Colors intentionally differ across themes; pixel equality between Light and Dark is not a requirement.

The fixture scenarios cover healthy/running, unavailable and disabled, failed, saved/offline, completed photo backup, remote destination unavailable, generic apps, open Manage, nested Details, 200% text, and mobile snap states.

## 12. Deferred qualification commands

Run only in a **subsequent, explicitly authorized qualification session**, from the DEV-PC worktree with dependencies provisioned. These commands are documentation, not evidence that anything was executed:

```bash
# Focused components and geometry controllers
npx vitest run src/lite/catalog/AppBalancedDensity.test.jsx src/lite/catalog/AppActionDetailsLazy.test.jsx src/lite/catalog/useDesktopManageGeometry.test.jsx src/lite/components/useMobileSheetSnap.test.jsx

# Mocked computed-style parity / viewport / Axe
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-apps-theme-density-parity.spec.ts --project=mocked-desktop --project=mocked-mobile

# Existing Apps regression and geometry suite
npm run test:apps:final:mocked
npm run test:apps:final:geometry
npm run test:apps:final:a11y

# Paired Storybook presentation
npm run storybook
# Inspect BalancedDensity* stories manually on desktop and mobile, then:
npm run build-storybook

# After explicit human review of new visual references ONLY:
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-apps-theme-density-visual.spec.ts --project=mocked-desktop --project=mocked-mobile
# Approved capture/promotion requires a separate review decision; do not
# blindly pass --update-snapshots or rewrite existing approved PNGs.

# Standard repository validation
npm run build
npm run test:a11y:states
task lite:check
```

Optional isolated Android/Termux verification: serve a distinct exact-SHA candidate using existing repo-owned Android qualification helpers and compare screenshots/performance with current stable main. Keep the production Server Phone unchanged and never execute install/backup/repair actions as part of visual inspection.

## 13. Expected acceptance

At 320, 360, 375, 390, 430, 768, 1280 and wider desktop, Light/Dark/System should show consistent computed layout, no unintended document/card/panel overflow, 44px or larger primary controls, readable labels, preserved tablist/keyboard focus and safe sheet scrolling. PhotoPrism's source-reported progress must not change, and the 200%-text variant must remain accessible. Confirm no unintended visual effects in Devices or other tabs.

## 14. Limitations and residual risks

- No browser-computed Light/Dark box measurements exist yet for this change; source inspection alone cannot prove visual parity.
- The existing global CSS still has legacy Daylight and high-specificity rules. Only Apps-scoped overrides with clear relevance were added; broad cascade cleanup is intentionally excluded.
- A larger font can require taller content and deeper Manage scrolling; confirm buttons, workflow connectors, and sheet accessibility at 320px/200% text.
- Existing visual references may legitimately need reviewed replacement; none were modified here.
- Android absolute frame-time SLOs have historical platform limitations. This branch has no new runtime benchmark evidence.
- If unrelated CI fails automatically, diagnosis/remediation is deferred; CI result was not used as a release gate in this authoring session.

## 15. Rollback

Before merge, close the Draft PR and abandon the feature branch without changing `main`. If subsequently merged with authorization, use a targeted Git revert of the merged commit on a new branch and qualify that revert. Avoid force-updating `main`, deleting unrelated branches, or touching runtime configuration. There is no data migration or backend rollback action.

**Final status at source authoring:** implemented source changes; **qualification pending**, visually unapproved, not deployable or merge-authorized.
