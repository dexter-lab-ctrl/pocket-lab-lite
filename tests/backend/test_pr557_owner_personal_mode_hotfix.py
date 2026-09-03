from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


@pytest.fixture()
def hotfix_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    monkeypatch.setenv("POCKETLAB_IDENTITY_SETUP_TOKEN", "one-time-setup-token")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state


def _setup_personal_owner():
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
        source="pr557-hotfix",
    )
    context = lite_identity_auth.authenticate_session_token(signed_in["session_token"])
    assert context
    return owner, signed_in, context


def _removal_target(device_id: str) -> dict:
    return {
        "confirmed": True,
        "revision_validated": True,
        "protected_server_host": False,
        "awareness_revision": 7,
        "removal_class": "stale",
        "device_id": device_id,
    }


def _install_device_removal_test_doubles(monkeypatch):
    from api_fastapi.routers import lite as lite_router
    from api_fastapi.services import fleet_registry, lite_invites, lite_policy_opa

    def assessment(device_id: str) -> dict:
        return {
            "node_id": device_id,
            "device_id": device_id,
            "safe_to_remove": True,
            "allowed": True,
            "assessment_revision": f"assessment-{device_id}",
            "awareness_revision": 7,
            "removal_class": "stale",
            "blockers": [],
            "warnings": [],
        }

    monkeypatch.setattr(fleet_registry, "find_device_identity_conflict", lambda _device_id: None)
    monkeypatch.setattr(lite_router, "_recompute_device_removal_assessment", assessment)
    monkeypatch.setattr(
        lite_router.CONTROL_PLANE,
        "validate_device_removal_assessment",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        lite_router.CONTROL_PLANE,
        "device_details",
        lambda device_id: {
            "device": {
                "node_id": device_id,
                "id": device_id,
                "name": "Old phone",
                "role": "compute",
                "status": "offline",
                "connection": "offline",
            }
        },
    )
    monkeypatch.setattr(
        lite_router.CONTROL_PLANE,
        "retire_enrolled_device",
        lambda device_id, **kwargs: {
            "device": {"node_id": device_id, "device_name": "Old phone", "role": "compute"},
            "receipt": {"receipt_id": f"receipt-{device_id}"},
        },
    )
    monkeypatch.setattr(lite_router.CONTROL_PLANE, "invalidate_domain", lambda *args, **kwargs: None)
    monkeypatch.setattr(fleet_registry, "append_device_lifecycle_event", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        fleet_registry,
        "remove_device_records",
        lambda _device_id: {"removed_device_records": 1, "removed_from": ["test-fixture"]},
    )
    monkeypatch.setattr(
        lite_invites,
        "remove_invites_for_device",
        lambda *args, **kwargs: {"removed_invite_records": 0},
    )
    monkeypatch.setattr(
        fleet_registry,
        "append_device_removed_evidence",
        lambda *args, **kwargs: {"event_type": "fleet.device_removed", "sanitized": True},
    )

    async def publish_device_removed_evidence(_evidence):
        return None

    monkeypatch.setattr(fleet_registry, "publish_device_removed_evidence", publish_device_removed_evidence)

    monkeypatch.setattr(lite_policy_opa, "_require_loopback_opa", lambda: None)
    monkeypatch.setattr(
        lite_policy_opa,
        "_policy_consistency",
        lambda: (True, "", "revision-pr557-hotfix"),
    )
    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: "revision-pr557-hotfix")

    def policy_http(method: str, path: str, payload=None, *, timeout=None):
        assert method == "POST"
        assert path == lite_policy_opa.OPA_DECISION_PATH
        input_doc = (payload or {}).get("input") or {}
        actor = input_doc.get("actor") or {}
        assert actor.get("role") == "Owner"
        assert input_doc.get("action", {}).get("id") == "device.remove"
        assert input_doc.get("target", {}).get("state", {}).get("confirmed") is True
        assert input_doc.get("target", {}).get("state", {}).get("revision_validated") is True
        assert input_doc.get("target", {}).get("state", {}).get("protected_server_host") is False
        enterprise_enabled = bool(actor.get("enterprise_enabled"))
        return 200, {
            "result": {
                "allow": True,
                "constraints": [
                    "confirmed_retirement",
                    "validated_revision",
                    "owner_authority" if enterprise_enabled else "personal_mode",
                ],
                "reason_code": (
                    "owner_authority_device_removal"
                    if enterprise_enabled
                    else "authenticated_confirmed_device_removal"
                ),
            }
        }

    monkeypatch.setattr(lite_policy_opa, "_http_json", policy_http)


