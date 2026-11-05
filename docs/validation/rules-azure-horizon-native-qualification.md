# Azure Horizon Rules Center — P0–P7 qualification handoff

> **VERIFIED — DEV-PC, MOCKED, AND PHYSICAL RULES-ONLY QUALIFICATION COMPLETE; PERFORMANCE TARGET/GATE MISS CLASSIFIED INCONCLUSIVE.** The Rules implementation was built and exercised on Dev-PC, the authored mocked desktop/mobile matrix and visual suites passed, and the exact-SHA Dev-PC candidate was exercised on physical Android Chrome through the repository CDP bridge. The physical run was anonymous and read-only: 28 Rules interactions were attempted, 26 were verified, two device-specific items were unavailable, and no non-GET request or destructive operation was issued.

## Source baseline and ownership

- Repo: `dexter-lab-ctrl/pocket-lab-lite`.
- Authoritative `main`: `463ad47de66345955e448e47df346c9525ffd67f`.
- Starting PR #642 SHA: `fee04eac0ac976f64453a5c0ae9c09828b5af4b6`.
- Physical/source-qualified candidate SHA: `947c91cf56a7b0e62f3a1b7c88e97642968f0a8d`.
- Final documentation and PR SHAs are recorded by the final Git/PR provenance after this document and generated projections are committed.
- Feature branch: `feat/azure-horizon-rules-center-revamp`.
- Server Phone backend SHA: `463ad47de66345955e448e47df346c9525ffd67f`; its checkout remained clean on `main`.
- Screen and Manage state: `src/lite/LiteRules.jsx`.
- Enterprise backend capability and role presentation: `src/lite/LiteRulesEnterprise.jsx`.
- Protection/decision/activation projections: `src/lite/rules/rulesPremiumView.js`.
- Journey and progressive details: `src/lite/rules/RulesProtectionJourney.jsx`, `RulesDecisionInsight.jsx`, `RulesPremiumTimeline.jsx`.
- Rules layout owner: `src/lite/rules/rulesPremium.css`.
- Legacy Rules-owned declarations inside `src/lite/identityRules.css` remain normalized for resolved-theme scope.
- Rules activation styles: `src/lite/rulesActivationProgress.css`, using Azure semantic color tokens.
- Shared `LiteSheet`, `useMobileSheetSnap`, `useDesktopManageGeometry`, and `installLiteGlobalHaptics` remain authoritative.

## Implementation matrix

| Phase | Current evidence | Gate |
| --- | --- | --- |
| P0 | CSS ownership, semantic tokens, theme-independent layout, overflow and geometry assertions; physical 360px candidate geometry | **VERIFIED** |
| P1 | One server-authoritative Protection Center hero and one Manage action; physical hero/open/reopen checks | **VERIFIED** |
| P2 | Four selectable educational Journey stages and server-backed Latest Decision/empty state; physical stage and decision checks | **VERIFIED** |
| P3 | Desktop split workspace; mobile grouped index and focused detail navigation; physical detail navigation and return checks | **VERIFIED** |
| P4 | Shared mobile snapping, safe-area checks, 200% text and reduced-motion coverage; physical snap and wrapping checks | **VERIFIED — 320px physical viewport and native touch unavailable** |
| P5 | Decision explanation and backend-only activation-state truth; physical Decision Insight remained read-only | **VERIFIED** |
| P6 | Azure semantic tokens, Lucide icons, optional haptics, reduced motion and theme parity; physical Daylight/Dark/System checks | **VERIFIED — native touch haptic activation unavailable** |
| P7 | Unit, Storybook fixture, mocked Playwright, accessibility, visual contracts and physical screenshots | **VERIFIED — approved evidence** |

## Dev-PC validation

- `npm run build`: **PASS**.
- Rules Vitest set: **23/23 PASS** across `rulesPremiumView.test.js`, `RulesProtectionJourney.test.jsx`, `rulesAzureHorizon.test.jsx`, and `catalog/useDesktopManageGeometry.test.jsx`.
- Mocked functional Rules/native-center matrix: **100/100 PASS** across `mocked-desktop` and `mocked-mobile`.
- Full targeted visual suites: **124/124 PASS** across `mocked-desktop` and `mocked-mobile`; the ten affected dark mobile landing baselines were regenerated only after inspecting the source-owned Refresh geometry change.
- Accessibility: serious/critical Axe assertions passed in the Rules regression/native-center suites; no serious or critical violations were reported by those checks.
- Responsive coverage exercised 320, 360, 375, 390, 430, 700, 701, 768, 1024, 1280, 1440 and 1920 CSS-pixel cases, plus 200% text and reduced motion.
- Appearance coverage exercised Daylight, Dark and System resolution in mocked fixtures. Geometry parity assertions passed for the Rules hero, Journey, Manage surface, navigation, detail pane and rows.
- Role fixtures exercised Personal Mode and Enterprise Owner/Admin/Operator/Auditor/Viewer capability presentation. No browser-side privileged write was accepted by the mocked tests.
- The native qualification test documentation now identifies the physical lane as Rules-only qualified; deterministic baselines remain separate from physical captures.

