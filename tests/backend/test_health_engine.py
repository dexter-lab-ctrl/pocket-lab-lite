from pocket_lab_test_utils import client, load_fixture


def test_health_engine_registered():
    assert client().get("/api/health-engine.json").status_code != 404


def test_health_fixture_supports_object_values():
    payload = load_fixture("health_vault_sealed.json")
    assert isinstance(payload["services"]["vault"], dict)
