from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REDUCER = ROOT / "src/lib/securityProgressEvents.js"
REDUCER_TEST = ROOT / "src/lib/securityProgressEvents.test.js"
HOOK = ROOT / "src/hooks/useLiteSecurityEvents.js"
SCREEN = ROOT / "src/lite/LiteSecurity.jsx"
DIAGNOSTICS = ROOT / "src/lib/liteLifecycleDiagnostics.js"
CADDY = (
    ROOT
    / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh"
)
MAIN = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/main.py"


def test_s6_frontend_has_one_canonical_event_acceptance_reducer():
    reducer = REDUCER.read_text()
    screen = SCREEN.read_text()
    hook = HOOK.read_text()
    assert "export function acceptSecurityProgressEvent" in reducer
    assert "duplicate_event_id" in reducer
    assert "stale_event_id" in reducer
    assert "terminal_outranks_active" in reducer
    assert "duplicate_completion" in reducer
    assert "next.percent = Math.max(current.percent, next.percent)" in reducer
    assert "nextId && !currentId" in reducer
    assert "acceptSecurityProgressEvent(previous, incoming)" in hook
    assert "acceptSecurityProgressEvent(accepted, candidate)" in screen


def test_s6_frontend_reducer_tests_cover_replay_dedup_and_cached_state():
    tests = REDUCER_TEST.read_text()
    assert "accepts replayed missed events in order" in tests
    assert "rejects duplicate and lower event ids" in tests
    assert "never regresses percent for one run" in tests
    assert "keeps terminal state above stale active state" in tests
    assert "deduplicates completion transitions" in tests
    assert "lets persisted replay outrank cached wrong-run state" in tests


def test_s6_eventsource_uses_native_reconnect_and_bounded_polling_handover():
    hook = HOOK.read_text()
    assert "new window.EventSource(endpoint(SECURITY_EVENTS_PATH))" in hook
    assert "Native EventSource owns reconnect and automatically sends Last-Event-ID" in hook
    assert "source.onerror" in hook
    error_section = hook.split("source.onerror", 1)[1].split("return disposeSource", 1)[0]
    assert "source.close()" not in error_section
    assert "activateFallback()" in error_section
    assert "source.onopen" in hook
    assert "setFallbackActive(false)" in hook
    assert "SECURITY_PROGRESS_FALLBACK_MS = 3000" in hook
    assert "shouldKeepSecurityFallbackAlive" in hook


def test_s6_frontend_diagnostics_are_sanitized_and_counter_only():
    diagnostics = DIAGNOSTICS.read_text()
    for field in (
        "last_accepted_event_id",
        "replayed_event_count",
        "duplicate_event_count",
        "stale_event_rejection_count",
        "polling_fallback_activation_count",
        "completion_deduplication_count",
    ):
        assert field in diagnostics
    assert "recordLiteSecurityProgressDecision" in diagnostics
    assert "recordLiteSecurityFallbackActivation" in diagnostics
    assert "token=" in diagnostics  # redaction guard, not a stored token
    assert "command payload" not in diagnostics.lower()


def test_s6_caddy_stream_route_precedes_generic_api_and_disables_buffering():
    script = CADDY.read_text()
    stream = script.index("handle /api/lite/security/events")
    generic = script.index("handle /api/*", stream)
    assert stream < generic
    stream_block = script[stream:generic]
    assert "reverse_proxy 127.0.0.1:${API_PORT}" in stream_block
    assert "flush_interval -1" in stream_block


def test_s6_retention_is_lifespan_owned_not_request_owned():
    main = MAIN.read_text()
    assert "security_progress_retention_loop" in main
    assert "pocketlab-security-progress-retention" in main
    assert "security_retention_task.cancel()" in main
