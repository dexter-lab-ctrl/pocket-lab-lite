from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


ensure_runtime_path()

from api_fastapi import deps  # noqa: E402
from api_fastapi.db.connection import reset_sqlite_path_cache  # noqa: E402
from api_fastapi.db.migrations import apply_migrations  # noqa: E402
from api_fastapi.db.runtime import SQLITE_READS  # noqa: E402
from api_fastapi.services import (  # noqa: E402
    lite_app_credentials,
    lite_app_governance,
    lite_app_registry,
)


def _verified_fleet(*, device_id: str = "pocket-lab-lite-server", capabilities: tuple[str, ...] = ("app_host", "compute")):
    return {
        "devices": [{
            "id": device_id,
            "role": "server_host",
            "protected_server_host": True,
            "connection": "online",
            "device_role_status": "active",
            "capability_states": [
                {"id": capability, "effective": True, "verification": "verified"}
                for capability in capabilities
            ],
        }]
    }


def test_semantic_compatibility_mapping_is_canonical_and_fail_closed():
    assert lite_app_governance.semantic_action("catalog.install") == "app.install"
    assert lite_app_governance.semantic_action("backup.create") == "app.backup.create"
    assert lite_app_governance.semantic_action("restore.preview") == "app.restore.preview"
    assert lite_app_governance.semantic_action("check_app") == "app.security_check"
    with pytest.raises(HTTPException):
        lite_app_governance.semantic_action("app.shell")


def test_resource_contract_derives_identity_capability_and_contract_revision(monkeypatch):
    from api_fastapi.services import lite_device_roles

    monkeypatch.setattr(lite_device_roles, "enrich_device_projection", lambda value: value)
    contract = lite_app_governance.resource_contract(
        "PhotoPrism",
        "app.install",
        fleet_payload=_verified_fleet(),
    )
    assert contract["resource_type"] == "app"
    assert contract["app_id"] == "photoprism"
    assert contract["semantic_action"] == "app.install"
    assert contract["required_capability"] == "install"
    assert contract["placement_required"] is True
    assert contract["placement"]["ready"] is True
    assert contract["target_device_id"] == "pocket-lab-lite-server"
    assert contract["request_fingerprint"] == contract["contract_revision"]
    assert len(contract["contract_revision"]) == 32


def test_resource_contract_rejects_capability_spoof_and_unverified_placement(monkeypatch):
    from dataclasses import replace
    from api_fastapi.services import lite_device_roles

    monkeypatch.setattr(lite_device_roles, "enrich_device_projection", lambda value: value)
    original_definition = lite_app_registry.app_definition
    production = original_definition("photoprism")
    without_repair = replace(
        production,
        capabilities=frozenset(item for item in production.capabilities if item != "repair"),
    )
    monkeypatch.setattr(
        lite_app_registry,
        "app_definition",
        lambda app_id: without_repair if str(app_id).lower() == "photoprism" else original_definition(app_id),
    )
    with pytest.raises(HTTPException) as unsupported:
        lite_app_governance.resource_contract("photoprism", "app.repair", fleet_payload=_verified_fleet())
    assert unsupported.value.status_code == 409
    assert unsupported.value.detail["status"] == "capability_not_supported"

    monkeypatch.setattr(lite_app_registry, "app_definition", original_definition)
    unverified = _verified_fleet(capabilities=("app_host",))
    with pytest.raises(HTTPException) as blocked:
        lite_app_governance.resource_contract(
            "photoprism",
            "app.install",
            fleet_payload=unverified,
            enforce_placement=True,
        )
    assert blocked.value.status_code == 409
    assert blocked.value.detail["reason_code"] == "required_device_capability_unverified"


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("Owner", {"app.install": "allow", "app.remove": "allow"}),
        ("Admin", {"app.install": "allow", "app.remove": "approval"}),
        ("Operator", {"app.install": "temporary_access", "app.remove": "approval"}),
        ("Auditor", {"app.install": "deny", "app.remove": "deny"}),
        ("Viewer", {"app.install": "deny", "app.remove": "deny"}),
    ],
)
def test_enterprise_roles_project_app_resource_authority(monkeypatch, role, expected):
    monkeypatch.setattr(
        lite_app_governance.lite_enterprise_identity,
        "enrich_auth_context",
        lambda value: {
            **value,
            "authorization": {
                "enterprise_enabled": True,
                "role": role,
                "membership_active": True,
                "authorization_version": 7,
                "owner_authority": role == "Owner",
            },
        },
    )
    projection = lite_app_governance.authority_projection(
        {"actor": {"type": "human", "identity_id": "human-test"}},
        app_id="photoprism",
    )
    actions = {item["action_id"]: item for item in projection["resources"][0]["actions"]}
    for action_id, mode in expected.items():
        assert actions[action_id]["mode"] == mode
    if role == "Operator":
        assert actions["app.install"]["allowed"] is False
        assert actions["app.install"]["requires_temporary_access"] is True