def test_personal_mode_owner_unified_projection_tolerates_null_enterprise_membership(hotfix_runtime):
    from api_fastapi.services import (
        lite_enterprise_enrollment,
        lite_enterprise_governance,
        lite_enterprise_identity,
        lite_policy_opa,
    )

    owner, _signed_in, context = _setup_personal_owner()

    projection = lite_enterprise_enrollment.unified_identity_projection(context)
    assert projection["authenticated"] is True
    assert projection["person"]["human_id"] == owner["human_id"]
    assert projection["person"]["is_local_owner"] is True
    assert projection["person"]["role"] == "Owner"
    assert projection["enterprise"]["enabled"] is False
    assert projection["enterprise"]["current_membership"] is None

    access = lite_enterprise_governance.access_projection(context)
    assert access["mode"] == "personal"
    assert access["current_role"] == "Owner"
    assert access["capabilities"]["device.remove.mode"] == "allow"
    assert access["capabilities"]["device.remove.requires_approval"] is False

    enriched = lite_enterprise_identity.enrich_auth_context(context)
    policy_input = lite_policy_opa.build_authorization_input(
        auth_context=enriched,
        action_id="device.remove",
        target_type="device",
        target_id="old-phone",
        target_revision="assessment-old-phone",
        target=_removal_target("old-phone"),
    )
    assert policy_input["actor"]["role"] == "Owner"
    assert policy_input["actor"]["enterprise_enabled"] is False


def test_remove_device_api_never_creates_peer_approval_for_personal_or_enterprise_owner(
    hotfix_runtime,
    monkeypatch,
):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth

    _owner, _signed_in, _context = _setup_personal_owner()
    _install_device_removal_test_doubles(monkeypatch)

    api = TestClient(load_fastapi_app(), base_url="http://localhost")
    personal_login = api.post(
        "/api/lite/identity/login",
        json={"username": "owner", "password": "correct horse battery staple"},
    )
    assert personal_login.status_code == 200, personal_login.text
    personal_csrf = personal_login.json()["csrf_token"]

    personal_remove = api.post(
        "/api/lite/fleet/remove-device",
        headers={"X-Pocket-Lab-CSRF": personal_csrf},
        json={
            "device_id": "old-personal-phone",
            "confirm": True,
            "reason": "Retire stale Personal Mode test device",
            "assessment_revision": "assessment-old-personal-phone",
            "expected_awareness_revision": 7,
        },
    )
    assert personal_remove.status_code == 200, personal_remove.text
    assert personal_remove.json()["authorization"]["reason_code"] == "authenticated_confirmed_device_removal"

    with connection() as conn:
        personal_approvals = conn.execute("SELECT COUNT(*) AS count FROM policy_approvals").fetchone()
        personal_decision = conn.execute(
            "SELECT allow,reason_code FROM policy_decisions WHERE action_id='device.remove' ORDER BY decision_row_id DESC LIMIT 1"
        ).fetchone()
    assert int(personal_approvals["count"] or 0) == 0
    assert bool(personal_decision["allow"]) is True
    assert personal_decision["reason_code"] == "authenticated_confirmed_device_removal"

    personal_session_token = api.cookies.get(lite_identity_auth.cookie_name(), "")
    personal_context = lite_identity_auth.authenticate_session_token(personal_session_token)
    assert personal_context
    enabled = lite_enterprise_identity.set_enterprise_enabled(
        auth_context=personal_context,
        enabled=True,
        correlation_id="pr557-hotfix-enable-enterprise",
    )
    assert enabled["enabled"] is True
    assert lite_identity_auth.authenticate_session_token(personal_session_token) is None

    enterprise_login = api.post(
        "/api/lite/identity/login",
        json={"username": "owner", "password": "correct horse battery staple"},
    )
    assert enterprise_login.status_code == 200, enterprise_login.text
    enterprise_csrf = enterprise_login.json()["csrf_token"]

    enterprise_remove = api.post(
        "/api/lite/fleet/remove-device",
        headers={"X-Pocket-Lab-CSRF": enterprise_csrf},
        json={
            "device_id": "old-enterprise-phone",
            "confirm": True,
            "reason": "Retire stale Enterprise Owner test device",
            "assessment_revision": "assessment-old-enterprise-phone",
            "expected_awareness_revision": 7,
        },
    )
    assert enterprise_remove.status_code == 200, enterprise_remove.text
    assert enterprise_remove.json()["authorization"]["reason_code"] == "owner_authority_device_removal"

    with connection() as conn:
        total_approvals = conn.execute("SELECT COUNT(*) AS count FROM policy_approvals").fetchone()
        owner_decision = conn.execute(
            "SELECT allow,reason_code FROM policy_decisions WHERE action_id='device.remove' ORDER BY decision_row_id DESC LIMIT 1"
        ).fetchone()
    assert int(total_approvals["count"] or 0) == 0
    assert bool(owner_decision["allow"]) is True
    assert owner_decision["reason_code"] == "owner_authority_device_removal"
