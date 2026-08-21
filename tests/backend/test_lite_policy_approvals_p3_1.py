from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"


@pytest.fixture()
def approvals_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import begin_immediate, connection, reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_SETUP_TOKEN", "token")
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    reset_sqlite_path_cache(); SQLITE_READS.invalidate(); deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    owner = lite_identity_auth.setup_owner(username="owner", display_name="Owner", password="correct horse battery staple", setup_token="token")
    owner_login = lite_identity_auth.login(username="owner", password="correct horse battery staple")
    owner_auth = lite_identity_auth.authenticate_session_token(owner_login["session_token"])
    lite_enterprise_identity.set_enterprise_enabled(auth_context=owner_auth, enabled=True)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    admin_id = "human-p3-admin"
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("INSERT INTO human_identities(human_id,username_normalized,display_name,status,auth_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", (admin_id, "admin", "Admin", "active", 1, now, now))
            tx.execute("INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id) VALUES (?,?,?,?,?,?,?,?)", (admin_id, "Admin", "active", 1, now, now, owner["human_id"], owner["human_id"]))
    owner_auth = lite_enterprise_identity.enrich_auth_context(lite_identity_auth.authenticate_session_token(lite_identity_auth.login(username="owner", password="correct horse battery staple")["session_token"]))
    admin_auth = {"actor": {"type": "human", "identity_id": admin_id, "display_name": "Admin"}, "session": {"authenticated": True, "assurance": []}}
    return state, owner, owner_auth, admin_id, admin_auth


def test_0028_fresh_upgrade_and_idempotence_preserve_p21(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.db.connection import read_connection, reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations

    fresh = tmp_path / "fresh.sqlite3"; monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(fresh)); reset_sqlite_path_cache()
    assert 28 in apply_migrations()
    assert apply_migrations() == []
    legacy = tmp_path / "legacy"; legacy.mkdir()
    for source in SCHEMA.glob("*.sql"):
        if source.name != "0028_policy_approvals_exceptions_p3.sql":
            shutil.copy2(source, legacy / source.name)
    upgraded = tmp_path / "upgrade.sqlite3"; monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(upgraded)); reset_sqlite_path_cache()
    assert 27 in apply_migrations(legacy)
    assert apply_migrations()[-1] == 28
    with read_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"human_identities", "enterprise_memberships", "auth_sessions", "policy_approvals", "policy_temporary_exceptions", "policy_continuation_events"} <= tables
    assert {"idx_policy_approvals_pending", "idx_policy_exceptions_scope", "idx_policy_activation_single_nonterminal"} <= indexes


