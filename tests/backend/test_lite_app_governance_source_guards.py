from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_generic_app_governance_layers_do_not_hardcode_photoprism_or_executable_manifest_fields():
    generic = "\n".join(
        _read(path)
        for path in (
            "pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_governance.py",
            "pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_credentials.py",
        )
    ).lower()
    assert "photoprism" not in generic
    for forbidden in ("shell_command", "pm2_command", "executable_path", "remote_host"):
        assert forbidden not in generic


def test_frontend_app_governance_has_no_direct_nats_pm2_shell_or_secret_projection():
    source = "\n".join(
        _read(path)
        for path in (
            "src/lib/liteApi.js",
            "src/lib/liteViewModels.js",
            "src/lite/catalog/AppCatalogScreen.jsx",
            "src/lite/LiteIdentityEnterprise.jsx",
            "src/lite/LiteRulesEnterprise.jsx",
            "src/lite/LiteRecovery.jsx",
        )
    ).lower()
    assert "nats://" not in source
    assert "pm2 " not in source
    assert "child_process" not in source
    assert "exec(" not in source
    for secret_field in ("refresh_token", "access_token", "private_key", "database_url", "restic_password"):
        assert secret_field not in source


def test_router_resolves_app_identity_before_policy_credential_recovery_handlers():
    source = _read("pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py")
    assert "lite_app_governance.resource_contract(" in source
    assert "lite_app_registry.app_definition(app_id)" in source
    assert "lite_app_credentials.update_metadata(" in source
    assert "_authorize_app_resource(" in source


def test_legacy_catalog_install_is_routed_through_canonical_app_install_governance():
    source = _read("pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py")
    marker = '@router.post("/catalog/install"'
    start = source.index(marker)
    end = source.index('@router.post("/catalog/remove"', start)
    route = source[start:end]
    assert 'action_id="app.install"' in route
    assert 'action_id="catalog.install"' not in route