## Appearance and Rules state matrix

The existing source-backed fixture catalog and view-model tests cover healthy, degraded, unavailable, revision verified/unverified, update required, pending/running/failed/rolling-back/rolled-back/uncertain activation projections, allowed/blocked decisions, passkey and independent-approval presentation, no decisions, saved/offline state, backend-unreachable state, Personal Mode and Enterprise roles. Mocked assertions preserve these distinctions and do not fabricate live backend evidence.

**Mandatory security assertions verified in the mocked lane:** healthy state is not inferred from uncertain/saved data; authorization is not execution; accepted update is not successful activation; earlier activation steps remain unconfirmed without server evidence; archived/saved state cannot authorize writes; Enterprise role checks, step-up, independent approvals, execution and audit evidence remain backend-owned; no browser-held secrets or direct shell/NATS access exist.

## Visual snapshots

- `tests/e2e/lite-azure-horizon-rules-visual.spec.ts` and `tests/e2e/lite-rules-premium-visual.spec.ts`: **124/124 PASS**, no unexpected diffs.
- The ten dark mobile landing baselines changed only to reflect the verified Rules header Refresh width at narrow viewports. The representative updated 320px image was inspected; the full suite then passed in both mocked projects.
- The native-center suite supplies deterministic Rules snapshots for light/dark desktop and mobile Manage states; representative landing, dark-theme, Policy Settings, activation and 320px images were inspected.
- Final physical captures were inspected separately under `.pocketlab-dev/physical-rules-screenshots-947c91cf56a7b0e62f3a1b7c88e97642968f0a8d/`: landing Daylight, landing Dark, landing System, Manage index, How Protection Works, Decision History, Decision Insight, Expanded, Compact and 200% text.
- **VISUAL SNAPSHOTS — APPROVED.** Mocked baselines are deterministic repository artifacts; physical captures are qualification evidence and are not used as deterministic baselines.

## Android CDP and physical qualification

- Windows ADB resolver selected one authorized physical Android target; the serial is intentionally omitted.
- The repository-owned CDP bridge was cleaned and re-established through the Windows portproxy/ADB-forward path. WSL-local CDP responded and identified `com.android.chrome`, Chrome `156.0.8078.79`, Protocol `1.3`. The initial preparation used one normal UAC-approved RunAs child; an interactive elevated session could not be retained, so no UAC bypass or repeated unrelated privileged operation was attempted.
- The exact-SHA candidate was served from Dev-PC on loopback `18765`, reached by the qualification-owned ADB reverse. Candidate manifest SHA, response-header SHA and page meta SHA all matched `947c91cf56a7b0e62f3a1b7c88e97642968f0a8d`. The Server Phone remained a consumer/backend target and was never checked out to the feature branch.
- The Rules-only qualifier is `scripts/dev/lite/qualify-ui-performance-android-rules.mjs`, with wrapper `scripts/dev/lite/run-ui-performance-android-rules.sh` and package entry `test:perf:android:rules`. The broad physical seven-screen matrix was **not run**.
- Physical viewport was `360 × 691` CSS pixels at device pixel ratio `3`. The physical device could not provide a real 320 CSS-pixel viewport; the 200% text/constrained no-overflow check was recorded as `VERIFIED_NO_OVERFLOW_EMULATED_200_PERCENT`.
- Physical interaction matrix: **28 total; 26 VERIFIED; 2 unavailable**. Verified items were initial render, Protection hero, landing scroll, Journey stages, Manage open, settings index, Protection Overview, Protected Actions, How Protection Works, Decision History, Decision Insight and return, Policy Settings, Rules Version, Governance, Technical Status and return, Compact/Medium/Expanded snaps, close, reopen, safe-area positioning, long-text wrapping, reduced motion, Daylight/Dark, System appearance and read-only request safety. Unavailable items were physical 320px viewport and native Android touch/haptic activation.
- Android CDP raw touch did not activate Manage; the qualifier continued with a read-only browser click. Haptics were instrumented and supported by the browser API, but native touch activation was not verified; no failure was converted into a pass.
- Network safety: **62 requests, all GET, 0 non-read requests**. Authority was `anonymous-read-only`; `synthetic_owner_used=false`, `destructive=false`, and `test_auth_bypass=false`.
- Decision Insight used the server-reported safe decision available to the anonymous read-only projection. No historical decision, approval, activation event, Enterprise capability or Owner session was fabricated.
- The synthetic Owner harness was not used. Anonymous read-only coverage was the narrowest safe path; Owner-only live surfaces remain explicitly unvalidated because no consumer-only-safe Owner projection was required for the executed matrix.

