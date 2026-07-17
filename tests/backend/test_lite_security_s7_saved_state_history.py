from __future__ import annotations
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_SQLITE_COMPACT_READS", "1")
    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE", "profile")
    from api_fastapi import deps
    from api_fastapi.services import lite_security
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    lite_security.invalidate_security_read_caches()
    return SecuritySQLiteRepository(), lite_security


def _finding(key: str, severity: str = "low"):
    return {"id": key, "source": "trivy", "severity": severity, "summary": f"Finding {key}", "recommendation": "Review safely."}


def _complete(repo, run_id, *, profile, requested_at, completed_at, findings=(), app_id=None, app_label=None, partial=False, score=99, evidence=True, tool_results=None):
    assert repo.reserve_scan(run_id=run_id, profile=profile, app_id=app_id, app_label=app_label, requested_at=requested_at).reserved
    repo.mark_running(run_id, started_at=requested_at)
    repo.complete_run(run_id, score=score, summary="Protected" if score >= 95 else "Something changed", partial_results=partial,
        completed_at=completed_at, findings=list(findings), evidence_refs=[f"security/evidence/{run_id}/summary.json"] if evidence else [],
        tool_results=tool_results or {"lynis": {"status": "succeeded", "duration_ms": 1200}, "trivy": {"status": "succeeded", "duration_ms": 2400}})


def test_s7_profile_snapshot_v2_is_exact_and_app_scoped(tmp_path, monkeypatch):
    repo, service = _configure(tmp_path, monkeypatch)
    _complete(repo, "security-quick", profile="quick", requested_at="2026-07-17T08:00:00Z", completed_at="2026-07-17T08:01:00Z", findings=[_finding("quick")])
    _complete(repo, "security-full", profile="full", requested_at="2026-07-17T08:02:00Z", completed_at="2026-07-17T08:04:00Z", findings=[_finding("full", "medium")], score=94)
    _complete(repo, "security-app", profile="app", app_id="photoprism", app_label="PhotoPrism", requested_at="2026-07-17T08:05:00Z", completed_at="2026-07-17T08:06:00Z", findings=[_finding("app")])
    service.invalidate_security_read_caches()
    snapshots = [service.split_profile_state("quick"), service.split_profile_state("full"), service.split_profile_state("app", "photoprism")]
    assert [item["latest_run_id"] for item in snapshots] == ["security-quick", "security-full", "security-app"]
    for item in snapshots:
        assert item["view_model"] == "security-profile-snapshot-v2"
        assert item["sanitized"] is True
        assert set(item["finding_counts"]) == {"critical", "high", "medium", "low", "info"}
        assert "evidence_refs" not in item
    assert snapshots[2]["app_id"] == "photoprism"
    assert snapshots[2]["label"] == "PhotoPrism App Check"
    assert snapshots[0]["duration_ms"] == 60_000


def test_s7_app_profile_route_requires_app_id(tmp_path, monkeypatch):
    repo, service = _configure(tmp_path, monkeypatch)
    _complete(repo, "security-app-route", profile="app", app_id="photoprism", app_label="PhotoPrism", requested_at="2026-07-17T09:00:00Z", completed_at="2026-07-17T09:01:00Z")
    service.invalidate_security_read_caches()
    http = client()
    assert http.get("/api/lite/security/profiles/app").status_code == 400
    payload = http.get("/api/lite/security/profiles/app?app_id=photoprism").json()
    assert payload["latest_run_id"] == "security-app-route"


def test_s7_delta_uses_stable_key_and_skips_partial_or_other_profile(tmp_path, monkeypatch):
    repo, service = _configure(tmp_path, monkeypatch)
    _complete(repo, "security-baseline", profile="quick", requested_at="2026-07-17T10:00:00Z", completed_at="2026-07-17T10:01:00Z", findings=[_finding("resolved"), _finding("ongoing")])
    _complete(repo, "security-partial", profile="quick", requested_at="2026-07-17T10:02:00Z", completed_at="2026-07-17T10:03:00Z", findings=[_finding("partial-only")], partial=True)
    _complete(repo, "security-current", profile="quick", requested_at="2026-07-17T10:04:00Z", completed_at="2026-07-17T10:05:00Z", findings=[_finding("ongoing"), _finding("new")])
    _complete(repo, "security-full-other", profile="full", requested_at="2026-07-17T10:06:00Z", completed_at="2026-07-17T10:07:00Z", findings=[_finding("full-only")])
    service.invalidate_security_read_caches()
    delta = service.split_profile_state("quick")["finding_delta"]
    assert delta["comparison_run_id"] == "security-baseline"
    assert (delta["new_count"], delta["resolved_count"], delta["ongoing_count"]) == (1, 1, 1)
    assert "partial-only" not in str(delta) and "full-only" not in str(delta)


def test_s7_first_run_does_not_claim_no_new_changes(tmp_path, monkeypatch):
    repo, service = _configure(tmp_path, monkeypatch)
    _complete(repo, "security-first", profile="app", app_id="photoprism", app_label="PhotoPrism", requested_at="2026-07-17T11:00:00Z", completed_at="2026-07-17T11:01:00Z", findings=[_finding("first")])
    service.invalidate_security_read_caches()
    change = service.split_profile_state("app", "photoprism")["change_summary"]
    assert change["comparison_available"] is False
    assert "No earlier check" in change["summary"]
    assert "No new changes" not in change["summary"]


