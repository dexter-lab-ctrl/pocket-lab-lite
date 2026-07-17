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


def _prepare_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
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


def test_security_f11_events_route_exists_and_returns_sse_headers(tmp_path, monkeypatch):
    _prepare_state(tmp_path, monkeypatch)
    _queue_security_run()

    from api_fastapi.services import lite_security
    from api_fastapi.routers.lite import _security_sse_payload

    plan = lite_security.security_event_replay(None)
    payload = plan["events"][0]
    frame = _security_sse_payload(payload)
    router = ROUTER.read_text()
    assert '@router.get("/security/events")' in router
    assert 'media_type="text/event-stream"' in router
    assert '"Cache-Control": "no-cache"' in router
    assert '"Connection": "keep-alive"' in router
    assert '"X-Accel-Buffering": "no"' in router
    assert payload["type"] == "security.scan.snapshot"
    assert payload["snapshot"] is True
    assert isinstance(payload["event_id"], int)
    assert f"id: {payload['event_id']}" in frame
    assert len(frame) < 2500


def test_security_f11_progress_event_shape_is_sanitized_and_bounded(tmp_path, monkeypatch):
    _prepare_state(tmp_path, monkeypatch)
    _queue_security_run()

    from api_fastapi.services import lite_security

    event = lite_security.security_progress_event()
    assert event["type"] == "security.scan.snapshot"
    assert event["run_id"] == "security-f11-run"
    assert event["profile"] == "quick"
    assert event["active_scan"] is True
    assert 0 <= event["percent"] <= 100
    assert event["event_id"] > 0
    assert event["snapshot"] is True
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



def test_security_f11_progress_fallback_endpoint_remains_tiny(tmp_path, monkeypatch):
    _prepare_state(tmp_path, monkeypatch)
    _queue_security_run()

    response = client().get("/api/lite/security/progress")
    assert response.status_code == 200
    payload = response.json()
    assert payload["view_model"] == "security-progress-f7-v1"
    assert payload["revision"].startswith(("security-progress-", "security-sqlite-progress-"))
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
    assert 'await asyncio.sleep(active_poll_seconds if active_scan else idle_poll_seconds)' in router
    assert 'security_event_replay(' in router
    assert 'list_security_progress_events_after' in router

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
    assert 'current_state()' not in router.partition('async def _security_events_generator')[2].partition('class LiteCatalogInstallRequest')[0]



def test_security_f11_frontend_uses_eventsource_with_bounded_progress_fallback():
    hook = SECURITY_EVENTS_HOOK.read_text()
    query = LITE_QUERY.read_text()
    security = LITE_SECURITY.read_text()
    api = LITE_API.read_text()
    status = LITE_STATUS.read_text()

    assert "new window.EventSource(endpoint(SECURITY_EVENTS_PATH))" in hook
    assert "SECURITY_EVENTS_PATH = '/api/lite/security/events'" in hook
    assert "liteApi.securityProgress()" in hook
    assert "SECURITY_PROGRESS_FALLBACK_MS = 3000" in hook
    assert "setFallbackActive(false)" in hook
    assert "terminalSecurityProgress(payload)" in hook
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
    assert "selectLiveSecurityProgress(result?.scan_progress, liveSecurityProgressData, data?.scan_progress, activeSecurityRunId)" in security
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


def test_security_group7_hotfix_keeps_live_scan_out_of_saved_state_reconnect_ui():
    security = LITE_SECURITY.read_text()
    hook = SECURITY_EVENTS_HOOK.read_text()

    assert "forceFallback: shouldLoadSecurityProgress" in security
    assert "savedStateOnly: savedStateOnly && !scanInProgress" in security
    assert "const savedSecurityDetails = !scanInProgress" in security
    assert "const effectiveBackendReachable = backendReachable !== false || scanInProgress" in security
    assert "securityFlow.writeBlocked ? 'Reconnect'" in security
    assert "scanInProgress && profile.id === latestScanProfile ? profile.running" in security
    assert "profile.running : 'Wait'" not in security
    assert "forceFallback = false" in hook
    assert "(!fallbackActive && !forceFallback)" in hook
    assert "SECURITY_PROGRESS_FALLBACK_MS = 3000" in hook


