# System Health P6 qualification handoff — executed with bounded evidence

This handoff records the approved qualification session for PR #649. The Gate B continuation started at feature SHA `1ce603d5524824e11b6b47da415569452f2bc93c`; the prior UI candidate was `8c21a4ff729f89064aa794c65bf8795beeef4ed4`; the backend-promotion candidate qualified below is `0b767dc662c8f7c37accb4bc5fbad71a5f31564f`; the final documentation-synchronized feature SHA is `613fab662f62c090f2fa7d7930315b4cb6c1e814`; base SHA: `cfd4194fd338aeae07580fa7f227d118bebdd907`. The exact candidate was staged in a run-owned, inactive Android/Termux cache on the physical Server Phone. Production `main`, PM2, Caddy, NATS and SQLite were not activated or modified. No source edits, commits or pushes were performed on the phone.

## 1. Baseline/read-only review

    git switch feat/azure-horizon-system-health-intelligence
    git status --short
    git diff origin/main...HEAD --stat
    git diff --check

Recorded exact base/head, local/remote parity, clean branch transitions and candidate manifest identity. The final documentation-synchronized feature SHA is `613fab662f62c090f2fa7d7930315b4cb6c1e814`; the UI/device candidate was `8c21a4ff729f89064aa794c65bf8795beeef4ed4` and the backend-promotion candidate was `0b767dc662c8f7c37accb4bc5fbad71a5f31564f`. No production rollout was performed.

## 2. Backend

    .venv/bin/python -m py_compile pocket-lab-final-structure/runtime/api_fastapi/services/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/routers/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3b_projections.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3c_projections.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_system_health.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_api.py

Result: py_compile passed; the new Android qualifier tests passed (8), the combined qualifier/System Health regression run passed (15), the full backend stage passed (416 with 1 warning), and the Lite backend gate passed (171, with 165 unrelated tests deselected). Additional migration, SQLite, authorization, security, identity, harness and tooling suites passed in the recorded DEV-PC run. The isolated route probe verified migration count 44, authenticated reads, diagnosis persistence, CSRF/session expiry, generation fencing, idempotent blocked repair and sanitized evidence. The final sanitized phone-candidate report is `.pocketlab-dev/validation/pr649-system-health-android-ui-8c21a4ff729f/pr649-system-health-android-ui-final-8c21a4ff729f.json`.

## 3. Frontend/mocked

    npm run test:unit -- src/lite/LiteSystemHealth.test.jsx
    VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
    npm run build-storybook
    npm run build

Result: 6 focused unit tests, 10 System Health Playwright tests, full unit 625 tests, Storybook build and production build passed. The final mocked gate completed 52 passed with 10 configured skips; accessibility completed 2 passed. Mocked accessibility, themes, context links, focus return, mobile snap and disabled repair were exercised. Canonical Home desktop/mobile snapshots were regenerated only for Home after physical validation and Home comparison passed. Hardware haptic actuation was not independently measurable through CDP.

## 4. Isolated ARM64/Termux candidate qualification

The exact feature candidate was copied as a read-only, checksum-bound snapshot to a run-owned phone directory. The Server Phone reported `aarch64` and Python `3.14.6`; the candidate used loopback-only FastAPI and worker processes, a disposable loopback NATS/JetStream broker, and an isolated SQLite database. Production PM2, Caddy, NATS and the production database were not used.

The migration proof passed from schema 42 to schema 44: migrations `[43, 44]` applied once, repeat application was empty/idempotent, quick-check/integrity-check/foreign-key checks passed, required System Health tables and indexes were present, marker data and diagnosis/audit/projection rows persisted, concurrent read/write errors were empty, and the isolated rollback proof restored/opened a schema-42 snapshot with the base runtime. The candidate database remained WAL-backed; the bounded post-UI-read WAL observation was `4,293,072` bytes. The production database was never touched.

The real candidate API returned the repository-defined route results: anonymous summary `401`; authenticated summary, incidents, detail, history, dependencies, resources, intelligence, configuration, policies, repairs, app diagnostics, diagnosis and preflight `200`; blocked repair `409` with `system_health_executor_not_qualified`; stale generation denial `409` with `incident_generation_changed`; unauthorized diagnosis `401`; idempotent replay remained blocked and recorded; raw evidence was not exposed. The projection driver verified duplicate suppression. The API lane used the `security-assurance-runner` profile with local-server target scope; the Android UI lane used a separate short-lived target-bound `qualification-owner` browser bridge. Destructive mode and test-auth bypass were disabled, and revocation returned `200`.

## 5. Non-disruptive Termux/ARM64 production observation

Authorized same-origin, bounded read-only observation used the existing normal runtime identity; no bypass was used:

    curl -fsS http://127.0.0.1:8443/api/lite/system-health/summary | python3 -m json.tool
    pm2 status

Result: Caddy, FastAPI readiness/status, NATS monitor/JetStream, PM2 core services and the main checkout were healthy. The installed production backend returned 404 for `/api/lite/system-health/`, as expected for the unchanged `main` runtime, and was not represented as PR #649 backend evidence. The production checkout remained clean at `cfd4194fd338aeae07580fa7f227d118bebdd907`; no service was stopped or mutated.

