# Azure Horizon — Safety Rules refinement

> [!IMPORTANT]
> QUALIFICATION PARTIAL — Dev-PC Rules validation, approved mocked visual baselines, Storybook, accessibility, responsive behavior and shared visual regressions are verified at feature HEAD `924047f3661ab2f96d1fc7acc75f6210ed08ec9f`. Physical Android candidate identity and read-only Rules smoke are verified, but the live runtime returned degraded Rules reads and the repository Android baseline harness could not complete its required 28-interaction runs. Enterprise synthetic-owner qualification is blocked because the Server Phone harness transport is unavailable. No protected live mutation was attempted.

## 1. Objective

Transform the existing Safety Rules tab into the Azure Horizon reference protection center, without rebuilding Rules authorization, OPA/policy execution, approval, activation, rollback or temporary access. Desktop and mobile share the same backend facts, role gates and explanatory content.

## 2. Current baseline and preserved architecture

Verified main before feature: 5a8f9980dcf037973c072cd23454bde942a95065. Implementation branch: feat/azure-horizon-rules-ui.

React/Vite PWA → Caddy same-origin → FastAPI /api/lite/* → NATS/JetStream → worker/agent/supervisor → sanitized evidence → FastAPI → Rules UI.

Frontend never executes a shell command, accesses NATS, stores secrets, creates permission grants, simulates success or treats offline snapshots as live authority.

## 3. Reference and reuse matrix

| Reference | Source actually reused | Responsibility |
| --- | --- | --- |
| [PR #606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606) | src/lite/LiteUi.jsx: PageHeader, GlassCard, LiteButton, StatusBadge, StateSurface, LiteActionRow, LiteRefreshButton | Consistent header/cards/actions/status/error/loading, no parallel Rules widgets |
| PR #606 | src/lite/LiteOverlay.jsx: LiteSheet | Responsive modal, portal, focus trap/return, Escape, internal scroll, nested Details |
| PR #606 | src/lite/LiteUx.jsx: LiteFreshness, LiteTechnicalFacts | Saved/stale freshness and on-demand technical evidence |
| [PR #622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622) | src/lite/theme/azureHorizonTokens.css, azureHorizon.css, LiteThemeProvider.jsx | Global Black/Daylight/System palette, semantic status/surface/input/focus tokens |
| [PR #623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623) | src/lite/components/useDesktopManageGeometry.js | Shared viewport-clamped move/resize/reset controls and accessible announcements |
| [PR #624](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/624) | src/lite/LiteIdentity.jsx, identity/identityPremium.css, LiteOverlay.jsx | Shared Manage header controls, protected overlay presentation and focus behavior; Identity auth logic not copied |
| [PR #588](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/588) | tests/e2e/lite-performance.spec.ts and lite-performance-helpers.ts | Existing 60 FPS performance contract, hard gates and instrumentation remain unchanged |

## 4. P0 — theme and CSS ownership

The only new Rules styles live in the existing src/lite/rules/rulesPremium.css. Shared identityRules.css and identityRulesGovernance.css are untouched. Scoped semantic colors use the root azure tokens for text, elevated surfaces, borders, statuses, focus, fields, selects, textareas and native color-scheme. The responsive Rules portal derives theme from the shared LiteOverlayRoot and existing document appearance. It uses no new theme provider, hardcoded palette, font service or animation library.

Black, Daylight and System preserve identical content, geometry and permission gates in the mocked visual and accessibility lanes. Controls and history are color-aware without using colors as the only state indicator. Axe severe/critical scans passed in all three appearances, including reduced-motion and 200%-text cases; numerical contrast-ratio evidence is not separately committed and remains `UNVALIDATED` for a standalone AA ratio claim.

## 5. P1 — responsive protection overview

Desktop order: Azure PageHeader (Help, one Refresh, Manage) → protection hero → responsive two-column Journey and Latest Decision → activation attention when reported. No second application header or unrelated status dashboard.

Mobile order: existing header/navigation → hero and freshness → vertical Request/Evaluate/Decision/Outcome journey → Latest Decision → backend-reported activation or update attention. The viewport breakpoint is 700px and below; single-column at 320, 360, 375, 390, 430 and tablets; 200%-text scenarios are defined for later qualification.

The hero consumes rulesProtectionView. Only engine-healthy, loopback-restricted, valid, not-updating current Rules can become Ready. Mode and revision statements depend on current backend state. No protection scores are invented.

The Journey remains illustrative, selected by keyboard and associated aria-controls. Selection does not advance any live operation. Latest Decision consumes rulesDecisionView, with status, action, reason, available timestamp, and a separate four-question RulesDecisionInsight. Allowed authorization is not execution.

## 6. P2 — Manage Safety Rules

Personal mode retains Overview, Protections, Decisions, Policies and Technical Status. Enterprise Mode routes managed sections to the existing embedded LiteRulesEnterprise for Protection, Policies, Test a Change, Activity, Requests, Temporary Access and Revision & Recovery.

The Manage header identifies state, mode and revision. The existing LiteSheet owns Escape, focus return, focus trap, portal, modal roles, safe scrolling and bottom-sheet treatment. RulesDecisionInsight is an independent Details sheet without desktop geometry.

Desktop only: useDesktopManageGeometry returns panelRef, desktopPanel, panelStyle, reset, startPanelInteraction, adjustPanelWithKeyboard and announcement. Designated header buttons move, resize and reset. Arrow keys use 16px steps; Shift uses larger steps; Home resets. The same hook handles viewport and visualViewport resize/reclamp, with transient geometry only. Minimum requested 380×360 and default width 680 are subject to viewport clamping. Inputs, policy selects, buttons, confirmations and nested overlays are never drag handles.

At <=700px: geometry controls are absent and native shared mobile bottom sheet is used. No geometry is persisted in localStorage.

## 7. P3 — protected Enterprise behavior

Current Rules backend continues to own candidate creation, parameter validation, activation, verification, known-good rollback, simulation, approval transitions, temporary access and Owner passkey step-up. Personal safe default and Enterprise opt-in are unchanged. Role-aware capability keys remain authoritative for Owner, Admin, Operator, Auditor and Viewer.

Rules status is not inferred from HTTP reachability alone. Enterprise mutations now reject stale, saved or unreachable Rules/access state at the UI boundary. This is defense in depth; backend authorization remains the actual gate. Disabled forms show reasons; live server still determines eligibility.

Policy candidate creation is a draft, not activation. An accepted activation request is not a verified active revision. Activation timeline and revision history use reported operation states; unknown, failed and rolled-back are not success. Owner step-up still uses server-provided WebAuthn options and purpose-bound verification; no frontend bypass exists.

Test a change is simulation only, with bounded supported revision/action/target/context and no actual grant. The response and Decision Insight remain labeled simulation. Review request acceptance does not execute the original action; Owner does not gain a new peer-review requirement. Temporary access stays narrow, expiring and scoped to actual supported app/action/person/device, with backend-owned active/expired/revoked evidence. Cached states cannot request or revoke an exception.

Enterprise toast/notice wording no longer labels a server request response as “Rules updated” without active-state evidence.

## 8. Accessibility and responsive alignment

Existing focus management, touch targets and accessible status components are reused. Journey buttons expose explanatory names, expanded state and controlled content. Timeline exposes actor/target when reported. The Rules page and portal use azure-focus ring, azure-muted readable captions and tokenized select/input surfaces. Muted text is not communicated by opacity alone. Narrow layouts stack forms and retain scrollable long content. Reduced-motion CSS disables cosmetic transitions and animations.

`npm run test:rules:azure:a11y` passed 28 tests across Black, Daylight, System, 200% text and reduced motion. The broader `npm run test:a11y` passed 2 suites and `npm run test:a11y:states` passed 36 state cases. Content stress passed 14 cases covering 320/390/430/768/1280 widths, 200% text, mobile Manage and navigation reachability. Screen-reader announcement quality, soft-keyboard interaction on a physical device, and a standalone computed contrast-ratio report remain `UNVALIDATED`; no WCAG AA certification is claimed.

## 9. P4 — authored and qualified where supported

Unit: src/lite/rules/rulesAzureHorizon.test.jsx; existing premium view/Journey, shared geometry tests.
Mocked: tests/e2e/lite-azure-horizon-rules.spec.ts; theme, state, width, role, Manage, geometry, Axe, focus, simulation.
Screenshots: tests/e2e/lite-azure-horizon-rules-visual.spec.ts; 320–1440, themes, Enterprise forms, requests, exceptions, decision and resized Manage.
Instrumentation: tests/e2e/lite-azure-horizon-rules-performance.spec.ts; first paint and key interactions, no threshold change.
Storybook: src/lite/LiteRules.stories.jsx additions, using existing createLiteStory and MSW fixtures.
Taskfile/npm: test:rules:azure:unit, mocked, a11y, geometry, visual, perf, qualification; and corresponding lite:test:rules:azure:* tasks.

**CAPTURED — INSPECTED AND APPROVED.** The 106 new mocked desktop/mobile/theme/width/Enterprise/Decision Insight/Manage screenshots were captured, visually inspected, committed and pass `npm run test:rules:azure:visual`. The six existing Rules snapshots that changed because of the feature’s new header, status chips and Manage geometry were inspected and promoted as approved baselines; `npm run test:visual:states` passed 42/42 and `npm run test:visual:overlays` passed 14/14. Existing PR #588 performance thresholds remain untouched. Physical Android screenshots are qualification evidence only and are not promoted to Playwright baselines.

## 10. Validation record

- `npm run test:rules:azure:unit` — **PASS**, 4 files / 21 tests.
- `npm run test:rules:premium:unit` — **PASS**, 2 files / 10 tests.
- `npm run test:rules:azure:mocked` — **PASS**, 46 tests.
- `npm run test:rules:premium:mocked` — **PASS**, 38 tests.
- `npm run test:rules:azure:geometry` — **PASS**, 24 tests across 320–1440px and shared move/resize/reset/clamp behavior.
- `npm run test:rules:azure:a11y` — **PASS**, 28 tests.
- `npm run test:rules:azure:visual` — **PASS**, 106/106 approved baselines.
- `npm run test:rules:azure:perf` — **PASS**, 2 tests.
- `npm run test:perf:components` — **PASS**, 27 tests; `npm run test:perf:mocked` had three initial renderer-sensitive non-Rules misses, then its focused rerun passed 4/4. `npm run check:render-budgets` reported 0 hard-gate failures and only unrelated target-only misses.
- `npm run test:e2e:mocked` — **PASS**, 52 passed / 10 skipped; `npm run test:phase9:qualification` — **PASS**, 12; `npm run test:content-stress` — **PASS**, 14.
- `task lite:test:storybook` — **PASS**, Storybook built and 16 representative renders passed.
- Physical Android candidate — **PARTIAL**: exact candidate SHA/header/metadata proof passed; read-only Rules smoke rendered one hero, one Journey and a mobile Manage sheet with no API writes observed. Five Rules reads returned HTTP 503 degraded responses from the current runtime.
- Physical Android normalized baseline — **BLOCKED**: three control samples were captured, but the required 28/28 interaction matrix could not complete after three attempts because progress/Manage controls were not consistently available. The controls themselves were platform-level misses (`p95` 41.7–42.0ms, `gate_passed: false`), so no repository-normalized candidate classification is claimed.
- `task lite:docs:generate`, `task lite:docs:check` and `task lite:check` are finalization gates and are run after this qualification record is updated.

The future session must additionally assess color contrast, PWA 200% zoom, lost network, mobile safe areas, responsive forms, all Enterprise roles, passkey step-up, safe approval/rollback/exception stories, Devices/Apps/Identity geometry regression, and Android/Termux physical runtime performance. Any CI failures are for later analysis; they were not investigated here.

## 11. Risks, rollback, and enterprise value

- **BLOCKED:** the live Server Phone qualification harness returned `harness_transport_unavailable`; its configuration was not changed. Synthetic Owner, WebAuthn step-up and protected Enterprise mutation behavior therefore remain unvalidated.
- **PARTIAL:** the Server Phone’s current Rules API returned five 503 read-degraded responses through the Dev-PC candidate proxy. The candidate remained read-only and no API write method was observed.
- **PARTIAL:** physical Android baseline normalization is unavailable because the established 28-interaction matrix did not complete. The three captured platform control samples already show the same ~42ms cadence seen by Rules, so no PR-attributable application incremental cost was established, but this is not a full normalized attribution result.
- **VERIFIED:** CSS/theme inheritance, mobile overflow, focus behavior, shared geometry, approved snapshots, Axe state coverage, responsive stress and shared overlay/state visual suites passed in the Dev-PC qualification lanes.
- **UNVALIDATED:** screen-reader announcement quality, physical soft-keyboard behavior, numerical contrast-ratio report, full Android Enterprise workflows and exact-head GitHub CI for the final pushed SHA.
- **Risk:** client-side safeguards are supplementary; backend capability and confirmation must remain mandatory.
- **Rollback:** revert these branch commits before merge, or close the draft PR. Do not touch main, live Rules policy/revisions, Android deployment or release tags.
- **Enterprise value:** auditable protection/authorization explanations, consistent shared accessibility/mode presentation, lower UI training cost and trustworthy separation of policy request, authorization and actual execution.

## 12. Current release/merge disposition

OPEN — DRAFT — NOT MERGED. The Server Phone was restored to its original main release state (`5a8f9980dcf037973c072cd23454bde942a95065`, release `lite-2026.10.22.1`) after the Dev-PC-only candidate session. No release/deployment authorization was used. The feature is Dev-PC qualified with runtime/Enterprise qualification partial or blocked as recorded above; merge remains unauthorized.
