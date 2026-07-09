from pathlib import Path

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py"
EVIDENCE = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_evidence.py"
ROUTER = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
LITE_API = ROOT / "src/lib/liteApi.js"
LITE_QUERY = ROOT / "src/lib/liteQueryClient.js"
LITE_STATUS = ROOT / "src/hooks/useLiteStatus.js"
LITE_SECURITY = ROOT / "src/lite/LiteSecurity.jsx"


def _prepare_state(tmp_path):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    return state


def _queue_security_run():
    from api_fastapi.services import lite_security

    return lite_security.record_queued_run(
        {
            "run_id": "security-test-run",
            "command_id": "security-test-run",
            "profile": "quick",
            "scope": "local",
            "reason": "contract test",
            "requested_at": "2026-07-09T00:00:00+00:00",
        }
    )


def test_security_f7_split_read_routes_are_registered_and_legacy_routes_remain():
    router = ROUTER.read_text()

    for route in (
        '@router.get("/security/freshness")',
        '@router.get("/security/profiles/{profile}")',
        '@router.get("/security/history")',
        '@router.get("/security/details/{run_id}")',
        '@router.get("/security/evidence/{run_id}/summary")',
        '@router.get("/security/progress")',
        '@router.get("/security/summary")',
        '@router.get("/security")',
        '@router.post("/security/check"',
    ):
        assert route in router


def test_security_f7_freshness_profile_history_and_progress_endpoints_are_compact(tmp_path):
    _prepare_state(tmp_path)
    _queue_security_run()

    http = client()
    freshness = http.get("/api/lite/security/freshness")
    assert freshness.status_code == 200
    freshness_payload = freshness.json()
    assert freshness_payload["revision"].startswith("security-")
    assert freshness_payload["summary_endpoint"] == "/api/lite/security/summary"
    assert "history" not in freshness_payload
    assert "findings" not in freshness_payload

    for profile in ("quick", "full", "app"):
        response = http.get(f"/api/lite/security/profiles/{profile}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile"] == profile
        assert payload["view_model"] == "security-profile-f7-v1"
        assert payload["sanitized"] is True
        assert len(payload.get("history", [])) <= 6
        assert "raw scanner" not in response.text.lower()
        assert "password" not in response.text.lower()

    history = http.get("/api/lite/security/history")
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["limit"] == 20
    assert history_payload["max_limit"] == 50
    assert len(history_payload["history"]) <= 20

    capped = http.get("/api/lite/security/history?limit=999")
    assert capped.status_code == 200
    capped_payload = capped.json()
    assert capped_payload["limit"] == 50
    assert len(capped_payload["history"]) <= 50

    progress = http.get("/api/lite/security/progress")
    assert progress.status_code == 200
    progress_payload = progress.json()
    assert progress_payload["view_model"] == "security-progress-f7-v1"
    assert isinstance(progress_payload["active_scan"], bool)
    assert "findings" not in progress_payload
    assert "evidence_refs" not in progress_payload


def test_security_f7_details_and_evidence_summary_are_run_scoped_and_sanitized(tmp_path):
    _prepare_state(tmp_path)
    _queue_security_run()

    http = client()
    details = http.get("/api/lite/security/details/security-test-run")
    assert details.status_code == 200
    details_payload = details.json()
    assert details_payload["run_id"] == "security-test-run"
    assert details_payload["view_model"] == "security-details-f7-v1"
    assert details_payload["sanitized"] is True
    assert len(details_payload.get("findings", [])) <= 50
    assert "raw scanner" not in details.text.lower()
    assert "private_key" not in details.text.lower()

    evidence = http.get("/api/lite/security/evidence/security-test-run/summary")
    assert evidence.status_code == 200
    evidence_payload = evidence.json()
    assert evidence_payload["run_id"] == "security-test-run"
    assert evidence_payload["sanitized"] is True
    assert evidence_payload["raw_output_hidden"] is True
    assert evidence_payload["secrets_hidden"] is True
    assert evidence_payload["private_paths_hidden"] is True
    assert "stdout" not in evidence.text.lower()
    assert "stderr" not in evidence.text.lower()