def test_independent_approval_requires_step_up_and_is_single_use(approvals_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals as approvals

    _, owner, owner_auth, admin_id, admin_auth = approvals_runtime
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("INSERT INTO policy_decisions(occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("2026-01-01T00:00:00Z", "decision-p3", "correlation-p3", "human", owner["human_id"], "device.remove", "device", "node-1", "assessment-1", 0, "approval_required", "revision-p3", 1.0))
    created = approvals.create_from_decision(decision_id="decision-p3", initiating_role="Owner")
    approval_id = created["approval"]["approval_id"]
    assert created["approval"]["status"] == "pending" and created["approval"]["expires_at"]
    with pytest.raises(approvals.ApprovalError) as self_approval:
        approvals.transition(auth_context=owner_auth, approval_id=approval_id, action="approve")
    assert self_approval.value.reason_code == "approval_self_forbidden"
    with pytest.raises(approvals.ApprovalError) as no_step_up:
        approvals.transition(auth_context=admin_auth, approval_id=approval_id, action="approve")
    assert no_step_up.value.reason_code == "approval_step_up_required"
    admin_auth["session"]["assurance"] = [{"purpose": approvals.APPROVAL_PURPOSE, "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")}]
    approved = approvals.transition(auth_context=admin_auth, approval_id=approval_id, action="approve")
    assert approved["approval"]["status"] == "approved"
    assert approvals.matching_approved(initiating_human_id=owner["human_id"], action_id="device.remove", target_type="device", target_id="node-1", policy_revision="revision-p3") == approval_id
    assert approvals.matching_approved(initiating_human_id=owner["human_id"], action_id="catalog.install", target_type="device", target_id="node-1", policy_revision="revision-p3") is None
    assert approvals.matching_approved(initiating_human_id=owner["human_id"], action_id="device.remove", target_type="device", target_id="node-other", policy_revision="revision-p3") is None
    assert approvals.matching_approved(initiating_human_id=owner["human_id"], action_id="device.remove", target_type="device", target_id="node-1", policy_revision="revision-other") is None
    consumed = approvals.consume_matching(auth_context=owner_auth, approval_id=approval_id, action_id="device.remove", target_type="device", target_id="node-1", policy_revision="revision-p3")
    assert consumed["consumed"] is True
    with pytest.raises(approvals.ApprovalError) as replay:
        approvals.consume_matching(auth_context=owner_auth, approval_id=approval_id, action_id="device.remove", target_type="device", target_id="node-1", policy_revision="revision-p3")
    assert replay.value.reason_code == "approval_continuation_unavailable"
    assert admin_id not in str(approved["approval"])


@pytest.mark.parametrize("role", ["Owner", "Admin", "Operator"])
def test_each_eligible_enterprise_initiator_receives_approval_required(approvals_runtime, monkeypatch, role):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_opa

    _, owner, owner_auth, _, _ = approvals_runtime
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE enterprise_memberships SET role=? WHERE human_id=?", (role, owner["human_id"]))
    owner_auth["authorization"]["role"] = role
    monkeypatch.setattr(lite_policy_opa, "_require_loopback_opa", lambda: None)
    monkeypatch.setattr(lite_policy_opa, "_policy_consistency", lambda: (True, "", "revision-p3"))
    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: "revision-p3")
    monkeypatch.setattr(lite_policy_opa, "_http_json", lambda *_args, **_kwargs: (200, {"result": {"allow": False, "reason_code": "approval_required", "constraints": [], "requirements": {"required_approver_roles": ["Owner", "Admin"], "required_assurance": "policy.approval.device.remove", "approval_lifetime_seconds": 900}}}))
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as blocked:
        lite_policy_opa.evaluate_authorization(auth_context=owner_auth, action_id="device.remove", target_type="device", target_id=f"node-{role}", target_revision="assessment", target={"confirmed": True, "revision_validated": True, "protected_server_host": False})
    assert blocked.value.reason_code == "approval_required"
    assert blocked.value.decision["approval"]["initiating_role"] == role
    assert blocked.value.decision["requirements"]["approval_lifetime_seconds"] == 900


