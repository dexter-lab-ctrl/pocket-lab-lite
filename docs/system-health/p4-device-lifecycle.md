# P4 — Controlled recovery and device lifecycle intelligence

**Source implementation: partial. Qualification: NOT RUN. No new recovery execution.**

Baseline: main `1ef9bcb622db6ad1d34fc38278822ed434ad6776` (#656).
This is not release or deployment authorization.

## Authority map (P4.0)

| Authority | Source | P4 treatment |
| --- | --- | --- |
| Enrollment | `api_fastapi/services/lite_control_plane_store.py`, schema 0022 | Exact device ID and removal_status; registry row persists independently of connectivity |
| Removal | `CONTROL_PLANE.retire_enrolled_device()`, device_removal_receipts | No change to retirement transaction or protected host rule |
| Incident intelligence | `api_fastapi/services/lite_system_health.py` | Membership join before pagination; ingestion skips non-active device identities |
| Policy | Existing authorization and OPA integration (#655) | Existing authenticated routes retained; no new action authorized |
| Command lifecycle | Existing worker and command-state admission (#654) | Unchanged; no new dispatch |
| Recovery owner | `workers/pocketlab_worker.py:worker_recovery_watchdog`, `api_fastapi/services/nats_bus.py:ensure_durable_consumer/recover_durable_consumers` | Autonomous recovery only |
| Verification | Durable-consumer status and committed health projections | Existing observation is not correlated request verification |
| Audit | System Health events, diagnoses, denials, repair attempts; durable removal receipts | Retained, bounded authenticated historical decisions |
| UI | `src/lite/LiteSystemHealth.jsx`, same-origin FastAPI | Presentation only |

## Membership and history (P4.1–P4.3)

Membership is not connectivity. The registry primary key joins agent, supervisor
and telemetry records. Shared system sources remain independent. Active registry
rows remain monitored even when the device is offline. Retired/removed and
unknown device rows are excluded from current incidents, current/saved counts,
dependency nodes, resources and recurrence lists. A protected host with an
inconsistent removal flag is retained with unknown evidence, not declared healthy.
Historical records are not rewritten as resolved. No new removal flag or schema
migration is introduced. Existing retention rules still apply.

The store rejects late upserts of retired IDs and duplicate normalized identity
conflicts; the incident engine does not reactivate retired identities. A new
authoritative enrollment with a distinct ID has its own incident identity. An
explicit same-ID re-enrollment protocol, if introduced in future, must add a
durable generation fence before it is permitted to authorize recovery. P4 does
not implement that protocol. Registry revision is metadata, not an immutable
enrollment generation.

Current incidents filter before LIMIT/OFFSET and use limit+1 for next_offset.
Summary counts aggregate matching rows, rather than silently cap at 256.
History and direct incident reads retain original incident state, timestamps,
generation, safe label, membership state and retirement time. Decisions include
bounded sanitized removal receipts, attempts, denials, diagnoses and events.
No live collectors are added. GET paths use existing prepared SQLite reads.

## Recovery decision (P4.4–P4.5): BLOCKED

The existing watchdog calls BUS.recover_durable_consumers(), which operates on
local registered durable specs and refuses to interrupt an in-flight callback.
The command connection itself is the impaired path. A command sent through
that same durable is not a demonstrated request-delivery contract, and a
healthy later projection cannot prove this particular request executed.
No requestable owner contract with request correlation, authorization,
generation fence and independent verification was established. Do not add a
parallel dispatcher, direct NATS or shell execution, forced PM2 restart, or
a flag that bypasses the structural blocker.

The repair route stays 409 and records a sanitized denial. Preflight now
distinguishes membership, stale or non-unhealthy observation, generation and
unsupported-operation blockers. Denial idempotency compares incident,
operation, generation and actor class; raw idempotency keys are not exposed.
No new approval, OPA rule, cooldown, retry, single-flight execution,
cancellation, execution/verification lifecycle or enablement flag is claimed.
Existing guardian behavior remains unchanged.

Before a future enablement PR, establish an existing-owner request path that
does not depend on the failed consumer, approved typed dispatch, actor/role
and policy revision enforcement, Personal/Enterprise approval, durable
admission/correlation, resource limits, bounded retries and cooldown, and
fresh independent generation-bound verification. Default must be OFF after
that path is authored and separately qualified. Never report acceptance or
a healthy observation alone as verified repair.

## Frontend reuse (P4.6)

| Requirement | Reused source | Reference |
| --- | --- | --- |
| Buttons, action rows, cards, empty states | src/lite/LiteUi.jsx: LiteButton, LiteActionRow, GlassCard, StateSurface | #606 |
| Theme | src/lite/theme/azureHorizonTokens.css: --azure-surface, --azure-text, --azure-border, --azure-muted, --azure-raised, --azure-warning | #622 |
| Manage | src/lite/LiteOverlay.jsx: LiteDetailsPanel; src/lite/components/useDesktopManageGeometry.js | #623 |
| Density | src/lite/catalog/appsPremiumRefinement.css: clamp(.75rem,2vw,1.2rem) panel padding, .85rem section gap; existing System Health H4 spacing | #636/#656 |
| Native controls | shared haptic props; useLitePanelSectionNavigation, HomeGroupedSections | #648/#656 |
| System Health | LiteSystemHealth.jsx, systemHealthPresentation.js, systemHealth.css | #656 |

No new CSS palette or geometry controller. Historical rows use existing
action rows and Details/Manage, no generic Fix or Request recovery action.
The user sees a safe blocked state, not invented progress. Device removal/add
invalidates the existing System Health query family; first mount revalidates
current incident reads. Cross-device and cross-tab propagation needs runtime
qualification.

## Qualification (P4.7) — ADDED, NOT RUN

Authored backend membership/late-event/pagination/resource/protected-host
tests, presentation grouping, deterministic membership mocks, desktop/mobile
Storybook stories, mocked Playwright history/axe/no-write scenario. Existing
H0–H6 visual and responsive coverage remains; P4-specific canonical screenshot
baselines are not generated or approved. Remaining gaps include full registry
retirement transaction integration, receipt and generation stress, UI visual
matrix, cache races, cross-tab convergence and complete runtime qualification.
Execution scenarios cannot be meaningfully qualified until the blocked owner
contract exists.

Future commands (DEV-PC, separate qualification session):

```bash
python3 -m pytest -q tests/backend/test_lite_system_health.py tests/backend/test_device_removal_invite_reconciliation.py
npx vitest run src/lite/systemHealthPresentation.test.js src/lite/LiteSystemHealth.test.jsx
npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
npm run build
task lite:docs:generate
task lite:docs:check
task lite:check
```

Isolated candidate qualification: enroll disposable device; disconnect it;
verify offline remains current where supported by evidence; explicitly remove
it using authorized Devices controls; inspect history/receipt and replay late
observations. Verify counts and paging, no mutation by GET, indexed joins,
bounded query cost/CPU/RAM and low SQLite writes. Cover 320/360/390/430/768/
1024/1280/1440px in both themes, focus, reduced motion, scroll and Axe, review
screenshots without automatically accepting regressions. Physical Android:
separate consent and isolated candidate only; verify PM2 owner, NATS, OPA,
low-power behavior and restart continuity. Do not exercise unqualified repair
or production mutation. Rollback by reverting these source commits before
deployment; no schema changes or production operations were made.

## Verdict

P4.0–P4.3 membership source work and P4.6 historical UX implemented in part;
P4.4/P4.5 execution blocked; P4.7 focused coverage authored, not run.
No CI troubleshooting, physical Android qualification, deployment or release.
