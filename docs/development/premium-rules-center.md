# Premium Rules Center — qualification record

**Scope:** P0–P3 implementation stabilization and qualification record. **Base:** `main` at `f90403e292e62f548e674f65bbc46a386a145056`.
**Branch:** `feat/rules-premium-refinement`. **Physical candidate:** `f4230bdf617097867beaf57b202ffd84e82b1107`. **Final source head at this record:** `ecdfa85f6a87eabeeb5611e1db97c9413139bd09`.
**Dev-PC status:** feature-focused qualification verified. **Physical Android status:** limited Rules smoke qualified on the exact candidate; the broader Android/performance/manual matrix remains partial.

The candidate was authored only on the Dev-PC, committed and pushed to the feature branch. The Server Phone remained a consumer-only runtime: its prequalification checkout was clean `main` at `f90403e292e62f548e674f65bbc46a386a145056`, and no source or production configuration was changed there.

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

Automated accessibility qualification passed the authored Rules states and the broader state matrix (`npm run test:a11y`, `npm run test:a11y:states`). The physical Android Rules smoke exercised the real Chrome renderer, stage selection, Manage navigation and dismissal, but did not qualify device keyboard behavior, screen-reader traversal, large-text/contrast review or the full Android performance matrix. This record does not claim full manual WCAG 2.2 AA conformance.

## Executed qualification

- Pure presentation and Journey tests: `npm run test:rules:premium:unit` — **10 passed**.
- Mocked Rules browser coverage: `npm run test:rules:premium:mocked` — **38 passed**; activation compatibility — **4 passed**; full mocked E2E — **52 passed, 10 skipped**.
- Rules visual contract: `npm run test:rules:premium:visual` — **18 passed**. Reviewed Rules state and overlay references were regenerated only for the refined Rules surfaces; unrelated Identity references were not overwritten.
- Rules performance instrumentation: `npm run test:rules:premium:perf` — **2 passed**. Rules paths in the broader 56-case performance matrix also passed after the hydration and nested-header styling fixes.
- Accessibility/content: `npm run test:a11y` — **2 passed**; `npm run test:a11y:states` — **36 passed**; `npm run test:content-stress` — **14 passed**.
- Build/tooling: `npm run build`, `npm run build:budget`, `npm run build-storybook`, `task lite:test:storybook`, and `npm run test:unit` passed. Storybook rendered 14 representative stories and documented 278 canonical stories.
- Existing Rules/backend governance suites passed their relevant cases. A broader 158-test Rules/governance selection reported **153 passed, 5 OPA/bootstrap failures**. The exact five failures reproduce on clean `origin/main` at `f90403e292e62f548e674f65bbc46a386a145056` with the same stale `pm2_start_or_restart` contract and missing test-harness `pm2_ensure_versioned_process`; PR #611 changes no OPA/bootstrap source or test path, so no backend authority change was introduced.
- Browser visual state and overlay matrices passed after reviewed Rules-only reference updates (`40 passed, 2 unrelated Identity baseline failures`; `14 passed`).
- The two canonical Identity visual mismatches reproduce on clean `origin/main` with the same dimensions and pixel-diff counts; the 24 Identity-premium visual references pass on the candidate. The shared `LiteOverlay` change is therefore not the source of those baseline mismatches.
- Final repository gate: `task lite:check` completed with **exit 0**. Its full path included 416 backend tests, 52 passed/10 skipped mocked E2E cases, 60 documentation browser tests, redaction, Storybook and generated-documentation checks.

## Physical Android, harness and runtime evidence

