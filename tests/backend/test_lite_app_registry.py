from __future__ import annotations

from dataclasses import replace

import pytest

from pocket_lab_test_utils import ensure_runtime_path


ensure_runtime_path()

from api_fastapi.services import lite_app_adapters, lite_app_registry  # noqa: E402


def _example(**overrides):
    base = lite_app_registry.app_definition("photoprism")
    values = {
        "id": "example-app",
        "name": "Example App",
        "category": "Test",
        "summary": "Synthetic test-only app.",
        "adapter": "example",
        "route": "/apps/example-app/",
        "upstream": "127.0.0.1:2999",
        "process": "pocketlab-app-example",
        "platforms": ("android-termux-arm64",),
        "capabilities": frozenset({"open"}),
        "actions": {
            "open": {
                "label": "Open",
                "category": "access",
                "summary": "Open the synthetic app.",
                "risk": "low",
            }
        },
        "presentation": {},
    }
    values.update(overrides)
    return replace(base, **values)


def test_registry_exposes_versioned_photoprism_contract():
    registry = lite_app_registry.public_registry()

    assert registry["schema_version"] == 1
    assert registry["count"] >= 1
    photoprism = next(item for item in registry["apps"] if item["id"] == "photoprism")
    assert photoprism["name"] == "PhotoPrism"
    assert photoprism["capabilities"]["open"] is True
    assert photoprism["capabilities"]["security_check"] is True
    assert "adapter" not in photoprism
    assert "upstream" not in photoprism
    assert "process" not in photoprism


@pytest.mark.parametrize(
    "value",
    ["../foo", "foo/bar", "foo?x=y", "foo#fragment", "%2e%2e", "/absolute"],
)
def test_registry_rejects_unsafe_app_ids(value):
    with pytest.raises(Exception):
        lite_app_registry.normalize_app_id(value)


def test_registry_normalizes_case_without_changing_route_identity():
    assert lite_app_registry.normalize_app_id("PhotoPrism") == "photoprism"


def test_registry_rejects_duplicate_ids():
    app = _example()
    with pytest.raises(RuntimeError, match="Duplicate app id"):
        lite_app_registry.validate_test_definitions((app, app))


def test_registry_rejects_duplicate_routes():
    first = _example(id="example-one", route="/apps/example-one/")
    second = _example(id="example-two", route="/apps/example-one/")
    with pytest.raises(RuntimeError, match="must own exactly|Duplicate app route"):
        lite_app_registry.validate_test_definitions((first, second))


def test_registry_rejects_route_escape():
    with pytest.raises(RuntimeError, match="must own exactly"):
        lite_app_registry.validate_test_definitions(
            (_example(route="/api/lite/apps/example-app/"),)
        )


@pytest.mark.parametrize(
    "upstream",
    [
        "https://example.invalid:443",
        "0.0.0.0:2999",
        "192.168.1.10:2999",
        "127.0.0.1:0",
        "127.0.0.1:70000",
        "127.0.0.1:2999/path",
    ],
)
def test_registry_rejects_non_loopback_or_invalid_upstream_bindings(upstream):
    with pytest.raises(RuntimeError, match="loopback"):
        lite_app_registry.validate_test_definitions((_example(upstream=upstream),))


def test_registry_rejects_action_without_required_capability():
    with pytest.raises(RuntimeError, match="requires capability"):
        lite_app_registry.validate_test_definitions(
            (
                _example(
                    capabilities=frozenset({"open"}),
                    actions={
                        "backup_app": {
                            "label": "Back up app",
                            "category": "recovery",
                            "summary": "Synthetic backup action.",
                            "risk": "low",
                        }
                    },
                ),
            )
        )


def test_platform_support_is_explicit_and_fail_closed():
    assert lite_app_registry.platform_supported("photoprism", "android-termux-arm64") is True
    assert lite_app_registry.platform_supported("photoprism", "ubuntu-dev") is True
    assert lite_app_registry.platform_supported("photoprism", "unsupported") is False


def test_registry_does_not_store_shell_commands_or_secrets():
    rendered = repr(lite_app_registry.public_registry()).lower()

    assert "bash -c" not in rendered
    assert "subprocess" not in rendered
    assert "password" not in rendered
    assert "api_key" not in rendered
    assert "private key" not in rendered


