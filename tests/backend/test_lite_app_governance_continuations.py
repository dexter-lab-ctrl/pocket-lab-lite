from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


ensure_runtime_path()


def _iso(minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def app_continuation_runtime(tmp_path, monkeypatch):
    from api_fastapi import deps
    from api_fastapi.db.connection import begin_immediate, connection, reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()

    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("UPDATE enterprise_configuration SET enabled=1, authorization_version=7 WHERE configuration_id=1")
            for human_id, username, role in (
                ("human-owner", "owner-app-governance", "Owner"),
                ("human-admin", "admin-app-governance", "Admin"),
                ("human-operator", "operator-app-governance", "Operator"),
            ):
                tx.execute(
                    """INSERT INTO human_identities(
                           human_id,username_normalized,display_name,status,auth_version,created_at,updated_at
                       ) VALUES (?,?,?,?,1,?,?)""",
                    (human_id, username, role, "active", now, now),
                )
                tx.execute(
                    """INSERT INTO enterprise_memberships(
                           human_id,role,status,authorization_version,created_at,updated_at,created_by_human_id,updated_by_human_id
                       ) VALUES (?,?,?,?,?,?,?,?)""",
                    (human_id, role, "active", 7, now, now, "human-owner", "human-owner"),
                )
    return state


def test_app_remove_approval_is_bound_to_actor_app_action_revision_and_policy(app_continuation_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals

    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_approvals(
                       approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,target_revision,
                       initiating_human_id,initiating_role,initiating_authorization_version,request_fingerprint,
                       required_approver_roles_json,required_assurance,policy_revision,status,created_at,expires_at,
                       approved_at,approved_by_human_id,reason_code,evidence_ref
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "approval-app-remove", "decision-app-remove", "corr-app-remove",
                    "app.remove", "app", "photoprism", "contract-rev-a",
                    "human-admin", "Admin", 7, "fingerprint-a",
                    '["Owner","Admin"]', "policy.approval.app.remove", "policy-rev-a",
                    "approved", now, _iso(10), now, "human-owner", "approval_required",
                    "policy:decision-app-remove",
                ),
            )

    assert lite_policy_approvals.matching_approved(
        initiating_human_id="human-admin",
        action_id="app.remove",
        target_type="app",
        target_id="photoprism",
        target_revision="contract-rev-a",
        policy_revision="policy-rev-a",
        authorization_version=7,
        request_fingerprint="fingerprint-a",
    ) == "approval-app-remove"

    for mismatch in (
        {"target_id": "example-app"},
        {"action_id": "device.remove"},
        {"target_revision": "contract-rev-stale"},
        {"policy_revision": "policy-rev-stale"},
        {"request_fingerprint": "fingerprint-other"},
        {"authorization_version": 8},
    ):
        args = {
            "initiating_human_id": "human-admin",
            "action_id": "app.remove",
            "target_type": "app",
            "target_id": "photoprism",
            "target_revision": "contract-rev-a",
            "policy_revision": "policy-rev-a",
            "authorization_version": 7,
            "request_fingerprint": "fingerprint-a",
            **mismatch,
        }
        assert lite_policy_approvals.matching_approved(**args) is None


def test_app_remove_approval_consumption_rejects_cross_app_and_replay(app_continuation_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals

    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_approvals(
                       approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,target_revision,
                       initiating_human_id,initiating_role,initiating_authorization_version,request_fingerprint,
                       required_approver_roles_json,required_assurance,policy_revision,status,created_at,expires_at,
                       approved_at,approved_by_human_id,reason_code,evidence_ref
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "approval-consume", "decision-consume", "corr-consume",
                    "app.remove", "app", "photoprism", "contract-rev-b",
                    "human-admin", "Admin", 7, "fingerprint-b",
                    '["Owner","Admin"]', "policy.approval.app.remove", "policy-rev-b",
                    "approved", now, _iso(10), now, "human-owner", "approval_required",
                    "policy:decision-consume",
                ),
            )

    auth = {"actor": {"type": "human", "identity_id": "human-admin"}, "session": {"authenticated": True}}
    with pytest.raises(lite_policy_approvals.ApprovalError) as cross_app:
        lite_policy_approvals.consume_matching(
            auth_context=auth,
            approval_id="approval-consume",
            action_id="app.remove",
            target_type="app",
            target_id="example-app",
            target_revision="contract-rev-b",
            policy_revision="policy-rev-b",
            request_fingerprint="fingerprint-b",
        )
    assert cross_app.value.reason_code == "approval_continuation_unavailable"

    consumed = lite_policy_approvals.consume_matching(
        auth_context=auth,
        approval_id="approval-consume",
        action_id="app.remove",
        target_type="app",
        target_id="photoprism",
        target_revision="contract-rev-b",
        policy_revision="policy-rev-b",
        request_fingerprint="fingerprint-b",
    )
    assert consumed["consumed"] is True

    with pytest.raises(lite_policy_approvals.ApprovalError) as replay:
        lite_policy_approvals.consume_matching(
            auth_context=auth,
            approval_id="approval-consume",
            action_id="app.remove",
            target_type="app",
            target_id="photoprism",
            target_revision="contract-rev-b",
            policy_revision="policy-rev-b",
            request_fingerprint="fingerprint-b",
        )
    assert replay.value.reason_code == "approval_continuation_unavailable"


def test_temporary_exception_is_exact_app_action_device_capability_contract_and_policy(app_continuation_runtime, monkeypatch):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_app_registry, lite_policy_approvals

    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_temporary_exceptions(
                       exception_id,action_id,app_id,device_id,human_id,required_capability,target_revision,
                       policy_revision,reason,created_by_human_id,status,created_at,expires_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "exception-install", "app.install", "photoprism", "pocket-lab-lite-server",
                    "human-operator", "install", "contract-install-a", "policy-install-a",
                    "Temporary install access", "human-owner", "active", now, _iso(10),
                ),
            )

    base = {
        "human_id": "human-operator",
        "action_id": "app.install",
        "app_id": "photoprism",
        "device_id": "pocket-lab-lite-server",
        "required_capability": "install",
        "target_revision": "contract-install-a",
        "policy_revision": "policy-install-a",
    }
    assert lite_policy_approvals.matching_exception(**base) == "exception-install"

    for mismatch in (
        {"device_id": "other-device"},
        {"required_capability": "repair"},
        {"target_revision": "contract-install-stale"},
        {"policy_revision": "policy-install-stale"},
    ):
        assert lite_policy_approvals.matching_exception(**{**base, **mismatch}) is None

    original = lite_app_registry.app_definition
    synthetic = replace(original("photoprism"), id="example-app", name="Example App", route="/apps/example-app/")
    monkeypatch.setattr(
        lite_app_registry,
        "app_definition",
        lambda value: synthetic if str(value).lower() == "example-app" else original(value),
    )
    assert lite_policy_approvals.matching_exception(**{**base, "app_id": "example-app"}) is None


def test_expired_temporary_exception_is_never_reused(app_continuation_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_approvals

    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_temporary_exceptions(
                       exception_id,action_id,app_id,device_id,human_id,required_capability,target_revision,
                       policy_revision,reason,created_by_human_id,status,created_at,expires_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "exception-expired", "app.install", "photoprism", "pocket-lab-lite-server",
                    "human-operator", "install", "contract-expired", "policy-expired",
                    "Expired", "human-owner", "active", _iso(-20), _iso(-10),
                ),
            )
    assert lite_policy_approvals.matching_exception(
        human_id="human-operator",
        action_id="app.install",
        app_id="photoprism",
        device_id="pocket-lab-lite-server",
        required_capability="install",
        target_revision="contract-expired",
        policy_revision="policy-expired",
    ) is None


def test_unknown_app_exception_lookup_fails_closed(app_continuation_runtime):
    from api_fastapi.services import lite_policy_approvals

    with pytest.raises(HTTPException):
        lite_policy_approvals.matching_exception(
            human_id="human-operator",
            action_id="app.install",
            app_id="../unknown",
            device_id="pocket-lab-lite-server",
            required_capability="install",
            target_revision="contract",
            policy_revision="policy",
        )
