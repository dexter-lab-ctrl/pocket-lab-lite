# System Health P6 qualification handoff — executed with bounded evidence

This handoff records the approved qualification session for PR #649. The Gate B continuation started at feature SHA `1ce603d5524824e11b6b47da415569452f2bc93c` and finished at `e3c9777d4e2c87da12c8197c24d8f2e4ab2766a6`; base SHA: `cfd4194fd338aeae07580fa7f227d118bebdd907`. The exact candidate was staged in a run-owned, isolated Android/Termux runtime on the physical Server Phone. Production `main`, PM2, Caddy, NATS and SQLite were not activated or modified. No source edits, commits or pushes were performed on the phone.

## 1. Baseline/read-only review

    git switch feat/azure-horizon-system-health-intelligence
    git status --short
    git diff origin/main...HEAD --stat
    git diff --check

Recorded exact base/head, local/remote parity, clean branch transitions and candidate manifest identity. The final local and remote feature SHA was `e3c9777d4e2c87da12c8197c24d8f2e4ab2766a6`; no production rollout was performed.

## 2. Backend

    .venv/bin/python -m py_compile pocket-lab-final-structure/runtime/api_fastapi/services/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/routers/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3b_projections.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3c_projections.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_system_health.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_api.py

Result: py_compile passed; the new Android qualifier tests passed (8), the combined qualifier/System Health regression run passed (15), the full backend stage passed (416 with 1 warning), and the Lite backend gate passed (171, with 165 unrelated tests deselected). Additional migration, SQLite, authorization, security, identity, harness and tooling suites passed in the recorded DEV-PC run. The isolated route probe verified migration count 44, authenticated reads, diagnosis persistence, CSRF/session expiry, generation fencing, idempotent blocked repair and sanitized evidence. The final sanitized phone-candidate report is `.pocketlab-dev/validation/pr649-system-health-android-ui-e3c9777d4e2c/pr649-system-health-android-ui-final-e3c9777d4e2c.json`.

## 3. Frontend/mocked

    npm run test:unit -- src/lite/LiteSystemHealth.test.jsx
    VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
    npm run build-storybook
    npm run build

Result: 6 focused unit tests, 10 System Health Playwright tests, full unit 625 tests, Storybook build and production build passed. The final mocked gate completed 52 passed with 10 configured skips; accessibility completed 2 passed. Mocked accessibility, themes, context links, focus return, mobile snap and disabled repair were exercised. Canonical Home desktop/mobile snapshots were regenerated only for Home after physical validation and Home comparison passed. Hardware haptic actuation was not independently measurable through CDP.

## 4. Isolated ARM64/Termux candidate qualification

The exact feature candidate was copied as a read-only, checksum-bound snapshot to a run-owned phone directory. The Server Phone reported `aarch64` and Python `3.14.6`; the candidate used loopback-only FastAPI and worker processes, a disposable loopback NATS/JetStream broker, and an isolated SQLite database. Production PM2, Caddy, NATS and the production database were not used.

The migration proof passed from schema 42 to schema 44: migrations `[43, 44]` applied once, repeat application was empty/idempotent, quick-check/integrity-check/foreign-key checks passed, required System Health tables and indexes were present, marker data and diagnosis/audit/projection rows persisted, concurrent read/write errors were empty, and the isolated rollback proof restored/opened a schema-42 snapshot with the base runtime. The candidate database remained WAL-backed; the bounded post-UI-read WAL observation was `4,124,152` bytes. The production database was never touched.

The real candidate API returned the repository-defined route results: anonymous summary `401`; authenticated summary, incidents, detail, history, dependencies, resources, intelligence, configuration, policies, repairs, app diagnostics, diagnosis and preflight `200`; blocked repair `409` with `system_health_executor_not_qualified`; stale generation denial `409` with `incident_generation_changed`; unauthorized diagnosis `401`; idempotent replay remained blocked and recorded; raw evidence was not exposed. The projection driver verified duplicate suppression. The API lane used the `security-assurance-runner` profile with local-server target scope; the Android UI lane used a separate short-lived target-bound `qualification-owner` browser bridge. Destructive mode and test-auth bypass were disabled, and revocation returned `200`.

