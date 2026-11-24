# P4 — Controlled recovery and device lifecycle intelligence

**Status: IMPLEMENTED; DEV-PC QUALIFIED; final physical Android rerun BLOCKED.**
This document is the source-authored P4 completion record for PR #657. It does
not authorize production activation or deployment to the Server Phone.

| Provenance | Value |
| --- | --- |
| Base | `main` `1ef9bcb622db6ad1d34fc38278822ed434ad6776` |
| Code-bearing candidate | `57985fac694626d6301f9111f4270292fa351fe0` |
| Physical functional evidence | `.pocketlab-dev/validation/pr657-system-health-android-ui-57985fac6946/pr657-system-health-android-ui-57985fac6946.json` (`PASS`) |
| Final physical wrapper evidence | `.pocketlab-dev/validation/pr657-system-health-android-ui-57985fac6946/pr657-system-health-android-ui-final-57985fac6946.json` (`BLOCKED`; screenshot timeout) |
| Production activation | Not performed; installed Server Phone remains on the authorized main runtime |

## Completion ledger

| Phase | Previous status | Implemented | Qualification | Final status |
| --- | --- | --- | --- | --- |
| P4.0 source authority | PARTIAL | Authority map completed across registry, projections, policy, worker/watchdog, API and UI | Source audit plus focused regression suites | VERIFIED / PASS |
| P4.1 membership | PARTIAL | Migration 0045 adds durable enrollment generation; retirement, removal, late-event and generation fences are enforced | Lifecycle, malformed identity, duplicate-name, stale-event, protected-host and concurrency tests | IMPLEMENTED / QUALIFIED |
| P4.2 prepared reads | PARTIAL | Current/history joins, counts, pagination, freshness and removed-device filtering are membership-aware and read-only | SQLite integration, query/read-only, count/list and revision tests | IMPLEMENTED / QUALIFIED |
| P4.3 history | PARTIAL | Historical incident identity, generation, observations, decisions, attempts and sanitized receipts remain bounded and read-only | Pagination, removal, receipt, retention and deep-link/history tests | IMPLEMENTED / QUALIFIED |
| P4.4 recovery adapter | BLOCKED | Migration 0046 durable request ledger and watchdog-owned allowlisted recovery contract | Isolated worker-owner execution and restart/reconciliation evidence | IMPLEMENTED / QUALIFIED ISOLATED |
| P4.5 lifecycle | OUTSTANDING | Migration 0047 approval compatibility; actor-bound admission, idempotency, lease, deadline, retry/cooldown and fresh verification | Authorization, OPA, replay, generation, approval, resource and verification tests | IMPLEMENTED / QUALIFIED |
| P4.6 frontend | PARTIAL | Current/history/recovery states, safe invalidation, managed panel, haptics and responsive disclosures | Vitest, Storybook, mocked Playwright/Axe, visual review and earlier exact-SHA physical functional lane; final repeat blocked at screenshot capture | IMPLEMENTED / DEV-PC QUALIFIED; PHYSICAL RERUN BLOCKED |
| P4.7 qualification | NOT RUN | Existing suites and exact-candidate controllers completed and extended | Backend, frontend, Storybook, Playwright, visual and isolated recovery evidence passed; final physical wrapper exited 1 before performance promotion | DEV-PC QUALIFIED; PHYSICAL ANDROID BLOCKED |

## P4.0 authority and architecture

The authoritative flow remains:

```text
React/Vite PWA → same-origin proxy → FastAPI /api/lite/*
→ policy and durable admission → NATS/JetStream
→ worker/agent/supervisor/guardian → committed evidence and projections → FastAPI → UI
```

Durable enrollment is owned by `lite_control_plane_store.py`; incidents,
observations, diagnosis, prepared reads and recovery admission are owned by
`lite_system_health.py`; authentication and policy remain in the existing
FastAPI/OPA boundary; execution remains worker/supervisor owned. The UI never
connects to NATS, executes shell commands, stores backend credentials or
decides eligibility. GET paths perform prepared SQLite reads only.

Relevant source files are:

- `pocketlab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py`
- `pocketlab-final-structure/runtime/api_fastapi/services/lite_system_health.py`
- `pocketlab-final-structure/runtime/api_fastapi/routers/lite_system_health.py`
- `pocketlab-final-structure/runtime/api_fastapi/services/nats_bus.py`
- `pocketlab-final-structure/runtime/workers/pocketlab_worker.py`
- `src/lite/LiteSystemHealth.jsx`, `src/lite/systemHealthPresentation.js` and existing shared Azure Horizon components

