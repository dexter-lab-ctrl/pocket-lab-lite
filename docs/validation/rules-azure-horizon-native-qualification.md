# Azure Horizon Rules Center — P0–P7 qualification handoff

> **AUTHORED — NOT EXECUTED.** No build, tests, lint, Playwright, Storybook execution, accessibility scanner, screenshots, CI reruns, benchmarks or device qualification were performed.

## Source baseline and ownership

- Repo: dexter-lab-ctrl/pocket-lab-lite.
- Baseline main: 463ad47de66345955e448e47df346c9525ffd67f.
- Feature branch: feat/azure-horizon-rules-center-revamp.
- PR #641 was confirmed merged into the baseline.
- Screen and Manage state: src/lite/LiteRules.jsx.
- Enterprise backend capability and role presentation: src/lite/LiteRulesEnterprise.jsx.
- Protection/decision/activation projections: src/lite/rules/rulesPremiumView.js.
- Journey and progressive details: src/lite/rules/RulesProtectionJourney.jsx, RulesDecisionInsight.jsx, RulesPremiumTimeline.jsx.
- Rules layout owner: src/lite/rules/rulesPremium.css.
- Legacy Rules-owned declarations inside src/lite/identityRules.css have Daylight-only selectors normalized for resolved-theme scope.
- Rules activation styles: src/lite/rulesActivationProgress.css, now using Azure semantic color tokens.
- Shared LiteSheet, useMobileSheetSnap, useDesktopManageGeometry, and installLiteGlobalHaptics remain authoritative.

## Implementation matrix

| Phase | Authored source changes | Gate |
| --- | --- | --- |
| P0 | CSS ownership, semantic tokens, theme-independent layout contract | AUTHORED — NOT EXECUTED |
| P1 | One server-authoritative Protection Center hero, one Manage action | AUTHORED — NOT EXECUTED |
| P2 | Interactive illustrative protection journey, compact Latest Decision | AUTHORED — NOT EXECUTED |
| P3 | Desktop settings split workspace; mobile grouped navigation and focused detail | AUTHORED — NOT EXECUTED |
| P4 | Shared mobile snap controller on Manage/Insight/activation, safe-area and text-scale CSS | AUTHORED — NOT EXECUTED |
| P5 | Decision explanation and backend-only activation-state truth | AUTHORED — NOT EXECUTED |
| P6 | Azure semantic tokens, Lucide, global haptics plus failure-only warning, reduced motion | AUTHORED — NOT EXECUTED |
| P7 | Unit assertions, Storybook scenarios, mocked Playwright coverage and visual contracts | AUTHORED — NOT EXECUTED |

## Appearance matrix

| Viewport | Daylight | Dark | System |
| --- | --- | --- | --- |
| Desktop 1280px | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED |
| Tablet 768px | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED | Deferred additional baseline |
| Mobile 390px | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED | Deferred additional baseline |
| Mobile 360px | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED | Deferred additional baseline |
| Mobile 320px | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED | Deferred additional baseline |
| 200% text, reduced motion | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED | Deferred manual review |
| Saved/offline/backend unavailable | AUTHORED — NOT EXECUTED | AUTHORED — NOT EXECUTED | Deferred manual review |

No visual screenshots were produced, updated or approved. Playwright snapshot assertions are baseline contracts requiring a later authorized baseline-generation and human-review session.

## Rules and roles matrix

Future qualification must cover healthy/degraded/unavailable protection, verified/unverified revision, update required, activation pending/running/failed, rolling back/rolled back/uncertain, decision allow/block/step-up/approval, no decision, saved decisions, Personal Mode and Enterprise Owner/Admin/Operator/Auditor/Viewer. The existing mocked fixture catalog and view-model unit tests provide authored coverage where source-backed. Missing fixture combinations must not be presented as verified live events.

**Mandatory security assertions:** No healthy state for uncertain/saved data; authorization is never evidence of execution; an accepted update never means successful activation; earlier activation steps remain unconfirmed absent server evidence; archived/saved state cannot authorize writes; Enterprise role checks, passkey step-up, independent approvals, NATS/worker execution and audit evidence remain backend-owned. No browser-held secrets or direct shell/NATS access.

## Qualification commands — future session only

**DOCUMENTED ONLY — NOT EXECUTED:**

    cd ~/pocket-lab-lite
    git fetch origin
    git switch feat/azure-horizon-rules-center-revamp
    npm run build
    npx vitest run src/lite/rules/rulesPremiumView.test.js
    npx playwright test tests/e2e/lite-azure-horizon-rules.spec.ts tests/e2e/lite-rules-native-center-qualification.spec.ts --project=mocked-desktop --project=mocked-mobile
    npm run test:a11y:states

Expected after authorized execution: clean build; no serious/critical WCAG AA findings; stable keyboard focus/return; desktop move/resize/reset and viewport containment; mobile Medium/Compact/Expanded snapping with no accidental dismiss; readable 320px and 200% text; Daylight/Dark bounds parity; System resolved theme; source-truthful decision/activation/role behavior.

**Separate owner-approved screenshot baseline session only:**

    npx playwright test tests/e2e/lite-rules-native-center-qualification.spec.ts --project=mocked-desktop --project=mocked-mobile --update-snapshots

Do not automatically accept image differences. Review all snapshot candidates, including light/dark density against PR #636, mobile headers, settings rows and nested Enterprise forms, before committing baselines.

## CSS ownership and risks

Azure Horizon tokens are reused for canvas, surfaces, borders, muted text, selected states, accent, focus, success, warning, danger and shadows. New layout geometry is Rules-scoped and theme-independent, with CSS container-query fallback when a movable desktop panel becomes narrow.

**UNVALIDATED:** Historical shared selectors in src/index.css and src/lite/identityRules.css; portalled overlay color and focus interactions; CSS container query and layout resizing on some Android browsers; 320px/200% text; contrast ratios; Safari/iOS no-vibration fallback; system appearance changes while the sheet is open. Computed style, visual comparison and device behavior were not evaluated.

## Performance and edge-first qualification

Keep the existing PR #588 performance budgets. In a later authorized session review first Rules paint, idle API request cadence, Manage open, scrolling, interaction responsiveness, memory and battery usage on ARM64/PWA, and absence of additional polling. No runtime measurements were made here.

## Release boundaries

CI may run automatically after GitHub writes; no CI result was inspected, rerun, investigated or fixed in this session. No branch was merged, no release or tag was created, no live Server Phone process was touched, and no deployment occurred.

**All qualification gates: AUTHORED — NOT EXECUTED.**
