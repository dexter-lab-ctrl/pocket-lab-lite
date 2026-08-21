from __future__ import annotations

import json

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture()
def runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3")); monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_SETUP_TOKEN", "token"); reset_sqlite_path_cache(); SQLITE_READS.invalidate(); deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations(); lite_identity_auth.setup_owner(username="owner", display_name="Owner", password="correct horse battery staple", setup_token="token")
    login = lite_identity_auth.login(username="owner", password="correct horse battery staple")
    auth = lite_identity_auth.authenticate_session_token(login["session_token"])
    lite_enterprise_identity.set_enterprise_enabled(auth_context=auth, enabled=True)
    login = lite_identity_auth.login(username="owner", password="correct horse battery staple")
    return state, lite_enterprise_identity.enrich_auth_context(lite_identity_auth.authenticate_session_token(login["session_token"]))


def _activate_row(revision_id: str):
    from api_fastapi.db.connection import begin_immediate, connection
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE policy_revisions SET validation_status='valid',lifecycle_status='active' WHERE revision_id=?", (revision_id,))
            tx.execute("INSERT INTO policy_runtime_state(state_id,active_revision_id,known_good_revision_id,updated_at) VALUES (1,?,?,?)", (revision_id, revision_id, "2026-01-01T00:00:00Z"))


def test_real_and_synthetic_simulation_are_bounded_and_non_mutating(runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_analysis as analysis, lite_policy_lifecycle as lifecycle, lite_policy_opa
    _, auth = runtime
    revision = lifecycle.create_revision(auth_context=auth, template_id="baseline", parameters={}, change_summary="simulate")["revision"]["revision_id"]
    _activate_row(revision)
    before = {}
    with connection() as conn:
        for table in ("policy_runtime_state", "policy_activation_operations", "enterprise_memberships", "auth_sessions"):
            before[table] = [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
    monkeypatch.setattr(lite_policy_opa, "_http_json", lambda *_args, **_kwargs: (200, {"result": {"allow": True, "reason_code": "authenticated_app_install", "constraints": ["authenticated_actor"]}}))
    real = analysis.simulate(auth_context=auth, revision_id=revision, action_id="catalog.install", target_id="app-1", mode="real_derived")
    synthetic = analysis.simulate(auth_context=auth, revision_id=revision, action_id="device.remove", target_id="device-1", mode="synthetic", scenario={"confirmed": True, "revision_validated": True, "protected_server_host": False})
    assert real["input_mode"] == "real_derived" and real["outcome"] == "allow"
    assert synthetic["input_mode"] == "synthetic" and synthetic["synthetic_fields"] == ["confirmed", "protected_server_host", "revision_validated"]
    assert "session" not in json.dumps(real).lower() and real["raw_input_exposed"] is False
    with connection() as conn:
        for table, prior in before.items():
            assert [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")] == prior
    with pytest.raises(analysis.PolicyAnalysisError) as invalid:
        analysis.simulate(auth_context=auth, revision_id=revision, action_id="catalog.install", target_id="app-1", mode="synthetic", scenario={"role": True})
    assert invalid.value.reason_code == "policy_simulation_invalid"


def test_candidate_analysis_health_and_decision_explorer(runtime, monkeypatch):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_analysis as analysis, lite_policy_lifecycle as lifecycle, lite_policy_opa
    _, auth = runtime
    active = lifecycle.create_revision(auth_context=auth, template_id="baseline", parameters={}, change_summary="active")["revision"]["revision_id"]
    candidate = lifecycle.create_revision(auth_context=auth, template_id="passkey_step_up", parameters={"max_age_seconds": 600}, change_summary="candidate")["revision"]["revision_id"]
    _activate_row(active)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE policy_revisions SET validation_status='valid' WHERE revision_id=?", (candidate,))
            tx.execute("INSERT INTO policy_decisions(occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("2026-01-01T00:00:00Z", "decision-p23", "c", "human", "owner", "catalog.install", "app", "app-1", "r", 1, "authenticated_app_install", active, 1.2))
    simulated = analysis.simulate(auth_context=auth, revision_id=candidate, action_id="device.remove", target_id="device-1", mode="synthetic", scenario={"confirmed": False})
    assert simulated["outcome"] == "block"
    report = analysis.analyze(auth_context=auth, revision_id=active)
    assert report["registered_protected_actions"] == report["represented_actions"] and report["findings"] == []
    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: active); monkeypatch.setattr(lite_policy_opa, "_observed_opa_revision", lambda: active)
    health = analysis.health(auth_context=auth)
    assert health["consistency_state"] == "ready" and health["raw_input_exposed"] is False
    page = lite_policy_opa.list_decisions(action_id="catalog.install", allowed=True, limit=1)
    assert page["decisions"][0]["decision_id"] == "decision-p23" and page["raw_input_exposed"] is False
