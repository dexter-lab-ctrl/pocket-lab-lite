# Azure Horizon Apps — Final Visual Stabilization (P0–P2)

> [!IMPORTANT]
> **SOURCE AUTHORED, UNVALIDATED.** This file is an implementation handoff, not visual, accessibility, unit, desktop, Android or production runtime evidence. No tests, builds, checks, benchmarks, screenshots, documentation/contract generation, CI investigation, Android CDP or Server Phone qualification were executed in this authoring session.

## 1. Executive summary and provenance

| Field | Source-authoring value |
|---|---|
| Repository | `dexter-lab-ctrl/pocket-lab-lite` |
| Base branch | `main` |
| Exact main SHA at branch creation | `2f25837463009b940a330817c3a9c412f9e1a4b8` |
| Feature branch | `feat/azure-horizon-apps-final-polish` |
| Prior Apps refinement | PR [#629](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/629), merged; historical merge `19ab217e42b4e585db7d21f52ff15d893bf5c510` |
| Scope | Apps visual surfaces, tab/disclosure consistency and opt-in overlay interaction |
| Status | **IMPLEMENTATION SOURCE AUTHORED / ALL CHANGES UNVALIDATED** |

The work preserves the Universal App Platform, generic application cards and app-specific capability boundaries. It does not introduce new backend commands, media operations, security exceptions, secrets, third-party runtime dependencies, or page-level design systems.

## 2. Scope, screenshots and root cause inventory

| ID | Screenshot/source symptom | Inspected source cause | Targeted source change | Validation |
|---|---|---|---|---|
| A1 | Daylight blocks within Black Manage | Legacy `.theme-pocket-lite-daylight` selectors in `src/index.css` coexist with newer portal and premium CSS; nested cards had different surface ownership | Scoped Azure token ownership for primary/raised/selected/warning/disabled/scroll/details surfaces | NOT RUN |
| A2 | Black Open/Manage gap crowded | Card action container and button geometry were not a single theme-neutral contract | Shared `.lite-catalog-actions`/`.lite-catalog-card-actions` flex/grid gap and 44px controls | NOT RUN |
| A3 | Featured description repeated as status | Card independently renders `app.description || app.summary` and `lifecycle.summary || canonical.statusSummary` | Generic `distinctCatalogStatusSummary` comparison, keeps operationally distinct status | NOT RUN |
| A4 | Close and decorative cue collided | Shared cue was absolutely placed near the close button; header did not reserve a control zone | Explicit title/status + Move/Reset/Resize + Close header, optional cue removed from this Manage surface | NOT RUN |
| B1 | Apps tabs differ from Recovery | Apps tabs were scrollable raised pills; Recovery used segmented selected/neutral styles | Reuse Recovery's Azure selected, hover, border, inset accent and keyboard/tablist contract | NOT RUN |
| B2–B4 | Storage/notices/guide disclosure unclear | Native summaries lacked a consistent visible open-state indicator | One CSS chevron disclosure pattern, retained native `details/summary` and existing backend facts | NOT RUN |
| C1–C3 | Detached desktop Resize | Apps used a bottom-right grip even though PR #623 shared geometry already existed | Header-owned Move/Reset/Resize; nested Action Details opts into same geometry hook | NOT RUN |
| C4–C6 | Grip dismisses, no snap control | Mobile grip closed Manage rather than controlling height | Opt-in shared 3-state snap controller with pointer capture, cancellation and accessible controls | NOT RUN |

These are **source-based diagnoses**, not claims of reproduced browser failures.

## 3. Source ownership and implementation

| Owner | Source files / symbols | Purpose |
|---|---|---|
| Apps UI | `src/lite/catalog/AppCatalogScreen.jsx` / `CatalogManagePortal`, `renderAppCard`, `PhotoBackupTruthCard` | Generic card copy, Manage header, sheet snap, disclosures, PhotoPrism capability-only facts |
| Apps presentation | `src/lite/catalog/appsPremiumRefinement.css` | Semantic surfaces, Recovery-style tabs, spacing, disclosure icon, responsive layout |
| Shared legacy cascade | `src/index.css` | Removes forced selected-tab overrides in favor of semantic source ownership |
| Generic copy | `src/lite/catalog/catalogPresentation.js` / `distinctCatalogStatusSummary` | Independent description/status deduplication |
| Desktop geometry | `src/lite/components/useDesktopManageGeometry.js` | **Reused unchanged** for Apps Manage, nested Details, Devices and existing consumers |
| Mobile geometry | `src/lite/components/useMobileSheetSnap.js` | **New shared, opt-in** snap-point/state/pointer controller |
| Mobile presentation | `src/lite/components/mobileSheetSnap.css` | Shared token-based snap controls and scroll/safe-area geometry |
| Shared overlay | `src/lite/LiteOverlay.jsx` / `LiteSheet`, `LiteDetailsPanel` | Adds optional `mobileSnap` prop; existing callers retain default behavior |
| Recovery precedent | `src/lite/recovery/recoveryPremium.css` / `.lite-recovery-manage-tabs` | **Inspected, unchanged** selected-state reference |
| Theme authority | `src/lite/theme/azureHorizonTokens.css` | **Inspected, unchanged** semantic palette for resolved Daylight/Black/System |
| Qualification | `src/lite/components/useMobileSheetSnap.test.jsx`, `src/lite/catalog/catalogFinalPolish.test.js`, `tests/e2e/lite-apps-azure-final-polish*.spec.ts`, `src/lite/LiteCatalog.stories.jsx`, `package.json`, `tasks/Taskfile.ui.yml`, `playwright.config.ts` | Authored but not executed |

## 4. PR #606 reusable component boundary

| Requirement | Origin | Exact current file / symbol | Reuse |
|---|---|---|---|
| Standard actions | #606 | `src/lite/LiteUi.jsx` / `LiteButton` | Existing Open/Manage/Details button primitives retained |
| Operational states | #606 | `src/lite/LiteUi.jsx` / `StatusBadge`, `StateSurface` | Existing status, access notices and disabled consequences retained |
| Details | #606 and subsequent shared overlay work | `src/lite/LiteOverlay.jsx` / `LiteDetailsPanel`, `LiteSheet` | Extended by an optional snap flag, no replacement |
| Focus safety | #606/shared overlay baseline | `src/lite/LiteOverlay.jsx` / `useFocusTrap`, `useFocusReturn` | Existing trapping, Escape and focus return retained |
| Existing progression | #606 + Apps follow-ups | `src/lite/catalog/AppActionDetailsLazy.jsx` | Existing backend-truthful details content untouched |
| Universal Apps | #600/#607 and #623 | `src/lite/catalog/AppCatalogScreen.jsx` | Generic cards, capability-driven action sets retained |

No new button, badge, generic Details or focus-trap framework was introduced.

## 5. Azure Horizon semantic token matrix

All values below come from `src/lite/theme/azureHorizonTokens.css`; these are **source declarations**, not measured browser computed styles. System follows the existing resolved `data-lite-theme` on the document root.

| Component / state | Semantic token | Daylight | Black |
|---|---|---|---|
| Page canvas | `--azure-canvas` | `#F4F9FF` | `#050607` |
| Manage primary / Details | `--azure-surface` | `#FFFFFF` | `#0B0F14` |
| Nested action, facts, control | `--azure-raised` | `#E7F2FF` | `#121822` |
| Borders | `--azure-border` | `#D5E5F8` | `#1F2A36` |
| Selected tab border | `--azure-strong-border` | `#A8C4E2` | `#37516B` |
| Selected tab | `--azure-selected` | `#DFEEFF` | `#142941` |
| Text | `--azure-text` | `#142841` | `#E6EDF7` |
| Secondary text | `--azure-muted` | `#5B7088` | `#A4B3C4` |
| Accent underline/chevron | `--azure-accent` | `#006BC7` | `#4AA8FF` |
| Focus | `--azure-focus` | `#075FAF` | `#79C5FF` |
| Hover | `--azure-hover` | `#D9ECFF` | `#19283B` |
| Warning state | `--azure-warning-subtle` | `#FFF1D7` | `#352B1B` |
| Disabled / neutral | `--azure-neutral-subtle` | `#EAF0F8` | `#18212A` |
| Input | `--azure-input` | `#FFFFFF` | `#0F1620` |
| Backdrop | `--azure-backdrop` | `rgba(12,28,47,.48)` | `rgba(0,0,0,.74)` |
| Radius | `--azure-radius-card`, `--azure-radius-control` | Shared `1.25rem` / `.8rem` | Same |
| Panel elevation | `--azure-panel-shadow` | Declared semantic shadow | Declared semantic shadow |

No new Apps-only color palette, fixed FQDN, screen credential or private backend path is introduced.

## 6. P0 theme, gap, duplicate and header decisions

- The nested portal continues to inherit document-level Azure variables. Portal rules are explicitly scoped to `html[data-lite-theme]` and an Apps premium marker. The standard app action rows use raised tokens; their parent scroll region uses the main surface. Warnings and disabled actions remain visually distinct, not falsely complete.
- Open, Manage and Install remain `LiteButton` instances with a common 44px minimum and layout gap independent of a legacy Daylight class. Mobile uses two columns when possible and one column at very narrow width.
- `distinctCatalogStatusSummary` does not know PhotoPrism's identity or description. It compares normalized copy and leaves genuine backend lifecycle and readiness text intact.
- Mobile title/state/Close sit in a separate header row. The decorative shared element cue is not rendered in Apps Manage. Desktop geometry controls are inside the header, not in a detached corner.

## 7. Recovery-style Apps tab and accessible disclosure decisions

The Apps `role="tablist"` and `role="tab"` semantics, `aria-selected` and tabpanel association remain in the existing React source. Arrow-left/right, Home and End remain handled by the Apps tablist; narrow widths use a horizontally scrollable tab strip. CSS follows Recovery's semantic transparent inactive, `--azure-selected` selected, strong border, inset accent and Azure focus ring. Recovery source is not edited.

Storage/device details, Other action notices and photo education preserve native `<details><summary>` semantics. A pseudo-element chevron rotates based on `[open]`, without JS state, new click listeners or unstable rerender keys. Expanded content retains structured backend facts; the Photo Backup educational three steps stack at mobile widths. Backend blockers, action readiness and disabled reasons remain accessible.

## 8. Desktop overlay architecture and PR #623 geometry

`useDesktopManageGeometry({open,defaultWidth:620})` still owns the main Manage panel; nested Action Details now uses a separate instance with `defaultWidth:580`. Each panel has its own ref, pointer capture and keyboard control group. Movement, resizing, Home reset, viewport clamping and visual-viewport updates remain implemented by the **existing shared hook**; no new desktop geometry mechanism was authored.

| Surface | Desktop Move | Resize | Reset | Mobile snap | Focus owner | Status |
|---|---|---|---|---|---|---|
| Apps Manage | Header | Header | Header | Opt-in | Existing Manage trap/return | AUTHORED, NOT RUN |
| Apps Action Details | Shared `LiteDetailsPanel` header | Same | Same | Opt-in | Nested Details trap/return | AUTHORED, NOT RUN |
| Devices Manage | Existing | Existing | Existing | Unchanged | Existing Devices owner | NOT MODIFIED |
| Home Workspace Details | Existing | Existing | Existing | Unchanged | Existing Home owner | NOT MODIFIED |
| Confirm / destructive modal | Unchanged | Unchanged | Unchanged | Off | Existing dialog owner | NOT MODIFIED |

Do not enable parent and child drag on the same pointer. Nested Action Details overlays already stack above Manage; the parent focus trap is disabled while details are selected, and each desktop controller has a distinct grip/control target.

## 9. Shared opt-in mobile controller API

`useMobileSheetSnap({ open, enabled, surfaceRef, initialState='medium' })` returns:

| API | Meaning |
|---|---|
| `state` | `compact`, `medium`, `expanded` |
| `active` | Whether the opt-in controller owns this open mobile panel |
| `style` | Height for the current state, capped to viewport |
| `gripProps` | Pointer capture, move, up/cancel/loss and keyboard listeners, accessible label |
| `expand()`, `contract()`, `resizeTo(state)` | Explicit non-gesture alternatives |
| `canExpand`, `canContract` | Disable unavailable direction controls |
| `mobileSheetHeight`, `closestMobileSheetState` | Pure geometry helpers for unit tests |

Compact ~35%, Medium ~72%, Expanded ~94% of available visual viewport, clamped below viewport height. Grip-only drags apply height directly to the surface during pointer movement to avoid frame-by-frame React state updates. State commits on release; pointer cancellation or capture loss restores the starting state. No content scroll is connected to dismissal, and the grip does not close the panel. An explicit Close remains mandatory.

The shared `LiteSheet` gains `mobileSnap=false` by default. `LiteDetailsPanel` forwards this opt-in and continues to accept existing desktop geometry. Only the two relevant Apps overlays opt in. A future tab migration should first review its component-specific scroll, headers, focus, nested sheets and confirmation safety.

## 10. Accessibility and responsive behavior

- Modal roles, labels, focus return, Escape handling and nested overlays remain owned by existing components.
- Tabs retain the native ARIA pattern plus a visible semantic focus ring.
- Disclosures remain native, keyboard-toggleable and visually distinguishable in both open/closed states.
- Grip keyboard shortcuts: Arrow Up/Down, Page Up/Down, Home and End; explicit Expand/Compact buttons are available for non-gesture users.
- 44px control targets for close, action buttons, tabs and snap controls.
- Mobile header remains outside the independently scrollable body. The body hides in Compact without remounting content.
- Safe-area insets and visual-viewport resize clamp heights; no forced fixed IP/domain or Android-only browser API.
- Reduced motion suppresses snap-height/chevron transitions.
- Responsive qualification matrix authored for 320, 360, 390, 430, 768 and desktop widths; no actual viewport checks executed.

## 11. Security, authority, generic app and performance boundary

The data flow remains **React/Vite PWA → Caddy → FastAPI `/api/lite/*` → NATS/JetStream → worker/agent/supervisor → sanitized evidence → FastAPI → UI**. The frontend does not execute shell commands, connect to NATS, store backend secrets, perform app backup, transfer media, restore, update or remove processes. App-specific PhotoPrism surfaces continue to be gated on the app capability/identity checks already present.

PR #588's frame/LoAF/React commit budgets and PR #589's attribution/stop-condition policy are unchanged. This implementation favors CSS-driven disclosure, limited React state changes on snap and the existing geometry hook. **No performance measurement or target claim is made.**

## 12. Authored qualification inventory — NOT RUN

| Coverage | Source |
|---|---|
| Generic status-copy deduplication | `src/lite/catalog/catalogFinalPolish.test.js` |
| Snap ratios, keyboard, pointer release/cancel, viewport, opt-in | `src/lite/components/useMobileSheetSnap.test.jsx` |
| Existing desktop geometry regression carried into scripts | `src/lite/catalog/useDesktopManageGeometry.test.jsx` |
| Responsive, themes, tabs, disclosures, nested focus, Axe, drag, generic app, saved state, backup scenarios | `tests/e2e/lite-apps-azure-final-polish.spec.ts` |
| Unapproved screenshot specifications | `tests/e2e/lite-apps-azure-final-polish-visual.spec.ts` |
| Existing Apps interaction performance retained | `tests/e2e/lite-apps-azure-premium-polish-performance.spec.ts` |
| Storybook surface variants | `src/lite/LiteCatalog.stories.jsx` (`AzureFinal*`) |
| Discovery | `playwright.config.ts` updated for mocked desktop/mobile |
| Invocation | `package.json` `test:apps:final:*`; `tasks/Taskfile.ui.yml` `lite:test:apps:final:*` |

Storybook states cover Daylight/Black/System, generic app, saved offline, 200% text, desktop controls, mobile Compact/Medium/Expanded, storage and notices disclosures, photo guide, ready/not-ready backup and nested Details.

Visual specifications require human review and explicit snapshot promotion **in a later qualification session**. These specifications were not executed, and PNG files were not created.

## 13. Deferred qualification plan

Run only in a separately authorized validation session; **none was run here**:

```bash
npm run test:apps:final:unit
npm run test:apps:final:mocked
npm run test:apps:final:a11y
npm run test:apps:final:geometry
npm run test:apps:final:storybook
npm run test:apps:final:performance
npm run test:apps:final:visual       # Requires approved screenshot references
npm run build
task lite:check
```

After Dev PC completion, evaluate a separate Android CDP and read-only Server Phone candidate plan using explicit runtime authorization and the exact feature SHA. Check visual-viewport behavior with soft keyboard, TalkBack/keyboard, pointer cancellation, System theme transitions, 320px and 200% text. Do not deploy or use production credentials for mocked tests.

Canonical MkDocs and contract generation/checking must be performed only in the future qualification phase, not this source authoring work.

## 14. Risks, unvalidated assumptions and rollback

- CSS source-order/specificity must be checked in an actual Vite bundle; legacy `src/index.css` remains large and some unrelated legacy selectors still exist.
- Playwright visual specs intentionally have no new baseline PNGs. Their first ordinary comparison can fail until reviewed/promoted.
- Body scroll, nested focus return, soft keyboard, pointer capture and width breakpoints need device/browser testing.
- The visual design, gesture thresholds, mobile height policy and WCAG/60 FPS targets are **unvalidated**.
- The existing 60 FPS contract cannot be declared passing from authored sources.
- No backend/API migration is necessary; revert the feature PR or the specific Apps CSS/controller/overlay commits on the feature branch if qualification identifies regressions. Keep main unchanged until separately authorized.

## 15. Final disposition

- **SOURCE:** Authored and committed on a feature branch.
- **TESTS / STORIES / COMMANDS:** Authored, NOT RUN.
- **VISUAL SNAPSHOTS:** NOT GENERATED, NOT APPROVED.
- **DEV PC / ANDROID CDP / SERVER PHONE:** NOT RUN / UNTOUCHED.
- **DOCUMENTATION / CONTRACT GENERATION:** NOT RUN.
- **CI:** NOT INVESTIGATED OR REMEDIATED.
- **PR:** DRAFT; not merged, tagged, deployed or released.

> No validation tasks, tests, builds, checks, benchmarks, screenshots, documentation generation, contract generation, Android CDP qualification, or Server Phone runtime qualification were executed, as explicitly instructed. All newly implemented changes remain unvalidated.
>
> CI failures were not investigated or remediated.
