from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py"
ROUTER = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
LITE_API = ROOT / "src/lib/liteApi.js"
LITE_QUERY = ROOT / "src/lib/liteQueryClient.js"
LITE_STATUS = ROOT / "src/hooks/useLiteStatus.js"
LITE_SECURITY = ROOT / "src/lite/LiteSecurity.jsx"


def test_lite_security_f3_summary_endpoint_contract():
    router = ROUTER.read_text()
    service = SERVICE.read_text()

    assert '@router.get("/security/summary")' in router
    assert "def get_lite_security_summary" in router
    assert "lite_security.summary_state()" in router
    assert "lite_app_profiles.app_security_profiles()" not in router.partition('def get_lite_security_summary')[2].partition('@router.get("/security")')[0]
    assert "lite_app_lifecycle.app_lifecycle_profiles()" not in router.partition('def get_lite_security_summary')[2].partition('@router.get("/security")')[0]

    assert "def summary_state() -> dict[str, Any]:" in service
    assert "def _security_summary_from_state" in service
    assert "_SECURITY_SUMMARY_CACHE" in service
    assert "security-summary-f3-v1" in service
    assert '"details_endpoint": "/api/lite/security"' in service
    assert '"summary_payload": True' in service


def test_lite_security_f3_summary_is_compact_and_bounded():
    service = SERVICE.read_text()
    summary_func = service.partition("def _security_summary_from_state")[2].partition("def _get_security_summary_cache")[0]

    assert "_SECURITY_SUMMARY_HISTORY_LIMIT" in service
    assert "_SECURITY_SUMMARY_FINDING_LIMIT" in service
    assert "raw_history[:_SECURITY_SUMMARY_HISTORY_LIMIT]" in summary_func
    assert "critical[:_SECURITY_SUMMARY_FINDING_LIMIT]" in summary_func
    assert "findings[:_SECURITY_SUMMARY_FINDING_LIMIT]" in summary_func
    assert "evidence_refs[:5]" in summary_func
    assert "app_security_profiles" not in summary_func
    assert "app_lifecycle_profiles" not in summary_func
    assert "lite_app_profiles" not in summary_func
    assert "lite_app_lifecycle" not in summary_func


def test_lite_security_f3_frontend_uses_summary_for_initial_render_and_full_for_details():
    api = LITE_API.read_text()
    query = LITE_QUERY.read_text()
    status = LITE_STATUS.read_text()
    screen = LITE_SECURITY.read_text()

    assert "security: safeGet('/api/lite/security/summary')" in api
    assert "securitySummary: safeGet('/api/lite/security/summary')" in api
    assert "securityDetails: safeGet('/api/lite/security')" in api
    assert "securityDetails: () => ['lite', 'security', 'details']" in query
    assert "securityDetails: '/api/lite/security'" in query
    assert "liteQueryPaths.securityDetails" in status
    assert "useLiteResource(liteApi.securitySummary || liteApi.security" in screen
    assert "useLiteResource(liteApi.securityDetails || liteApi.security" in screen
    assert "const shouldLoadSecurityDetails = securityManageOpen || Boolean(activeSecurityDetails);" in screen
    assert "enabled: shouldLoadSecurityDetails" in screen
    assert "const data = securityDetailsData || securitySummaryData;" in screen
    assert "liteQueryKeys.securityDetails()" in screen


def test_lite_security_f3_preserves_backend_owned_security_boundaries():
    screen = LITE_SECURITY.read_text()
    api = LITE_API.read_text()

    assert "nats.connect" not in screen
    assert "child_process" not in screen
    assert "lynis" not in api.lower()
    assert "trivy" not in api.lower()
    assert "securityDetails: safeGet('/api/lite/security')" in api

SECURITY_PRELOAD = ROOT / "src/lite/security/securityPreload.js"
LITE_APP = ROOT / "src/lite/LiteApp.jsx"
LITE_QUERY_HOOK = ROOT / "src/hooks/useLiteQuery.js"
LITE_SNAPSHOTS = ROOT / "src/lib/liteSafeSnapshots.js"
LITE_UI = ROOT / "src/lite/LiteUi.jsx"


