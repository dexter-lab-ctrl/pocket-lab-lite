from pathlib import Path

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir, load_fastapi_app


ROOT = Path(__file__).resolve().parents[2]
LITE_API = ROOT / "src/lib/liteApi.js"
LITE_QUERY = ROOT / "src/lib/liteQueryClient.js"
LITE_SECURITY = ROOT / "src/lite/LiteSecurity.jsx"
SECURITY_EVENTS_HOOK = ROOT / "src/hooks/useLiteSecurityEvents.js"


def _prepare_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
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


def test_security_f11_routes_are_registered_independent_of_decorator_formatting():
    paths = {getattr(route, "path", "") for route in load_fastapi_app().routes}
    assert "/api/lite/security/events" in paths
    assert "/api/lite/security/progress" in paths
    assert "/api/lite/security/summary" in paths


def test_security_f11_sse_payload_is_bounded_and_sanitized(tmp_path, monkeypatch):
    _prepare_state(tmp_path, monkeypatch)
    _queue_security_run()

    from api_fastapi.routers.lite import _security_sse_payload
    from api_fastapi.services import lite_security

    plan = lite_security.security_event_replay(None)
    payload = plan["events"][0]
    frame = _security_sse_payload(payload)
    assert payload["type"] == "security.scan.snapshot"
    assert payload["snapshot"] is True
    assert isinstance(payload["event_id"], int)
    assert f"id: {payload['event_id']}" in frame
    assert "data: " in frame
    assert len(frame) < 2500

    serialized = str(payload).lower()
    for forbidden in (
        "nats://", "authorization:", "stdout", "stderr", "/data/data/",
        "/storage/emulated/", "photoprism_admin_password", "restic_password", "vault_token",
    ):
        assert forbidden not in serialized


def test_security_f11_progress_snapshot_shape_is_sanitized_and_bounded(tmp_path, monkeypatch):
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
    assert "findings" not in event
    assert "evidence_refs" not in event
    assert "raw_output" not in event
    assert len(str(event)) < 1500


def test_security_f11_progress_endpoint_is_prepared_read_only_and_truthful(tmp_path, monkeypatch):
    _prepare_state(tmp_path, monkeypatch)
    _queue_security_run()

    response = client().get("/api/lite/security/progress")
    assert response.status_code in {200, 503}
    payload = response.json()
    if response.status_code == 200:
        assert payload["view_model"] == "security-progress-f7-v1"
        assert payload["revision"].startswith(("security-progress-", "security-sqlite-progress-"))
        assert "findings" not in payload
        assert "evidence_refs" not in payload
        assert len(response.text) < 1500
    else:
        # Prepared reads must not execute a collector just to satisfy GET.
        assert payload["status"] == "warming"
        assert payload["retryable"] is True
        assert payload["refresh_pending"] is True
        assert response.headers.get("Retry-After")


def test_security_f11_frontend_uses_eventsource_with_bounded_progress_fallback():
    hook = SECURITY_EVENTS_HOOK.read_text(encoding="utf-8")
    query = LITE_QUERY.read_text(encoding="utf-8")
    security = LITE_SECURITY.read_text(encoding="utf-8")
    api = LITE_API.read_text(encoding="utf-8")

    assert "EventSource" in hook
    assert "/api/lite/security/events" in hook
    assert "liteApi.securityProgress()" in hook
    assert "SECURITY_PROGRESS_FALLBACK_MS" in hook
    assert "liteQueryKeys.securityProgress()" in hook
    assert "liteQueryKeys.securityFreshness()" in hook
    assert "liteQueryKeys.catalog" not in hook
    assert "liteQueryKeys.fleet" not in hook
    assert "liteQueryKeys.recovery" not in hook
    assert "securityEvents: '/api/lite/security/events'" in query
    assert "useLiteSecurityEvents" in security
    assert "safeGet('/api/lite/security')" in api


def test_security_f11_frontend_preserves_control_plane_boundaries():
    combined = "\n".join(
        [LITE_API.read_text(encoding="utf-8"), SECURITY_EVENTS_HOOK.read_text(encoding="utf-8"), LITE_SECURITY.read_text(encoding="utf-8")]
    ).lower()
    assert "/api/lite/security/summary" in combined
    assert "/api/lite/security/events" in combined
    assert "/api/lite/security/progress" in combined
    assert "eventsource" in combined
    assert "nats.connect" not in combined
    assert "child_process" not in combined
    assert "spawn(" not in combined


def test_security_f11_backend_dedupes_active_scan(tmp_path, monkeypatch):
    _prepare_state(tmp_path, monkeypatch)
    _queue_security_run(run_id="security-active-f11", profile="quick")

    response = client().post("/api/lite/security/check", json={"profile": "quick"})
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["duplicate"] is True
    assert payload["already_running"] is True
    assert payload["run_id"] == "security-active-f11"
