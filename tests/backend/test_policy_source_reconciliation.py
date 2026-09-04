from __future__ import annotations

import json
import sqlite3

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture()
def policy_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_OPA_ACTIVE_POLICY_DIR", str(state / "opa" / "active"))
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    monkeypatch.setenv("POCKETLAB_IDENTITY_SETUP_TOKEN", "one-time-setup-token")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state


def _owner_context():
    from api_fastapi.services import lite_identity_auth

    owner = lite_identity_auth.setup_owner(
        username="owner",
        display_name="Pocket Lab Owner",
        password="correct horse battery staple",
        setup_token="one-time-setup-token",
    )
    signed_in = lite_identity_auth.login(
        username="owner",
        password="correct horse battery staple",
        source="policy-source-reconciliation",
    )
    context = lite_identity_auth.authenticate_session_token(signed_in["session_token"])
    assert context
    context["session"]["assurance"] = [
        {
            "purpose": "policy.rules.activate",
            "credential_id": "test-passkey",
            "satisfied_at": "2026-09-04T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
        }
    ]
    return owner, context


def _install_stale_durable_revision(owner_id: str) -> str:
    from api_fastapi.db.connection import begin_immediate, connection

    revision = "plr-00000000000000000000000000000000"
    params = {"admin_device_remove_approval": 1, "operator_device_remove_approval": 1}
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_revisions(
                       revision_id,parent_revision_id,template_id,template_version,
                       canonical_parameters_json,manifest_json,content_hash,created_by_human_id,
                       created_at,validation_status,validated_at,validation_reason_code,lifecycle_status,
                       activated_at,change_summary
                   ) VALUES (NULLIF(?,''),NULL,'enterprise_governance','1',?,?,?,?,?,
                             'valid','2026-09-01T00:00:00Z','','active','2026-09-01T00:00:00Z','Old durable Rules')""",
                (
                    revision,
                    json.dumps(params, sort_keys=True, separators=(",", ":")),
                    json.dumps({"files": [], "candidate_hash": "old"}, sort_keys=True, separators=(",", ":")),
                    "0" * 64,
                    owner_id,
                    "2026-09-01T00:00:00Z",
                ),
            )
            tx.execute(
                """INSERT INTO policy_runtime_state(state_id,active_revision_id,known_good_revision_id,updated_at,updated_by_operation_id)
                   VALUES (1,?,?,?,NULL)""",
                (revision, revision, "2026-09-01T00:00:00Z"),
            )
    return revision


def _insert_legacy_owner_approval(owner_id: str, revision: str, *, approval_id: str = "apr-legacy-owner") -> None:
    """Simulate an Owner row that existed before migration 0031 was installed."""
    from api_fastapi.db.connection import begin_immediate, connection

    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_insert")
            tx.execute("DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_update")
            tx.execute(
                """INSERT INTO policy_approvals(
                       approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,
                       initiating_human_id,initiating_role,required_approver_roles_json,required_assurance,
                       policy_revision,status,created_at,expires_at,reason_code,evidence_ref
                   ) VALUES (?,?,?,'device.remove','device','old-phone',?,'Owner',?,
                             'policy.approval.device.remove',?,'pending',?,?, 'approval_required',?)""",
                (
                    approval_id,
                    "decision-" + approval_id,
                    "corr-" + approval_id,
                    owner_id,
                    json.dumps(["Admin", "Owner"]),
                    revision,
                    "2026-09-04T00:00:00Z",
                    "2099-01-01T00:00:00Z",
                    "policy:legacy-owner",
                ),
            )


def test_repository_source_drift_fails_closed_before_stale_opa(policy_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_opa, lite_policy_source_sync

    owner, context = _owner_context()
    stale_revision = _install_stale_durable_revision(owner["human_id"])

    source = lite_policy_source_sync.source_state()
    assert source["durable"] is True
    assert source["active_revision"] == stale_revision
    assert source["repository_revision"] != stale_revision
    assert source["source_update_required"] is True

    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: stale_revision)
    monkeypatch.setattr(lite_policy_opa, "_observed_opa_revision", lambda: stale_revision)
    consistent, reason, observed = lite_policy_opa._policy_consistency()
    assert consistent is False
    assert reason == "policy_source_update_pending"
    assert observed == stale_revision

    called = {"opa_post": False}

    def _unexpected_opa(*args, **kwargs):
        called["opa_post"] = True
        raise AssertionError("stale OPA must not be queried after source drift is detected")

    monkeypatch.setattr(lite_policy_opa, "_require_loopback_opa", lambda: None)
    monkeypatch.setattr(lite_policy_opa, "_http_json", _unexpected_opa)
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as error:
        lite_policy_opa.evaluate_authorization(
            auth_context=context,
            action_id="device.remove",
            target_type="device",
            target_id="old-phone",
            target_revision="assessment-old-phone",
            target={"confirmed": True, "revision_validated": True, "protected_server_host": False},
            correlation_id="source-drift-fail-closed",
        )
    assert error.value.reason_code == "policy_source_update_pending"
    assert error.value.status_code == 503
    assert called["opa_post"] is False


def test_source_sync_cancels_impossible_owner_request_and_queues_supervisor_operation(policy_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_source_sync

    owner, context = _owner_context()
    stale_revision = _install_stale_durable_revision(owner["human_id"])
    _insert_legacy_owner_approval(owner["human_id"], stale_revision)

    result = lite_policy_source_sync.request_source_sync(
        auth_context=context,
        correlation_id="source-sync-test",
    )
    assert result["status"] == "queued"
    assert result["accepted"] is True
    assert result["activation_required"] is True
    assert result["operation"]["state"] == "pending"
    assert result["operation"]["candidate_revision_id"] != stale_revision
    assert result["cleanup"]["owner_approval_requests_cancelled"] == 1

    with connection() as conn:
        approval = conn.execute(
            "SELECT status,reason_code FROM policy_approvals WHERE approval_id='apr-legacy-owner'"
        ).fetchone()
        operation = conn.execute(
            "SELECT requested_by_human_id,candidate_revision_id,state FROM policy_activation_operations LIMIT 1"
        ).fetchone()
        candidate = conn.execute(
            "SELECT parent_revision_id,created_by_human_id,lifecycle_status,validation_status FROM policy_revisions WHERE revision_id=?",
            (result["operation"]["candidate_revision_id"],),
        ).fetchone()
        evidence = conn.execute(
            "SELECT event_type,reason_code FROM policy_continuation_events WHERE subject_id='apr-legacy-owner' ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
    assert approval["status"] == "cancelled"
    assert approval["reason_code"] == "owner_authority_policy_inconsistency"
    assert operation["requested_by_human_id"] == owner["human_id"]
    assert operation["state"] == "pending"
    assert candidate["parent_revision_id"] == stale_revision
    assert candidate["created_by_human_id"] == owner["human_id"]
    assert candidate["lifecycle_status"] == "draft"
    assert candidate["validation_status"] == "pending"
    assert evidence["event_type"] == "approval.invalidated"
    assert evidence["reason_code"] == "owner_authority_policy_inconsistency"


def test_source_sync_requires_recent_owner_passkey_assurance(policy_runtime):
    from api_fastapi.services import lite_enterprise_governance, lite_policy_source_sync

    owner, context = _owner_context()
    _install_stale_durable_revision(owner["human_id"])
    context["session"]["assurance"] = []

    with pytest.raises(lite_enterprise_governance.GovernanceError) as error:
        lite_policy_source_sync.request_source_sync(
            auth_context=context,
            correlation_id="source-sync-step-up-required",
        )
    assert error.value.reason_code == "owner_step_up_required"
    assert error.value.status_code == 428


def test_source_sync_is_idempotent_while_same_candidate_is_pending(policy_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_source_sync

    owner, context = _owner_context()
    _install_stale_durable_revision(owner["human_id"])
    first = lite_policy_source_sync.request_source_sync(
        auth_context=context,
        correlation_id="source-sync-first",
    )
    second = lite_policy_source_sync.request_source_sync(
        auth_context=context,
        correlation_id="source-sync-second",
    )
    assert first["status"] == "queued"
    assert second["status"] == "already_requested"
    assert second["operation"]["operation_id"] == first["operation"]["operation_id"]
    assert second["operation"]["candidate_revision_id"] == first["operation"]["candidate_revision_id"]

    with connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM policy_activation_operations").fetchone()
    assert int(count["count"] or 0) == 1


def test_owner_approval_required_result_is_rejected_without_creating_request(policy_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_opa

    _owner, context = _owner_context()
    context["authorization"] = {
        "enterprise_enabled": True,
        "role": "Owner",
        "membership_active": True,
        "authorization_version": 1,
        "identity_class": "enterprise_member",
    }
    monkeypatch.setattr(lite_policy_opa, "_require_loopback_opa", lambda: None)
    monkeypatch.setattr(lite_policy_opa, "_policy_consistency", lambda: (True, "", "revision-owner-defense"))
    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: "revision-owner-defense")
    monkeypatch.setattr(
        lite_policy_opa,
        "_http_json",
        lambda *args, **kwargs: (
            200,
            {
                "result": {
                    "allow": False,
                    "constraints": ["independent_approval", "active_owner_or_admin", "passkey_step_up"],
                    "reason_code": "approval_required",
                    "requirements": {
                        "required_approver_roles": ["Owner", "Admin"],
                        "required_assurance": "policy.approval.device.remove",
                        "approval_lifetime_seconds": 900,
                    },
                }
            },
        ),
    )

    with pytest.raises(lite_policy_opa.PolicyDecisionError) as error:
        lite_policy_opa.evaluate_authorization(
            auth_context=context,
            action_id="device.remove",
            target_type="device",
            target_id="old-phone",
            target_revision="assessment-old-phone",
            target={"confirmed": True, "revision_validated": True, "protected_server_host": False},
            correlation_id="owner-defense",
        )
    assert error.value.reason_code == "owner_approval_policy_inconsistent"
    assert error.value.status_code == 503
    assert error.value.decision["reason_code"] == "approval_required"
    assert error.value.decision.get("approval") is None

    with connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM policy_approvals").fetchone()
    assert int(count["count"] or 0) == 0


def test_sqlite_rejects_new_owner_or_nonmember_device_approval(policy_runtime):
    from api_fastapi.db.connection import begin_immediate, connection

    owner, _context = _owner_context()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_decisions(
                       occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,
                       target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "2026-09-04T00:00:00Z",
                    "decision-db-owner-reject",
                    "corr-db-owner-reject",
                    "human",
                    owner["human_id"],
                    "device.remove",
                    "device",
                    "old-phone",
                    "assessment-old-phone",
                    0,
                    "approval_required",
                    "plr-db-defense",
                    1.0,
                ),
            )
            with pytest.raises(sqlite3.IntegrityError, match="policy_approval_requester_invalid"):
                tx.execute(
                    """INSERT INTO policy_approvals(
                           approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,
                           initiating_human_id,initiating_role,required_approver_roles_json,required_assurance,
                           policy_revision,status,created_at,expires_at,reason_code,evidence_ref
                       ) VALUES (?,?,?,'device.remove','device','old-phone',?,'Owner',?,
                                 'policy.approval.device.remove','plr-db-defense','pending',?,?, 'approval_required',?)""",
                    (
                        "apr-db-owner-reject",
                        "decision-db-owner-reject",
                        "corr-db-owner-reject",
                        owner["human_id"],
                        json.dumps(["Admin", "Owner"]),
                        "2026-09-04T00:00:00Z",
                        "2099-01-01T00:00:00Z",
                        "policy:db-owner-reject",
                    ),
                )


def test_legacy_owner_request_is_cancel_only_and_cannot_be_reviewed(policy_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals

    owner, context = _owner_context()
    revision = _install_stale_durable_revision(owner["human_id"])
    _insert_legacy_owner_approval(owner["human_id"], revision)
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO enterprise_configuration(configuration_id,enabled,authorization_version,enabled_at,created_at,updated_at,updated_by_human_id)
                   VALUES (1,1,1,?,?,?,?)
                   ON CONFLICT(configuration_id) DO UPDATE SET enabled=1""",
                ("2026-09-04T00:00:00Z", "2026-09-04T00:00:00Z", "2026-09-04T00:00:00Z", owner["human_id"]),
            )
            tx.execute(
                """INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id)
                   VALUES (?,'Owner','active',1,?,?,?,?)
                   ON CONFLICT(human_id) DO UPDATE SET role='Owner',status='active'""",
                (owner["human_id"], "2026-09-04T00:00:00Z", "2026-09-04T00:00:00Z", owner["human_id"], owner["human_id"]),
            )

    listed = lite_policy_approvals.list_approvals(auth_context=context)["approvals"]
    legacy = next(item for item in listed if item["approval_id"] == "apr-legacy-owner")
    assert legacy["policy_inconsistency"] is True
    assert legacy["viewer_actions"] == {"approve": False, "reject": False, "cancel": True}
    assert legacy["eligible_approver_count"] == 0

    with pytest.raises(lite_policy_approvals.ApprovalError) as error:
        lite_policy_approvals.transition(
            auth_context=context,
            approval_id="apr-legacy-owner",
            action="reject",
        )
    assert error.value.reason_code == "owner_approval_policy_inconsistent"


def test_create_from_decision_refuses_owner_even_if_called_directly(policy_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals

    owner, _context = _owner_context()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_decisions(
                       occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,
                       target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "2026-09-04T00:00:00Z",
                    "decision-owner-impossible",
                    "corr-owner-impossible",
                    "human",
                    owner["human_id"],
                    "device.remove",
                    "device",
                    "old-phone",
                    "assessment-old-phone",
                    0,
                    "approval_required",
                    "plr-old-owner",
                    1.0,
                ),
            )
    with pytest.raises(lite_policy_approvals.ApprovalError) as error:
        lite_policy_approvals.create_from_decision(
            decision_id="decision-owner-impossible",
            initiating_role="Owner",
        )
    assert error.value.reason_code == "owner_approval_policy_inconsistent"

    with connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM policy_approvals").fetchone()
    assert int(count["count"] or 0) == 0
