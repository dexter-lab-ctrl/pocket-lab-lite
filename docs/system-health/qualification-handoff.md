# System Health P6 qualification handoff — executed with bounded evidence

This handoff records the approved qualification session for PR #649. Final feature SHA: `fce2c643eff02fab996a8583f3a6ac74541d80d5`; base SHA: `cfd4194fd338aeae07580fa7f227d118bebdd907`. Qualification used an isolated DEV-PC candidate and repository fixtures. The Server Phone remained consumer-only: no source edits, commits, pushes, fault injection or PR #649 backend installation were performed.

## 1. Baseline/read-only review

    git switch feat/azure-horizon-system-health-intelligence
    git status --short
    git diff origin/main...HEAD --stat
    git diff --check

Recorded exact base/head, local/remote parity, clean branch transitions and candidate manifest identity. No rollout was performed.

## 2. Backend

    .venv/bin/python -m py_compile pocket-lab-final-structure/runtime/api_fastapi/services/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/routers/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3b_projections.py pocket-lab-final-structure/runtime/api_fastapi/services/lite_phase3c_projections.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_system_health.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_api.py

Result: py_compile passed; System Health tests passed (9); Lite API tests passed (336). Additional migration, SQLite, authorization, security, identity, harness and tooling suites passed in the recorded DEV-PC run. The isolated route probe verified migration count 44, authenticated reads, diagnosis persistence, CSRF/session expiry, generation fencing, idempotent blocked repair and sanitized evidence. Local NATS lifespan startup was not claimed because `nats-server` is not installed; the repository isolated-runtime CI check remained a separate exact-head evidence source.

## 3. Frontend/mocked

    npm run test:unit -- src/lite/LiteSystemHealth.test.jsx
    VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
    npm run build-storybook
    npm run build

Result: 6 focused unit tests, 10 System Health Playwright tests, full unit 624 tests, Storybook build and production build passed. Mocked accessibility, themes, context links, focus return, mobile snap and disabled repair were exercised. Canonical Home desktop/mobile snapshots were regenerated only for Home after physical validation and Home comparison passed. Hardware haptic actuation was not independently measurable through CDP.

## 4. Non-disruptive Termux/ARM64 observation

Authorized same-origin, bounded read-only observation used the existing normal runtime identity; no bypass was used:

    curl -fsS http://127.0.0.1:8443/api/lite/system-health/summary | python3 -m json.tool
    pm2 status

Result: Caddy, FastAPI readiness/status, NATS monitor/JetStream, PM2 core services and the main checkout were healthy. The installed backend returned 404 for `/api/lite/system-health/`, so it was not represented as PR #649 backend evidence. Detailed battery/thermal/WAL trend and live System Health runtime metrics remain deferred; no service was stopped or mutated.

## 5. Android Chrome candidate qualification

The Windows standard-user ADB/CDP path was reused without UAC elevation. The selected Android Chrome target reported Chrome `156.0.8078.79`, CDP `1.3`, package `com.android.chrome`; the WSL localhost relay and Playwright attach passed. The exact candidate manifest and page response/header matched `fce2c643eff02fab996a8583f3a6ac74541d80d5`.

The narrow System Health UI qualifier passed 10/10 checks: attention, diagnosis, disabled repair with zero repair POSTs, focus restoration, Compact/Expand, healthy/stale/unknown, Daylight/Black/System, deep link, Home navigation, reduced motion and simulated 200% layout safety. API responses were repository MSW fixtures; the installed phone backend remained separately identified.

The Home-only performance candidate ran 18 reports at the exact SHA. Three baseline repetitions ran 18 reports each. Absolute targets remained red; final normalized attribution was `MIXED=18`, `APP_INCREMENTAL_COST=0`. The broad seven-screen workflow was not run. No unrelated optimization was made.

## 6. Deferred isolated fault scenarios

NATS down/connected-but-unconsumed; active callback in flight; worker dead/returned; disconnected agent vs stopped supervisor; unexpected Caddy route state; PhotoPrism stopped/uninstalled; SQLite storage pressure; expired evidence; partial app dependency; code release/rollback blockers; failed post-repair verification; idempotent concurrent denial; rejected authorization; recurrence after resolution; unknown command outcome; restart-storm budget.

Do not treat process online, accepted command or an observed healthy signal as proof of a verified repair. Controlled fault injection requires separate approval and nonproduction targets.

## 7. Promotion gate

Targeted backend/frontend tests, permission/redaction checks, candidate identity, mocked UI and narrow physical Android UI qualification passed. Live PR #649 backend behavior on the installed Server Phone, detailed low-power trend evidence and deferred fault-injection scenarios remain incomplete and are not represented as passed.

**Qualification status: DEV-PC AND PHYSICAL ANDROID UI QUALIFIED — INSTALLED PHONE BACKEND AND DEFERRED RUNTIME SCENARIOS PARTIAL/BLOCKED BY SCOPE. DRAFT PR REQUIRED.**
