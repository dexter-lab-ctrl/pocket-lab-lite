# Premium Rules Center — implementation handoff

**Scope:** P0–P3 source authoring, not qualified. **Base:** `main` at `f90403e292e62f548e674f65bbc46a386a145056`.
**Branch:** `feat/rules-premium-refinement`. **Validation:** expressly deferred by the owner.

## Objective and screen hierarchy

The previous Rules page displayed an operational story, explanation guide, protection-area list, three overlapping overview cards, an update card, an Enterprise panel, and a separate Manage sheet. The new default is intentionally limited to **Safety Rules hero → Protection Journey → Latest Decision**, plus conditional safety/update/activation notifications and the established page Refresh control.

| Level | Content | Data provenance |
|---|---|---|
| Main hero | Protection status, supported update readiness and mode | Prepared `liteApi.policy`, separately `identitySelf` |
| Journey | Four interactive Request → Evaluate → Decision → Outcome descriptions | Explicitly educational, not a fabricated real trace |
| Latest Decision | One actual reported protected decision, or empty state | `policy.recent_decisions` |
| Manage | Overview, protections, decisions, policies and technical status | Existing policies; Enterprise sections mounted only on demand |
| Decision Insight | Who / What / Why / What Next and optional technical facts | Selected server-provided decision; Enterprise Details hydrated using existing decision API |
| Activation / revision | Server-reported stage and revision facts | Source-sync and existing Enterprise health/revision reads |

No browser-held policy authority is introduced. An empty, saved, stale or unreachable read never proves a healthy Rules engine.

## Components and presentation

- `src/lite/LiteRules.jsx`: summary-first Rules screen, source-sync control retained behind Manage, one Refresh in page header, responsive `LiteSheet` Manage and Insight surfaces.
- `src/lite/rules/rulesPremiumView.js`: strict outcome and readiness projection. Rejects inferred actors, targets, execution and revision history. `allow` means policy authorization, **never downstream success**.
- `RulesProtectionJourney.jsx`: four native-button stages with `aria-expanded` and an explicit educational disclaimer; inspect mode only displays actual provided decision facts.
- `RulesDecisionInsight.jsx`: Who → What → Why → What Next; explicit simulation disclaimer; missing actor/target is unavailable; raw payloads, policy source and credentials are never displayed.
- `RulesPremiumTimeline.jsx`: decision chronology, activation state rail and current revision/recovery comparison; no timer-driven advancement.
- `LiteRulesEnterprise.jsx`: previously supported policy candidates, Owner passkey activation, rollback, request review, simulation, exceptions, role matrix, revision and lazy decision hydration remain backed by the existing API. Enterprise sections are embedded in the **single** Rules Manage navigation.
- `rulesPremium.css`: scoped low-cost styling, responsive two- or one-column Journey on narrow screens, text wrapping, focus visibility and reduced-motion behavior.

## Truth and security contracts

1. **Simulation:** `simulateRule` is hypothetical. No permission or operation is granted. A simulated allow state is labeled *Simulation allowed*, not *Authorization allowed*.
2. **Authorization:** A real policy result can allow or block a request, or report step-up / review needs. Missing booleans/outcome do not mean blocked or allowed.
3. **Execution:** Only separately reported `execution_status` or `execution_state` from a trusted server response is labeled execution state. No action completion is inferred from policy allowance.
4. **Activation:** `pending`, `validating`, `switching`, `restarting`, `verifying`, `active`, `rolling_back`, `rolled_back`, `failed`, `not_completed`, `uncertain` are kept semantically distinct. A missing operation after a tracked activation resolves to *uncertain*, not synthetic success. Known-good revision authority is not changed client-side.
5. **Revisions:** Current active/known-good comparison is factual; historical transitions are never synthesized from a revision array.
6. **Saved/offline:** Read-only information can be reviewed but cannot authorize a Rules update; current server confirmation and role capability remain mandatory.
7. **Security:** PWA → Caddy → FastAPI /api/lite/* → NATS/JetStream → worker/agent/supervisor → sanitized event/evidence → FastAPI → UI. The browser never connects to NATS, runs commands, stores backend secrets, or displays raw OPA source. Protected Server Host and independent approver rules remain backend-controlled.

## Manage and role mapping

Personal Mode presents Overview, Protections, Decisions, Policies and Technical Status. Enterprise adds Test a Change, Policies, Requests, Temporary Access, Revision & Recovery and Governance. Existing server-returned capabilities gate draft/activate/rollback, simulate, review and temporary access; hidden UI is not a security boundary. The Owner still requires passkey step-up for root-level policy updates, but not unnecessary peer approval.

Manage and Decision Insight each use the established shared `LiteSheet`; the Enterprise decision explanation is inline inside its active Manage section to avoid a nested modal trap. Expensive Enterprise reads mount only when an Enterprise Manage section is opened. The latest decision uses the existing prepared policy read, not a default full Enterprise history call.

## Responsive / accessibility intent

Use native stage buttons, four semantic ordered Journey steps, headings, accessible labels and selected/expanded state. CSS uses `min-width:0`, wrapping and no forced single-line labels. 320–1440px widths, browser zoom, mobile safe-area sheet, reduced-motion media query, consistent focus management and low-power animation constraints are covered in **authored** tests, not proven by a renderer.

**WCAG 2.2 AA compliance has not been qualified.** Contrast against actual translucent surfaces, focus restoration, keyboard/screen-reader traversal and physical Android/PWA behavior require later execution/manual review.

## Authored tests (not executed)

- Pure presentation: `src/lite/rules/rulesPremiumView.test.js`.
- Journey, Insights and timelines: `src/lite/rules/RulesProtectionJourney.test.jsx`.
- Storybook: `src/lite/LiteRules.stories.jsx` with personal, Enterprise roles, saved/degraded, activation, mobile, expanded journey, Manage, and Insight states.
- Browser/Axe: `tests/e2e/lite-rules-premium-refinement.spec.ts`.
- Visual: `tests/e2e/lite-rules-premium-visual.spec.ts` (**no PNGs generated or approved**).
- Performance instrumentation: `tests/e2e/lite-rules-premium-performance.spec.ts`, without changing established gate thresholds.
- Activation compatibility: `tests/e2e/lite-rules-activation-progress.spec.ts` reflects fail-closed no-synthetic-success semantics.

## Known limitations / qualification

The main screen uses the latest entry of `policy.recent_decisions`; it does not load an entire Enterprise history by default. Inspect Decision's stage evaluation description is illustrative when backend does not supply a complete trace. Some fixtures may need expanding during the validation session for explicit step-up, pending review, rolling-back and long-reason responses. No screenshot baselines were rendered because test execution was prohibited. Source semantics, browser interaction, accessibility, contrast, motion, performance and runtime remain **unvalidated** until the next session.

## Future validation session — commands **not executed here**

```bash
npm run test:rules:premium:unit
npm run test:rules:premium:mocked
npm run test:rules:premium:visual
npm run test:rules:premium:perf
npm run test:a11y:states
npm run test:mock-regression
npm run build
npm run build:budget
task lite:test:rules:premium:unit
task lite:test:rules:premium:mocked
task lite:test:rules:premium:visual
task lite:check
git diff --check
```

For visual baselines, run the **specific** Playwright visual spec with `--update-snapshots` only after approved rendering and review. Do not overwrite unrelated approved baselines. Follow with read-only isolated Android/Termux qualification and separate CI investigation if required. Generated docs/contracts may need a future refresh; none were run or falsified in this implementation-only session.
