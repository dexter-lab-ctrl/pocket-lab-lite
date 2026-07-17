from pathlib import Path

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
SERVICE = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py"
LITE_API = ROOT / "src/lib/liteApi.js"
LITE_QUERY_HOOK = ROOT / "src/hooks/useLiteQuery.js"
LITE_QUERY = ROOT / "src/lib/liteQueryClient.js"
LITE_STATUS = ROOT / "src/hooks/useLiteStatus.js"
LITE_SECURITY = ROOT / "src/lite/LiteSecurity.jsx"


def _prepare_state(tmp_path):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    return state


def _queue_security_run(run_id="security-f9-run", profile="quick"):
    from api_fastapi.services import lite_security

    return lite_security.record_queued_run(
        {
            "run_id": run_id,
            "command_id": run_id,
            "profile": profile,
            "scope": "local",
            "reason": "f9 contract test",
            "requested_at": "2026-07-09T00:00:00+00:00",
        }
    )


def _assert_etag_response(http, path):
    response = http.get(path)
    assert response.status_code == 200
    etag = response.headers.get("etag")
    assert etag and etag.startswith('"security-') and etag.endswith('"')
    assert response.headers.get("cache-control") == "no-cache"
    payload = response.json()
    assert payload["revision"].startswith("security-")
    assert payload.get("source")

    unchanged = http.get(path, headers={"If-None-Match": etag})
    assert unchanged.status_code == 304
    assert unchanged.content == b""
    assert unchanged.headers.get("etag") == etag
    assert unchanged.headers.get("cache-control") == "no-cache"
    return etag


def test_security_f9_freshness_is_tiny_revision_aware_and_conditional(tmp_path):
    _prepare_state(tmp_path)
    _queue_security_run()

    http = client()
    etag = _assert_etag_response(http, "/api/lite/security/freshness")
    payload = http.get("/api/lite/security/freshness").json()

    assert payload["view_model"] == "security-freshness-f9-v1"
    assert payload["summary_endpoint"] == "/api/lite/security/summary"
    assert payload["details_endpoint"] == "/api/lite/security"
    assert set(payload["profile_revisions"]) == {"quick", "full", "app"}
    assert payload["summary_revision"].startswith("security-summary-")
    assert payload["history_revision"].startswith("security-history-")
    assert payload["progress_revision"].startswith("security-progress-")
    assert "history" not in payload
    assert "findings" not in payload
    assert "critical_issues" not in payload
    assert len(str(payload)) < 2000

    _queue_security_run("security-f9-run-new")
    changed = http.get("/api/lite/security/freshness", headers={"If-None-Match": etag})
    assert changed.status_code == 200
    assert changed.headers.get("etag") != etag
    assert changed.json()["revision"].startswith("security-")


def test_security_f9_compact_endpoints_return_etag_and_304(tmp_path):
    _prepare_state(tmp_path)
    _queue_security_run()

    http = client()
    for path in (
        "/api/lite/security/summary",
        "/api/lite/security/profiles/quick",
        "/api/lite/security/profiles/full",
        "/api/lite/security/profiles/app?app_id=photoprism",
        "/api/lite/security/history?limit=20",
        "/api/lite/security/progress",
        "/api/lite/security/details/security-f9-run",
        "/api/lite/security/evidence/security-f9-run/summary",
    ):
        _assert_etag_response(http, path)


def test_security_f9_profile_history_and_progress_revisions_are_bounded(tmp_path):
    _prepare_state(tmp_path)
    _queue_security_run()

    http = client()
    quick = http.get("/api/lite/security/profiles/quick").json()
    full = http.get("/api/lite/security/profiles/full").json()
    history = http.get("/api/lite/security/history?limit=20").json()
    progress = http.get("/api/lite/security/progress").json()

    assert quick["revision"].startswith("security-profile-quick-")
    assert full["revision"].startswith("security-profile-full-")
    assert quick["revision"] != full["revision"]
    assert history["revision"].startswith("security-history-")
    assert len(history["history"]) <= 20
    assert progress["revision"].startswith("security-progress-")
    assert "findings" not in progress
    assert len(str(progress)) < 1200


def test_security_f9_backend_source_contract():
    router = ROUTER.read_text()
    service = SERVICE.read_text()

    assert "_security_compact_response" in router
    assert "If-None-Match" not in router  # uses lowercase ASGI header lookup
    assert 'request.headers.get("if-none-match")' in router
    assert "Response(status_code=304" in router
    assert "JSONResponse(content=payload" in router
    assert '"Cache-Control": "no-cache"' in router
    assert "compact_response_etag" in service
    assert "if_none_match_matches" in service
    assert "hashlib.sha256" in service
    assert "_profile_revision" in service
    assert "_history_revision" in service
    assert "_progress_revision" in service
    assert "security-freshness-f9-v1" in service


def test_security_f9_frontend_handles_304_without_clearing_previous_data():
    api = LITE_API.read_text()
    hook = LITE_QUERY_HOOK.read_text()
    query = LITE_QUERY.read_text()
    status = LITE_STATUS.read_text()
    screen = LITE_SECURITY.read_text()

    assert "If-None-Match" in api
    assert "response.status === 304" in api
    assert "__liteNotModified" in api
    assert "isLiteNotModified" in api
    assert "conditionalGet('/api/lite/security/summary')" in api
    assert "securityFreshness: conditionalGet('/api/lite/security/freshness')" in api
    assert "conditionalRead(`/api/lite/security/profiles/" in api
    assert "conditionalRead(`/api/lite/security/history" in api
    assert "conditionalRead('/api/lite/security/progress')" in api

    assert "useQueryClient" in hook
    assert "queryClient.getQueryData(resolvedQueryKey)" in hook
    assert "if (!isLiteNotModified(data)) {" in hook
    assert "writeLiteSnapshot(path" in hook
    assert "isLiteNotModified(data)" in hook

    assert "securityFreshness: () => ['lite', 'security', 'freshness']" in query
    assert "securityProfile: (profile = 'quick', appId = '')" in query
    assert "securityHistory: (limit = 20)" in query
    assert "securityHistoryPage: (limit = 20, cursor = '')" in query
    assert "securityProgress: '/api/lite/security/progress'" in query
    assert "securityFreshness" in status

    assert "securityFreshnessData" in screen
    assert "lastSecurityFreshnessRef" in screen
    assert "previous.summary_revision !== securityFreshnessData.summary_revision" in screen
    assert "previousProfiles[profile] !== currentProfiles[profile]" in screen
    assert "liteQueryKeys.securityProgress()" in screen
    assert "liteQueryKeys.fleet" not in screen.partition("lastSecurityFreshnessRef")[2].partition("const [evidence")[0]
    assert "liteQueryKeys.recovery" not in screen.partition("lastSecurityFreshnessRef")[2].partition("const [evidence")[0]
    assert "liteQueryKeys.catalog" not in screen.partition("lastSecurityFreshnessRef")[2].partition("const [evidence")[0]


def test_security_f9_preserves_frontend_execution_boundaries():
    combined = "\n".join([
        LITE_API.read_text(),
        LITE_QUERY_HOOK.read_text(),
        LITE_SECURITY.read_text(),
    ]).lower()

    assert "/api/lite/security/summary" in combined
    assert "/api/lite/security/freshness" in combined
    assert "/api/lite/security/profiles" in combined
    assert "nats.connect" not in combined
    assert "child_process" not in combined
    assert "exec(" not in combined
    assert "spawn(" not in combined
    assert "lynis" not in LITE_API.read_text().lower()
    assert "trivy" not in LITE_API.read_text().lower()
