# Azure Horizon — Safety Rules refinement

> [!IMPORTANT]
> IMPLEMENTATION ONLY — UNVALIDATED. No tests, builds, CI troubleshooting, lint, screenshots, contrast measurement, benchmarks or physical Android qualification were executed. The main repository remains source of truth.

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

Black, Daylight and System are expected to preserve identical content, geometry and permission gates. Controls and history are color-aware without using colors as the only state indicator. Contrast and complete inherited dark behavior remain UNVALIDATED pending browser inspection.

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

No WCAG AA claim is made without Axe and computed contrast measurements. Screen-reader nested-overlay, mobile soft keyboard and 200%-text observations are DEFERRED.

## 9. P4 — authored, never executed

Unit: src/lite/rules/rulesAzureHorizon.test.jsx; existing premium view/Journey, shared geometry tests.
Mocked: tests/e2e/lite-azure-horizon-rules.spec.ts; theme, state, width, role, Manage, geometry, Axe, focus, simulation.
Screenshots: tests/e2e/lite-azure-horizon-rules-visual.spec.ts; 320–1440, themes, Enterprise forms, requests, exceptions, decision and resized Manage.
Instrumentation: tests/e2e/lite-azure-horizon-rules-performance.spec.ts; first paint and key interactions, no threshold change.
Storybook: src/lite/LiteRules.stories.jsx additions, using existing createLiteStory and MSW fixtures.
Taskfile/npm: test:rules:azure:unit, mocked, a11y, geometry, visual, perf, qualification; and corresponding lite:test:rules:azure:* tasks.

**DEFINED — CAPTURE AND APPROVAL DEFERRED.** No screenshot baseline was generated or approved. New screenshot tests are intended for an independent owner review/capture session and are not claimed to pass. Existing PR #588 hard performance gate thresholds remain untouched.

## 10. Validation plan — NOT RUN, CODEX STABILIZATION ONLY

- npm run test:rules:azure:unit
- npm run test:rules:azure:mocked
- npm run test:rules:azure:a11y
- npm run test:rules:azure:geometry
- npm run test:rules:azure:visual (after independent screenshot baseline approval)
- npm run test:rules:azure:perf
- npm run build
- npm run test:mock-regression
- npm run test:a11y:states
- npm run test:perf
- task lite:check

The future session must additionally assess color contrast, PWA 200% zoom, lost network, mobile safe areas, responsive forms, all Enterprise roles, passkey step-up, safe approval/rollback/exception stories, Devices/Apps/Identity geometry regression, and Android/Termux physical runtime performance. Any CI failures are for later analysis; they were not investigated here.

## 11. Risks, rollback, and enterprise value

- **UNVALIDATED:** CSS specificity with older Daylight-scoped Rules definitions, Azure portal inheritance, mobile overflow, screen reader focus and pointer handling, all new and old test outcomes.
- **UNVALIDATED:** screenshot baselines, contrast and performance. No claim of green CI, 60 FPS, Android qualification or successful protected live operation.
- **Risk:** client-side safeguards are supplementary; backend capability and confirmation must remain mandatory.
- **Rollback:** revert these branch commits before merge, or close the draft PR. Do not touch main, live Rules policy/revisions, Android deployment or release tags.
- **Enterprise value:** auditable protection/authorization explanations, consistent shared accessibility/mode presentation, lower UI training cost and trustworthy separation of policy request, authorization and actual execution.

## 12. Current release/merge disposition

OPEN — DRAFT — NOT MERGED. No release/deployment authorization. All implementation source remains unvalidated.