def test_security_group7_hotfix_uses_calm_progress_language_without_fake_short_eta():
    security = LITE_SECURITY.read_text()
    lite_ui = (ROOT / "src/lite/LiteUi.jsx").read_text()

    assert "estimated_total_seconds: profileId === 'app' ? 120 : 900" in security
    assert "const scanProgressStatusText" in security
    assert "{scanProgressPercent}% · {scanProgressStatusText} · {activeProfileMeta.label} is working." in security
    assert "progress?.estimated_total_seconds || 900" in lite_ui
    assert "eta: 'working'" in lite_ui
    assert "const scanProgressStatusText = ['complete', 'completed'].includes" in security
    assert "${scanProgressEta} remaining" not in security
    assert "status === 'accepted'" in lite_ui


def test_security_group7_hotfix_prefers_live_progress_over_stale_optimistic_result():
    security = LITE_SECURITY.read_text()

    assert "function selectLiveSecurityProgress" in security
    assert "securityProgressData" in security
    assert "const scanProgress = activeProfileIsLatest ? selectLiveSecurityProgress(result?.scan_progress, liveSecurityProgressData, data?.scan_progress, activeSecurityRunId) : null;" in security
    assert "acceptSecurityProgressEvent(accepted, candidate)" in security
    assert "if (decision.accepted) accepted = decision.value" in security



def test_security_group7c_progress_fallback_stays_alive_for_active_local_run():
    hook = SECURITY_EVENTS_HOOK.read_text()
    security = LITE_SECURITY.read_text()

    assert "activeRunId = ''" in hook
    assert "localActive = false" in hook
    assert "shouldKeepSecurityFallbackAlive" in hook
    assert "securityEventMatchesActiveRun" in hook
    assert "keepFallbackAlive" in hook
    assert "setFallbackActive(true)" in hook
    assert "activeRunId: activeSecurityProgressRunId" in security
    assert "localActive: localSecurityProgressActive" in security


def test_security_group7c_live_progress_render_binding_is_run_scoped():
    security = LITE_SECURITY.read_text()

    assert "function selectLiveSecurityProgress(resultProgress = null, liveProgress = null, fallbackProgress = null, expectedRunId = '')" in security
    assert "const expectedRun = securityProgressRunKey(expectedRunId)" in security
    assert "const candidates = [resultProgress, fallbackProgress, liveProgress].filter(Boolean)" in security
    assert "acceptSecurityProgressEvent" in security
    assert "securityProgressData" in security
    assert "liveSecurityProgressData" in security
    assert "const activeSecurityRunId" in security
    assert "selectLiveSecurityProgress(result?.scan_progress, liveSecurityProgressData, data?.scan_progress, activeSecurityRunId)" in security


def test_security_group7c_frontend_blocks_duplicate_scan_submits():
    security = LITE_SECURITY.read_text()

    assert "securityScanSubmitGuardRef" in security
    assert "function securityScanAlreadyRunning" in security
    assert "function blockDuplicateSecurityScan" in security
    assert "A safety check is already running. Wait for it to finish before starting another one." in security
    assert "if (securityScanAlreadyRunning()) { blockDuplicateSecurityScan(); return; }" in security
    assert "securityScanSubmitGuardRef.current = true" in security
    assert "securityScanSubmitGuardRef.current = false" in security


def test_security_group7c_backend_dedupes_active_security_scan(tmp_path, monkeypatch):
    _prepare_state(tmp_path, monkeypatch)
    _queue_security_run(run_id="security-active-7c", profile="quick")

    response = client().post("/api/lite/security/check", json={"profile": "quick"})
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["duplicate"] is True
    assert payload["already_running"] is True
    assert payload["run_id"] == "security-active-7c"
    assert payload["scan_profile"] == "quick"
    assert payload.get("scan_progress", {"active_scan": True})["active_scan"] is True


def test_security_group7c_no_caddy_restart_patch_needed_for_sse_client_cancel():
    # Caddy log evidence showed EventSource client cancellation and SIGINT restarts,
    # not a Caddyfile defect. Group 7C keeps the UI resilient with fallback polling
    # instead of changing proxy topology.
    hook = SECURITY_EVENTS_HOOK.read_text()
    assert "shouldKeepSecurityFallbackAlive" in hook
    assert "SECURITY_PROGRESS_FALLBACK_MS = 3000" in hook