def test_lite_security_group1_f4_f5_summary_stale_while_revalidate_contract():
    hook = LITE_QUERY_HOOK.read_text()
    screen = LITE_SECURITY.read_text()
    preload = SECURITY_PRELOAD.read_text()
    snapshots = LITE_SNAPSHOTS.read_text()

    assert "gcTime," in hook
    assert "placeholderData" in hook
    assert "refetchOnReconnect" in hook
    assert "'/api/lite/security/summary'" in snapshots
    assert "SECURITY_SNAPSHOT_ENDPOINTS.has(normalizeLiteSnapshotPath(sourcePath))" in snapshots
    assert "readSecurityCompositeSnapshot(normalizedPath)" in snapshots

    assert "useLiteResource(liteApi.securitySummary || liteApi.security" in screen
    assert "useLiteResource(liteApi.securityDetails || liteApi.security" in screen
    assert "enabled: shouldLoadSecurityDetails" in screen
    assert "placeholderData: (previousData) => previousData" in screen
    assert "staleTime: (query) => securitySummaryStaleTime(query?.state?.data)" in screen
    assert "gcTime: SECURITY_SUMMARY_GC_TIME_MS" in screen
    assert "refetchOnWindowFocus: false" in screen
    assert "refetchOnReconnect: true" in screen
    assert "Refreshing quietly…" in screen
    assert "Fresh just now" in screen
    assert "Showing saved state" in screen

    assert "SECURITY_SUMMARY_IDLE_STALE_TIME_MS = 180_000" in preload
    assert "SECURITY_SUMMARY_ACTIVE_STALE_TIME_MS = 2_000" in preload
    assert "SECURITY_SUMMARY_GC_TIME_MS = 45 * 60_000" in preload


def test_lite_security_group1_f6_prefetch_is_guarded_and_summary_first():
    app = LITE_APP.read_text()
    preload = SECURITY_PRELOAD.read_text()

    assert "prefetchSecuritySummary" in app
    assert "SECURITY_PREFETCH_SETTLE_MS" in app
    assert "active === 'security'" in app
    assert "warmSecurityOnNavIntent" in app
    assert "onPointerEnter={() => warmSecurityOnNavIntent(item.id)}" in app
    assert "onFocus={() => warmSecurityOnNavIntent(item.id)}" in app
    assert "onTouchStart={() => warmSecurityOnNavIntent(item.id)}" in app

    assert "navigator.onLine" in preload
    assert "connection.saveData" in preload
    assert "connection.effectiveType" in preload
    assert "document.visibilityState !== 'hidden'" in preload
    assert "navigator.getBattery" in preload
    assert "activeScan" in preload
    assert "queryKey: liteQueryKeys.security()" in preload
    assert "queryFn: liteApi.securitySummary" in preload
    assert "queryFn: liteApi.securityDetails" in preload


def test_lite_security_group1_f13_lazy_preload_contract():
    screen = LITE_SECURITY.read_text()
    preload = SECURITY_PRELOAD.read_text()
    ui = LITE_UI.read_text()

    assert "preloadSecurityDetails" in preload
    assert "import('./SecurityProgressiveDetailsLazy.jsx')" in preload
    assert "preloadSecurityHistory" in preload
    assert "import('./SecurityHistoryLazy.jsx')" in preload
    assert "import('../components/LiteHistorySection.jsx')" in preload
    assert "preloadSecurityManageChunks" in preload
    assert "prefetchSecurityManageOnIntent" in preload

    assert "warmSecurityManageIntent" in screen
    assert "onPointerEnter={warmSecurityManageIntent}" in screen
    assert "onFocus={warmSecurityManageIntent}" in screen
    assert "onTouchStart={warmSecurityManageIntent}" in screen
    assert "if (type === 'history') preloadSecurityHistory();" in screen
    assert "preloadSecurityDetails();" in screen
    assert "chooseSecurityManageSection" in screen
    assert "preloadSecurityManageChunks();" in screen

    assert "...buttonProps" in ui


def test_lite_security_group1_preserves_frontend_boundaries():
    combined = "\n".join([
        LITE_SECURITY.read_text(),
        SECURITY_PRELOAD.read_text(),
        LITE_APP.read_text(),
        LITE_QUERY_HOOK.read_text(),
        LITE_API.read_text(),
    ])

    assert "/api/lite/security/summary" in combined
    assert "liteApi.securityDetails" in combined
    assert "fetch(" not in LITE_SECURITY.read_text()
    assert "window.fetch(" not in SECURITY_PRELOAD.read_text()
    assert "globalThis.fetch(" not in SECURITY_PRELOAD.read_text()
    assert "nats.connect" not in combined
    assert "child_process" not in combined
    assert "exec(" not in combined
    assert "spawn(" not in combined
    assert "BaseHTTPRequestHandler" not in combined
    assert "/api/action/update" not in combined
