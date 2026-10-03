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