## P4.1 membership and enrollment generation

Migration `0045_lite_enrollment_generation.sql` adds the durable generation
authority to the canonical enrollment record and binds observations, incidents
and removal receipts to it. Backfill is deterministic from authoritative active
registry records only. It is indexed and applied transactionally. Connectivity,
heartbeat freshness, display names, registry revisions, projection IDs and
browser identities are not generation authority.

Offline enrolled devices remain current membership. Retirement/removal is
explicit and prevents late heartbeats, stale projections, queued events and old
commands from restoring membership. Unknown or malformed identities are
classified as unknown and cannot create fabricated enrolled-device incidents.
Legitimate short IDs and the protected Server Host remain supported. Same-ID
re-enrollment is not implicitly allowed; an explicit authorized generation
transition is required before a future re-enrollment can authorize actions.

## P4.2 prepared read models

Summary, current incidents, saved unresolved incidents, critical counts,
details, dependencies, resources, recurrence, history, Home summaries and
contextual navigation use the same membership and generation classification.
Membership joins occur before pagination and aggregation. Removed devices do
not contribute to current actionable counts solely because historical SQLite
observations remain. Legacy unresolved fields remain additive-compatible; new
current/saved fields carry the distinction.

Freshness is calculated consistently from authoritative observation/revision
boundaries. Database-instance changes and stale projection revisions fail safe.
Missing registry/schema conditions are explicit rather than silently healthy.
Queries are bounded and indexed. Read endpoints do not migrate, write SQLite,
collect PM2 state, run shell commands, publish commands or execute recovery.

## P4.3 historical preservation

Removal is not recovery. Historical records preserve incident identity, state,
incident and enrollment generations, observations and timestamps, diagnosis,
recovery attempts, execution and verification outcomes, denials, lifecycle
events, retirement/removal time and sanitized receipt/correlation evidence when
authoritative. A removed unresolved incident is not rewritten healthy or
resolved. History ordering is deterministic, pagination is bounded and direct
history views are read-only; historical records cannot submit diagnosis or
recovery.

Retention remains bounded and does not prune active attempts or orphan repair
records. Concurrent removal and admission revalidate the membership and
generation fence before execution.

## P4.4 recovery-owner adapter

The former blocker was that a repair acknowledgment could not prove execution:
the impaired command consumer could not be used as its own recovery channel,
and the existing watchdog had no requestable, correlated operation contract.

Migration `0046_lite_system_health_recovery_requests.sql` provides the durable
request ledger. It stores bounded digests and sanitized metadata, exact incident
and enrollment generations, canonical target, allowlisted operation, actor and
policy facts, approval state, idempotency binding, lease/deadline, execution
correlation and verification evidence. The worker watchdog independently
reconciles this ledger and calls the existing `NatsBus.ensure_durable_consumer`
owner. It does not interrupt an in-flight callback and it is not a second
executor. Requests are candidate-only and require explicit qualification
activation; the installed runtime remains default-off.

The initial operation is the existing durable-consumer recovery candidate.
Arbitrary process restart, shell input, browser delivery, command-consumer
delivery, Risk B/C automatic recovery and unauthenticated local control are
not supported.

## P4.5 authorization and lifecycle

FastAPI authenticates the actor, enforces CSRF/session rules and asks the
existing OPA/policy boundary for `system_health.recovery` against the exact
`system_health_incident` target. Personal and Enterprise approval semantics are
preserved; qualification Owner authority is synthetic, scoped, short-lived and
isolated. Viewer/Auditor, anonymous, expired, stale-policy, wrong-workspace,
wrong-incident-generation and wrong-enrollment-generation requests fail closed.

Migration `0047_lite_system_health_recovery_policy.sql` carries the existing
approval model to the recovery action. Admission is actor-bound and durable.
The same canonical request and actor replay safely; changed actor, target,
generation or request material conflicts. Duplicate concurrent submissions are
single-flight. A request cannot remain queued or running indefinitely: lease,
deadline, bounded retry, cooldown, resource/low-power admission and explicit
terminal outcomes are persisted.

The lifecycle is `requested → preflight_checked → approved/admitted →
accepted_by_recovery_owner → executing → awaiting_verification → verified`,
with denied, blocked, expired, cancelled where supported, execution_failed,
verification_failed, verification_unavailable and manual_attention outcomes.
Verification requires fresh post-completion evidence tied to the exact target,
incident generation, enrollment generation, operation and execution boundary.
Healthy unrelated heartbeats, acceptance acknowledgments and stale pre-execution
observations do not verify recovery.

## P4.6 frontend

