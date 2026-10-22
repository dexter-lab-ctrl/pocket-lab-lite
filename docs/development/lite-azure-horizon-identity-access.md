# Azure Horizon — Identity & Access (stabilization and qualification record)

> [!IMPORTANT]
> **SOURCE STABILIZED / NOT MERGE READY.** The Dev-PC implementation, approved visual references, mocked browser matrix, Storybook, accessibility, geometry and Identity performance gates remain verified. The final targeted pass also proved the exact candidate on physical Android and recovered the live mobile matrix to 4/4, but the full physical Android qualifier still fails broad renderer budgets and cannot exercise the Owner-gated Identity Manage surface on the production-main runtime. PR #624 must remain OPEN, DRAFT and NOT MERGED.

## 1. Objective and current baseline

The source-of-truth baseline is remote `main` at `424d8337f5b16a9a1a3d8b36117cc1543dbbf9c4` (squash integration of [PR #623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623)). It already includes the Identity profile projection, Owner setup, WebAuthn/passkey flows, sign-in, recovery, sessions, protected confirmations, Owner operations, trusted clients, Enterprise People and Roles, and active/saved-state semantics. This PR is a presentation and regression-coverage change, not a new identity service.

The prior stabilized candidate was `5b59ca14398cef8f4b5baf12b441f90891356c44`. This targeted final pass added commit `41c1485fca3fd728ef4f0dd3c587e161601718aa`, which corrects Black Recovery Manage portal inheritance and adds a regression contract. The feature branch is synchronized with its remote at `41c1485fca3fd728ef4f0dd3c587e161601718aa`; this is the exact candidate SHA used for the rerun physical Android build.

The goal is a premium, account-first Identity screen without changing FastAPI authority or inventing account facts.

## 2. Architecture and shared components

```text
React/Vite Identity → Caddy same-origin → authenticated FastAPI /api/lite/*
→ NATS/JetStream when operational commands apply → worker/agent/supervisor
→ sanitized server evidence → FastAPI → UI
```

Reuse [PR #606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606) `PageHeader`, `GlassCard`, `LiteButton`, `StateSurface`, `LiteField`, `LiteProtectedConfirmation`, `LiteSheet`, `LiteDetailsPanel`, focus/escape handling and loading/error boundaries. No new identity theme provider or browser-owned authorization model.

## 3. Theme ownership and dark-surface completeness

Reuse [PR #622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622) `src/lite/theme/azureHorizonTokens.css` and `azureHorizon.css`: the root `data-lite-theme` resolves Black, Daylight, and System preferences. `identityPremium.css` now uses attribute-root selectors instead of Daylight-only skin rules and consumes `--azure-*` semantic surface, border, text, muted, input, status, focus, and backdrop tokens. During physical Android review, the shared catalog Manage primitive was found to leak a hard-coded Daylight background into Recovery Black; `azureHorizon.css` now scopes a complete Black Recovery Manage skin and responsive section layout, with a focused computed-style regression. The body-mounted `LiteOverlayRoot` remains under the same root attribute, including Manage, Details, nested confirmation, settings forms and one-time code containers. `color-scheme` follows the root and browser-native controls.

## 4. Personal desktop arrangement

Account identity and sign-in state appear first, with role and mode from `identityPremiumProjection`; three backend-derived counts/status summaries follow. A two-column Sign-in Methods / Active Sessions action grid provides focused Manage entry points. Pending Owner review appears when reported. Sanitized recent activity and the conceptual four-stage Access Journey follow the key controls. The operational next-action story remains available beneath the primary account sections.

## 5. Personal mobile arrangement

A compact account card, two passkey/session summaries, full-width Manage Access action, one-column Sign-in Methods / Sessions / Recovery cards, then activity and Journey. At 320px and enlarged text the summary grid stacks. Existing Pocket Lab shell and responsive nav remain unchanged. No second mobile navigation system is introduced.

## 6. Enterprise overview, people and roles

Enterprise People and Roles remain within the backend-enabled Manage navigation and the existing `LiteIdentityEnterprise` adapter. Access roles remain `Owner`, `Admin`, `Operator`, `Auditor`, `Viewer`; effective capabilities, role catalog, people topology, permissions and reasons come from the existing server projection. Owner is not styled as green health. Existing Owner/Admin action and step-up conditions remain in source; no frontend privilege escalation is added.

## 7. Sign-in, setup and enrollment

Unauthenticated screens still use Owner claim verification, first Owner passkey setup, person enrollment, passkey login, optional password fallback, conditional username, safe server errors and advanced setup disclosure. The account dashboard only renders if `data.authenticated === true`. These are **not** new or emulated ceremonies; `liteApi`, `liteEnterpriseApi`, and `liteWebAuthn` own existing challenge and verification flows.

## 8. Passkeys and WebAuthn

Manage lists safe friendly names, active/revoked state, and server-reported dates, with Details retaining Rename/Remove behavior. Add uses existing WebAuthn ceremony; revocation can require recent Owner passkey confirmation. No credential IDs are promoted to the card title and no browser storage is added.

## 9. Sessions

Current and other sessions are distinguishable when marked by the backend. Other session revocation and Sign Out Others retain existing confirmation and server writes. Refresh/saved authority remains read-only. No sign-out is presented as reversible.

## 10. Recovery

Readiness is separate from new recovery-code results. The only-once `recoveryCodes` live in component state; switching away from Recovery, closing Manage or signing out clears them. They are not added to Dexie, localStorage, story fixtures, safe snapshots, analytics, or screenshots. New screenshot tests stop at the consequence confirmation before any codes are generated.

## 11. Settings and workspace mode

Settings retain Change Password, Sign Out, and backend-previewed workspace mode switching. Owner step-up, session invalidation and Enterprise opt-in remain server-led. Mode switching is consequential, not a visual preference control.

## 12. Access Journey and Activity

`IdentityAccessJourney` remains a four-stage explanatory sequence (Identity → Authentication → Authorization → Recovery), never a live sign-in indicator. `IdentityActivityTimeline` uses the sanitized `identityActivityView` projection and progressive Details; do not render raw audit payloads.

## 13. Manage sections and identity details

Overview, Passkeys, Sessions, Recovery, Activity, Settings and capability-dependent Approvals / Trusted Clients, plus server-enabled Enterprise People and Roles. `IdentityDetailsContent` continues progressive safe facts, known reason codes and authorized action callbacks.

## 14. Desktop movable/resizable Manage

Reuse [PR #623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623) `src/lite/components/useDesktopManageGeometry.js`, also consumed by Apps and Devices, with the **same 701px desktop breakpoint**. The `LiteSheet` optional header-actions slot holds named Move, Resize and Reset controls; the shared hook provides pointer-driven requestAnimationFrame updates, viewport clamps, keyboard arrows/Shift steps/Home reset and screen-reader status. Geometry is transient, never persisted. No interactive input, passkey widget, section tab, or confirmation is a drag region. Under 701px the regular accessible bottom sheet receives no desktop handles or style geometry.

## 15. Protected confirmation and Owner operations

Existing nested `LiteSheet` confirmations keep backdrop, focus, Escape and authorization handling; new drag controls apply only to the parent Manage sheet. OwnerOperationApprovals and TrustedAutomationClients preserve fresh/eligible gates, server verification, sanitized operation disclosures, client capability, approval/rejection, and revocation. No frontend auto-approval.

## 16. Responsive alignment, typography and accessibility

Shared Azure type and semantically colored surfaces replace hard-coded Daylight presentation. Buttons target at least 44px where existing component contracts provide it; inputs inherit the correct scheme and focus tokens. Long names, error reasons, roles and technical facts wrap. Safe-area and visual viewport support remain in `LiteSheet`. Keyboard and focus trapping, nested dialogs, reduced motion and accessible geometry require browser qualification, not assumptions.

## 17. Performance and low-power

No new dependency, background animation, polling path or server endpoint. The shared geometry hook schedules updates via `requestAnimationFrame` and clamps viewport changes. Hidden Manage content remains section-gated. [PR #588](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/588) owns all existing performance ceilings; new samples do **not** relax its gates.

## 18. Regression inventory

- `src/lite/identity/identityHorizon.test.jsx`: safe projection, count unknowns, conceptual journey, activity sanitization, Manage stale-state and sections.
- `tests/e2e/lite-azure-horizon-identity.spec.ts`: mocked personal/Enterprise, responsive widths, accessibility, nested confirmations, desktop geometry, mobile separation, roles and saved approval.
- `tests/e2e/lite-azure-horizon-identity-visual.spec.ts`: Black/Daylight screenshot definitions with widths, first-run, signed-out, enrollment, governance and private-code-safe confirmations.
- `tests/e2e/lite-azure-horizon-identity-performance.spec.ts`: first paint, Manage and section interaction sampling; existing performance gates remain separate.
- `src/lite/LiteIdentity.stories.jsx`: deterministic Azure Black, Daylight, System, mobile, enlarged text, protected/Enterprise variants.

**VERIFIED — HUMAN BASELINE APPROVAL.** The requested “snapshot does not exist” gap was resolved by updating every affected snapshot reference after visual review. This includes 100 new Azure Identity references and 70 refreshed existing Lite visual references across the Identity, visual-state and overlay suites. Black and Daylight were reviewed separately, including desktop/mobile, Manage, moved/resized, protected confirmation and 200% text cases. No recovery code or secret appears in the approved artifacts. The loaded-state marker was added after the first candidate exposed an incorrect lazy skeleton capture; the affected mobile reference was regenerated after the fix.

## 19. Task/npm entry points and executed results

```bash
npm run test:identity:azure:unit
npm run test:identity:azure:mocked
npm run test:identity:azure:geometry
npm run test:identity:azure:a11y
npm run test:identity:azure:visual
npm run test:identity:azure:perf
npm run test:identity:azure:qualification
task lite:ui:identity:azure:qualification
npm run test:mock-regression
npm run test:a11y:states
npm run test:perf
npm run build
task lite:check
```

The previously completed focused results at `6e5b10c3e031025de9c98603295fc783558424f1` remain applicable because the final source fix is scoped to the Recovery Black portal; the new targeted and exact-candidate results are:

| Gate | Result |
| --- | --- |
| `npm run test:identity:premium:unit` | PASS — 27/27 |
| `npm run test:identity:azure:unit` | PASS — 32/32 |
| `npm run test:identity:premium:mocked` | PASS — 46/46 |
| `npm run test:identity:azure:mocked` | PASS — 116/116 |
| `npm run test:identity:azure:mocked` at `41c1485fca3fd728ef4f0dd3c587e161601718aa` | PASS — 116/116 |
| Black Recovery Manage computed-style regression at `41c1485fca3fd728ef4f0dd3c587e161601718aa` | PASS — 1/1 mocked-mobile |
| Recovery Manage visual overlays at `41c1485fca3fd728ef4f0dd3c587e161601718aa` | PASS — 2/2 daylight desktop/mobile baselines |
| `npm run test:identity:azure:geometry` | PASS — 20/20 |
| `npm run test:apps:azure:geometry` | PASS — 40/40 |
| `npm run test:identity:azure:a11y` | PASS — 8/8 |
| `npm run test:identity:azure:perf` | PASS — 12/12 |
| `npm run test:identity:azure:visual` | PASS — 96/96 |
| `npm run test:azure:storybook` | PASS |
| `npm run build-storybook` | PASS — Storybook 8.6.18, 2,332 modules |
| `npm run test:a11y:states` | PASS — 36/36 |
| `npm run test:mock-regression` | PASS — all constituent suites passed; intentional skips retained |
| `POCKETLAB_BUILD_ID=<candidate> POCKETLAB_UI_PERF_CANDIDATE=1 npm run build` | PASS — Vite 6.4.3, exact SHA marker present |

The broad `npm run test:perf` gate remains FAIL for three pre-existing or variable, non-Identity Apps/Devices measurements. Controlled main-vs-feature targeted runs used the same Node 24.16.0, browser and single-worker process: Devices desktop React commit p95 was 25.6/24.6 ms on main and 26.2/26.2/26.2 ms on the feature; Devices mobile was 24.7 ms then a pass on main and 24.2/26.3/25.6 ms on the feature; Home-to-Devices passed the main targeted runs and measured 15.1/15.9 ms on the feature, with one unrelated cross-tab long-animation outlier. These are classified PRE-EXISTING/VARIABLE, not a stable PR regression. Thresholds were not changed, and no unrelated Apps/Devices source was altered. Repository-wide `npm run lint` is not runnable because no ESLint configuration exists; `npm run format:check` reports existing repository-wide formatting/parser failures, including `docs/generated/schemaspy/anomalies.html`. These are recorded as repository-gate limitations, not hidden.

The documentation platform's generated contracts, screenshots and navigation indexes are regenerated only after source/runtime qualification, as required by the execution runbook.

## 20. Limitations, risk and qualification

**VERIFIED on Dev-PC:** source build, mocked browser behavior, approved Black/Daylight references, accessibility assertions, geometry, Storybook and Identity performance. The matrix covers 320/360/375/390/430/768/1024/1280/1440 layouts where defined, 200% text, protected confirmations, Enterprise state projections and portal-mounted sheets.

**FINAL TARGETED PASS — NOT MERGE READY:** the standard repository PowerShell CDP preparation was launched through UAC and exited 0. `npm run check:perf:android-cdp` then passed: Android Chrome `Chrome/156.0.8078.47`, CDP 1.3, Playwright attach, contexts/pages and device smoke were verified. The exact candidate build at `41c1485fca3fd728ef4f0dd3c587e161601718aa` rendered on the physical Android device; candidate manifest, response header and DOM provenance matched that SHA. The full physical qualifier still exited 1: broad screen/navigation/Manage samples exceeded the existing renderer gate, the production-main runtime did not expose Owner-gated Identity Manage, and the read-only Home refresh-progress analogue timed out at the existing qualifier probe. The rerun Recovery Manage screenshot is now correctly Black-themed and readable after the targeted CSS fix. No screenshot contained recovery codes or other secrets.

Live read-only candidate UI reached the Server Phone through the repository-owned loopback tunnel. The two formerly failing mobile cases were rerun individually and then in the complete live-mobile project: **4/4 PASS** on the exact pre-fix candidate `5b59ca14398cef8f4b5baf12b441f90891356c44`. The earlier repeated candidate-proxy 502 responses/timeouts did not reproduce under bounded stable reruns and are classified as transient tunnel/runtime instability, not allowlisted application success. The expected unauthenticated `/api/lite/enterprise/access` boundary remains 401; no unexpected 502 was accepted. This is read-only runtime evidence, not authenticated production qualification.

Privileged authentication and protected-operation execution were not run against the production phone. The isolated Dev-PC harness/backend tests passed 87 tests and the Identity/Enterprise backend contract tests passed 34 tests. The phone harness remained disabled with zero active sessions and zero principals; the Dev-PC harness could not start because no local qualification API was running. No production Owner credential, auth bypass, browser-held secret or synthetic principal was used.

The follow-up stabilization sequence has now run source build/unit first, mocked state/auth/geometry, Axe/contrast, human-approved visual references, the existing PR #588 performance gates, docs and full repository gates. Live/physical qualification remains bounded by the documented authorization and environment limits. Exact-head CI for the final documentation commit is recorded in section 29 after the documentation update; the earlier green run at `5b59ca14398cef8f4b5baf12b441f90891356c44` is historical evidence only.

## 21. Rollback and future cross-tab consistency

Revert the feature-branch source commits before merging; no backend schema or auth state migration exists. Keep PR DRAFT until qualification. For future work, consider shared Identity-safe visual tokens and panel sizing across Apps, Devices, Rules, Recovery, and Security **without changing** those tabs as part of this PR.

## 22. Owner approval and trusted-client presentation details

Pending, executing, completed, rejected, blocked and expired status texts remain server-derived. Fresh pending records expose Approve/Reject only under existing handlers; saved data disables decisions. Trusted-client pairings present requester, public fingerprint and bounded capability; no private material.

## 23. People lifecycle actions and Owner/Admin boundaries

Separate person invitations, enrollment, suspension, reactivation, sign-in reset, role assignment and removal remain delegated to `LiteIdentityEnterprise`. Frontend controls are a convenience filter only; server permissions and step-up are the enforcement boundary. Enterprise is disabled by default.

## 24. Native controls and dropdowns

Form styling uses existing `LiteField` and `pocket-input` with root-owned Azure colors, visible focus, non-text control borders and native `color-scheme` inheritance for select/inputs/textarea, including portal forms. Browser-dependent native dropdown contrast is unvalidated until platform qualification.

## 25. Screen-reader and keyboard behavior

Manage section buttons report pressed/current state. Move/Resize controls provide accessible names and arrow/Shift+arrow commands; Reset restores bounds. Focus remains managed by `LiteSheet` and its nested surface stack. Behavior with live platform passkeys remains deferred to the permitted qualification session.

## 26. Browser support

Desktop media breakpoint is inherited from shared Apps/Devices geometry (701px). Mobile is the accessible LiteSheet bottom sheet; installed PWA and Android viewport/safe-area behavior will require real-device review.

## 27. First-paint and render metrics

The new performance spec records first paint, Manage open, section switching and keyboard movement for synthetic scenarios only. Identity performance passed 12/12 and no thresholds or results were changed; PR #588 remains authoritative. The broad legacy performance gate retains the three non-Identity hard failures listed in section 19.

## 28. Baseline management

All new `toHaveScreenshot` scenarios now have reviewed PNG references. Human approval was explicitly supplied for this execution. Black/Daylight, mobile/desktop, signed-out, protected dialog, moved/resized and 200% cases were reviewed; the lazy-loading marker fix was applied before the final 96/96 Identity visual run. No browser-generated secret is included in a fixture.

## 29. CI and generated documentation

The last completed matching CI run before the targeted Recovery Black fix was [#981](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/39687848857), passing `isolated-devpc-qualification`, `quick-and-docs` and `ui-performance-qualification` at `5b59ca14398cef8f4b5baf12b441f90891356c44`. That run is historical evidence only: the Recovery Black fix at `41c1485fca3fd728ef4f0dd3c587e161601718aa` was validated locally and the final documentation commit is pending its own exact-head CI. The final exact-head result will be recorded in the PR report; no green CI is claimed here for a post-#981 SHA. Generated docs, navigation metadata and contracts were regenerated after source/runtime qualification, with source truth preserved. Historical pre-stabilization run `39644380456` is not evidence for the final candidate: its isolated-devpc job passed, while its UI-performance and quick-and-docs jobs failed.

## 30. Safety gaps and deferred evidence

**VERIFIED in mocked/isolated coverage:** missing projections remain unavailable rather than zero, recovery codes are ephemeral, portal sheets inherit the selected Azure root, nested confirmations retain focus ownership, and browser-side approval is not introduced. **NOT RUN against production:** Owner setup, WebAuthn registration, passkey rename/revocation, password change, recovery-code generation and Enterprise role mutations, because the Server Phone is production and the no-mutation rule prohibits those writes. Their isolated contract and harness tests passed as recorded above.

## 31. Final disposition

**NOT MERGE READY.** The Black Recovery portal defect found during physical review is fixed and verified on the exact candidate. Live mobile is 4/4 and the three broad Apps/Devices performance concerns are PRE-EXISTING/VARIABLE rather than a stable PR regression. The remaining blocker is the failed full physical Android qualification: the renderer gate is not green across the requested matrix, and production-main does not expose the Owner-gated Identity Manage surface needed for protected Identity coverage. No merge, tag, `dist.zip`, deployment, or Server Phone change is authorized. PR #624 remains OPEN, DRAFT and NOT MERGED.

## 32. Security and runtime preservation record

- Server Phone source, checkout, PM2 configuration, Caddy, NATS, Tailscale and persistent identity records were not modified.
- The phone remained on its recorded main-based runtime; only read-only SSH inspection, health/readiness checks, the repository-owned runtime resilience check and the fixed loopback candidate tunnel were used.
- The candidate server served the exact feature SHA, proxied only read-oriented `/api/lite/*` paths, rejected writes and never proxied the harness namespace.
- FastAPI remained authoritative. No frontend permission grant, production authentication bypass, private key, recovery code, session cookie or challenge secret was printed or stored in evidence.