## 5. Non-disruptive Termux/ARM64 production observation

Authorized same-origin, bounded read-only observation used the existing normal runtime identity; no bypass was used:

    curl -fsS http://127.0.0.1:8443/api/lite/system-health/summary | python3 -m json.tool
    pm2 status

Result: Caddy, FastAPI readiness/status, NATS monitor/JetStream, PM2 core services and the main checkout were healthy. The installed production backend returned 404 for `/api/lite/system-health/`, as expected for the unchanged `main` runtime, and was not represented as PR #649 backend evidence. The production checkout remained clean at `cfd4194fd338aeae07580fa7f227d118bebdd907`; no service was stopped or mutated.

## 6. Android Chrome qualification boundary

The final Windows standard-user preflight and browser run completed without UAC elevation. Android Chrome `157.0.8103.50`, CDP Protocol `1.3`, package `com.android.chrome`, loopback websocket and explicit ADB device selection were verified. The existing CDP relay was reused through the repository-owned bounded standard-user bridge; no elevation, firewall change, protected-service manipulation or Chrome restart was used.

The final narrow Android UI qualifier is exact-SHA candidate evidence: the manifest and API response headers matched `e3c9777d4e2c87da12c8197c24d8f2e4ab2766a6`; summary, incidents and diagnosis responses were consumed through the candidate same-origin proxy. The active incident rendered, Manage opened, diagnosis returned `200`, Fix remained disabled, no repair/preflight write occurred and navigation returned Home. A first retry timed out waiting for the fixture incident; a fresh session rerun passed and cleanup completed. Earlier MSW-based UI evidence remains separately labelled as fixture evidence.

The previously completed Home-only performance candidate ran 18 reports with three 18-report baseline repetitions. Absolute targets remained red; final normalized attribution was `MIXED=18`, `APP_INCREMENTAL_COST=0`. The broad seven-screen workflow was not run. No unrelated optimization was made.

## 7. Bounded low-power candidate observation

Candidate-only System Health latency samples were `139.12`, `125.95`, `194.26`, `187.17` and `234.95 ms` (mean `176.29 ms`, max `234.95 ms`). Candidate API and worker processes were owned and sleeping during observation; available memory was approximately `2.14 GB`, free phone storage approximately `92.8 GB`, and 85 thermal zones were observed with raw thermal values sanitized. These are isolated-candidate measurements, not production regression or improvement claims. No production stress or fault injection was performed.

## 8. Deferred isolated fault scenarios

NATS down/connected-but-unconsumed; active callback in flight; worker dead/returned; disconnected agent vs stopped supervisor; unexpected Caddy route state; PhotoPrism stopped/uninstalled; SQLite storage pressure; expired evidence; partial app dependency; code release/rollback blockers; failed post-repair verification; idempotent concurrent denial; rejected authorization; recurrence after resolution; unknown command outcome; restart-storm budget.

Do not treat process online, accepted command or an observed healthy signal as proof of a verified repair. Controlled fault injection requires separate approval and nonproduction targets.

## 9. Promotion gate

Targeted backend/frontend tests, permission/redaction checks, exact-SHA ARM64/Termux candidate identity, isolated migrations, real candidate API routes, worker/NATS projection behavior, bounded candidate resource observations, Android Chrome UI-to-candidate interaction and cleanup passed. Live PR #649 backend behavior on the installed production runtime was intentionally not activated. Deferred fault-injection scenarios and production deployment readiness remain incomplete and are not represented as passed. The former Android UI blocker was a harness gap and is now fixed; production activation remains a separate promotion/rollback safety and authorization boundary.

**Qualification status: DEV-PC AND ISOLATED PHYSICAL ANDROID/TERMUX BACKEND + ANDROID CHROME-TO-CANDIDATE UI QUALIFIED — PRODUCTION BACKEND ACTIVATION NOT PERFORMED; PROMOTION/ROLLBACK READINESS BLOCKED. DRAFT PR REQUIRED.**
