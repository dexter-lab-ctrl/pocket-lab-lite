from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


@pytest.fixture()
def enterprise_runtime(tmp_path, monkeypatch):
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
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state


def _client_with_owner(enterprise_runtime):
    client = TestClient(load_fastapi_app())
    setup = client.post(
        "/api/lite/identity/setup",
        json={
            "username": "owner",
            "display_name": "Owner",
            "password": "correct horse battery staple",
            "setup_token": "one-time-setup-token",
        },
    )
    assert setup.status_code == 201
    return client, setup.json(), "correct horse battery staple"


def _sign_in(client, password):
    response = client.post("/api/lite/identity/login", json={"username": "owner", "password": password})
    assert response.status_code == 200
    return response.json()


def _current_auth(client):
    from api_fastapi.services import lite_identity_auth

    token = client.cookies.get("pocketlab_session")
    assert token
    auth = lite_identity_auth.authenticate_session_token(token)
    assert auth
    return auth


def _enable_enterprise_server_side(client):
    """Exercise server-owned mode mutation after the route step-up guard is proven.

    WebAuthn step-up itself is covered in the passkey/governance suites. These P2
    tests focus on mode/membership persistence and session invalidation.
    """
    from api_fastapi.services import lite_enterprise_identity

    return lite_enterprise_identity.set_enterprise_enabled(
        auth_context=_current_auth(client),
        enabled=True,
    )


def test_enterprise_routes_reject_personal_mode_and_require_csrf(enterprise_runtime):
    client, owner, password = _client_with_owner(enterprise_runtime)
    hidden = client.get("/api/lite/enterprise/identity")
    assert hidden.status_code == 404
    assert hidden.json()["reason_code"] == "enterprise_mode_disabled"

    missing_csrf = client.put("/api/lite/enterprise/identity/mode", json={"enabled": True})
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["reason_code"] == "csrf_required"

    # CSRF is necessary but no longer sufficient for this root-level change.
    # Current Lite requires recent Owner passkey assurance.
    guarded = client.put(
        "/api/lite/enterprise/identity/mode",
        json={"enabled": True},
        headers={"x-pocket-lab-csrf": owner["csrf_token"]},
    )
    assert guarded.status_code == 428
    assert guarded.json()["detail"]["reason_code"] == "owner_step_up_required"

    enabled = _enable_enterprise_server_side(client)
    assert enabled["enabled"] is True

    # Mode changes invalidate the pre-change session, so the stale browser
    # session cannot be used to manage roles.
    stale = client.get("/api/lite/enterprise/identity")
    assert stale.status_code == 401
    fresh = _sign_in(client, password)
    visible = client.get("/api/lite/enterprise/identity")
    assert visible.status_code == 200
    assert visible.json()["current_membership"]["role"] == "Owner"
    members = client.get("/api/lite/enterprise/identity/members")
    assert members.status_code == 200
    assert members.json()["members"][0]["role"] == "Owner"
    assert fresh["enterprise"]["enabled"] is True


def test_membership_is_server_owned_invalidates_stale_sessions_and_protects_final_owner(enterprise_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth

    client, _owner, password = _client_with_owner(enterprise_runtime)
    enabled = _enable_enterprise_server_side(client)
    assert enabled["enabled"] is True
    _sign_in(client, password)
    stale_token = client.cookies.get("pocketlab_session")
    auth = lite_enterprise_identity.enrich_auth_context(
        lite_identity_auth.authenticate_session_token(client.cookies.get("pocketlab_session"))
    )
    assert auth and auth["authorization"]["role"] == "Owner"

    with connection() as conn:
        with begin_immediate(conn) as tx:
            now = "2026-01-01T00:00:00Z"
            tx.execute(
                "INSERT INTO human_identities(human_id,username_normalized,display_name,status,auth_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                ("human-second", "second", "Second Owner", "active", 1, now, now),
            )

    second = lite_enterprise_identity.set_membership(
        auth_context=auth,
        human_id="human-second",
        role="Owner",
        membership_status="active",
    )
    assert second["member"]["role"] == "Owner"
    with pytest.raises(lite_enterprise_identity.EnterpriseIdentityError) as invalid:
        lite_enterprise_identity.set_membership(auth_context=auth, human_id="human-second", role="Root", membership_status="active")
    assert invalid.value.reason_code == "enterprise_role_invalid"

    # Reducing the second Owner leaves one Owner; reducing that final Owner is
    # rejected before a role/session change can take effect.
    reduced_second = lite_enterprise_identity.set_membership(auth_context=auth, human_id="human-second", role="Admin", membership_status="active")
    assert reduced_second["member"]["role"] == "Admin"
    with pytest.raises(lite_enterprise_identity.EnterpriseIdentityError) as invalid:
        lite_enterprise_identity.set_membership(auth_context=auth, human_id=auth["actor"]["identity_id"], role="Admin", membership_status="active")
    assert invalid.value.reason_code == "enterprise_final_owner_protected"

    restored = lite_enterprise_identity.set_membership(auth_context=auth, human_id="human-second", role="Owner", membership_status="active")
    assert restored["member"]["role"] == "Owner"
    changed = lite_enterprise_identity.set_membership(auth_context=auth, human_id=auth["actor"]["identity_id"], role="Admin", membership_status="active")
    assert changed["member"]["role"] == "Admin"
    assert lite_identity_auth.authenticate_session_token(stale_token) is None

    # A browser-provided role cannot restore authorization after downgrade.
    forged = {**auth, "authorization": {"enterprise_enabled": True, "role": "Owner"}}
    with pytest.raises(lite_enterprise_identity.EnterpriseIdentityError) as stale:
        lite_enterprise_identity.set_membership(auth_context=forged, human_id="human-second", role="Admin", membership_status="active")
    assert stale.value.reason_code == "enterprise_owner_required"
