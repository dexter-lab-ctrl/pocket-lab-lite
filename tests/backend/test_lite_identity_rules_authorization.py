from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


def _reason_code(response):
    body = response.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        return body.get("reason_code") or detail.get("reason_code")
    return body.get("reason_code")


@pytest.fixture()
def auth_runtime(tmp_path, monkeypatch):
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


def test_identity_password_session_and_recovery_are_hash_only(auth_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_identity_auth

    owner = lite_identity_auth.setup_owner(
        username="Owner_User",
        display_name="Local Owner",
        password="correct horse battery staple",
        setup_token="one-time-setup-token",
    )
    assert owner["username"] == "owner-user"

    signed_in = lite_identity_auth.login(
        username="owner_user",
        password="correct horse battery staple",
        source="test",
    )
    assert signed_in["session_token"]
    assert signed_in["csrf_token"]
    context = lite_identity_auth.authenticate_session_token(signed_in["session_token"])
    assert context["actor"]["type"] == "human"
    assert lite_identity_auth.csrf_matches(context, signed_in["csrf_token"]) is True

    recovery = lite_identity_auth.regenerate_recovery_codes(
        human_id=owner["human_id"], session_id=signed_in["session_id"]
    )
    assert len(recovery["codes"]) == 10

    with connection() as conn:
        credential = conn.execute(
            "SELECT verifier,salt,algorithm FROM human_credentials WHERE human_id=? AND disabled_at IS NULL",
            (owner["human_id"],),
        ).fetchone()
        stored_codes = [row["code_hash"] for row in conn.execute("SELECT code_hash FROM recovery_codes")]
        stored_session = conn.execute("SELECT token_hash,csrf_hash FROM auth_sessions WHERE session_id=?", (signed_in["session_id"],)).fetchone()
    assert credential["algorithm"] == "scrypt"
    assert credential["verifier"] != "correct horse battery staple"
    assert credential["salt"] != "correct horse battery staple"
    assert signed_in["session_token"] != stored_session["token_hash"]
    assert signed_in["csrf_token"] != stored_session["csrf_hash"]
    assert all(code.replace("-", "").casefold() not in stored_codes for code in recovery["codes"])

    recovered = lite_identity_auth.recover_with_code(
        username="owner-user",
        recovery_code=recovery["codes"][0],
        new_password="new correct horse battery staple",
        source="test",
    )
    assert recovered["session_token"]
    assert lite_identity_auth.authenticate_session_token(signed_in["session_token"]) is None
    with pytest.raises(lite_identity_auth.IdentityError) as reused:
        lite_identity_auth.recover_with_code(
            username="owner-user",
            recovery_code=recovery["codes"][0],
            new_password="another correct horse battery staple",
            source="test",
        )
    assert reused.value.reason_code == "identity_recovery_failed"


def test_identity_http_session_requires_csrf_for_writes(auth_runtime, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    deps.core.SETTINGS = deps.core.Settings(state_dir=auth_runtime)

    api = TestClient(load_fastapi_app())
    setup = api.post(
        "/api/lite/identity/setup",
        json={
            "username": "owner",
            "display_name": "Pocket Lab Owner",
            "password": "correct horse battery staple",
            "setup_token": "one-time-setup-token",
        },
    )
    assert setup.status_code == 201
    payload = setup.json()
    assert payload["authenticated"] is True
    assert payload["csrf_token"]
    cookies = setup.headers.get_list("set-cookie")
    assert any("pocketlab_session" in value and "HttpOnly" in value and "SameSite=strict" in value for value in cookies)
    assert any("pocketlab_csrf" in value and "HttpOnly" not in value and "SameSite=strict" in value for value in cookies)

    missing_csrf = api.post(
        "/api/lite/identity/password",
        json={
            "current_password": "correct horse battery staple",
            "new_password": "new correct horse battery staple",
        },
    )
    assert missing_csrf.status_code == 403
    assert _reason_code(missing_csrf) == "csrf_required"

    changed = api.post(
        "/api/lite/identity/password",
        headers={"X-Pocket-Lab-CSRF": payload["csrf_token"]},
        json={
            "current_password": "correct horse battery staple",
            "new_password": "new correct horse battery staple",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "changed"
    changed_text = json.dumps(changed.json())
    assert "correct horse battery staple" not in changed_text
    assert "new correct horse battery staple" not in changed_text
    assert "verifier" not in changed_text.casefold()
    assert "token_hash" not in changed_text.casefold()


def test_tokenless_loopback_write_bypass_is_removed(auth_runtime, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    monkeypatch.setenv("POCKETLAB_ALLOW_LOCAL_WRITE", "1")
    deps.core.SETTINGS = deps.core.Settings(state_dir=auth_runtime)
    api = TestClient(load_fastapi_app())

    response = api.post("/api/lite/policy/apply", json={"protection_enabled": True})
    assert response.status_code == 401
    assert _reason_code(response) == "authentication_required"


def test_catalog_policy_unavailable_fails_closed_before_nats(auth_runtime, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.routers import lite
    from api_fastapi.services import lite_policy_opa

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "service-test-token")
    deps.core.SETTINGS = deps.core.Settings(state_dir=auth_runtime)

    monkeypatch.setattr(
        lite.lite_catalog,
        "install_command",
        lambda *args, **kwargs: {
            "operation_id": "install-policy-test",
            "app_id": "photoprism",
            "target_node_id": "pocket-lab-lite-server",
            "dry_run": False,
        },
    )
    published = {"value": False}

    async def should_not_publish(*args, **kwargs):
        published["value"] = True
        raise AssertionError("NATS publish must not happen after a denied/unavailable policy decision")

    monkeypatch.setattr(lite, "submit_domain_command", should_not_publish)
    monkeypatch.setattr(lite_policy_opa, "_http_json", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))

    api = TestClient(load_fastapi_app(), headers={"Authorization": "Bearer service-test-token"})
    response = api.post("/api/lite/catalog/install", json={"app_id": "photoprism"})
    assert response.status_code == 503
    assert _reason_code(response) == "policy_unavailable"
    assert published["value"] is False

    from api_fastapi.db.connection import connection
    with connection() as conn:
        row = conn.execute("SELECT allow,reason_code,action_id FROM policy_decisions ORDER BY decision_row_id DESC LIMIT 1").fetchone()
    assert row["allow"] == 0
    assert row["reason_code"] == "policy_unavailable"
    assert row["action_id"] == "catalog.install"


def test_device_policy_denial_preserves_device_and_stops_before_retirement(auth_runtime, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services import lite_policy_opa

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "service-test-token")
    deps.core.SETTINGS = deps.core.Settings(state_dir=auth_runtime)
    deps.core.write_json_file(
        deps.settings().state_dir / "fleet.json",
        [
            {
                "id": "policy-denied-phone",
                "name": "Policy Denied Phone",
                "role": "compute",
                "status": "offline",
                "connection": "offline",
                "last_seen_at": "2025-01-01T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        lite_policy_opa,
        "_http_json",
        lambda *args, **kwargs: (
            200,
            {
                "result": {
                    "allow": False,
                    "constraints": ["authenticated_actor"],
                    "reason_code": "device_removal_policy_denied",
                    "policy_revision": "policy-test",
                }
            },
        ),
    )

    from api_fastapi.routers import lite
    lite.CONTROL_PLANE.prepared_read(
        domain="fleet",
        key="summary",
        builder=lite.lite_status.lite_fleet,
        projector=lite.CONTROL_PLANE.project_fleet,
        stale_after_ms=0,
        max_stale_ms=0,
        deadline_seconds=10.0,
    )
    api = TestClient(load_fastapi_app(), headers={"Authorization": "Bearer service-test-token"})
    assessment_response = api.get("/api/lite/devices/policy-denied-phone/removal-assessment")
    assert assessment_response.status_code == 200, assessment_response.text
    assessment = assessment_response.json()
    response = api.post(
        "/api/lite/fleet/remove-device",
        json={
            "device_id": "policy-denied-phone",
            "confirm": True,
            "assessment_revision": assessment["assessment_revision"],
            "expected_awareness_revision": assessment["awareness_revision"],
        },
    )
    assert response.status_code == 403
    assert _reason_code(response) == "policy_denied"
    fleet = api.get("/api/lite/fleet").json()
    assert any(item.get("id") == "policy-denied-phone" for item in fleet.get("devices", []))

    from api_fastapi.db.connection import connection
    with connection() as conn:
        row = conn.execute(
            "SELECT allow,reason_code,action_id FROM policy_decisions ORDER BY decision_row_id DESC LIMIT 1"
        ).fetchone()
    assert row["allow"] == 0
    assert row["reason_code"] == "device_removal_policy_denied"
    assert row["action_id"] == "device.remove"


def test_policy_adapter_rejects_invalid_response_and_records_bounded_metadata(auth_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_opa

    monkeypatch.setattr(lite_policy_opa, "_http_json", lambda *args, **kwargs: (200, {"result": {"allow": "yes"}}))
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as raised:
        lite_policy_opa.evaluate_authorization(
            auth_context={
                "actor": {"identity_id": "service", "type": "service", "display_name": "service"},
                "session": {"authenticated": True, "auth_method": "api_token"},
            },
            action_id="catalog.install",
            target_type="app",
            target_id="photoprism",
            target_revision="revision-test",
            target={"already_installed": False},
            correlation_id="corr-test",
        )
    assert raised.value.status_code == 503
    assert raised.value.decision["allow"] is False
    assert raised.value.decision["reason_code"] == "policy_invalid_response"


def test_vault_command_evidence_and_operation_projection_redact_material(auth_runtime):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services.action_queue import _prepare_domain_publish_bundle

    bundle = _prepare_domain_publish_bundle(
        "pocketlab.commands.vault.rotate",
        "vault.rotate.requested",
        {"target": "demo", "value": "super-secret-value", "nested": {"password": "also-secret"}},
        "trace-test",
    )
    evidence = bundle["evidence_payload"]
    assert evidence["value"] == "***REDACTED***"
    assert evidence["nested"]["password"] == "***REDACTED***"

    projected = deps._safe_operation_projection(
        {
            "operation": "rotate_secret",
            "stdout": '{"password":"super-secret-value"}',
            "artifacts": {"value": "super-secret-value", "password": "also-secret"},
        }
    )
    serialized = json.dumps(projected)
    assert "super-secret-value" not in serialized
    assert "also-secret" not in serialized


def test_identity_rules_frontend_and_opa_source_contracts():
    identity = Path("src/lite/LiteIdentity.jsx").read_text()
    rules = Path("src/lite/LiteRules.jsx").read_text()
    api = Path("src/lib/liteApi.js").read_text()
    rego = Path("security/policies/opa/pocketlab/pocketlab.rego").read_text()
    installer = Path("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-binaries.sh").read_text()
    start = Path("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh").read_text()

    assert "setupIdentity" in identity
    assert "loginIdentity" in identity
    assert "changeIdentityPassword" in identity
    assert "regenerateIdentityRecovery" in identity
    assert "rotateIdentity" not in identity
    assert "local-admin" not in identity
    assert "applyPolicy" not in rules
    assert "protection_enabled" not in rules
    assert "Policy engine" in rules
    assert "recent_decisions" in rules
    assert "localStorage" not in api[api.find("let liteCsrfToken"):api.find("export const liteApi")]
    assert 'input.action.id == "catalog.install"' in rego
    assert 'input.action.id == "device.remove"' in rego
    assert "06680087ed236c8c6aaa021660d83178db829a2ad30bdb3482481fada6791b2a" in installer
    assert "--addr=127.0.0.1:8181" in start
    assert "pocket-opa" in start


def _setup_owner_and_session(lite_identity_auth, *, source="expanded-tests"):
    owner = lite_identity_auth.setup_owner(
        username="owner",
        display_name="Pocket Lab Owner",
        password="correct horse battery staple",
        setup_token="one-time-setup-token",
    )
    signed_in = lite_identity_auth.login(
        username="owner",
        password="correct horse battery staple",
        source=source,
    )
    return owner, signed_in


def test_identity_login_failure_throttle_expiry_revocation_and_logout(auth_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_identity_auth

    lite_identity_auth._LOGIN_ATTEMPTS.clear()
    monkeypatch.setenv("POCKETLAB_IDENTITY_LOGIN_MAX_ATTEMPTS", "3")
    owner = lite_identity_auth.setup_owner(
        username="owner",
        display_name="Pocket Lab Owner",
        password="correct horse battery staple",
        setup_token="one-time-setup-token",
    )

    for _ in range(3):
        with pytest.raises(lite_identity_auth.IdentityError) as rejected:
            lite_identity_auth.login(username="owner", password="wrong-password-value", source="throttle-test")
        assert rejected.value.reason_code == "identity_login_failed"
    with pytest.raises(lite_identity_auth.IdentityError) as throttled:
        lite_identity_auth.login(username="owner", password="correct horse battery staple", source="throttle-test")
    assert throttled.value.reason_code == "identity_login_throttled"
    assert throttled.value.status_code == 429

    lite_identity_auth._LOGIN_ATTEMPTS.clear()
    first = lite_identity_auth.login(username="owner", password="correct horse battery staple", source="session-a")
    second = lite_identity_auth.login(username="owner", password="correct horse battery staple", source="session-b")
    assert lite_identity_auth.authenticate_session_token(first["session_token"])
    assert lite_identity_auth.revoke_session(human_id=owner["human_id"], session_id=first["session_id"])
    assert lite_identity_auth.authenticate_session_token(first["session_token"]) is None

    assert lite_identity_auth.logout(human_id=owner["human_id"], session_id=second["session_id"])
    assert lite_identity_auth.authenticate_session_token(second["session_token"]) is None

    expiring = lite_identity_auth.login(username="owner", password="correct horse battery staple", source="session-expire")
    with connection() as conn:
        conn.execute(
            "UPDATE auth_sessions SET idle_expires_at='2000-01-01T00:00:00Z' WHERE session_id=?",
            (expiring["session_id"],),
        )
        conn.commit()
    assert lite_identity_auth.authenticate_session_token(expiring["session_token"]) is None


def test_password_rotation_recovery_regeneration_and_audit_are_safe(auth_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_identity_auth

    owner, signed_in = _setup_owner_and_session(lite_identity_auth, source="password-test")
    before = lite_identity_auth.regenerate_recovery_codes(
        human_id=owner["human_id"], session_id=signed_in["session_id"]
    )
    after = lite_identity_auth.regenerate_recovery_codes(
        human_id=owner["human_id"], session_id=signed_in["session_id"]
    )
    with pytest.raises(lite_identity_auth.IdentityError) as old_batch:
        lite_identity_auth.recover_with_code(
            username="owner",
            recovery_code=before["codes"][0],
            new_password="recovery replacement password",
            source="old-batch",
        )
    assert old_batch.value.reason_code == "identity_recovery_failed"

    rotated = lite_identity_auth.change_password(
        human_id=owner["human_id"],
        session_id=signed_in["session_id"],
        current_password="correct horse battery staple",
        new_password="new correct horse battery staple",
    )
    assert lite_identity_auth.authenticate_session_token(signed_in["session_token"]) is None
    assert lite_identity_auth.authenticate_session_token(rotated["session_token"])
    with pytest.raises(lite_identity_auth.IdentityError) as old_password:
        lite_identity_auth.login(username="owner", password="correct horse battery staple", source="old-password")
    assert old_password.value.reason_code == "identity_login_failed"
    new_login = lite_identity_auth.login(username="owner", password="new correct horse battery staple", source="new-password")
    assert new_login["session_token"]

    with connection() as conn:
        batches = [dict(row) for row in conn.execute(
            "SELECT batch_id,invalidated_at FROM recovery_code_batches ORDER BY generation"
        )]
        events = [dict(row) for row in conn.execute(
            "SELECT event_type,reason_code,summary,correlation_id FROM identity_audit_events ORDER BY event_id"
        )]
    assert batches[0]["invalidated_at"] is not None
    serialized = json.dumps(events).casefold()
    for forbidden in (
        "correct horse battery staple",
        "new correct horse battery staple",
        before["codes"][0].casefold(),
        after["codes"][0].casefold(),
        "token_hash",
        "csrf_hash",
        "verifier",
    ):
        assert forbidden not in serialized


def test_policy_timeout_allow_status_and_bounded_fields(auth_runtime, monkeypatch, tmp_path):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_opa

    active = tmp_path / "opa-active"
    active.mkdir()
    (active / "revision.txt").write_text("revision-verified\n", encoding="utf-8")
    (active / "pocketlab.rego").write_text("package pocketlab.authz\n", encoding="utf-8")
    monkeypatch.setenv("POCKETLAB_OPA_ACTIVE_POLICY_DIR", str(active))

    def timeout(*args, **kwargs):
        raise TimeoutError("bounded timeout")

    monkeypatch.setattr(lite_policy_opa, "_http_json", timeout)
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as unavailable:
        lite_policy_opa.evaluate_authorization(
            auth_context={
                "actor": {"identity_id": "owner", "type": "human", "display_name": "Owner"},
                "session": {"authenticated": True, "auth_method": "password"},
            },
            action_id="catalog.install",
            target_type="app",
            target_id="x" * 500,
            target_revision="r" * 500,
            target={"password": "must-not-persist", "description": "z" * 2000},
            correlation_id="timeout-test",
        )
    assert unavailable.value.reason_code == "policy_unavailable"

    responses = {
        "/health": (200, {}),
        "/version": (200, {"version": "1.19.0"}),
        lite_policy_opa.OPA_DECISION_PATH: (
            200,
            {
                "result": {
                    "allow": True,
                    "constraints": ["authenticated_actor"],
                    "reason_code": "catalog_install_allowed",
                    "policy_revision": "revision-verified",
                }
            },
        ),
    }
    monkeypatch.setattr(lite_policy_opa, "_http_json", lambda method, path, *args, **kwargs: responses[path])
    allowed = lite_policy_opa.evaluate_authorization(
        auth_context={
            "actor": {"identity_id": "owner", "type": "human", "display_name": "Owner"},
            "session": {"authenticated": True, "auth_method": "password"},
        },
        action_id="catalog.install",
        target_type="app",
        target_id="photoprism",
        target_revision="revision-target",
        target={"already_installed": False},
        correlation_id="allow-test",
    )
    assert allowed["allow"] is True
    assert allowed["policy_revision"] == "revision-verified"
    status = lite_policy_opa.policy_status()
    assert status["status"] == "ready"
    assert status["engine"]["version"] == "1.19.0"
    assert status["active_policy"]["bundle_ready"] is True
    assert status["active_policy"]["package_status"] == "active"
    assert status["last_decision_at"]
    assert status["degraded_reason"] == ""

    with connection() as conn:
        recent = [dict(row) for row in conn.execute(
            "SELECT actor_id,target_id,target_revision,reason_code,policy_revision FROM policy_decisions ORDER BY decision_row_id"
        )]
    assert len(recent[-1]["target_id"]) <= 160
    assert len(recent[-1]["target_revision"]) <= 160
    assert "must-not-persist" not in json.dumps(recent)


def test_authenticated_allowed_catalog_install_reaches_submit_boundary(auth_runtime, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.routers import lite
    from api_fastapi.services import lite_policy_opa

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "service-test-token")
    deps.core.SETTINGS = deps.core.Settings(state_dir=auth_runtime)
    monkeypatch.setattr(
        lite.lite_catalog,
        "install_command",
        lambda *args, **kwargs: {
            "operation_id": "allowed-install",
            "command_id": "allowed-command",
            "app_id": "photoprism",
            "target_node_id": "pocket-lab-lite-server",
            "dry_run": False,
        },
    )
    monkeypatch.setattr(
        lite_policy_opa,
        "_http_json",
        lambda *args, **kwargs: (
            200,
            {"result": {"allow": True, "constraints": [], "reason_code": "catalog_install_allowed", "policy_revision": "allow-rev"}},
        ),
    )
    submitted = {"count": 0}

    async def submit(*args, **kwargs):
        submitted["count"] += 1
        return {"status": "queued", "operation_id": "allowed-install", "accepted": True}

    async def ready():
        return {"ready": True}

    monkeypatch.setattr(lite, "ensure_worker_execution_ready", ready)
    monkeypatch.setattr(lite, "submit_domain_command", submit)
    api = TestClient(load_fastapi_app(), headers={"Authorization": "Bearer service-test-token"})
    response = api.post("/api/lite/catalog/install", json={"app_id": "photoprism"})
    assert response.status_code == 202, response.text
    assert submitted["count"] == 1
    decision = response.json().get("authorization") or response.json().get("decision") or {}
    assert decision.get("reason_code") == "catalog_install_allowed"
    assert decision.get("policy_revision") == "allow-rev"
    from api_fastapi.db.connection import connection
    with connection() as conn:
        row = conn.execute("SELECT allow,reason_code FROM policy_decisions ORDER BY decision_row_id DESC LIMIT 1").fetchone()
    assert row["allow"] == 1
    assert row["reason_code"] == "catalog_install_allowed"


def test_device_hard_invariant_blocks_before_opa_and_revoked_human_cannot_mutate(auth_runtime, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.routers import lite
    from api_fastapi.services import lite_identity_auth, lite_policy_opa

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "service-test-token")
    deps.core.SETTINGS = deps.core.Settings(state_dir=auth_runtime)
    deps.core.write_json_file(
        deps.settings().state_dir / "fleet.json",
        [{"id": "pocket-lab-lite-server", "name": "Pocket Lab Lite Server", "role": "server", "status": "online", "connection": "online"}],
    )
    calls = {"opa": 0}

    def should_not_reach_opa(*args, **kwargs):
        calls["opa"] += 1
        return (200, {"result": {"allow": True, "constraints": [], "reason_code": "would_allow", "policy_revision": "rev"}})

    monkeypatch.setattr(lite_policy_opa, "_http_json", should_not_reach_opa)
    api = TestClient(load_fastapi_app(), headers={"Authorization": "Bearer service-test-token"})
    response = api.post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "pocket-lab-lite-server", "confirm": True},
    )
    assert response.status_code in {400, 403, 409}
    assert calls["opa"] == 0

    owner, signed_in = _setup_owner_and_session(lite_identity_auth, source="revoked-human")
    assert lite_identity_auth.revoke_session(human_id=owner["human_id"], session_id=signed_in["session_id"])
    human_api = TestClient(load_fastapi_app())
    human_api.cookies.set(lite_identity_auth.cookie_name(), signed_in["session_token"])
    human_api.cookies.set(lite_identity_auth.csrf_cookie_name(), signed_in["csrf_token"])
    blocked = human_api.post(
        "/api/lite/catalog/install",
        headers={"X-Pocket-Lab-CSRF": signed_in["csrf_token"]},
        json={"app_id": "photoprism"},
    )
    assert blocked.status_code == 401
    assert _reason_code(blocked) == "authentication_required"
