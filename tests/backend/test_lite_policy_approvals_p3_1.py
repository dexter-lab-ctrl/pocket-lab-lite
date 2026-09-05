from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

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
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()

    owner = lite_identity_auth.setup_owner(
        username="owner", display_name="Owner", password="correct horse battery staple", setup_token="token"
    )
    owner_login = lite_identity_auth.login(username="owner", password="correct horse battery staple")
    owner_auth = lite_identity_auth.authenticate_session_token(owner_login["session_token"])
    lite_enterprise_identity.set_enterprise_enabled(auth_context=owner_auth, enabled=True)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    admin_id = "human-p3-admin"
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                "INSERT INTO human_identities(human_id,username_normalized,display_name,status,auth_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (admin_id, "admin", "Admin", "active", 1, now, now),
            )
            tx.execute(
                "INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id) VALUES (?,?,?,?,?,?,?,?)",
                (admin_id, "Admin", "active", 1, now, now, owner["human_id"], owner["human_id"]),
            )

    owner_auth = lite_enterprise_identity.enrich_auth_context(
        lite_identity_auth.authenticate_session_token(
            lite_identity_auth.login(username="owner", password="correct horse battery staple")["session_token"]
        )
    )
    admin_auth = {
        "actor": {"type": "human", "identity_id": admin_id, "display_name": "Admin"},
        "session": {"authenticated": True, "assurance": []},
    }
    return state, owner, owner_auth, admin_id, admin_auth


def _insert_approval_required_decision(*, actor_id: str, decision_id: str, target_id: str, revision: str = "revision-p3") -> None:
    from api_fastapi.db.connection import begin_immediate, connection

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                "INSERT INTO policy_decisions(occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (now, decision_id, decision_id, "human", actor_id, "device.remove", "device", target_id, "assessment", 0, "approval_required", revision, 0.1),
            )


def test_0028_upgrade_is_tested_from_real_schema_27_prefix(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.db.connection import read_connection, reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations, latest_schema_version, migration_versions

    legacy = tmp_path / "schema-v27"
    legacy.mkdir()
    for source in SCHEMA.glob("*.sql"):
        if int(source.name.split("_", 1)[0]) <= 27:
            shutil.copy2(source, legacy / source.name)

    database = tmp_path / "upgrade.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    reset_sqlite_path_cache()
    assert apply_migrations(legacy) == migration_versions(legacy)
    applied = apply_migrations()
    assert 28 in applied
    assert applied == [version for version in migration_versions() if version >= 28]
    assert latest_schema_version() == migration_versions()[-1]
    with read_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"policy_approvals", "policy_temporary_exceptions", "policy_continuation_events"} <= tables


def test_owner_authority_never_creates_independent_removal_approval(approvals_runtime):
    from api_fastapi.services import lite_policy_approvals as approvals

    _, owner, _, _, _ = approvals_runtime
    _insert_approval_required_decision(actor_id=owner["human_id"], decision_id="decision-owner", target_id="node-owner")
    with pytest.raises(approvals.ApprovalError) as blocked:
        approvals.create_from_decision(decision_id="decision-owner", initiating_role="Owner")
    assert blocked.value.reason_code == "owner_approval_policy_inconsistent"
    assert blocked.value.status_code == 503


def test_admin_request_requires_independent_step_up_and_is_single_use(approvals_runtime):
    from api_fastapi.services import lite_policy_approvals as approvals

    _, _, owner_auth, admin_id, admin_auth = approvals_runtime
    _insert_approval_required_decision(actor_id=admin_id, decision_id="decision-admin", target_id="node-1")
    created = approvals.create_from_decision(decision_id="decision-admin", initiating_role="Admin")
    approval_id = created["approval"]["approval_id"]
    assert created["approval"]["status"] == "pending"

    with pytest.raises(approvals.ApprovalError) as self_approval:
        approvals.transition(auth_context=admin_auth, approval_id=approval_id, action="approve")
    assert self_approval.value.reason_code == "approval_self_forbidden"

    with pytest.raises(approvals.ApprovalError) as no_step_up:
        approvals.transition(auth_context=owner_auth, approval_id=approval_id, action="approve")
    assert no_step_up.value.reason_code == "approval_step_up_required"

    owner_auth["session"]["assurance"] = [{
        "purpose": approvals.APPROVAL_PURPOSE,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }]
    approved = approvals.transition(auth_context=owner_auth, approval_id=approval_id, action="approve")
    assert approved["approval"]["status"] == "approved"
    assert admin_id not in str(approved["approval"])

    assert approvals.matching_approved(
        initiating_human_id=admin_id,
        action_id="device.remove",
        target_type="device",
        target_id="node-1",
        policy_revision="revision-p3",
    ) == approval_id
    consumed = approvals.consume_matching(
        auth_context=admin_auth,
        approval_id=approval_id,
        action_id="device.remove",
        target_type="device",
        target_id="node-1",
        policy_revision="revision-p3",
    )
    assert consumed["consumed"] is True
    with pytest.raises(approvals.ApprovalError) as replay:
        approvals.consume_matching(
            auth_context=admin_auth,
            approval_id=approval_id,
            action_id="device.remove",
            target_type="device",
            target_id="node-1",
            policy_revision="revision-p3",
        )
    assert replay.value.reason_code == "approval_continuation_unavailable"


