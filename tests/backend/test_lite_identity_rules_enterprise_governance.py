from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


def _iso(offset_minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def governance_runtime(tmp_path, monkeypatch):
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


def _setup_enterprise_owner():
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth

    owner = lite_identity_auth.setup_owner(
        username="owner",
        display_name="Pocket Lab Owner",
        password="correct horse battery staple",
        setup_token="one-time-setup-token",
    )
    first = lite_identity_auth.login(username="owner", password="correct horse battery staple", source="governance-setup")
    first_context = lite_identity_auth.authenticate_session_token(first["session_token"])
    assert first_context
    lite_enterprise_identity.set_enterprise_enabled(auth_context=first_context, enabled=True, correlation_id="enable-enterprise")
    assert lite_identity_auth.authenticate_session_token(first["session_token"]) is None
    signed_in = lite_identity_auth.login(username="owner", password="correct horse battery staple", source="governance-enterprise")
    context = lite_identity_auth.authenticate_session_token(signed_in["session_token"])
    assert context
    return owner, signed_in, context


def _insert_person(*, human_id: str, username: str, role: str, status: str = "active") -> None:
    from api_fastapi.db.connection import begin_immediate, connection

    now = _iso()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                "INSERT INTO human_identities(human_id,username_normalized,display_name,status,auth_version,created_at,updated_at) VALUES (?,?,?,?,1,?,?)",
                (human_id, username, username.replace("-", " ").title(), status, now, now),
            )
            tx.execute(
                "INSERT INTO enterprise_memberships(human_id,role,status,authorization_version,created_at,updated_at) VALUES (?,?, 'active',1,?,?)",
                (human_id, role, now, now),
            )


def _context(human_id: str) -> dict:
    return {
        "actor": {"identity_id": human_id, "type": "human", "display_name": human_id},
        "session": {"session_id": f"session-{human_id}", "authenticated": True, "auth_method": "passkey", "assurance": []},
    }


