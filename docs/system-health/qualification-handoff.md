# System Health P6 qualification plan — NOT RUN

The authoring session must not execute any command below. Execute only in a separate approved qualification session, starting from a known clean feature branch and isolated dev fixture. Never inject faults into the production server phone.

## 1. Baseline/read-only review

    git switch feat/azure-horizon-system-health-intelligence
    git status --short
    git diff main...HEAD --stat
    git diff --check

Record exact base/head, isolated environment and scenario ID. Check the branch before any new rollout.

## 2. Backend

    python3 -m py_compile pocket-lab-final-structure/runtime/api_fastapi/services/lite_system_health.py pocket-lab-final-structure/runtime/api_fastapi/routers/lite_system_health.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/backend/test_lite_system_health.py
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/backend/test_lite_api.py

Required: no DDL on GET; stable IDs; reopen generation, unknown/stale invariant, duplicate sequence, actor permission (401/403), blocked Class C actions, safe idempotent denial, migration upgrade, database concurrency, bounded retention, sanitization, NATS consumer callback ownership and single-flight. Add missing integration cases before promotion.

## 3. Frontend/mocked

    npm run test:unit -- src/lite/LiteSystemHealth.test.jsx
    VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/e2e/lite-system-health.spec.ts --project=mocked-desktop --project=mocked-mobile
    npm run build-storybook
    npm run build

Check Daylight, Black and System at 320/360/390/768/1024/1440px, 200% text, keyboard and screen reader, focus return, Escape, backdrop, chevron, shared desktop drag/resize/reset, mobile safe area, Compact/Expand, reduced motion and one haptic per supported user interaction. Verify Home and context links to System Health and canonical deep links. Compare card rhythm/spacing with the merged Apps PR #636. Confirm Fix is disabled when unqualified and no unauthorized POST is issued.

## 4. Non-disruptive Termux/ARM64 observation

Authorized same-origin GET queries only, with normal authentication; do not bypass user identity checks:

    curl -fsS http://127.0.0.1:8443/api/lite/system-health/summary | python3 -m json.tool
    pm2 status

Capture CPU, RSS, battery, thermal, SQLite WAL size, idle startup time, route readiness and backend projection age. Do not assume /tmp is writable on Termux; use the project-owned writable state temp or TMPDIR. Observe existing guardian, NATS durable consumer and supervisor without stopping a production service.

## 5. Deferred isolated fault scenarios

NATS down/connected-but-unconsumed; active callback in flight; worker dead/returned; disconnected agent vs stopped supervisor; unexpected Caddy route state; PhotoPrism stopped/uninstalled; SQLite storage pressure; expired evidence; partial app dependency; code release/rollback blockers; failed post-repair verification; idempotent concurrent denial; rejected authorization; recurrence after resolution; unknown command outcome; restart-storm budget.

Do not treat process online, accepted command or an observed healthy signal as proof of a verified repair. Controlled fault injection requires separate approval and nonproduction targets.

## 6. Promotion gate

Require passing targeted backend/frontend tests, permission and redaction audit, live runtime evidence, mobile/desktop/theme/200%-text qualification, low-power/idle budget, reconciled app/NATS ownership and rollback compatibility before PR review readiness. Record actual outputs in a separate evidence report.

**Qualification status: NOT RUN — DEFERRED.**