def test_personal_mode_preserves_local_owner_authority(monkeypatch):
    monkeypatch.setattr(
        lite_app_governance.lite_enterprise_identity,
        "enrich_auth_context",
        lambda value: {
            **value,
            "authorization": {
                "enterprise_enabled": False,
                "role": "Owner",
                "membership_active": True,
                "authorization_version": 1,
                "owner_authority": True,
            },
        },
    )
    projection = lite_app_governance.authority_projection(
        {"actor": {"type": "human", "identity_id": "owner"}},
        app_id="photoprism",
    )
    assert projection["mode"] == "personal"
    assert all(item["mode"] == "allow" for item in projection["resources"][0]["actions"])


def test_credential_metadata_never_accepts_or_projects_secret_values(tmp_path, monkeypatch):
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()

    result = lite_app_credentials.update_metadata(
        "photoprism",
        credential_id="app_sign_in",
        status="external_manual",
        management="external_or_manual",
    )
    rendered = json.dumps(result).lower()
    assert result["secret_values_stored_here"] is False
    assert result["secret_values_exposed"] is False
    assert "password" not in rendered
    assert "token" not in rendered
    assert "api_key" not in rendered
    assert "private_key" not in rendered

    with pytest.raises(HTTPException):
        lite_app_credentials.update_metadata(
            "photoprism",
            credential_id="../secret",
            status="configured",
        )


def test_generic_governance_services_do_not_hardcode_photoprism():
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_governance.py",
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_credentials.py",
    ):
        source = (root / relative).read_text(encoding="utf-8").lower()
        assert "photoprism" not in source, relative


def test_frontend_app_governance_boundaries_remain_control_api_only():
    root = Path(__file__).resolve().parents[2]
    frontend_paths = (
        root / "src/lib/liteApi.js",
        root / "src/lib/liteEnterpriseApi.js",
        root / "src/lite/catalog/AppCatalogScreen.jsx",
        root / "src/lite/LiteIdentityEnterprise.jsx",
        root / "src/lite/LiteRulesEnterprise.jsx",
        root / "src/lite/LiteRecovery.jsx",
    )
    forbidden = (
        "nats.connect",
        "jetstream(",
        "child_process",
        "subprocess",
        "pm2 ",
        "exec(",
        "spawn(",
    )
    for path in frontend_paths:
        source = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in source, (path, token)


def test_app_registry_public_contract_has_no_executable_manifest_fields():
    contract = lite_app_registry.public_registry()
    rendered = json.dumps(contract).lower()
    for forbidden in (
        "shell_command",
        "command_line",
        "executable_path",
        "pm2_command",
        "remote_host",
        "private_key",
        "refresh_token",
        "access_token",
        "database_url",
    ):
        assert forbidden not in rendered


