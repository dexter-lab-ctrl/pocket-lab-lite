from pathlib import Path
import json

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
SERVICE = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py"
LITE_API = ROOT / "src/lib/liteApi.js"
LITE_QUERY = ROOT / "src/lib/liteQueryClient.js"
LITE_STATUS = ROOT / "src/hooks/useLiteStatus.js"
LITE_SECURITY = ROOT / "src/lite/LiteSecurity.jsx"
SECURITY_EVENTS_HOOK = ROOT / "src/hooks/useLiteSecurityEvents.js"


def _prepare_state(tmp_path):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    return state


def _queue_security_run(run_id="security-f11-run", profile="quick"):
    from api_fastapi.services import lite_security

    return lite_security.record_queued_run(
        {
            "run_id": run_id,
            "command_id": run_id,
            "profile": profile,
            "scope": "local",
            "reason": "f11 contract test",
            "requested_at": "2026-07-09T00:00:00+00:00",
        }
    )


def _parse_first_sse_event(text):
    data_lines = [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: ")]
    assert data_lines, text
    return json.loads(data_lines[0])


def test_security_f11_events_route_exists_and_returns_sse_headers(tmp_path):
    _prepare_state(tmp_path)

    response = client().get("/api/lite/security/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers.get("cache-control") == "no-cache"
    payload = _parse_first_sse_event(response.text)

    assert payload["type"] in {"security.scan.heartbeat", "security.scan.completed"}
    assert payload["revision"].startswith("security-progress-")
    assert payload["progress_revision"].startswith("security-progress-")
    assert payload["summary_revision"].startswith("security-summary-")
    assert payload["history_revision"].startswith("security-history-")
    assert set(payload).issubset(
        {
            "type",
            "run_id",
            "profile",
            "app_id",
            "stage",
            "percent",
            "message",
            "status",
            "revision",
            "updated_at",
            "active_scan",
            "summary_revision",
            "profile_revision",
            "history_revision",
            "progress_revision",
        }
    )
    assert len(response.text) < 2500



def test_security_f11_progress_event_shape_is_sanitized_and_bounded(tmp_path):
    _prepare_state(tmp_path)
    _queue_security_run()

    from api_fastapi.services import lite_security

    event = lite_security.security_progress_event()
    assert event["type"] == "security.scan.queued"
    assert event["run_id"] == "security-f11-run"
    assert event["profile"] == "quick"
    assert event["active_scan"] is True
    assert 0 <= event["percent"] <= 100
    assert event["revision"].startswith("security-progress-")
    assert event["profile_revision"].startswith("security-profile-quick-")
    assert "findings" not in event
    assert "evidence_refs" not in event
    assert "raw_output" not in event
    assert len(str(event)) < 1500

    forbidden = "\n".join(str(value) for value in event.values()).lower()
    for term in (
        "password",
        "api_key",
        "private key",
        "nats://",
        "authorization:",
        "stdout",
        "stderr",
        "/data/data/",
        "/storage/emulated/",
        "photoprism_admin_password",
        "restic_password",
        "vault_token",
    ):
        assert term not in forbidden



def test_security_f11_progress_fallback_endpoint_remains_tiny(tmp_path):
    _prepare_state(tmp_path)
    _queue_security_run()

    response = client().get("/api/lite/security/progress")
    assert response.status_code == 200
    payload = response.json()
    assert payload["view_model"] == "security-progress-f7-v1"
    assert payload["revision"].startswith("security-progress-")
    assert payload["active_scan"] is True
    assert "findings" not in payload
    assert "evidence_refs" not in payload
    assert len(response.text) < 1500



def test_security_f11_backend_source_contract():
    router = ROUTER.read_text()
    service = SERVICE.read_text()

    assert '@router.get("/security/events")' in router
    assert "StreamingResponse" in router
    assert 'media_type="text/event-stream"' in router
    assert '"Cache-Control": "no-cache"' in router
    assert '_security_events_generator' in router
    assert 'request.is_disconnected()' in router
    assert 'await asyncio.sleep(1.5)' in router
    assert 'security_progress_event()' in router
    assert 'security_progress_event_fingerprint' in router

    assert 'split_progress_state()' in service
    assert 'split_freshness_state()' in service
    assert '_SECURITY_STREAM_ALLOWED_FIELDS' in service
    assert 'policy.redact_value' in service
    assert 'security.scan.progress' in service
    assert 'security.scan.completed' in service
    assert 'security.scan.failed' in service
    assert 'security.scan.cancelled' in service
    assert 'security.scan.heartbeat' in service
    assert 'read_evidence_summary' not in service.partition('def security_progress_event')[2].partition('def security_progress_event_fingerprint')[0]
    assert 'current_state()' not in router.partition('async def _security_events_generator')[2].partition('@router.get("/security/events")')[0]



def test_security_f11_frontend_uses_eventsource_with_bounded_progress_fallback():
    hook = SECURITY_EVENTS_HOOK.read_text()
    query = LITE_QUERY.read_text()
    security = LITE_SECURITY.read_text()
    api = LITE_API.read_text()
    status = LITE_STATUS.read_text()

    assert "new window.EventSource(endpoint(SECURITY_EVENTS_PATH))" in hook
    assert "SECURITY_EVENTS_PATH = '/api/lite/security/events'" in hook
    assert "liteApi.securityProgress()" in hook
    assert "SECURITY_PROGRESS_FALLBACK_MS = 4000" in hook
    assert "setFallbackActive(false)" in hook
    assert "terminalSecurityEvent(event)" in hook
    assert "liteQueryKeys.securityProgress()" in hook
    assert "liteQueryKeys.securityFreshness()" in hook
    assert "liteQueryKeys.securityProfile(profile)" in hook
    assert "liteQueryKeys.securityHistory(historyLimit" in hook
    assert "liteQueryKeys.fleet" not in hook
    assert "liteQueryKeys.recovery" not in hook
    assert "liteQueryKeys.catalog" not in hook

    assert "securityEvents: '/api/lite/security/events'" in query
    assert "securityEvents: () => ['lite', 'security', 'events']" in query
    assert "useLiteSecurityEvents" in security
    assert "shouldUseSecurityProgressStream" in security
    assert "pollingMode: 'fast'" not in security.partition("shouldUseSecurityProgressStream")[2].partition("const splitSecurityData")[0]
    assert "safeGet('/api/lite/security')" in api  # full fallback still exists
    assert "securityDetails" in status



def test_security_f11_frontend_execution_boundaries_are_preserved():
    combined = "\n".join(
        [
            LITE_API.read_text(),
            SECURITY_EVENTS_HOOK.read_text(),
            LITE_SECURITY.read_text(),
        ]
    ).lower()

    assert "/api/lite/security/summary" in combined
    assert "/api/lite/security/events" in combined
    assert "/api/lite/security/progress" in combined
    assert "eventsource" in combined
    assert "nats.connect" not in combined
    assert "jetstream" not in combined
    assert "child_process" not in combined
    assert "exec(" not in combined
    assert "spawn(" not in combined
    assert "lynis" not in SECURITY_EVENTS_HOOK.read_text().lower()
    assert "trivy" not in SECURITY_EVENTS_HOOK.read_text().lower()



def test_security_group7_frontend_instant_feedback_and_quiet_result_notice_contract():
    security = LITE_SECURITY.read_text()
    lite_ui = (ROOT / "src/lite/LiteUi.jsx").read_text()

    assert "createOptimisticSecurityResult" in security
    assert "Getting ready" in security
    assert "Pocket Lab is starting the safety check." in security
    assert "mergeSecurityAcceptedResult" in security
    assert "hasOptimisticSecurityProgress(result)" in security
    assert "result?.scan_progress || data?.scan_progress" in security
    assert "<ResultNotice result={null} error={actionError} />" in security
    assert "<ResultNotice result={result} error={actionError} />" not in security
    assert "Request sent safely" in lite_ui  # generic notice remains available outside Security


def test_security_group7_cross_tab_completion_broadcast_is_sanitized_and_focused():
    hook = SECURITY_EVENTS_HOOK.read_text()
    snapshots = (ROOT / "src/lib/liteSafeSnapshots.js").read_text()

    assert "export function broadcastLiteSecurityScanCompleted" in snapshots
    assert "LITE_SECURITY_SCAN_BROADCAST_CHANNEL" in snapshots
    assert "LITE_SECURITY_SCAN_COMPLETED_EVENT" in snapshots
    assert "type: LITE_SECURITY_SCAN_COMPLETED_EVENT" in snapshots
    assert "profile," in snapshots
    assert "run_id:" in snapshots
    assert "completed_at:" in snapshots
    assert "status:" in snapshots
    assert "findings" not in snapshots.partition("function sanitizeSecurityScanCompletedPayload")[2].partition("export function subscribeLiteSecurityScanCompleted")[0]
    assert "evidence_refs" not in snapshots.partition("function sanitizeSecurityScanCompletedPayload")[2].partition("export function subscribeLiteSecurityScanCompleted")[0]
    assert "raw_output" not in snapshots.partition("function sanitizeSecurityScanCompletedPayload")[2].partition("export function subscribeLiteSecurityScanCompleted")[0]

    assert "broadcastLiteSecurityScanCompleted" in hook
    assert "source: 'security-events-stream'" in hook
    assert "liteQueryKeys.securityProfile(profile)" in hook
    assert "liteQueryKeys.securityHistory(historyLimit" in hook
    assert "liteQueryKeys.catalog" not in hook
    assert "liteQueryKeys.fleet" not in hook
    assert "liteQueryKeys.recovery" not in hook
