# System Health — Azure Horizon H0–H6 experience hardening

**State:** SOURCE IMPLEMENTATION AUTHORED — NOT VALIDATED. **Base:** `main` at `a9f8b2d7625fd84f82dffee5f44bcee20225661e`. **Feature:** `feat/azure-horizon-system-health-experience-hardening`. This document describes source changes, not a qualified runtime.

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

## H5 — Qualification source authored; NOT RUN

- Backend: target parsing, malformed projections, short identities, fresh/saved/critical counts, unknown lifecycle, observed-not-repaired, repair denial.
- Frontend: map known IDs to meaningful labels, unknown fallbacks, evidence grouping, counts, action destinations and no stale green.
- Storybook: healthy, critical, unknown, stale, mixed, offline, no incidents, many incidents, recovery outcomes, long/malformed target, light/dark, desktop/mobile.
- Playwright: current/saved issue cards, narrative, disclosure, safe action semantics, deep links, keyboard dismissal, Axe and 320–1440px responsive matrix.
- Visual: light/dark at 320, 360, 390, 430, tablet, 1024, 1280, 1440 and Manage desktop/mobile screenshots. Baselines have **not** been captured or approved.
- Performance future observations: no new live polling, prepared reads, bounded history, no new background collector, stable viewport layout, ARM64 browser memory.

See [qualification handoff](qualification-handoff-h0-h6.md). No build, tests, docs generation, screenshot, CI troubleshooting, or Android runtime qualification occurred in this source session.

## H6 — Documentation and PR

This source document, source audit, additive contract notes and qualification handoff are committed to the feature branch. A detailed Draft PR describes exact changes, reuse, risks, qualification and rollback. Existing PR #649 historical qualification evidence is retained unchanged.

## Security and future P4

UI → same-origin Caddy → FastAPI `/api/lite/system-health/*` → prepared SQLite state and approved backend-owned actions. Worker, agent, supervisor and existing recovery services own execution. Frontend does not run shell commands, speak to NATS, cache secrets, forge eligibility, alter identities, restore data or mark a process repaired merely because it is online.

P4 controlled self-healing is deliberately **NOT IMPLEMENTED**. A future separate review must demonstrate authorized execution ownership, idempotency, cooldown, fresh evidence, policy, progress and independent recovery verification before presenting a Fix control.

## Known residuals

- Production historical device labels require separate read-only provenance; there is no cleanup in H0–H6.
- Screenshot appearance, 320px/desktop geometry, light/dark parity, focus and haptics await qualification.
- New visual specs require human-approved baseline creation in a later session.
- Existing APIs retain legacy unresolved counts for compatibility; clients must use the new additive fields for current concern counters.
- Storybook/Playwright fixtures are synthetic and cannot prove live device recovery.
