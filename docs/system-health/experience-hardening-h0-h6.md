# System Health — Azure Horizon H0–H6 experience hardening

**State:** SOURCE IMPLEMENTATION AND BOUNDED QUALIFICATION RECORDED; PERFORMANCE HAS A RETAINED MIXED RESIDUAL. **Base:** `main` at `a9f8b2d7625fd84f82dffee5f44bcee20225661e`. **Feature:** `feat/azure-horizon-system-health-experience-hardening`. The qualified UI/runtime candidate source SHA was `b65d83c2f83229e3abd59e01b33aaecaa5797734`; production was not changed.

## H0 — Source findings and scope

See [source audit](source-audit-h0.md). The source confirms stale unresolved incidents counted under current attention, raw machine fields in first-level UI, an unsupported Diagnose & Fix affordance, and brittle input shape assumptions. The reported short device names are **unvalidated historical provenance**; they are not deleted or silently renamed.

## H1 — Authoritative data and evidence semantics

`services/lite_system_health.py` ingests worker-owned, committed projections only. It now accepts `items`/`devices` only as lists of dictionaries, requires explicit safe string target identity and uses the known component allowlist. Numeric IDs, paths, malformed collection objects and unsafe consumer names do not become incidents. **Legitimate short strings remain valid.**

The incident lifecycle, identity hash, generation, recurrence, timestamps, source revision, audit events, diagnosis history and existing fail-closed repair preflight are retained.

The original `active_problems` and `critical_problems` API fields **continue to represent unresolved incidents**. New additive summary fields are:

- `current_problems`: unresolved incidents with matching **fresh unhealthy** observation.
- `saved_problems`: unresolved incidents without matching fresh unhealthy evidence.
- `current_critical_problems`: current critical incidents.
- `unresolved_critical_problems`: all unresolved critical incidents.

Each public incident adds `observation_freshness` and `concern_state` (`current_concern`, `saved_concern`, `resolved_observation`) using the persisted latest observation for its source/target. Existing `evidence_freshness` retains its incident last-seen meaning. No destructive migration or historical cleanup occurs.

**Truth rules:** stale is not resolved; saved is not healthy; observed healthy is not a verified repair; a new unknown observation cannot close an old incident. A fresh unhealthy observation may warrant current attention; older unresolved evidence alone forces an incomplete/unknown overall assessment rather than false attention or false green.

## H2 — Central presentation mapping

`src/lite/systemHealthPresentation.js` owns display-only component labels, recovery operation labels, availability language, incident grouping, evidence counts, time formatting, unknown fallbacks and controlled navigation destinations. Canonical operation IDs remain unchanged in FastAPI and persisted audit. Unknown IDs never become fabricated friendly service names. Legitimate device IDs remain recognizable, including short names.

Advanced incident disclosures retain sanitized incident ID, source, target, generation, revision and observation freshness. This does not expose raw evidence or secrets.

## H3 — Four-area information architecture

1. **Overview:** one authoritative headline; healthy signals; current concerns; older unresolved records; freshness and guidance.
2. **Problems & Diagnosis:** current confirmed issues first, saved unresolved issues second; narrative sections What happened / What we know / Cause assessment / Recommended next step; Check cause only when evidence is current and the backend is reachable.
3. **Recovery & History:** historical incidents, observed healthy transitions and distinct repair-attempt outcomes. A completed execution does not become a verified repair without separate verification state.
4. **Advanced Diagnostics:** dependencies, resource signals, policies, configuration mismatch, technical metadata, disclosed only when requested.

`LiteDetailsPanel` and `HomeGroupedSections` remain the only Manage and section-navigation framework. The selected incident can also be loaded by the canonical incident read endpoint for deep links, without activating repair. History stays bounded and lazy.

Home is adjusted to show current/saved evidence rather than treating all unresolved records as currently active.

## H4 — Azure Horizon desktop/mobile polish

Desktop retains the shared draggable/resizable, viewport-bounded Manage panel via `useDesktopManageGeometry`. Mobile retains the shared `mobileSnap` sheet, portal, focus, Escape, safe-area and scroll behavior. No alternate resize engine was added.

