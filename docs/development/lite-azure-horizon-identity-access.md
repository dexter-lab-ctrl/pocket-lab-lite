# Azure Horizon — Identity & Access (implementation-only handoff)

> [!IMPORTANT]
> **IMPLEMENTED IN SOURCE / UNVALIDATED.** This feature branch was intentionally authored without executing any build, unit test, browser test, lint, accessibility scan, screenshot baseline, benchmark, docs check, or runtime qualification. No approval to merge, release, or deploy is implied.

## 1. Objective and current baseline

The source-of-truth baseline is remote `main` at `424d8337f5b16a9a1a3d8b36117cc1543dbbf9c4` (squash integration of [PR #623](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/623)). It already includes the Identity profile projection, Owner setup, WebAuthn/passkey flows, sign-in, recovery, sessions, protected confirmations, Owner operations, trusted clients, Enterprise People and Roles, and active/saved-state semantics. This PR is a presentation and regression-coverage change, not a new identity service.

The goal is a premium, account-first Identity screen without changing FastAPI authority or inventing account facts.

## 2. Architecture and shared components

```text
React/Vite Identity → Caddy same-origin → authenticated FastAPI /api/lite/*
→ NATS/JetStream when operational commands apply → worker/agent/supervisor
→ sanitized server evidence → FastAPI → UI
```

Reuse [PR #606](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/606) `PageHeader`, `GlassCard`, `LiteButton`, `StateSurface`, `LiteField`, `LiteProtectedConfirmation`, `LiteSheet`, `LiteDetailsPanel`, focus/escape handling and loading/error boundaries. No new identity theme provider or browser-owned authorization model.

## 3. Theme ownership and dark-surface completeness

Reuse [PR #622](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/622) `src/lite/theme/azureHorizonTokens.css` and `azureHorizon.css`: the root `data-lite-theme` resolves Black, Daylight, and System preferences. `identityPremium.css` now uses attribute-root selectors instead of Daylight-only skin rules and consumes `--azure-*` semantic surface, border, text, muted, input, status, focus, and backdrop tokens. The body-mounted `LiteOverlayRoot` remains under the same root attribute, including Manage, Details, nested confirmation, settings forms and one-time code containers. `color-scheme` follows the root and browser-native controls. Visual and measured contrast completeness require deferred qualification.

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

**DEFINED — BASELINE CAPTURE AND APPROVAL DEFERRED.** New screenshots are not approved golden artifacts.

## 19. Task/npm entry points — NOT RUN / DEFERRED

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

The documentation platform's generated contracts, screenshots and navigation indexes may require regeneration by the later stabilization agent. Do not promote generated baselines without human review.

## 20. Limitations, risk and qualification

**[UNVALIDATED]** Source-authored UI may have visual/semantic regressions until build/Playwright/Axe and physical Android evidence. **[UNVALIDATED]** WCAG AA, 200% scaling, nested focus and pointer capture, and 60fps behavior are targets, not certified outcomes. **[DEFERRED]** exact-head CI triage, Azure contrast sampling, browser/platform WebAuthn, live Owner/Admin role authorization, Android/Termux PWA and mock screenshot approval.

The follow-up stabilization sequence should run source build/unit first, then mocked state/auth/geometry, Axe/contrast, visual reference approval, existing PR #588 performance gates, docs and full repository gates; live/physical qualification requires explicit authorization. CI failures were not investigated in this session.

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

The new performance spec records first paint, Manage open, section switching and keyboard movement for synthetic scenarios only. No thresholds or results are changed; PR #588 remains authoritative.

## 28. Baseline management

All new `toHaveScreenshot` scenarios intentionally have no approved PNG files. Human approval of Black/Daylight, mobile/desktop, signed-out, protected dialog and moved/resized cases is a later gate. No browser-generated secret is included in a fixture.

## 29. CI and generated documentation

CI can trigger automatically after push but must not be inspected or rerun in this implementation-only session. Generated docs, navigation metadata and contracts must be assessed and refreshed as needed after source stabilization, with source truth preserved.

## 30. Safety gaps and deferred evidence

**[UNVALIDATED]** Check owner/passkey challenge cancellation, backend 428 step-up, empty/missing session projections, revoked sessions, stale approvals, mode preview sign-out, focus return and portal theme inheritance in real browsers. Contrast, a11y, performance and Android behavior remain unproven.

## 31. Final disposition

This is an OPEN DRAFT source implementation, not a qualified production release. No merge, tag, `dist.zip`, or Server Phone change is authorized.