def test_security_f8_compact_state_files_are_written_once_and_used_for_reads(tmp_path):
    state = _prepare_state(tmp_path)
    _queue_security_run()

    from api_fastapi.services import lite_security_evidence

    compact = lite_security_evidence.security_root() / "compact"
    expected = [
        compact / "security_summary.json",
        compact / "security_freshness.json",
        compact / "security_history_index.json",
        compact / "security_progress.json",
        compact / "profile_latest.json",
        compact / "coverage_summary_compact.json",
        compact / "profiles" / "quick.json",
        compact / "profiles" / "full.json",
        compact / "profiles" / "app.json",
        compact / "details" / "security-test-run.json",
    ]
    for path in expected:
        assert path.exists(), f"missing compact state file: {path.relative_to(state)}"

    response = client().get("/api/lite/security/profiles/quick")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_cache"]["source"] in {"compact_profile", "fastapi_profile_memory"}


def test_security_f10_ttl_cache_contract_and_active_scan_short_ttl():
    service = SERVICE.read_text()
    evidence = EVIDENCE.read_text()

    assert "_SECURITY_SPLIT_READ_CACHE" in service
    assert '"freshness": (2.0, 1.0)' in service
    assert '"profile": (30.0, 2.0)' in service
    assert '"history": (60.0, 2.0)' in service
    assert '"progress": (3.0, 1.0)' in service
    assert "_compact_file_key(path" in service
    assert "st_mtime_ns" in service and "st_size" in service
    assert "_is_live_security_state(payload)" in service
    assert "invalidate_security_read_caches()" in service
    assert "write_compact_security_state" in service
    assert "tempfile.mkstemp" in evidence
    assert "os.replace" in evidence
    assert "os.fsync" in evidence


def test_security_f7_frontend_uses_split_read_endpoints_for_manage_details():
    api = LITE_API.read_text()
    query = LITE_QUERY.read_text()
    status = LITE_STATUS.read_text()
    screen = LITE_SECURITY.read_text()

    assert "security: conditionalGet('/api/lite/security/summary')" in api
    assert "securityProfile: (profile = 'quick') => conditionalRead(`/api/lite/security/profiles/${encodeURIComponent(profile || 'quick')}`)" in api
    assert "securityHistory: (limit = 20) => conditionalRead(`/api/lite/security/history?limit=${encodeURIComponent(limit || 20)}`)" in api
    assert "securityProgress: () => conditionalRead('/api/lite/security/progress')" in api
    assert "securityRunDetails: (runId) => conditionalRead(`/api/lite/security/details/${encodeURIComponent(runId || '')}`)" in api
    assert "securityEvidenceSummary: (runId) => conditionalRead(`/api/lite/security/evidence/${encodeURIComponent(runId || '')}/summary`)" in api
    assert "securityEvidence: (runId) => conditionalRead(`/api/lite/security/evidence/${encodeURIComponent(runId || '')}/summary`)" in api

    assert "securityProfile: (profile = 'quick')" in query
    assert "securityHistory: (limit = 20)" in query
    assert "securityFreshness" in status
    assert "securityProgress" in status

    assert "securityProfileLoader" in screen
    assert "liteApi.securityProfile(scanProfile)" in screen
    assert "liteApi.securityHistory(20)" in screen
    assert "liteApi.securityProgress()" in screen
    assert "setEvidence(await liteApi.securityEvidenceSummary(runId));" in screen
    assert "useLiteResource(liteApi.securityDetails || liteApi.security" not in screen
    assert "liteQueryKeys.securityDetails()," not in screen

    forbidden = ["nats.connect", "child_process", "exec(", "spawn("]
    lowered_screen = screen.lower()
    for needle in forbidden:
        assert needle not in lowered_screen
    assert "lynis" not in api.lower()
    assert "trivy" not in api.lower()