The System Health CSS uses exclusively existing Azure Horizon semantic tokens such as `--azure-surface`, `--azure-raised`, `--azure-border`, `--azure-text`, `--azure-muted`, `--azure-accent`, `--azure-success`, `--azure-warning`, `--azure-danger`, `--azure-shadow` and `--azure-radius-card`.

Spacing uses the Apps premium reference's restrained card density and section rhythm, without copying Apps-only selectors. Breakpoints and geometry do not depend on light or dark themes. At narrow widths, metrics stack and actions use accessible touch heights; long technical IDs wrap in disclosed detail. Reduced-motion CSS remains supported.

`LiteButton`'s existing `haptic` behavior is reused on eligible System Health actions. The existing shared action row and grouped navigation add opt-in access to the same `triggerLiteHaptic` helper. Unsupported vibration or reduced-motion environments do not vibrate. Haptics are never triggered by background refresh or state transitions.

## H5 — Qualification evidence

The following evidence was captured on the feature branch before documentation regeneration:

| Surface | Result | Evidence |
|---|---|---|
| Backend syntax and focused System Health tests | PASS | `py_compile`; focused and related qualification suites: 71 passed |
| Frontend System Health tests | PASS | Vitest: 3 files, 19 tests, including saved-to-fresh and fresh-to-saved regressions |
| Production build and Storybook | PASS | `npm run build`; `npm run build-storybook` |
| Mocked desktop/mobile and Axe | PASS | System Health Playwright: 42/42; portal-mounted Manage Axe included |
| Responsive visual suite | APPROVED | 42/42; 40 reviewed canonical light/dark desktop/mobile snapshots |
| Physical Android Chrome UI | PASS | Exact candidate `b65d83c2f83229e3abd59e01b33aaecaa5797734`; Chrome 158.0.8127.42/CDP 1.3, Manage, diagnosis `200`, Home return, no repair/preflight |
| Android performance and baseline attribution | RESIDUAL | 3 repetitions × 9 System Health interactions; 9/9 `MIXED`, 0/9 absolute target or hard-gate passes; no `APP_INCREMENTAL_COST` |

The physical run used the Dev-PC-hosted isolated candidate and synthetic qualification Owner harness. It is not production Server Phone backend evidence. The candidate proxy preserved the safe-read nonce and the screen revalidated the summary on mount; direct current responses and the rendered current-attention state converged. The performance residual is retained rather than converted into an unsupported result.

## H6 — Documentation and PR

This source document, source audit, additive contract notes and qualification handoff record the bounded qualification above. Canonical generated documentation was regenerated only after source and device evidence converged. A detailed Draft PR describes exact changes, reuse, risks, qualification and rollback. Existing PR #649 historical qualification evidence is retained unchanged.

## Security and future P4

UI → same-origin Caddy → FastAPI `/api/lite/system-health/*` → prepared SQLite state and approved backend-owned actions. Worker, agent, supervisor and existing recovery services own execution. Frontend does not run shell commands, speak to NATS, cache secrets, forge eligibility, alter identities, restore data or mark a process repaired merely because it is online.

P4 controlled self-healing is deliberately **NOT IMPLEMENTED**. A future separate review must demonstrate authorized execution ownership, idempotency, cooldown, fresh evidence, policy, progress and independent recovery verification before presenting a Fix control.

## Known residuals

- Production historical device labels require separate read-only provenance; there is no cleanup in H0–H6.
- Hardware vibration and ARM64 production-backend behavior were not independently qualified; the physical browser consumed the Dev-PC candidate.
- Android System Health performance retains a reproducible mixed residual: baseline absolute limits already miss on this device and candidate LoAF/Event Timing deltas remain in the mixed classification. Absolute target and hard-gate passes are not claimed; no PR-specific actionable regression was established.
- The two Devices assertion failures are pre-existing on current `main` and were reproduced in an isolated main worktree; PR #656 does not change the asserted files.
- Local `task lite:check` is blocked by the protected Java patch mismatch (`17.0.20.1` required versus `17.0.21.1` installed); no version guard or global toolchain was changed.
- CI exact-head status and final generated-documentation/repository-gate output are recorded in the PR continuation and must remain separate from local PASS evidence.
- Existing APIs retain legacy unresolved counts for compatibility; clients must use the new additive fields for current concern counters.
- Storybook/Playwright fixtures are synthetic and cannot prove live device recovery.