## 6. Android Chrome qualification boundary

The final Windows standard-user preflight and browser run completed without UAC elevation. Android Chrome `157.0.8103.50`, CDP Protocol `1.3`, package `com.android.chrome`, loopback websocket and explicit ADB device selection were verified. The existing CDP relay was reused through the repository-owned bounded standard-user bridge; no elevation, firewall change, protected-service manipulation or Chrome restart was used.

The final narrow Android UI qualifier is exact-SHA candidate evidence: the manifest and API response headers matched `8c21a4ff729f89064aa794c65bf8795beeef4ed4`; summary, incidents and diagnosis responses were consumed through the candidate same-origin proxy. The active incident rendered, Manage opened, diagnosis returned `200`, Fix remained disabled, no repair/preflight write occurred and navigation returned Home. One bounded session timed out before the projection incident was visible; a fresh session rerun passed and cleanup completed. Earlier MSW-based UI evidence remains separately labelled as fixture evidence.

The previously completed Home-only performance candidate ran 18 reports with three 18-report baseline repetitions. Absolute targets remained red; final normalized attribution was `MIXED=18`, `APP_INCREMENTAL_COST=0`. The broad seven-screen workflow was not run. No unrelated optimization was made.

## 7. Bounded low-power candidate observation

Candidate-only System Health latency samples were `124.67`, `226.88`, `229.61`, `293.75` and `303.32 ms` (mean `235.65 ms`, max `303.32 ms`). Candidate API and worker processes were owned and sleeping during observation; available memory was approximately `1.99 GB`, free phone storage approximately `92.7 GB`, and 85 thermal zones were observed with raw thermal values sanitized. These are isolated-candidate measurements, not production regression or improvement claims. No production stress or fault injection was performed.

## 8. Deferred isolated fault scenarios

NATS down/connected-but-unconsumed; active callback in flight; worker dead/returned; disconnected agent vs stopped supervisor; unexpected Caddy route state; PhotoPrism stopped/uninstalled; SQLite storage pressure; expired evidence; partial app dependency; code release/rollback blockers; failed post-repair verification; idempotent concurrent denial; rejected authorization; recurrence after resolution; unknown command outcome; restart-storm budget.

Do not treat process online, accepted command or an observed healthy signal as proof of a verified repair. Controlled fault injection requires separate approval and nonproduction targets.

## 9. Promotion gate

Targeted backend/frontend tests, permission/redaction checks, exact-SHA ARM64/Termux candidate identity, isolated migrations, real candidate API routes, worker/NATS projection behavior, bounded candidate resource observations, Android Chrome UI-to-candidate interaction and cleanup passed. Live PR #649 backend behavior on the installed production runtime was intentionally not activated. Deferred fault-injection scenarios and production deployment readiness remain incomplete and are not represented as passed. The former Android UI blocker was a harness gap and is now fixed; production activation remains a separate promotion/rollback safety and authorization boundary.

## 10. Backend promotion and live admission evidence

The new repository-owned backend promotion controller was qualified at `0b767dc662c8f7c37accb4bc5fbad71a5f31564f`. The deterministic artifact verified with 284 files, SHA256 sidecars, exact source SHA, Android/Termux aarch64 + PRoot Ubuntu target, schema 44 and migration checksums. The isolated phone-side run used a disposable SQLite database: backup with WAL-aware online copy, independent restore rehearsal, migrations `[43, 44]`, schema 44 integrity/quick-check/foreign-key validation, atomic pointer/database lifecycle, three consecutive simulated health observations, authorization replay rejection, health-failure rollback, write-observed fail-closed recovery and non-destructive restart reconciliation all passed. The temporary candidate cache was removed.

The same run collected a read-only live admission snapshot against the installed phone runtime. PASS: protected device identity `pocket-lab-lite-server`, schema 42, SQLite integrity/quick-check, storage, memory, battery 94%, thermal maximum 48.1°C, all required PM2 services, Caddy/FastAPI health/readiness and worker heartbeat from the existing sanitized `/api/lite/runtime` contract. BLOCKED: external runtime guardian process absent. This is a real runtime readiness condition, not a harness assertion; the guardian script exists on the phone but its process was not running. The controller correctly refused production admission with exit 3 and did not activate or stop any service.

The rollback strategy is deliberately code-and-database restore, not code-only rollback: `main` knows migrations only through 0042, so after 0043/0044 a code-only return would be unsafe. Automatic rollback after newer writes is disabled; an uncertain write boundary becomes durable manual recovery. Production activation therefore remains unperformed pending the supported guardian restoration/verification, a fresh admission snapshot, a verified production backup/restore receipt bound to the exact candidate, and a separate explicit single-use production-promotion authorization. No synthetic qualification authority can authorize this transition.

**Qualification status: DEV-PC AND ISOLATED PHYSICAL ANDROID/TERMUX BACKEND + ANDROID CHROME-TO-CANDIDATE UI QUALIFIED — BACKEND PROMOTION WORKFLOW IMPLEMENTED AND ISOLATED-QUALIFIED — PRODUCTION BACKEND ACTIVATION NOT PERFORMED; LIVE ADMISSION BLOCKED BY THE ABSENT EXTERNAL GUARDIAN. DRAFT PR REQUIRED.**