@pytest.mark.parametrize("role", ["Admin", "Operator"])
def test_delegated_enterprise_initiators_receive_approval_required(approvals_runtime, monkeypatch, role):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_enterprise_identity, lite_policy_opa

    _, _, _, admin_id, admin_auth = approvals_runtime
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE enterprise_memberships SET role=? WHERE human_id=?", (role, admin_id))
    auth = lite_enterprise_identity.enrich_auth_context(admin_auth)

    monkeypatch.setattr(lite_policy_opa, "_require_loopback_opa", lambda: None)
    monkeypatch.setattr(lite_policy_opa, "_policy_consistency", lambda: (True, "", "revision-p3"))
    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: "revision-p3")
    monkeypatch.setattr(
        lite_policy_opa,
        "_http_json",
        lambda *_args, **_kwargs: (
            200,
            {"result": {
                "allow": False,
                "reason_code": "approval_required",
                "constraints": [],
                "requirements": {
                    "required_approver_roles": ["Owner", "Admin"],
                    "required_assurance": "policy.approval.device.remove",
                    "approval_lifetime_seconds": 900,
                },
            }},
        ),
    )
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as blocked:
        lite_policy_opa.evaluate_authorization(
            auth_context=auth,
            action_id="device.remove",
            target_type="device",
            target_id=f"node-{role}",
            target_revision="assessment",
            target={"confirmed": True, "revision_validated": True, "protected_server_host": False},
        )
    assert blocked.value.reason_code == "approval_required"
    assert blocked.value.decision["approval"]["initiating_role"] == role


def test_owner_faulty_opa_approval_result_fails_closed_as_policy_inconsistency(approvals_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_opa

    _, _, owner_auth, _, _ = approvals_runtime
    monkeypatch.setattr(lite_policy_opa, "_require_loopback_opa", lambda: None)
    monkeypatch.setattr(lite_policy_opa, "_policy_consistency", lambda: (True, "", "revision-p3"))
    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: "revision-p3")
    monkeypatch.setattr(
        lite_policy_opa,
        "_http_json",
        lambda *_args, **_kwargs: (200, {"result": {"allow": False, "reason_code": "approval_required", "constraints": ["independent_approval"]}}),
    )
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as blocked:
        lite_policy_opa.evaluate_authorization(
            auth_context=owner_auth,
            action_id="device.remove",
            target_type="device",
            target_id="node-owner",
            target_revision="assessment",
            target={"confirmed": True, "revision_validated": True, "protected_server_host": False},
        )
    assert blocked.value.reason_code == "owner_approval_policy_inconsistent"


def test_concurrent_consumption_is_single_use(approvals_runtime):
    from api_fastapi.services import lite_policy_approvals as approvals

    _, _, owner_auth, admin_id, admin_auth = approvals_runtime
    _insert_approval_required_decision(actor_id=admin_id, decision_id="decision-race", target_id="node-race")
    approval_id = approvals.create_from_decision(decision_id="decision-race", initiating_role="Admin")["approval"]["approval_id"]
    owner_auth["session"]["assurance"] = [{
        "purpose": approvals.APPROVAL_PURPOSE,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }]
    approvals.transition(auth_context=owner_auth, approval_id=approval_id, action="approve")

    def consume():
        try:
            return approvals.consume_matching(
                auth_context=admin_auth,
                approval_id=approval_id,
                action_id="device.remove",
                target_type="device",
                target_id="node-race",
                policy_revision="revision-p3",
            )["consumed"]
        except approvals.ApprovalError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert results.count(True) == 1
    assert results.count(False) == 1