def test_app_resource_policy_context_is_registry_derived_not_browser_claimed():
    root = Path(__file__).resolve().parents[2]
    router = (root / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py").read_text(encoding="utf-8")
    governance = (root / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_governance.py").read_text(encoding="utf-8")
    assert "lite_app_governance.resource_contract(" in router
    assert "lite_app_registry.app_definition(app_id)" in governance
    assert "required_capability" in governance
    assert "contract_revision" in governance


def test_simulation_contract_preserves_placement_requirement_without_enforcing_it(monkeypatch):
    from api_fastapi.services import lite_device_roles

    monkeypatch.setattr(lite_device_roles, "enrich_device_projection", lambda value: value)
    contract = lite_app_governance.resource_contract(
        "photoprism",
        "app.install",
        fleet_payload={"devices": []},
        require_placement=None,
        enforce_placement=False,
        operation_id="policy-simulation",
    )
    target = lite_app_governance.policy_target(contract)
    assert target["placement_required"] is True
    assert target["placement_ready"] is False
    assert target["operation_id"] == "policy-simulation"


def test_operator_projection_marks_exact_active_temporary_access(monkeypatch):
    from api_fastapi.services import lite_policy_approvals

    monkeypatch.setattr(
        lite_app_governance.lite_enterprise_identity,
        "enrich_auth_context",
        lambda value: {
            **value,
            "actor": {"type": "human", "identity_id": "human-operator"},
            "authorization": {
                "enterprise_enabled": True,
                "role": "Operator",
                "membership_active": True,
                "authorization_version": 3,
                "owner_authority": False,
            },
        },
    )
    original_contract = lite_app_governance.resource_contract
    monkeypatch.setattr(
        lite_app_governance,
        "resource_contract",
        lambda app_id, action_id, **_kwargs: {
            "app_id": "photoprism",
            "target_device_id": "pocket-lab-lite-server",
            "contract_revision": "contract-install-active",
        } if lite_app_governance.semantic_action(action_id) == "app.install" else original_contract(app_id, action_id, **_kwargs),
    )
    monkeypatch.setattr(
        lite_policy_approvals,
        "active_exception_details",
        lambda **kwargs: {
            "exception_id": "exc-active",
            "action_id": kwargs["action_id"],
            "app_id": kwargs["app_id"],
            "device_id": kwargs["device_id"],
            "required_capability": kwargs["required_capability"],
            "target_revision": kwargs["target_revision"],
            "expires_at": "2026-10-04T00:15:00Z",
            "status": "active",
        },
    )

    projection = lite_app_governance.authority_projection(
        {"actor": {"type": "human", "identity_id": "human-operator"}},
        app_id="photoprism",
    )
    resource = projection["resources"][0]
    install = next(item for item in resource["actions"] if item["action_id"] == "app.install")
    assert install["mode"] == "temporary_active"
    assert install["allowed"] is True
    assert install["requires_temporary_access"] is False
    assert install["temporary_access_active"] is True
    assert install["temporary_access_expires_at"] == "2026-10-04T00:15:00Z"
    assert resource["temporary_access"]["exception_id"] == "exc-active"


def test_sanitized_evidence_link_keeps_actor_reference_but_no_session_material():
    contract = {
        "app_id": "photoprism",
        "semantic_action": "app.security_check",
        "operation_id": "security-run-1",
        "contract_revision": "contract-security",
        "target_device_id": "pocket-lab-lite-server",
        "requested_actor": {"type": "human", "id": "human-owner"},
    }
    link = lite_app_governance.sanitized_evidence_link(
        contract,
        {"decision_id": "decision-1", "policy_revision": "policy-a"},
    )
    assert link["initiating_actor"] == {"type": "human", "id": "human-owner"}
    assert "session" not in link
    assert "token" not in json.dumps(link).lower()


def test_credential_metadata_cannot_claim_backend_secret_management(tmp_path, monkeypatch):
    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()

    with pytest.raises(HTTPException):
        lite_app_credentials.update_metadata(
            "photoprism",
            credential_id="app_sign_in",
            status="configured",
            management="pocket_lab_metadata",
        )


def test_governance_reference_persistence_is_whitelisted_and_secret_free():
    value = {
        "app_id": "photoprism",
        "semantic_action": "app.backup.create",
        "operation_id": "app-op-1",
        "authorization_decision_id": "decision-1",
        "policy_revision": "policy-1",
        "contract_revision": "contract-1",
        "target_device_id": "server",
        "initiating_actor": {"type": "human", "id": "human-owner", "session_id": "do-not-copy"},
        "token": "do-not-copy",
        "password": "do-not-copy",
    }
    clean = lite_app_governance.sanitize_governance_reference(value)
    assert clean["initiating_actor"] == {"type": "human", "id": "human-owner"}
    rendered = json.dumps(clean).lower()
    assert "session_id" not in rendered
    assert "token" not in rendered
    assert "password" not in rendered


def test_recovery_contract_declares_secret_safe_credential_backup_policy(monkeypatch):
    from api_fastapi.services import lite_app_backup, lite_app_credentials

    monkeypatch.setattr(
        lite_app_backup,
        "app_backup_status",
        lambda app_id: {
            "backup_supported": True,
            "restore_preview_supported": True,
            "restore_apply_supported": False,
            "profile": {"media_included": False},
            "latest_backup": None,
            "storage_target": {},
        },
    )
    monkeypatch.setattr(
        lite_app_credentials,
        "credential_status",
        lambda app_id: {"credentials": [], "secret_values_stored_here": False},
    )
    projection = lite_app_governance.recovery_projection("photoprism")
    assert projection["credential_backup_policy"] == {
        "app_backup": "neither",
        "workspace_database": "metadata_only",
        "secret_material": "not_stored",
    }