def test_s7_cursor_history_is_stable_bounded_and_compact(tmp_path, monkeypatch):
    repo, service = _configure(tmp_path, monkeypatch)
    for suffix in ("a", "b", "c"):
        _complete(repo, f"security-history-{suffix}", profile="quick", requested_at="2026-07-17T12:00:00Z", completed_at="2026-07-17T12:01:00Z", findings=[_finding(suffix)])
    service.invalidate_security_read_caches()
    first = service.split_history_state(2)
    second = service.split_history_state(2, first["next_cursor"])
    first_ids = [item["run_id"] for item in first["history"]]
    second_ids = [item["run_id"] for item in second["history"]]
    assert first["view_model"] == "security-history-cursor-v2"
    assert first_ids + second_ids == ["security-history-c", "security-history-b", "security-history-a"]
    assert set(first_ids).isdisjoint(second_ids)
    for item in first["history"] + second["history"]:
        assert "evidence_refs" not in item and "findings" not in item and "tool_results" not in item
        assert "tool_status" in item and "duration_ms" in item and "finding_counts" in item
    assert service.split_history_state(999)["limit"] == 100
    with pytest.raises(ValueError, match="Invalid Security history cursor"):
        service.split_history_state(20, "invalid-cursor")


def test_s7_profile_metadata_is_bounded_truthful_and_failure_safe(tmp_path, monkeypatch):
    repo, service = _configure(tmp_path, monkeypatch)
    tools = {f"tool-{index}": {"status": "succeeded", "duration_ms": index + 1} for index in range(20)}
    _complete(repo, "security-bounded", profile="quick", requested_at="2026-07-17T13:00:00Z", completed_at="2026-07-17T13:02:00Z", evidence=True, tool_results=tools)
    service.invalidate_security_read_caches()
    snapshot = service.split_profile_state("quick")
    assert snapshot["completed_at"] == "2026-07-17T13:02:00Z"
    assert snapshot["evidence_saved"] is True
    assert snapshot["evidence_saved_at"] == "2026-07-17T13:02:00Z"
    assert snapshot["duration_ms"] == 120_000
    assert len(snapshot["tool_status"]) == 12
    assert all(set(item) <= {"tool", "status", "duration_ms", "timed_out"} for item in snapshot["tool_status"])

    assert repo.reserve_scan(run_id="security-timeout", profile="quick", requested_at="2026-07-17T13:03:00Z").reserved
    repo.mark_running("security-timeout", started_at="2026-07-17T13:03:00Z")
    repo.fail_run("security-timeout", failure_code="lynis_timeout", failure_message="internal timeout details", completed_at="2026-07-17T13:04:00Z")
    service.invalidate_security_read_caches()
    failed = service.split_profile_state("quick")
    assert failed["status"] == "failed"
    assert failed["summary"] != "Protected"
    assert failed["timeout"]["summary"] == "The host check took too long and was stopped safely."
    assert "internal timeout details" not in str(failed["timeout"])


def test_s7_frontend_source_boundaries_and_lazy_composition():
    screen = (ROOT / "src/lite/LiteSecurity.jsx").read_text(encoding="utf-8")
    history = (ROOT / "src/lite/security/SecurityHistoryLazy.jsx").read_text(encoding="utf-8")
    details = (ROOT / "src/lite/security/SecurityProgressiveDetailsLazy.jsx").read_text(encoding="utf-8")
    snapshots = (ROOT / "src/lib/liteSafeSnapshots.js").read_text(encoding="utf-8")
    selectors = (ROOT / "src/lib/liteViewModels.js").read_text(encoding="utf-8")
    css = (ROOT / "src/index.css").read_text(encoding="utf-8")

    assert 'data-security-s7-profile-cards="true"' in screen
    assert "selectSecurityStatePrecedence" in screen
    assert "useInfiniteQuery" in history
    assert "Load older checks" in history
    assert "mergeSecurityHistoryPages" in history
    assert "<time" in history and "title={completedAt" in history
    assert "React.lazy(() => import('./SecurityHistoryLazy.jsx'))" in details
    assert "type === 'history'" in details
    assert "security-profile-snapshot-v2" in selectors
    assert "offline_dexie_snapshot" in selectors
    assert "liteSecurityProfileSnapshotPath" in snapshots
    assert "evidence_refs" not in selectors[selectors.index("export function selectSecurityProfileSnapshotView"):selectors.index("export function selectSecurityProfileSnapshotViews")]
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "child_process" not in screen
    assert "nats.connect" not in screen
    assert "/api/lite/security/evidence/" not in screen

    gate = (ROOT / "scripts/dev/check-lite-security-s7-exit-gate.sh").read_text(encoding="utf-8")
    taskfile = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")
    assert "PRAGMA quick_check" in gate
    assert "security-profile-snapshot-v2" in gate
    assert "security-history-cursor-v2" in gate
    assert "matched" in gate and "security-db-compare.py" in gate
    assert "lite:security:s7:check" in taskfile
    assert "npm run build" in taskfile
