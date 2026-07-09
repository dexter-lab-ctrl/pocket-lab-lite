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
