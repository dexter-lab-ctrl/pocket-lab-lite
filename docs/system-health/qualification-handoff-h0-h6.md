# System Health H0–H6 qualification handoff

**All commands below are deferred. They were NOT RUN during H0–H6 implementation.**

## Preconditions

Use a clean checkout of the exact PR feature SHA on a dev PC/WSL2 Ubuntu. Keep production Android/Termux state, PM2, SQLite, OPA, credentials and NATS untouched. Do not interpret a passing mocked test as production runtime readiness.

## Focused commands — execute in a separately authorized qualification session

```bash
python3 -m py_compile pocket-lab-final-structure/runtime/api_fastapi/services/lite_system_health.py
python3 -m pytest -q tests/backend/test_lite_system_health.py
npx vitest run src/lite/LiteSystemHealth.test.jsx src/lite/systemHealthPresentation.test.js
npm run build
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
```

Expected: no Python syntax errors; all source and UI tests pass; Vite build succeeds; mocked desktop/mobile UI and Axe checks pass; no repair POST issued by review/navigation interactions.

## Visual and accessibility qualification — deferred

```bash
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health-visual.spec.ts --project=mocked-desktop --project=mocked-mobile
```

The new screenshot tests deliberately ship **without approved baselines**. In a separate, human-supervised qualification step, review 320, 360, 390, 430, 768, 1024, 1280 and 1440 pixel cases in both themes; establish and approve baselines only after visual assessment. Do not auto-approve failed snapshots.

Review real keyboard focus restoration, Escape, screen-reader headings, 44px touch targets, semantic contrast, no horizontal scrolling, portal stacking, single scroll owner, short-content and long-history Manage panels, reduced motion, unsupported haptics and safe-area insets.

## Repository and documentation gates — deferred

```bash
task lite:docs:generate
task lite:docs:check
task lite:check
git diff --check
```

These regenerate/check documentation only in qualification; compare source-authored contracts against generated output and record any drift without silently altering historical PR #649 evidence.

## Non-destructive runtime checks — separately authorized only

On isolated candidate runtime (never production by default), verify: fresh unhealthy observation → current concern; unknown observation → saved concern; stale critical record stays unresolved; observed healthy → resolved observation, **not** verified repair; no new System Health repair executor; `409` policy denial preserved; no direct NATS or shell from browser; no leaked tokens, paths or backend-only evidence; no high-frequency poll burst or additional service.

Observe an ARM64 phone only after explicit scheduling and authorization. Keep Termux temporary files under the writable project state directory or ${TMPDIR:-$PREFIX/tmp}, not `/tmp`.

## Performance review definitions

Compare idle network requests, API response size, query invalidations, CPU/RAM/battery and time to first meaningful System Health summary against the same baseline. Ensure 30-row capped default lists, lazy Manage queries, reused geometry and no new periodic collector. Do not lower existing thresholds merely to pass.

## Handoff status

| Gate | At PR creation |
|---|---|
| Source edits | Authored, not validated |
| Backend tests | Added, NOT RUN |
| Vitest | Added, NOT RUN |
| Storybook | Added, NOT RUN |
| Playwright/Axe | Added, NOT RUN |
| Visual screenshots | Defined; no capture, baselines not approved |
| Build/docs generators | NOT RUN |
| CI | Not troubleshot |
| Physical Android | NOT RUN |
| Production deployment | NOT RUN |

Failures belong to a separate qualification/fix PR or an authorized continuation. Preserve the Draft PR state until qualification evidence supports promotion.

## Rollback

If qualification or code review rejects this work, revert the feature commits or close the Draft PR; `main` is unaffected. After merge in a separately authorized session, use `git revert` of the merge commit and redeploy only through the governed release process. No data migration or destructive cleanup is needed for source rollback; existing incident/evidence tables and immutable identity history remain intact.
