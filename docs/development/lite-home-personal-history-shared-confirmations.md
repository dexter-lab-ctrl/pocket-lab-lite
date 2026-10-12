# Home personal history and shared confirmation hardening

**Status:** Committed source and regression definitions. **Exact-head tests, builds, CI, live runtime and Android qualification not executed in this implementation session.**

## Objective and boundaries

Give signed-in humans a durable reviewed-history position while preserving shared workspace activity as sanitized, backend-prepared evidence. Standardize consequence disclosure in existing high-impact workflows without migrating execution or authority to the browser.

## Backend

- `db/schema/0040_home_activity_read_cursors.sql` stores one monotonic revision and last-reviewed timestamp per authenticated human ID. No session ID, password, token, event body or secret is stored.
- `lite_home_activity_cursor.py` owns durable reads and atomic monotonic writes using existing SQLite migration/connection infrastructure. Reads do not perform schema migration or side effects; write path ensures migrations.
- `GET /api/lite/home/activity-cursor`: authenticated human session only; returns current prepared-history revision, reviewed revision, changed-since-review and last-reviewed timestamp. `Cache-Control: private, no-store`.
- `POST /api/lite/home/activity-cursor/review`: authenticated human session and normal write/CSRF enforcement; server obtains the revision from the prepared SQLite activity projection and atomically records it. No client-controlled identity or revision.
- No state write on Home load, no browser-local owner identity, no background approval, no false claim that activity completed.

## Timeline

Existing Phase 3C scheduled activity collector now prepares at most 12 sanitized events containing **domain, status and event time**. It excludes raw operation IDs, entity IDs, paths, payloads, evidence, and credentials. The Home view shows the bounded timeline alongside verified activity counts and an explicit **Mark activity reviewed** button.

This is a **workspace history with a private reviewed marker**, not a claim that each event belongs exclusively to a specific user. A revision difference means the prepared activity changed; it is not an exact count of unseen events. Expired/stale history must not enable Mark Reviewed.

## Shared form and confirmation presentation

- `LiteField`: consistent accessible labels, required/error/help association, preserved existing CSS classes.
- `LiteProtectedConfirmation`: reuses the pre-existing consequence presenter and preserves the workflow's original step-up/confirmation/mutation contract. Adopted by Identity, Devices removal, Apps removal and Recovery restore.
- Enterprise Identity person creation fields use `LiteField` for sign-in/display name and role.
- Complex Rules switches retain their native properly labeled checkbox semantics. No policy, approval or role inference is performed by common components.

## Tests provided (not executed)

- `tests/backend/test_lite_home_activity_cursor.py`: durable monotonic per-person cursor and authenticated route contract.
- `src/lite/homeActivityEvidence.test.js`: filtering/bounding sanitized activity.
- `src/lite/components/LiteSafeForms.test.jsx`: field errors and no implicit privileged confirmation.
- Existing Phase 3C and UI suites remain required.

```bash
task lite:ui:personal-history:backend
task lite:ui:protected-confirmation:unit
task lite:ui:p4:mocked
npm run test:a11y:states
npm run build:budget
task lite:check
```

## Risks and acceptance

The branch changes an SQLite migration and an activity projection materialization schema: exact-head migration upgrade, cursor isolation, cache boundaries, read-only GETs, CSRF rejection, stale projection handling, browser accessibility, low-memory impact, Android/Termux, and performance budgets all require qualification. Snapshot baselines must be reviewed rather than automatically rewritten. PR remains draft/unmerged until evidence is collected.

Backend remains control plane. The frontend never accesses NATS, runs shell commands, stores backend secrets, creates event IDs or grants approvals.