def test_photoprism_adapter_binding_is_explicit_and_fail_closed():
    adapter = lite_app_adapters.adapter_for("photoprism")

    assert adapter.app_id == "photoprism"

    synthetic = _example(adapter="missing-adapter")
    registry = lite_app_registry.validate_test_definitions((synthetic,))
    assert registry["example-app"].adapter == "missing-adapter"


def test_adapter_service_bindings_are_explicit_and_metadata_is_not_execution():
    assert lite_app_adapters.supports_service("photoprism", "actions") is True
    assert lite_app_adapters.supports_service("photoprism", "backup") is True
    assert lite_app_adapters.supports_service("photoprism", "not-a-service") is False
    assert lite_app_adapters.supports_service("example-app", "actions") is False


def test_photoprism_adapter_owns_end_to_end_projection_and_special_action_hooks():
    adapter = lite_app_adapters.adapter_for("photoprism")

    for method_name in (
        "catalog_payload",
        "lifecycle_profile",
        "security_profile",
        "security_scan_contract",
        "backup_profile",
        "backup_policy",
        "update_status",
        "update_receipt",
        "update_apply_disabled",
        "media_status",
        "media_import_blocked",
        "prepare_special_action",
        "record_special_action_queued",
        "discard_special_action_queued",
    ):
        assert callable(getattr(adapter, method_name, None)), method_name

    assert lite_app_adapters.supports_service("photoprism", "catalog") is True
    assert lite_app_adapters.supports_service("photoprism", "lifecycle") is True
    assert lite_app_adapters.supports_service("photoprism", "security_profile") is True
    assert lite_app_adapters.supports_service("photoprism", "backup_profile") is True
    assert lite_app_adapters.supports_service("photoprism", "security_scan") is True
    assert lite_app_adapters.supports_service("photoprism", "update_readiness") is True


def test_photoprism_security_scan_contract_is_bounded_and_relative():
    contract = lite_app_adapters.adapter_for("photoprism").security_scan_contract()

    assert contract["app_id"] == "photoprism"
    assert contract["route"] == "/apps/photoprism/"
    assert contract["process_name"] == "pocketlab-app-photoprism"
    for key in ("proot_app_path", "proot_binary_path", "config_relative"):
        value = str(contract[key])
        assert not value.startswith("/")
        assert ".." not in value.split("/")
    rendered = repr(contract).lower()
    assert "originals" in rendered
    assert "import" in rendered
    assert "thumbnail" in rendered


def test_photoprism_backup_policy_keeps_user_media_out_by_default():
    policy = lite_app_adapters.adapter_for("photoprism").backup_policy()

    assert policy["media_included_by_default"] is False
    assert policy["restore_apply_supported"] is False
    assert "original_media" in policy["excluded_sets"]
    assert "raw_secrets" in policy["excluded_sets"]


def test_action_contract_is_registry_owned():
    ids = lite_app_registry.registered_action_ids("photoprism")

    assert {"open", "install_app", "repair_app", "backup_app", "remove_app"} <= ids
    assert lite_app_registry.action_definition("photoprism", "open")["risk"] == "low"
    assert lite_app_registry.action_definition("photoprism", "does_not_exist") is None


def test_synthetic_second_app_proves_multi_app_registry_without_production_enablement():
    production = lite_app_registry.app_definition("photoprism")
    synthetic = _example(
        capabilities=frozenset({"open"}),
        actions={
            "open": {
                "label": "Open",
                "category": "access",
                "summary": "Open the synthetic app.",
                "risk": "low",
            }
        },
    )

    registry = lite_app_registry.validate_test_definitions((production, synthetic))

    assert tuple(sorted(registry)) == ("example-app", "photoprism")
    assert registry["example-app"].capabilities == frozenset({"open"})
    assert "backup_app" not in registry["example-app"].actions
    assert "example-app" not in lite_app_registry.app_ids()


def test_unknown_app_fails_closed():
    with pytest.raises(Exception):
        lite_app_registry.app_definition("unknown-app")