The four-area Azure Horizon experience remains Overview, Problems & Diagnosis,
Recovery & History and Advanced Diagnostics. It distinguishes current enrolled
online/offline devices, saved concerns, removed history, unknown membership and
protected-host conflicts using backend labels. Recovery controls are shown only
when backend-derived candidate eligibility is current; disabled, approval,
queued, working, verification, failure, unavailable and manual-attention states
are human-readable and historical records are read-only.

Existing `GlassCard`, `LiteButton`, `LiteActionRow`, `StateSurface`,
`LiteDetailsPanel`, `useDesktopManageGeometry`, `HomeGroupedSections`,
`useLitePanelSectionNavigation` and PR #640 native haptics are reused. Query
invalidation preserves the safe-read nonce and revision-driven convergence;
browser pending state is never execution authority. Desktop geometry, mobile
sheet/snap behavior, focus, safe areas, reduced motion, keyboard and screen
reader behavior remain within existing components.

## Qualification evidence

The final exact candidate was built with `POCKETLAB_BUILD_ID` set to the exact
code-bearing SHA. The focused/full evidence recorded for this continuation is:

| Surface | Result |
| --- | --- |
| Backend P4/System Health suites | `104 passed, 1 warning` |
| OPA/policy/harness suite | `37 passed` |
| Focused post-performance qualification | `17 passed` |
| Frontend targeted tests | `18 passed` in the final focused run |
| Storybook | Build PASS; deterministic P4 stories present |
| Mocked Playwright and Axe | `42 passed` visual/interaction run; final System Health interaction lane `48 passed` |
| Production build | PASS |
| Visual snapshots | Reviewed; current run `42 passed`, no unintended snapshot changes |
| Physical Android System Health | Earlier exact-SHA functional PASS; final wrapper rerun BLOCKED at first full-page screenshot |

The earlier exact-SHA functional evidence proves standard-user Android Chrome
CDP 1.3, explicit Server Phone identity, exact candidate
manifest/response/backend identity, isolated loopback transport, synthetic
Owner authorization, diagnosis, preflight, recovery request, fresh
verification, Home return and sanitized screenshots. The later bounded wrapper
reruns also proved candidate runtime identity, standard-user CDP and cleanup,
but failed at the first full-page screenshot with a reproducible 30-second
Playwright/CDP timeout while waiting for fonts. The isolated API/read fixtures
and mocked/UI suites separately cover saved/offline membership, historical
receipts, advanced disclosures and read-only history. The physical lane used
isolated DEV-PC SQLite/NATS/OPA/worker state and did not use the installed
backend or production database.

## Performance and residuals

The PR #588/#589 thresholds and attribution policy were unchanged. The final
exact-SHA physical wrapper stopped before the System-Health-only matrix could
be promoted because its functional screenshot step failed. A retained
three-repetition report with `0` target passes, `0` gate passes, `9` `MIXED`
and `0` `APP_INCREMENTAL_COST` belongs to older staging source commit
`ff67f01e465d2762cdb831fe22138609c2431c25`, not the frozen PR #657 code
candidate, and is therefore not PR #657 final evidence.

| Classification | Final exact-SHA status |
| --- | --- |
| TARGET MET / GATE PASS | BLOCKED / UNVALIDATED |
| PLATFORM_DOMINATED | BLOCKED / UNVALIDATED |
| MIXED | BLOCKED / UNVALIDATED |
| APP_INCREMENTAL_COST | BLOCKED / UNVALIDATED |

The older report is retained only as historical diagnostic material; it is not
used to claim an absolute performance result or PR-specific attribution for
the frozen candidate. No broad seven-screen performance run was performed.

## Default-off rollout and device boundary

Controlled recovery is implemented and isolated-qualified, but activation is
disabled by default and is not enabled on the installed Server Phone. Existing
autonomous watchdog, guardian, agent and protected recovery ownership remains
unchanged. Production activation would require a separate policy decision,
fresh admission and explicit authorization.

The Server Phone was used only as a consumer for wake/keyguard, existing
standard-user ADB/CDP, candidate reverse transport and sanitized screenshots.
No source, dependency, configuration, installed PWA, production SQLite,
credentials, PM2/Caddy/NATS/OPA service or runtime release was modified.

## Final P4 status

P4.0–P4.7 source implementation and DEV-PC qualification are complete for the
isolated candidate. The earlier exact-SHA physical functional lane passed, but
the final bounded physical wrapper remains **BLOCKED at screenshot capture**
and exact-candidate physical performance is **UNVALIDATED**. Controlled
recovery remains default-off, with no production activation or deployment.
