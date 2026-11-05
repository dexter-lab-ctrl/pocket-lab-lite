# Azure Horizon Rules Center — P0–P7 qualification handoff

> **VERIFIED — DEV-PC AND MOCKED QUALIFICATION COMPLETE; PHYSICAL ANDROID BLOCKED.** The Rules implementation was built and exercised on Dev-PC, the authored mocked desktop/mobile matrix passed, and deterministic visual baselines were regenerated and reviewed. Physical Android transport and exact-SHA candidate identity were established, but Android Chrome could not produce foreground frames because the dedicated device's secure keyguard remained in `Bouncer` after the permitted `wm dismiss-keyguard` command. No credential or lock-security bypass was attempted.

## Source baseline and ownership

- Repo: `dexter-lab-ctrl/pocket-lab-lite`.
- Baseline `main`: `463ad47de66345955e448e47df346c9525ffd67f`.
- Starting PR #642 / exact source candidate during this qualification: `fee04eac0ac976f64453a5c0ae9c09828b5af4b6`.
- Source-qualified Dev-PC/mocked commit: `daaa15cb` (full SHA is recorded in the final PR provenance).
- Feature branch: `feat/azure-horizon-rules-center-revamp`.
- PR #641 was confirmed merged into the baseline.
- Server Phone backend SHA: `463ad47de66345955e448e47df346c9525ffd67f`; its checkout remained clean on `main` throughout.
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
| P0 | CSS ownership, semantic tokens, theme-independent layout, overflow and geometry assertions | **VERIFIED — mocked** |
| P1 | One server-authoritative Protection Center hero and one Manage action | **VERIFIED — source and mocked** |
| P2 | Four selectable educational Journey stages and server-backed Latest Decision/empty state | **VERIFIED — source and mocked** |
| P3 | Desktop split workspace; mobile grouped index and focused detail navigation | **VERIFIED — mocked desktop/mobile** |
| P4 | Shared mobile snapping, safe-area checks, 200% text and reduced-motion coverage | **VERIFIED — mocked; physical pending** |
| P5 | Decision explanation and backend-only activation-state truth | **VERIFIED — source and mocked** |
| P6 | Azure semantic tokens, Lucide icons, optional haptics, reduced motion and theme parity | **VERIFIED — mocked** |
| P7 | Unit, Storybook fixture, mocked Playwright, accessibility and visual contracts | **VERIFIED — executed; physical visual proof blocked** |

## Dev-PC validation

- `npm run build`: **PASS**.
- Rules Vitest set: **23/23 PASS** across `rulesPremiumView.test.js`, `RulesProtectionJourney.test.jsx`, `rulesAzureHorizon.test.jsx`, and `catalog/useDesktopManageGeometry.test.jsx`.
- Mocked functional Rules/native-center matrix: **98/98 PASS** across `mocked-desktop` and `mocked-mobile`.
- Additional 1920px responsive checks: **2/2 PASS**.
- Mocked visual suites: **124/124 PASS** across `mocked-desktop` and `mocked-mobile`, without snapshot updates.
- Accessibility: serious/critical Axe assertions passed in the Rules regression/native-center suites; no serious or critical violations were reported by those checks.
- Responsive coverage exercised 320, 360, 375, 390, 430, 700, 701, 768, 1024, 1280, 1440 and 1920 CSS-pixel cases, plus 200% text and reduced motion.
- Appearance coverage exercised Daylight, Dark and System resolution in mocked fixtures. Geometry parity assertions passed for the Rules hero, Journey, Manage surface, navigation, detail pane and rows.
- Role fixtures exercised Personal Mode and Enterprise Owner/Admin/Operator/Auditor/Viewer capability presentation. No browser-side privileged write was accepted by the mocked tests.
- Final repository-wide mocked gate: **PASS** — 554 Vitest tests, 416 backend tests, 52/52 mocked contract cases, 2/2 accessibility cases, 74/74 documentation browser cases, Storybook 581 canonical stories plus 17 representative renders, and generated-evidence redaction.

## Appearance and Rules state matrix

The existing source-backed fixture catalog and view-model tests cover healthy, degraded, unavailable, revision verified/unverified, update required, pending/running/failed/rolling-back/rolled-back/uncertain activation projections, allowed/blocked decisions, passkey and independent-approval presentation, no decisions, saved/offline state, backend-unreachable state, Personal Mode and Enterprise roles. Mocked assertions preserve these distinctions and do not fabricate live backend evidence.

**Mandatory security assertions verified in the mocked lane:** healthy state is not inferred from uncertain/saved data; authorization is not execution; accepted update is not successful activation; earlier activation steps remain unconfirmed without server evidence; archived/saved state cannot authorize writes; Enterprise role checks, step-up, independent approvals, execution and audit evidence remain backend-owned; no browser-held secrets or direct shell/NATS access exist.

## Visual snapshots

- `tests/e2e/lite-azure-horizon-rules-visual.spec.ts` and `tests/e2e/lite-rules-premium-visual.spec.ts` pass **124/124** without updates.
- The native-center suite added eight deterministic Rules snapshots for light/dark desktop and mobile Manage states; the new set and representative landing, dark-theme, Policy Settings, activation and 320px images were inspected.
- Updated baselines cover Rules landing, Protection Center, Journey/decision states, Manage sections, Decision Insight, activation, 320px/narrow layouts, Daylight, Dark and System fixtures.
- **VISUAL SNAPSHOTS — APPROVED for mocked deterministic fixtures.** This approval does not imply physical Android screenshot approval; that gate is blocked by the secure keyguard.