The repository-owned exact-candidate workflow built and served `f4230bdf617097867beaf57b202ffd84e82b1107` from the Dev-PC. After the approved UAC elevation, `prepare-ui-performance-android-cdp.ps1` reported `READY`; the bridge exposed Android Chrome `155.0.8059.41` at `172.19.0.1:19222`. The physical Rules smoke proved the candidate manifest/header/meta, rendered Rules at a 360px CSS viewport, selected and expanded all four Request/Evaluate/Decision/Outcome stages, opened Manage Safety Rules, selected Technical Status, observed no horizontal overflow, and dismissed the sheet with Escape. Rules API reads were HTTP 200 with no page errors or failed requests. A Manage screenshot was captured and reviewed at `.pocketlab-dev/performance/android-rules-manage-smoke-f4230bdf617097867beaf57b202ffd84e82b1107.png`; the default-page screenshot attempt timed out while waiting for the physical renderer to stabilize. Shared `/api/lite/apps/photoprism/actions` prefetches returned 503 during the smoke and are not Rules endpoints; no Rules API failure was observed.

The owned candidate server, ADB reverse and Android wake lock were cleaned up. The local Windows CDP bridge remains configured for bounded follow-up use; no source, policy, or runtime artifact was changed on the Server Phone. This is **limited physical Rules qualification**, not a full Android performance, keyboard, screen-reader, large-text or contrast qualification.

The read-only Server Phone baseline and restoration checks passed: the final `task lite:runtime:resilience:phone:check` passed health/readiness, PM2 convergence, NATS/Tailscale, agent/supervisor and runtime projections. Rules reported active and known-good revision `plr-c802978be4c9b958df7d3312a30baed1`, with no source update pending. The phone remained on clean `main` at `f90403e292e62f548e674f65bbc46a386a145056`, with no source modifications or candidate deployment. The harness status was safely disabled (`enabled=false`, `qualification_owner=false`, `active_sessions=0`, no profiles returned), so no synthetic Owner qualification was attempted and no authentication bypass was used. Because the OPA comparison found no authority change, comprehensive privileged governance remains deferred to a separate security-focused effort.

The main screen uses the latest entry of `policy.recent_decisions`; it does not load an entire Enterprise history by default. Inspect Decision's stage evaluation description is illustrative when backend does not supply a complete trace. Remaining non-qualifying findings are the two unrelated Identity visual baselines, seven non-Rules shared performance misses, the five pre-existing OPA/bootstrap contract failures reproduced on clean main, the shared exact-head performance variance described below, and the unexecuted broader Android/manual matrix.

## Documentation and remaining gates

After the feature and bounded runtime work, `task lite:docs:generate` completed and `task lite:docs:check` passed with the repository Node 24.16.0 environment. Generated contracts, catalogs, runtime projections, architecture, knowledge/intelligence, development/production/enterprise pages, SchemaSpy, diagrams and Codebase Map are current and redaction-safe. Redocly reported 88 existing warnings but no lint errors; MkDocs completed with repository navigation warnings and no build error.

`task lite:check` is locally verified. Exact-head GitHub Actions run `38705382145` evaluated source head `ecdfa85f6a87eabeeb5611e1db97c9413139bd09`: the isolated job passed ([job 116323386563](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/38705382145/job/116323386563)), while the quick/docs job failed at the shared UI performance contract ([job 116323386384](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/38705382145/job/116323386384)). Rerunning failed jobs on the same exact head produced the same classification ([quick/docs rerun 116333831210](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/38705382145/job/116333831210), [isolated rerun 116333832760](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/38705382145/job/116333832760)): Rules-specific performance passed, but shared Identity desktop frame-budget cases remained below the established smoothness threshold, with Home/overlay variance also observed on the rerun. The Identity case reproduces on clean `main`; no threshold or source relaxation was made. Exact-head CI is therefore **PARTIAL / BLOCKED by a pre-existing shared performance variance**, not green. The PR must remain OPEN and DRAFT; no merge, release or permanent deployment is authorized.

## Requalification command

```bash
task lite:check
git diff --check

# Physical phase, after running prepare-ui-performance-android-cdp.ps1
# from elevated Windows PowerShell:
npm run check:perf:android-cdp
bash scripts/dev/lite/run-ui-performance-android-candidate.sh
```

For visual baselines, run the **specific** Playwright visual spec with `--update-snapshots` only after approved rendering and review. Do not overwrite unrelated approved baselines. Keep all physical Android qualification and any future harness session bounded, auditable and revocable.
