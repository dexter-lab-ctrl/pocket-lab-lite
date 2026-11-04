# Pocket Lab Lite — Azure Horizon Safety visual hardening (R0–R7)

> **Implementation provenance:** SOURCE AUTHORED — NOT EXECUTED — NOT QUALIFIED. This note describes repository-source changes made on `feat/safety-azure-horizon-visual-hardening`, based on `main` at `2f3433ffbdc5a548f62b51112703b1015056009d` (PR #640 merged). No browser, Android, build, test, screenshot, accessibility, documentation generation, performance or CI checks were executed during authoring. Statements below marked **source-verified** refer to inspected source, not measured runtime outcomes.

## Objective and visual problem statement

After PR #640, Safety still had inconsistent Light/Dark portalled surfaces, low-contrast text, light rectangular nested panels, duplicated Coverage and progressive-details titles, mobile grid text compression, inconsistent decorators, and oversized mobile snap-header actions. R0–R7 implement a **focused presentation refinement**, not a new information architecture or Security workflow.

The retained presentation is **Safety landing → three focused destinations → grouped Manage Safety → on-demand details**, with one Quick Scan primary action. Desktop retains the existing movable/resizable panel; mobile retains the shared Compact/Medium/Expanded sheet and the index→selected detail→Back interaction. Status, scores, check coverage and actions remain FastAPI-derived.

## R0 — Source-level ownership and conflict audit

| Source-verified conflict | Owner before change | Authoritative owner and treatment | Preserved behavior |
|---|---|---|---|
| `.lite-security-manage-row` used `auto minmax(0,1fr) auto`, including text-and-action rows | `src/index.css` original Security skin | Corrected base grid to text + action; Safety width-based variant in `security/safetyCenter.css` preserves three-column icon/severity rows and stacks constrained content | Finding severity, view/remediation buttons and multi-control rows |
| Legacy hardcoded `#0f172a`, `#64748b`, white gradients and pale backgrounds with `!important` | `src/index.css` historic Security block | Corrected main panel/header/close/section declarations at source to Azure roles; replaced prior dark-only exemption in `security/safetyCenter.css` with one token-driven selector scoped to Safety portal roots | No unrelated tab palette replacement; scanner semantics unchanged |
| Separate dark-only portal fix block (Manage but not all nested sheets) | `security/safetyCenter.css` | Replaced existing block, rather than appending another dark override; applies to both Manage and focused details through `html[data-lite-theme]` | Body portals still use resolved theme and existing scroll/focus infrastructure |
| Ordinary prose inherited `overflow-wrap:anywhere` | `security/safetyCenter.css`, old `src/index.css` Security rows | Safety prose uses `break-word`, `word-break:normal`, `hyphens:none`; technical code/IDs retain a separate break policy | Safe evidence representation and sanitization unchanged |
| `SafetyManageNavigation` rendered selected `h2`, while `LiteSecurity.jsx` repeated its label in section `span` and `h3` | Two React heading owners | Navigation owns the selected `h2` and description; selected content owns only genuine content subsections such as `Quick safety coverage` `h3` | Accessible section routing, Back, deep on-demand details |
| Focused `LiteSheet` title was repeated by inner progressive-details and finding headers, including second Close button | `LiteOverlay.jsx`, `SecurityProgressiveDetailsLazy.jsx`, `SecurityFindingDetailsLazy.jsx`, `LiteProgressiveDetails.jsx` | `LiteSheet` owns dialog title, description and Close; Safety presentation of shared progressive details keeps the result summary and detail sections without a second `Details` heading | Status, history, disclosure and technical detail remain available |
| Mobile snap actions consumed excessive header width | `LiteOverlay.jsx`, `mobileSheetSnap.css` | New opt-in `mobileHeaderVariant="safety"` only on Safety sheets; existing snap hook remains authority; compact two-row header aligns title/Close then status/Compact/Expand | Compact/Medium/Expanded, drag grip, keyboard, accessibility, safe area, reduced motion |
| Generic success color and green score treatment could imply fully checked state | Historic `src/index.css` & Safety score-ring | Reported-score progress uses neutral Azure accent; checked/partial/failed/skipped outcomes retain independent semantic colors and backend data | No fabricated status or changed scanner output |

**Inferred / unvalidated:** Without rendered screenshots and computed-style evidence, selector-cascade coverage and contrast remain unproven in the browser. A later qualification session must inspect all nested sheet states, including low-width desktop geometry.

## R1 — Semantic Light / Dark / System authority

The repository's authoritative tokens remain in `src/lite/theme/azureHorizonTokens.css`; the resolver is `src/lite/theme/liteThemeRuntime.js`, and `LiteOverlay.jsx` updates the legacy compatibility classes on portalled layers when the resolved `data-lite-theme` attribute changes.

| Safety role | Existing token |
|---|---|
| Main sheet, selected content and nested primary surface | `--azure-surface` |
| Inner detail cards, actions, status facts | `--azure-raised` |
| Primary and secondary text | `--azure-text`, `--azure-muted` |
| Borders and control affordances | `--azure-border`, `--azure-strong-border` |
| Selected navigation | `--azure-selected`, `--azure-accent` |
| Hover / pressed / keyboard focus | `--azure-hover`, `--azure-pressed`, `--azure-focus` |
| Informational highlight | `--azure-accent-subtle` |
| Checked / review / failure / skipped indicators | `--azure-success-subtle` + `--azure-success`; `--azure-warning-subtle` + `--azure-warning`; `--azure-danger-subtle` + `--azure-danger`; `--azure-neutral-subtle` + `--azure-neutral` |
| Input and sanitized machine text | `--azure-input` |
| Portal backdrop and panel depth | `--azure-backdrop`, `--azure-panel-shadow` |
| Shared geometry | `--azure-radius-card`, `--azure-radius-control`, `--azure-spacing-card` |

The implementation does **not** introduce a parallel Safety palette. Existing legacy `!important` declarations require **scoped** semantic authority at the Safety portals until all historical consumers can be retired in a separate, qualified cleanup. No broad global stylesheet rewrite or unrelated component re-theming is intended.

## R2 — Text, action rows and containment

The ordinary Safety row is text + action with `minmax(0, 1fr) auto`. Severity-led finding rows intentionally retain an icon/severity track, flexible text and actions when room is available. In Safety's existing `.lite-security-manage-scroll` inline-size container, rows transition at 520 CSS pixels to a single-column layout, with full-width actions; the profile chip stays content-width. Ordinary prose no longer uses arbitrary mid-word breaking. Long paths, hashes and machine strings only receive a specific technical-code overflow policy.

Deferred width matrix:

- Mobile: **320, 360, 375, 390, 430px**.
- Tablet/desktop/panel: **768, 1024, 1280, 1440, 1920px**.
- Appearances: **Light, Dark, System-light, System-dark**.
- Additional: **200% text scaling, reduced motion, safe areas, nested scroll, viewport overflow, desktop Move/Reset/Resize**.

The container query uses the **actual content width**, not a desktop viewport assumption. Geometry and typography metrics are theme-independent, following #636 without adopting Apps-specific spacing overrides.

## R3 — Heading hierarchy and surfaces

One owner per layer:

1. **Manage Safety** — dialog title from `LiteSheet`.
2. **Coverage** — selected `h2` and one sentence from `SafetyManageNavigation`.
3. **Quick safety coverage** — genuine `h3` inside the Coverage content.
4. **On-demand focused details** — one separate `LiteSheet` title and summary; no redundant inner heading or secondary Close control.
5. **Detail titles** — safe content-section titles, not repeated dialog chrome.

The selected Manage section itself becomes a transparent grouping surface rather than another white bounded card. Cards remain on their existing tokenized inner surfaces; no pseudo-element masks the old rectangle.

## R4 — Detail decorators and semantic truth

The shared `LiteProgressiveDetails`, `LiteTechnicalDetails` and `LiteHistorySection` accept an optional `presentation="safety"` variant. Other consumers retain `default`. This avoids copying summarization, redaction, progressive mount and history behavior.

| Meaning | Lucide icon | Owner |
|---|---|---|
| What happened | `Info` | `LiteProgressiveDetails` |
| What changed | `GitCompareArrows` | `LiteProgressiveDetails` |
| What needs attention | `AlertTriangle` | `LiteProgressiveDetails` |
| What did not happen / protected boundary | `ShieldCheck` | `LiteProgressiveDetails` |
| Next step / recommended action | `ArrowRightCircle` | `LiteProgressiveDetails` and remediation guidance |
| Saved for troubleshooting | `FileCheck2` | `LiteProgressiveDetails` |
| History | `History` | `LiteHistorySection` |
| Technical details | `Settings2` | `LiteTechnicalDetails` |
| What it means | `CircleHelp` | Safety remediation |

Icons are decorative (`aria-hidden`) and do not replace accessible text or encode scanner success. Status colors are based on the existing classes created from actual view models; a failed, partial, missing or timed-out check is never converted to a green success claim.

## R5 — Native mobile sheet header

The current `LiteSheet` and `useMobileSheetSnap` remain authoritative. Safety opts into `mobileHeaderVariant="safety"`; its title and Close appear in the first compact row, with snap-state guidance and compact-but-accessible Compact/Expand controls beneath. The existing dedicated handle remains visible and retains gesture/keyboard snap semantics.

No new mobile controller, drag gesture, fixed sheet height, event trap or desktop geometry implementation was created. Desktop continues to reuse `useDesktopManageGeometry` for Move/Reset/Resize; reduced motion and focus behavior remain owned by `LiteOverlay.jsx`.

## Source-verified component and design reuse matrix

| Reference | Current source actually inspected / retained behavior | Reuse or change in this PR | Why not duplicated |
|---|---|---|---|
| **#606** | `LiteUi.jsx`: `GlassCard`, `StatusBadge`, `StateSurface`, `LiteButton`; `LiteProgressiveDetails.jsx` | Safety retains shared button/state primitives; explicit optional Safety variant for progressive details, technical/history | Shared feedback, sanitizer and disclosure remain one implementation |
| **#622** | `azureHorizonTokens.css`, `azureHorizon.css`, `liteThemeRuntime.js` | Exact existing theme roles listed in R1, no new tokens | One resolver for Light/Dark/System |
| **#623** | `components/useDesktopManageGeometry.js` | Hook, panel style, Move/Reset/Resize, keyboard clamping retained; **not modified** | Existing geometry authority and accessibility |
| **#629** | `catalog/AppCatalogScreen.jsx`, `catalog/appsPremiumRefinement.css` | Referenced density and progressive disclosure; **not modified** | No Apps-specific CSS copied into Safety |
| **#634** | `components/useMobileSheetSnap.js`, `components/mobileSheetSnap.css`, `LiteOverlay.jsx` | Shared Compact/Medium/Expanded hook retained, opt-in Safety header layout added in `LiteOverlay`; hook/CSS **not modified** | No second mobile snap implementation |
| **#635** | `LiteOverlay.jsx`, `catalog/appsPremiumRefinement.css` | Shared close/button/control convention reused; Safety only scopes toolbar alignment | No global Apps geometry change |
| **#636** | `catalog/appsPremiumRefinement.css`, Azure geometry token references | Theme-neutral Safety geometry authored using shared radius/padding tokens; Apps CSS **not modified** | Avoid separate Light/Dark spacing |
| **#637** | `catalog/AppCatalogScreen.jsx` | Library summary→Manage→detail disclosure referenced; **not modified** | Safety retains its own native layout |
| **#638** | `LiteHome.jsx`, `components/HomeGroupedSections.jsx` | Focused destinations and container-based hierarchy referenced; **not modified** | No competing Home cards/navigation |
| **#639** | `identity/AccessManageNavigation.jsx` | Grouped index, `aria-current`, selected heading, Back vs Close semantics retained in Safety; Access **not modified** | One established navigation pattern, separately owned |
| **#640** | `SafetyNativeCenter.jsx`, `LiteSecurity.jsx`, `safetyCenter.css`, `SecurityProgressiveDetailsLazy.jsx` | Landing, destinations, current Safety projections, Manage navigation, overlay composition retained; presentation and ownership corrected | Backend state model and scan workflow preserved |
| **Recovery** | `LiteRecovery.jsx`, shared `LiteOverlay` / `useDesktopManageGeometry` | Same semantic focus/navigation/control roles referenced; Recovery **not modified** | No cross-tab regression surface added |
| **#588** | PR #588 performance contract and existing `liteNavigationRuntime.js` | No performance thresholds changed; same low-power, reduced-motion and animation-containment intent retained | Separate performance qualification remains authoritative |

**Source-verified files inspected:** Safety source, its CSS, `src/index.css`, theme tokens, `LiteOverlay`, shared progressive/technical/history, shared hooks, Apps/Home/Access/Recovery owners, PR metadata and relevant existing Storybook/Playwright source. The file-to-PR associations are based on GitHub's changed-file listings and current source; historical PR descriptions are contextual only. No browser was launched.

## R6 — Qualification authored, not executed

- Component: `src/lite/security/SafetyNativeCenter.test.jsx` single selected heading; `src/lite/components/LiteProgressiveDetails.safety.test.jsx` semantic icon mapping, no fake success, optional Safety scope, redacted/collapsed technical/history.
- Stories: `src/lite/LiteSecurity.stories.jsx` expanded with healthy, partial, unavailable, first-run, offline, activity, nested details, remediation, Coverage, Findings, Evidence, History, Technical, Run Checks, and Compact/Medium/Expanded states. Existing stories now expect the `h2` heading owner.
- Playwright: `tests/e2e/lite-safety-azure-visual-hardening.spec.ts` covers all target widths × appearance modes, semantic tokens, text tracks, section surfaces, nested details, snap controls, keyboard, focus, overflow, explicit WCAG AA, non-text indicators, reduced motion, 200% text and desktop geometry. Existing Safety and native geometry specs remain unchanged.
- Visual candidate tests and physical Android CDP cases are **deferred**; no screenshots or canonical PNG baseline updates were made.

**Validation status:** Build **NOT RUN** · Component tests **NOT RUN** · Playwright **NOT RUN** · Storybook **NOT RUN** · Screenshots **NOT GENERATED** · A11y **NOT RUN** · Android CDP **NOT RUN** · Docs generation **NOT RUN** · CI investigation **NOT PERFORMED**.

### Deferred commands — do not execute in this authoring session

```bash
npm run build
npx vitest run src/lite/security/SafetyNativeCenter.test.jsx src/lite/components/LiteProgressiveDetails.safety.test.jsx
npx playwright test tests/e2e/lite-safety-azure-visual-hardening.spec.ts --project=mocked-desktop --project=mocked-mobile
npx playwright test tests/e2e/lite-azure-horizon-safety.spec.ts tests/e2e/lite-safety-native-geometry.spec.ts --project=mocked-desktop --project=mocked-mobile
# Review visual candidate captures against PR #640 references before promoting any baselines.
# Run the separate physical-Android Safety-only CDP qualification afterward.
```

The next session must confirm contrast numerically, inspect both parent and nested overlays, safe-area and scroll behavior on Android/browser/PWA, evaluate actual current fonts, and compare layout geometry between appearance variants. Keep #588/#589 performance budgets and attribution semantics unchanged; do not run the seven-screen Android matrix for this Safety-only change.

## Backend boundaries and data preservation

No FastAPI, NATS/JetStream, worker, agent, supervisor, scan policies, SQLite state, evidence writer, auth, SSE replay, cache, or snapshot code is changed. Quick/Full/App scan actions, required confirmations, cancellation, progress, same-profile comparison, and saved/offline precedence remain backend-owned and unchanged. No browser shell, secrets, direct NATS, raw evidence, invented scan result or unauthorized execution path is introduced.

## Risks and rollback

**Unvalidated risks:** CSS import order and `!important` cascades; portal nesting and Escape/focus return; screen-reader heading navigation; compact/expanded sheet scroll; real 320px and 200% text rendering; System appearance toggling; partial/offline status contrast; unit/story fixtures; non-CSS animation/render cost; physical Android CDP behavior. The new test source may need revisions after initial execution, and visual baselines deliberately remain unapproved.

**Rollback:** Withhold/close the Draft PR and retain `main` unchanged. Before merge, revert the targeted feature commits or delete the feature branch only by explicit authorization. After merge, revert the specific PR through standard GitHub rollback; do not reset `main`, force push, or repackage a release.

## Enterprise value and disposition

Consistency and truthfulness of Safety surfaces improve operator comprehension while limiting CSS conflicts, eliminating redundant heading narration and preserving explicit backend provenance. **Source authored — awaiting qualification; Draft PR only; unmerged, undeployed, unreleased.**