## Performance and attribution

The Rules-only qualifier reuses the repository frame/Long Task/LoAF schema and the existing `summarizeLiteFrames` target and hard-gate thresholds. It adds Rules evidence filtering without changing thresholds, minimum samples, renderer identity requirements or attribution labels.

- Physical evidence: **17 interaction samples**.
- Performance target: **TARGET MISS** for all 17 samples.
- Performance hard gate: **GATE MISS** for all 17 samples; the wrapper's non-zero exit is the honest hard-gate result.
- Observed p95 frame duration ranged from **16.9 ms to 75.2 ms**; Long Task counts were zero in the recorded samples. The full per-interaction evidence is in `.pocketlab-dev/performance/android-rules-947c91cf56a7b0e62f3a1b7c88e97642968f0a8d/`.
- Baseline attribution: **INCONCLUSIVE**. The same-device `main` comparison could not reach the current Rules surface because authoritative `main` does not expose `Protection Center` and the baseline attempt timed out waiting for it. No `APP_INCREMENTAL_COST` classification is claimed.
- Rules-owned performance regression: **none reproducibly demonstrated** after the source fixes. Remaining target/gate misses are reported without weakening the PR #588/#589 60-FPS, frame-duration, p95, smooth-frame, Long Task, LoAF, minimum-sample or hard-gate contracts.

The existing `WITHIN_BASELINE`, `PLATFORM_DOMINATED`, `APP_INCREMENTAL_COST`, `MIXED` and `INCONCLUSIVE` semantics remain unchanged. A future comparable baseline is required before assigning application ownership to the Android residual.

## Qualification commands executed

```text
npm run build
npm run test:rules:azure:unit
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-azure-horizon-rules.spec.ts tests/e2e/lite-rules-native-center-qualification.spec.ts --project=mocked-desktop --project=mocked-mobile
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-azure-horizon-rules-visual.spec.ts tests/e2e/lite-rules-premium-visual.spec.ts --project=mocked-desktop --project=mocked-mobile
bash -n scripts/dev/lite/run-ui-performance-android-rules.sh
node --check scripts/dev/lite/qualify-ui-performance-android-rules.mjs
npm run test:perf:android:rules
```

The physical command was exact-SHA and Rules-only: build, candidate manifest, ADB reverse, CDP identity, foreground readiness, read-only interaction matrix, performance evidence and owned cleanup. The broad physical seven-screen matrix was **not run**.

## CSS ownership and remaining limitations

Azure Horizon tokens remain the source for canvas, surfaces, borders, muted text, selected states, accent, focus, success, warning, danger and shadows. Rules geometry is scoped and theme-independent, with the shared container-query and sheet/desktop geometry infrastructure preserved.

Remaining limitations are the physical 320px viewport, native touch/haptic activation, the unavailable live synthetic Owner projection, and the inconclusive same-device main baseline. These are explicitly labelled and do not invalidate the read-only functional or visual evidence. No performance target or gate pass is claimed.

## Documentation, repository gates and cleanup

- Canonical documentation is regenerated only after source, mocked, physical and visual qualification; final task results are recorded in the final PR provenance.
- `task lite:docs:generate`, `task lite:docs:check` and `task lite:check` are run in that order before final commit/push. Their exact results are recorded in the final PR description and handoff.
- Server Phone source was not edited, installed, restarted, deployed or switched to the feature branch. Its checkout remained clean on `main` at backend SHA `463ad47de66345955e448e47df346c9525ffd67f`.
- No Rules activation, policy mutation, approval, access grant, device removal or destructive operation was performed.
- No synthetic Owner credentials, browser bridge secrets or production cookies were used.
- Candidate server, candidate ADB reverse, candidate tab, candidate-only port and qualification-owned candidate state were cleaned after physical qualification. The final CDP bridge cleanup and WSL relay cleanup are recorded separately from the candidate cleanup; unrelated ADB mappings remain untouched.
- No branch was merged, no release or tag was created, and no deployment occurred. PR #642 remains open and draft pending a separate merge decision.

**Overall status: VERIFIED Dev-PC/mocked Rules qualification; VERIFIED physical Rules-only functional and visual qualification; PERFORMANCE TARGET MISS / GATE MISS with INCONCLUSIVE attribution; documentation and repository gate results recorded at finalization.**