def test_governance_migration_and_managed_enrollment_do_not_expose_person_tokens(governance_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_enterprise_enrollment, lite_enterprise_managed_enrollment

    _owner, _session, owner_context = _setup_enterprise_owner()
    created = lite_enterprise_enrollment.create_person(
        auth_context=owner_context,
        username="operator-one",
        display_name="Operator One",
        role="Operator",
        origin="http://localhost",
    )
    person = created["person"]
    assert person["status"] == "invited"
    assert person["role"] == "Operator"

    options = lite_enterprise_managed_enrollment.registration_options(
        auth_context=owner_context,
        human_id=person["human_id"],
        origin="http://localhost",
    )
    serialized = json.dumps(options).lower()
    assert options["person"]["human_id"] == person["human_id"]
    assert options["publicKey"]["rp"]["id"] == "localhost"
    assert "claim_url" not in serialized
    assert "person_claim" not in serialized
    assert "session_token" not in serialized

    with connection() as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        events = [dict(item) for item in conn.execute("SELECT event_type,reason_code,summary,correlation_id FROM identity_audit_events ORDER BY event_id")]
    assert "human_enrollment_claims" in tables
    assert "session_token" not in json.dumps(events).lower()


def test_enrollment_origin_duplicate_and_admin_privilege_boundaries(governance_runtime):
    from api_fastapi.services import lite_enterprise_enrollment, lite_enterprise_managed_enrollment, lite_webauthn

    _owner, _session, owner_context = _setup_enterprise_owner()
    created = lite_enterprise_enrollment.create_person(
        auth_context=owner_context,
        username="admin-one",
        display_name="Admin One",
        role="Admin",
        origin="http://localhost",
    )
    with pytest.raises(lite_enterprise_enrollment.EnrollmentError) as duplicate:
        lite_enterprise_enrollment.create_person(
            auth_context=owner_context,
            username="ADMIN_ONE",
            display_name="Duplicate",
            role="Viewer",
            origin="http://localhost",
        )
    assert duplicate.value.reason_code == "identity_username_exists"

    # Managed WebAuthn enrollment uses the current trusted Pocket Lab origin.
    # Non-localhost HTTP origins are rejected before any challenge is created.
    with pytest.raises(lite_webauthn.WebAuthnError) as insecure_origin:
        lite_enterprise_managed_enrollment.registration_options(
            auth_context=owner_context,
            human_id=created["person"]["human_id"],
            origin="http://example.invalid",
        )
    assert insecure_origin.value.reason_code == "webauthn_secure_origin_required"

    # Promote the invited Admin to an active identity for authorization tests.
    from api_fastapi.db.connection import connection
    with connection() as conn:
        conn.execute("UPDATE human_identities SET status='active' WHERE human_id=?", (created["person"]["human_id"],))
        conn.commit()
    admin_context = _context(created["person"]["human_id"])
    with pytest.raises(lite_enterprise_enrollment.EnrollmentError) as privilege_escalation:
        lite_enterprise_enrollment.create_person(
            auth_context=admin_context,
            username="second-owner",
            display_name="Second Owner",
            role="Owner",
            origin="http://localhost",
        )
    assert privilege_escalation.value.reason_code == "enterprise_owner_authority_required"


def test_shared_access_projection_keeps_identity_and_rules_role_truth_synchronized(governance_runtime):
    from api_fastapi.services import lite_enterprise_governance

    owner, _session, owner_context = _setup_enterprise_owner()
    for role in ("Admin", "Operator", "Auditor", "Viewer"):
        _insert_person(human_id=f"human-{role.lower()}", username=f"person-{role.lower()}", role=role)

    owner_access = lite_enterprise_governance.access_projection(owner_context)
    assert owner_access["current_role"] == "Owner"
    assert owner_access["owner_authority"] is True
    assert owner_access["capabilities"]["device.remove.mode"] == "allow"
    assert owner_access["capabilities"]["device.remove.requires_approval"] is False
    assert owner_access["capabilities"]["rules.activate.mode"] == "step_up"
    assert owner_access["capabilities"]["rules.activate.requires_step_up"] is True
    assert owner_access["topology"]["active_owners"] == 1

    admin = lite_enterprise_governance.access_projection(_context("human-admin"))
    operator = lite_enterprise_governance.access_projection(_context("human-operator"))
    auditor = lite_enterprise_governance.access_projection(_context("human-auditor"))
    viewer = lite_enterprise_governance.access_projection(_context("human-viewer"))
    assert admin["capabilities"]["device.remove.mode"] == "approval"
    assert operator["capabilities"]["device.remove.mode"] == "approval"
    assert auditor["capabilities"]["rules.simulate.mode"] == "allow"
    assert auditor["capabilities"]["rules.draft.mode"] == "deny"
    assert viewer["capabilities"]["evidence.read.mode"] == "allow"
    assert viewer["capabilities"]["rules.simulate.mode"] == "deny"

    matrix = {row["action_id"]: row for row in owner_access["action_matrix"]}
    assert matrix["device.remove"]["roles"] == {
        "Owner": "allow", "Admin": "approval", "Operator": "approval", "Auditor": "deny", "Viewer": "deny"
    }
    assert owner["human_id"]


def test_final_owner_is_protected_and_role_change_revokes_authorization(governance_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth

    owner, signed_in, owner_context = _setup_enterprise_owner()
    with pytest.raises(lite_enterprise_identity.EnterpriseIdentityError) as final_owner:
        lite_enterprise_identity.set_membership(
            auth_context=owner_context,
            human_id=owner["human_id"],
            role="Admin",
            membership_status="active",
        )
    assert final_owner.value.reason_code == "enterprise_final_owner_protected"

    _insert_person(human_id="human-admin", username="admin-person", role="Admin")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            session = lite_identity_auth._insert_session(tx, human={"human_id": "human-admin", "auth_version": 1}, method="passkey")
            tx.execute(
                """INSERT INTO policy_temporary_exceptions(exception_id,action_id,app_id,device_id,human_id,policy_revision,reason,created_by_human_id,status,created_at,expires_at)
                   VALUES ('exc-role-change','catalog.install','photoprism','phone','human-admin','revision-test','short maintenance','human-admin','active',?,?)""",
                (_iso(), _iso(30)),
            )
    assert lite_identity_auth.authenticate_session_token(session["session_token"])

    changed = lite_enterprise_identity.set_membership(
        auth_context=owner_context,
        human_id="human-admin",
        role="Operator",
        membership_status="active",
    )
    assert changed["member"]["role"] == "Operator"
    assert lite_identity_auth.authenticate_session_token(session["session_token"]) is None
    with connection() as conn:
        exception = conn.execute("SELECT status FROM policy_temporary_exceptions WHERE exception_id='exc-role-change'").fetchone()
    assert exception["status"] == "revoked"
    assert lite_identity_auth.authenticate_session_token(signed_in["session_token"])


def test_enterprise_mode_is_reversible_and_closes_enterprise_only_continuations(governance_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_enterprise_enrollment, lite_enterprise_identity, lite_identity_auth

    _owner, signed_in, owner_context = _setup_enterprise_owner()
    invited = lite_enterprise_enrollment.create_person(
        auth_context=owner_context,
        username="operator-two",
        display_name="Operator Two",
        role="Operator",
        origin="http://localhost",
    )["person"]
    with connection() as conn:
        conn.execute(
            """INSERT INTO policy_approvals(approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,initiating_human_id,initiating_role,required_approver_roles_json,required_assurance,policy_revision,status,created_at,expires_at,reason_code,evidence_ref)
               VALUES ('apr-mode','decision-mode','corr-mode','device.remove','device','old-phone',?,'Operator','[\"Admin\",\"Owner\"]','policy.approval.device.remove','revision-test','pending',?,?,'approval_required','policy:decision-mode')""",
            (invited["human_id"], _iso(), _iso(15)),
        )
        conn.execute(
            """INSERT INTO policy_temporary_exceptions(exception_id,action_id,app_id,device_id,human_id,policy_revision,reason,created_by_human_id,status,created_at,expires_at)
               VALUES ('exc-mode','catalog.install','photoprism','phone',?,'revision-test','short maintenance',?,'active',?,?)""",
            (invited["human_id"], owner_context["actor"]["identity_id"], _iso(), _iso(30)),
        )
        conn.commit()

    preview = lite_enterprise_identity.mode_preview(auth_context=owner_context, enabled=False)
    assert preview["target_mode"] == "personal"
    assert preview["pending_approvals"] == 1
    assert preview["active_exceptions"] == 1

    disabled = lite_enterprise_identity.set_enterprise_enabled(auth_context=owner_context, enabled=False, correlation_id="disable-enterprise")
    assert disabled["enabled"] is False
    assert disabled["continuations"] == {"approvals_cancelled": 1, "exceptions_revoked": 1}
    assert lite_identity_auth.authenticate_session_token(signed_in["session_token"]) is None
    with connection() as conn:
        membership = conn.execute("SELECT role,status FROM enterprise_memberships WHERE human_id=?", (invited["human_id"],)).fetchone()
        approval = conn.execute("SELECT status FROM policy_approvals WHERE approval_id='apr-mode'").fetchone()
        exception = conn.execute("SELECT status FROM policy_temporary_exceptions WHERE exception_id='exc-mode'").fetchone()
    assert dict(membership) == {"role": "Operator", "status": "active"}
    assert approval["status"] == "cancelled"
    assert exception["status"] == "revoked"

    personal_login = lite_identity_auth.login(username="owner", password="correct horse battery staple", source="personal-reenable")
    personal_context = lite_identity_auth.authenticate_session_token(personal_login["session_token"])
    assert personal_context
    enabled = lite_enterprise_identity.set_enterprise_enabled(auth_context=personal_context, enabled=True, correlation_id="reenable-enterprise")
    assert enabled["enabled"] is True
    with connection() as conn:
        retained = conn.execute("SELECT role,status FROM enterprise_memberships WHERE human_id=?", (invited["human_id"],)).fetchone()
    assert dict(retained) == {"role": "Operator", "status": "active"}


def test_typed_rules_candidate_owner_step_up_and_health_roles(governance_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_enterprise_governance, lite_policy_analysis, lite_policy_lifecycle, lite_policy_opa

    owner, _session, owner_context = _setup_enterprise_owner()
    _insert_person(human_id="human-operator", username="operator-person", role="Operator")
    _insert_person(human_id="human-auditor", username="auditor-person", role="Auditor")
    _insert_person(human_id="human-viewer", username="viewer-person", role="Viewer")

    lite_enterprise_governance.ensure_policy_templates()
    created = lite_policy_lifecycle.create_revision(
        auth_context=owner_context,
        template_id="enterprise_governance",
        parameters={"admin_device_remove_approval": 1, "operator_device_remove_approval": 1},
        change_summary="Keep independent review for delegated device retirement.",
    )
    revision_id = created["revision"]["revision_id"]
    assert created["revision"]["template_id"] == "enterprise_governance"
    assert "canonical_parameters_json" not in created["revision"]
    with connection() as conn:
        raw = conn.execute("SELECT canonical_parameters_json FROM policy_revisions WHERE revision_id=?", (revision_id,)).fetchone()
        conn.execute(
            "INSERT OR REPLACE INTO policy_runtime_state(state_id,active_revision_id,known_good_revision_id,updated_at) VALUES (1,?,?,?)",
            (revision_id, revision_id, _iso()),
        )
        conn.commit()
    assert json.loads(raw["canonical_parameters_json"]) == {"admin_device_remove_approval": 1, "operator_device_remove_approval": 1}

    with pytest.raises(lite_enterprise_governance.GovernanceError) as needs_step_up:
        lite_enterprise_governance.require_recent_assurance(owner_context, "policy.rules.activate")
    assert needs_step_up.value.reason_code == "owner_step_up_required"
    assert needs_step_up.value.status_code == 428

    assured = {**owner_context, "session": {**owner_context["session"], "assurance": [{"purpose": "policy.rules.activate", "expires_at": _iso(5)}]}}
    _context_result, actor_id = lite_enterprise_governance.require_recent_assurance(assured, "policy.rules.activate")
    assert actor_id == owner["human_id"]

    monkeypatch.setattr(lite_policy_opa, "_safe_revision", lambda: revision_id)
    monkeypatch.setattr(lite_policy_opa, "_observed_opa_revision", lambda: revision_id)
    monkeypatch.setattr(lite_policy_opa, "_opa_endpoint_is_loopback", lambda: True)
    operator_health = lite_policy_analysis.health(auth_context=_context("human-operator"))
    viewer_health = lite_policy_analysis.health(auth_context=_context("human-viewer"))
    auditor_health = lite_policy_analysis.health(auth_context=_context("human-auditor"))
    assert operator_health["consistency_state"] == "ready"
    assert operator_health["analysis_status"] == "not_authorized"
    assert viewer_health["consistency_state"] == "ready"
    assert viewer_health["analysis_status"] == "not_authorized"
    assert auditor_health["analysis_status"] == "complete"
    assert "Auditor" in lite_policy_analysis.SIMULATE_ROLES


def test_enterprise_api_projects_access_people_typed_rules_and_root_step_up(governance_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_identity_auth

    _owner, _session, _context_owner = _setup_enterprise_owner()
    api = TestClient(load_fastapi_app(), base_url="http://localhost")
    login = api.post("/api/lite/identity/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200, login.text
    csrf = login.json()["csrf_token"]

    access = api.get("/api/lite/enterprise/access")
    assert access.status_code == 200, access.text
    assert access.json()["current_role"] == "Owner"
    assert access.json()["capabilities"]["device.remove.mode"] == "allow"

    people = api.post(
        "/api/lite/enterprise/identity/people",
        headers={"X-Pocket-Lab-CSRF": csrf},
        json={"username": "api-operator", "display_name": "API Operator", "role": "Operator"},
    )
    assert people.status_code == 201, people.text
    person_payload = people.json()
    assert person_payload["person"]["status"] == "invited"
    assert "invite" not in person_payload
    assert "claim" not in json.dumps(person_payload).lower()
    human_id = person_payload["person"]["human_id"]

    managed_options = api.post(
        f"/api/lite/enterprise/identity/people/{human_id}/passkey/options",
        headers={"X-Pocket-Lab-CSRF": csrf},
    )
    assert managed_options.status_code == 200, managed_options.text
    managed_serialized = json.dumps(managed_options.json()).lower()
    assert managed_options.json()["person"]["human_id"] == human_id
    assert "claim_url" not in managed_serialized
    assert "person_claim" not in managed_serialized
    assert "session_token" not in managed_serialized

    templates = api.get("/api/lite/enterprise/rules/templates")
    assert templates.status_code == 200, templates.text
    assert templates.json()["free_form_rego"] is False
    assert templates.json()["templates"][0]["template_id"] == "enterprise_governance"

    candidate = api.post(
        "/api/lite/enterprise/rules/revisions",
        headers={"X-Pocket-Lab-CSRF": csrf},
        json={
            "template_id": "enterprise_governance",
            "parameters": {"admin_device_remove_approval": True, "operator_device_remove_approval": False},
            "change_summary": "Allow Operators to retire validated stale lab devices directly.",
        },
    )
    assert candidate.status_code == 201, candidate.text
    revision_id = candidate.json()["revision"]["revision_id"]
    assert candidate.json()["revision"]["lifecycle_status"] == "draft"

    activation = api.post(
        "/api/lite/enterprise/rules/activations",
        headers={"X-Pocket-Lab-CSRF": csrf},
        json={"revision_id": revision_id},
    )
    assert activation.status_code == 428, activation.text
    assert "owner_step_up_required" in activation.text

    mode_change = api.put(
        "/api/lite/enterprise/identity/mode",
        headers={"X-Pocket-Lab-CSRF": csrf},
        json={"enabled": False},
    )
    assert mode_change.status_code == 428, mode_change.text
    assert "owner_step_up_required" in mode_change.text

    # Browser-facing responses and sanitized audit evidence must never expose a
    # person enrollment bearer secret.
    with connection() as conn:
        audit = json.dumps([dict(row) for row in conn.execute("SELECT event_type,reason_code,summary,correlation_id FROM identity_audit_events")]).lower()
    assert "claim_url" not in audit
    assert "session_token" not in audit
    assert lite_identity_auth.authenticate_session_token(login.cookies.get("pocketlab_session", "")) is not None


def test_viewer_can_read_sanitized_decision_evidence_but_cannot_mutate_rules(governance_runtime):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_identity_auth

    _setup_enterprise_owner()
    _insert_person(human_id="human-viewer", username="viewer-person", role="Viewer")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            session = lite_identity_auth._insert_session(tx, human={"human_id": "human-viewer", "auth_version": 1}, method="passkey")
            tx.execute(
                """INSERT INTO policy_decisions(occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (_iso(), "decision-viewer", "corr-viewer", "human", "human-owner", "device.remove", "device", "old-phone", "assessment", 1, "owner_authority_device_removal", "revision-test", 0.4),
            )

    api = TestClient(load_fastapi_app(), base_url="http://localhost")
    api.cookies.set(lite_identity_auth.cookie_name(), session["session_token"])
    decisions = api.get("/api/lite/enterprise/rules/decisions")
    assert decisions.status_code == 200, decisions.text
    serialized = json.dumps(decisions.json()).lower()
    assert "decision-viewer" in serialized
    for forbidden in ("session_token", "token_hash", "csrf_hash", "password", "authenticator"):
        assert forbidden not in serialized

    templates = api.get("/api/lite/enterprise/rules/templates")
    assert templates.status_code == 200
    denied = api.post(
        "/api/lite/enterprise/rules/revisions",
        headers={"X-Pocket-Lab-CSRF": "not-a-valid-csrf"},
        json={"template_id": "enterprise_governance", "parameters": {}, "change_summary": "Viewer must not mutate Rules."},
    )
    assert denied.status_code in {403, 422}


def test_frontend_contract_uses_unified_identity_rules_story_help_and_no_browser_authority():
    identity = Path("src/lite/LiteIdentity.jsx").read_text(encoding="utf-8")
    identity_enterprise = Path("src/lite/LiteIdentityEnterprise.jsx").read_text(encoding="utf-8")
    rules = Path("src/lite/LiteRules.jsx").read_text(encoding="utf-8")
    rules_enterprise = Path("src/lite/LiteRulesEnterprise.jsx").read_text(encoding="utf-8")
    help_component = Path("src/lite/LiteHelp.jsx").read_text(encoding="utf-8")
    api = Path("src/lib/liteEnterpriseApi.js").read_text(encoding="utf-8")
    identity_stories = Path("src/lite/LiteIdentity.stories.jsx").read_text(encoding="utf-8")
    rules_stories = Path("src/lite/LiteRules.stories.jsx").read_text(encoding="utf-8")

    assert "identitySelf" in identity
    assert "LiteIdentityEnterprise" in identity
    assert "LiteHelp" in identity and "LiteHelp" in rules and "LiteHelp" in rules_enterprise
    assert "People, roles and Safety Rules use the same server-owned authority model" in identity_enterprise
    assert "enterprise_governance" in rules_enterprise
    assert "browser cannot submit Rego source" in rules_enterprise
    assert "policy.rules.activate" in rules_enterprise
    assert "Restore known-good Rules" in rules_enterprise
    assert "rules/activations" in api and "identity/people" in api and "enterprise/access" in api
    assert "managedPersonPasskeyOptions" in api and "verifyManagedPersonPasskey" in api
    assert "localStorage" not in api
    assert "LITE_CONTEXT_HELP_READY" in help_component
    for role in ("EnterpriseOwner", "EnterpriseAdmin", "EnterpriseOperator", "EnterpriseAuditor", "EnterpriseViewer"):
        assert role in identity_stories
    for story in ("EnterpriseOwnerProtection", "EnterpriseAdminReview", "EnterpriseOperatorReview", "EnterpriseAuditorReadOnly", "EnterpriseViewerReadOnly"):
        assert story in rules_stories
    assert "applyPolicy" not in rules
    assert "package pocketlab" not in rules_enterprise