## Android CDP and physical qualification

- Windows ADB resolver selected one authorized physical Android target; the serial is intentionally omitted here.
- Repository-owned CDP bridge was cleaned and re-established through the Windows portproxy/ADB-forward path. WSL-local CDP responded on the configured bridge and identified `com.android.chrome`, Chrome `156.0.8078.79`, Protocol `1.3`.
- Dev-PC candidate server exposed a sanitized candidate manifest for tested source `fee04eac0ac976f64453a5c0ae9c09828b5af4b6` on loopback port `18765`; the owned ADB reverse was established and removed after each bounded attempt. The later source-qualified commit is `daaa15cb`; no physical result was claimed for it because the keyguard blocked the earlier candidate before interaction.
- Candidate response-header and page-meta SHA checks were implemented and reached before the foreground frame gate; the phone remained a consumer of the Dev-PC candidate and was never checked out to the feature branch.
- The Rules-only qualifier is `scripts/dev/lite/qualify-ui-performance-android-rules.mjs`, with wrapper `scripts/dev/lite/run-ui-performance-android-rules.sh` and package entry `test:perf:android:rules`. It does not invoke the broad seven-screen matrix.
- The physical interaction matrix was **not executed** because the device remained behind a secure `Bouncer`/keyguard after the permitted `wm dismiss-keyguard` request. Physical interaction count: **0**. This is **BLOCKED**, not PASS, and no Owner session was fabricated.
- The synthetic Owner harness was not used. Anonymous read-only coverage was the narrowest safe path; Owner-only live surfaces remain unvalidated because the phone is consumer-only and the candidate proxy does not expose the harness route.
- The candidate wrapper now fails closed with an explicit keyguard blocker rather than converting a throttled/zero-RAF renderer into a performance result.

## Performance and attribution

The Rules-only qualifier reuses the repository frame/Long Task/LoAF schema and the existing `summarizeLiteFrames` target and hard-gate thresholds. It adds Rules evidence filtering to the existing baseline analyzer without changing thresholds, minimum samples, renderer identity requirements or attribution labels.

No physical Rules samples were accepted because the foreground renderer gate was blocked. Therefore:

- Performance target: **UNVALIDATED — no physical samples**.
- Performance hard gate: **UNVALIDATED — no physical samples**.
- Baseline attribution: **INCONCLUSIVE / UNVALIDATED**, not `APP_INCREMENTAL_COST`, because a same-device main-versus-candidate sample could not be collected.
- Rules-owned performance regression: **none reproducibly demonstrated in Dev-PC or mocked coverage**; physical attribution remains a limitation.

The existing `WITHIN_BASELINE`, `PLATFORM_DOMINATED`, `APP_INCREMENTAL_COST`, `MIXED` and `INCONCLUSIVE` semantics remain unchanged. The PR does not weaken the PR #588/#589 60-FPS, frame-duration, p95, smooth-frame, Long Task, LoAF, minimum-sample or hard-gate contracts.

## Qualification commands executed

```text
npm run build
npx vitest run <four focused Rules/geometry files>
npx playwright test <Rules regression + native-center> --project=mocked-desktop --project=mocked-mobile
npx playwright test <Rules regression> --project=mocked-desktop --project=mocked-mobile --grep=1920
npx playwright test <Rules visual + premium visual> --project=mocked-desktop --project=mocked-mobile
bash -n scripts/dev/lite/run-ui-performance-android-rules.sh
node --check scripts/dev/lite/qualify-ui-performance-android-rules.mjs
```

The physical Rules wrapper was executed with exact-SHA build, candidate server, ADB reverse, CDP identity, wake and keyguard checks; it stopped at the secure-keyguard/foreground-renderer blocker. The broad physical seven-screen matrix was **not run**.

## CSS ownership and remaining risks

Azure Horizon tokens remain the source for canvas, surfaces, borders, muted text, selected states, accent, focus, success, warning, danger and shadows. Rules geometry is scoped and theme-independent, with the shared container-query and sheet/desktop geometry infrastructure preserved.

Remaining risks are the blocked physical Android foreground interaction/performance/screenshot gates, unavailable live synthetic Owner projection, Android-specific haptic behavior, and any device-only rendering differences that cannot be inferred from mocked browser output. No performance claim is made for those unavailable gates.

## Release boundaries and cleanup

- Server Phone source was not edited, installed, restarted, deployed or switched to the feature branch. Its checkout remained clean on `main` at `463ad47de66345955e448e47df346c9525ffd67f`.
- No Rules activation, policy mutation, approval, access grant, device removal or destructive operation was performed.
- No synthetic Owner credentials, browser bridge secrets or production cookies were used.
- Qualification-owned candidate server, ADB reverse, candidate wake-lock and WSL CDP relay were cleaned after the bounded physical attempts; unrelated ADB mappings were untouched.
- The initial elevated PowerShell preparation used one normal UAC-approved RunAs child invocation. An interactive elevated session could not be retained, so no unrelated privileged work was performed.
- No branch was merged, no release or tag was created, and no deployment occurred. PR #642 remains open and draft pending the remaining physical gate and separate merge decision.

**Overall status: VERIFIED Dev-PC/mocked Rules qualification; VERIFIED canonical documentation and repository gates; BLOCKED physical Android qualification.**
