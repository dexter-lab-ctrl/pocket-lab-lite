# System Health P6 qualification handoff — executed with bounded evidence

This handoff records the approved qualification session for PR #649. The Gate B continuation started at feature SHA `1ce603d5524824e11b6b47da415569452f2bc93c` and finished at `1ba45f410cf3c9a1f993b84b6dcffe90a895ac5b`; base SHA: `cfd4194fd338aeae07580fa7f227d118bebdd907`. The exact candidate was staged in a run-owned, isolated Android/Termux runtime on the physical Server Phone. Production `main`, PM2, Caddy, NATS and SQLite were not activated or modified. No source edits, commits or pushes were performed on the phone.

## 1. Baseline/read-only review

    git switch feat/azure-horizon-system-health-intelligence
    git status --short
    git diff origin/main...HEAD --stat
    git diff --check

Recorded exact base/head, local/remote parity, clean branch transitions and candidate manifest identity. The final local and remote feature SHA was `1ba45f410cf3c9a1f993b84b6dcffe90a895ac5b`; no production rollout was performed.

## 2. Backend

    .venv/bin/python -m py_compile pocket-lab-final-structure/runtime/api_fastapi/services/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/routers/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3b_projections.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3c_projections.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_system_health.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_api.py

Result: py_compile passed; the new Android qualifier tests passed (8), the combined qualifier/System Health regression run passed (15), and the full backend gate passed (171, with 165 unrelated tests deselected by the gate). Additional migration, SQLite, authorization, security, identity, harness and tooling suites passed in the recorded DEV-PC run. The isolated route probe verified migration count 44, authenticated reads, diagnosis persistence, CSRF/session expiry, generation fencing, idempotent blocked repair and sanitized evidence. The final sanitized phone-candidate report is `.pocketlab-dev/validation/pr649-system-health-android-1ba45f410cf3.json`.

## 3. Frontend/mocked

    npm run test:unit -- src/lite/LiteSystemHealth.test.jsx
    VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
    npm run build-storybook
    npm run build

Result: 6 focused unit tests, 10 System Health Playwright tests, full unit 625 tests, Storybook build and production build passed. Mocked accessibility, themes, context links, focus return, mobile snap and disabled repair were exercised. Canonical Home desktop/mobile snapshots were regenerated only for Home after physical validation and Home comparison passed. Hardware haptic actuation was not independently measurable through CDP.

## 4. Isolated ARM64/Termux candidate qualification

The exact feature candidate was copied as a read-only, checksum-bound snapshot to a run-owned phone directory. The Server Phone reported `aarch64` and Python `3.14.6`; the candidate used loopback-only FastAPI and worker processes, a disposable loopback NATS/JetStream broker, and an isolated SQLite database. Production PM2, Caddy, NATS and the production database were not used.

The migration proof passed from schema 42 to schema 44: migrations `[43, 44]` applied once, repeat application was empty/idempotent, quick-check/integrity-check/foreign-key checks passed, required System Health tables and indexes were present, marker data and diagnosis/audit/projection rows persisted, concurrent read/write errors were empty, and the isolated rollback proof restored/opened a schema-42 snapshot with the base runtime. The candidate database remained WAL-backed; the bounded post-read WAL observation was `3,131,232` bytes. The production database was never touched.

The real candidate API returned the repository-defined route results: anonymous summary `401`; authenticated summary, incidents, detail, history, dependencies, resources, intelligence, configuration, policies, repairs, app diagnostics, diagnosis and preflight `200`; blocked repair `409` with `system_health_executor_not_qualified`; stale generation denial `409` with `incident_generation_changed`; unauthorized diagnosis `401`; idempotent replay remained blocked and recorded; raw evidence was not exposed. The projection driver verified duplicate suppression. The Security Assurance harness used the `security-assurance-runner` profile, local-server target scope, destructive mode disabled, test-auth bypass disabled, and revocation returned `200`.

## 5. Non-disruptive Termux/ARM64 production observation

Authorized same-origin, bounded read-only observation used the existing normal runtime identity; no bypass was used:

    curl -fsS http://127.0.0.1:8443/api/lite/system-health/summary | python3 -m json.tool
    pm2 status

Result: Caddy, FastAPI readiness/status, NATS monitor/JetStream, PM2 core services and the main checkout were healthy. The installed production backend returned 404 for `/api/lite/system-health/`, as expected for the unchanged `main` runtime, and was not represented as PR #649 backend evidence. The production checkout remained clean at `cfd4194fd338aeae07580fa7f227d118bebdd907`; no service was stopped or mutated.

## 6. Android Chrome qualification boundary

The current Windows standard-user preflight was attempted without UAC elevation. The Windows ADB selector reported two authorized logical connections for the same Android model, and the existing `tcp:9222` Chrome forward closed unexpectedly; the Chrome DevTools socket was not exposed. The repository therefore did not claim a current browser-to-candidate-backend result. No elevation, firewall change, port replacement or Chrome restart was attempted.

The earlier narrow Android UI qualifier remains frontend-only evidence at its then-exact SHA: 10/10 checks passed for attention, diagnosis, disabled repair with zero repair POSTs, focus restoration, Compact/Expand, healthy/stale/unknown, Daylight/Black/System, deep link, Home navigation, reduced motion and simulated 200% layout safety. Its API responses were repository MSW fixtures. It is not evidence that Android Chrome consumed the current phone-side candidate API.

The previously completed Home-only performance candidate ran 18 reports with three 18-report baseline repetitions. Absolute targets remained red; final normalized attribution was `MIXED=18`, `APP_INCREMENTAL_COST=0`. The broad seven-screen workflow was not run. No unrelated optimization was made.

## 7. Bounded low-power candidate observation

Candidate-only System Health latency samples were `127.41`, `202.13`, `337.09`, `209.35` and `136.83 ms` (mean `202.56 ms`, max `337.09 ms`). Candidate API and worker processes were owned and sleeping during observation; available memory was approximately `2.21 GB`, free phone storage approximately `92.6 GB`, and 85 thermal zones were observed with raw thermal values sanitized. These are isolated-candidate measurements, not production regression or improvement claims. No production stress or fault injection was performed.

## 8. Deferred isolated fault scenarios

NATS down/connected-but-unconsumed; active callback in flight; worker dead/returned; disconnected agent vs stopped supervisor; unexpected Caddy route state; PhotoPrism stopped/uninstalled; SQLite storage pressure; expired evidence; partial app dependency; code release/rollback blockers; failed post-repair verification; idempotent concurrent denial; rejected authorization; recurrence after resolution; unknown command outcome; restart-storm budget.

Do not treat process online, accepted command or an observed healthy signal as proof of a verified repair. Controlled fault injection requires separate approval and nonproduction targets.

## 9. Promotion gate

Targeted backend/frontend tests, permission/redaction checks, exact-SHA ARM64/Termux candidate identity, isolated migrations, real candidate API routes, worker/NATS projection behavior, bounded candidate resource observations and cleanup passed. Live PR #649 backend behavior on the installed production runtime was intentionally not activated. Current Android Chrome browser-to-candidate integration remains blocked by the unavailable CDP endpoint. Deferred fault-injection scenarios and production deployment readiness remain incomplete and are not represented as passed.

**Qualification status: DEV-PC AND ISOLATED PHYSICAL ANDROID/TERMUX BACKEND QUALIFIED — PRODUCTION BACKEND ACTIVATION NOT PERFORMED; CURRENT ANDROID CHROME-TO-CANDIDATE UI PARTIAL/BLOCKED BY CDP; DEPLOYMENT READINESS BLOCKED. DRAFT PR REQUIRED.**
