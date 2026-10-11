import pytest
from runtime.api_fastapi.services.lite_app_registry import load_app_registry, validate_app_definition, project_registered_catalog

BASE = {"schema_version":1,"id":"example-app","name":"Example","adapter":"example","route":"/apps/example-app/","platforms":["termux"],"capabilities":["open"]}

def test_production_registry_is_photoprism_only():
    assert list(load_app_registry()) == ["photoprism"]

@pytest.mark.parametrize("app_id", ["../foo", "foo/bar", "foo?x=y", "%2e%2e", "/absolute", "Foo", "foo_bar"])
def test_reject_unsafe_identity(app_id):
    with pytest.raises(ValueError):
        validate_app_definition({**BASE,"id":app_id},allowed_adapters=frozenset({"example"}))

def test_synthetic_adapter_is_test_only():
    assert "example-app" in load_app_registry([BASE],allowed_adapters=frozenset({"example"}))
    with pytest.raises(ValueError):
        load_app_registry([BASE])

def test_duplicate_and_route_conflict_fail_closed():
    with pytest.raises(ValueError):
        load_app_registry([BASE,BASE],allowed_adapters=frozenset({"example"}))

def test_unsupported_projection_has_no_actions():
    payload={"apps":[{"id":"rogue","actions":{"install":True}},{"id":"photoprism","actions":{"open":True}}]}
    result=project_registered_catalog(payload)
    assert result["apps"][0]["actions"] == {}
    assert result["apps"][1]["adapter"] == "photoprism"