def test_revoked_approver_and_concurrent_consumption_fail_closed(approvals_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals as approvals

    _, owner, owner_auth, admin_id, admin_auth = approvals_runtime
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            for suffix in ("revoked", "race"):
                tx.execute("INSERT INTO policy_decisions(occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (now, f"decision-{suffix}", suffix, "human", owner["human_id"], "device.remove", "device", f"node-{suffix}", "assessment", 0, "approval_required", "revision-p3", 0.1))
    admin_auth["session"]["assurance"] = [{"purpose": approvals.APPROVAL_PURPOSE, "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")}]
    revoked_id = approvals.create_from_decision(decision_id="decision-revoked", initiating_role="Owner")["approval"]["approval_id"]
    approvals.transition(auth_context=admin_auth, approval_id=revoked_id, action="approve")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE enterprise_memberships SET status='removed' WHERE human_id=?", (admin_id,))
    assert approvals.matching_approved(initiating_human_id=owner["human_id"], action_id="device.remove", target_type="device", target_id="node-revoked", policy_revision="revision-p3") is None
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE enterprise_memberships SET status='active' WHERE human_id=?", (admin_id,))
    race_id = approvals.create_from_decision(decision_id="decision-race", initiating_role="Owner")["approval"]["approval_id"]
    approvals.transition(auth_context=admin_auth, approval_id=race_id, action="approve")
    def consume():
        try:
            return approvals.consume_matching(auth_context=owner_auth, approval_id=race_id, action_id="device.remove", target_type="device", target_id="node-race", policy_revision="revision-p3")["consumed"]
        except approvals.ApprovalError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert results.count(True) == 1 and results.count(False) == 1


def test_evaluator_creates_approval_from_real_opa_result(approvals_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_opa

    _, _, owner_auth, _, _ = approvals_runtime
    monkeypatch.setattr(lite_policy_opa, "_require_loopback_opa", lambda: None)
    monkeypatch.setattr(lite_policy_opa, "_policy_consistency", lambda: (True, "", "revision-p3"))
    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: "revision-p3")
    monkeypatch.setattr(lite_policy_opa, "_http_json", lambda *_args, **_kwargs: (200, {"result": {"allow": False, "reason_code": "approval_required", "constraints": ["independent_approval"]}}))
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as blocked:
        lite_policy_opa.evaluate_authorization(auth_context=owner_auth, action_id="device.remove", target_type="device", target_id="node-2", target_revision="assessment-2", target={"confirmed": True, "revision_validated": True, "protected_server_host": False})
    assert blocked.value.reason_code == "approval_required"
    assert blocked.value.decision["approval"]["target_id"] == "node-2"


def test_temporary_exceptions_are_exact_bounded_and_role_gated(approvals_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_approvals as approvals

    _, owner, owner_auth, _, _ = approvals_runtime
    monkeypatch.setattr(approvals, "_active_revision", lambda: "revision-p3")
    created = approvals.create_exception(auth_context=owner_auth, app_id="photoprism", device_id="node-1", human_id=owner["human_id"], reason="Short maintenance window", duration_minutes=60)
    exception_id = created["exception"]["exception_id"]
    assert created["exception"]["policy_revision"] == "revision-p3"
    assert approvals.matching_exception(human_id=owner["human_id"], app_id="photoprism", device_id="node-1", policy_revision="revision-p3") == exception_id
    assert approvals.revoke_exception(auth_context=owner_auth, exception_id=exception_id)["exception"]["status"] == "revoked"
    assert approvals.matching_exception(human_id=owner["human_id"], app_id="photoprism", device_id="node-1", policy_revision="revision-p3") is None
    with pytest.raises(approvals.ApprovalError) as wildcard:
        approvals.create_exception(auth_context=owner_auth, app_id="*", device_id="node-1", human_id=owner["human_id"], reason="bad", duration_minutes=10)
    assert wildcard.value.reason_code == "exception_scope_invalid"


@pytest.mark.parametrize("role", ["Operator", "Viewer", "Auditor"])
def test_non_privileged_roles_cannot_create_or_revoke_exceptions(approvals_runtime, monkeypatch, role):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals as approvals

    _, owner, owner_auth, _, _ = approvals_runtime
    monkeypatch.setattr(approvals, "_active_revision", lambda: "revision-p3")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE enterprise_memberships SET role=? WHERE human_id=?", (role, owner["human_id"]))
    with pytest.raises(approvals.ApprovalError) as forbidden:
        approvals.create_exception(auth_context=owner_auth, app_id="photoprism", device_id="node-1", human_id=owner["human_id"], reason="maintenance", duration_minutes=5)
    assert forbidden.value.reason_code == "enterprise_rules_role_required"


def test_admin_can_create_bounded_exception(approvals_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_approvals as approvals

    _, owner, _, _, admin_auth = approvals_runtime
    monkeypatch.setattr(approvals, "_active_revision", lambda: "revision-p3")
    result = approvals.create_exception(auth_context=admin_auth, app_id="photoprism", device_id="node-admin", human_id=owner["human_id"], reason="Approved maintenance", duration_minutes=1)
    assert result["exception"]["status"] == "active"


def test_continuation_api_has_csrf_and_bounded_exception_contract(approvals_runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from api_fastapi.services import lite_policy_approvals as approvals
    from pocket_lab_test_utils import load_fastapi_app

    _, owner, _, _, _ = approvals_runtime
    monkeypatch.setattr(approvals, "_active_revision", lambda: "revision-p3")
    client = TestClient(load_fastapi_app())
    login = client.post("/api/lite/identity/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    assert client.get("/api/lite/enterprise/rules/approvals").status_code == 200
    assert client.get("/api/lite/enterprise/rules/approvals/not-found").status_code == 404
    assert client.post("/api/lite/enterprise/rules/exceptions", json={"app_id": "photoprism", "device_id": "node-api", "human_id": owner["human_id"], "reason": "maintenance", "duration_minutes": 10}).status_code == 403
    created = client.post("/api/lite/enterprise/rules/exceptions", headers={"x-pocket-lab-csrf": csrf}, json={"app_id": "photoprism", "device_id": "node-api", "human_id": owner["human_id"], "reason": "maintenance", "duration_minutes": 10})
    assert created.status_code == 201
    assert client.post(f"/api/lite/enterprise/rules/exceptions/{created.json()['exception']['exception_id']}/revoke", headers={"x-pocket-lab-csrf": csrf}).status_code == 200
